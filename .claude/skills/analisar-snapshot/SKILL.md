---
name: analisar-snapshot
description: Escreve a leitura analítica em prosa de UM jogo (um snapshot) da Copa 2026, na camada Diagnóstica da aba Analytics — Claude lê os achados estruturados do fact_insights daquele jogo e conta, em prosa, por que ele terminou como terminou. Foco total no jogo do snapshot, sem repetir contexto de torneio entre snapshots. Não inventa: cita só os achados e números reais daquele jogo.
---

# Analisar snapshot

Esta skill produz a **memória semântica** da camada de análise: a leitura em prosa de um
snapshot, que o próximo snapshot vai ler e cobrar. É o que transforma a lista de achados
determinísticos (`fact_insights`) em *análise que evolui* — não uma foto isolada.

O motor determinístico (Python, `analytics/diagnostic.py`) já roda dentro do `fifa-coletar`
e grava os achados estruturados por jogo. Esta skill **não recalcula nada** — lê esses
achados e escreve a síntese.

## Quando usar

O usuário pede para "analisar o snapshot N", "escrever a leitura da rodada", "atualizar a
análise diagnóstica", ou referencia esta skill. Tipicamente após uma coleta que finalizou
jogos novos.

## Conceitos

- **snapshot = UM único jogo.** É a posição cronológica de um jogo finalizado (1, 2, 3…),
  mesma convenção de `analytics/snapshot.py`. O snapshot mais alto é o jogo mais recente.
  **A narrativa de um snapshot é sobre AQUELE jogo** — não é um apanhado do torneio. Foque
  nele: o enredo, o que os dados revelam sobre por que terminou assim. Não repita entre
  snapshots contexto que não é daquele jogo (estado da tabela, ranking geral, tendências de
  outras seleções) — isso pertence a outra camada, não à leitura de um jogo.
- A narrativa de cada snapshot vive em
  `data/gold/analytics/insights/narrative/diagnostica/snapshot_{NNN}.md` (NNN com zero à
  esquerda, ex. `snapshot_054.md`). Arquivo escrito **só por você** — o Python nunca toca
  nessa pasta, então não há risco de sobrescrita pelo pipeline.
- A API (`GET /analytics/insights/narrative`) e a aba Analytics leem esse arquivo ao vivo.
  **Não precisa remontar nada** — escreveu, aparece.

## Passo 1 — Descobrir o snapshot a analisar

Se o usuário não disse qual, use o mais recente disponível:

```bash
# Windows: .venv\Scripts\python.exe   |   Linux/VM: .venv/bin/python
.venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_parquet('data/gold/analytics/insights/fact_insights.parquet')
print('snapshots com achados:', sorted(df['snapshot'].unique()))
print('mais recente:', int(df['snapshot'].max()))
"
```

## Passo 2 — Ler os achados estruturados (a base factual)

**Nunca invente.** A narrativa só pode citar achados e números que existem no
`fact_insights`. Leia os achados **do jogo daquele snapshot** — é só um jogo:

```bash
.venv/Scripts/python.exe -c "
import pandas as pd
N = <SNAPSHOT>
ins = pd.read_parquet('data/gold/analytics/insights/fact_insights.parquet')
dim = pd.read_parquet('data/gold/dim_match.parquet')
g = ins[ins['snapshot'] == N]
mid = g['match_id'].iloc[0]
m = dim[dim['match_id'] == mid].iloc[0]
print(f\"=== {m['home_team']} {int(m['home_score'])}-{int(m['away_score'])} {m['away_team']} ({m['group']}, {m['stage']}) ===\")
for r in g.itertuples():
    print(f'  [{r.direcao}/{r.severidade}] {r.achado_key}: {r.detalhe}  | ev={r.evidencia}')
"
```

Os achados (resumo, resultado×xG, finalização, domínio territorial, goleiro, disciplina,
contexto de força do adversário) são a matéria-prima. Identifique qual deles é o eixo da
história daquele jogo — normalmente o que tem severidade mais alta ou que melhor explica o
placar.

## Passo 3 — (opcional) Continuidade que ilumina ESTE jogo

