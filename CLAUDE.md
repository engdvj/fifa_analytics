# CLAUDE.md

Orientações para o Claude Code ao trabalhar neste repositório.

## O que é este projeto

Pipeline Python para acompanhar e analisar os 104 jogos da Copa do Mundo 2026 usando **exclusivamente a API oficial da FIFA** (sem fontes de terceiros). Gera relatórios Markdown por jogo e por torneio, scores analíticos de seleções e jogadores, um dashboard HTML interativo e uma API REST de bolão de palpites. Tudo a partir de dados oficiais, sem chave de API, sem scraping.

**Fonte única:** `src/fifa_analytics/fifa/` — sem worldcup2026, ESPN, Wikipedia ou 365Scores.

## Arquitetura

```
fifa/client.py  →  raw (data/raw/fifa/)
                       ↓
              fifa/transforms.py  →  silver (data/silver/fifa/)
                                          ↓
                              gold (data/gold/)  →  templates/  →  reports/
                                          ↓
                                       api/app/  (bolão FastAPI)
```

Camadas de código:
- `src/fifa_analytics/fifa/` — cliente HTTP + transforms + pipeline (fonte única)
- `src/fifa_analytics/analytics/` — scores, Elo, calibração, estilo de jogo
- `src/fifa_analytics/reporting/` — renderização Jinja2 e montagem de relatórios
- `src/fifa_analytics/workflows/` — orquestração de ponta a ponta
- `src/fifa_analytics/validation/` — validação de schema dos DataFrames
- `src/fifa_analytics/utils/` — I/O, logging, tempo (sem dependências internas)
- `api/` — FastAPI + Postgres (bolão de palpites, pontuação, ranking)

## A fonte: FIFA oficial

Duas APIs públicas, sem autenticação, sem chave. Basta `User-Agent` de browser (já configurado em `fifa/client.py`).

### Identificadores fixos (Copa 2026)

| O quê | Valor |
|---|---|
| `IdCompetition` | `17` |
| `IdSeason` | `285023` |

### FIFA Data API v3 — `https://api.fifa.com/api/v3`

Dados estruturais: calendário, jogos, escalações, eventos.

| Endpoint | O que retorna | Implementado |
|---|---|---|
| `/calendar/matches?idCompetition=17&idSeason=285023&language=en&count=200` | 104 jogos: placar, status, stage, grupo, stadium, `Properties.IdIFES` | ✅ `client.fetch_calendar_matches()` |
| `/live/football/17/285023/{idStage}/{idMatch}?language=en` | Detalhe completo: escalação com posição tática, gols, cartões, subs, árbitros | ❌ pendente |
| `/timelines/17/285023/{idStage}/{idMatch}?language=en` | Timeline de eventos (ordem cronológica) | ❌ pendente |

### FIFA Data Hub — `https://fdh-api.fifa.com/v1`

Dados avançados/tracking. Usa **`IdIFES`** (não `IdMatch`). O `IdIFES` já vem no `calendar/matches` em `Properties.IdIFES` (104/104) — uma única chamada resolve o mapeamento.

| Endpoint | O que retorna | Implementado |
|---|---|---|
| `/stats/match/{IdIFES}/teams.json` | 145 métricas por time, por jogo (formato long `[[nome, valor, oficial], ...]`) | ✅ `client.fetch_match_team_stats()` |
| `/stats/match/{IdIFES}/players.json` | Métricas por jogador, por jogo | ❌ pendente |
| `/stats/season/285023/team/{idTeam}.json` | 145 métricas acumuladas por time | ❌ pendente |
| `/stats/season/285023/players.json` | ~5.4 MB — 1249 jogadores × 119 métricas | ❌ pendente |
| `/powerranking/season/285023.json` | ~600 KB — Power Ranking por jogador (attacking/defensive/creativity + histórico por rodada) | ❌ pendente |
| `/powerranking/match/{IdIFES}.json` | Power Ranking daquele jogo | ❌ pendente |

