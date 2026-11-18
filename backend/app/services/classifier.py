# ==============================================================================
# CLASSIFICADOR — lê o conn_live.log, calcula as features de janela de 10 s com o
# MESMO código do treino (ml/features.py), roda o modelo ativo e publica em
# app.services.state. Suporta troca de versão a quente (registry.json mudou?
# recarrega em ~2 s) e nunca derruba o modelo em uso se o novo falhar ao carregar.
# ==============================================================================
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app import config
from app.services import state

if str(config.PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(config.PROJECT_ROOT))
from ml import features as F      # noqa: E402
from ml import registry           # noqa: E402

_M = None                          # modelo em uso (dict) — substituído atomicamente
_lock_carga = threading.Lock()
_versao_falha = None               # versão que falhou ao carregar (não repetir a cada 2 s)

_MSG_NORMAL = "✔ Rede operando normalmente. Nenhuma anomalia detectada."
_ultimo_relatorio = _MSG_NORMAL
_ultima_assinatura = ""
_TAIL_BYTES = 4 * 1024 * 1024


# ------------------------------------------------------------------- modelo
def _resolver_modelo():
    if config.MODEL_PATH_OVERRIDE:
        return config.MODEL_PATH_OVERRIDE, 'override'
    registry.migrar_legado()
    v = registry.versao_ativa()
    return (registry.caminho_versao(v), v) if v else (None, None)


def carregar_modelo() -> bool:
    """(Re)carrega o modelo ativo. Em falha, mantém o modelo anterior (se houver)."""
    global _M, _versao_falha
    with _lock_carga:
        caminho, versao = _resolver_modelo()
        if caminho is None or not Path(caminho).exists():
            msg = ("Nenhum modelo disponível. Rode 'python ml/train.py' para treinar a primeira versão."
                   if caminho is None else f"Arquivo do modelo não encontrado: {caminho}")
            if _M is None:
                state.marcar_erro_modelo(msg)
            return False
        try:
            art = joblib.load(caminho)
            novo = {'pipeline': art['pipeline_xgb'], 'enc': art['codificador_y'],
                    'num': art['colunas_numericas'], 'cat': art['colunas_categoricas'], 'versao': versao}
        except Exception as e:
            _versao_falha = versao
            msg = (f"Falha ao carregar {versao} ({type(e).__name__}: {e}). Normalmente é incompatibilidade de "
                   f"versão de scikit-learn/xgboost entre o treino e o backend.")
            if _M is None:
                state.marcar_erro_modelo(msg)
            else:
                state.atualizar_estado({"erro_modelo": msg + f" Mantendo {_M['versao']} em uso."})
            return False
        _M, _versao_falha = novo, None
    upd = {"modelo_carregado": True, "erro_modelo": None, "modelo_versao": versao}
    if state.obter_estado()["status_rede"] in ("INICIALIZANDO", "ERRO_MODELO"):
        upd["status_rede"] = "NORMAL"
    state.atualizar_estado(upd)
    print(f"[CLASSIFIER] Modelo carregado: {versao}")
    return True


def versao_em_uso():
    return _M['versao'] if _M else None


def _verificar_troca_de_versao():
    if _M is None or config.MODEL_PATH_OVERRIDE:
        return
    ativa = registry.versao_ativa()
    if ativa and ativa != _M['versao'] and ativa != _versao_falha:
        carregar_modelo()


# ------------------------------------------------------------------- leitura / classificação
def _ler_conn_live():
    """Lê só o final do arquivo (o log cresce sem parar). Retorna (df, truncado)."""
    p = config.CONN_LOG_PATH
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame(), False
    try:
        tam = p.stat().st_size
        truncado = tam > _TAIL_BYTES
        if not truncado:
            return F.ler_conn_log(p), False
        with open(p, 'rb') as fh:
            fh.seek(tam - _TAIL_BYTES)
            fh.readline()                      # descarta linha cortada
            import io
            return F.ler_conn_log(io.StringIO(fh.read().decode('utf-8', errors='ignore'))), True
    except Exception as e:
        print(f"[CLASSIFIER] Erro ao ler conn_live.log: {e}")
        return pd.DataFrame(), False


def _payload_vazio(versao):
    global _ultima_assinatura, _ultimo_relatorio
    _ultima_assinatura, _ultimo_relatorio = "", _MSG_NORMAL
    return {"status_rede": "NORMAL", "total_fluxos_analisados": 0, "total_ataques_detectados": 0,
            "distribuicao_trafego": {}, "dispositivos_atacantes": [], "relatorio_llm": _MSG_NORMAL,
            "feed_tempo_real": [], "modelo_versao": versao}


