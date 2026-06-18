# Relatório de auditoria — Aquisição de dados e modelo de scores

> **Status:** documento de referência para a refatoração de raiz.
> **Data:** 2026-06-18.
> **Contexto:** levantamento do que cada fonte realmente oferece por jogador e dos
> furos do modelo de score, para alinhar com a auditoria paralela (Codex) e
> reescrever os pontos críticos do zero, de forma consistente.

---

## 1. Sumário executivo

O score de **defensor** e **goleiro** é pobre porque o pipeline **não coleta**
métricas defensivas (desarmes, interceptações, cortes, xGP) — não por falta de
dados, mas porque o parser do 365Scores ignora 16 das 37 stats disponíveis. **Os
dados já estão nos arquivos raw coletados.** A correção de raiz é estender o
parser + reescrever o score defensivo. Em paralelo, há inconsistências de nome
entre fontes (já com mitigação) e o modelo de score do jogador acabou de ser
ajustado (rating 50% + produção absoluta), mas defensor/goleiro continuam
limitados até a aquisição ser refeita.

---

## 2. Inventário de fontes (o que cada uma dá POR JOGADOR)

| Fonte | Stats/jogador | Defensivo | Avançado (xG/xA/xGP) | Mapa de chute | Papel |
|---|---|---|---|---|---|
| **365Scores** | **37** | ✅ desarmes, interceptações, cortes, recuperações, duelos | ✅ xG, xA, xGP, xGOT | heatMap/jogador | **Fonte rica de stats** |
| **ESPN** (`/summary`) | 14 | ❌ (só o líder de cada time em `leaders`) | ❌ | ✅ coords em `keyEvents` | Eventos, formação, commentary |
| **worldcup2026** | 0 | ❌ | ❌ | ❌ | Operacional: match_id, placar, status |
| **Wikipedia** | 0 | ❌ | ❌ | ❌ | Referência pública |

### 2.1 ESPN — detalhe
- **Per-jogador** vem de `summary.rosters[].roster[].stats` — só 14 campos:
  `appearances, foulsCommitted, foulsSuffered, ownGoals, redCards, subIns,
  yellowCards, goalsConceded, saves, shotsFaced, goalAssists, shotsOnTarget,
  totalGoals, totalShots`. **Sem desarmes/passes.** Esse caminho está esgotado.
- `summary.leaders[]` tem `accuratePasses`, `defensiveInterventions`, `totalShots`,
  `saves` — mas **só do líder de cada categoria por time** (1 jogador). Serve no
  máximo como sinal parcial, não para todos.
- `summary.keyEvents[]` tem coordenadas (`fieldPositionX/Y`) de gols/chutes =
  matéria-prima de **mapa de chute**, por evento (não é stat defensiva).
- `summary.boxscore.players` veio **vazio** nos jogos inspecionados.

### 2.2 365Scores — detalhe (a fonte que resolve o problema)
- Per-jogador: `game.{home,away}Competitor.lineups.members[].stats`, com `type`
  (id numérico) + `value`. Cada member tem ainda `ranking` (= rating de atuação,
  hoje já usado) e `heatMap`.
- **37 stats disponíveis. O parser atual (`_STAT_TYPE_MAP`) mapeia ~21.**

#### Stats que JÁ coletamos (revisar ids — ver §4)
shots(3), shots_on_target(4), shots_off_target(5), offsides(9), passes(19),
saves(23), assists(26), goals(27), was_fouled(37), fouls(42), touches(45),
key_passes(46), dribbles_won(54), was_dribbled_past(60), error_led_to_shot(65),
possession_lost(73), expected_assists(78), passes_into_final_third(80),
final_third_possession_won(84), minutes(30).

#### Stats que FALTAM (type id → nome → uso no score)
| type | Stat | Perfil que beneficia |
|---|---|---|
| 39 | **Tackles Won** (ratio "2/2") | Defensor (desarmes) |
| 41 | **Interceptions** | Defensor |
| 40 | **Clearances** (cortes) | Defensor |
| 86 | **Ball Recovery** | Defensor/Meia |
| 55 | **Ground Duels Won** (ratio) | Defensor/Meia |
| 56 | **Aerial Duels Won** (ratio) | Defensor/Zagueiro |
| 6  | **Shots Blocked** | Defensor |
| 83 | **Expected Goals Prevented (xGP)** | **Goleiro** (métrica nº 1) |
| 82 | xG On Target Conceded | Goleiro |
| 43 | Punches | Goleiro |
| 35 | Goals Conceded | Goleiro/Defensor |
| 76 | **Expected Goals (xG)** | Atacante/Meia |
| 79 | xG On Target | Atacante |
| 36 | Big Chances Missed | Atacante (negativo) |
| 52 | Crosses Completed (ratio) | Lateral/Meia |
| 53 | Long Passes Completed (ratio) | Meia/Zagueiro |
| 81 | Backward Passes | (descritivo) |

---

## 3. Furos do modelo de score (estado atual)

