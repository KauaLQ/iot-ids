from fastapi import APIRouter, HTTPException

from app.schemas import RelatorioIAEstado
from app.services import llm_report

router = APIRouter(prefix="/api/ia", tags=["ia"])


@router.get("/relatorio", response_model=RelatorioIAEstado)
def obter_relatorio():
    """Estado atual do relatório de IA (o mesmo que vai embutido em /api/status)."""
    return llm_report.snapshot()


@router.post("/relatorio/gerar", response_model=RelatorioIAEstado, status_code=202)
def gerar_relatorio():
    """Disparo sob demanda. Ignora o cache, mas respeita intervalo mínimo,
    orçamento por hora e a regra de uma geração por vez (429/409 se negado)."""
    try:
        return llm_report.solicitar_manual()
    except llm_report.SolicitacaoNegada as e:
        headers = {"Retry-After": str(e.espera_s)} if e.espera_s else None
        raise HTTPException(status_code=e.status, detail=e.mensagem, headers=headers)