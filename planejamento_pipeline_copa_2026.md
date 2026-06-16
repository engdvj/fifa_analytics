# Planejamento do Projeto - Analises da Copa do Mundo 2026

## 1. Objetivo do projeto

Criar uma pipeline em Python + Jupyter para acompanhar, analisar e documentar os 104 jogos da Copa do Mundo 2026.

O projeto deve usar **notebooks por processo**, e nao um notebook por jogo. Cada notebook executa uma etapa reutilizavel do fluxo, recebe parametros como `match_id`, `match_date` ou `run_scope`, gera dados estruturados e, quando fizer sentido, cria fragmentos Markdown que depois sao reunidos em relatorios finais.

Como a Copa esta acontecendo, o projeto deve nascer como uma pipeline viva:

- usar jogos reais ja realizados para testar e ajustar;
- suportar jogos agendados, ao vivo, finalizados e consolidados;
- permitir reprocessamento de um jogo, de uma data ou de todo o torneio;
- lidar com grande volume de informacao sem virar uma colecao manual de notebooks;
- manter rastreabilidade dos dados, fontes, execucoes e qualidade.

---

## 2. Principios do projeto

### 2.1 Processo antes de partida

Fluxo correto:

```text
Fonte de dados
-> dados brutos
-> dados limpos
-> dados analiticos
-> fragmentos .md
-> relatorio final por jogo
-> relatorios agregados do torneio
```

Fluxo a evitar:

```text
Notebook de jogo 1
Notebook de jogo 2
Notebook de jogo 3
...
```

Cada processo deve ser reaproveitavel para qualquer jogo usando parametros.

### 2.2 Jupyter como camada de execucao e inspecao

Os notebooks serao usados para:

- executar etapas da pipeline;
- inspecionar dados;
- validar resultados visualmente;
- documentar raciocinios;
- facilitar uso manual durante a Copa.

A logica principal deve ficar em codigo Python reutilizavel dentro de `src/`, para evitar notebooks enormes e dificeis de manter.

### 2.3 Markdown e relatorio nao sao base de dados

Os arquivos `.md` devem ser saidas de apresentacao. A base real do projeto deve estar em:

```text
data/raw
data/silver
data/gold
```

Evitar:

```text
Notebook -> Markdown -> Notebook -> Markdown
```

Preferir:

```text
Dados -> codigo Python -> notebook -> dados tratados + Markdown
```

Decisao atual:

- relatorio final deve ser gerado por `canonical_match_id`, nao por id de fonte;
- fontes especificas alimentam `data/raw` e `data/silver`;
- reconciliacao entre fontes alimenta `data/gold/dim_match/canonical_matches.parquet`;
- `reports/final` deve ter no maximo um arquivo por jogo real;
- metadados das fontes usadas entram no manifesto e na secao de qualidade do relatorio.
- quando a fonte primaria tiver numero de partida, `canonical_match_id` usa esse numero estavel;
- ordem temporal fica em coluna separada: `temporal_order`;
- numeracao da fonte primaria fica em coluna separada: `match_number`.

### 2.4 Escalabilidade para 104 jogos

O projeto precisa funcionar para:

- um unico jogo;
- jogos de uma data;
- jogos ja finalizados;
- jogos ao vivo;
- todos os 104 jogos.

Modos de execucao:

```text
jogo_unico
data_de_jogos
finalizados_pendentes
ao_vivo
torneio
```

---

## 3. Perguntas que o projeto deve responder

### 3.1 Por jogo

- Qual foi o resumo objetivo da partida?
- O resultado foi coerente com volume ofensivo e estatisticas?
- Quais foram os momentos decisivos?
- Como o jogo impactou a classificacao do grupo ou fase eliminatoria?
- Quais jogadores tiveram maior impacto?
- Houve diferencas relevantes entre fontes de dados?
- O relatorio esta completo, parcial ou pendente?

### 3.2 Por selecao

- Como a selecao evolui ao longo da Copa?
- Quais sao seus padroes ofensivos e defensivos?
- Ela depende mais de volume, eficiencia ou transicao?
- Quais jogadores acumulam maior participacao em gols, chutes, passes ou acoes defensivas?
- Qual e a situacao da selecao no grupo ou chaveamento?

### 3.3 Por grupo

- Qual e a classificacao atual?
- Quais selecoes dependem de combinacoes?
- Qual foi o impacto de cada rodada?
- Ha divergencia entre standings da API e standings calculado internamente?

### 3.4 Por torneio

- Quais jogos tiveram maior volume ofensivo?
- Quais selecoes sao mais eficientes?
- Quais jogadores lideram gols, assistencias, finalizacoes e participacoes decisivas?
- Quais partidas tiveram maior desequilibrio estatistico?
- Quais fontes estao mais completas e confiaveis?

---

## 4. Dados que vamos coletar

### 4.1 Dados obrigatorios

Esses dados sustentam o MVP e todos os relatorios.

```text
matches
teams
groups
stadiums
standings
match_status
scores
schedule
```

Campos importantes:

```text
match_id
source_match_id
fifa_match_id
home_team
away_team
home_team_code
away_team_code
date
kickoff_time
timezone
group
stage
round
stadium
city
country
status
home_score
away_score
winner
main_source
official_reference
last_updated_at
```

### 4.2 Dados de eventos do jogo

Esses dados alimentam timeline e leitura narrativa.

```text
goals
cards
substitutions
penalties
own_goals
var_events
injury_time
key_events
```

Campos importantes:

```text
match_id
event_id
event_type
minute
stoppage_minute
team
team_code
player
player_id
related_player
period
description
source
collected_at
```

### 4.3 Dados de escalacao

