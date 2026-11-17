# ==============================================================================
# ml/train.py — Treinamento do motor de IA do IoT-IDS (IoT-23 dataset)
# Conversão do notebook original para script, com caminhos portáveis
# (pathlib) e parâmetros via linha de comando.
#
# Uso:
#   python ml/train.py
#   python ml/train.py --dataset-dir ml/datasets --out ml/models/motor_ia_ids_iot.joblib
#
# IMPORTANTE: use o MESMO requirements.txt (raiz do projeto) para treinar e
# para rodar o backend. Treinar com uma versão de scikit-learn/xgboost e
# rodar a inferência com outra é a causa mais comum de erro de "joblib
# corrompido" ao carregar o modelo.
# ==============================================================================
import argparse
import glob
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MAPA_ATAQUES = {
    'Benign': 'Benigno', 'benign': 'Benigno',
    'PartOfAHorizontalPortScan': 'PortScan',
    'C&C-PartOfAHorizontalPortScan': 'PortScan', 'PortScan': 'PortScan',
    'Attack': 'Ataque_Generico',
    'C&C': 'C&C', 'C&C-HeartBeat': 'C&C', 'C&C-FileDownload': 'C&C',
    'C&C-HeartBeat-FileDownload': 'C&C', 'C&C-Torii': 'C&C', 'C&C-Mirai': 'C&C',
    'DDoS': 'DDoS', 'Okiru': 'Botnet_Okiru',
}

COLUNAS_CONN_23 = [
    'ts', 'uid', 'id.orig_h', 'id.orig_p', 'id.resp_h', 'id.resp_p',
    'proto', 'service', 'duration', 'orig_bytes', 'resp_bytes',
    'conn_state', 'local_orig', 'local_resp', 'missed_bytes',
    'history', 'orig_pkts', 'orig_ip_bytes', 'resp_pkts',
    'resp_ip_bytes', 'tunnel_parents', 'label', 'detailed_label',
]

COLUNAS_NUMERICAS = [
    'duration', 'orig_bytes', 'resp_bytes', 'missed_bytes',
    'orig_pkts', 'orig_ip_bytes', 'resp_pkts', 'resp_ip_bytes',
    'win_qtd_conexoes', 'win_ips_destino_unicos', 'win_portas_destino_unicas',
    'win_media_orig_bytes', 'win_taxa_s0',
]
COLUNAS_CATEGORICAS = ['proto', 'service', 'conn_state']

COLUNAS_PROIBIDAS_LEAKAGE = [
    'arquivo_origem', 'id_janela_unica', 'ts', 'uid', 'id.orig_h', 'id.resp_h',
    'id.orig_p', 'id.resp_p', 'local_orig', 'local_resp', 'tunnel_parents',
    'history', 'label', 'detailed_label', 'tipo_trafego',
]


def carregar_log_zeek(caminho_arquivo: Path, max_linhas: int = 200_000) -> pd.DataFrame:
    df = pd.read_csv(
        caminho_arquivo, sep=r'\t|\s{2,}', comment='#', header=None, engine='python',
        na_values=['-', '(empty)'], nrows=max_linhas,
    )
    df.columns = COLUNAS_CONN_23
    df["arquivo_origem"] = caminho_arquivo.name
    return df


def carregar_dataset(dataset_dir: Path) -> pd.DataFrame:
    arquivos = sorted(glob.glob(str(dataset_dir / "*labeled")))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo '.labeled' encontrado em '{dataset_dir}'.")

    print(f"[INFO] {len(arquivos)} arquivo(s) encontrado(s) em '{dataset_dir}'.")
    partes = []
    for caminho in arquivos:
        caminho = Path(caminho)
        print(f"[INFO] Carregando: {caminho.name} ...")
        try:
            partes.append(carregar_log_zeek(caminho))
        except Exception as e:
            print(f"[ERRO] Falha ao carregar '{caminho.name}': {e}")

    df_bruto = pd.concat(partes, ignore_index=True)
    print(df_bruto['arquivo_origem'].value_counts())
    return df_bruto


def rotular_e_mapear(df_bruto: pd.DataFrame) -> pd.DataFrame:
    df_bruto['label'] = df_bruto['label'].astype(str).str.strip().str.lower()
    df_bruto['detailed_label'] = df_bruto['detailed_label'].fillna('Benign').astype(str).str.strip()
    df_bruto['tipo_trafego'] = df_bruto['detailed_label'].map(lambda x: MAPA_ATAQUES.get(x, x))
    df_bruto.loc[df_bruto['label'] == 'benign', 'tipo_trafego'] = 'Benigno'
    return df_bruto


