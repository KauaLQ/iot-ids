# ==============================================================================
# SNIFFER — captura com Scapy e emula o conn.log do Zeek (o formato do IoT-23).
#
# O que foi alinhado ao Zeek (divergências corrigidas em relação à versão anterior):
#  1. orig_bytes/resp_bytes = bytes de PAYLOAD (TCP: pelo espaço de sequência, sem
#     retransmissões; UDP: udp.len-8; ICMP: ip.len-ihl-8). Antes usava len(pkt),
#     que inclui o cabeçalho Ethernet+IP+TCP (um SYN virava "66 bytes").
#  2. orig_ip_bytes/resp_ip_bytes = soma do TOTAL LENGTH do cabeçalho IP (não len(pkt)).
#  3. conn_state segue a máquina de estados do Zeek: S0, S1, SF, REJ, S2, S3, RSTO,
#     RSTR, RSTOS0, RSTRH, SH, SHR, OTH. Antes: RST => sempre 'REJ'; UDP/ICMP => 'OTH'.
#     UDP/ICMP no Zeek: 'SF' se houve resposta, 'S0' se só o originador falou.
#  4. service só é preenchido quando há payload que o confirme (HTTP/TLS/SSH/DNS/DHCP),
#     como o DPI do Zeek. Antes era inferido pela porta (443 em SYN sem resposta
#     virava 'ssl'; 1883 virava 'mqtt', categoria inexistente no treino).
#  5. Papéis orig/resp: ao descobrir o SYN, os contadores são TROCADOS junto com os
#     endpoints (antes só os endpoints eram trocados e os pacotes ficavam contados
#     no lado errado).
#  6. Reuso de 4-tupla: novo SYN puro sobre conexão já estabelecida/encerrada abre
#     NOVO flow (antes fundia conexões distintas). Pacotes tardios de conexão já
#     encerrada (ACK final, etc.) são ignorados por 10 s em vez de virar flows 'OTH'.
#  7. Timeouts por estado (tentativa 5 s, fechado 2 s, ativo 30 s, UDP/ICMP 10 s) em
#     vez de 5 s fixos para tudo (que quebrava conexões longas em vários flows).
#  8. Timestamp = relógio da captura (pkt.time), não o do processamento; ICMP usa
#     (type, code) como portas, como o Zeek; ip.len==0 (offload do Windows) tratado;
#     uid único (antes 'win-<ms>' colidia).
# Requisitos: Windows -> Npcap + Administrador; Linux/macOS -> root.
# ==============================================================================
import itertools
import threading
import time

from app import config
from app.services import coleta

try:
    from scapy.all import sniff, IP, TCP, UDP, ICMP, conf
    SCAPY_DISPONIVEL = True
except Exception:
    SCAPY_DISPONIVEL = False

INTERVALO_FLUSH = 2.0
SYN, ACK, FIN, RST = 0x02, 0x10, 0x01, 0x04
PROTO_NOME = {1: 'icmp', 6: 'tcp', 17: 'udp'}
PROTOCOLOS_SUPORTADOS = set(PROTO_NOME)
SERVICOS_UDP = {53: 'dns', 67: 'dhcp', 68: 'dhcp'}
_HTTP = (b'GET ', b'POST', b'HEAD', b'PUT ', b'DELE', b'OPTI', b'PATC', b'HTTP')
_PARES = ('pkts', 'ip_bytes', 'bytes', 'head', 'fin', 'rst', 'seq_max')

_lock_arquivo = threading.Lock()


# ------------------------------------------------------------------- tabela de flows
def _novo_flow(ts, ep_o, ep_r, proto, icmp_tc):
    f = {'proto': proto, 'ts_inicio': ts, 'ts_fim': ts, 'orig': ep_o, 'resp': ep_r, 'icmp_tc': icmp_tc,
         'syn': False, 'synack': False, 'fechado': False, 'historico': ''}
    for lado in ('orig', 'resp'):
        f[lado + '_pkts'] = f[lado + '_ip_bytes'] = f[lado + '_bytes'] = 0
        f[lado + '_head'] = b''
        f[lado + '_fin'] = f[lado + '_rst'] = False
        f[lado + '_seq_max'] = None
    return f


def _trocar_papeis(f):
    f['orig'], f['resp'] = f['resp'], f['orig']
    for k in _PARES:
        f['orig_' + k], f['resp_' + k] = f['resp_' + k], f['orig_' + k]
    f['historico'] = f['historico'].swapcase()


def _hist(f, de_orig, ch):
    c = ch.upper() if de_orig else ch.lower()
    if c not in f['historico']:
        f['historico'] += c


