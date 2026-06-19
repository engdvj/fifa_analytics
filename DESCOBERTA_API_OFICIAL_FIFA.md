# Descoberta: API oficial da FIFA (Copa 2026)

> **Status:** descoberta validada em 2026-06-19. Endpoints testados e funcionando. Implementação ainda não iniciada — este doc é o ponto de retomada (continuar em outra sessão/PC).

A FIFA tem **duas APIs públicas, sem autenticação e sem chave**, que cobrem a Copa 2026 com dados **oficiais** — muito além do que ESPN/365scores/wikipedia oferecem hoje. O site `fifa.com` é uma SPA React (por isso `curl`/scraping na URL da página só traz a casca vazia ~4.5KB), mas as APIs por trás respondem direto. Basta mandar um `User-Agent` de browser.

Isto é considerado **um achado grande**: viabiliza usar a FIFA como fonte primária oficial e repensar o modelo de análise.

---

## IDs da Copa 2026

| O quê | ID |
|---|---|
| Competição (Copa do Mundo masc.) | `IdCompetition=17` |
| Temporada (edição 2026) | `IdSeason=285023` |
| Stage Grupo (exemplo) | `289273` |
| IdMatch (exemplo, formato `400…`) | `400021443` |
| IdTeam (exemplo) | `43854` |
| **IdIFES** (id interno Stats Perform, usado pelo fdh-api) | `151600` |

---

## 1. FIFA Data API v3 — `https://api.fifa.com/api/v3`

JSON puro, sem chave. Dados estruturais (jogos, escalações, eventos).

| Endpoint | O que traz |
|---|---|
| `/competitions/all?language=en&count=500` | Todas as competições |
| `/seasons?idCompetition=17&language=en&count=100` | Edições (acha 285023) |
| `/stages?idCompetition=17&idSeason=285023&language=en` | Fases |
| `/calendar/matches?idCompetition=17&idSeason=285023&language=en&count=200` | **104 jogos**: placar, pênaltis, agregado, weather, attendance, stage, grupo, data local/UTC. **Inclui `Results[].Properties.IdIFES`** (104/104) |
| `/live/football/17/285023/{idStage}/{idMatch}?language=en` | Detalhe completo do jogo: escalação com posição tática (`LineupX`/`LineupY`), gols, cartões, substituições, árbitros, estádio, clima, público. Também tem `Properties.IdIFES` |
| `/timelines/17/285023/{idStage}/{idMatch}?language=en` | Timeline de eventos |
| `/picture/flags-{format}-{size}/{COD}` | Bandeiras (ex: `CIV`) |

---

## 2. FIFA Data Hub — `https://fdh-api.fifa.com/v1`

Dados avançados/tracking (normalmente pagos — tipo FIFA Training Centre / Stats Perform). **Formato dos stats:** lista de triplas `[NomeMetrica, valor, isOfficial]`.

| Endpoint | O que traz |
|---|---|
| `/powerranking/season/285023.json` (~600KB) | **Power Ranking oficial por jogador**: attacking/defensive/creativity Score+Rank, rankWithinTeam, rankChange, + `tournamentHistory` rodada a rodada. Split goalkeepers/outfieldPlayers |
| `/powerranking/match/{IdIFES}.json` | Power ranking daquele jogo (fullTime, period, outfield/goalkeepers) |
| `/stats/season/285023/team/{idTeam}.json` | **145 métricas por time** (acumulado) |
| `/stats/season/285023/players.json` (~5.4MB) | **1249 jogadores × 119 métricas** (dict idPlayer→métricas) |
| `/stats/match/{IdIFES}/teams.json` | 145 métricas por time, por jogo (dict idTeam→métricas) |
| `/stats/match/{IdIFES}/players.json` | Métricas por jogador, por jogo |

**Pendente mapear (baixa prioridade — dados deriváveis dos outros):** `/teamsqualified/season/{s}/stage/{stg}`, `/topseasonplayerstatistics/season/{s}/topscorers`, `/statistics/headtohead/{a}/{b}` (404 com os ids/forma testados).

---

## Mapeamento IdMatch (v3) ↔ IdIFES (fdh) — **RESOLVIDO**

O fdh-api por-jogo usa **IdIFES** (id interno Stats Perform), **não** o IdMatch `400…` da v3 (usar IdMatch dá 404).

**O IdIFES já vem no `calendar/matches`** em `Results[].Properties.IdIFES` (104/104 jogos) → **não precisa de chamada `live` extra por jogo**.

Fluxo: 1 chamada `calendar/matches` pega IdMatch+IdIFES de todos os jogos → loop nos endpoints fdh por IdIFES.

---

## Catálogo de métricas (fdh-api) — grupos de alto valor

