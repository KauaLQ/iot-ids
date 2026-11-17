# ==============================================================================
# SNIFFER — captura de flows de rede, substituindo o Zeek (sem build nativo p/
# Windows). Usa Scapy, que é OS-agnóstico:
#   - Windows: precisa do Npcap instalado e do processo rodando como Administrador.
#   - Linux/macOS: usa libpcap, precisa rodar como root (sudo).
#
# IMPORTANTE (correção pós-diagnóstico): os dois sentidos de uma MESMA conexão
# TCP são agregados em UM ÚNICO flow (como o Zeek faz), identificando
# explicitamente quem é o originador (quem mandou o SYN puro) e quem é o
# respondente (quem mandou o SYN-ACK). Antes, cada direção virava um flow
# separado e o lado "cliente" nunca via o SYN-ACK (que só chegava na entrada
# do outro lado) — isso fazia TODA conexão de saída, mesmo bem-sucedida,
# cair em conn_state='S0', inflando artificialmente win_taxa_s0 e gerando
# falsos positivos de PortScan/C&C/DDoS inclusive para tráfego normal.
# ==============================================================================
import threading
import time

from app import config

try:
    from scapy.all import sniff, IP, TCP, UDP, conf
    SCAPY_DISPONIVEL = True
except Exception:
    SCAPY_DISPONIVEL = False

TIMEOUT_FLOW = 5.0
INTERVALO_FLUSH = 2.0
SERVICOS_CONHECIDOS = {80: 'http', 443: 'ssl', 53: 'dns', 22: 'ssh', 1883: 'mqtt'}

SYN, ACK, FIN, RST = 0x02, 0x10, 0x01, 0x04

_lock = threading.Lock()
_flows: dict = {}

_stats = {"vistos": 0, "ignorados_proto": 0, "ignorados_subnet": 0, "aceitos": 0}


def _resolver_interface():
    """Retorna (iface, descricao). iface=None significa 'ainda não encontrada'
    (ex.: hotspot desligado)."""
    if config.SNIFFER_IFACE:
        return config.SNIFFER_IFACE, f"nome '{config.SNIFFER_IFACE}'"
    if not config.SNIFFER_IFACE_IP:
        return conf.iface, f"padrão do Scapy ({conf.iface})"
    try:
        conf.ifaces.reload()   # relê os adaptadores (o hotspot pode ter ligado depois do import)
    except Exception:
        pass
    alvo = config.SNIFFER_IFACE_IP
    for i in conf.ifaces.values():
        ips = set(getattr(i, "ips", {}).get(4, [])) | {getattr(i, "ip", None)}
        if alvo in ips:
            nome = getattr(i, "description", None) or getattr(i, "name", str(i))
            return i, f"IP {alvo} -> {nome}"
    return None, f"nenhuma interface com IP {alvo}"


def _endpoints(pkt):
    ip = pkt[IP]
    if TCP in pkt:
        sport, dport = pkt[TCP].sport, pkt[TCP].dport
    elif UDP in pkt:
        sport, dport = pkt[UDP].sport, pkt[UDP].dport
    else:
        sport, dport = 0, 0
    return ip.proto, (ip.src, sport), (ip.dst, dport)


def _chave_flow(proto, ep_a, ep_b):
    # Normaliza a ordem dos endpoints para que os dois sentidos do mesmo
    # fluxo caiam sempre na mesma chave, não importa quem foi capturado primeiro.
    par = tuple(sorted([ep_a, ep_b]))
    return (proto,) + par


def _novo_flow(ts, ep_origem_tentativa, ep_destino_tentativa):
    return {
        'ts_inicio': ts, 'ts_fim': ts,
        # orig_ep/resp_ep são "tentativos" até vermos um SYN puro que confirme
        # definitivamente quem iniciou a conexão.
        'orig_ep': ep_origem_tentativa, 'resp_ep': ep_destino_tentativa,
        'orig_pkts': 0, 'resp_pkts': 0,
        'orig_bytes': 0, 'resp_bytes': 0,
        'syn_visto': False, 'synack_visto': False,
        'fin_orig': False, 'fin_resp': False, 'rst_visto': False,
    }


PROTOCOLOS_SUPORTADOS = {1, 6, 17}  # ICMP, TCP, UDP — o resto (IGMP, etc.) não vira "flow"