```text
starting_xi
bench
coach
formation
captain
player_positions
unavailable_players
```

Campos importantes:

```text
match_id
team
player_id
player_name
shirt_number
position
is_starter
is_substitute
formation_slot
minutes_played
source
collected_at
```

### 4.4 Estatisticas por selecao

```text
possession
shots
shots_on_target
shots_off_target
blocked_shots
xg
passes
pass_accuracy
corners
fouls
offsides
saves
tackles
duels
yellow_cards
red_cards
```

Nem toda fonte tera todos os campos. A pipeline deve aceitar dados parciais e marcar qualidade.

### 4.5 Estatisticas por jogador

```text
minutes_played
goals
assists
shots
shots_on_target
passes
key_passes
tackles
interceptions
saves
cards
fouls_committed
fouls_drawn
```

### 4.6 Dados de chutes, se disponiveis

```text
shot_id
minute
team
player
xg
body_part
situation
outcome
location_x
location_y
```

Shot map e xG devem ser tratados como enriquecimento, nao como requisito do MVP.

---

## 5. Analises que vamos fazer

### 5.1 Analises obrigatorias do MVP

- resumo da partida;
- placar e status;
- contexto do jogo;
- impacto na classificacao;
- standings calculado internamente;
- validacao entre fontes;
- relatorio final simples por `match_id`;
- resumo diario dos jogos finalizados.

### 5.2 Analises por jogo

- linha do tempo da partida;
- pontos de virada;
- eficiencia ofensiva;
- comparacao entre posse, finalizacoes e resultado;
- disciplina e impacto de cartoes;
- impacto de substituicoes;
- melhores jogadores;
- qualidade e completude dos dados.

### 5.3 Analises por selecao

- evolucao jogo a jogo;
- saldo de gols, pontos e aproveitamento;
- volume ofensivo medio;
- eficiencia: gols por finalizacao e gols por chute no alvo;
- solidez defensiva: chutes sofridos, gols sofridos e defesas;
- dependencia de jogadores especificos;
- comparacao entre desempenho e posicao no grupo.

### 5.4 Analises por grupo

- classificacao atual;
- standings calculado vs standings da API;
- cenario de classificacao;
- impacto de cada resultado;
- melhores terceiros, quando aplicavel;
- jogos decisivos restantes.

### 5.5 Analises do torneio

- ranking de selecoes por pontos, saldo, gols, finalizacoes e eficiencia;
- ranking de jogadores por gols, assistencias e participacoes;
- jogos com maior dominio estatistico;
- jogos com maior eficiencia ofensiva;
- alertas de dados ausentes ou divergentes;
- resumo por rodada ou por dia.

### 5.6 Scores acumulados

Objetivo:

- criar uma nota viva para selecoes e jogadores;
- atualizar as notas conforme novos jogos forem coletados;
- manter a fonte de verdade nas tabelas `data/gold/analytics/`;
- gerar arquivos Markdown por selecao e por jogador apenas como saida de leitura.

Arquitetura:

```text
data/gold/dim_match/canonical_matches.parquet
data/gold/fact_team_match_stats/canonical_team_stats.parquet
data/gold/fact_player_match_stats/canonical_player_stats.parquet
data/gold/lineups/canonical_lineups.parquet
-> data/gold/analytics/team_match_features.parquet
-> data/gold/analytics/team_scores.parquet
-> data/gold/analytics/player_match_features.parquet
-> data/gold/analytics/player_scores.parquet
-> reports/teams/{selecao}.md
-> reports/players/{jogador}_{selecao}.md
-> reports/rankings/index.md
-> reports/rankings/selecoes/index.md
-> reports/rankings/selecoes/{metrica}.md
-> reports/rankings/jogadores/index.md
-> reports/rankings/jogadores/{metrica}.md
```

Score de selecoes:

- `score_ataque`: gols, chutes e chutes no alvo por jogo;
- `score_defesa`: gols, chutes e chutes no alvo sofridos, alem de jogos sem sofrer gol;
- `score_controle`: posse, passes e precisao de passe;
- `score_eficiencia`: gols por chute e chutes no alvo por chute;
- `score_disciplina` exibido como `fair_play`: faltas, amarelos e vermelhos;
- `score_geral`: media ponderada dos componentes.
- `nivel_evidencia`: faixa textual (`baixa`, `media`, `alta`) indicando estabilidade da nota;
- `teste_defensivo`: quanto a defesa foi testada por volume de finalizacoes sofridas.

Para evitar falso positivo, cada componente deve ter:

```text
score_bruto
score_ajustado
confianca
```

O ranking usa a nota ajustada. O score bruto continua salvo para auditoria. Em poucos jogos, ou quando o adversario quase nao testa a defesa, notas muito altas sao puxadas para uma referencia mais conservadora. O `nivel_evidencia` nao diz se a nota esta certa ou errada; ele diz se a nota ja tem amostra suficiente para ser considerada estavel.

Interpretacao dos componentes:

- ataque mede volume/producao ofensiva;
- defesa mede protecao do proprio gol;
- controle mede dominio com bola;
- eficiencia mede aproveitamento ofensivo, nao volume;
- fair play mede risco disciplinar.

`eficiencia` e um componente ofensivo proprio. Ela compara o quanto a selecao transforma finalizacoes em finalizacoes no alvo e gols. Uma selecao pode atacar muito e ser pouco eficiente, ou atacar pouco e ser muito eficiente.

`peso_evidencia` aparece na auditoria para explicar quanto da nota bruta foi preservado. Com poucos jogos, dados incompletos ou defesa pouco testada, o peso de evidencia e menor e a nota usada fica mais conservadora.