def _contar_payload_tcp(f, lado, payload_len, seq):
    """Zeek conta orig_bytes/resp_bytes pelo espaço de sequência: retransmissão não soma."""
    if payload_len <= 0:
        return
    fim = (seq + payload_len) & 0xFFFFFFFF
    atual = f[lado + '_seq_max']
    if atual is None:
        f[lado + '_bytes'] += payload_len
        f[lado + '_seq_max'] = fim
    else:
        avanco = (fim - atual) & 0xFFFFFFFF
        if 0 < avanco < 0x80000000:
            f[lado + '_bytes'] += min(avanco, payload_len)
            f[lado + '_seq_max'] = fim


class TabelaFlows:
    def __init__(self):
        self._lock = threading.Lock()
        self._flows = {}
        self._rotacionados = []
        self._fechados = {}     # chave -> ts em que foi emitido (ignora pacotes tardios)
        self.stats = {"vistos": 0, "ignorados_proto": 0, "ignorados_subnet": 0, "aceitos": 0}

    def processar(self, ts, proto, src, sport, dst, dport, flags=0, ip_len=0,
                  payload_len=0, seq=0, payload_head=b'', icmp_tc=None):
        ep_s, ep_d = (src, sport), (dst, dport)
        chave = (proto,) + tuple(sorted([ep_s, ep_d]))
        tcp = proto == 6
        is_syn = tcp and bool(flags & SYN)
        is_ack = tcp and bool(flags & ACK)
        is_fin = tcp and bool(flags & FIN)
        is_rst = tcp and bool(flags & RST)

        with self._lock:
            f = self._flows.get(chave)
            if f is not None and is_syn and not is_ack and (f['fechado'] or f['synack']):
                self._rotacionados.append(self._flows.pop(chave))      # nova conexão, mesma 4-tupla
                f = None
            if f is None:
                if tcp and not is_syn and ts - self._fechados.get(chave, -1e9) < 10.0:
                    return                                              # sobra de conexão já encerrada
                f = _novo_flow(ts, ep_s, ep_d, proto, icmp_tc)
                self._flows[chave] = f

            if tcp:
                if is_syn and not is_ack:
                    if not f['syn'] and f['orig'] != ep_s:
                        _trocar_papeis(f)
                    f['syn'] = True
                elif is_syn and is_ack:
                    if not f['synack'] and not f['syn'] and f['orig'] == ep_s:
                        _trocar_papeis(f)       # quem manda SYN-ACK é o respondente
                    f['synack'] = True

            de_orig = (ep_s == f['orig'])
            lado = 'orig' if de_orig else 'resp'
            f['ts_fim'] = max(f['ts_fim'], ts)
            f[lado + '_pkts'] += 1
            f[lado + '_ip_bytes'] += ip_len
            if tcp:
                _contar_payload_tcp(f, lado, payload_len, seq)
                if is_syn:
                    _hist(f, de_orig, 'H' if is_ack else 'S')
                if payload_len > 0:
                    _hist(f, de_orig, 'D')
                if is_fin:
                    f[lado + '_fin'] = True; _hist(f, de_orig, 'F')
                if is_rst:
                    f[lado + '_rst'] = True; _hist(f, de_orig, 'R')
                if is_ack and not is_syn and not payload_len and not is_fin and not is_rst:
                    _hist(f, de_orig, 'A')
                f['fechado'] = f['orig_rst'] or f['resp_rst'] or (f['orig_fin'] and f['resp_fin'])
            else:
                f[lado + '_bytes'] += payload_len
            if payload_len > 0 and not f[lado + '_head']:
                f[lado + '_head'] = payload_head

    @staticmethod
    def _timeout(f):
        if f['proto'] != 6:
            return config.TIMEOUT_UDP_ICMP
        if f['fechado']:
            return config.TIMEOUT_TCP_FECHADO
        if f['syn'] and not f['synack']:
            return config.TIMEOUT_TCP_TENTATIVA
        return config.TIMEOUT_TCP_ATIVO

    def coletar(self, agora, forcar_origem=None, forcar_todos=False):
        """Retorna flows expirados. forcar_origem=IP / forcar_todos=True encerram flows
        em andamento (usado ao PARAR uma coleta, para não perder o fim da sessão)."""
        saida = []
        with self._lock:
            saida.extend(self._rotacionados)
            self._rotacionados = []
            for chave in list(self._flows):
                f = self._flows[chave]
                forcar = forcar_todos or (forcar_origem is not None and f['orig'][0] == forcar_origem)
                if forcar or agora - f['ts_fim'] >= self._timeout(f):
                    saida.append(self._flows.pop(chave))
                    if f['proto'] == 6:
                        self._fechados[chave] = agora
            for k in [k for k, t in self._fechados.items() if agora - t > 30.0]:
                del self._fechados[k]
        return saida

    def ativos(self):
        with self._lock:
            return len(self._flows)


