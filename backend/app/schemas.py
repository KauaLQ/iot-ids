from typing import Any, Optional
from pydantic import BaseModel, Field


class DispositivoAtacante(BaseModel):
    ip_dispositivo: str
    tipo_ataque: str
    fluxos_maliciosos: int
    ip_vitima: str
    porta_vitima: int
    confianca_ia_pct: float
    ultimo_alerta: str


# ---------- Relatório de IA generativa ----------
class AcaoMitigacao(BaseModel):
    titulo: str = Field(description="Ação em até 8 palavras, no imperativo (ex.: 'Bloquear o dispositivo no firewall do Windows')")
    detalhe: str = Field(description="1 ou 2 frases: o que fazer, por quê e como desfazer, se aplicável")
    onde: str = Field(description="Onde executar: 'Windows (PowerShell admin)', 'Linux', 'Hotspot/roteador', 'Dispositivo' ou 'Análise'")
    comando: str = Field(description="Comando puro, sem crases nem markdown. String vazia se a ação não for um comando")


class RelatorioIA(BaseModel):
    """Schema usado como response_schema do Gemini E exposto à API/frontend."""
    severidade: str = Field(description="Exatamente um de: baixa, media, alta")
    resumo: str = Field(description="Uma única frase com a conclusão do incidente")
    diagnostico_tecnico: list[str] = Field(
        min_length=1, description="3 a 5 itens objetivos, cada um com evidências numéricas concretas")
    acoes_mitigacao: list[AcaoMitigacao] = Field(
        min_length=1, description="3 a 5 ações em ordem de prioridade")
    ressalvas: str = Field(description="Uma frase sobre possível falso positivo e como confirmar. Vazia se não houver")


class RelatorioIAEstado(BaseModel):
    estado: str   # desativado | ocioso | aguardando | disponivel | gerando | pronto | erro | limite
    modo: str     # auto | manual
    modelo: Optional[str] = None
    incidentes: list[str] = []
    gerado_em: Optional[str] = None
    desatualizado: bool = False        # True = relatório de um incidente anterior (o atual ainda não foi gerado)
    relatorio: Optional[RelatorioIA] = None
    mensagem: Optional[str] = None
    pode_solicitar: bool = False       # o botão "Gerar/Regenerar" está liberado?
    espera_s: int = 0
    chamadas_restantes_hora: int = 0


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
    relatorio_llm: str                              # resumo estático (fallback quando a IA não está disponível)
    relatorio_ia: Optional[RelatorioIAEstado] = None
    feed_tempo_real: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str = "ok"