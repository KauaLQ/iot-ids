from fastapi import APIRouter

from app.schemas import StatusResponse, HealthResponse
from app.services import state

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/health", response_model=HealthResponse)
def health():
    """Usado pelo frontend/orquestrador para saber se o backend está de pé."""
    return HealthResponse()


@router.get("/status", response_model=StatusResponse)
def get_status():
    """Substitui o antigo status_rede_frontend.json: o frontend consome isto
    via fetch() a cada poucos segundos."""
    return state.obter_estado()
