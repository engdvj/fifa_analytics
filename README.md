# FIFA Analytics - Copa do Mundo 2026

Pipeline em Python + Jupyter para coletar, validar, analisar e gerar relatorios dos 104 jogos da Copa do Mundo 2026.

O projeto usa notebooks por processo, nao por partida. Cada notebook recebe parametros como `match_id`, `match_date` e `run_scope`, chama funcoes reutilizaveis em `src/` e grava dados em camadas `raw`, `silver` e `gold`.

## Arquitetura

```text
fontes de dados
-> data/raw
-> data/silver
-> data/gold
-> reports/fragments
-> reports/final
-> reports/tournament
```

## Instalar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Abrir os notebooks

```bash
jupyter lab
```

## Testar agora

Ative o ambiente virtual:

```bash
source .venv/bin/activate
```

Rode a suite de testes:

```bash
python -m pytest -q
```

Gere um relatorio de amostra de ponta a ponta:

```bash
python -m fifa_analytics amostra
```

Esse comando cria:

```text
data/raw/sample/...
data/silver/matches/matches.parquet
data/silver/teams/teams.parquet
data/silver/standings/standings.parquet
data/gold/standings/group_standings.parquet
reports/fragments/copa_2026_jogo_001/
reports/final/copa_2026_jogo_001.md
manifests/copa_2026_jogo_001.yaml
```

Gere dados a partir da Wikipedia:

```bash
python -m fifa_analytics wikipedia
```

Esse comando usa a pagina publica da Copa 2026 como fonte inicial para partidas e classificacao dos grupos. A Wikipedia nao e fonte oficial; os dados devem ser validados contra FIFA ou outra fonte operacional antes de conclusoes finais.

Gere dados a partir da API operacional gratuita `worldcup26.ir`:

```bash
python -m fifa_analytics worldcup2026
```

Esse comando coleta os 104 jogos, selecoes, estadios, classificacao dos grupos e eventos basicos de gols quando a fonte disponibiliza autores/minutos. A fonte e publica e nao oficial; por isso a pipeline tambem calcula a classificacao internamente e grava a validacao em `data/silver/validation_results/`.

Gere dados analiticos gratuitos a partir da ESPN:

```bash
python -m fifa_analytics espn
```

Esse comando coleta calendario, detalhes de eventos, estatisticas por selecao, escalacoes e estatisticas individuais quando disponiveis. Ele cria tabelas como:

```text
data/gold/fact_team_match_stats/espn_team_stats.parquet
data/gold/lineups/espn_lineups.parquet
data/gold/fact_player_match_stats/espn_player_stats.parquet
```

Atualize tudo em uma rodada unica:

```bash
python -m fifa_analytics atualizar
```

Esse comando coleta `worldcup2026` e ESPN, recria o indice canonico, gera relatorios de jogos finalizados, atualiza o status do torneio e recalcula os scores/rankings. Ele e uma atualizacao sob demanda, nao um servico em background. Para ignorar uma fonte temporariamente:

```bash
python -m fifa_analytics atualizar --sem-espn
python -m fifa_analytics atualizar --sem-worldcup2026
```

Crie o indice canonico de partidas, reconciliando ids das fontes:

```bash
python -m fifa_analytics indice-canonico
```

Esse comando cria:

```text
data/gold/dim_match/canonical_matches.parquet
data/gold/dim_match/source_match_map.parquet
data/gold/fact_events/canonical_events.parquet
data/gold/fact_team_match_stats/canonical_team_stats.parquet
data/gold/lineups/canonical_lineups.parquet
data/gold/fact_player_match_stats/canonical_player_stats.parquet
```

O `canonical_match_id` usa a numeracao estavel da fonte primaria quando ela existe, por exemplo `copa_2026_jogo_013`. Isso nao significa necessariamente ordem temporal. Para analises cronologicas, use a coluna `temporal_order`; para a numeracao original da fonte primaria, use `match_number`.

Gere relatorios basicos no estilo canonico, com um relatorio por jogo real:

```bash
python -m fifa_analytics relatorios-basicos
python -m fifa_analytics status-torneio
```

O comando `relatorios-basicos` usa `canonical` por padrao, gera relatorios para as partidas `finalizado` e inclui metadados das fontes vinculadas ao jogo. Quando as fontes trazem autores e minutos dos gols, ele tambem preenche a linha do tempo basica da partida.