### Grupos de métricas de alto valor (fdh)

- **Qualidade de chance:** `XG`, `Threat`, `AttemptAtGoal*` desmembrado por zona/origem/desfecho
- **Controle territorial:** `PitchControl`, `FinalThirdPitchControl`, `Possession`, `NumberOfPossessionSequences`
- **Fases de jogo (16 métricas `Phase*`):** AttackingTransition, BuildUp(Opposed/Unopposed), Counterattack, CounterPress, DefensiveTransition, FinalThird, High/Mid/LowBlock, High/Mid/LowPress, LongBall, Progression, Recovery, SetPieces — **substitui** o z-score inferido de estilo
- **Tracking físico:** `TotalDistance`, `Sprints`, `SpeedRuns`, `AvgSpeed`, `TopSpeed`
- **Sob pressão:** `ForcedTurnovers`, `DistributionsUnderPressure`, `DefensivePressuresApplied`
- **Progressão:** `CompletedBallProgressions`, `CompletedSwitchesOfPlay`
- **Goleiro:** `GoalkeeperSaves`, `GoalkeeperSavePercentage`
- **Disciplina:** `Fouls(For/Against)`, `Yellow/RedCards`, `Offsides`

## Convenções

### match_id canônico

Formato: `copa_2026_jogo_NNN` (ex: `copa_2026_jogo_001`). Derivado de `MatchNumber` da v3. Gerado por `fifa/transforms.make_match_id()`. Nunca usar `IdMatch` (formato `400…`) nem `IdIFES` em relatórios finais.

### Fluxo de dados

```
data/raw/fifa/{endpoint}/date=YYYYMMDD/collected_at=TS/*.json   ← snapshots brutos
data/silver/fifa/                                                ← DataFrames normalizados
data/gold/                                                       ← pronto para API e reports
  dim_match.parquet          (uma linha por jogo)
  fact_team_match_stats.parquet   (long: match_id + id_team + metric + value)
  fact_events.parquet        (linha do tempo por jogo)     ← pendente
  fact_lineups.parquet       (escalações)                  ← pendente
  fact_player_match_stats.parquet                          ← pendente
```

### Nomes de times

Normalizados via `config/teams_mapping.yaml` + `transforms/team_names.traduzir_selecao()`. Sempre passar por essa função antes de salvar qualquer string de país.

### Nomes de jogadores

Limpeza: `utils/text.clean_person_name()`. Chave de join: `utils/text.person_name_key()`. A FIFA às vezes usa espaços extras, abreviações e acentos divergentes — normalizar na raiz (`fifa/transforms`) e não nos relatórios.

### Relatórios

- Fragmentos em `reports/fragments/{match_id}/NN_secao.md` — gerados por `reporting/fragments.py`
- Relatório final em `reports/final/{match_id}.md` — montado por `reporting/build_report.py`
- Seções controladas por `config/report_sections.yaml`
- Templates em `templates/fragments/*.md.j2`

### Narrativa do jogo

`reports/fragments/{match_id}/01b_story.md` — o Python gera um template; Claude reescreve como prosa via skill `atualizar-jogo`. O marcador `<!-- narrativa-manual -->` na linha 1 protege de sobrescrita. Sem o marcador o template volta silenciosamente. Após editar: `fifa-analytics remontar-relatorio {match_id}`.

### Scores de seleção

`TEAM_SCORE_WEIGHTS` em `analytics/scores.py`:
- **Fixos:** `score_resultado` (0.35), `score_forca_relativa` (0.15 escalado por Elo maturity)
- **Calibrados (RidgeCV):** `score_ataque`, `score_defesa`, `score_eficiencia`, `score_controle` — regressão contra saldo de gols real, features das métricas fdh quando disponíveis

`score_forca_relativa` é escalado por `_elo_maturity_factor()`: no início do torneio todos começam em Elo 1500 — o peso cresce conforme os ratings se diferenciam de verdade.

### Métricas descritivas (fora do score_geral)

