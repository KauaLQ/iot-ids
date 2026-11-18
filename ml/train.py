# ==============================================================================
# ml/train.py — Treinamento do motor de IA do IoT-IDS (IoT-23 + coletas próprias)
#
# Uso típico:
#   python ml/train.py                              # IoT-23 + coletas, salva nova versão
#   python ml/train.py --ativar-se-melhor           # só ativa se não piorar vs. a versão ativa
#   python ml/train.py --fontes coletas             # somente dados coletados do seu ambiente
#   python ml/train.py --peso-coleta 5 --nota "mais sessões do ESP32"
#
# Cada execução cria ml/models/model_vN.pkl + model_vN.json (métricas, dados,
# versões das libs). NADA é sobrescrito. Ativar/rollback: python ml/registry.py
# ==============================================================================
import argparse
import glob
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from ml import features as F        # noqa: E402
from ml import registry             # noqa: E402

MAPA_ATAQUES = {
    'Benign': 'Benigno', 'benign': 'Benigno',
    'PartOfAHorizontalPortScan': 'PortScan',
    'C&C-PartOfAHorizontalPortScan': 'PortScan', 'PortScan': 'PortScan',
    'Attack': 'Ataque_Generico',
    'C&C': 'C&C', 'C&C-HeartBeat': 'C&C', 'C&C-FileDownload': 'C&C',
    'C&C-HeartBeat-FileDownload': 'C&C', 'C&C-Torii': 'C&C', 'C&C-Mirai': 'C&C',
    'DDoS': 'DDoS', 'Okiru': 'Botnet_Okiru',
}


# ----------------------------------------------------------------------------- carga
def carregar_log_zeek(caminho: Path, max_linhas: int) -> pd.DataFrame:
    df = pd.read_csv(caminho, sep=r'\t|\s{2,}', comment='#', header=None, engine='python',
                     na_values=['-', '(empty)'], nrows=max_linhas)
    df.columns = F.COLUNAS_CONN_23
    df['arquivo_origem'] = caminho.name
    return df


def carregar_iot23(dataset_dir: Path, max_linhas: int) -> pd.DataFrame:
    arquivos = sorted(glob.glob(str(dataset_dir / "*labeled")))
    if not arquivos:
        print(f"[INFO] Nenhum '*.labeled' em '{dataset_dir}' — IoT-23 ignorado.")
        return pd.DataFrame()
    partes = []
    for a in arquivos:
        a = Path(a)
        print(f"[INFO] IoT-23: carregando {a.name} ...")
        try:
            partes.append(carregar_log_zeek(a, max_linhas))
        except Exception as e:
            print(f"[ERRO] Falha ao carregar '{a.name}': {e}")
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    df['label'] = df['label'].astype(str).str.strip().str.lower()
    df['detailed_label'] = df['detailed_label'].fillna('Benign').astype(str).str.strip()
    df['tipo_trafego'] = df['detailed_label'].map(lambda x: MAPA_ATAQUES.get(x, x))
    df.loc[df['label'] == 'benign', 'tipo_trafego'] = 'Benigno'
    df['origem'] = 'iot23'
    df['sessao'] = df['arquivo_origem']
    return df


def carregar_coletas(pasta: Path):
    """Cada sessão = pasta com conn.log + meta.json (criada pelo backend /api/coleta/*).
    Para excluir uma sessão ruim sem apagá-la: edite meta.json -> "ativa": false."""
    partes, sessoes = [], []
    for meta_path in sorted(pasta.glob('*/meta.json')):
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        log = meta_path.parent / 'conn.log'
        if not meta.get('ativa', True) or not log.exists() or log.stat().st_size == 0:
            continue
        df = F.ler_conn_log(log)
        if df.empty:
            continue
        df['arquivo_origem'] = meta['nome']
        df['sessao'] = meta['nome']
        df['tipo_trafego'] = meta['rotulo']
        df['origem'] = 'coleta'
        partes.append(df)
        sessoes.append({'nome': meta['nome'], 'rotulo': meta['rotulo'], 'fluxos': int(len(df)),
                        'ip_dispositivo': meta.get('ip_dispositivo'), 'descricao': meta.get('descricao', '')})
    if not partes:
        return pd.DataFrame(), []
    return pd.concat(partes, ignore_index=True), sessoes