def calcular_features_de_janela(df_bruto: pd.DataFrame) -> pd.DataFrame:
    df_bruto['ts'] = pd.to_numeric(df_bruto['ts'], errors='coerce')
    df_bruto = df_bruto.dropna(subset=['ts']).reset_index(drop=True)
    df_bruto = df_bruto.sort_values(by=['arquivo_origem', 'id.orig_h', 'ts']).reset_index(drop=True)

    bloco_10s = (df_bruto['ts'] // 10).astype(np.int64)
    df_bruto['id_janela_unica'] = (
        df_bruto['arquivo_origem'].astype(str) + "_" +
        df_bruto['id.orig_h'].astype(str) + "_" + bloco_10s.astype(str)
    )

    df_bruto['orig_bytes_temp'] = pd.to_numeric(df_bruto['orig_bytes'], errors='coerce').fillna(0.0)
    df_bruto['flag_s0_temp'] = (df_bruto['conn_state'] == 'S0').astype(float)

    grupo = df_bruto.groupby('id_janela_unica')
    df_bruto['win_qtd_conexoes'] = grupo['uid'].transform('count')
    df_bruto['win_ips_destino_unicos'] = grupo['id.resp_h'].transform('nunique')
    df_bruto['win_portas_destino_unicas'] = grupo['id.resp_p'].transform('nunique')
    df_bruto['win_media_orig_bytes'] = grupo['orig_bytes_temp'].transform('mean')
    df_bruto['win_taxa_s0'] = grupo['flag_s0_temp'].transform('mean')

    return df_bruto.drop(columns=['orig_bytes_temp', 'flag_s0_temp'])


def balancear_classes(df: pd.DataFrame, limite_por_classe: int, seed: int) -> pd.DataFrame:
    indices = []
    for _, grupo in df.groupby('tipo_trafego'):
        qtd = min(len(grupo), limite_por_classe)
        indices.extend(grupo.sample(n=qtd, random_state=seed).index)
    return df.loc[indices].sample(frac=1.0, random_state=seed).reset_index(drop=True)


def treinar(dataset_dir: Path, saida_modelo: Path, limite_por_classe: int, seed: int):
    df_bruto = carregar_dataset(dataset_dir)
    df_bruto = rotular_e_mapear(df_bruto)
    df_bruto = calcular_features_de_janela(df_bruto)
    df_balanceado = balancear_classes(df_bruto, limite_por_classe, seed)

    print("\n=== DISTRIBUIÇÃO DAS CLASSES APÓS PREPARAÇÃO ===")
    print(df_balanceado['tipo_trafego'].value_counts())

    grupos_janela = df_balanceado['id_janela_unica'].copy()
    X = df_balanceado.drop(columns=COLUNAS_PROIBIDAS_LEAKAGE).copy()
    codificador_y = LabelEncoder()
    y = codificador_y.fit_transform(df_balanceado['tipo_trafego'])

    X[COLUNAS_NUMERICAS] = X[COLUNAS_NUMERICAS].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    X[COLUNAS_CATEGORICAS] = X[COLUNAS_CATEGORICAS].fillna('desconhecido').astype(str)

    divisor = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    idx_treino, idx_teste = next(divisor.split(X, y, groups=grupos_janela))
    X_train, X_test = X.iloc[idx_treino].copy(), X.iloc[idx_teste].copy()
    y_train, y_test = y[idx_treino], y[idx_teste]

    preprocessador = ColumnTransformer(transformers=[
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), COLUNAS_CATEGORICAS),
        ('num', 'passthrough', COLUNAS_NUMERICAS),
    ])

    pipeline_rf = Pipeline(steps=[
        ('prep', preprocessador),
        ('modelo', RandomForestClassifier(n_estimators=150, max_depth=15,
                                           class_weight='balanced', random_state=seed, n_jobs=-1)),
    ])
    pipeline_xgb = Pipeline(steps=[
        ('prep', preprocessador),
        ('modelo', XGBClassifier(n_estimators=150, learning_rate=0.1, max_depth=6,
                                  eval_metric='mlogloss', random_state=seed, n_jobs=-1)),
    ])

    print("\n[INFO] Treinando Random Forest...")
    pipeline_rf.fit(X_train, y_train)
    print(classification_report(y_test, pipeline_rf.predict(X_test),
                                 target_names=codificador_y.classes_, digits=4))

    print("\n[INFO] Treinando XGBoost...")
    pipeline_xgb.fit(X_train, y_train)
    print(classification_report(y_test, pipeline_xgb.predict(X_test),
                                 target_names=codificador_y.classes_, digits=4))

    saida_modelo.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        'pipeline_xgb': pipeline_xgb, 'pipeline_rf': pipeline_rf,
        'codificador_y': codificador_y,
        'colunas_numericas': COLUNAS_NUMERICAS, 'colunas_categoricas': COLUNAS_CATEGORICAS,
    }, saida_modelo, compress=3)

    print(f"\n[SUCESSO] Modelo exportado para '{saida_modelo}'!")
    print(f"[INFO] Classes suportadas: {list(codificador_y.classes_)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Treina o motor de IA do IoT-IDS.")
    parser.add_argument('--dataset-dir', type=Path, default=PROJECT_ROOT / 'ml' / 'datasets')
    parser.add_argument('--out', type=Path, default=PROJECT_ROOT / 'ml' / 'models' / 'motor_ia_ids_iot.joblib')
    parser.add_argument('--limite-por-classe', type=int, default=15000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    treinar(args.dataset_dir, args.out, args.limite_por_classe, args.seed)