Calculadas e exibidas mas **não entram no `score_geral`**:
- `score_disciplina` — faltas + cartões/jogo. Alta nota = disciplinado.
- `estilo_jogo` — leitura das 16 métricas `Phase*` do fdh (quando disponível), senão z-score inferido. Descritivo, não qualitativo.

## O que NÃO fazer

- Não criar adaptadores de fonte fora de `src/fifa_analytics/fifa/` — fonte única
- Não reintroduzir worldcup2026, ESPN, Wikipedia ou 365Scores
- Não reconciliar entre fontes (não existe mais `SOURCE_PRIORITY`, não existe `indice-canonico`)
- Não salvar DataFrames em `reports/` — Markdown é saída, não base de dados
- Não criar notebook por jogo — notebooks são por processo, parametrizados
- Não hardcodar `IdMatch` (400…) ou `IdIFES` nos relatórios finais — usar `match_id` canônico
- Não chamar transforms complexos dentro de `fifa/client.py` — normalize em `fifa/transforms.py`
- Não ignorar `config/report_sections.yaml` ao adicionar seções
- Não commitar `data/`, `logs/`, `outputs/` — estão no `.gitignore`
- Não commitar `manifests/*.yaml` nem `manifests/*.parquet` — gerados automaticamente
- Não commitar `reports/fragments/`, `reports/final/`, `reports/tournament/` — gerados

## CLI

```bash
# Ativar ambiente (Windows)
.venv\Scripts\activate

# Coletar tudo (calendário + stats dos jogos finalizados)
fifa-analytics fifa-coletar

# Com flag para incluir jogos ainda não finalizados
fifa-analytics fifa-coletar --todos

# Outros passos (ainda legados, aguardam substituição)
fifa-analytics relatorios-basicos  # gera fragmentos + relatórios finais
fifa-analytics status-torneio      # standings, status, pendências
fifa-analytics scores              # scores e rankings
fifa-analytics calibrar-pesos      # calibra pesos via RidgeCV; --forcar ignora intervalo mínimo
fifa-analytics reprocessar-snapshots --jogo N   # snapshot incremental do N-ésimo jogo finalizado
fifa-analytics remontar-relatorio {match_id}    # remonta relatório sem recalcular

# Dashboard HTML
python scripts/bar_chart_race.py

# Testes
pytest -q
pytest tests/test_fifa_transforms.py -q
pytest tests/test_platform_api.py -q
```

## Arquivos de configuração

| Arquivo | Uso |
|---|---|
| `config/pipeline.yaml` | Defaults (status válidos, timezone) |
| `config/sources.yaml` | Fontes disponíveis — apenas `fifa` está habilitada nesta branch |
| `config/report_sections.yaml` | Seções do relatório por jogo — ordem e obrigatoriedade |
| `config/teams_mapping.yaml` | Tradução de nomes de países para pt-BR |
| `config/teams_info.yaml` | Infos curadas das 48 seleções (técnico, títulos, apelido) — não vem de fonte |

## Schemas

`schemas/*.yaml` definem colunas esperadas por tipo. Validação real em `validation/schemas.py` via `validate_required_columns(df, schema="matches.yaml")`. Use sempre antes de gravar em silver/gold.

## API — plataforma de bolão (`api/`)

FastAPI + Postgres (SQLAlchemy + Alembic). Independente do pipeline — lê o gold via loader.

**Models:** `Match` (espelho de `dim_match.parquet`), `User`, `Pool`, `PoolMember`, `ScoringRule`, `Prediction`.

**Routers:**
- `GET /matches` — lista jogos (filtro por status)
- `GET /matches/{match_id}/stats` — métricas avançadas do jogo (lê `fact_team_match_stats.parquet`)
- `POST /users` / `GET /users` — usuários do bolão
- `POST /pools` / `GET /pools` — bolões
- `POST /pools/{pool_id}/predictions` — palpites (upsert)
- `GET /pools/{pool_id}/ranking` — ranking de pontos

