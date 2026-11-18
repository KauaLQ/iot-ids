# ==============================================================================
# ESTADO COMPARTILHADO — classificador escreve, rotas da API leem (tudo em RAM).
# ==============================================================================
import threading
from datetime import datetime

_lock = threading.Lock()

_estado_atual = {
    "ultima_atualizacao": None,
    "status_rede": "INICIALIZANDO",
    "modelo_carregado": False,
    "modelo_versao": None,
    "erro_modelo": None,
    "total_fluxos_analisados": 0,
    "total_ataques_detectados": 0,
    "distribuicao_trafego": {},
    "dispositivos_atacantes": [],
    "relatorio_llm": "Aguardando o motor de IA carregar...",
    "feed_tempo_real": [],
}


def atualizar_estado(novos_dados: dict) -> None:
    with _lock:
        _estado_atual.update(novos_dados)
        _estado_atual["ultima_atualizacao"] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def obter_estado() -> dict:
    with _lock:
        return dict(_estado_atual)


def marcar_erro_modelo(mensagem: str) -> None:
    with _lock:
        _estado_atual["modelo_carregado"] = False
        _estado_atual["erro_modelo"] = mensagem
        _estado_atual["status_rede"] = "ERRO_MODELO"