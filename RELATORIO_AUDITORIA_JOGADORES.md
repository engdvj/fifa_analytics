# Relatorio de Auditoria - Jogadores

Gerado em: 2026-06-18

## Escopo

Auditoria read-only da parte de jogadores do projeto `fifa_analytics`, cobrindo:

- Dados: `data/silver/player_stats`, `data/silver/player_match_stats`, `data/gold/fact_player_match_stats`, `data/gold/lineups`, `data/gold/rosters`, `data/gold/analytics/player_match_features.parquet`.
- Regras: `analytics/scores.py`, `workflows/scores_pipeline.py`, `workflows/scores365_pipeline.py`, `workflows/canonical_reports.py`.
- Saidas: `reports/players/**`, `reports/teams/*.md`, fragmentos/finais com links de jogadores.

Usei a venv do projeto com pandas/pyarrow e subagentes para auditar regras, dados e relatorios gerados em paralelo. Nao corrigi regras nesta etapa.

## Resumo Executivo

A suspeita de bug procede. Os problemas mais importantes nao parecem ser um unico erro, mas tres familias:

1. **Rating 365Scores esta inseguro e parcialmente desatualizado nos artefatos.**
   O canonico tem `836` ratings, mas o `player_match_features.parquet` persistido atual nao tem coluna `rating`. Quando reconstruido em memoria, a coluna aparece. Alem disso, o matching atual por tokens anexa notas erradas em muitos casos.

2. **Gols contra quebram links e somatorios por jogador.**
   Em eventos de `gol_contra`, o campo `team` representa o beneficiario, mas o `player` pertence ao adversario. O link usa sempre `team`, gerando caminhos impossiveis como `reports/players/catar/miro_muheim`.

3. **Identidade de jogador/slug ainda e fragil.**
   Ha colisao real entre `Ederson` e `Éderson` no Brasil, nomes com `" null"` literal, espacos finais e transliteracao ruim de letras como `ø`.

## Numeros Consolidados

| item | valor |
|---|---:|
| `canonical_player_stats` | 1241 linhas |
| `canonical_lineups` | 1241 linhas |
| `espn_rosters` | 1246 linhas |
| `player_match_features.parquet` persistido | 1255 linhas |
| `player_match_features` reconstruido em memoria | 1254 linhas |
| ratings no canonico | 836 |
| ratings faltando em jogadores que entraram | 24 |
| ratings faltando em reservas DNP | 381 |
| ratings 365 duplicados por match/team/player | 1 grupo |
| ratings anexados por matching fraco de 1 token | 154 |
| links de jogador realmente quebrados | 6 |
| eventos de gol cujo jogador nao existe no mesmo time do evento | 6 |
| match/team com menos de 26 jogadores | 6 |
| nomes de roster terminando em `null` literal | 3 |
| paginas de jogador sem jogo e com linha vazia | 14 |

## Achados Criticos

### 1. Matching de rating 365Scores permite notas erradas

**Severidade:** alta  
**Tipo:** regra de reconciliacao

O rating 365 e anexado ao `canonical_player_stats` por sobreposicao de tokens de nome em `src/fifa_analytics/workflows/canonical_reports.py:69`. A funcao escolhe o maior score, mas:

- nao consome o rating depois de usado;
- nao exige score minimo;
- nao rejeita match ambiguo;
- nao usa `player_id_365`;
- permite subset muito amplo.

Trecho critico: `src/fifa_analytics/workflows/canonical_reports.py:69` a `src/fifa_analytics/workflows/canonical_reports.py:94`.

Exemplos encontrados:

| canonico | recebeu rating de | problema |
|---|---|---|
| `César Huerta` | `Cesar Montes` | apenas token `cesar` |
| `Luis Romo` | `Luis Chavez` | apenas token `luis` |
| `Mateo Chávez` | `Luis Chavez` | apenas token `chavez` |
| `Sphephelo Sithole` | `Yaya Sithole` | apenas sobrenome |
| `Gabriel Martinelli` | `Gabriel Magalhaes` ou `Marquinhos Gabriel` | token comum generico |
| varios jogadores coreanos | varios `Kim`/`Lee` | sobrenomes comuns |

Quantificacao: `154` linhas com rating anexado por score fraco `<= 1`.

**Impacto:** rankings e scores de jogadores podem ser distorcidos por notas de outro jogador. Como `PLAYER_RATING_WEIGHT = 0.50`, isso pode dominar o score.

**Recomendacao:** trocar por estrategia em camadas:

