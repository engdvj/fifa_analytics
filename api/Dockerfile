FROM python:3.12-slim

WORKDIR /app

# deps de sistema mínimas (psycopg2-binary já traz o necessário; build-essential
# só por segurança em wheels que faltem).
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY api ./api
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir -e ".[api]"

EXPOSE 8000

# roda migrations e sobe a API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.app.main:app --host 0.0.0.0 --port 8000"]
