# Revisão geral do cálculo de métricas — 2026-06-22

Auditoria completa do pipeline de scores (seleções + jogadores) e do dashboard.
Resposta direta à tua pergunta principal está em **§0**.

---

## 0. "Por que muda conforme muda o snapshot se os pesos são fixos?" → ✅ RESOLVIDO

**Decisão tomada: referência fixa.** O score de uma seleção agora só muda quando ELA
joga — não quando o campo muda. Implementado em `analytics/scores.py` +
`analytics/snapshot.py`:
- `_zscore_to_100` aceita uma referência `(média, desvio)` FIXA, calculada uma vez
  sobre TODOS os jogos finalizados e reusada em cada snapshot (parâmetro `ref_stats`).
- `elo_maturity` é congelado na referência (pesos efetivos constantes entre snapshots).
- Aproveitamento ponderado usa o Elo do adversário **pré-jogo** (estável) com âncora
  fixa de 1500, em vez do Elo pós-jogo que evoluía depois.

**Validação empírica:** África do Sul (1 jogo) agora mantém score_geral = 38.9 em
todos os snapshots 1–24 e só muda no snapshot 25 (quando joga o 2º jogo). Varredura
de todas as seleções: 80 blocos de "mesmo nº de jogos em vários snapshots", **0 com
score variando**. 78 testes verdes.

O texto abaixo (diagnóstico original) fica como registro do problema que foi corrigido.

---

## 0-bis. Diagnóstico original (antes da correção)

**Os pesos (`TEAM_SCORE_WEIGHTS`) são fixos, mas os scores que eles combinam NÃO são absolutos — são relativos ao campo de seleções daquele snapshot.** Prova empírica: a África do Sul jogou **1 único jogo** e não jogou mais nada entre os snapshots 1 e 24, mas seus scores mudam em todo snapshot:

| snapshot | jogos | score_ataque | score_geral | elo_maturity |
|---|---|---|---|---|
| 1 | 1 | 45.1 | 41.4 | 0.52 |
| 3 | 1 | 42.3 | 39.5 | 0.32 |
| 24 | 1 | 44.5 | 40.4 | 0.29 |

Mesmo dado de entrada, scores diferentes. Três causas, todas por design (não são bugs de código, são decisões que talvez você queira mudar):

1. **Normalização por z-score relativo (`_zscore_to_100`)** — `score_ataque/eficiencia/controle/forca_relativa/resultado` são `(valor − média_do_campo) / desvio_do_campo`. Quando OUTRAS seleções jogam, a média/desvio do torneio mudam, então o score de TODO mundo se mexe mesmo sem jogar. O score é uma **posição relativa**, não uma nota absoluta.

2. **Reponderação dinâmica por `elo_maturity`** — em `build_team_scores`, o peso de `score_forca_relativa` é multiplicado por `elo_maturity` e o que sobra vai para `score_resultado` (`eff_fr`/`eff_res`). `elo_maturity` muda a cada snapshot (cresce conforme os Elos se diferenciam). Ou seja: **os pesos efetivos mudam snapshot a snapshot**, apesar de "fixos". Pior: `_elo_maturity_factor` usa `int(round(jogos.mean()))`, o que provoca saltos bruscos (ex.: 0.46 → 0.17 entre dois snapshots).

3. **Encolhimento por confiança (`_apply_confidence`)** — scores são puxados para 50 conforme há poucos jogos. Conforme acumulam jogos, expandem. Também move o valor por snapshot.

**Decisão sua (precisa do teu input):** você quer que o score seja
- (A) **posição relativa** dentro do torneio naquele momento (comportamento atual — muda quando o campo muda), ou
- (B) **nota absoluta** estável (mesmo desempenho → mesma nota, independente do que os outros fizeram)?

Se (B): trocar `_zscore_to_100` por uma escala ancorada em referência fixa (faixas absolutas tipo o `_band` que já é usado na defesa, ou z-score contra uma distribuição de referência fixa) e congelar os pesos efetivos (remover ou suavizar o `elo_maturity`). É uma mudança de filosofia do score — por isso **não mexi sem te perguntar**.

---

## 1. Bugs corrigidos nesta revisão (já aplicados + testados)

### ✅ `score_disciplina` estava grudado em 100 para 94.6% das seleções
`analytics/scores.py` — a fórmula dividia por `0.30` sendo que os pesos já somavam 1.0, inflando ~3.3× e estourando o clip em 100. **Corrigido** (removida a divisão). Antes: 94.6% em 100. Depois: centrado em 50.2, faixa 20–67.

