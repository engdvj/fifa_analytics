# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Orientações para o Claude Code ao trabalhar neste repositório.

## O que é este projeto

Pipeline Python + Jupyter para acompanhar e analisar os 104 jogos da Copa do Mundo 2026. Coleta dados de múltiplas fontes (worldcup26.ir, ESPN, Wikipedia, 365scores), reconcilia num índice canônico e gera relatórios Markdown por jogo e por torneio, além de um dashboard HTML interativo. O comando `fifa-analytics atualizar` faz o fluxo completo: coleta as fontes → reconcilia no índice canônico (gold) → gera relatórios → status → scores. **Coletar sem reconciliar não atualiza o gold** — o `dim_match` (lido pelo watcher) só reflete novos placares/status após o `indice-canonico`, que o `atualizar` já inclui.

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

### Narrativa do jogo (escrita por Claude, não Python)
A seção "A história do jogo" (`reports/fragments/{match_id}/01b_story.md`) tem um texto template determinístico do Python (`_build_match_story` em `canonical_reports.py`), mas a versão boa é **prosa reescrita por Claude** via a skill `atualizar-jogo` (`.claude/skills/atualizar-jogo/`). O marcador `<!-- narrativa-manual -->` na 1ª linha do fragmento protege a narrativa de ser sobrescrita pelo pipeline Python (`relatorios-basicos`/`atualizar`). Sem o marcador, o template volta silenciosamente. Para reescrever uma narrativa: leia os dados gold reais, escreva o fragmento com o marcador, e rode `fifa-analytics remontar-relatorio {match_id}` (remonta sem recalcular).

### Manifests
`manifests/copa_2026_jogo_NNN.yaml` — metadados de cada jogo: status do relatório, qualidade, fontes usadas, IDs por fonte. Gerado automaticamente por `reporting/build_report.py`. Não editar à mão.

### Nomes de times
Normalizados via `config/teams_mapping.yaml` + `transforms/team_names.traduzir_selecao()`. Sempre passar nomes pela função antes de salvar.

### Pesos do score de seleções (calibração incremental)
`TEAM_SCORE_WEIGHTS` em `analytics/scores.py` define os pesos de design (fixos: `score_resultado`=0.35, `score_forca_relativa`=0.15). Os 4 componentes de processo (`score_ataque`, `score_defesa`, `score_eficiencia`, `score_controle`) são recalibrados a cada 2 jogos novos finalizados via regressão (RidgeCV) em `analytics/calibration.py`, contra saldo de gols real — não confunda com os pesos fixos, que não entram nessa regressão por serem circulares (resultado) ou acumulados (Elo). `scores_pipeline._load_latest_calibrated_weights()` lê o snapshot mais recente em `data/gold/analytics/calibration_history/` e aplica via `apply_calibrated_weights()`. Rode `fifa-analytics calibrar-pesos` após coletar jogos novos para gerar um snapshot; ele só gera se houver +2 jogos desde o último (`--forcar` ignora isso).

`score_forca_relativa` tem peso adicionalmente escalado por `_elo_maturity_factor()`: no início do torneio, com todos os times no rating Elo inicial (1500), vencer não prova força relativa de fato — o peso cresce organicamente conforme os ratings se diferenciam de verdade (variância real do Elo vs. teto teórico simulado via `_simulate_max_elo_variance`). A fração "não ganha" é transferida para `score_resultado`.

### Métricas informacionais (fora do score_geral)
Duas métricas em `analytics/scores.py` são calculadas, exibidas e ranqueadas, mas **não entram no `score_geral`** — descrevem, não avaliam qualidade:
- `score_disciplina`: índice de violência (faltas + cartões/jogo). Nota alta = disciplinado.
- **Estilo de jogo** (`_add_team_style`): assinatura DESCRITIVA de COMO o time joga, em 4 eixos z-score 0–100 relativos ao torneio (`estilo_posse`, `estilo_pressao`, `estilo_verticalidade`, `estilo_largura`) + um rótulo textual (`estilo_jogo`) que junta os 2 traços mais marcantes via `_style_label` (sem extremos = "equilibrado"). Atraído ao neutro pela confiança da amostra (1 jogo ≈ "equilibrado"; afia conforme acumulam jogos). Exposto no relatório da seleção, em `reports/rankings/selecoes/estilo.md` (tabela comparativa, não ranking ordenado) e no relatório do jogo (lido de `team_scores.parquet`, pode estar 1 ciclo defasado pois `relatorios-basicos` roda antes de `scores`). Estilo não é melhor/pior — não confundir com os componentes de qualidade.

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
fifa-analytics 365scores           # segunda fonte de validação: formação, expected_assists, key_passes, dribbles_won
fifa-analytics indice-canonico     # reconcilia fontes → gold
fifa-analytics relatorios-basicos  # gera fragmentos + relatórios finais
fifa-analytics status-torneio      # standings, status, pendências
fifa-analytics scores              # scores e rankings de times e jogadores
fifa-analytics calibrar-pesos      # calibra pesos de score_geral via regressão (RidgeCV); --forcar ignora o intervalo mínimo
fifa-analytics reprocessar-snapshots --jogo N  # (re)gera o snapshot do N-ésimo jogo finalizado (estado incremental)
fifa-analytics remontar-relatorio {match_id}   # remonta o relatório final sem recalcular (após editar narrativa)