**Loader:** `api/app/loaders/load_matches.py` — upsert de `dim_match.parquet` → tabela `matches`; recalcula pontos dos palpites quando um jogo passa a `finalizado`.

**Motor de pontuação:** `api/app/scoring/engine.py` — data-driven (interpreta `ScoringRule.spec`). Regras builtin seedadas: `Clássico` (exato 5/vencedor 3), `Detalhado` (exato 6/saldo 3/vencedor 2), `Soma de acertos`.

**Docker:**
```bash
# Subir Postgres + API
docker compose -f infra/docker-compose.yml up -d

# Migrations
alembic upgrade head
```

**Variáveis de ambiente (`.env` a partir de `.env.example`):**
```
DATABASE_URL=postgresql+psycopg2://fifa:fifa@localhost:5432/fifa
```

## Dashboard HTML (`scripts/bar_chart_race.py`)

Gera `reports/tournament/ranking_race.html` — arquivo único autossuficiente (JSON embutido). Duas abas: **Ranking Race** (corrida de barras jogo a jogo) e **Seleções** (grade das 48 → modal com Resumo/Jogos/Elenco). Ao editar:
- CSS+JS dentro de f-string Python: `{{`/`}}` escapam chaves literais; regex JS precisa de `\\` para barras
- Sempre valide: `tests/test_dashboard_js.py` extrai o `<script>` e roda `node --check`
- Itens flex que rolam precisam de `min-height: 0` no pai (causa recorrente de "scroll não funciona")
- Jogadores casados **por nome** — normalizar em `fifa/transforms` antes de gravar

## Estado atual da implementação

### Implementado (fonte FIFA)

- `fifa/client.py` — `fetch_calendar_matches()`, `fetch_match_team_stats()`, retry com backoff, 404 definitivo
- `fifa/transforms.py` — `normalize_matches()`, `normalize_match_team_stats()`, `make_match_id()`
- `fifa/pipeline.py` — `run()`: coleta calendário + stats de jogos finalizados → raw → silver → gold
- CLI: comando `fifa-coletar` (com flag `--todos`) já registrado em `cli.py`
- API FastAPI: modelos, routers, loader, scoring engine, Alembic migration inicial
- Testes: `test_fifa_transforms.py`, `test_platform_api.py`, `test_scoring_engine.py`

### Pendente (próximas implementações)

| O quê | Onde | Prioridade |
|---|---|---|
| `client.fetch_match_player_stats(id_ifes)` + transform | `fifa/client.py`, `fifa/transforms.py` | Alta |
| `client.fetch_match_live(id_stage, id_match)` (escalações + eventos) + transforms | idem | Alta |
| `client.fetch_match_timeline(id_stage, id_match)` + transform | idem | Alta |
| `client.fetch_power_ranking_season()` + transform | idem | Média |
| `client.fetch_season_players()` (1249 jogadores × 119 métricas) | idem | Média |
| `client.fetch_season_team_stats(id_team)` por time (48 chamadas) | idem | Média |
| Integrar `fact_events`, `fact_lineups`, `fact_player_match_stats` no gold | `fifa/pipeline.py` | Alta |
| Atualizar `reporting/` para ler dados FIFA (sem fallback legado) | `reporting/` | Alta |
| CI (`.github/workflows/ci.yml`) com Postgres + pytest | nova | Alta |
| Limpar CLI: remover comandos de fontes legadas (worldcup2026, espn, wikipedia, 365scores, atualizar, indice-canonico) | `cli.py` | Média |

## Problemas conhecidos

- `.venv` não existe no Windows — criar com `python -m venv .venv` e `pip install -e ".[api,dev]"` antes de rodar qualquer coisa
- Watcher (`watcher/`) usa socket Unix (`/tmp/`) — não funciona no Windows sem ajuste de path
- Comandos legados no CLI ainda importam módulos de fontes antigas; testes legados continuam passando mas serão removidos conforme a migração avança
