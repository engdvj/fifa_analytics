# FIFA Analytics - Copa do Mundo 2026

Pipeline em Python + Jupyter para coletar, validar, analisar e gerar relatorios dos 104 jogos da Copa do Mundo 2026.

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

## Fluxo do dia a dia — quando ha jogos novos

A rotina normal, quando uma nova rodada de jogos aconteceu:

```bash
source .venv/bin/activate
fifa-analytics atualizar
```

Esse unico comando coleta as fontes (`worldcup2026` + ESPN), reconcilia o indice canonico, gera os relatorios de jogos finalizados, atualiza o status do torneio e recalcula scores/rankings de selecoes. E seguro rodar todos os dias — ele relê as fontes do zero e nao duplica nada.

Depois de `atualizar`, a narrativa de cada jogo ("A historia do jogo") vem de um texto generico gerado pelo pipeline. Para reescrever com prosa real, peca para invocar a skill `atualizar-jogo` (em `.claude/skills/atualizar-jogo/`) numa sessao do Claude Code: ela le os dados reais do jogo (placar, eventos, estatisticas) e escreve um texto variado, sem repetir a mesma formula entre jogos. A skill protege esse texto com o marcador `<!-- narrativa-manual -->` no fragmento — depois que isso esta lá, rodar `atualizar` de novo NAO sobrescreve a narrativa escrita a mao.

**Ordem correta:**

```text
1. fifa-analytics atualizar          # coleta dados + gera relatorios + recalcula scores
2. skill atualizar-jogo (no Claude)  # reescreve a narrativa dos jogos novos com prosa real
```

Nunca inverta essa ordem — rodar `atualizar` depois de escrever narrativas manuais so e seguro porque o marcador protege o texto, mas a skill so consegue ler dados atualizados se o passo 1 já tiver rodado.

### Quando rodar `espn-elencos`

```bash
fifa-analytics espn-elencos
```

Coleta o elenco completo (convocacao oficial, com posicao estavel) de cada uma das 48 selecoes — diferente da escalacao por partida, que so mostra quem jogou. Isso ja foi coletado para todas as selecoes confirmadas na Copa; só precisa rodar de novo se uma convocacao mudar (lesao, substituicao na lista) ou se uma nova selecao aparecer nos dados sem elenco ainda coletado. Nao precisa rodar isso a cada atualizacao diaria.

### Se uma fonte estiver fora do ar

```bash
fifa-analytics atualizar --sem-espn
fifa-analytics atualizar --sem-worldcup2026
```

## Comandos individuais

Quando precisar rodar so uma etapa especifica em vez do fluxo completo:

```bash
fifa-analytics worldcup2026        # fonte operacional principal (104 jogos, eventos basicos)
fifa-analytics espn                # enriquecimento ESPN (stats, escalacoes por partida, eventos)
fifa-analytics espn-elencos        # elenco/convocacao completo por selecao (raro precisar)
fifa-analytics wikipedia           # referencia publica nao-oficial
fifa-analytics indice-canonico     # reconcilia fontes -> indice canonico em data/gold
fifa-analytics relatorios-basicos  # gera fragmentos + relatorios finais por jogo
fifa-analytics status-torneio      # standings, status, pendencias
fifa-analytics scores              # scores de selecoes + relatorios de time/jogador
fifa-analytics remontar-relatorio <match_id>  # remonta um relatorio a partir dos fragmentos, sem recalcular nada
```

`remontar-relatorio` e usado pela skill `atualizar-jogo` apos escrever a narrativa manual de um jogo — ele so reconstroi o `.md` final juntando os fragmentos existentes, nao refaz coleta nem calculo.

## Testar

```bash
source .venv/bin/activate
python -m pytest -q
```

Relatorio de amostra de ponta a ponta, sem depender de fontes externas:

```bash
fifa-analytics amostra
```

## O que cada relatorio mostra

### Relatorio de jogo (`reports/final/{fase}/{rodada}/{numero}_{time1}_x_{time2}.md`)

Organizado em: historia do jogo (narrativa) -> estatisticas comparativas (posse, chutes, cartoes, gols, frente a frente) -> escalacoes titulares. Metadados tecnicos (arbitro, publico, fontes, status de qualidade) ficam no comentario HTML no topo do arquivo, fora da leitura principal.

