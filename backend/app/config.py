# ==============================================================================
# CONFIGURAÇÃO CENTRAL — todos os caminhos do projeto num só lugar.
# 100% pathlib; qualquer valor pode ser sobrescrito por variável de ambiente
# (ou por um arquivo .env na raiz do projeto, carregado abaixo).
# ==============================================================================
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:                                   # .env na raiz do projeto (opcional)
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def _float(nome, padrao):
    return float(os.environ.get(nome, padrao))


def _bool(nome, padrao):
    return os.environ.get(nome, str(padrao)).lower() == "true"


# Modelo: por padrão vem do registro de versões (ml/models/registry.json).
# Defina IOT_IDS_MODEL_PATH só para FORÇAR um arquivo específico (ignora o registro).
MODEL_PATH_OVERRIDE = Path(os.environ["IOT_IDS_MODEL_PATH"]) if os.environ.get("IOT_IDS_MODEL_PATH") else None

CONN_LOG_PATH = Path(os.environ.get(
    "IOT_IDS_CONN_LOG_PATH", PROJECT_ROOT / "backend" / "runtime_data" / "conn_live.log"))
COLETAS_DIR = Path(os.environ.get(
    "IOT_IDS_COLETAS_DIR", PROJECT_ROOT / "ml" / "datasets" / "coletas"))

WRITE_DEBUG_JSON = _bool("IOT_IDS_WRITE_DEBUG_JSON", False)
DEBUG_JSON_PATH = Path(os.environ.get(
    "IOT_IDS_DEBUG_JSON_PATH", PROJECT_ROOT / "backend" / "runtime_data" / "status_debug.json"))

# ------------------------------- SNIFFER --------------------------------------
SUBNET_PREFIX = os.environ.get("IOT_IDS_SUBNET_PREFIX", "192.168.137.")
SNIFFER_IFACE = os.environ.get("IOT_IDS_SNIFFER_IFACE") or None
SNIFFER_IFACE_IP = os.environ.get("IOT_IDS_SNIFFER_IFACE_IP", "192.168.137.1") or None
ENABLE_SNIFFER = _bool("IOT_IDS_ENABLE_SNIFFER", True)

# Ignorar broadcast/multicast (SSDP, mDNS, IGMP...)? O Zeek NÃO ignora; padrão false
# para manter a distribuição igual à do IoT-23. Se o ruído do Windows atrapalhar
# (e você retreinar com seus dados), pode ligar — o importante é treinar e inferir igual.
IGNORAR_MULTICAST = _bool("IOT_IDS_IGNORAR_MULTICAST", False)

# Timeouts de flow (segundos). Zeek usa 5 / 5 / 300 / 60; aqui os dois últimos são
# menores para o dashboard não ficar com minutos de atraso. Trade-off documentado no README.
TIMEOUT_TCP_TENTATIVA = _float("IOT_IDS_TIMEOUT_TCP_TENTATIVA", 5.0)   # SYN sem SYN-ACK (Zeek tcp_attempt_delay=5)
TIMEOUT_TCP_FECHADO = _float("IOT_IDS_TIMEOUT_TCP_FECHADO", 2.0)       # após FIN/FIN ou RST
TIMEOUT_TCP_ATIVO = _float("IOT_IDS_TIMEOUT_TCP_ATIVO", 30.0)          # conexão aberta ociosa (Zeek: 300)
TIMEOUT_UDP_ICMP = _float("IOT_IDS_TIMEOUT_UDP_ICMP", 10.0)            # Zeek: 60

# ------------------------------- CLASSIFICADOR --------------------------------
# Só classifica janelas de 10 s JÁ FECHADAS (+ este atraso para os flows serem
# gravados). Classificar janela em andamento gera win_* subestimados (skew).
ATRASO_JANELA_S = _float("IOT_IDS_ATRASO_JANELA_S", 12.0)
JANELA_HISTORICO_S = _float("IOT_IDS_JANELA_HISTORICO_S", 300.0)
# REPLAY=true: desliga os filtros de tempo (útil p/ reanalisar um conn_live.log antigo)
REPLAY = _bool("IOT_IDS_REPLAY", False)

CONFIANCA_MINIMA_ATAQUE = _float("IOT_IDS_CONFIANCA_MINIMA", 75.0)
MIN_FLUXOS_PARA_ALERTA = int(os.environ.get("IOT_IDS_MIN_FLUXOS_ALERTA", "3"))

# ------------------------------- IA GENERATIVA (Google AI Studio) -------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip() or None
# Configurável via .env: quando o Google aposentar um modelo, basta trocar aqui.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

LLM_HABILITADO = _bool("IOT_IDS_LLM_HABILITADO", True)
LLM_MODO = os.environ.get("IOT_IDS_LLM_MODO", "auto").strip().lower()
if LLM_MODO not in ("auto", "manual"):
    LLM_MODO = "auto"

LLM_ESTABILIDADE_S = _float("IOT_IDS_LLM_ESTABILIDADE_S", 6.0)
LLM_COOLDOWN_S = _float("IOT_IDS_LLM_COOLDOWN_S", 30.0)
LLM_MANUAL_MIN_S = _float("IOT_IDS_LLM_MANUAL_MIN_S", 15.0)
LLM_CACHE_TTL_S = _float("IOT_IDS_LLM_CACHE_TTL_S", 900.0)
LLM_MAX_CHAMADAS_HORA = int(os.environ.get("IOT_IDS_LLM_MAX_CHAMADAS_HORA", "20"))
LLM_MAX_INCIDENTES = int(os.environ.get("IOT_IDS_LLM_MAX_INCIDENTES", "3"))
LLM_TIMEOUT_S = _float("IOT_IDS_LLM_TIMEOUT_S", 25.0)
LLM_BACKOFF_ERRO_S = _float("IOT_IDS_LLM_BACKOFF_ERRO_S", 60.0)
LLM_BACKOFF_429_S = _float("IOT_IDS_LLM_BACKOFF_429_S", 180.0)

CONN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
DEBUG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
COLETAS_DIR.mkdir(parents=True, exist_ok=True)