# Dashboard HTML + watcher
python scripts/bar_chart_race.py   # gera reports/tournament/ranking_race.html
bash watcher/run-window.sh         # app desktop de processamento sob demanda

# Testes
pytest -q
pytest tests/test_cli.py -q                       # um arquivo
pytest tests/test_update_pipeline.py::test_run_update_pipeline_orchestrates_full_refresh  # um teste
```

## Arquivos de configuração

| Arquivo | Uso |
|---|---|
| `config/pipeline.yaml` | Defaults e lista de status válidos (documentário, não carregado automaticamente) |
| `config/sources.yaml` | Fontes disponíveis, roles, endpoints (lido pelos notebooks) |
| `config/report_sections.yaml` | Seções do relatório por jogo — ordem e obrigatoriedade |
| `config/teams_mapping.yaml` | Tradução de nomes de países para pt-BR |
| `config/teams_info.yaml` | Infos curadas à mão das 48 seleções (técnico, títulos, apelido, curiosidade) — não vem de fonte; usado pelo dashboard HTML |

## Schemas

`schemas/*.yaml` definem as colunas esperadas por tipo de dado. Ainda não são carregados automaticamente pelo código — servem como referência para implementar validação real via `validation/schemas.py`.

## Watcher (`watcher/`)

App desktop (PySide6) que processa jogos sob demanda. `watch-fifa.py` é o daemon; `fifa_progress.py` é a janela flutuante; comunicam por socket Unix (`/tmp/fifa-copa.sock`) + estado em `/tmp/fifa-copa.json`. Suba com `bash watcher/run-window.sh` (a janela é a "dona": fechar a janela encerra o daemon). Log em `logs/watcher.log`.

Ao clicar "Processar", o daemon roda por jogo: **coleta** (`fifa-analytics atualizar`) → **snapshot** (`reprocessar-snapshots --jogo N`) → **narrativa** (`claude -p` headless com a skill atualizar-jogo) → **HTML** (`scripts/bar_chart_race.py`). Pontos críticos:
- O que marca um jogo como "processado" é o arquivo `data/gold/analytics/snapshots/snapshot_jogo_NNN.parquet`. Se ele não for salvo, o jogo reaparece como pendente.
- O `N` do watcher é a posição **cronológica entre finalizados**, não o número do match_id; mapeia via `match_order.json`.
- Etapas longas (coleta, narrativa) emitem heartbeat a cada ~5s; a janela tem guarda de "daemon morto" se o estado passar de ~30s sem atualizar — sem heartbeat ela falsamente mostra "erro/ocioso".
- A narrativa é trabalho de LLM: o daemon chama `claude` headless. Override com `FIFA_SKIP_NARRATIVE=1`; timeouts por etapa via `FIFA_*_TIMEOUT`.

## Dashboard HTML (`scripts/bar_chart_race.py`)

Gera `reports/tournament/ranking_race.html` — um arquivo único e autossuficiente (dados embutidos como JSON, sem servidor) com duas abas: **Ranking Race** (corrida de barras jogo a jogo) e **Seleções** (grade das 48 seleções → modal por seleção com Resumo/Jogos/Elenco). É o passo final do watcher e roda standalone (`python scripts/bar_chart_race.py`). Ao editar:
- Quase tudo é CSS+JS dentro de um `f-string` Python gigante — `{{`/`}}` escapam chaves literais, e barras em regex JS precisam ser `\\` (ex: `split(/\\s+/)`) senão dão SyntaxWarning.
- Sempre valide o JS gerado: extraia o `<script>` e rode `node --check`. Para testar lógica, stube o DOM fazendo `getElementById` retornar `null` para ids inexistentes (imita o navegador — captura referências a elementos removidos, que travam o modal).
- Itens flex que rolam precisam de `min-height: 0` no pai, senão crescem além da viewport em vez de scrollar (causa recorrente de "scroll não funciona").
- Jogadores são casados **por nome** entre lineup/eventos/commentary/365scores. Os nomes vêm com lixo (espaço extra: "Gavi "; abreviação: "C. Larin"; acento divergente no 365scores). Normalize na raiz (`_strip_name_cols`, `_name_key`) — senão gols/cartões/substituições não casam.
- Substituições vêm de `fact_commentary` (ESPN, `play_type='substitution'`, texto "X replaces Y"), não dos eventos. Stats por jogador/partida: canonical (ESPN, por match_id) + 365scores (rating/xA/passes, casado por nome).

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