1. match exato por slug normalizado;
2. aliases curados;
3. match fuzzy apenas com limiar alto e sem ambiguidade;
4. usar posicao/status/minutos para desempate;
5. consumir rating um-para-um;
6. gravar relatorio de nao-casados e ambiguos.

### 2. Mapeamento 365Scores para jogo canonico nao usa chave de fonte

**Severidade:** alta/media  
**Tipo:** regra de reconciliacao

`src/fifa_analytics/workflows/scores365_pipeline.py:196` mapeia ratings por `team/opponent`, sem `source_game_id`, sem data e sem dedupe de jogador.

Trecho critico: `src/fifa_analytics/workflows/scores365_pipeline.py:189` a `src/fifa_analytics/workflows/scores365_pipeline.py:201`.

Evidencias:

- `source_match_map` nao tem fonte `365scores`.
- Por inferencia data+times, `22/24` jogos mapeiam.
- `2/24` tem data divergente entre 365 e canonico:
  - `4627910 Austria x Jordania`: 365 = `2026-06-17`, canonico = `copa_2026_jogo_020` em `2026-06-16`.
  - `4697702 Australia x Turquia`: 365 = `2026-06-14`, canonico = `copa_2026_jogo_006` em `2026-06-13`.
- Duplicata atual: `copa_2026_jogo_007 / Brasil / Danilo / 6.8`.

**Impacto:** se o mesmo confronto se repetir no mata-mata, ratings podem ser anexados ao jogo errado. Mesmo agora, a duplicata alimenta colisoes no matching por nome.

**Recomendacao:** incluir `365scores` no mapa canonico ou persistir uma tabela propria `source_game_id -> canonical_match_id`; deduplicar por `source_game_id/team/player_id_365`.

### 3. Artefato `player_match_features.parquet` esta sem rating

**Severidade:** alta  
**Tipo:** artefato gerado/desatualizado

O arquivo persistido em `data/gold/analytics/player_match_features.parquet` nao tem coluna `rating`, apesar de `canonical_player_stats` ja ter `rating`.

Teste local:

- Persistido: `1255` linhas, `rating` ausente.
- Reconstruido por `build_player_match_features(canonical, lineups, rosters)`: `1254` linhas, `rating` presente, `836` valores nao nulos.
- `build_player_scores()` com o arquivo persistido gera `rating_medio` vazio.
- `build_player_scores()` com a feature reconstruida gera `729` jogadores com `rating_medio`.

O codigo ja espera `rating` em `src/fifa_analytics/analytics/scores.py:1038`.

**Impacto:** os relatorios/rankings atuais de jogadores podem estar ignorando uma coluna que o modelo diz ter peso de 50%.

**Recomendacao:** depois de corrigir o matching, rodar novamente `fifa-analytics scores` e validar que `player_match_features.parquet` contem `rating`.

### 4. Gol contra usa time beneficiario para linkar jogador

**Severidade:** alta  
**Tipo:** regra de link/semantica de evento

`_player_link()` cria path com `team` em `src/fifa_analytics/workflows/canonical_reports.py:1122`. Para `gol_contra`, porem, `team` e o beneficiario do gol, enquanto `player` pertence ao adversario.

Links quebrados reais:

| arquivo | alvo quebrado | causa |
|---|---|---|
| `reports/fragments/copa_2026_jogo_008/04_timeline.md` | `catar/miro_muheim` | Miro Muheim e da Suica |
| `reports/fragments/copa_2026_jogo_015/04_timeline.md` | `belgica/mohamed_hany` | Mohamed Hany e do Egito |
| `reports/fragments/copa_2026_jogo_004/04_timeline.md` | `estados_unidos/damian_bobadilla` | Damián Bobadilla e do Paraguai |

Tambem ha casos equivalentes em eventos ainda nao necessariamente linkados no arquivo final:

- `copa_2026_jogo_018`: Aymen Hussein.
- `copa_2026_jogo_020`: Yazan Al-Arab.

**Impacto:** timeline e narrativa apontam para paginas inexistentes e atribuem visualmente o jogador ao time errado.

**Recomendacao:** para `gol_contra`, resolver `player_team` por lineups/rosters do mesmo match; se nao encontrar, usar o adversario do beneficiario. Idealmente persistir `player_team` ou `own_goal_team`.

## Achados Importantes

### 5. Colisao de slug: `Ederson` vs `Éderson`

**Severidade:** alta/media  
**Tipo:** identidade/renderizacao

