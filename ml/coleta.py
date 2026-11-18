# ==============================================================================
# ml/coleta.py — cliente de linha de comando da coleta rotulada (fala com o backend).
#   python ml/coleta.py iniciar --rotulo Benigno  --ip 192.168.137.50 --descricao "ESP32 normal"
#   python ml/coleta.py iniciar --rotulo PortScan --ip 192.168.137.50 --descricao "ESP32 scan rapido"
#   python ml/coleta.py status
#   python ml/coleta.py parar
#   python ml/coleta.py sessoes
# (Equivalente a usar os botões do Swagger em http://localhost:8000/docs)
# ==============================================================================
import argparse
import json
import sys
import urllib.error
import urllib.request


def chamar(base, metodo, caminho, corpo=None):
    req = urllib.request.Request(base.rstrip('/') + caminho, method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detalhe = json.loads(e.read().decode()).get('detail')
        except Exception:
            detalhe = e.reason
        sys.exit(f"ERRO {e.code}: {detalhe}")
    except urllib.error.URLError as e:
        sys.exit(f"Backend inacessível em {base} ({e.reason}). Ele está rodando?")


def main():
    p = argparse.ArgumentParser(description="Coleta rotulada de tráfego para retreino.")
    p.add_argument('--api', default='http://localhost:8000')
    sp = p.add_subparsers(dest='cmd', required=True)
    i = sp.add_parser('iniciar')
    i.add_argument('--rotulo', required=True, help='Benigno | PortScan | DDoS | Ataque_Generico | C&C | Botnet_Okiru')
    i.add_argument('--ip', help='IP do ESP32 (obrigatório para ataques)')
    i.add_argument('--descricao', default='')
    for n in ('parar', 'status', 'sessoes'):
        sp.add_parser(n)
    a = p.parse_args()
    if a.cmd == 'iniciar':
        r = chamar(a.api, 'POST', '/api/coleta/iniciar', {'rotulo': a.rotulo, 'ip_dispositivo': a.ip, 'descricao': a.descricao})
    elif a.cmd == 'parar':
        r = chamar(a.api, 'POST', '/api/coleta/parar')
    elif a.cmd == 'status':
        r = chamar(a.api, 'GET', '/api/coleta/status')
    else:
        r = chamar(a.api, 'GET', '/api/coleta/sessoes')
    print(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()