# ------------------------------------------------------------------- conn_state / service
def estimar_conn_state(f) -> str:
    if f['proto'] != 6:
        return 'SF' if f['resp_pkts'] > 0 else 'S0'      # regra do Zeek p/ UDP e ICMP
    syn, synack = f['syn'], f['synack']
    o_fin, r_fin, o_rst, r_rst = f['orig_fin'], f['resp_fin'], f['orig_rst'], f['resp_rst']
    if syn and not synack:
        if r_rst: return 'REJ'
        if o_rst: return 'RSTOS0'
        if o_fin: return 'SH'
        return 'S0'
    if synack and not syn:
        if r_rst: return 'RSTRH'
        if r_fin: return 'SHR'
        return 'OTH'
    if syn and synack:
        if o_rst: return 'RSTO'
        if r_rst: return 'RSTR'
        if o_fin and r_fin: return 'SF'
        if o_fin: return 'S2'
        if r_fin: return 'S3'
        return 'S1'
    if o_rst: return 'RSTO'
    if r_rst: return 'RSTR'
    if o_fin and r_fin: return 'SF'
    return 'OTH'


def detectar_servico(f) -> str:
    """DPI mínimo, só com o que o Zeek também confirma pelo payload. '-' caso contrário."""
    if f['proto'] == 6:
        if not (f['syn'] and f['synack']):
            return '-'
        for head in (f['orig_head'], f['resp_head']):
            if head.startswith(_HTTP):
                return 'http'
            if len(head) >= 2 and head[0] == 0x16 and head[1] == 0x03:
                return 'ssl'
            if head.startswith(b'SSH-'):
                return 'ssh'
        return '-'
    if f['proto'] == 17 and f['orig_bytes'] > 0:
        return SERVICOS_UDP.get(f['resp'][1], '-')
    return '-'


_contador_uid = itertools.count(1)


def flow_para_linha(f):
    """Retorna (ip_orig, ts_inicio, linha_tsv) com as 22 colunas de COLUNAS_CONN_22."""
    proto = f['proto']
    (ip_o, p_o), (ip_r, p_r) = f['orig'], f['resp']
    if proto == 1 and f['icmp_tc']:
        p_o, p_r = f['icmp_tc']                  # Zeek: orig_p=type, resp_p=code
    uid = f"C{next(_contador_uid):07x}{int(f['ts_inicio'] * 1000) & 0xFFFFFF:06x}"
    pkts_total = f['orig_pkts'] + f['resp_pkts']
    dur = max(f['ts_fim'] - f['ts_inicio'], 0.0)
    campos = [
        f"{f['ts_inicio']:.6f}", uid, ip_o, str(p_o), ip_r, str(p_r),
        PROTO_NOME[proto], detectar_servico(f),
        '-' if pkts_total <= 1 else f"{dur:.6f}",     # '-' e 0 são equivalentes após fillna(0)
        str(f['orig_bytes']), str(f['resp_bytes']),
        estimar_conn_state(f), '-', '-', '0', f['historico'] or '-',
        str(f['orig_pkts']), str(f['orig_ip_bytes']), str(f['resp_pkts']), str(f['resp_ip_bytes']),
        '-', str(proto),
    ]
    return ip_o, f['ts_inicio'], '\t'.join(campos)


TABELA = TabelaFlows()


def _emitir(flows):
    registros = [flow_para_linha(f) for f in flows]
    if not registros:
        return
    with _lock_arquivo:
        with open(config.CONN_LOG_PATH, 'a', encoding='utf-8') as fh:
            fh.write('\n'.join(r[2] for r in registros) + '\n')
    coleta.registrar_fluxos(registros)


def descarregar_pendentes(ip_origem=None):
    """Encerra e grava flows em andamento (chamado por coleta.parar)."""
    _emitir(TABELA.coletar(time.time(), forcar_origem=ip_origem, forcar_todos=ip_origem is None))


# ------------------------------------------------------------------- captura (Scapy)
def _resolver_interface():
    if config.SNIFFER_IFACE:
        return config.SNIFFER_IFACE, f"nome '{config.SNIFFER_IFACE}'"
    if not config.SNIFFER_IFACE_IP:
        return conf.iface, f"padrão do Scapy ({conf.iface})"
    try:
        conf.ifaces.reload()
    except Exception:
        pass
    alvo = config.SNIFFER_IFACE_IP
    for i in conf.ifaces.values():
        ips = set(getattr(i, "ips", {}).get(4, [])) | {getattr(i, "ip", None)}
        if alvo in ips:
            return i, f"IP {alvo} -> {getattr(i, 'description', None) or getattr(i, 'name', str(i))}"
    return None, f"nenhuma interface com IP {alvo}"


