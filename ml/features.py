# ==============================================================================
# ml/features.py — FONTE ÚNICA da engenharia de features.
# Treino (ml/train.py) e inferência (backend/app/services/classifier.py) usam
# EXATAMENTE este código. Isso elimina o training-serving skew por construção:
# antes, o treino marcava S0 só com conn_state == 'S0' e o classificador usava
# {S0, REJ, RSTO, RSTOS0} e ainda reescrevia REJ->S0 na entrada do modelo.
# ==============================================================================
import numpy as np
import pandas as pd

JANELA_S = 10
VERSAO_FEATURES = 2

COLUNAS_CONN_22 = [
    'ts', 'uid', 'id.orig_h', 'id.orig_p', 'id.resp_h', 'id.resp_p',
    'proto', 'service', 'duration', 'orig_bytes', 'resp_bytes',
    'conn_state', 'local_orig', 'local_resp', 'missed_bytes',
    'history', 'orig_pkts', 'orig_ip_bytes', 'resp_pkts',
    'resp_ip_bytes', 'tunnel_parents', 'ip_proto',
]
COLUNAS_CONN_23 = COLUNAS_CONN_22[:21] + ['label', 'detailed_label']  # formato .labeled do IoT-23

# Estados Zeek que representam "tentativa que não virou conversa normal".
CONN_FALHA = frozenset({'S0', 'REJ', 'RSTO', 'RSTOS0', 'RSTRH', 'SH'})

COLUNAS_NUMERICAS = [
    'duration', 'orig_bytes', 'resp_bytes', 'missed_bytes',
    'orig_pkts', 'orig_ip_bytes', 'resp_pkts', 'resp_ip_bytes',
    'win_qtd_conexoes', 'win_ips_destino_unicos', 'win_portas_destino_unicas',
    'win_media_orig_bytes', 'win_taxa_s0', 'win_taxa_falha',
]
COLUNAS_CATEGORICAS = ['proto', 'service', 'conn_state']


def ler_conn_log(caminho, **kw) -> pd.DataFrame:
    """Lê o conn_live.log do sniffer / conn.log de sessões de coleta (22 colunas)."""
    return pd.read_csv(
        caminho, sep='\t', comment='#', names=COLUNAS_CONN_22, index_col=False,
        na_values=['-', '(empty)'], on_bad_lines='skip', low_memory=False, **kw,
    )


def preparar_janelas(df: pd.DataFrame, col_sessao: str | None = None) -> pd.DataFrame:
    """Cria bloco_10s, id_janela_unica e as features win_*.
    col_sessao: no treino, coluna que separa arquivos/sessões (para que janelas
    de capturas diferentes nunca se misturem). Na inferência, None."""
    df = df.copy()
    df['ts'] = pd.to_numeric(df['ts'], errors='coerce')
    df = df.dropna(subset=['ts', 'id.orig_h', 'id.resp_h']).reset_index(drop=True)
    if df.empty:
        return df
    df = df.sort_values(by=([col_sessao] if col_sessao else []) + ['id.orig_h', 'ts']).reset_index(drop=True)

    df['bloco_10s'] = (df['ts'] // JANELA_S).astype(np.int64)
    idj = df['id.orig_h'].astype(str) + '_' + df['bloco_10s'].astype(str)
    if col_sessao:
        idj = df[col_sessao].astype(str) + '_' + idj
    df['id_janela_unica'] = idj

    df['_ob'] = pd.to_numeric(df['orig_bytes'], errors='coerce').fillna(0.0)
    df['_s0'] = (df['conn_state'] == 'S0').astype(float)
    df['_falha'] = df['conn_state'].isin(CONN_FALHA).astype(float)

    g = df.groupby('id_janela_unica')
    df['win_qtd_conexoes'] = g['ts'].transform('size')
    df['win_ips_destino_unicos'] = g['id.resp_h'].transform('nunique')
    df['win_portas_destino_unicas'] = g['id.resp_p'].transform('nunique')
    df['win_media_orig_bytes'] = g['_ob'].transform('mean')
    df['win_taxa_s0'] = g['_s0'].transform('mean')
    df['win_taxa_falha'] = g['_falha'].transform('mean')
    return df.drop(columns=['_ob', '_s0', '_falha'])


def montar_X(df: pd.DataFrame, colunas_cat, colunas_num) -> pd.DataFrame:
    """Mesmo tratamento de nulos no treino e na inferência."""
    X = df[list(colunas_cat) + list(colunas_num)].copy()
    X[list(colunas_num)] = X[list(colunas_num)].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    X[list(colunas_cat)] = X[list(colunas_cat)].fillna('desconhecido').astype(str)
    return X