145 por time / 119 por jogador. Os grupos que **mudam o que o modelo pode fazer**:

- **Qualidade de chance:** `XG`, `Threat` (≈xThreat), `AttemptAtGoal*` desmembrado por origem (Pass/Cross/Corner/FreeKick/Penalty/Rebound/BallProgression), zona (Inside/OutsidePenaltyArea), desfecho (OnTarget/OffTarget/Blocked). Espelho defensivo: `AttemptAtGoalAgainst*`, `GoalsConcededFromAttemptAtGoalAgainst`.
- **Controle territorial (NOVO — não existia nas fontes antigas):** `PitchControl`, `FinalThirdPitchControl`, `Possession`, `NumberOfPossessionSequences`, `NumberOfShotEndingSequences`.
- **Fases de jogo = ESTILO MEDIDO (substitui o z-score inferido):** `PhaseAggregate*` em 16 fases — AttackingTransition, BuildUpOpposed/Unopposed, Counterattack, CounterPress, DefensiveTransition, FinalThird, High/Mid/LowBlock, High/Mid/LowPress, LongBall, Progression, Recovery, SetPieces.
- **Quebra de linhas (raro):** `Linebreaks*` por setor (Defensive/Midfield/Attacking line), attempted vs completed, e UnderPressure.
- **Movimentação sem bola (raríssimo):** `OffersToReceive*` (InBehind/InBetween/InFront/Inside/Outside), `ReceptionsInBehind`, `ReceptionsUnder(Direct/Indirect/No)Pressure`.
- **Sob pressão:** `DistributionsUnderPressure(+Completed)`, `DefensivePressuresApplied`, `DirectDefensivePressuresApplied`, `ForcedTurnovers`, `BallRecoveryTime`.
- **Tracking físico (NOVO):** `TotalDistance`, `Distance{Walking,Jogging,LowSpeedSprinting,HighSpeedRunning,HighSpeedSprinting}`, `Sprints`, `SpeedRuns`, `AvgSpeed`, `TopSpeed`.
- **Progressão/largura:** `Attempted/CompletedBallProgressions`, `Attempted/CompletedSwitchesOfPlay`, `FinalThirdEntriesReception*` por canal.
- **Goleiro:** `GoalkeeperSaves(OnTarget)`, `GoalkeeperSavePercentage`, `GoalkeeperDefensiveActionsInside/OutsidePenaltyArea`, `CleanSheets`.
- **Básico/disciplina:** Goals, Assists, Passes(Completed), Corners, Crosses(Completed), TakeOnsCompleted, Offsides, Fouls(For/Against), Yellow/Red(Direct/Indirect)Cards, OwnGoals, Penalties(Scored), MatchesPlayed, TimePlayed, NumberOfInvolvements.

---

## CMS FIFA+ (só layout, NÃO os dados)

`https://cxm-api.fifa.com/fifaplusweb/api/pages/{locale}/{relativeUrl}`
Ex: `/pages/en/tournaments/mens/worldcup/canadamexicousa2026/power-rankings`.
Devolve só o **layout dos widgets** (lista um bloco `powerRanking` com properties vazio) — os números vêm das APIs acima. Útil apenas pra descobrir que widgets existem.

---

## Como foi descoberto (para reproduzir/atualizar quando os hashes mudarem)

1. Bundle da SPA: `https://www.fifa.com/static/js/main.<hash>.js` — lista env (`SERVICE_API_URL`=cxm-api).
2. Endpoints de dados estão nos **chunks lazy** `static/js/{id}.{hash}.chunk.js`. O mapa `id→hash` está no `main.js`, logo antes de `.chunk.js`.
3. Baixar todos os chunks e `grep` por `powerranking` / `statistics` / `fetch`.
4. baseURL do fdh = `${fdh-api.fifa.com}/${SY}`, onde `SY="v1"`.

---

## Caçadas futuras: outras competições (para depois)

A descoberta da FIFA não foi entregue — foi **caçada** (bundle → chunks lazy → endpoints escondidos). A mesma técnica pode render em outras competições. A FIFA não é responsável por ligas/Champions (organização em camadas: **FIFA** = seleções/Mundial; **confederações** = UEFA/CONMEBOL; **ligas nacionais** = CBF/LaLiga/PL). Cada uma tem seu próprio provedor.

**Sondagem inicial já feita (2026-06-19):**

