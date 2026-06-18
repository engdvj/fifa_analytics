# Checklist - Auditoria de Jogadores

Gerado em: 2026-06-18

## Prioridade Alta

- [x] Corrigir o casamento de rating 365Scores com jogadores canonicos.
  - Evidencia: `154` ratings anexados por casamento fraco de apenas 1 token; exemplo `César Huerta` recebendo rating de `Cesar Montes`.
  - Arquivos: `src/fifa_analytics/workflows/canonical_reports.py`, `src/fifa_analytics/workflows/scores365_pipeline.py`.

- [x] Deduplicar e tornar um-para-um o uso de ratings 365Scores.
  - Evidencia: `data/gold/fact_player_match_stats/365scores_rating.parquet` tem duplicata `copa_2026_jogo_007 / Brasil / Danilo / 6.8`; `Danilo` e `Danilo Santos` recebem a mesma nota.

- [x] Resolver links/atribuicao de gol contra.
  - Evidencia: `6` eventos de gol apontam para jogador inexistente no time beneficiario, criando links quebrados como `reports/players/catar/miro_muheim`.
  - Causa provavel: em `gol_contra`, `team` e o beneficiario, mas `player` pertence ao adversario.

- [x] Corrigir colisao de slugs de jogadores no mesmo time.
  - Evidencia: `Brasil / Ederson` e `Brasil / Éderson` colidem em `reports/players/brasil/ederson.md`; a selecao aponta duas linhas para o mesmo alvo.

- [x] Regenerar `data/gold/analytics/player_match_features.parquet` e relatorios de jogadores apos corrigir rating.
  - Evidencia: o Parquet persistido atual nao tem coluna `rating`, mas reconstruir em memoria a partir do canonico gera `rating` com `836` valores.

## Prioridade Media

- [x] Normalizar nomes de roster antes de gerar paginas e comparar cobertura.
  - Evidencia: `Trézéguet null`, `Zizo null`, `Maurício null`; tambem nomes com espaco final como `Ederson `, `Raphinha `, `Rodri `, `Vitinha `.
  - Correcao de raiz: `clean_person_name()`/`person_name_key()` centralizam espacos invisiveis, NBSP, `null`, hifens Unicode e hifen com espacos. O gold canonico, features, snapshots e dashboard usam a mesma regra; joins por nome caem para chave exata apenas quando ha colisao real.

- [x] Corrigir ou documentar divergencias entre totais de selecao e soma de jogadores.
  - Evidencia: `5` divergencias de gols, `2` de faltas, `1` de defesas e `1` de chutes no alvo.
  - Parte dos gols vem de gol contra, mas a exibicao atual nao deixa isso claro.
  - Correcao: relatorios de selecao agora exibem `gols contra a favor/sofridos` quando aplicavel e documentam que totais de selecao podem vir de estatisticas de equipe enquanto a tabela de jogadores soma eventos individuais disponiveis.

- [x] Ajustar paginas de jogadores sem partida.
  - Evidencia: `14` paginas com `jogos = 0` e linha vazia em "Por jogo" (`Neymar`, `Zeno Debast`, `Ronald Araújo`, etc.).

- [x] Investigar cobertura incompleta de elenco por jogo.
  - Evidencia: `6` match/team com menos de 26 jogadores em lineup/stats: Brasil, Nova Zelandia, Belgica, Uruguai, Inglaterra, Gana.
  - Correcao: `player_match_features` agora expande o roster por `match_id/team`, criando linhas DNP (`appearances = 0`) para jogadores sem stats naquela partida. Validacao atual: `48` pares match/team, `0` abaixo do roster, minimo `26` jogadores por par.

- [x] Integrar `365scores` ao `source_match_map` ou criar chave robusta de jogo.
  - Evidencia: a fonte 365 e mapeada por inferencia; `2/24` jogos tem data divergente contra o canonico.
  - Correcao: criado `data/gold/dim_match/365scores_match_map.parquet`, materializando `source_game_id -> match_id` com desempate por menor diferenca de data.

- [x] Revisar agregacao do bloco de jogadores no relatorio de selecao.
  - Evidencia: `_team_players_by_position` conta `match_id.nunique`, entao jogador de roster sem aparicao pode parecer "listado por jogo" de forma confusa.
  - Correcao: bloco agrega por `player_slug`, usa `appearances` quando disponivel e preserva metricas decimais como xG/xA.

## Prioridade Baixa

- [x] Corrigir transliteracao de slugs para letras como `ø`.
  - Evidencia: `Martin Ødegaard` vira `martin_degaard`, `Ørjan Nyland` vira `rjan_nyland`.

- [x] Revisar mapeamento de perfil `DM` vs `CDM`.
  - Evidencia: `DM` vira defensor, `CDM` vira meio, embora ambos sejam volante em outras partes do projeto.

- [x] Adicionar dedupe defensivo em datasets canonicos multi-fonte.
  - Evidencia: hoje so a ESPN fornece player stats/lineups; se outra fonte entrar, `build_canonical_dataset` concatena sem deduplicar entidades.
  - Correcao: `build_canonical_dataset` agora aplica dedupe por prioridade de fonte em chaves claras (`match_id/team`, `match_id/team/player_name`, `match_id`), preservando datasets sem chave confiavel.

## Checagens OK

- [x] Silver e gold estao logicamente consistentes para ESPN player stats, ESPN lineups, ESPN rosters e 365scores.
- [x] `canonical_player_stats`, `canonical_lineups` e `player_match_features` nao tem duplicatas por `match_id/team/player_name`.
- [x] `canonical_player_stats`, `canonical_lineups`, `player_match_features` e `player_snapshot_timeline` tem `0` nomes com espaco nas pontas, espaco duplicado, NBSP ou hifen Unicode.
- [x] ESPN canonical esta toda mapeada: `0` stats/lineups sem match canonico e `0` times fora de home/away.
- [x] Lineups e stats ESPN tem cobertura cruzada: `0` lineup sem stats e `0` stats sem lineup.
- [x] Roster tem tamanho plausivel em todas as selecoes: nenhum time fora do intervalo 23-30 jogadores.
- [x] Nao encontrei negativos, ratings fora de 0-10, minutos fora de 0-130, `shots_on_target > shots`, ou `goals > shots_on_target` nos dados principais.

## Fechamento Operacional

- [x] Atualizar elencos, fontes disponiveis, gold, relatorios e scores apos as correcoes.
  - `espn-elencos`: `1246` jogadores, `48` selecoes.
  - `365scores`: `24` jogos com stats, `752` jogadores, `48` linhas de time.
  - Gold canonico: `104` partidas, `1289` lineups/player stats, `618` chutes.
  - Scores/relatorios: `48` selecoes ranqueadas e `1258` relatorios de jogadores.

- [x] Reprocessar snapshots e dashboard do inicio ao fim.
  - Snapshots regenerados de `snapshot_jogo_001.parquet` a `snapshot_jogo_024.parquet`.
  - `reports/tournament/ranking_race.html` regenerado sem `SyntaxWarning`.
  - Validacao final: suite completa fechou em `167 passed`.

- [x] Registrar excecao de fonte indisponivel.
  - `worldcup26.ir` falhou em 2026-06-18 por TLS tambem via `curl -k`; foi mantido o ultimo gold da fonte e o refresh seguiu com ESPN + 365Scores + dados canonicos existentes.
