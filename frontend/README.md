# Frontend

Hoje: `index.html` estático (HTML/CSS/JS puro), que consome a API do backend
em `GET /api/status` a cada 2 segundos. Não precisa de build nem de servidor
Node — basta abrir via um servidor HTTP simples (ver roteiro na raiz do projeto).

## Evolução planejada para React + Vite

Quando migrar:
1. `npm create vite@latest frontend -- --template react`
2. Mover a lógica de `atualizarDashboard()` para um hook (`useStatusPolling`)
   que faz `fetch(`${import.meta.env.VITE_API_BASE_URL}/api/status`)`.
3. Definir `VITE_API_BASE_URL` em `frontend/.env` (ex.: `http://localhost:8000`).
4. O backend já está com CORS liberado (`backend/app/main.py`) para aceitar
   chamadas vindas da porta do Vite (geralmente `5173`) durante o desenvolvimento.
