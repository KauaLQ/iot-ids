# ==============================================================================
# CLASSIFICADOR — lê o conn_live.log, recalcula as mesmas features de janela
# de 10s usadas no treinamento (ml/train.py), roda o modelo e publica o
# resultado em app.services.state (memória, consumido pela API).
# ==============================================================================
import json
import threading
import time
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from app import config
from app.services import state

COLUNAS_CONN_22 = [
    'ts', 'uid', 'id.orig_h', 'id.orig_p', 'id.resp_h', 'id.resp_p',
    'proto', 'service', 'duration', 'orig_bytes', 'resp_bytes',
    'conn_state', 'local_orig', 'local_resp', 'missed_bytes',
    'history', 'orig_pkts', 'orig_ip_bytes', 'resp_pkts',
    'resp_ip_bytes', 'tunnel_parents', 'ip_proto',
]

_modelo_ativo = None
_codificador_y = None
_colunas_numericas = None
_colunas_categoricas = None

_ultimo_relatorio = "✔ Rede operando normalmente. Nenhuma anomalia detectada."
_ultima_assinatura = ""


def carregar_modelo() -> bool:
    """Carrega o .joblib com tratamento de erro explícito. Retorna False (sem
    derrubar o backend) se o arquivo não existir ou estiver corrompido/
    incompatível com a versão instalada de scikit-learn/xgboost — nesse caso
    a causa mais comum é treinar e rodar com requirements.txt diferentes."""
    global _modelo_ativo, _codificador_y, _colunas_numericas, _colunas_categoricas

    if not config.MODEL_PATH.exists():
        state.marcar_erro_modelo(
            f"Modelo não encontrado em {config.MODEL_PATH}. "
            f"Rode 'python ml/train.py' primeiro para gerá-lo."
        )
        return False

    try:
        artefato = joblib.load(config.MODEL_PATH)
        _modelo_ativo = artefato['pipeline_xgb']
        _codificador_y = artefato['codificador_y']
        _colunas_numericas = artefato['colunas_numericas']
        _colunas_categoricas = artefato['colunas_categoricas']
    except Exception as e:
        state.marcar_erro_modelo(
            f"Falha ao carregar o modelo ({type(e).__name__}: {e}). "
            f"Normalmente é incompatibilidade de versão entre o ambiente que "
            f"treinou o modelo e este aqui — reinstale com o requirements.txt "
            f"da raiz do projeto e retreine com 'python ml/train.py'."
        )
        return False

    state.atualizar_estado({"modelo_carregado": True, "erro_modelo": None, "status_rede": "NORMAL"})
    return True


def _ler_conn_live(ultimas_n_linhas: int = 5000) -> pd.DataFrame:
    caminho = config.CONN_LOG_PATH
    if not caminho.exists() or caminho.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(
            caminho, sep='\t', comment='#', names=COLUNAS_CONN_22,
            index_col=False, na_values=['-', '(empty)'], on_bad_lines='skip', low_memory=False,
        )
    except Exception as e:
        print(f"[CLASSIFIER] Erro ao ler conn_live.log: {e}")
        return pd.DataFrame()
    return df.tail(ultimas_n_linhas).reset_index(drop=True) if len(df) > ultimas_n_linhas else df