| Alvo | Status | Nota |
|---|---|---|
| **UEFA / Champions League** | 🟢 Prioritário | `https://comp.uefa.com/v2/competitions` responde 200 (aberto, 306 competições incl. Champions, Nations League, Ligue 1). Mesmo padrão de SPA da FIFA → **alta chance** de ter stats avançados num chunk lazy, tipo o fdh-api. Fonte oficial equivalente à FIFA pra Champions. **Caçar primeiro.** |
| **La Liga / Premier / Bundesliga** | 🟡 Incerto, vale tentar | Cada uma tem site-SPA próprio. Ligas ricas costumam ter painéis Opta/AWS de stats avançados — caçar pode revelar endpoints abertos. |
| **StatsBomb Open Data** | 🟡 Só histórico | `https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json` (grátis, GitHub). Event data nível pro, mas só temporadas históricas (Champions/La Liga até ~2019/20). Ótimo p/ treinar modelo, inútil ao vivo. |
| **football-data.org** | 🟡 Básico c/ key | Free tier cobre 5 grandes ligas + Champions + **Brasileirão Série A**, mas só dados básicos (jogos/tabela/artilheiro), sem xG/tracking. Rate limit baixo. |
| **Brasileirão (avançado, ao vivo)** | 🔴 Difícil | CBF sem API pública decente. Métricas avançadas são pagas (Sofascore/Opta). Caçar provavelmente só acha o básico. |

**Ressalva honesta:** o que tornou a FIFA excepcional foi ter os dados **caros** (tracking físico, 16 fases) abertos e ao vivo — isso é incomum, meio sorte. Nas ligas, o básico costuma estar aberto; o avançado nem sempre. Mas não dá pra saber sem caçar — foi o que provou a FIFA.

**Método de caça (o que funcionou, reaplicar):**
1. Abrir o site-SPA, achar `main.<hash>.js` e o env com a base da API.
2. Extrair o mapa `id→hash` dos chunks lazy (logo antes de `.chunk.js` no main).
3. Baixar todos os chunks; `grep` por `statistics`/`ranking`/`stats`/`fetch`/baseURL.
4. Reconstruir os endpoints (templates `${...}`) e testar com `User-Agent` de browser.
5. Mapear o id interno (na FIFA foi o `IdIFES`, escondido em `Properties`) — outras fontes têm o equivalente.

---

## Decisão-mãe do projeto (definida com o usuário, 2026-06-19)

A alma do projeto é **narrativa + motor de score próprio JUNTOS**, sobre dados oficiais — acompanhar a evolução de cada time **e** traduzir isso em números organizados de um jeito personalizado. **Não** é "só consumir a FIFA" nem "construir tudo do zero competindo com a FIFA".

**Princípio de divisão:**
- **Consumir (não recriar):** medição bruta que a FIFA faz melhor — XG, Threat, PitchControl, tracking físico, avaliação **individual** de jogador (Power Ranking). Recriar = reinventar pior, gastando energia à toa.
- **Construir (é o motor dele, FIFA não faz):** score de **seleção** (síntese "quem joga melhor como time"), **evolução** ao longo do torneio (foto→filme: bar chart race, subiu/caiu), e **narrativa** ancorada em dado oficial.
- **Metáfora-guia:** FIFA = olhos (medição), motor próprio = cérebro (síntese + evolução), narrativa = voz. **Empilham, não competem.** Os dados oficiais não tornam a análise redundante — tornam-na *credível*.

---

## Próximos passos (retomar daqui)

**Arquitetura decidida:** FIFA **primária + fallback** (mantém ESPN/wikipedia como rede de segurança — é API interna, sem SLA, ponto único de falha se for fonte única).

**Modelo de score — repensar do zero, mas mantendo o que é "dele":**
- `score_resultado` + Elo → **mantém** (resultado/trajetória são coisa dele).
- `score_ataque/defesa/eficiência/controle` por proxy → **vira síntese de métricas oficiais** (XG, Threat, AttemptAtGoalAgainst, PitchControl) — joga fora a adivinhação, mantém a fórmula de síntese.
- `estilo de jogo` por z-score inferido → **vira leitura direta das 16 fases `Phase*`** (deixa de adivinhar).
- calibração RidgeCV contra saldo de gols → **mantém** (é o que dá sentido aos pesos; agora com features de verdade).
- Power Ranking FIFA → **novo insumo/benchmark**: comparar score próprio vs oficial valida ou expõe discordâncias (ótimo material de narrativa).

**Fases de implementação:**
1. **Fase 1 — Ingestão (mecânica, baixo risco):** criar `sources/fifa.py` (v3 + fdh-api) + transforms → novo schema gold; ESPN/wiki recuam para fallback. **Não toca no score ainda.**
2. **Olhar os dados reais** num jogo aterrissado — o formato do motor novo fica óbvio com dados na mesa (em vez de chutado no abstrato).
3. **Fase 2 — Motor novo + narrativa ancorada**, desenhado com evidência.

> Sugestão de retomada: começar pela Fase 1 (ou pedir um plano escrito do `sources/fifa.py` + schema antes de codar). Validar num jogo real antes de mexer no modelo.