Pesos iniciais:

```text
30% ataque
25% defesa
20% controle
15% eficiencia
10% fair_play
```

Score de jogadores:

- `impacto_partida`: gols, assistencias, chutes no alvo, chutes, defesas e acoes defensivas, com penalizacao por cartoes;
- `score_medio`: impacto por jogo normalizado;
- `score_acumulado`: impacto total normalizado;
- `score_ofensivo`: gols, assistencias e finalizacoes;
- `score_goleiro`: defesas;
- `score_disciplina`: cartoes por jogo, usado como penalizacao/controle disciplinar;
- `score_geral`: combinacao entre impacto medio e acumulado.

Observacao:

- os pesos sao versao inicial e devem ser ajustados depois que houver mais jogos;
- jogadores devem ter score geral e score por perfil, para nao comparar goleiro, defensor e atacante de forma cega;
- relatórios por entidade devem sempre informar a ultima atualizacao e os jogos considerados.
- os rankings e perfis Markdown devem usar links de Obsidian para selecoes, jogadores e jogos.
- em tabelas Markdown, wikilinks com alias devem escapar o pipe: `[[arquivo\|Alias]]`.

Atualizacao:

```text
coletar fontes
-> atualizar indice canonico
-> recalcular tabelas analytics do zero
-> regenerar rankings e perfis Markdown
```

O score nao deve ser atualizado manualmente em Markdown. A fonte da verdade permanece em `data/gold`. Os arquivos de Obsidian sao uma camada de navegacao.

Estatistica aplicada na versao inicial:

- acumulados;
- medias por jogo;
- razoes de eficiencia;
- normalizacao relativa ao torneio;
- ajuste conservador por nivel de evidencia.

Estatistica a aplicar nas proximas iteracoes:

- mediana por jogo;
- desvio padrao por metrica;
- media movel dos ultimos jogos;
- percentil e z-score por componente;
- ajuste por forca do adversario;
- score por perfil/posicao de jogador;
- tendencia de subida/queda no ranking.

---

## 6. Fontes de dados

### 6.1 FIFA oficial

Uso principal:

- validacao;
- calendario oficial;
- jogos;
- datas;
- horarios;
- estadios;
- placares finais;
- status oficial.

Papel no projeto:

```text
fonte de verdade minima
```

Ponto de atencao:

- pode nao ter API publica simples;
- pode exigir coleta semi-manual, scraping controlado ou validacao pontual.

### 6.2 FIFA Training Centre / Match Report Hub

Uso principal:

- relatorios oficiais pos-jogo;
- enriquecimento;
- validacao apos estabilizacao.

Papel no projeto:

```text
enriquecimento e validacao pos-jogo
```

### 6.3 worldcup2026 open-source API

Uso principal:

- API operacional gratuita para comecar;
- partidas;
- grupos;
- selecoes;
- estadios;
- placares;
- standings.

Papel no projeto:

```text
principal candidata para fonte operacional gratuita
```

Ponto de atencao:

- nao e oficial;
- precisa ser validada continuamente contra FIFA e outras fontes.
- pode oscilar em rede/TLS; a coleta deve ter retry e erro explicito.

Status no projeto:

```text
implementada como fonte operacional inicial
```

Comandos:

```bash
python -m fifa_analytics worldcup2026
python -m fifa_analytics relatorios-basicos --fonte worldcup2026
python -m fifa_analytics status-torneio --source worldcup2026
```

Saidas atuais esperadas:

```text
data/raw/worldcup2026/...
data/silver/matches/worldcup2026_matches.parquet
data/silver/events/worldcup2026_events.parquet
data/silver/teams/worldcup2026_teams.parquet
data/silver/stadiums/worldcup2026_stadiums.parquet
data/silver/standings/worldcup2026_standings.parquet
data/gold/standings/worldcup2026_calculated_group_standings.parquet
data/gold/fact_events/worldcup2026_events.parquet
```

### 6.4 Atualizacao sob demanda

Comando principal:

```bash
python -m fifa_analytics atualizar
```

Objetivo:

- coletar novamente `worldcup2026`;
- coletar novamente ESPN;
- recriar o indice canonico;
- gerar relatorios canonicos para jogos `finalizado`;
- atualizar status do torneio;
- recalcular scores e rankings.

Observacao:

- isso nao roda em background sozinho;
- para atualizar logo apos um jogo, rode o comando manualmente ou agende esse comando em cron/systemd;
- se uma fonte estiver instavel, use `--sem-espn` ou `--sem-worldcup2026`.

### 6.5 BALLDONTLIE FIFA API

Uso principal:

- dados mais ricos;
- eventos;
- estatisticas;
- lineups;
- jogadores;
- shot maps, se disponiveis.

Papel no projeto:

```text
enriquecimento analitico
```

Ponto de atencao:

- exige chave de API;
- pode ter limite de requisicoes;
- pode exigir planejamento de cache.

### 6.6 ESPN publica

Uso principal:

- enriquecimento gratuito sem chave;
- estatisticas por selecao;
- eventos com gols, cartoes e jogadores;
- escalacoes, formacoes e estatisticas individuais quando disponiveis;
- links de materia, videos e transmissao como metadados opcionais.

Papel no projeto:

```text
enriquecimento analitico gratuito
```

Status no projeto:

```text
implementada como fonte de enriquecimento
```

Comando:

```bash
python -m fifa_analytics espn
```

Saidas atuais esperadas:

```text
data/silver/team_stats/espn_team_stats.parquet
data/silver/lineups/espn_lineups.parquet
data/silver/player_stats/espn_player_stats.parquet
data/gold/fact_team_match_stats/espn_team_stats.parquet
data/gold/lineups/espn_lineups.parquet
data/gold/fact_player_match_stats/espn_player_stats.parquet
```

