# Plano de CI/CD

> **Status:** apenas planejado (2026-06-19). Nada implementado ainda. Ponto de
> retomada para a próxima sessão.

O repo está no GitHub (`engdvj/fifa_analytics`) → **GitHub Actions** é o CI.
Docker **não** está instalado na máquina local — por isso a validação do
Postgres real acontece **no CI** (service container), não localmente.

## Contexto / por quê

A fundação da plataforma (ver `project-plataforma-bolao` na memória e o plano
em `.claude/plans/`) foi construída e testada **só em SQLite**. Falta validar
contra **Postgres real** (JSONB, constraints, tipos de data) antes de empilhar
escopo novo (auth, frontend, deploy). O CI resolve isso de forma reproduzível e
automática a cada push — melhor que um teste manual único.

## Decisão de recorte

- **Fazer agora (próxima sessão): só CI.** Valida a fundação. Custo financeiro
  zero (Actions é grátis pra repo; API FIFA é pública).
- **Adiar: CD (deploy automático na VM Oracle).** Exige SSH/secrets da VM,
  Docker na VM, registry de imagem e app pronta pra produção — pré-requisitos
  que ainda não existem. CD entra na **fase de deploy Oracle**, quando houver
  VM acessível e app deployável. "Construir o cano antes de ter água" agora.

## CI a implementar (`.github/workflows/ci.yml`)

Gatilho: `push` e `pull_request`.

Job **test** (Ubuntu, Python 3.12):
1. `services: postgres:16` (service container) com user/db de teste e healthcheck.
2. `pip install -e ".[api,dev]"`.
3. `DATABASE_URL=postgresql+psycopg2://...@localhost:5432/...`
4. `alembic upgrade head` → valida que a migration aplica em Postgres real
   (pega divergências JSON vs JSONB, server_default, etc).
5. `pytest -q` → suíte inteira (196+ testes) contra Postgres.

Checks adicionais a decidir na implementação (ficaram em aberto):
- **Lint/format (ruff)** — projeto ainda não tem linter; avaliar adicionar.
- **Rodar a suíte também em SQLite** (matriz) — garante que o dev local rápido
  sem Docker continua funcionando. Hoje os testes usam SQLite por padrão; o CI
  é que introduz o Postgres.

## CD futuro (esboço, fase de deploy Oracle)

Quando a app estiver pronta e a VM no jogo:
- Build da imagem Docker da API (`api/Dockerfile`) e push pra um registry
  (GHCR ou Oracle Container Registry).
- Workflow de deploy: SSH na VM Oracle (secrets no GitHub) → `docker compose pull
  && up -d` → `alembic upgrade head`.
- Disparo: tag de release ou push na `main` (a definir).
- Pré-requisitos: VM com Docker, secrets (SSH key, DATABASE_URL de prod),
  domínio + HTTPS.

## Pendências da fundação que o CI vai exercitar
- Subir Postgres real e rodar `fifa-coletar` + loader + API encadeados nele
  (até agora só SQLite). O CI cobre migration + testes; o fluxo de coleta real
  contra Postgres pode virar um job/manual à parte.