# ----------------------------------------------------------------------------- split / balanceamento
def dividir_coletas(df: pd.DataFrame):
    """Hold-out HONESTO: janelas vizinhas da mesma sessão são quase idênticas, então
    sortear janelas aleatórias vaza informação e infla as métricas.
      - rótulo com >=2 sessões: a sessão mais recente inteira vai para teste;
      - rótulo com 1 sessão: últimos 20% do tempo vão para teste (com 1 bloco de folga)."""
    tr, te = [], []
    for rotulo, g in df.groupby('tipo_trafego'):
        sess = g.groupby('sessao')['ts'].min().sort_values().index.tolist()
        if len(sess) >= 2:
            m = g['sessao'] == sess[-1]
            te += g.index[m].tolist(); tr += g.index[~m].tolist()
        else:
            corte = int(g['bloco_10s'].quantile(0.8))
            m_te, m_tr = g['bloco_10s'] > corte, g['bloco_10s'] < corte
            if m_te.sum() == 0:
                print(f"[AVISO] '{rotulo}': dados insuficientes para teste — tudo foi para treino.")
                tr += g.index.tolist(); continue
            print(f"[AVISO] '{rotulo}' tem 1 sessão: teste = últimos 20% do tempo. Colete MAIS sessões "
                  f"(ideal >=3 por classe) para uma métrica confiável.")
            te += g.index[m_te].tolist(); tr += g.index[m_tr].tolist()
    return tr, te


def limitar_por_classe(df: pd.DataFrame, limite: int, seed: int) -> pd.DataFrame:
    partes = [g.sample(n=limite, random_state=seed) if len(g) > limite else g
              for _, g in df.groupby(['origem', 'tipo_trafego'])]
    return pd.concat(partes) if partes else df


# ----------------------------------------------------------------------------- avaliação
def _pred(art, X_full, chave):
    cols_c, cols_n = art['colunas_categoricas'], art['colunas_numericas']
    X = F.montar_X(X_full, cols_c, cols_n)
    probas = art[chave].predict_proba(X)
    idx = probas.argmax(axis=1)
    return art['codificador_y'].inverse_transform(idx), probas.max(axis=1) * 100.0


def avaliar(art, df_teste, chave='pipeline_xgb', limiar=75.0):
    y = df_teste['tipo_trafego'].to_numpy()
    nomes, conf = _pred(art, df_teste, chave)
    labels = sorted(set(y) | set(nomes))
    rel = classification_report(y, nomes, labels=labels, output_dict=True, zero_division=0)
    benigno = y == 'Benigno'
    alarme = (nomes != 'Benigno') & (conf >= limiar)
    def _m(mask, arr):
        return float(arr[mask].mean()) if mask.any() else None
    return {
        'n_teste': int(len(y)),
        'accuracy': float(accuracy_score(y, nomes)),
        'f1_macro': float(f1_score(y, nomes, labels=labels, average='macro', zero_division=0)),
        'f1_weighted': float(f1_score(y, nomes, labels=labels, average='weighted', zero_division=0)),
        'por_classe': {k: {m: float(v) for m, v in d.items()} for k, d in rel.items() if isinstance(d, dict)},
        # Métricas OPERACIONAIS (o que o dashboard realmente mostra, com o filtro de confiança):
        'limiar_confianca': limiar,
        'confianca_media_benigno': _m(benigno, conf),
        'confianca_media_ataque': _m(~benigno, conf),
        'falso_alarme_benigno_pct': None if _m(benigno, alarme) is None else _m(benigno, alarme) * 100,
        'deteccao_ataque_pct': None if _m(~benigno, alarme) is None else _m(~benigno, alarme) * 100,
    }


def _resumo_print(titulo, m):
    if not m:
        return
    f = lambda x: '  -  ' if x is None else f"{x:6.2f}"
    print(f"  {titulo:<26} acc={m['accuracy']:.4f}  F1-macro={m['f1_macro']:.4f}  | "
          f"conf.benigno={f(m['confianca_media_benigno'])}%  conf.ataque={f(m['confianca_media_ataque'])}%  "
          f"falso-alarme={f(m['falso_alarme_benigno_pct'])}%  detecção={f(m['deteccao_ataque_pct'])}%  (n={m['n_teste']})")


