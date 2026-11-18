# ==============================================================================
# ml/registry.py — versionamento de modelos + rollback.
#   ml/models/registry.json   -> versão ativa, histórico de ativações, resumo
#   ml/models/model_vN.pkl    -> artefato (joblib)
#   ml/models/model_vN.json   -> metadados completos (métricas, dados, libs)
# CLI:  python ml/registry.py listar | info vN | ativar vN | rollback | remover vN | comparar vA vB
# O backend detecta a troca em ~2 s (sem reiniciar).
# ==============================================================================
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / 'ml' / 'models'
REGISTRY_PATH = MODELS_DIR / 'registry.json'
LEGADO = MODELS_DIR / 'motor_ia_ids_iot.joblib'


def _vazio():
    return {"ativo": None, "historico": [], "versoes": {}}


def ler() -> dict:
    if not REGISTRY_PATH.exists():
        return _vazio()
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    except Exception:
        return _vazio()


def _gravar(reg: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, REGISTRY_PATH)  # atômico: o backend nunca lê um JSON pela metade


def _json_default(o):
    try:
        return float(o)
    except Exception:
        return str(o)


def versao_ativa():
    return ler().get('ativo')


def caminho_versao(v: str) -> Path:
    return MODELS_DIR / f"model_{v}.pkl"


def snapshot() -> dict:
    return ler()


def restaurar(snap: dict) -> None:
    _gravar(snap)


def _proximo_id(reg) -> str:
    nums = [int(k[1:]) for k in reg['versoes']] or [0]
    return f"v{max(nums) + 1}"


def registrar(artefato: dict, metadados: dict) -> str:
    reg = ler()
    v = _proximo_id(reg)
    joblib.dump({**artefato, 'versao': v}, caminho_versao(v), compress=3)
    meta = {**metadados, 'versao': v, 'arquivo': caminho_versao(v).name,
            'criado_em': datetime.now().isoformat(timespec='seconds')}
    (MODELS_DIR / f"model_{v}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=_json_default), encoding='utf-8')
    m = meta.get('metricas', {})
    reg['versoes'][v] = {
        'criado_em': meta['criado_em'], 'f1_macro': m.get('f1_macro'), 'accuracy': m.get('accuracy'),
        'f1_macro_coletas': (m.get('so_coletas') or {}).get('f1_macro'),
        'fontes': meta.get('dados', {}).get('fontes'), 'nota': meta.get('nota', ''),
    }
    if reg['ativo'] is None:
        reg['ativo'] = v
    _gravar(reg)
    return v


def ativar(v: str) -> None:
    reg = ler()
    if v not in reg['versoes'] or not caminho_versao(v).exists():
        raise ValueError(f"Versão '{v}' não existe. Disponíveis: {', '.join(reg['versoes']) or '(nenhuma)'}")
    if reg['ativo'] == v:
        return
    if reg['ativo']:
        reg['historico'].append(reg['ativo'])
    reg['ativo'] = v
    _gravar(reg)


def rollback() -> str:
    reg = ler()
    while reg['historico']:
        anterior = reg['historico'].pop()
        if anterior in reg['versoes'] and caminho_versao(anterior).exists():
            reg['ativo'] = anterior
            _gravar(reg)
            return anterior
    raise RuntimeError("Não há versão anterior para reverter.")


def remover(v: str) -> None:
    reg = ler()
    if reg['ativo'] == v:
        raise ValueError("Não é possível remover a versão ativa. Faça rollback/ative outra antes.")
    reg['versoes'].pop(v, None)
    reg['historico'] = [h for h in reg['historico'] if h != v]
    for p in (caminho_versao(v), MODELS_DIR / f"model_{v}.json"):
        p.unlink(missing_ok=True)
    _gravar(reg)


def carregar_ativo():
    v = versao_ativa()
    if not v or not caminho_versao(v).exists():
        return None
    return joblib.load(caminho_versao(v))


def migrar_legado() -> None:
    """Se existir o antigo motor_ia_ids_iot.joblib e nenhuma versão registrada, vira v1."""
    reg = ler()
    if reg['versoes'] or not LEGADO.exists():
        return
    shutil.copy2(LEGADO, caminho_versao('v1'))
    meta = {'versao': 'v1', 'arquivo': 'model_v1.pkl', 'nota': 'Importado de motor_ia_ids_iot.joblib (sem métricas registradas)',
            'criado_em': datetime.fromtimestamp(LEGADO.stat().st_mtime).isoformat(timespec='seconds'), 'metricas': {}}
    (MODELS_DIR / 'model_v1.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    reg['versoes']['v1'] = {'criado_em': meta['criado_em'], 'nota': meta['nota'], 'f1_macro': None, 'accuracy': None}
    reg['ativo'] = 'v1'
    _gravar(reg)


# ----------------------------------------------------------------------------- CLI
def _fmt(x, nd=4):
    return '   -  ' if x is None else f"{x:.{nd}f}"


def _cli_listar():
    migrar_legado()
    reg = ler()
    if not reg['versoes']:
        print("Nenhuma versão registrada. Rode: python ml/train.py")
        return
    print(f"{'':2}{'versão':<8}{'criado em':<21}{'F1-macro':>9}{'acc':>9}{'F1 coletas':>11}  nota")
    for v in sorted(reg['versoes'], key=lambda s: int(s[1:])):
        d = reg['versoes'][v]
        marca = '→ ' if v == reg['ativo'] else '  '
        print(f"{marca}{v:<8}{d.get('criado_em', ''):<21}{_fmt(d.get('f1_macro')):>9}{_fmt(d.get('accuracy')):>9}"
              f"{_fmt(d.get('f1_macro_coletas')):>11}  {d.get('nota', '')}")
    print(f"\nAtiva: {reg['ativo']}   |   Histórico p/ rollback: {reg['historico'] or '(vazio)'}")


def main():
    p = argparse.ArgumentParser(description="Gerencia versões de modelos do IoT-IDS.")
    sp = p.add_subparsers(dest='cmd', required=True)
    sp.add_parser('listar')
    for nome in ('info', 'ativar', 'remover'):
        sp.add_parser(nome).add_argument('versao')
    sp.add_parser('rollback')
    c = sp.add_parser('comparar'); c.add_argument('a'); c.add_argument('b')
    a = p.parse_args()
    try:
        if a.cmd == 'listar':
            _cli_listar()
        elif a.cmd == 'info':
            print((MODELS_DIR / f"model_{a.versao}.json").read_text(encoding='utf-8'))
        elif a.cmd == 'ativar':
            migrar_legado(); ativar(a.versao); print(f"Versão ativa: {a.versao} (o backend recarrega em ~2 s)")
        elif a.cmd == 'rollback':
            print(f"Rollback concluído. Versão ativa: {rollback()} (o backend recarrega em ~2 s)")
        elif a.cmd == 'remover':
            remover(a.versao); print(f"{a.versao} removida.")
        elif a.cmd == 'comparar':
            reg = ler()['versoes']
            print("ATENÇÃO: métricas de versões diferentes vêm de conjuntos de teste diferentes.\n"
                  "Para comparação justa use a seção 'comparacao_com_ativo' impressa pelo train.py.\n")
            for v in (a.a, a.b):
                d = reg.get(v, {})
                print(f"{v}: F1-macro={_fmt(d.get('f1_macro'))} acc={_fmt(d.get('accuracy'))} F1(coletas)={_fmt(d.get('f1_macro_coletas'))}")
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"ERRO: {e}"); sys.exit(1)


if __name__ == '__main__':
    main()