Nos relatorios por jogo, a secao de selecoes inclui comparativo de `nota_jogo` e frente a frente por componente. A secao de escalacoes junta titulares, reservas com impacto registrado, nota do jogador na partida e principais estatisticas individuais.

Para processar outro status:

```bash
python -m fifa_analytics relatorios-basicos --status agendado
python -m fifa_analytics relatorios-basicos --status todos
python -m fifa_analytics status-torneio --source canonical
```

O comando `status-torneio` cria:

```text
manifests/tournament_status.parquet
reports/tournament/status.md
reports/tournament/standings.md
reports/tournament/pendencias_relatorios.md
```

Gere scores acumulados por selecao e jogador:

```bash
python -m fifa_analytics scores
```

Esse comando cria tabelas analiticas derivadas e relatorios navegaveis por entidade:

```text
data/gold/analytics/team_match_features.parquet
data/gold/analytics/team_scores.parquet
data/gold/analytics/player_match_features.parquet
data/gold/analytics/player_scores.parquet
reports/teams/index.md
reports/teams/{selecao}.md
reports/players/index.md
reports/players/{jogador}_{selecao}.md
reports/rankings/index.md
reports/rankings/selecoes/index.md
reports/rankings/selecoes/{metrica}.md
reports/rankings/jogadores/index.md
reports/rankings/jogadores/{metrica}.md
```

O score inicial e uma nota de 0 a 100, transparente e recalculavel. Para selecoes, combina ataque, defesa, controle, eficiencia e `fair_play`. O componente `fair_play` e uma nota pequena de controle disciplinar: menos faltas, amarelos e vermelhos melhoram a nota; ele nao mede qualidade tecnica. Para jogadores, a nota geral combina impacto medio por jogo e impacto acumulado; cartoes entram como penalizacao no impacto. Os rankings principais ficam em `reports/rankings/selecoes/index.md` e `reports/rankings/jogadores/index.md`.

Tambem sao gerados rankings separados por metrica. Para selecoes: `geral`, `ataque`, `defesa`, `controle`, `eficiencia` e `fair_play`. Para jogadores: `geral`, `medio`, `acumulado`, `ofensivo` e `goleiro`.

Para evitar falsos positivos em poucos jogos, cada nota tem um `nivel_evidencia` textual: `baixa`, `media` ou `alta`. Isso nao e chance de acerto; e um aviso de estabilidade da nota. Com poucos jogos, a nota existe e entra no ranking, mas aparece com evidencia baixa. Os arquivos Markdown sao saidas geradas; a fonte real continua sendo `data/gold/analytics/`.

Componentes da nota de selecoes:

- `ataque`: volume/producao ofensiva, usando gols, chutes e chutes no alvo por jogo;
- `defesa`: solidez defensiva, usando gols sofridos, chutes sofridos, chutes no alvo sofridos e jogos sem sofrer gol;
- `controle`: dominio com bola, usando posse, passes e precisao de passe;
- `eficiencia`: aproveitamento ofensivo, usando gols por chute e chutes no alvo por chute;
- `fair_play`: controle disciplinar, usando faltas, amarelos e vermelhos.

`eficiencia` nao e a mesma coisa que `ataque`: ataque mede volume/producao; eficiencia mede o quanto esse volume vira perigo/gol.

`peso_evidencia` aparece apenas na auditoria da nota. Ele e um fator tecnico usado para reduzir exageros quando ha pouca amostra, dados incompletos ou baixo teste defensivo. Exemplo: uma defesa pode ter nota bruta alta por nao sofrer gol, mas a nota usada no ranking e ajustada se ela quase nao foi testada.

Atualizacao dos scores:

- os scores sao recalculados sempre que `python -m fifa_analytics scores` roda;
- o comando nao soma em cima do Markdown anterior;
- ele le novamente as tabelas canonicas em `data/gold`, reconstrói features por jogo e gera rankings atualizados;
- quando novos jogos forem coletados, basta rodar `python -m fifa_analytics atualizar` para refazer fontes, indice canonico, relatorios, status e scores em sequencia.

Estatisticas usadas na primeira versao:

- acumulados: gols, assistencias, chutes, pontos, cartoes, defesas;
- medias por jogo: gols por jogo, chutes por jogo, gols contra por jogo, impacto por jogo;
- razoes: gols por chute, chutes no alvo por chute, aproveitamento;
- normalizacao por percentil relativo ao torneio atual;
- ajuste conservador por evidencia para reduzir exagero em amostra pequena.
- links de Obsidian entre rankings, selecoes, jogadores e relatorios de jogos; em tabelas, os aliases usam `\|` para nao quebrar colunas Markdown.

Estatisticas candidatas para a proxima evolucao:

- mediana por jogo, para reduzir efeito de uma goleada isolada;
- desvio padrao, para medir consistencia;
- media movel dos ultimos jogos, para forma recente;
- z-score/percentil por metrica, para comparar selecoes e jogadores;
- ajuste por forca do adversario;
- rankings por perfil de jogador, separando goleiros, defensores, meio-campistas e atacantes.

## Modos de uso

Jogo especifico:

```python
run_scope = "jogo_unico"
match_id = "copa_2026_jogo_001"
```

Jogos de uma data:

```python
run_scope = "data_de_jogos"
match_date = "2026-06-16"
```

Jogos finalizados pendentes:

```python
run_scope = "finalizados_pendentes"
```

Torneio inteiro:

```python
run_scope = "torneio"
```

## Notebooks

- `00_match_index.ipynb`: cria e atualiza o indice de partidas.
- `01_ingest_sources.ipynb`: coleta dados das fontes e salva snapshots raw.
- `02_validate_match_data.ipynb`: valida dados entre fontes e schemas.
- `03_match_context.ipynb`: gera contexto da partida.
- `04_lineups.ipynb`: processa escalacoes.
- `05_match_events.ipynb`: monta timeline de eventos.
- `06_team_stats.ipynb`: gera estatisticas por selecao.
- `07_player_stats.ipynb`: gera estatisticas individuais.
- `08_insights.ipynb`: gera leitura analitica.
- `09_build_report.ipynb`: monta relatorio final por jogo.
- `10_tournament_reports.ipynb`: gera relatorios agregados do torneio.
- `11_scores.ipynb`: inspeciona scores acumulados por selecao e jogador.

## Status de qualidade

- `ok`: dados consistentes.
- `aviso`: divergencia ou incompletude nao bloqueante.
- `erro`: divergencia grave ou dado invalido.
- `ausente`: fonte ou campo esperado ausente.
- `desconhecido`: status ainda nao determinado.

## Fluxo recomendado

1. Atualizar indice de partidas.
2. Ingerir dados brutos.
3. Normalizar dados das camadas silver/gold.
4. Validar placar, status, estadio e classificacao.
5. Gerar fragmentos Markdown.
6. Montar relatorio final.
7. Atualizar manifesto do jogo e status global do torneio.
8. Gerar scores acumulados por selecao e jogador.

## Fontes de dados

| Fonte | Status | O que coleta |
|---|---|---|
| `worldcup2026` | Operacional | 104 jogos, selecoes, estadios, classificacao, gols basicos |
| `espn` | Operacional | Calendario, stats por selecao, escalacoes, stats por jogador |
| `wikipedia` | Operacional | Partidas e classificacao de grupos (nao oficial) |
| `api_football` | Candidata | Jogadores, perfis, injuries, rankings e stats individuais por partida no plano gratuito limitado |
| `fifa` | Validacao oficial | PDF oficial de elencos com posicao, DOB, clube, altura, caps e gols |
| `canonical` | Derivado | Indice reconciliado das fontes acima |

A pipeline calcula classificacao internamente e valida contra as fontes. Resultados gravados em `data/silver/validation_results/`.

## Troubleshooting

**ESPN retornou erro ou ficou fora:**
```bash
python -m fifa_analytics atualizar --sem-espn
```

**Reprocessar um jogo especifico apos nova coleta:**
```bash
# Apague os fragmentos e o relatorio do jogo e rode novamente
rm -rf reports/fragments/copa_2026_jogo_013
rm -f reports/final/copa_2026_jogo_013.md
python -m fifa_analytics relatorios-basicos
```

**Limpar cache e reprocessar tudo do zero:**
```bash
python -m fifa_analytics atualizar
```

**Fontes divergem no placar:**
Confira `data/silver/validation_results/` — cada arquivo contem o resultado da comparacao entre fontes. O indice canonico usa prioridade `worldcup2026 > espn > wikipedia`; o campo `primary_source` no manifesto indica qual fonte foi usada.