### 3.1 Jogador — CORRIGIDO nesta sessão
- **Era:** rating de atuação (9.8 do Messi) não entrava no score; produção via
  z-score saturava (3 gols ≈ 1 gol). Resultado absurdo: Gyökeres (1 gol, nota 8.6)
  > Messi (3 gols, nota 9.8).
- **Agora:** rating = 50% do score_geral em todos os perfis; produção ofensiva
  (atacante/meia) em **escala absoluta** proporcional; `_wavg` NaN-aware
  (redistribui peso sem nota). Messi voltou ao topo dos atacantes.
- **Atualização:** o parser 365Scores foi ampliado, as métricas novas foram
  propagadas até `canonical_player_stats`/`player_match_features`, e o score de
  defensor/goleiro passou a usar desarmes, interceptações, cortes, duelos,
  recuperações, bloqueios e xGP quando disponíveis.

### 3.2 Time — pontos a revisar na refatoração
- `score_defesa` usa bandas + gol contra 1.5x + Elo do adversário (recente, ok),
  mas ainda sem stats defensivas individuais agregadas.
- Calibração (RidgeCV a cada 2 jogos) só recalibra 4 componentes de processo.

### 3.3 Reconciliação de nomes — MITIGADO
- ESPN escreve nome diferente entre roster e stats (ex.: "Agustín Canobbio" vs
  "Agustín Cano"). Mitigação: `config/player_aliases.yaml` +
  `analytics/name_reconciliation.py` (detecta e avisa via WARNING + relatório em
  `data/gold/quality/`). CLI: `fifa-analytics verificar-nomes`.
- **Na refatoração:** considerar casar por `player_id` (existe no canonical e no
  365Scores) em vez de por nome, eliminando a classe de bug.

---

## 4. Riscos/erros pontuais já identificados

- **Ids do `_STAT_TYPE_MAP` (365Scores) possivelmente stale:** o map diz
  `19→accurate_passes` e `20→long_passes_completed`, mas no raw atual
  `type 19 = "Passes Completed"` e long passes = `type 53` (20 não existe).
  **Revisar o map INTEIRO contra o raw** antes de confiar nas colunas atuais.
- Ratios ("5/9 (56%)") hoje pegam só o numerador (`_RATIO_TYPES`). Ao adicionar
  Tackles/Duels/Crosses (todos ratio), decidir se guardar numerador, %, ou ambos.
- Casamento jogador entre fontes por **nome** (frágil). Migrar para `player_id`.
- Dois "stores" de score (scores vs snapshots): mudança de fórmula exige
  reprocessar snapshots — fácil de esquecer (ver memória project-scores-two-stores).

---

## 5. Checklist da refatoração de raiz (futuro)

### Fase A — Aquisição (365Scores)
- [x] Revisar `_STAT_TYPE_MAP` inteiro contra o raw (corrigir ids stale).
- [x] Adicionar as 16 stats faltantes (§2.2), tratando ratios de forma consistente.
- [x] Propagar novas colunas: `sources/scores365.py` → silver → `scores365_pipeline`
      → `canonical_player_stats` (gold).
- [x] Garantir casamento por `player_id` (não por nome) onde possível.
- [x] Decidir armazenamento do `heatMap` (guardar? agregar? ignorar por ora).
      - Decisao: ignorar por ora no silver/gold. O raw permanece preservado; nao ha consumo atual no score/relatorios.
- [x] (Opcional) ESPN `keyEvents` → tabela de chutes com coordenadas (mapa de chute).
      - Implementado via `fact_shots`/`canonical_shots`, com `location_x/location_y` extraidos de `fieldPositionX/Y`.

### Fase B — Modelo de score (jogador)
- [x] **Defensor:** redesenhar com Tackles Won, Interceptions, Clearances,
      Duels Won, Ball Recovery, Shots Blocked, goals_conceded — escala/normalização
      apropriada; rating como componente, não como muleta.
- [x] **Goleiro:** usar xGP (Expected Goals Prevented) como eixo principal +
      save%, saves/jogo, goals_conceded.
- [x] **Atacante/Meia:** incorporar xG/xA como complemento de gols/assists.
- [x] Revalidar pesos por perfil (PLAYER_RATING_WEIGHT, PLAYER_PRODUCTION_REFS).
- [x] Definir refs absolutas por métrica defensiva (ex.: desarmes/jogo de elite).

### Fase C — Consistência geral
- [x] Unificar casamento de nomes por `player_id` (aposentar aliases por nome).
      - Implementado onde ha chave comum: `build_player_match_features()` prefere `player_id` ao anexar lineup ESPN aos stats ESPN. Limite documentado: `365scores` usa `player_id_365`, namespace diferente do `player_id` ESPN; o casamento ESPN↔365 ainda precisa de nome/alias ate existir crosswalk curado.
      - Normalizacao de fallback por nome centralizada em `utils/text.py`: espacos invisiveis/NBSP, sufixo `null`, hifens Unicode e `Al - Harbi`/`Al-Harbi`/`Al Harbi` passam pela mesma chave. Colisoes como `Ederson`/`Éderson` continuam separadas pela chave exata.