# ----------------------------------------------------------------------------- treino
def treinar(a):
    fontes = {s.strip() for s in a.fontes.split(',')}
    partes, sessoes = [], []
    if 'iot23' in fontes:
        d = carregar_iot23(a.dataset_dir, a.max_linhas)
        if not d.empty:
            partes.append(d)
    if 'coletas' in fontes:
        d, sessoes = carregar_coletas(a.coletas_dir)
        if not d.empty:
            partes.append(d)
            print(f"[INFO] {len(sessoes)} sessão(ões) de coleta: " + ', '.join(f"{s['nome']}({s['fluxos']})" for s in sessoes))
        else:
            print(f"[INFO] Nenhuma sessão de coleta em '{a.coletas_dir}'.")
    if not partes:
        sys.exit("[ERRO] Nenhum dado de treino disponível.")

    df = pd.concat(partes, ignore_index=True)
    # Janelas calculadas ANTES de qualquer amostragem, separadas por arquivo/sessão
    df = F.preparar_janelas(df, col_sessao='arquivo_origem')
    df = limitar_por_classe(df, a.limite_por_classe, a.seed).reset_index(drop=True)

    print("\n=== DISTRIBUIÇÃO (origem x classe) ===")
    print(df.groupby(['origem', 'tipo_trafego']).size().unstack(0, fill_value=0))
    if df['tipo_trafego'].nunique() < 2:
        sys.exit("[ERRO] É preciso ao menos 2 classes (ex.: Benigno + PortScan).")

    # --- split
    idx_tr, idx_te = [], []
    iot = df.index[df['origem'] == 'iot23']
    if len(iot):
        sub = df.loc[iot]
        sgk = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=a.seed)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            t, e = next(sgk.split(sub, sub['tipo_trafego'], groups=sub['id_janela_unica']))
        idx_tr += sub.index[t].tolist(); idx_te += sub.index[e].tolist()
    col = df.index[df['origem'] == 'coleta']
    if len(col):
        t, e = dividir_coletas(df.loc[col])
        idx_tr += t; idx_te += e
    df_tr, df_te = df.loc[idx_tr], df.loc[idx_te]
    if df_te.empty:
        sys.exit("[ERRO] Conjunto de teste vazio — colete mais dados.")

    enc = LabelEncoder().fit(df_tr['tipo_trafego'])
    y_tr = enc.transform(df_tr['tipo_trafego'])
    X_tr = F.montar_X(df_tr, F.COLUNAS_CATEGORICAS, F.COLUNAS_NUMERICAS)

    # --- pesos: dados coletados valem N vezes mais + balanceamento de classes
    w_origem = np.where(df_tr['origem'].to_numpy() == 'coleta', a.peso_coleta, 1.0)
    w_xgb = w_origem * compute_sample_weight('balanced', y_tr)

    prep = ColumnTransformer([
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), F.COLUNAS_CATEGORICAS),
        ('num', 'passthrough', F.COLUNAS_NUMERICAS),
    ])
    rf = Pipeline([('prep', prep), ('modelo', RandomForestClassifier(
        n_estimators=150, max_depth=15, class_weight='balanced', random_state=a.seed, n_jobs=-1))])
    xgb = Pipeline([('prep', prep), ('modelo', XGBClassifier(
        n_estimators=150, learning_rate=0.1, max_depth=6, eval_metric='mlogloss',
        random_state=a.seed, n_jobs=-1))])
    print("\n[INFO] Treinando Random Forest ...")
    rf.fit(X_tr, y_tr, modelo__sample_weight=w_origem)
    print("[INFO] Treinando XGBoost ...")
    xgb.fit(X_tr, y_tr, modelo__sample_weight=w_xgb)

    novo = {'pipeline_xgb': xgb, 'pipeline_rf': rf, 'codificador_y': enc,
            'colunas_numericas': F.COLUNAS_NUMERICAS, 'colunas_categoricas': F.COLUNAS_CATEGORICAS,
            'versao_features': F.VERSAO_FEATURES}

    # --- avaliação (mesmo conjunto de teste para o novo e para o ativo = comparação justa)
    print("\n=== AVALIAÇÃO NO CONJUNTO DE TESTE ===")
    m_rf = avaliar(novo, df_te, 'pipeline_rf', a.limiar)
    m_xgb = avaliar(novo, df_te, 'pipeline_xgb', a.limiar)
    _resumo_print('RandomForest', m_rf)
    _resumo_print('XGBoost (usado no backend)', m_xgb)
    te_col = df_te[df_te['origem'] == 'coleta']
    m_col = avaliar(novo, te_col, 'pipeline_xgb', a.limiar) if len(te_col) else None
    _resumo_print('XGBoost só coletas', m_col)
    print("\n--- Relatório por classe (XGBoost) ---")
    y_nomes = df_te['tipo_trafego'].to_numpy()
    nomes, _ = _pred(novo, df_te, 'pipeline_xgb')
    print(classification_report(y_nomes, nomes, digits=4, zero_division=0))

    comparacao = None
    ativo = None
    try:
        ativo = registry.carregar_ativo()
    except Exception as e:
        print(f"[AVISO] Não foi possível carregar a versão ativa para comparar ({e}).")
    if ativo is not None:
        v_at = registry.versao_ativa()
        try:
            c_all = avaliar(ativo, df_te, 'pipeline_xgb', a.limiar)
            c_col = avaliar(ativo, te_col, 'pipeline_xgb', a.limiar) if len(te_col) else None
            comparacao = {'versao': v_at, 'todos': c_all, 'so_coletas': c_col}
            print(f"=== COMPARAÇÃO NO MESMO TESTE: ativa ({v_at}) vs. NOVA ===")
            _resumo_print(f'{v_at} (ativa) — tudo', c_all); _resumo_print('NOVA — tudo', m_xgb)
            if c_col and m_col:
                _resumo_print(f'{v_at} (ativa) — coletas', c_col); _resumo_print('NOVA — coletas', m_col)
        except Exception as e:
            print(f"[AVISO] Comparação com a versão ativa falhou ({type(e).__name__}: {e}).")

    meta = {
        'nota': a.nota, 'metricas': {**m_xgb, 'so_coletas': m_col}, 'metricas_random_forest': m_rf,
        'comparacao_com_ativo': comparacao,
        'dados': {'fontes': sorted(fontes), 'n_treino': int(len(df_tr)), 'n_teste': int(len(df_te)),
                  'por_origem_classe': {f"{o}/{c}": int(n) for (o, c), n in df.groupby(['origem', 'tipo_trafego']).size().items()},
                  'sessoes': sessoes},
        'parametros': {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
        'features': {'versao': F.VERSAO_FEATURES, 'numericas': F.COLUNAS_NUMERICAS, 'categoricas': F.COLUNAS_CATEGORICAS},
        'classes': list(enc.classes_),
        'libs': {'python': sys.version.split()[0], 'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__,
                 'pandas': pd.__version__, 'numpy': np.__version__, 'joblib': joblib.__version__},
    }
    v = registry.registrar(novo, meta)
    print(f"\n[SUCESSO] Modelo salvo como {v}  (ml/models/model_{v}.pkl + .json). Classes: {list(enc.classes_)}")

    deve_ativar = a.ativar
    if a.ativar_se_melhor and not a.ativar:
        if comparacao is None:
            deve_ativar = True
            print("[INFO] Não havia versão ativa válida — ativando.")
        else:
            ok = m_xgb['f1_macro'] >= comparacao['todos']['f1_macro']
            if m_col and comparacao['so_coletas']:
                ok = ok and m_col['f1_macro'] >= comparacao['so_coletas']['f1_macro']
            deve_ativar = ok
            print("[INFO] Critério (F1-macro >= ativa, no mesmo teste): " + ("ATENDIDO" if ok else "NÃO atendido — versão ativa mantida."))
    if deve_ativar:
        registry.ativar(v)
        print(f"[INFO] {v} ATIVADA (backend recarrega em ~2 s). Reverter: python ml/registry.py rollback")
    else:
        print(f"[INFO] {v} NÃO está ativa. Para ativar: python ml/registry.py ativar {v}")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description="Treina o motor de IA do IoT-IDS (versionado).")
    p.add_argument('--dataset-dir', type=Path, default=PROJECT_ROOT / 'ml' / 'datasets')
    p.add_argument('--coletas-dir', type=Path, default=PROJECT_ROOT / 'ml' / 'datasets' / 'coletas')
    p.add_argument('--fontes', default='iot23,coletas', help="'iot23', 'coletas' ou 'iot23,coletas'")
    p.add_argument('--limite-por-classe', type=int, default=15000, help='teto de fluxos por (origem, classe)')
    p.add_argument('--peso-coleta', type=float, default=3.0, help='peso extra das amostras coletadas (ESP32/seu ambiente)')
    p.add_argument('--max-linhas', type=int, default=200_000, help='linhas lidas por arquivo IoT-23')
    p.add_argument('--limiar', type=float, default=75.0, help='limiar de confiança das métricas operacionais')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--ativar', action='store_true', help='ativa a nova versão ao final')
    p.add_argument('--ativar-se-melhor', action='store_true', help='ativa só se F1-macro >= versão ativa (mesmo teste)')
    p.add_argument('--nota', default='', help='comentário gravado nos metadados')
    treinar(p.parse_args())