A memória pode "construir sobre si", mas sem desviar do jogo do snapshot. Use o passado só
quando ele afia a leitura de uma das **duas seleções em campo agora** — não para resumir o
torneio. Se um dos times jogou antes, vale espiar a leitura daquele jogo:

```bash
cat data/gold/analytics/insights/narrative/diagnostica/snapshot_<NN anterior>.md 2>/dev/null || echo "(sem narrativa anterior)"
```

Exemplo legítimo (continua sobre o jogo de hoje): *"o time que na estreia desperdiçou tudo o
que criou, hoje foi clínico"*. Exemplo a EVITAR (apanhado que se repete entre snapshots):
recapitular a tabela, o ranking geral ou tendências de seleções que não estão neste jogo. Na
dúvida, corte — é melhor focar no jogo do que encher de contexto repetido.

## Passo 4 — Escrever a leitura

Escreva a história **daquele jogo** em prosa real, **2 a 3 parágrafos curtos**, seguindo:

- **Foco total no jogo do snapshot.** É um único jogo: conte por que terminou como terminou.
  O eixo é o achado principal (domínio estéril, finalização clínica, goleiro decisivo,
  resultado contra o xG…). Vá fundo nesse enredo em vez de espalhar para o torneio.
- **A prosa é o RELATO, não um inventário.** A aba já mostra, em blocos próprios, os
  destaques e pontos fracos por seleção e o comparativo de números. A narrativa NÃO deve
  repetir isso em forma de lista ("destaques: …; pontos fracos: …"). É o texto jornalístico
  que costura o arco do jogo: como começou, o momento que virou, o que de fato decidiu — no
  tom de um match report dos grandes veículos.
- **Nada de contexto que se repete entre snapshots.** Sem estado da tabela, ranking geral ou
  tendências de outras seleções. Se não é sobre uma das duas seleções deste jogo, não entra.
- **Cite com precisão, sem inventar.** Todo número (xG, controle, defesas, cartões) vem do
  Passo 2, e é daquele jogo. Nomes de seleções como no gold. Nada de estatística inventada.
- **Honestidade sobre incerteza.** Em jogo isolado, evite cravar tendência ("vai", "sempre");
  descreva o que ESTE jogo mostrou.
- **Cada jogo lê diferente.** Varie o ângulo de abertura conforme a história do jogo (o lance
  que decidiu, a estatística que contraria o placar, o personagem central). Não reuse a
  mesma fórmula de um snapshot para o outro.
- Sem listas de bullets. Sem adjetivo vazio sem fato que o sustente.

## Passo 5 — Gravar o arquivo

Escreva em `data/gold/analytics/insights/narrative/diagnostica/snapshot_{NNN}.md`
(NNN com 3 dígitos), **incluindo o marcador na primeira linha**:

```markdown
<!-- analise-manual -->
<parágrafo 1>

<parágrafo 2>

<parágrafo 3>
```

O marcador `<!-- analise-manual -->` na primeira linha sinaliza que é texto curado por você
(a API o remove ao servir). Crie a pasta se não existir. Não há etapa de remontagem — a aba
Analytics passa a exibir a leitura assim que o arquivo existe.

## Passo 6 — Resumo final

Ao terminar, diga em 1 linha por snapshot analisado: `snapshot N — jogo — uma frase do que a
leitura destacou`. Não cole a narrativa inteira no chat.

## Regras

- **Foco no jogo do snapshot.** Cada snapshot é um único jogo; a leitura é sobre ele. Não
  encha de contexto de torneio (tabela, ranking, outras seleções) que se repetiria entre
  snapshots — isso é o erro a evitar.
- **Nunca invente dados.** Só achados e números do `fact_insights` daquele jogo. Se faltar
  base para uma afirmação, não a faça.
- Sempre inclua `<!-- analise-manual -->` na primeira linha do arquivo.
- Continuidade é bem-vinda só quando afia a leitura de uma das duas seleções em campo (Passo
  3) — nunca às custas do foco no jogo.
- Esta skill é só leitura do gold + escrita da prosa — **não rode `fifa-coletar`** (isso é
  coleta de dados, decisão do usuário). Se os achados parecerem desatualizados, avise o
  usuário em vez de coletar por conta própria.
