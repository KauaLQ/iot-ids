from typing import Any, Optional
from pydantic import BaseModel


class DispositivoAtacante(BaseModel):
    ip_dispositivo: str
    tipo_ataque: str
    fluxos_maliciosos: int
    ip_vitima: str
    porta_vitima: int
    confianca_ia_pct: float
    ultimo_alerta: str


class StatusResponse(BaseModel):
    ultima_atualizacao: Optional[str] = None
    status_rede: str
    modelo_carregado: bool
    modelo_versao: Optional[str] = None
    erro_modelo: Optional[str] = None
    total_fluxos_analisados: int
    total_ataques_detectados: int
    distribuicao_trafego: dict
    dispositivos_atacantes: list[DispositivoAtacante]
    relatorio_llm: str
    feed_tempo_real: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str = "ok"