def _multicast_ou_broadcast(ip: str) -> bool:
    if ip.endswith('.255') or ip == '255.255.255.255':
        return True
    try:
        return 224 <= int(ip.split('.', 1)[0]) <= 239
    except ValueError:
        return False


def _processar_pacote(pkt):
    if IP not in pkt:
        return
    st = TABELA.stats
    st["vistos"] += 1
    ip = pkt[IP]
    if ip.proto not in PROTOCOLOS_SUPORTADOS:
        st["ignorados_proto"] += 1
        return
    if not (ip.src.startswith(config.SUBNET_PREFIX) or ip.dst.startswith(config.SUBNET_PREFIX)):
        st["ignorados_subnet"] += 1
        return
    if config.IGNORAR_MULTICAST and (_multicast_ou_broadcast(ip.dst) or _multicast_ou_broadcast(ip.src)):
        st["ignorados_subnet"] += 1
        return
    st["aceitos"] += 1

    ts = float(pkt.time)
    ip_len = int(ip.len or 0) or max(len(pkt) - 14, 0)   # ip.len==0 com offload no Windows
    ihl = int(ip.ihl or 5) * 4
    if TCP in pkt:
        t = pkt[TCP]
        # Payload pelo cabeçalho (NÃO por len(t.payload): o padding Ethernet de 60 bytes
        # faria um SYN parecer ter payload).
        pl = max(ip_len - ihl - int(t.dataofs or 5) * 4, 0)
        head = bytes(t.payload)[:min(pl, 16)] if pl else b''
        TABELA.processar(ts, 6, ip.src, int(t.sport), ip.dst, int(t.dport), flags=int(t.flags),
                         ip_len=ip_len, payload_len=pl, seq=int(t.seq), payload_head=head)
    elif UDP in pkt:
        u = pkt[UDP]
        pl = max(int(u.len) - 8, 0) if u.len else max(ip_len - ihl - 8, 0)
        head = bytes(u.payload)[:min(pl, 16)] if pl else b''
        TABELA.processar(ts, 17, ip.src, int(u.sport), ip.dst, int(u.dport),
                         ip_len=ip_len, payload_len=pl, payload_head=head)
    elif ICMP in pkt:
        i = pkt[ICMP]
        pl = max(ip_len - ihl - 8, 0)
        TABELA.processar(ts, 1, ip.src, 0, ip.dst, 0, ip_len=ip_len, payload_len=pl,
                         icmp_tc=(int(i.type), int(i.code)))


def _loop_flush(stop_event: threading.Event):
    ultimo_log = 0.0
    while not stop_event.is_set():
        time.sleep(INTERVALO_FLUSH)
        if time.time() - ultimo_log > 10:
            ultimo_log = time.time()
            st = TABELA.stats
            print(f"[SNIFFER] stats={st} flows_ativos={TABELA.ativos()}")
            if st["vistos"] == 0:
                print("[SNIFFER] AVISO: nenhum pacote IP visto (interface errada, hotspot sem clientes ou Npcap).")
            elif st["aceitos"] == 0:
                print(f"[SNIFFER] AVISO: pacotes vistos, mas fora de {config.SUBNET_PREFIX}*")
        _emitir(TABELA.coletar(time.time()))


def iniciar_sniffer_em_background(stop_event: threading.Event) -> threading.Thread | None:
    if not SCAPY_DISPONIVEL:
        print("[SNIFFER] Scapy/driver de captura indisponível — sniffer desativado. "
              "Instale o Npcap (Windows) ou rode como root (Linux/macOS).")
        return None

    threading.Thread(target=_loop_flush, args=(stop_event,), daemon=True).start()

    def _run_sniff():
        avisou = False
        while not stop_event.is_set():
            iface, desc = _resolver_interface()
            if iface is None:
                if not avisou:
                    print(f"[SNIFFER] Aguardando interface: {desc}. Ligue o Hotspot Móvel (nova tentativa a cada 5s).")
                    avisou = True
                stop_event.wait(5)
                continue
            avisou = False
            print(f"[SNIFFER] Capturando em: {desc} | filtro de sub-rede: {config.SUBNET_PREFIX}*")
            try:
                sniff(iface=iface, filter="ip", prn=_processar_pacote, store=False,
                      stop_filter=lambda _: stop_event.is_set())
            except PermissionError:
                print("[SNIFFER] Permissão negada. Rode o backend como Administrador.")
                return
            except Exception as e:
                print(f"[SNIFFER] Captura interrompida ({e}). Tentando de novo em 5s...")
            stop_event.wait(5)

    thread = threading.Thread(target=_run_sniff, daemon=True)
    thread.start()
    return thread