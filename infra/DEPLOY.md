# Deploy na VM Oracle (CI/CD)

Pipeline: **CI** roda em todo push/PR (`pytest` + `tsc`). Ao dar push na `main`, o
job **deploy** conecta na VM por SSH e roda `docker compose up -d --build` — a VM
builda as imagens (sem registry) e sobe Postgres + API + Frontend.

```
push/PR ──> CI (backend: pytest | frontend: tsc + lint)
push main ─> deploy (SSH na VM ──> git reset --hard origin/main ──> docker compose up -d --build)
```

## 1. Secrets do GitHub (Settings → Secrets and variables → Actions)

| Secret | Valor |
|---|---|
| `VM_HOST` | IP público da VM Oracle |
| `VM_USER` | usuário SSH (ex.: `ubuntu` ou `opc`) |
| `VM_SSH_KEY` | **chave privada** SSH (conteúdo completo, com `-----BEGIN ...-----`) |
| `VM_APP_DIR` | caminho do repo clonado na VM (ex.: `/home/ubuntu/fifa_analytics`) |

A chave **pública** correspondente precisa estar em `~/.ssh/authorized_keys` na VM.

## 2. Preparação única da VM

```bash
# clonar o repo no caminho de VM_APP_DIR
git clone https://github.com/<voce>/fifa_analytics.git
cd fifa_analytics

# criar infra/.env com os segredos de produção
cat > infra/.env <<'EOF'
POSTGRES_USER=fifa
POSTGRES_PASSWORD=<senha-forte>
POSTGRES_DB=fifa
JWT_SECRET_KEY=<segredo-forte>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<senha-admin>
ADMIN_NAME=Admin
# URLs públicas (troque pelo IP/domínio da VM):
NEXT_PUBLIC_API_URL=http://<IP-DA-VM>:8000
CORS_ORIGINS=http://<IP-DA-VM>:3000
EOF

# popular o gold (a API lê data/gold/*.parquet; data/ é gitignored):
#   opção A) rodar a coleta na VM:  pip install -e ".[api]" && fifa-analytics fifa-coletar
#   opção B) copiar a pasta data/ da sua máquina:  rsync -av data/ <user>@<ip>:.../fifa_analytics/data/

# primeira subida
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

> **`NEXT_PUBLIC_API_URL` é embutido no build do frontend** — se mudar o IP/domínio,
> precisa rebuildar o `web` (o deploy já faz `--build`).

## 3. Portas (Oracle)

Libere **3000** (frontend) e **8000** (API) na *Security List/NSG* do Oracle Cloud
**e** no firewall da VM:

```bash
sudo iptables -I INPUT -p tcp --dport 3000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
# (ou firewalld) sudo firewall-cmd --add-port=3000/tcp --add-port=8000/tcp --permanent && sudo firewall-cmd --reload
```

O Postgres **não** é exposto publicamente (só na rede interna do compose).

## 4. Acesso

- Frontend: `http://<IP-DA-VM>:3000`
- API:      `http://<IP-DA-VM>:8000`

## Notas

- As migrations rodam sozinhas no start da API (`alembic upgrade head` no CMD).
- O `seed_admin` cria o admin a partir de `ADMIN_USERNAME`/`ADMIN_PASSWORD`
  (não sobrescreve a senha se o usuário já existir).
- Próximo passo recomendado: pôr um reverse proxy (Caddy/Nginx) com HTTPS na
  frente e servir tudo em `:443` (aí `NEXT_PUBLIC_API_URL`/`CORS_ORIGINS` viram
  `https://<dominio>`).
```