Ponto de atencao:

- nao e fonte oficial FIFA;
- dados podem mudar de estrutura;
- deve ser validada contra fonte oficial quando possivel.

### 6.7 football-data.org

Uso principal:

- fonte secundaria;
- partidas;
- resultados;
- classificacao;
- dados gerais de competicao.

Papel no projeto:

```text
backup e validacao cruzada
```

### 6.8 Estrategia recomendada

Comecar com:

```text
worldcup2026 API
+ ESPN publica
+ FIFA oficial para validacao
+ standings calculado internamente
```

Depois enriquecer com:

```text
BALLDONTLIE FIFA API
+ relatorios oficiais FIFA pos-jogo
```

---

## 7. Arquitetura de dados

### 7.1 Raw / Bronze

Dados exatamente como vieram das fontes.

Regras:

- nao limpar;
- nao corrigir;
- nao sobrescrever sem snapshot;
- salvar timestamp de coleta;
- preservar fonte e endpoint.

Estrutura sugerida:

```text
data/raw/{source}/competition=world_cup_2026/date=YYYY-MM-DD/collected_at=YYYYMMDDTHHMMSSZ/
```

Exemplos:

```text
data/raw/worldcup2026/competition=world_cup_2026/date=2026-06-16/collected_at=20260616T180000Z/matches.json
data/raw/balldontlie/competition=world_cup_2026/date=2026-06-16/collected_at=20260616T180000Z/events.json
data/raw/fifa/competition=world_cup_2026/date=2026-06-16/collected_at=20260616T230000Z/schedule.json
```

### 7.2 Silver

Dados limpos, normalizados e padronizados.

Responsabilidades:

- padronizar nomes de selecoes;
- padronizar ids;
- converter datas e fusos;
- normalizar status;
- remover duplicatas;
- harmonizar campos entre fontes.

Estrutura sugerida:

```text
data/silver/matches/
data/silver/teams/
data/silver/stadiums/
data/silver/standings/
data/silver/events/match_id={match_id}/
data/silver/lineups/match_id={match_id}/
```

### 7.3 Gold

Dados prontos para analise e relatorio.

Estrutura sugerida:

```text
data/gold/dim_match/canonical_matches.parquet
data/gold/dim_match/source_match_map.parquet
data/gold/dim_match/canonical_sources_metadata.json
data/gold/fact_matches/
data/gold/fact_events/canonical_events.parquet
data/gold/fact_team_match_stats/match_id={match_id}/
data/gold/fact_player_match_stats/match_id={match_id}/
data/gold/fact_events/match_id={match_id}/
data/gold/dim_team/
data/gold/dim_player/
data/gold/dim_stadium/
data/gold/dim_group/
data/gold/dim_match/
```

### 7.4 Formatos

Preferencias:

- JSON para snapshots crus;
- Parquet para Silver e Gold;
- YAML para configuracao e manifestos;
- Markdown para relatorios;
- CSV apenas para exportacao simples.

---

## 8. Estrutura de pastas

```text
fifa_analytics/
  README.md
  pyproject.toml
  requirements.txt
  .gitignore

  planejamento_pipeline_copa_2026.md

  notebooks/
    00_match_index.ipynb
    01_ingest_sources.ipynb
    02_validate_match_data.ipynb
    03_match_context.ipynb
    04_lineups.ipynb
    05_match_events.ipynb
    06_team_stats.ipynb
    07_player_stats.ipynb
    08_insights.ipynb
    09_build_report.ipynb
    10_tournament_reports.ipynb

  src/
    fifa_analytics/
      __init__.py
      config.py
      paths.py
      sources/
        __init__.py
        worldcup2026.py
        balldontlie.py
        fifa.py
        football_data.py
      transforms/
        __init__.py
        matches.py
        teams.py
        standings.py
        events.py
        lineups.py
        stats.py
      validation/
        __init__.py
        match_validation.py
        standings_validation.py
        schemas.py
      analytics/
        __init__.py
        match_summary.py
        efficiency.py
        standings.py
        player_leaders.py
      reporting/
        __init__.py
        fragments.py
        build_report.py
        tournament_reports.py
      utils/
        __init__.py
        io.py
        time.py
        logging.py

  config/
    sources.yaml
    pipeline.yaml
    teams_mapping.yaml
    report_sections.yaml

  schemas/
    matches.yaml
    teams.yaml
    events.yaml
    lineups.yaml
    team_stats.yaml
    player_stats.yaml

  templates/
    fragments/
      00_metadata.md.j2
      01_match_summary.md.j2
      02_context.md.j2
      03_lineups.md.j2
      04_timeline.md.j2
      05_team_stats.md.j2
      06_player_stats.md.j2
      07_key_insights.md.j2
      08_data_quality.md.j2
    tournament/
      daily_summary.md.j2
      standings.md.j2
      team_index.md.j2
      player_leaders.md.j2

  data/
    raw/
    silver/
    gold/

  reports/
    fragments/
      {match_id}/
    final/
      {match_id}.md
    tournament/
      daily_summary_YYYY-MM-DD.md
      standings.md
      team_index.md
      player_leaders.md

  manifests/
    {match_id}.yaml
    tournament_status.parquet

  tests/
    test_standings.py
    test_validation.py
    test_report_build.py
    fixtures/

  logs/
```

---

## 9. Status de jogos e relatorios

### 9.1 Status da partida

```text
agendado
pre_jogo
ao_vivo
intervalo
finalizado
consolidado
adiado
cancelado
desconhecido
```