### ✅ Todos os goleiros ficavam com `score_geral = NaN`
`analytics/player_snapshot.py::_player_scores` — `float(creativity_score or 0)` não protege contra `NaN` (em Python `nan or 0 == nan`, porque NaN é "truthy"). Goleiros não têm creativity_score → todo GK virava NaN e sumia do ranking. **Corrigido** com guarda `pd.isna`. Antes: 0 GKs pontuados. Depois: 1465 linhas de GK com score.

### ✅ Média "por jogo" de jogador dividia por convocações, não por jogos jogados
`analytics/player_snapshot.py` — `jogos` vinha de `groupby.size()` (linhas de escalação), contando jogador que ficou no banco e não entrou. Isso diluía todas as médias `_por_jogo`. **Corrigido**: agora conta partidas com `minutos > 0`. (Ex.: jogador que fez 1 gol no único jogo que entrou mostrava 0.5 gols/jogo em vez de 1.0.)

### ✅ Dashboard: ordem/medalha/cor invertidas ao filtrar métricas "menor = melhor"
`scripts/bar_chart_race.py` — Race, grade de Seleções, grade de Jogadores e os badges dos cards ordenavam pelo valor bruto seguindo só o toggle manual, **ignorando `LOWER_IS_BETTER`**. Resultado: ao filtrar por Faltas / Amarelos / Gols Sofridos, o **pior** time aparecia em 1º com medalha de ouro. Só o gráfico de trajetória respeitava a polaridade. **Corrigido** com um helper único `effectiveSortDir(metric)` (fonte única de verdade) roteado por todos os pontos de ordenação. Agora rank #1 = melhor sempre. O toggle virou "Melhores primeiro / Piores primeiro". `node --check` e suíte (78 testes) passando.

---

## 2. Precisa de decisão sua (não mexi)

### ⚠️ `score_geral` do jogador é CONSTANTE em todos os snapshots (vazamento de futuro)
`player_snapshot.py:146` calcula o score uma vez do `fact_power_ranking` (que é um **único snapshot acumulado da temporada**) e carimba o MESMO valor em todos os snapshots 1..41. Então o snapshot 1 já mostra a nota de fim de torneio. E o `ranking_score_geral` "se mexe" só porque a população de jogadores cresce (não por desempenho) — exatamente o sintoma que você notou no lado dos jogadores.
**Limitação de dado:** o endpoint de power ranking traz `tournament_history` por rodada (já parseado em `transforms.py`), mas hoje só tem 1 rodada coletada. Dá para calcular o score "até a rodada N" quando houver mais rodadas. Quer que eu implemente o score por-rodada agora (fica certo automaticamente quando os dados crescerem)?

### ⚠️ Cobertura do power ranking: só 296 de 1242 jogadores têm score
80% das linhas da timeline de jogadores ficam com `score_geral` NaN. É limite do endpoint da FIFA, não bug. Decisão: aceitar, ou derivar um score próprio das métricas fdh do jogador (como fazemos no lado das seleções)?

### ⚠️ Rótulos de proxy enganosos no lado do jogador
`player_pivot.py`: `tackles_won` = `ForcedTurnovers`, `interceptions` = `DirectDefensivePressuresApplied`, `ball_recovery` = `DefensivePressuresApplied`, `key_passes` = `NumberOfShotEndingSequences`. Sem erro aritmético, mas `duels_won = tackles_won + dribbles_won` soma um proxy de turnover com dribles — conceitualmente frouxo. Renomear para o que realmente é?

### ⚠️ `LEFT JOIN` preenche stats ausentes com 0
`player_pivot.py:141-144` — jogador escalado sem linha de stats fica com 0 em tudo (indistinguível de um 0 real). Em parte já mitigado pela correção do denominador (§1). Distinguir "sem dado" (NaN) de "zero real" exige decidir caso a caso.

---

## 3. Itens menores observados (não críticos)
- `analytics/scores.py` emite `PerformanceWarning` (DataFrame fragmentado por `frame.insert` repetido). Cosmético; dá para limpar com `pd.concat` das colunas derivadas.
- `_simulate_max_elo_variance` usa `n_teams=32`; a Copa 2026 tem 48. Pequeno descasamento de calibração do `elo_maturity`.
- `_mean_score` retorna `pd.Series(50.0)` sem índice quando não há componente válido — risco de desalinhamento se todos os componentes forem NaN.

---

## Como reproduzir os números desta revisão
```
.venv\Scripts\activate
python -m pytest -q                      # 78 passando
python scripts/bar_chart_race.py         # regera o dashboard
```
Os parquets de snapshot já foram regerados com as correções (estão em `data/gold/analytics/`, fora do git).
