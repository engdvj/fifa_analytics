#!/usr/bin/env bash
# Sobe o ambiente de dev local (SQLite + FastAPI + Next.js).
# Uso: bash start_dev.sh
# Pré-requisitos: .venv ativado, Node.js no PATH.

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/Scripts/activate"

export DATABASE_URL="sqlite:///./dev.db"
export JWT_SECRET_KEY="copa2026-dev-secret-change-in-prod"

echo "=== Copa 2026 — Dev Start ==="

# 1. Setup do banco (idempotente)
echo "[1/3] Inicializando banco e dados..."
source "$VENV"
python "$ROOT/scripts/setup_dev.py"

# 2. Backend
echo "[2/3] Iniciando backend FastAPI (porta 8000)..."
DATABASE_URL="sqlite:///./dev.db" uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"
sleep 3

# 3. Frontend
echo "[3/3] Iniciando frontend Next.js (porta 3000)..."
cd "$ROOT/frontend"
npm run dev -- --port 3000 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

echo ""
echo "✓ Tudo rodando!"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
echo "  Usuário de teste: teste@copa2026.dev / copa2026"
echo ""
echo "Pressione Ctrl+C para encerrar."

# Aguarda ambos os processos
wait $BACKEND_PID $FRONTEND_PID
