# ==============================================================================
# BACKEND — FastAPI
# Ao subir, inicializa o sniffer e o classificador em background e expõe as
# rotas que o frontend consome. Rodar com:  uvicorn app.main:app --reload
# (a partir da pasta backend/)
# ==============================================================================
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.routers import status
from app.services import sniffer, classifier

_stop_event = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Inicializando componentes do IoT-IDS...")

    if config.ENABLE_SNIFFER:
        sniffer.iniciar_sniffer_em_background(_stop_event)
    else:
        print("[STARTUP] Sniffer desativado via IOT_IDS_ENABLE_SNIFFER=false.")

    classifier.iniciar_classificador_em_background(_stop_event)

    yield

    print("[SHUTDOWN] Encerrando componentes em background...")
    _stop_event.set()


app = FastAPI(title="IoT-IDS Backend", version="2.0.0", lifespan=lifespan)

# CORS liberado para desenvolvimento (frontend React+Vite roda em outra porta).
# Em produção, restrinja allow_origins para o domínio real do frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status.router)


@app.get("/")
def raiz():
    return {"servico": "IoT-IDS Backend", "docs": "/docs", "status_api": "/api/status"}