def _processar_e_classificar(df_live: pd.DataFrame, truncado: bool, m: dict):
    df = F.preparar_janelas(df_live)               # MESMA função do treino
    if df.empty:
        return None
    if truncado:                                   # o bloco mais antigo pode estar cortado
        df = df[df['bloco_10s'] > df['bloco_10s'].min()]
    if not config.REPLAY:
        agora = time.time()
        b_max = int((agora - config.ATRASO_JANELA_S) // F.JANELA_S) - 1     # só janelas já fechadas
        b_min = int(agora // F.JANELA_S) - int(config.JANELA_HISTORICO_S // F.JANELA_S)
        df = df[(df['bloco_10s'] <= b_max) & (df['bloco_10s'] >= b_min)]
    df = df.reset_index(drop=True)
    if df.empty:
        return None

    X = F.montar_X(df, m['cat'], m['num'])
    probas = m['pipeline'].predict_proba(X)
    pred = probas.argmax(axis=1)
    conf = probas.max(axis=1).astype(float) * 100.0

    res = df[['ts', 'uid', 'id.orig_h', 'id.orig_p', 'id.resp_h', 'id.resp_p', 'proto', 'service', 'conn_state']].copy()
    res['tipo_trafego'] = m['enc'].inverse_transform(pred)
    res['confianca_ia'] = np.round(conf, 2)
    # Filtro 1: confiança mínima. O rótulo bruto do modelo continua em 'tipo_trafego'.
    res['status_geral'] = np.where(
        (res['tipo_trafego'] != 'Benigno') & (res['confianca_ia'] >= config.CONFIANCA_MINIMA_ATAQUE),
        'MALIGNO', 'BENIGNO')
    res['horario'] = res['ts'].apply(lambda x: datetime.fromtimestamp(x).strftime('%H:%M:%S'))
    return res


def _gerar_relatorio(lista):
    global _ultimo_relatorio, _ultima_assinatura
    if not lista:
        _ultima_assinatura, _ultimo_relatorio = "", _MSG_NORMAL
        return _ultimo_relatorio
    assinatura = "|".join(f"{d['ip_dispositivo']}:{d['tipo_ataque']}" for d in lista)
    if assinatura == _ultima_assinatura:
        return _ultimo_relatorio
    a = lista[0]
    _ultimo_relatorio = (
        f"[ALERTA SOC] Dispositivo IoT {a['ip_dispositivo']} comprometido executando "
        f"{a['tipo_ataque']} contra {a['ip_vitima']}:{a['porta_vitima']} "
        f"({a['fluxos_maliciosos']} fluxos, confiança de {a['confianca_ia_pct']}%).\n"
        f"• Mitigação sugerida (Windows): netsh advfirewall firewall add rule "
        f"name=\"Bloquear_{a['ip_dispositivo']}\" dir=in action=block remoteip={a['ip_dispositivo']}\n"
        f"• Mitigação sugerida (Linux): sudo iptables -A INPUT -s {a['ip_dispositivo']} -j DROP")
    _ultima_assinatura = assinatura
    return _ultimo_relatorio


def _montar_payload(res: pd.DataFrame, versao: str) -> dict:
    ataques = res[res['status_geral'] == 'MALIGNO']
    lista, total = [], 0
    if not ataques.empty:
        def moda(s):
            mo = s.mode()
            return mo.iloc[0] if not mo.empty else None
        resumo = (ataques.groupby(['id.orig_h', 'tipo_trafego'])
                  .agg(qtd=('uid', 'count'), alvo=('id.resp_h', moda), porta=('id.resp_p', moda),
                       conf=('confianca_ia', 'mean'), visto=('horario', 'max'))
                  .reset_index().sort_values('qtd', ascending=False))
        # Filtro 2: persistência mínima de fluxos por (dispositivo, tipo).
        resumo = resumo[resumo['qtd'] >= config.MIN_FLUXOS_PARA_ALERTA]
        for _, l in resumo.iterrows():
            porta = pd.to_numeric(l['porta'], errors='coerce')
            lista.append({'ip_dispositivo': str(l['id.orig_h']), 'tipo_ataque': str(l['tipo_trafego']),
                          'fluxos_maliciosos': int(l['qtd']), 'ip_vitima': str(l['alvo'] if l['alvo'] is not None else '-'),
                          'porta_vitima': 0 if pd.isna(porta) else int(porta),
                          'confianca_ia_pct': round(float(l['conf']), 1), 'ultimo_alerta': str(l['visto'])})
        total = sum(a['fluxos_maliciosos'] for a in lista)
    return {
        "status_rede": "SOB ATAQUE" if lista else "NORMAL",
        "total_fluxos_analisados": int(len(res)),
        "total_ataques_detectados": total,
        "distribuicao_trafego": {str(k): int(v) for k, v in res['tipo_trafego'].value_counts().items()},
        "dispositivos_atacantes": lista,
        "relatorio_llm": _gerar_relatorio(lista),
        "feed_tempo_real": res.sort_values('ts').tail(20).iloc[::-1].fillna('-').to_dict(orient='records'),
        "modelo_versao": versao,
    }


def _loop_classificacao(stop_event: threading.Event):
    carregar_modelo()
    ultima_tentativa = time.time()
    while not stop_event.is_set():
        try:
            _verificar_troca_de_versao()
            m = _M
            if m is None:
                if time.time() - ultima_tentativa > 10:   # permite treinar o 1º modelo com o backend já no ar
                    ultima_tentativa = time.time()
                    carregar_modelo()
            else:
                df_captura, truncado = _ler_conn_live()
                res = _processar_e_classificar(df_captura, truncado, m) if not df_captura.empty else None
                payload = _montar_payload(res, m['versao']) if res is not None else _payload_vazio(m['versao'])
                state.atualizar_estado(payload)
                if config.WRITE_DEBUG_JSON:
                    try:
                        with open(config.DEBUG_JSON_PATH, 'w', encoding='utf-8') as f:
                            json.dump(state.obter_estado(), f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
        except Exception as e:                     # o loop nunca deve morrer
            print(f"[CLASSIFIER] Erro no ciclo: {type(e).__name__}: {e}")
        stop_event.wait(2)


def iniciar_classificador_em_background(stop_event: threading.Event) -> threading.Thread:
    t = threading.Thread(target=_loop_classificacao, args=(stop_event,), daemon=True)
    t.start()
    return t