### 9.2 Status do relatorio

```text
nao_iniciado
parcial
completo
precisa_revisao
final
```

### 9.3 Status de qualidade dos dados

```text
ok
aviso
erro
ausente
desconhecido
```

### 9.4 Manifesto por jogo

Exemplo:

```yaml
match_id: "mexico_africa_do_sul_2026_06_11"
home_team: "México"
away_team: "África do Sul"
status: "finalizado"
report_status: "completo"
last_updated_at: "2026-06-11T23:00:00Z"

sources_used:
  - worldcup2026
  - fifa

notebooks_executed:
  - 00_match_index
  - 01_ingest_sources
  - 02_validate_match_data
  - 03_match_context
  - 05_match_events
  - 06_team_stats
  - 08_insights
  - 09_build_report

missing_sections:
  - 06_player_stats

data_quality_status: "aviso"
final_report_path: "reports/final/mexico_africa_do_sul_2026_06_11.md"
```

### 9.5 Controle global do torneio

Arquivo:

```text
manifests/tournament_status.parquet
```

Campos:

```text
match_id
date
home_team
away_team
stage
group
status
last_raw_ingestion_at
last_validation_at
last_report_build_at
has_lineups
has_events
has_team_stats
has_player_stats
data_quality_status
report_status
final_report_path
```

Esse arquivo deve responder rapidamente:

- quais jogos ja foram processados;
- quais relatorios estao incompletos;
- quais jogos precisam de reprocessamento;
- quais fontes estao falhando;
- quais jogos tem divergencia de dados.

---

## 10. Notebooks e responsabilidades

Todos os notebooks devem ter uma celula inicial de parametros.

Parametros comuns:

```python
match_id = None
match_date = None
run_scope = "jogo_unico"
source = "worldcup2026"
force_refresh = False
write_outputs = True
```

### 10.1 `00_match_index.ipynb`

Funcao:

- criar e atualizar o indice central de partidas.

Escopo:

```text
torneio
data_de_jogos
```

Responsabilidades:

- listar jogos;
- criar `canonical_match_id`;
- reconciliar ids entre Wikipedia, worldcup2026, FIFA e futuras APIs;
- mapear ids entre fontes;
- identificar grupo, fase, data, horario e estadio;
- atualizar `data/silver/matches/`;
- atualizar `data/gold/dim_match/`;
- atualizar `manifests/tournament_status.parquet`.

Saidas:

```text
data/silver/matches/
data/gold/dim_match/
manifests/tournament_status.parquet
```

### 10.2 `01_ingest_sources.ipynb`

Funcao:

- coletar dados das fontes.

Escopo:

```text
jogo_unico
data_de_jogos
ao_vivo
torneio
```

Responsabilidades:

- buscar dados nas APIs;
- salvar snapshots crus;
- preservar timestamp;
- respeitar cache e rate limit;
- registrar erros de fonte.

Saidas:

```text
data/raw/{source}/...
logs/ingestion.log
```

### 10.3 `02_validate_match_data.ipynb`

Funcao:

- validar dados entre fontes e contra regras internas.

Escopo:

```text
jogo_unico
data_de_jogos
finalizados_pendentes
torneio
```

Responsabilidades:

- comparar placar;
- comparar status;
- comparar horario;
- comparar estadio;
- comparar selecoes;
- validar schema;
- gerar alertas.

Saidas:

```text
data/silver/validation_results/
reports/fragments/{match_id}/08_data_quality.md
```

### 10.4 `03_match_context.ipynb`

Funcao:

- gerar contexto da partida.

Escopo:

```text
jogo_unico
data_de_jogos
```

Responsabilidades:

- identificar grupo ou fase;
- situacao das selecoes;
- impacto potencial na classificacao;
- contexto pre-jogo ou pos-jogo.

Saidas:

```text
reports/fragments/{match_id}/02_context.md
```

### 10.5 `04_lineups.ipynb`

Funcao:

- processar escalacoes.

Escopo:

```text
jogo_unico
data_de_jogos
ao_vivo
```

Responsabilidades:

- coletar titulares;
- coletar reservas;
- identificar tecnicos;
- mapear formacoes;
- registrar ausencias, quando disponiveis.

Saidas:

```text
data/gold/lineups/match_id={match_id}/
reports/fragments/{match_id}/03_lineups.md
```

### 10.6 `05_match_events.ipynb`

Funcao:

- montar a timeline da partida.

Escopo:

```text
jogo_unico
data_de_jogos
ao_vivo
```

Responsabilidades:

- gols;
- cartoes;
- substituicoes;
- penaltis;
- VAR, se disponivel;
- eventos relevantes;
- minutos de cada evento.

Saidas:

```text
data/gold/fact_events/match_id={match_id}/
reports/fragments/{match_id}/04_timeline.md
```

### 10.7 `06_team_stats.ipynb`

Funcao:

- gerar estatisticas por selecao.

Escopo:

```text
jogo_unico
data_de_jogos
finalizados_pendentes
torneio
```

Responsabilidades:

- posse de bola;
- finalizacoes;
- finalizacoes no alvo;
- faltas;
- escanteios;
- passes;
- eficiencia ofensiva;
- comparacao entre times.

Saidas:

```text
data/gold/fact_team_match_stats/match_id={match_id}/
reports/fragments/{match_id}/05_team_stats.md
```

### 10.8 `07_player_stats.ipynb`

Funcao:

- gerar estatisticas individuais.

Escopo:

```text
jogo_unico
data_de_jogos
finalizados_pendentes
torneio
```

Responsabilidades:

- gols;
- assistencias;
- finalizacoes;
- passes;
- desarmes;
- cartoes;
- minutos jogados;
- destaques individuais.

