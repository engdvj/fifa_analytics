---
name: atualizar-jogo
description: Roda o pipeline de dados da Copa 2026 para um ou mais jogos e reescreve a narrativa ("A historia do jogo") com texto variado e bem escrito, gerado diretamente por Claude a partir dos dados reais — substitui o texto template fixo do pipeline Python.
---

# Atualizar jogo

Esta skill faz dois tipos de trabalho em sequência: primeiro deixa os dados em dia (coleta + reconciliação + scores), depois reescreve a narrativa de cada jogo pedido com prosa real — não o texto fixo gerado por `_build_match_story` em `canonical_reports.py`.

## Quando usar

O usuário pede para "atualizar o jogo X", "gerar a história do jogo Y", "rodar a copa e melhorar as narrativas", ou referencia esta skill diretamente.

## Passo 1 — Atualizar dados

Rode o pipeline correspondente ao que o usuário pediu:

```bash
source .venv/bin/activate && fifa-analytics atualizar
```

Ou, se o usuário só quer recompor relatórios sem recoletar fontes:

```bash
source .venv/bin/activate && fifa-analytics relatorios-basicos && fifa-analytics scores
```

Isso gera (ou regenera) `reports/fragments/{match_id}/01b_story.md` com uma narrativa determinística em Python — funcional, mas repetitiva entre jogos (mesmo molde de frases). O próximo passo substitui esse texto.

## Passo 2 — Identificar os jogos a reescrever

Se o usuário não especificou quais jogos, liste os finalizados:

```bash
find manifests -name "*.yaml" -newer <referencia> 2>/dev/null
```

Ou simplesmente pergunte/assuma todos os jogos com `status: finalizado` que ainda não tiveram a narrativa revisada por você nesta sessão.

## Passo 3 — Para cada jogo, ler os dados reais

**Nunca invente.** Leia sempre os dados brutos antes de escrever — a narrativa só pode citar gols, jogadores, cartões e estatísticas que existem nos dados. Para o jogo `{match_id}`:

```bash
source .venv/bin/activate && python -c "
import pandas as pd
match_id = '<match_id>'
matches = pd.read_parquet('data/gold/dim_match/canonical_matches.parquet')
events = pd.read_parquet('data/gold/fact_events/canonical_events.parquet')
team_stats = pd.read_parquet('data/gold/fact_team_match_stats/canonical_team_stats.parquet')
player_stats = pd.read_parquet('data/gold/fact_player_match_stats/canonical_player_stats.parquet')

m = matches[matches['canonical_match_id'] == match_id].iloc[0]
print('PLACAR:', m['home_team'], int(m['home_score']), 'x', int(m['away_score']), m['away_team'])
print()
print('EVENTOS:')
print(events[events['match_id'] == match_id][['minute','minute_sort','player','team','event_type']].sort_values('minute_sort').to_string())
print()
print('STATS DE TIME:')
print(team_stats[team_stats['match_id'] == match_id].to_string())
print()
print('DESTAQUES DE JOGADORES (gols/assist/defesas):')
ps = player_stats[player_stats['match_id'] == match_id]
cols = [c for c in ['player_name','team','goals','assists','saves','shots_on_target'] if c in ps.columns]
print(ps[ps[['goals','assists','saves']].fillna(0).gt(0).any(axis=1)][cols].to_string() if not ps.empty else 'sem dados')
"
```

Ajuste as colunas conforme o que existir (alguns jogos podem não ter `team_stats`/`player_stats` completos).

## Passo 4 — Escrever a narrativa

Escreva a seção "A historia do jogo" em prosa real, seguindo estas regras:

- **Cada jogo precisa ler diferente dos outros.** Não reuse a mesma fórmula de abertura/fechamento em jogos consecutivos. Varie o ângulo: as vezes comece pelo contexto (mando de campo, fase do grupo), as vezes pelo primeiro lance decisivo, as vezes por uma estatística que conta a história (posse, eficiência, um time que sofreu mas venceu).
- **Use os bullets cronológicos só quando agregarem.** Para jogos com 3+ gols ou viradas, bullets com placar parcial ajudam a acompanhar. Para jogos de 1-2 gols, pode ser só prosa corrida sem precisar de lista.
- **Cite com precisão.** Minuto exato, nome completo do jogador como aparece nos dados, placar real. Use os wikilinks no formato `[[reports/players/{slug_time}/{slug_jogador}\|Nome]]` e `[[reports/teams/{slug_time}\|Nome do Time]]` (mesmo padrão usado pelo restante dos relatórios — confira em outro arquivo de `reports/final/` já gerado se tiver dúvida do slug exato).
- **Não repita números já visíveis no nome do arquivo.** O arquivo já se chama `NNN_time1_x_time2.md` e o título com placar foi removido do corpo — não comece a narrativa restatando "Time A 2 x 0 Time B" como primeira frase se isso for óbvio; prefira revelar o resultado como parte do enredo (quem decidiu, quando, como).
- **Cartões vermelhos e pênaltis entram quando mudam o jogo**, não como nota de rodapé burocrática.
- **Tamanho:** 1 a 3 parágrafos curtos, ou prosa + bullets cronológicos quando o jogo tiver muitos lances. Não infle com adjetivos vazios ("emocionante", "espetacular") sem um fato que sustente o adjetivo.

## Passo 5 — Escrever o fragmento e remontar o relatório

Escreva o texto final em:

```
reports/fragments/{match_id}/01b_story.md
```

O arquivo deve conter exatamente, **incluindo a primeira linha com o marcador**:

```markdown
<!-- narrativa-manual -->
## A historia do jogo

<seu texto aqui>
```

O marcador `<!-- narrativa-manual -->` é obrigatório na primeira linha. Sem ele, o pipeline (`fifa-analytics atualizar` ou `relatorios-basicos`) trata o fragmento como gerado automaticamente e o sobrescreve com o texto template na próxima execução — com o marcador, o código em `write_canonical_fragments` (`canonical_reports.py`) pula a regeneração desse fragmento e preserva sua narrativa, mesmo que alguém rode o pipeline completo de novo por engano em uma sessão futura.

Depois remonte o relatório final sem recalcular nada:

```bash
source .venv/bin/activate && fifa-analytics remontar-relatorio {match_id}
```

Repita os passos 3-5 para cada jogo da lista.

## Passo 6 — Resumo final

Ao terminar todos os jogos pedidos, liste em 1 linha por jogo: `match_id — resultado — uma frase do que ficou diferente na narrativa`. Não repita o texto inteiro de cada narrativa no chat.

## Regras

- Sempre inclua `<!-- narrativa-manual -->` como primeira linha do fragmento (Passo 5) — é o que protege a narrativa de ser sobrescrita se o pipeline completo rodar de novo numa sessão futura. Sem o marcador, o texto template volta a aparecer silenciosamente na próxima vez que alguém rodar `atualizar` ou `relatorios-basicos`.
- Apesar da proteção do marcador, prefira ainda assim nunca rodar `fifa-analytics relatorios-basicos` ou `atualizar` depois de escrever as narrativas na mesma sessão — a ordem correta continua sendo: atualizar dados → escrever narrativas (com marcador) → remontar relatórios.
- Se um jogo não tiver `events` ou `team_stats` suficientes para uma narrativa rica, seja honesto no texto (ex: "dados de eventos limitados para esta partida") em vez de inventar.
- Se o placar mudar numa atualização futura (jogo que estava "em andamento" e virou "finalizado", ou correção de fonte), a narrativa anterior fica desatualizada — sempre releia os dados atuais antes de reescrever, não confie em uma narrativa de sessão anterior.
