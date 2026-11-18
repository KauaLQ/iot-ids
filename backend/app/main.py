# ==============================================================================
# BACKEND — FastAPI. Sobe sniffer + classificador em background.
# Rodar (como Administrador, a partir de backend/):  uvicorn app.main:app --host 0.0.0.0 --port 8000
# ==============================================================================
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.routers import status, coleta, modelo
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


app = FastAPI(title="IoT-IDS Backend", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(status.router)
app.include_router(coleta.router)
app.include_router(modelo.router)


@app.get("/")
def raiz():
    return {"servico": "IoT-IDS Backend", "docs": "/docs", "status_api": "/api/status"}