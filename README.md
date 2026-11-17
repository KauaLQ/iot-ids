# IoT-IDS — Sistema de Detecção de Intrusão para IoT

Pipeline: **ESP32 (firmware de teste)** → **sniffer (Scapy)** → **classificador (XGBoost/RandomForest)**
→ **backend FastAPI** → **frontend (dashboard)**.

```
.
├── backend/            # FastAPI: orquestra sniffer + classificador, expõe /api/status
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── schemas.py
│       ├── routers/status.py
│       └── services/{sniffer,classifier,state}.py
├── frontend/           # Dashboard (hoje HTML/JS estático; preparado p/ React+Vite)
├── firmware/           # Firmware ESP32 (Arduino/PlatformIO) para gerar tráfego de teste
│   └── esp32_test_firmware/
├── ml/                 # Treinamento do modelo
│   ├── train.py
│   ├── datasets/       # coloque aqui os *.labeled do IoT-23 (gitignored)
│   └── models/         # motor_ia_ids_iot.joblib gerado aqui (gitignored)
├── requirements.txt    # dependência única do projeto inteiro
└── .gitignore
```

Veja o roteiro completo de instalação/execução na resposta do assistente ou no
histórico do projeto. Resumo rápido:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1) treinar (uma vez, com o dataset IoT-23 em ml/datasets/)
python ml/train.py

# 2) subir o backend (Administrador, para o sniffer capturar pacotes)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3) servir o frontend
cd ../frontend
python -m http.server 5500
```
