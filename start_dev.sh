#!/usr/bin/env bash
# Sobe o ambiente de dev local (Postgres via Docker + FastAPI + Next.js).
# Uso: bash start_dev.sh
# Pré-requisitos: .venv com extras [api,dev]; Docker; Node.js no PATH.

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
# .venv/bin no Linux/macOS, .venv/Scripts no Windows (Git Bash)
if [ -f "$ROOT/.venv/bin/activate" ]; then
  VENV="$ROOT/.venv/bin/activate"
else
  VENV="$ROOT/.venv/Scripts/activate"
fi

# Banco: Postgres do compose (mesmo de produção). O override .dev expõe a 5432.
export DATABASE_URL="postgresql+psycopg2://fifa:fifa@localhost:5432/fifa"
export JWT_SECRET_KEY="copa2026-dev-secret-change-in-prod"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="copa2026"
export ADMIN_NAME="Admin"
export CORS_ORIGINS="http://localhost:3000"
# Coleta automática ligada em dev (checa o calendário a cada N min; 0 = off).
export AUTO_COLLECT_MINUTES="15"

echo "=== Copa 2026 — Dev Start ==="
source "$VENV"

# 1. Postgres (sobe só o serviço db; idempotente). Use sudo se necessário.
echo "[1/4] Subindo Postgres (Docker)..."
docker compose --env-file "$ROOT/infra/.env" \
  -f "$ROOT/infra/docker-compose.yml" -f "$ROOT/infra/docker-compose.dev.yml" \
  up -d db
# Espera o Postgres aceitar conexão.
echo "  aguardando Postgres..."
until docker compose -f "$ROOT/infra/docker-compose.yml" exec -T db pg_isready -U fifa >/dev/null 2>&1; do
  sleep 1
done

# 2. Migrations + seed + carga do gold (idempotente).
echo "[2/4] Migrations e dados..."
alembic upgrade head
python "$ROOT/scripts/seed_dev.py"

# 3. Backend
echo "[3/4] Iniciando backend FastAPI (porta 8000)..."
uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"
sleep 3

# 4. Frontend
echo "[4/4] Iniciando frontend Next.js (porta 3000)..."
cd "$ROOT/frontend"
npm run dev -- --port 3000 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

echo ""
echo "✓ Tudo rodando!"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
echo "  Admin: admin / copa2026   ·   Teste: teste / copa2026"
echo "  Coleta automática: a cada ${AUTO_COLLECT_MINUTES} min"
echo ""
echo "Pressione Ctrl+C para encerrar (o Postgres segue rodando no Docker)."

# Aguarda ambos os processos
wait $BACKEND_PID $FRONTEND_PID