No Brasil, ha dois jogadores distintos:

- `Ederson `, goleiro.
- `Éderson`, meia.

Ambos viram slug `ederson`, entao as duas linhas em `reports/teams/brasil.md` apontam para `reports/players/brasil/ederson.md`. A pagina tambem carrega trailing space no titulo/metadados.

**Impacto:** uma pagina pode sobrescrever/representar o jogador errado; links de selecao ficam ambiguos.

**Recomendacao:** usar `player_id` no slug quando houver colisao, ou manter uma chave `player_slug` unica por time com sufixo estavel.

### 6. Nomes sujos no roster

**Severidade:** media  
**Tipo:** dado de fonte/normalizacao

O roster tem nomes com `null` literal:

- `Egito / Trézéguet null`
- `Egito / Zizo null`
- `Paraguai / Maurício null`

Tambem ha nomes com espaco final ou variacao de acento:

- `Brasil / Ederson `
- `Brasil / Raphinha `
- `Espanha / Rodri `
- `Portugal / Vitinha `
- `Uruguai / Agustín Cano` vs `Agustín Canobbio`
- `Marrocos / Amine Sbaï`

O helper `_player_name_key()` ja remove `" null"` ao casar nomes, mas o dado sujo ainda aparece em comparacoes e pode vazar para relatorios.

**Recomendacao:** aplicar normalizacao/alias logo na ingestao do roster e preservar nome de exibicao limpo.

**Status atualizado:** corrigido. `clean_person_name()`/`person_name_key()` agora limpam `null`, espacos invisiveis/NBSP, espacos nas pontas, hifens Unicode e variacoes `Al - Harbi`/`Al-Harbi`/`Al Harbi`. O gold canonico, features, snapshots e dashboard foram regenerados; checagem em `canonical_player_stats`, `canonical_lineups`, `player_match_features` e `player_snapshot_timeline` retornou `0` nomes sujos.

### 7. Totais de selecao nao batem com soma dos jogadores

**Severidade:** media  
**Tipo:** regra de apresentacao + fonte

Divergencias encontradas:

| metrica | quantidade |
|---|---:|
| gols | 5 |
| faltas | 2 |
| defesas | 1 |
| chutes no alvo | 1 |

Exemplos confirmados nos relatorios:

- `Austria`: resumo diz 3 gols; linhas de jogadores somam 2.
- `Belgica`: resumo diz 1 gol; jogadores somam 0.
- `Catar`: resumo diz 1 gol; jogadores somam 0.
- `Estados Unidos`: resumo diz 4 gols; jogadores somam 3.
- `Noruega`: resumo diz 4 gols; jogadores somam 3.

Parte dos gols e explicada por gols contra: o gol conta para a selecao beneficiada, mas o jogador aparece no adversario como `own_goals`.

**Recomendacao:** no bloco de jogadores da selecao, incluir uma linha/nota de `gols contra a favor` ou ajustar a comparacao para `goals + own_goals_for`. Para faltas/chutes/defesas, manter relatorio de divergencia entre fonte de time e fonte de jogador.

### 8. Cobertura incompleta de lineup/stats por jogo

**Severidade:** media  
**Tipo:** dado de fonte/cobertura

Seis pares match/team tem menos de 26 jogadores:

- `copa_2026_jogo_007 / Brasil = 25`
- `copa_2026_jogo_013 / Nova Zelandia = 25`
- `copa_2026_jogo_015 / Belgica = 25`
- `copa_2026_jogo_016 / Uruguai = 24`
- `copa_2026_jogo_022 / Inglaterra = 25`
- `copa_2026_jogo_024 / Gana = 25`

Exemplos de ausentes que viram linhas extras de roster sem partida: `Neymar`, `Ronald Araújo`, `Giorgian de Arrascaeta`, `Agustín Canobbio`.

**Recomendacao:** diferenciar claramente "elenco" de "relacionados no jogo". Se a ESPN nao traz banco completo, nao renderizar esses jogadores como uma linha de partida vazia.

### 9. Paginas de jogadores sem jogo tem linha vazia

**Severidade:** media  
**Tipo:** renderizacao

Ha `14` paginas com `jogos = 0` e uma tabela "Por jogo" com linha vazia. Exemplos:

- `reports/players/brasil/neymar.md`
- `reports/players/belgica/zeno_debast.md`
- `reports/players/marrocos/abde_ezzalzouli.md`
- `reports/players/uruguai/ronald_araujo.md`
- `reports/players/uruguai/agustin_canobbio.md`

