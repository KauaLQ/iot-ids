# ==============================================================================
# ml/diagnostico.py — compara DISTRIBUIÇÕES (a causa-raiz do training-serving skew).
#   python ml/diagnostico.py --log backend/runtime_data/conn_live.log
#   python ml/diagnostico.py --sessoes                 # todas as sessões coletadas
#   python ml/diagnostico.py --iot23 --max-linhas 50000
# Mostra, por origem/classe: mediana das features de janela e proporção de
# conn_state / service / orig_bytes==0. Se "Benigno do ESP32" e "Benigno do IoT-23"
# estiverem muito diferentes, o modelo vai ficar incerto (~50% de confiança).
# ==============================================================================
import argparse
import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ml import features as F  # noqa: E402

pd.set_option('display.width', 200, 'display.max_columns', 30)


def resumo(df, grupo):
    df = F.preparar_janelas(df, col_sessao='arquivo_origem')
    jan = df.drop_duplicates('id_janela_unica')
    print("\n=== Features de janela (mediana | p90) por", grupo, "===")
    cols = ['win_qtd_conexoes', 'win_ips_destino_unicos', 'win_portas_destino_unicas',
            'win_media_orig_bytes', 'win_taxa_s0', 'win_taxa_falha']
    p50 = jan.groupby(grupo)[cols].median().add_suffix('.p50')
    p90 = jan.groupby(grupo)[cols].quantile(0.9).add_suffix('.p90')
    agg = pd.concat([p50, p90], axis=1).sort_index(axis=1)
    print(agg.round(2).to_string())
    print("\n=== conn_state (%) ===")
    print((pd.crosstab(df[grupo], df['conn_state'].fillna('NA'), normalize='index') * 100).round(1).to_string())
    print("\n=== service (%) ===")
    print((pd.crosstab(df[grupo], df['service'].fillna('-'), normalize='index') * 100).round(1).to_string())
    ob = pd.to_numeric(df['orig_bytes'], errors='coerce').fillna(0)
    print("\n=== % fluxos com orig_bytes == 0 ===")
    print((ob.eq(0).groupby(df[grupo]).mean() * 100).round(1).to_string())


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--log'); p.add_argument('--sessoes', action='store_true')
    p.add_argument('--iot23', action='store_true'); p.add_argument('--max-linhas', type=int, default=50000)
    a = p.parse_args()
    partes = []
    if a.log:
        d = F.ler_conn_log(a.log); d['arquivo_origem'] = 'conn_live'; d['grupo'] = 'conn_live.log'; partes.append(d)
    if a.sessoes:
        for m in sorted((ROOT / 'ml/datasets/coletas').glob('*/meta.json')):
            meta = json.loads(m.read_text(encoding='utf-8')); lg = m.parent / 'conn.log'
            if lg.exists() and lg.stat().st_size:
                d = F.ler_conn_log(lg); d['arquivo_origem'] = meta['nome']; d['grupo'] = f"coleta/{meta['rotulo']}"; partes.append(d)
    if a.iot23:
        sys.path.insert(0, str(ROOT / 'ml'))
        import train
        d = train.carregar_iot23(ROOT / 'ml/datasets', a.max_linhas)
        if not d.empty:
            d['grupo'] = 'iot23/' + d['tipo_trafego']; partes.append(d)
    if not partes:
        sys.exit("Informe --log, --sessoes e/ou --iot23")
    resumo(pd.concat(partes, ignore_index=True), 'grupo')