def _processar_pacote(pkt):
    if IP not in pkt:
        return
    _stats["vistos"] += 1
    ip = pkt[IP]
    if ip.proto not in PROTOCOLOS_SUPORTADOS:
        _stats["ignorados_proto"] += 1
        return
    if not (ip.src.startswith(config.SUBNET_PREFIX) or ip.dst.startswith(config.SUBNET_PREFIX)):
        _stats["ignorados_subnet"] += 1
        return
    _stats["aceitos"] += 1

    agora = time.time()
    proto, ep_src, ep_dst = _endpoints(pkt)
    chave = _chave_flow(proto, ep_src, ep_dst)
    tamanho = len(pkt)

    is_syn = is_ack = is_fin = is_rst = False
    if TCP in pkt:
        flags = pkt[TCP].flags
        is_syn, is_ack = bool(flags & SYN), bool(flags & ACK)
        is_fin, is_rst = bool(flags & FIN), bool(flags & RST)

    with _lock:
        flow = _flows.get(chave)
        if flow is None:
            flow = _novo_flow(agora, ep_src, ep_dst)
            _flows[chave] = flow

        # SYN puro (sem ACK) = quem está iniciando a conexão de fato.
        # Corrige o papel orig/resp mesmo que o primeiro pacote capturado
        # tenha sido, por azar de timing, da resposta.
        if is_syn and not is_ack:
            flow['orig_ep'], flow['resp_ep'] = ep_src, ep_dst
            flow['syn_visto'] = True
        elif is_syn and is_ack:
            flow['synack_visto'] = True
            if flow['orig_ep'] == ep_src:
                # o remetente deste SYN-ACK é, na verdade, quem responde
                flow['orig_ep'], flow['resp_ep'] = ep_dst, ep_src

        flow['ts_fim'] = agora

        if ep_src == flow['orig_ep']:
            flow['orig_pkts'] += 1
            flow['orig_bytes'] += tamanho
        else:
            flow['resp_pkts'] += 1
            flow['resp_bytes'] += tamanho

        if is_fin:
            if ep_src == flow['orig_ep']:
                flow['fin_orig'] = True
            else:
                flow['fin_resp'] = True
        if is_rst:
            flow['rst_visto'] = True


def _estimar_conn_state(flow):
    if flow['rst_visto']:
        return 'REJ'
    if flow['syn_visto'] and not flow['synack_visto']:
        return 'S0'          # tentativa sem resposta — isso sim é suspeito
    if flow['syn_visto'] and flow['synack_visto'] and (flow['fin_orig'] or flow['fin_resp']):
        return 'SF'          # handshake completo + encerramento normal
    if flow['syn_visto'] and flow['synack_visto']:
        return 'S1'          # conexão estabelecida, ainda em andamento
    return 'OTH'             # UDP/ICMP ou flow capturado parcialmente


def _loop_flush(stop_event: threading.Event):
    ultimo_log = 0.0
    while not stop_event.is_set():
        time.sleep(INTERVALO_FLUSH)
        if time.time() - ultimo_log > 10:
            ultimo_log = time.time()
            print(f"[SNIFFER] stats={_stats} flows_ativos={len(_flows)}")
            if _stats["vistos"] == 0:
                print("[SNIFFER] AVISO: nenhum pacote IP visto (interface errada, hotspot sem clientes ou Npcap).")
            elif _stats["aceitos"] == 0:
                print(f"[SNIFFER] AVISO: pacotes vistos, mas fora de {config.SUBNET_PREFIX}*")
        agora = time.time()
        linhas = []
        with _lock:
            expirados = [k for k, f in _flows.items() if agora - f['ts_fim'] >= TIMEOUT_FLOW]
            for chave in expirados:
                flow = _flows.pop(chave)
                proto_num = chave[0]
                ip_orig, porta_orig = flow['orig_ep']
                ip_resp, porta_resp = flow['resp_ep']
                proto_nome = {6: 'tcp', 17: 'udp', 1: 'icmp'}[proto_num]  # só chega aqui o que é suportado
                servico = SERVICOS_CONHECIDOS.get(porta_resp, '-')
                duracao = max(flow['ts_fim'] - flow['ts_inicio'], 0.0)
                conn_state = _estimar_conn_state(flow)
                linha = [
                    f"{flow['ts_inicio']:.6f}", f"win-{int(flow['ts_inicio']*1000)}",
                    ip_orig, str(porta_orig), ip_resp, str(porta_resp),
                    proto_nome, servico, f"{duracao:.6f}",
                    str(flow['orig_bytes']), str(flow['resp_bytes']),
                    conn_state, 'T', 'F', '0', '-',
                    str(flow['orig_pkts']), str(flow['orig_bytes']),
                    str(flow['resp_pkts']), str(flow['resp_bytes']),
                    '-', str(proto_num),
                ]
                linhas.append('\t'.join(linha))
        if linhas:
            with open(config.CONN_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write('\n'.join(linhas) + '\n')


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
                    print(f"[SNIFFER] Aguardando interface: {desc}. Ligue o Hotspot Móvel "
                          f"(tentando de novo a cada 5s).")
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