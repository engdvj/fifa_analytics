# CLAUDE.md

Orientações para o Claude Code ao trabalhar neste repositório.

## O que é este projeto

Pipeline Python + Jupyter para acompanhar e analisar os 104 jogos da Copa do Mundo 2026. Coleta dados de múltiplas fontes (worldcup26.ir, ESPN, Wikipedia), reconcilia num índice canônico e gera relatórios Markdown por jogo e por torneio.

## Arquitetura

```
Fonte (sources/) → raw (data/raw/) → silver (data/silver/) → gold (data/gold/)
                                                                      ↓
                                                  templates/ → fragments (reports/fragments/)
                                                                      ↓
                                                           relatório final (reports/final/)
```

Camadas:
- `src/fifa_analytics/sources/` — adaptadores de fontes externas (fetch + normalize)
- `src/fifa_analytics/transforms/` — raw dict/list → DataFrame com schema padrão
- `src/fifa_analytics/analytics/` — análises sobre DataFrames prontos
- `src/fifa_analytics/reporting/` — renderização Jinja2 e montagem de relatórios
- `src/fifa_analytics/workflows/` — orquestração de ponta a ponta
- `src/fifa_analytics/validation/` — comparação entre fontes e verificação de colunas
- `src/fifa_analytics/utils/` — I/O, logging, tempo (sem dependências internas)
- `notebooks/` — execução parametrizada por processo (00 a 11)

## Convenções

### match_id canônico
Formato: `copa_2026_jogo_NNN` (ex: `copa_2026_jogo_001`). Derivado do número de partida da fonte primária (worldcup2026). Nunca usar ID de fonte diretamente nos relatórios finais.

### Prioridade de fontes
`worldcup2026 > espn > wikipedia`. Definido em `SOURCE_PRIORITY` em `canonical_reports.py`.

### Fluxo de dados
- `data/raw/` — snapshots brutos particionados por `fonte/competicao/date=YYYYMMDD/collected_at=TIMESTAMP/`
- `data/silver/` — DataFrames normalizados por tipo (`matches/`, `events/`, `lineups/`, etc.)
- `data/gold/` — índice canônico reconciliado (`dim_match/`, `fact_events/`, `fact_team_match_stats/`, etc.)

### Relatórios
- Fragmentos em `reports/fragments/{match_id}/NN_secao.md` — gerados por `reporting/fragments.py`
- Relatório final em `reports/final/{match_id}.md` — montado por `reporting/build_report.py`
- Seções controladas por `config/report_sections.yaml`
- Templates em `templates/fragments/*.md.j2` e `templates/tournament/*.md.j2`

### Manifests
`manifests/copa_2026_jogo_NNN.yaml` — metadados de cada jogo: status do relatório, qualidade, fontes usadas, IDs por fonte. Gerado automaticamente por `reporting/build_report.py`. Não editar à mão.

### Nomes de times
Normalizados via `config/teams_mapping.yaml` + `transforms/team_names.traduzir_selecao()`. Sempre passar nomes pela função antes de salvar.

## O que NÃO fazer

- Não salvar DataFrames em `reports/` — Markdown é saída, não base de dados
- Não criar um notebook por jogo — notebooks são por processo, parametrizados
- Não hardcodar `match_id` de fonte nos relatórios finais
- Não chamar `normalize_*` dentro de `sources/` para DataFrames complexos — mover para `transforms/`
- Não ignorar `config/report_sections.yaml` ao adicionar novas seções de relatório
- Não commitar `data/`, `logs/`, `outputs/` — estão no `.gitignore`
- Não commitar `manifests/*.yaml` nem `manifests/*.parquet` — gerados automaticamente
- Não commitar `reports/fragments/`, `reports/final/`, `reports/tournament/` — gerados

## CLI

```bash
# Ativar ambiente
source .venv/bin/activate

# Fluxo completo
fifa-analytics atualizar

# Passos individuais
fifa-analytics worldcup2026        # fonte operacional principal
fifa-analytics espn                # enriquecimento ESPN
fifa-analytics wikipedia           # referência pública
fifa-analytics indice-canonico     # reconcilia fontes → gold
fifa-analytics relatorios-basicos  # gera fragmentos + relatórios finais
fifa-analytics status-torneio      # standings, status, pendências
fifa-analytics scores              # scores e rankings de times e jogadores

# Testes
pytest -q
```

## Arquivos de configuração

| Arquivo | Uso |
|---|---|
| `config/pipeline.yaml` | Defaults e lista de status válidos (documentário, não carregado automaticamente) |
| `config/sources.yaml` | Fontes disponíveis, roles, endpoints (lido pelos notebooks) |
| `config/report_sections.yaml` | Seções do relatório por jogo — ordem e obrigatoriedade |
| `config/teams_mapping.yaml` | Tradução de nomes de países para pt-BR |

## Schemas

`schemas/*.yaml` definem as colunas esperadas por tipo de dado. Ainda não são carregados automaticamente pelo código — servem como referência para implementar validação real via `validation/schemas.py`.

## Problemas conhecidos e pendências

Ver `planejamento_pipeline_copa_2026.md` seção "Checklist de melhorias" para o backlog atualizado.

Problemas ativos principais:
- `analytics/standings.py` é re-export inútil de `transforms/standings.py`
- `slugify()` duplicada em `analytics/scores.py` e `canonical_reports.py` — deveria estar em `utils/`
- URLs de fontes hardcoded nos módulos — deveriam vir de `config/sources.yaml`
- `config/pipeline.yaml` não é carregado pelo código, apenas documentário
- `schemas/*.yaml` não são usados para validação — `load_schema()` existe mas nunca é chamado
- `reports/players/`, `reports/teams/`, `reports/rankings/` não estão no `.gitignore`
- `manifests/tournament_status.parquet` deveria estar em `data/gold/`, não em `manifests/`
- Sources não implementadas (`fifa.py`, `football_data.py`, `balldontlie.py`) geram confusão — remover ou marcar claramente como stub