O renderizador esta em `src/fifa_analytics/workflows/scores_pipeline.py:539`.

**Recomendacao:** se `appearances.sum() == 0` ou `match_id` nulo, mostrar "Ainda nao disputou jogos" e omitir tabela por jogo.

## Achados Menores / Riscos Futuros

### 10. `build_canonical_dataset` concatena fontes sem dedupe

**Severidade:** media/baixa  
**Tipo:** risco futuro

`src/fifa_analytics/workflows/canonical_reports.py:337` concatena datasets por prioridade, mas nao deduplica por entidade. Hoje, player stats/lineups efetivos vem da ESPN, entao nao explodiu. Se outra fonte passar a gerar player stats, jogadores podem duplicar e somar stats em dobro.

### 11. Relatorio de selecao agrega por `player_name`

**Severidade:** baixa  
**Tipo:** regra de agregacao

`_team_players_by_position()` agrupa por `player_name` em `src/fifa_analytics/workflows/scores_pipeline.py:930`. Homonimos no mesmo time seriam fundidos. O ideal e agrupar por `player_slug` ou `player_id`, mantendo `player_name` como label.

### 12. `DM` e `CDM` caem em perfis diferentes

**Severidade:** baixa  
**Tipo:** regra de classificacao

Em `src/fifa_analytics/analytics/scores.py:75`, `DM` vira `defensor`, mas `CDM` vira `meio`. Isso pode classificar volantes de forma diferente dependendo da abreviacao da fonte.

### 13. Slugs perdem letras nordicas

**Severidade:** baixa  
**Tipo:** slug/transliteracao

Exemplos:

- `Martin Ødegaard` -> `martin_degaard`
- `Ørjan Nyland` -> `rjan_nyland`
- `Alexander Sørloth` -> `alexander_srloth`
- `Jørgen Strand Larsen` -> `jrgen_strand_larsen`

**Recomendacao:** melhorar `slugify` para transliterar `ø/Ø -> o/O`, `å -> a`, etc.

## Checagens sem Problema

- Silver e gold sao logicamente identicos para:
  - `365scores.parquet`
  - `espn_player_stats.parquet`
  - `espn_lineups.parquet`
  - `espn_rosters.parquet`
- `canonical_player_stats`, `canonical_lineups` e `player_match_features` nao tem duplicatas por `match_id/team/player_name`.
- ESPN canonical/source esta totalmente mapeada:
  - `0` stats sem match canonico.
  - `0` lineups sem match canonico.
  - `0` times fora de home/away.
- Lineups vs stats tem cobertura cruzada:
  - `0` lineup sem stats.
  - `0` stats sem lineup.
- Roster por selecao tem tamanho plausivel:
  - nenhum time fora de 23-30 jogadores.
- Nao encontrei nos dados principais:
  - valores negativos;
  - ratings fora de 0-10;
  - minutos fora de 0-130;
  - `shots_on_target > shots`;
  - `goals > shots_on_target`.

## Ordem Recomendada de Correcao

1. Corrigir matching de rating 365 e dedupe de `365scores_rating`.
2. Regenerar `indice-canonico` e `scores`; validar que `player_match_features.parquet` tem `rating`.
3. Corrigir semantica de gol contra e links de jogador nos fragmentos/finais.
4. Resolver colisao de slug `Ederson/Éderson` e normalizar nomes com `null`/espaco final. **Concluido.**
5. Ajustar renderizacao de jogadores sem jogo.
6. Melhorar relatorio de selecao para explicar gols contra a favor e nao comparar soma de gols de jogadores sem essa ressalva.
7. Adicionar testes de regressao para os casos acima.

## Testes/Guardas Sugeridos

- Teste que um rating 365 nao pode ser anexado a dois jogadores canonicos no mesmo match/team.
- Teste que match por token unico comum (`Kim`, `Lee`, `Gabriel`, `Luis`, `Mohamed`) e rejeitado quando ambiguo.
- Teste de `gol_contra`: link deve apontar para o time do jogador que marcou contra, nao para o beneficiario.
- Teste de colisao de slug no mesmo time: dois jogadores distintos nao podem escrever o mesmo arquivo.
- Teste que jogador com `jogos = 0` nao renderiza linha vazia em "Por jogo".
- Teste que `player_match_features.parquet` preserva `rating` quando o canonico tem rating.
- Teste que hifen/espaco/espaco invisivel casam o mesmo jogador sem colidir `Ederson` e `Éderson`.