- [x] Carregar `schemas/*.yaml` de fato (validação real via `validation/schemas.py`).
- [x] Mover `manifests/tournament_status.parquet` para `data/gold/`.
      - `run_tournament_status()` grava em `data/gold/tournament_status/tournament_status.parquet`.
- [x] Resolver pendências do CLAUDE.md (§"Problemas conhecidos").
      - Atualizadas pendencias ja resolvidas: schemas, `tournament_status`, `slugify` centralizado, reports gerados e dashboard testado.
- [x] Após qualquer mudança de fórmula: reprocessar snapshots + regenerar HTML.

### Fase D — Validação
- [x] Testes para o parser estendido (cada stat nova, ratios, valores ausentes).
- [x] Casos de sanidade do score (ex.: melhor goleiro por xGP, melhor zagueiro
      por desarmes+interceptações) revisados manualmente.
- [x] `node --check` no JS do dashboard + teste stub-DOM.
      - Coberto por `tests/test_dashboard_js.py`: extrai o `<script>` de `reports/tournament/ranking_race.html`, roda `node --check` e executa com DOM minimo stubado.

### Fase E — Fechamento operacional
- [x] Atualizar elencos ESPN.
      - `espn-elencos`: `1246` jogadores, `48` selecoes.
- [x] Atualizar fontes e gold do inicio ao fim.
      - `worldcup26.ir` falhou em 2026-06-18 por erro TLS tambem via `curl -k`; mantido o ultimo gold dessa fonte.
      - ESPN atualizada via `atualizar --sem-worldcup2026`; 365Scores reprocessado com os `24` `source_game_id` ja mapeados.
      - Gold canonico regenerado: `104` partidas, `132` eventos, `1289` lineups/player stats, `618` chutes.
- [x] Regenerar relatorios, status e scores.
      - Relatorios finais: `24` jogos finalizados; status do torneio: `24` completos, `80` nao iniciados.
      - Scores: `48` selecoes ranqueadas e `1258` relatorios de jogadores.
- [x] Reprocessar snapshots do inicio ao fim.
      - Snapshots `snapshot_jogo_001.parquet` a `snapshot_jogo_024.parquet` regenerados.
- [x] Regenerar HTML limpo e atualizado.
      - `reports/tournament/ranking_race.html` regenerado sem `SyntaxWarning`; contem o snapshot final.
      - Validacao final: suite completa fechou em `167 passed`.
- [x] Expor metricas avancadas no dashboard, nao apenas no score interno.
      - Cards de elenco agora mostram lideres e blocos avancados por perfil: xG, xA, xGOT, passes-chave, desarmes, interceptacoes, recuperacoes, duelos, xGP e defesas.
      - Aba Jogadores recebeu opcoes de ordenacao por metricas avancadas por jogo e totais; colunas por posicao passaram a destacar metricas adequadas ao perfil.
      - `player_snapshot_timeline.parquet` reprocessado com `63` colunas, incluindo metricas avancadas e taxas por jogo; HTML regenerado a partir desse snapshot.
- [x] Alinhar notas de jogadores entre tabela, elenco e jogos.
      - O modal de selecao agora respeita o `currentJogo`: aba Jogos esconde partidas finalizadas futuras e aba Elenco usa o mesmo `PLAYER_DATA[currentJogo]` da tabela.
      - `player_snapshot_timeline.parquet` passou a carregar tambem `shots`, `fouls_committed` e `fouls_drawn` para evitar perda de detalhes ao usar uma unica fonte.
      - Corrigido caso Raphinha: o canonical tinha `player_name = "Raphinha "` (espaco final); o snapshot recalculava rating por nome cru e perdia a nota. Agora usa `rating_medio` de `build_player_scores()`, ja sobre nomes normalizados.
      - Correcao ampliada: o gold canonico tambem foi reescrito com nomes limpos. Checagem em `canonical_player_stats`, `canonical_lineups`, `player_match_features` e `player_snapshot_timeline`: `0` nomes com espaco nas pontas, espaco duplicado, NBSP ou hifen Unicode.
      - Checagem final: `0` jogadores com rating canonico ausente na tabela e `0` ratings na tabela sem fonte canonica.

---

## 6. Como reproduzir a investigação

```bash
# stats por jogador no 365Scores (raw) — listar TODOS os type ids
python3 -c "import json,glob; d=json.load(open(sorted(glob.glob('data/raw/365scores/**/details.json',recursive=True))[-1])); g=next(iter(d.values()))['game']; m=g['homeCompetitor']['lineups']['members']; ts={x['type']:x['name'] for p in m for x in (p.get('stats') or [])}; [print(t, ts[t]) for t in sorted(ts)]"

# stats por jogador na ESPN (raw) — confirma os 14 campos
# ver rosters[].roster[].stats em data/raw/espn/**/summaries.json
```

Memória relacionada: `project-data-inventory`, `project-name-reconciliation`,
`project-scores-two-stores`, `project-player-rating-canonical`.
