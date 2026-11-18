# ==============================================================================
# COLETA ROTULADA — grava os flows do sniffer em ml/datasets/coletas/<sessão>/
#   conn.log   (mesmas 22 colunas do conn_live.log)
#   meta.json  (rótulo, IP do dispositivo, horários, nº de fluxos, "ativa")
# Só entram flows cujo ORIGINADOR é o IP informado (senão o tráfego do Windows,
# do celular etc. seria rotulado como ataque). Para sessões Benigno o IP é opcional.
# ==============================================================================
import json
import re
import threading
import time
from datetime import datetime

from app import config

ROTULOS = {'benigno': 'Benigno', 'portscan': 'PortScan', 'ddos': 'DDoS',
           'ataque_generico': 'Ataque_Generico', 'c&c': 'C&C', 'botnet_okiru': 'Botnet_Okiru'}
_RE_IP = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')

_lock = threading.Lock()
_sessao = None


def _salvar_meta(s, fim=False):
    meta = {k: s[k] for k in ('nome', 'rotulo', 'ip_dispositivo', 'descricao', 'inicio', 'n_fluxos', 'ativa')}
    meta['fim'] = datetime.now().isoformat(timespec='seconds') if fim else None
    (s['pasta'] / 'meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')


def iniciar(rotulo: str, ip_dispositivo: str | None = None, descricao: str = '') -> dict:
    global _sessao
    chave = (rotulo or '').strip().lower()
    if chave not in ROTULOS:
        raise ValueError(f"Rótulo inválido. Use um de: {', '.join(ROTULOS.values())}")
    rot = ROTULOS[chave]
    ip = (ip_dispositivo or '').strip() or None
    if ip and not _RE_IP.match(ip):
        raise ValueError("ip_dispositivo inválido (esperado IPv4, ex.: 192.168.137.50)")
    if rot != 'Benigno' and not ip:
        raise ValueError("Para rótulos de ataque informe o ip_dispositivo (IP do ESP32), "
                         "senão tráfego de outras máquinas seria rotulado como ataque.")
    with _lock:
        if _sessao:
            raise RuntimeError(f"Já existe uma coleta em andamento: {_sessao['nome']}. Pare-a primeiro.")
        agora = datetime.now()
        nome = f"{agora:%Y%m%d_%H%M%S}_{rot}" + (f"_{ip.replace('.', '-')}" if ip else '')
        pasta, n = config.COLETAS_DIR / nome, 1
        while pasta.exists():                      # nunca sobrescreve uma sessão existente
            n += 1
            pasta = config.COLETAS_DIR / f"{nome}_{n}"
        nome = pasta.name
        pasta.mkdir(parents=True)
        (pasta / 'conn.log').touch()
        _sessao = {'nome': nome, 'pasta': pasta, 'rotulo': rot, 'ip_dispositivo': ip, 'descricao': descricao,
                   'inicio': agora.isoformat(timespec='seconds'), 'inicio_ts': time.time(), 'n_fluxos': 0, 'ativa': True}
        _salvar_meta(_sessao)
        return status_unlocked()


def registrar_fluxos(registros) -> None:
    """Chamado pelo sniffer a cada flush. registros = [(ip_orig, ts_inicio, linha)]."""
    with _lock:
        s = _sessao
        if not s:
            return
        linhas = [l for ip, ts, l in registros
                  if ts >= s['inicio_ts'] - 0.5 and (s['ip_dispositivo'] is None or ip == s['ip_dispositivo'])]
        if linhas:
            with open(s['pasta'] / 'conn.log', 'a', encoding='utf-8') as fh:
                fh.write('\n'.join(linhas) + '\n')
            s['n_fluxos'] += len(linhas)


def parar() -> dict:
    global _sessao
    with _lock:
        s = _sessao
    if not s:
        raise RuntimeError("Nenhuma coleta em andamento.")
    from app.services import sniffer          # import tardio (evita ciclo)
    sniffer.descarregar_pendentes(s['ip_dispositivo'])   # grava flows ainda abertos do dispositivo
    with _lock:
        _salvar_meta(s, fim=True)
        _sessao = None
        res = {k: s[k] for k in ('nome', 'rotulo', 'ip_dispositivo', 'n_fluxos')}
        res['pasta'] = str(s['pasta'])
        if s['n_fluxos'] == 0:
            res['aviso'] = ("0 fluxos gravados: confira o IP do dispositivo, se o sniffer está capturando "
                            "e se o ESP32 estava gerando tráfego. Apague a pasta da sessão se não servir.")
        return res


def status_unlocked() -> dict:
    s = _sessao
    if not s:
        return {'ativa': False}
    return {'ativa': True, 'nome': s['nome'], 'rotulo': s['rotulo'], 'ip_dispositivo': s['ip_dispositivo'],
            'n_fluxos': s['n_fluxos'], 'segundos': int(time.time() - s['inicio_ts'])}


def status() -> dict:
    with _lock:
        return status_unlocked()


def listar_sessoes() -> list:
    out = []
    for m in sorted(config.COLETAS_DIR.glob('*/meta.json')):
        try:
            out.append(json.loads(m.read_text(encoding='utf-8')))
        except Exception:
            pass
    return out