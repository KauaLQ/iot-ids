# ==============================================================================
# CONFIGURAÇÃO CENTRAL — todos os caminhos do projeto num só lugar.
# 100% baseado em pathlib: funciona igual em Windows, Linux ou macOS.
# Qualquer caminho pode ser sobrescrito por variável de ambiente, sem editar código.
# ==============================================================================
import os
from pathlib import Path

# backend/app/config.py -> parents[0]=app, [1]=backend, [2]=raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = Path(os.environ.get(
    "IOT_IDS_MODEL_PATH", PROJECT_ROOT / "ml" / "models" / "motor_ia_ids_iot.joblib"
))

CONN_LOG_PATH = Path(os.environ.get(
    "IOT_IDS_CONN_LOG_PATH", PROJECT_ROOT / "backend" / "runtime_data" / "conn_live.log"
))

# Debug opcional: também grava um snapshot em JSON no disco (útil para inspecionar
# fora da API). Desligado por padrão porque a API já serve tudo em memória.
WRITE_DEBUG_JSON = os.environ.get("IOT_IDS_WRITE_DEBUG_JSON", "false").lower() == "true"
DEBUG_JSON_PATH = Path(os.environ.get(
    "IOT_IDS_DEBUG_JSON_PATH", PROJECT_ROOT / "backend" / "runtime_data" / "status_debug.json"
))

# Prefixo de sub-rede considerado "local" pelo sniffer (ajuste para a sua LAN)
SUBNET_PREFIX = os.environ.get("IOT_IDS_SUBNET_PREFIX", "192.168.")

# Interface de captura explícita (opcional). Deixe None para o Scapy escolher
# automaticamente, ou defina para o nome exato (ex.: "Wi-Fi", "Ethernet", "eth0").
SNIFFER_IFACE = os.environ.get("IOT_IDS_SNIFFER_IFACE") or None

# Liga/desliga o sniffer real (útil para testar o backend sem admin/Npcap,
# usando apenas o endpoint de ingestão manual ou um conn_live.log já existente)
ENABLE_SNIFFER = os.environ.get("IOT_IDS_ENABLE_SNIFFER", "true").lower() == "true"

# ------------------------------------------------------------------------------
# FILTROS ANTI-FALSO-POSITIVO (camada de pós-processamento, não mexe no modelo)
# ------------------------------------------------------------------------------
# Só conta um fluxo como MALIGNO se a confiança do modelo for >= este valor.
# Evita alarmes em cima de previsões "quase no chute" (ex.: 55% de confiança).
CONFIANCA_MINIMA_ATAQUE = float(os.environ.get("IOT_IDS_CONFIANCA_MINIMA", "75.0"))

# Só lista um dispositivo como "atacante" se ele tiver pelo menos esta
# quantidade de fluxos maliciosos (já filtrados pela confiança acima) na
# janela atual. Elimina eventos isolados de 1-2 fluxos (rajada assimétrica
# de um serviço de nuvem legítimo, por exemplo), mantendo detecção de
# padrões sustentados (scan, flood, brute-force real geram MUITOS fluxos).
MIN_FLUXOS_PARA_ALERTA = int(os.environ.get("IOT_IDS_MIN_FLUXOS_ALERTA", "3"))

CONN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
DEBUG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)