def _processar_e_classificar(df_live: pd.DataFrame):
    df_live['ts'] = pd.to_numeric(df_live['ts'], errors='coerce')
    df_live = df_live.dropna(subset=['ts', 'id.orig_h', 'id.resp_h']).reset_index(drop=True)
    if df_live.empty:
        return None

    df_live = df_live.sort_values(by=['id.orig_h', 'ts']).reset_index(drop=True)
    df_live['bloco_10s'] = (df_live['ts'] // 10).astype(np.int64)
    df_live['orig_bytes_temp'] = pd.to_numeric(df_live['orig_bytes'], errors='coerce').fillna(0.0)
    df_live['flag_s0_temp'] = df_live['conn_state'].isin(['S0', 'REJ', 'RSTO', 'RSTOS0']).astype(float)
    df_live.loc[df_live['conn_state'] == 'REJ', 'conn_state'] = 'S0'

    grupo = df_live.groupby(['id.orig_h', 'bloco_10s'])
    df_live['win_qtd_conexoes'] = grupo['uid'].transform('count')
    df_live['win_ips_destino_unicos'] = grupo['id.resp_h'].transform('nunique')
    df_live['win_portas_destino_unicas'] = grupo['id.resp_p'].transform('nunique')
    df_live['win_media_orig_bytes'] = grupo['orig_bytes_temp'].transform('mean')
    df_live['win_taxa_s0'] = grupo['flag_s0_temp'].transform('mean')

    metadados = df_live[['ts', 'uid', 'id.orig_h', 'id.orig_p', 'id.resp_h', 'id.resp_p', 'proto', 'service']].copy()

    X = df_live[_colunas_categoricas + _colunas_numericas].copy()
    X[_colunas_numericas] = X[_colunas_numericas].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    X[_colunas_categoricas] = X[_colunas_categoricas].fillna('desconhecido').astype(str)

    pred_num = _modelo_ativo.predict(X)
    probas = _modelo_ativo.predict_proba(X)
    confianca = np.max(probas, axis=1) * 100.0
    nomes = _codificador_y.inverse_transform(pred_num)

    metadados['tipo_trafego'] = nomes
    metadados['confianca_ia'] = np.round(confianca, 2)
    # FILTRO 1 (confiança mínima): uma previsão "quase no chute" (ex.: 55%)
    # não deve acender alarme. Abaixo do limiar, tratamos como BENIGNO para
    # fins de alerta — o rótulo bruto do modelo continua disponível em
    # 'tipo_trafego' para quem quiser auditar.
    metadados['status_geral'] = np.where(
        (metadados['tipo_trafego'] != 'Benigno') & (metadados['confianca_ia'] >= config.CONFIANCA_MINIMA_ATAQUE),
        'MALIGNO', 'BENIGNO',
    )
    metadados['horario'] = metadados['ts'].apply(lambda x: datetime.fromtimestamp(x).strftime('%H:%M:%S'))
    return metadados


def _gerar_relatorio(lista_atacantes):
    global _ultimo_relatorio, _ultima_assinatura
    if not lista_atacantes:
        _ultima_assinatura = ""
        _ultimo_relatorio = "✔ Rede operando normalmente. Nenhuma anomalia detectada."
        return _ultimo_relatorio

    assinatura = "|".join(f"{d['ip_dispositivo']}:{d['tipo_ataque']}" for d in lista_atacantes)
    if assinatura == _ultima_assinatura:
        return _ultimo_relatorio

    a = lista_atacantes[0]
    _ultimo_relatorio = (
        f"[ALERTA SOC] Dispositivo IoT {a['ip_dispositivo']} comprometido executando "
        f"{a['tipo_ataque']} contra {a['ip_vitima']}:{a['porta_vitima']} "
        f"({a['fluxos_maliciosos']} fluxos, confiança de {a['confianca_ia_pct']}%).\n"
        f"• Mitigação sugerida (Windows): netsh advfirewall firewall add rule "
        f"name=\"Bloquear_{a['ip_dispositivo']}\" dir=in action=block remoteip={a['ip_dispositivo']}\n"
        f"• Mitigação sugerida (Linux): sudo iptables -A INPUT -s {a['ip_dispositivo']} -j DROP"
    )
    _ultima_assinatura = assinatura
    return _ultimo_relatorio


def _montar_payload(df_resultado: pd.DataFrame) -> dict:
    ataques = df_resultado[df_resultado['status_geral'] == 'MALIGNO'].copy()
    lista_atacantes = []
    total_ataques_confirmados = 0

    if not ataques.empty:
        resumo = (
            ataques.groupby(['id.orig_h', 'tipo_trafego'])
            .agg(qtd_conexoes=('uid', 'count'),
                 ip_alvo_principal=('id.resp_h', lambda s: s.mode().iloc[0] if not s.mode().empty else '-'),
                 porta_alvo=('id.resp_p', lambda s: int(s.mode().iloc[0]) if not s.mode().empty and pd.notna(s.mode().iloc[0]) else 0),
                 confianca_media=('confianca_ia', 'mean'),
                 ultimo_visto=('horario', 'max'))
            .reset_index().sort_values(by='qtd_conexoes', ascending=False)
        )
        # FILTRO 2 (persistência mínima): descarta grupos com poucos fluxos
        # isolados (ex.: 1-2 conexões de um serviço de nuvem legítimo que deu
        # uma rajada assimétrica). Um ataque de verdade (scan, flood,
        # brute-force) gera MUITOS fluxos na mesma janela, então esse corte
        # não compromete a detecção real.
        resumo = resumo[resumo['qtd_conexoes'] >= config.MIN_FLUXOS_PARA_ALERTA]

        for _, linha in resumo.iterrows():
            lista_atacantes.append({
                'ip_dispositivo': str(linha['id.orig_h']), 'tipo_ataque': str(linha['tipo_trafego']),
                'fluxos_maliciosos': int(linha['qtd_conexoes']), 'ip_vitima': str(linha['ip_alvo_principal']),
                'porta_vitima': int(linha['porta_alvo']), 'confianca_ia_pct': round(float(linha['confianca_media']), 1),
                'ultimo_alerta': str(linha['ultimo_visto']),
            })
        total_ataques_confirmados = sum(a['fluxos_maliciosos'] for a in lista_atacantes)

    return {
        "status_rede": "SOB ATAQUE" if lista_atacantes else "NORMAL",
        "total_fluxos_analisados": int(len(df_resultado)),
        "total_ataques_detectados": total_ataques_confirmados,
        "distribuicao_trafego": {str(k): int(v) for k, v in df_resultado['tipo_trafego'].value_counts().to_dict().items()},
        "dispositivos_atacantes": lista_atacantes,
        "relatorio_llm": _gerar_relatorio(lista_atacantes),
        "feed_tempo_real": df_resultado.tail(20).iloc[::-1].fillna('-').to_dict(orient='records'),
    }


def _loop_classificacao(stop_event: threading.Event):
    if not carregar_modelo():
        return  # erro já registrado em state; a API reporta modelo_carregado=False

    while not stop_event.is_set():
        df_captura = _ler_conn_live()
        if not df_captura.empty:
            df_classificado = _processar_e_classificar(df_captura)
            if df_classificado is not None:
                payload = _montar_payload(df_classificado)
                state.atualizar_estado(payload)
                if config.WRITE_DEBUG_JSON:
                    try:
                        with open(config.DEBUG_JSON_PATH, 'w', encoding='utf-8') as f:
                            json.dump(state.obter_estado(), f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
        time.sleep(2)


def iniciar_classificador_em_background(stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(target=_loop_classificacao, args=(stop_event,), daemon=True)
    thread.start()
    return thread