Saidas:

```text
data/gold/fact_player_match_stats/match_id={match_id}/
reports/fragments/{match_id}/06_player_stats.md
```

### 10.9 `08_insights.ipynb`

Funcao:

- gerar leitura analitica do jogo.

Escopo:

```text
jogo_unico
data_de_jogos
finalizados_pendentes
```

Responsabilidades:

- principais padroes;
- pontos de virada;
- jogadores decisivos;
- desequilibrios estatisticos;
- leitura tatica simples;
- conclusoes relevantes.

Saidas:

```text
reports/fragments/{match_id}/07_key_insights.md
```

### 10.10 `09_build_report.ipynb`

Funcao:

- montar o relatorio final por jogo.

Escopo:

```text
jogo_unico
data_de_jogos
finalizados_pendentes
torneio
```

Regras:

- nao fazer analise nova;
- apenas localizar fragmentos;
- ordenar secoes;
- montar o `.md` final;
- registrar secoes faltantes;
- atualizar manifesto.

Saidas:

```text
reports/final/{match_id}.md
manifests/{match_id}.yaml
```

### 10.11 `10_tournament_reports.ipynb`

Funcao:

- gerar relatorios agregados do torneio.

Escopo:

```text
data_de_jogos
torneio
```

Responsabilidades:

- resumo diario;
- standings por grupo;
- ranking de selecoes;
- ranking de jogadores;
- alertas de qualidade;
- acompanhamento de relatorios faltantes.

Saidas:

```text
reports/tournament/daily_summary_YYYY-MM-DD.md
reports/tournament/standings.md
reports/tournament/team_index.md
reports/tournament/player_leaders.md
```

### 10.12 `11_scores.ipynb`

Funcao:

- inspecionar e gerar scores acumulados por selecao e jogador.

Escopo:

```text
finalizados_pendentes
torneio
```

Responsabilidades:

- gerar features por selecao por jogo;
- gerar features por jogador por jogo;
- calcular scores acumulados;
- criar ranking geral e por componente;
- gerar arquivos Markdown por selecao e jogador;
- validar se os scores fazem sentido visualmente.

Comando:

```bash
python -m fifa_analytics scores
```

Saidas:

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

Metricas com ranking proprio:

- selecoes: `geral`, `ataque`, `defesa`, `controle`, `eficiencia` e `fair_play`;
- jogadores: `geral`, `medio`, `acumulado`, `ofensivo` e `goleiro`.

---

## 11. Fragmentos Markdown por jogo

Ordem fixa:

```text
reports/fragments/{match_id}/
  00_metadata.md
  01_match_summary.md
  02_context.md
  03_lineups.md
  04_timeline.md
  05_team_stats.md
  06_player_stats.md
  07_key_insights.md
  08_data_quality.md
```

Estrutura do relatorio final:

```text
# {home_team} x {away_team}

## Resumo da partida

## Contexto

## Estatisticas das selecoes

- comparativo de nota da partida por selecao;
- frente a frente por componente: ataque, defesa, controle, eficiencia, fair play, pontos e volume.

## Leitura rapida

## Escalacoes e notas dos jogadores

- titulares sempre;
- reservas apenas quando houver acao/impacto registrado;
- nota do jogador na partida, impacto simples e principais estatisticas.

## Destaques individuais

## Linha do tempo

## Qualidade dos dados
```

Se uma secao nao estiver disponivel, o relatorio deve registrar isso de forma clara:

```text
Secao pendente: estatisticas individuais ainda nao disponiveis na fonte usada.
```

---

## 12. README do projeto

O `README.md` deve ter:

```text
1. O que e o projeto
2. Objetivo
3. Arquitetura
4. Fontes de dados
5. Como instalar
6. Como configurar chaves de API
7. Como abrir os notebooks
8. Como rodar um jogo especifico
9. Como rodar jogos de uma data
10. Como gerar relatorios finais
11. Como interpretar data_quality_status
12. Estrutura de pastas
13. Fluxo recomendado de trabalho
14. Limitacoes conhecidas
```

