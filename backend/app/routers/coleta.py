from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import coleta

router = APIRouter(prefix="/api/coleta", tags=["coleta"])


class IniciarColeta(BaseModel):
    rotulo: str                        # Benigno | PortScan | DDoS | Ataque_Generico | C&C | Botnet_Okiru
    ip_dispositivo: Optional[str] = None   # obrigatório para rótulos de ataque
    descricao: str = ""


@router.post("/iniciar")
def iniciar(req: IniciarColeta):
    try:
        return coleta.iniciar(req.rotulo, req.ip_dispositivo, req.descricao)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.post("/parar")
def parar():
    try:
        return coleta.parar()
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.get("/status")
def status():
    return coleta.status()


@router.get("/sessoes")
def sessoes():
    return coleta.listar_sessoes()