### Relatorio de selecao (`reports/teams/{selecao}.md`)

Nota geral de 0 a 100, combinando seis componentes por media ponderada:

| Componente | Peso | O que mede |
|---|---|---|
| Resultado | 35% | Aproveitamento real de pontos (vitoria/empate/derrota) |
| Defesa | 20% | Gols sofridos, chutes no alvo sofridos, jogos sem sofrer gol |
| Ataque | 15% | Gols e chutes no alvo por jogo |
| Forca Relativa | 15% | Rating Elo — contextualiza o resultado pela qualidade do adversario e pelo dominio de jogo (gols, chutes, posse), nao so o placar puro |
| Eficiencia | 10% | Conversao de chutes em gol |
| Controle | 5% | Posse, passes, precisao de passe |

Os pesos nao sao iguais (nao e simplesmente 1/6 para cada) porque os componentes nao tem o mesmo poder de explicar o resultado de uma partida de futebol — ver a justificativa completa nos comentarios de `TEAM_SCORE_WEIGHTS` em `src/fifa_analytics/analytics/scores.py`.

Tambem aparecem: classificacao do grupo, evolucao da nota por jogo (a partir do 2o jogo), mediana/consistencia/tendencia (a partir do 2o jogo), e a tabela de jogadores do elenco agrupada por posicao (goleiro/defensor/meio/atacante).

### Rankings (`reports/rankings/selecoes/{metrica}.md`)

Uma tabela por componente (geral, resultado, ataque, defesa, eficiencia, controle, forca-relativa, forma) ordenada por essa metrica.

### Confianca da nota

`nivel_evidencia` (`baixa`/`media`/`alta`) reflete quantos jogos a selecao ja disputou em relacao aos 3 da fase de grupos — nao e probabilidade de a nota estar "certa", e so um aviso de estabilidade estatistica. Jogos do mata-mata so aumentam a confianca, nao mudam a referencia de 3.

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
- `11_scores.ipynb`: inspeciona scores acumulados por selecao.

## Status de qualidade

- `ok`: dados consistentes entre fontes, incluindo contagem de gols vs. eventos da timeline.
- `aviso`: divergencia entre fontes (placar, ou numero de eventos de gol diferente do placar oficial).
- `erro`: divergencia grave ou dado invalido.
- `ausente`: fonte ou campo esperado ausente.
- `desconhecido`: status ainda nao determinado.

## Fontes de dados

| Fonte | Status | O que coleta |
|---|---|---|
| `worldcup2026` | Operacional | 104 jogos, selecoes, estadios, classificacao, gols basicos |
| `espn` | Operacional | Calendario, stats por selecao, escalacoes por partida, stats por jogador |
| `espn-elencos` | Operacional | Elenco/convocacao completo por selecao, com posicao estavel |
| `wikipedia` | Operacional | Partidas e classificacao de grupos (nao oficial) |
| `canonical` | Derivado | Indice reconciliado das fontes acima, prioridade `worldcup2026 > espn > wikipedia` |

A pipeline calcula classificacao internamente e valida contra as fontes. Resultados gravados em `data/silver/validation_results/`.

## Troubleshooting

**ESPN retornou erro ou ficou fora do ar:**
```bash
fifa-analytics atualizar --sem-espn
```

**Reescrevi uma narrativa manual e ela voltou ao texto generico:**
Confirme que o fragmento `reports/fragments/{match_id}/01b_story.md` comeca com a linha `<!-- narrativa-manual -->`. Sem ela, `atualizar`/`relatorios-basicos` sobrescreve o texto na proxima execucao.

**Fontes divergem no placar ou no numero de gols da timeline:**
Confira o campo `data_quality_status` no comentario HTML do relatorio do jogo, e `data/silver/validation_results/` para o detalhe da comparacao entre fontes.

**Links de jogador quebrados:**
Geralmente e nome de jogador escrito diferente entre fontes (ex: "C. Larin" vs "Cyle Larin") ou time errado atribuido a um autor de gol contra. Verifique a escalacao do jogo certo em `reports/final/.../{jogo}.md` para confirmar o nome e o time corretos antes de corrigir o link manualmente.