Comandos esperados:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab
```

Execucao futura com Papermill:

```bash
papermill notebooks/09_build_report.ipynb outputs/09_build_report_mexico_africa_do_sul.ipynb -p match_id mexico_africa_do_sul_2026_06_11
```

---

## 13. Checklists

### 13.1 Checklist de criacao do projeto

- [ ] Criar estrutura de pastas.
- [ ] Criar `README.md`.
- [ ] Criar `requirements.txt` ou `pyproject.toml`.
- [ ] Criar `.gitignore`.
- [ ] Criar pacote `src/fifa_analytics`.
- [ ] Criar configs iniciais.
- [ ] Criar schemas iniciais.
- [ ] Criar templates Markdown.
- [ ] Criar notebooks vazios com celula de parametros.

### 13.2 Checklist do MVP

- [ ] Coletar indice de partidas.
- [ ] Salvar raw snapshot.
- [ ] Normalizar tabela de partidas.
- [ ] Calcular standings internamente.
- [ ] Validar placar/status contra outra fonte.
- [ ] Gerar fragmentos basicos.
- [ ] Montar relatorio final por jogo.
- [ ] Gerar manifesto por jogo.
- [ ] Atualizar status global do torneio.

### 13.3 Checklist por jogo

- [ ] Existe `match_id`.
- [ ] Existe snapshot raw.
- [ ] Partida existe em `data/silver/matches`.
- [ ] Status esta normalizado.
- [ ] Placar esta validado.
- [ ] Standing foi recalculado.
- [ ] Fragmentos foram gerados.
- [ ] Relatorio final foi criado.
- [ ] Manifesto foi atualizado.
- [ ] Qualidade dos dados foi registrada.

### 13.4 Checklist diario

- [ ] Atualizar indice de partidas.
- [ ] Ingerir jogos do dia.
- [ ] Reprocessar jogos finalizados.
- [ ] Validar divergencias.
- [ ] Gerar relatorios dos jogos finalizados.
- [ ] Gerar resumo diario.
- [ ] Atualizar standings do torneio.
- [ ] Revisar alertas de qualidade.

---

## 14. Testes

### 14.1 Testes obrigatorios no inicio

```text
tests/test_standings.py
tests/test_validation.py
tests/test_report_build.py
```

### 14.2 O que testar

Standings:

- vitoria soma 3 pontos;
- empate soma 1 ponto;
- saldo de gols correto;
- ordenacao correta;
- dados incompletos nao quebram o calculo.

Validacao:

- placares iguais geram `ok`;
- placares divergentes geram `aviso` ou `erro`;
- fonte ausente gera `ausente`;
- status desconhecido vira `desconhecido`.

Relatorio:

- fragmentos sao ordenados corretamente;
- secao ausente entra em `missing_sections`;
- manifesto e atualizado;
- relatorio final nao faz analise nova.

Schemas:

- colunas obrigatorias existem;
- tipos principais estao corretos;
- `match_id` nao e nulo;
- datas sao parseaveis.

### 14.3 Testes com jogos reais

Escolher 2 ou 3 jogos ja finalizados para validar:

- um jogo com dados completos;
- um jogo com dados parciais;
- um jogo com divergencia ou fonte ausente, se existir.

Esses jogos viram fixtures de teste depois que os snapshots forem salvos.

---

## 15. Usos esperados

### 15.1 Rodar um jogo especifico

Uso:

```text
run_scope = "jogo_unico"
match_id = "mexico_africa_do_sul_2026_06_11"
```

Objetivo:

- reprocessar dados;
- atualizar relatorio;
- corrigir divergencia.

### 15.2 Rodar jogos de uma data

Uso:

```text
run_scope = "data_de_jogos"
match_date = "2026-06-16"
```

Objetivo:

- ingerir jogos do dia;
- atualizar status;
- gerar resumo diario.

### 15.3 Rodar jogos finalizados pendentes

Uso:

```text
run_scope = "finalizados_pendentes"
```

Objetivo:

- encontrar jogos finalizados sem relatorio completo;
- gerar ou corrigir relatorios;
- atualizar manifestos.

### 15.4 Rodar torneio inteiro

Uso:

```text
run_scope = "tournament"
```

Objetivo:

- reprocessar tudo;
- recalcular rankings;
- gerar relatorios agregados;
- revisar qualidade global.

### 15.5 Durante jogo ao vivo

Uso:

```text
run_scope = "live"
match_id = "..."
```

Objetivo:

- atualizar placar;
- atualizar eventos;
- manter timeline parcial;
- evitar consolidar relatorio como final antes da estabilizacao.

---

## 16. Estrategia de atualizacao

### 16.1 Antes do jogo

Frequencia:

```text
a cada 15 ou 30 minutos
```

Objetivo:

- confirmar horario;
- confirmar estadio;
- capturar escalacoes quando sairem;
- preparar contexto.

### 16.2 Durante o jogo

Frequencia:

```text
a cada 30 ou 60 segundos, se a fonte e o limite permitirem
```

Objetivo:

- placar;
- eventos;
- timeline;
- estatisticas parciais.

### 16.3 Logo apos o jogo

Frequencia:

```text
por 1 ou 2 horas apos o fim
```

Objetivo:

- capturar correcoes;
- confirmar placar final;
- atualizar estatisticas finais;
- fechar relatorio.

### 16.4 Depois da estabilizacao

Objetivo:

- congelar snapshot final;
- marcar `finalized`;
- preservar reprodutibilidade;
- evitar mudancas inesperadas.

---

## 17. Ordem de implementacao

### Fase 1 - Base operacional

Arquivos principais:

```text
README.md
requirements.txt
.gitignore
src/fifa_analytics/
config/
schemas/
templates/
notebooks/00_match_index.ipynb
notebooks/01_ingest_sources.ipynb
notebooks/02_validate_match_data.ipynb
notebooks/09_build_report.ipynb
```

Objetivo:

- criar estrutura;
- coletar jogos reais;
- salvar raw;
- normalizar partidas;
- validar dados basicos;
- gerar primeiro relatorio simples.

### Fase 2 - Relatorio util por jogo

Arquivos principais:

```text
notebooks/03_match_context.ipynb
notebooks/05_match_events.ipynb
notebooks/06_team_stats.ipynb
notebooks/08_insights.ipynb
```

Objetivo:

- gerar relatorios mais completos;
- incluir contexto, timeline e estatisticas;
- produzir insights basicos.

### Fase 3 - Dados ricos

Arquivos principais:

```text
notebooks/04_lineups.ipynb
notebooks/07_player_stats.ipynb
```

Objetivo:

- incluir escalacoes;
- incluir jogadores;
- criar rankings individuais;
- enriquecer relatorios.

### Fase 4 - Operacao do torneio

Arquivos principais:

```text
notebooks/10_tournament_reports.ipynb
manifests/tournament_status.parquet
reports/tournament/
```

Objetivo:

- gerar resumo diario;
- acompanhar todos os 104 jogos;
- criar rankings do torneio;
- identificar pendencias;
- automatizar reprocessamentos.

### Fase 5 - Scores vivos

Arquivos principais:

```text
notebooks/11_scores.ipynb
data/gold/analytics/
reports/teams/
reports/players/
```

Objetivo:

- manter score vivo de selecoes e jogadores;
- recalcular rankings depois de cada rodada;
- gerar um arquivo acumulado por selecao e por jogador;
- usar os scores como insumo para insights dos relatorios por jogo.

### Fase 5 - Automacao

Objetivo:

- rodar notebooks por parametro;
- usar Papermill ou equivalente;
- criar execucao por data;
- criar execucao de jogos pendentes;
- registrar logs;
- preparar agendamento.

---

## 18. Checklist de melhorias

Levantado em 2026-06-16 após revisão completa do repositório. Organizado por prioridade.

### Critico (bloqueia qualidade ou corretude)

- [ ] **`.gitignore` incompleto** — `reports/players/`, `reports/teams/*.md`, `reports/rankings/` não estão ignorados; centenas de arquivos gerados sendo commitados sem intenção
- [ ] **`manifests/tournament_status.parquet` no lugar errado** — arquivo gerado automaticamente deveria ficar em `data/gold/`, não em `manifests/`; atualizar `.gitignore` e `tournament_status.py`

### Arquitetura (confusao de responsabilidades)

- [ ] **`analytics/standings.py` é re-export inútil** — apenas reexporta `calculate_group_standings` de `transforms/standings.py`; remover o arquivo e ajustar imports nos workflows que o usam
- [ ] **`slugify()` duplicada** — definida em `analytics/scores.py` e reimportada em `canonical_reports.py`; mover para `utils/` e atualizar todos os imports
- [ ] **URLs hardcoded nos módulos de fontes** — `worldcup2026.py` e `espn.py` têm `BASE_URL` hardcoded; deveriam ler de `config/sources.yaml` via `load_config()`
- [x] **`config/pipeline.yaml` não é carregado** — arquivo bem estruturado mas ignorado pelo código; usar em `cli.py` para defaults globais (status válidos, run_scope, timezone)
- [x] **`efficiency.py` trivial** — `goals_per_shot()` é uma linha de fórmula; mover para `utils/` ou absorver em `analytics/scores.py` e remover o arquivo

### Validação e schemas (falta de contrato real)

- [x] **`schemas/*.yaml` são decorativos** — `load_schema()` existe em `config.py` mas nunca é chamado; implementar validação real via `validation/schemas.py` usando os schemas YAML para verificar colunas obrigatórias nos DataFrames antes de salvar em silver/gold
- [x] **`validate_required_columns()` em `validation/schemas.py` está vazia** — implementar com base nos schemas YAML

### Sources stubs (confusão de leitura)

- [ ] **Remover ou isolar stubs não implementados** — `sources/fifa.py`, `sources/football_data.py`, `sources/balldontlie.py` lançam `NotImplementedError`; criar pasta `sources/stubs/` ou adicionar comentário `# not implemented` claro no topo e excluir da discovery automática

### Testes (gaps de cobertura)

- [ ] **Sem testes de CLI** — `cli.py` com 8 comandos não tem nenhum teste; cobrir ao menos argumentos inválidos e saída de ajuda
- [ ] **Sem testes de I/O real** — `utils/io.py` (write/read parquet, JSON, YAML) não tem testes; adicionar com `tmp_path` do pytest
- [ ] **Sem testes de integração** — nenhum teste executa um fluxo completo (ingest → canonical → report); adicionar ao menos um teste E2E com dados de sample
- [ ] **Sem testes de edge cases em Wikipedia** — HTML quebrado, tabelas com formato inesperado, times com caracteres especiais

### Dependências e packaging

- [ ] **`pytest` em `requirements.txt` junto com runtime** — separar em `requirements-dev.txt` ou `[project.optional-dependencies]` no `pyproject.toml`
- [ ] **`papermill` declarado mas pouco usado** — verificar se notebooks estão sendo executados programaticamente; se não, mover para `requirements-dev.txt`

### README e documentação

- [ ] **Exemplos de output do `amostra` usam nome temporal** — README mostra `mexico_africa_do_sul_2026_06_11` mas o match_id real é `copa_2026_jogo_001`; corrigir exemplos
- [ ] **Seção "Limitações iniciais" vaga** — especificar quais fontes estão 100% operacionais (worldcup2026 ✅, espn ✅, wikipedia ✅ básico) e quais são stubs (fifa ❌, football_data ❌, balldontlie ❌)
- [ ] **Falta seção de Troubleshooting** — o que fazer se ESPN cair, como reprocessar um jogo, como limpar cache parcial

### Melhorias de qualidade (quando der)

- [ ] **TLS bypass global em `worldcup2026.py`** — `urllib3.disable_warnings()` afeta toda a sessão; usar `verify=False` inline em `requests.get()` sem desabilitar warnings globalmente
- [ ] **Type hints imprecisos em workflows** — varios retornam `dict[str, object]`; tipar com `dict[str, Path | str | int]` onde o retorno é conhecido

---

## 20. Resultado esperado

Para cada jogo:

```text
reports/final/{match_id}.md
manifests/{match_id}.yaml
```

Para o torneio:

```text
reports/tournament/daily_summary_YYYY-MM-DD.md
reports/tournament/standings.md
reports/tournament/team_index.md
reports/tournament/player_leaders.md
manifests/tournament_status.parquet
```

O projeto sera considerado bem estruturado quando permitir:

- processar qualquer um dos 104 jogos;
- reprocessar apenas jogos pendentes;
- validar dados entre fontes;
- gerar relatorios parciais sem quebrar;
- consolidar relatorios finais depois da estabilizacao;
- acompanhar a Copa inteira a partir de uma tabela de status global.
