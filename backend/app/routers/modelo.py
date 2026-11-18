from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import classifier
from ml import registry

router = APIRouter(prefix="/api/modelo", tags=["modelo"])


class Ativar(BaseModel):
    versao: str


@router.get("/versoes")
def versoes():
    registry.migrar_legado()
    reg = registry.ler()
    return {"ativa": reg["ativo"], "em_uso": classifier.versao_em_uso(),
            "historico": reg["historico"], "versoes": reg["versoes"]}


def _trocar(acao):
    """Aplica a troca no registro e valida carregando o modelo; se falhar, desfaz."""
    snap = registry.snapshot()
    try:
        acao()
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    if not classifier.carregar_modelo():
        registry.restaurar(snap)
        raise HTTPException(500, "A versão não carregou (veja erro_modelo em /api/status). Registro restaurado.")
    return {"ativa": registry.versao_ativa()}


@router.post("/ativar")
def ativar(req: Ativar):
    return _trocar(lambda: registry.ativar(req.versao))


@router.post("/rollback")
def rollback():
    return _trocar(registry.rollback)


@router.post("/recarregar")
def recarregar():
    return {"ok": classifier.carregar_modelo(), "em_uso": classifier.versao_em_uso()}