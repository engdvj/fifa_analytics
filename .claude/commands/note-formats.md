# Formatos de nota — referência

Usado pelas skills ao redigir notas. Leia somente a seção relevante.

---

## Convenção global de nomes

Toda nota formal usa prefixo de tipo no `title:`, no filename e nos wikilinks. O formato é `Prefixo — <título nominal>`.

Prefixos:
- `Fleeting —`
- `Literature —`
- `PIC —`
- `Pattern —`
- `Permanent —`
- `Principle —`
- `Tension —`
- `Situation —`
- `Decision —`
- `Application —`
- `Brief —`
- `Project —`
- `MOC —`
- `Tópico —`

Research e Handoff mantêm os padrões operacionais próprios: `Radar — <tema>` e `Handoff — Radar <tema>`.

Destino físico para os tipos reorganizados:

- `Fleeting ativa`: `vault/Capture/Fleeting/<domínio>/Fleeting — <título>.md`
- `Fleeting arquivada`: `vault/Archive/<domínio>/Fleeting/Fleeting — <título>.md`
- `Literature`: `vault/Knowledge/Literature/<Tipo>/<domínio>/Literature — <título>.md` — Tipo é `Artigos|Livros|Notebooks` (por source-type). Para `source-type: course`, o caminho tem um nível extra de curso: `vault/Knowledge/Literature/Cursos/<curso>/<domínio>/Literature — <título>.md` (ex: `Cursos/Gran Pós-Graduação em Gestão Pública/Administração/`). Aula/matéria de um curso consolida na Literature-coleção do curso, não vira nota solta.
- `PIC`: `vault/Knowledge/PIC/<domínio>/PIC — <título>.md`
- `Pattern`: `vault/Knowledge/Pattern/<domínio>/Pattern — <título>.md`
- `Permanent cluster`: `vault/Knowledge/Permanent/Cluster/<domínio>/Permanent — <título>.md`
- `Permanent bridge`: `vault/Knowledge/Permanent/Bridge/<domínio>/Permanent — <título>.md`
- `Permanent architectural`: `vault/Knowledge/Permanent/Architectural/<domínio>/Permanent — <título>.md`
- `Principle`: `vault/Knowledge/Principle/<grupo>/Principle — <título>.md`
- `Tension`: `vault/Knowledge/Tension/<severity>/Tension — <título>.md`
- `Tópico`: `vault/Navigation/Tópicos/<domínio>/Tópico — <título>.md`

Domínios vigentes: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`.
Domínios são expansíveis: se uma nova linha de pensamento durável surgir, crie o novo diretório de domínio nos tipos organizados por domínio conforme necessário (`Capture/Fleeting`, `Archive`, `Literature`, `PIC`, `Permanent/Cluster`, `Permanent/Bridge` e `Permanent/Architectural`) e atualize as instruções centrais e o MOC de conteúdo. Exemplo: uma trilha real de finanças deve usar `Finanças` como domínio, não ser forçada para `Sistemas de Informação`.
Grupos vigentes para `Principle`: `Abstrações e Camadas`, `Tecnologia e Responsabilidade`, `Sistemas e Convenções`.
Severidades vigentes para `Tension`: `Estrutural`, `Moderada`, `Leve`.

---

## Literature

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: literature
title: Literature — <título da fonte>
created: <YYYY-MM-DD>
tags: []
source-type: book|article|video|course|podcast
role: foundation|frontier|evidence|tension|method|reference
status: unread|reading|done
ingest-flow: normal|radar
research: [[Radar — <tema>]] # obrigatório quando ingest-flow: radar; omitir quando normal
---
```

**Corpo:**
- `## Resumo` — resumo geral da fonte inteira.
- `## Sumário` — capítulos, aulas ou seções com link para o bruto arquivado quando houver, seguido de uma linha `Fonte:` com referência breve e caminho da coleção quando aplicável.
- `## Conteúdo ingerido` — cada capítulo, aula ou seção tem um resumo local curto e subtítulos `####` para agrupar PICs por tema.
- `## Sínteses geradas`, `## Patterns gerados`, `## MOC relacionado` e `## Referências citadas pela fonte` quando aplicável.
- `## Patterns gerados` lista, por agrupamento temático, todos os patterns derivados desta fonte — cada entrada no formato `- [[Pattern — <título>]]`. A seção é omitida quando não há patterns; obrigatória assim que ao menos um existir.
- `ingest-flow` separa fontes de ingestão direta (`normal`) de fontes promovidas a partir de Research/Handoff (`radar`). Quando for `radar`, preencha `research:` com o radar de origem.

## PIC

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: pic
title: PIC — <título nominal e atômico>
created: <YYYY-MM-DD>
tags: []
moc: [[MOC — <tema>]]
---
```

**Corpo:**
- **P:** pergunta autocontida que a ideia responde, sem depender de abrir a fonte original.
- **I:** ideia em densidade média, normalmente 2 frases ou 3 linhas, nas próprias palavras.
- **C:** conexões com títulos completos, incluindo prefixo.

---

## Pattern

**Função:** solução técnica reutilizável para um problema recorrente. Pattern é prescritivo e concreto — diferente do PIC (que descreve *o que algo é*) e do Principle (que abstrai uma regra transferível), o Pattern codifica *como fazer* com código ou pseudo-código como conteúdo de primeiro nível.

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: pattern
title: Pattern — <nome descritivo do padrão>
created: <YYYY-MM-DD>
tags: []
language: python|javascript|sql|bash|pseudo|agnostic
context: <onde se aplica — ex: "análise de dados tabulares", "pipelines ML">
domain: <domínio do vault>
status: rascunho|estável|superado
source: [[Literatura ou PIC de origem]] # omitir quando não houver
---
```

**Status possíveis:**
| Status | Significado |
|---|---|
| `rascunho` | Identificado mas ainda não validado em uso real |
| `estável` | Confirmado por uso real ou referência sólida |
| `superado` | Substituído por abordagem melhor — preservar como histórico |

**Corpo:**
- `## Problema`: quando este padrão aparece — contexto, sintoma ou força que o motiva. 2–4 frases.
- `## Solução`: o padrão em si — bloco de código ou pseudo-código como elemento central, seguido de explicação breve do mecanismo.
- `## Quando usar`: condições e contextos em que o padrão é a escolha certa.
- `## Quando NÃO usar` (opcional): mal-uso comum, anti-condições ou alternativas superiores em outros contextos.
- `## Anti-padrão` (opcional): o que evitar e por quê — com contra-exemplo de código quando útil.
- `## Conexões`: links para PICs conceituais de base, Literature de origem e Applications onde foi testado.

**Localização:** `vault/Knowledge/Pattern/<domínio>/Pattern — <título>.md`

---

## Permanent

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: permanent
title: Permanent — <título nominal, curto, em português>
created: <YYYY-MM-DD>
tags: [<tags herdadas do cluster>]
sources: [[[<nota 1>]], [[<nota 2>]], ...]
synthesis-level: cluster|bridge|architectural
synthesis-stage: base|tensioned|comparative
status: em-formação
---
```

**Campo `synthesis-level`:**
| Valor | Função |
|---|---|
| `cluster` | Sintetiza PICs e Literature dentro de um único MOC, tag dominante ou tema local |
| `bridge` | Conecta dois ou mais clusters, normalmente usando permanents existentes como fontes principais |
| `architectural` | Reorganiza várias permanents/bridges em uma tese estrutural sobre o domínio |

**Campo `synthesis-stage`:**
| Valor | Função |
|---|---|
| `base` | Primeira síntese gerada a partir de ingestão, PICs e MOC de origem |
| `tensioned` | Síntese nova gerada após limitações, radar, handoff, tensions ou fontes críticas |
| `comparative` | Síntese que compara uma base com uma ou mais tensioned, ou múltiplas trilhas maduras |

`synthesis-level` mede alcance; `synthesis-stage` mede maturidade da trilha. Não sobrescreva uma permanent `base` quando uma investigação crítica gerar tese nova: crie uma nova permanent `tensioned` e preserve a base como camada comparável.

**Corpo:**
- **Tese**: 1–2 frases defendendo uma posição — não descrevendo um tema
- **Desenvolvimento**: prosa densa onde cada seção empurra a próxima; a tese atravessa o texto inteiro, não só a abertura
- **Comparativo** (só se revelar algo que prosa não revelaria): tabela com conceitos paralelos
- **Limitações** (obrigatória): onde a tese encontra resistência — casos que não se aplicam, condições que a quebram, evidências contrárias conhecidas
- **Referências externas**: autores e obras situados no argumento (não lista solta no fim) — mínimo 2–3 referências externas relevantes
- **Conexões vivas**: links para notas do vault que expandem pontos específicos
- **Relações qualificadas** (opcional): só quando a função da conexão não for óbvia

---

## Principle

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: principle
title: Principle — <convicção como afirmação — curta, nominal>
created: <YYYY-MM-DD>
tags: []
sources: [[[permanent 1]], [[permanent 2]]]
confidence: alto|médio|baixo
status: em-formação
---
```

**Corpo** (máx. ~300 palavras — não argumenta, conclui):
- **Posição**: regra transferível em 1–2 frases, em terceira pessoa — afirmação defendível, não descrição
- **Fundamento**: por que a regra se sustenta — links diretos para permanentes que construíram esta convicção, em 2–4 frases
- **Limitações** (obrigatória): onde este princípio não se aplica, em que condições quebra, o que poderia fazer revisá-lo
- **Revisão** (obrigatória): quando e o que mudaria este princípio
- **Conexões**: [[decisões que aplicam este princípio]] + [[permanentes ou princípios relacionados]]

**Campo `confidence`:**
| Valor | Significado |
|---|---|
| `alto` | Testado empiricamente ou sustentado por múltiplas fontes convergentes |
| `médio` | Argumentado em permanentes mas ainda não testado na prática |
| `baixo` | Intuição ou hipótese — precisa de decisão e aplicação para ser validada |

---

## Decision

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: decision
title: Decision — <verbo + objeto — ex: "Adotar NoSQL para dados de comportamento">
created: <YYYY-MM-DD>
tags: []
context: <domínio ou área de aplicação>
status: ativa
principles: [[[principle 1]], [[principle 2]]]
---
```

**Status possíveis:** `ativa | aplicada | revisada | cancelada | superada`

**Corpo:**
- **Situação**: o que motivou esta decisão — contexto específico, não genérico
- **Opções consideradas**: Opção A — por que foi descartada; Opção B — por que foi descartada
- **Decisão**: o que foi escolhido e por quê, em 2–4 frases
- **Fundamento**: quais princípios ou permanentes sustentam esta escolha (links)
- **Resultado esperado**: como saberemos que funcionou — indicadores concretos ou eventos observáveis
- **Revisão** (obrigatória): data específica ou gatilho (ex: "após 3 meses de uso" ou "quando X mudar") + o que mudaria esta decisão
- **Conexões**: [[applications que testam esta decisão]]

---

## Application

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: application
title: Application — <o que foi aplicado e onde — ex: "Aplicação do princípio X no projeto Y">
created: <YYYY-MM-DD>
tags: []
status: explorando|ativa|concluída|abandonada
decision: [[decisão que originou esta aplicação]]
principle: [[princípio testado]] (opcional)
---
```

**Corpo:**
- **Contexto**: onde, quando e em que circunstâncias ocorreu ou poderia ocorrer
- **O que foi aplicado**: qual conhecimento, princípio ou decisão foi testado na prática
- **Resultado**: o que aconteceu — ou, se status=explorando, o que se espera que aconteça
- **Aprendizado**: o que isso ensinou; o que volta para o sistema → links para novos Fleetings ou indicação de revisão de princípio/decision
- **Conexões**: [[decisão que esta aplicação testa]] + [[permanentes confirmadas ou refutadas]]

---

## Tension

**Função:** objeção forte, reutilizável e auditável. Tension não é ressalva solta nem comentário dependente da nota afetada: ela desenvolve o argumento em texto próprio, mantém links para rastreabilidade e mostra qual tese resiste, por quê, qual impacto tem e como poderia ser resolvida.

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: tension
title: Tension — <título — preferencialmente "X Também Pode Ser Y" ou "Limite de Z em Contexto W">
created: <YYYY-MM-DD>
tags: []
affects:
  - "[[Nota A]]"
  - "[[Nota B]]"
origin: [[Permanent/Radar/Handoff de origem]]
severity: leve | moderada | estrutural
---
```

**Corpo:**
- `## Objeção`: a tensão em 1–2 frases autocontidas — descreve o problema sem exigir que a nota afetada seja aberta.
- `## Argumento`: por que a objeção é relevante — evidência, caso, mecanismo ou raciocínio suficiente para entender a tensão dentro da própria nota.
- `## Impacto`: como isso afeta cada nota em `affects:` — inclui links para rastreabilidade, mas explica o que muda sem depender da leitura externa.
- `## Resolução possível`: o que seria necessário para incorporar, testar ou superar a tensão.
- `## Limites desta tensão`: onde a própria objeção não se aplica ou fica fraca.
- `## Conexões`: links qualificados para as notas afetadas e, quando houver, fonte/evidência.

**Conexões:**
```markdown
- tensiona: [[Nota afetada]]
- fundamenta: [[Fonte ou evidência]]
- pode gerar: [[Decision ou Application]] (opcional)
```

**Regra de escrita:** evite abrir a nota com "A tese de que...". A `Tension` pode mencionar a tese afetada, mas deve primeiro apresentar o conflito conceitual, o mecanismo e a consequência. Links servem para rastrear origem e impacto; o argumento precisa ser legível sem abrir esses links.

**Após criar Tension:** atualizar `status:` de permanentes e princípios afetados para `tensionada`. Se a tension afetar uma decision, preservar o status operacional da decision e registrar o vínculo em `## Revisão` ou `## Relações qualificadas`.

---

## Status de maturidade

Aplica-se a `permanent`, `principle`, `decision`, `application` e `situation`.

| Status | Significado operacional |
|---|---|
| `em-formação` | criada, ainda não revisada criticamente |
| `estável` | argumento consolidado, sem tensões conhecidas abertas |
| `tensionada` | objeção relevante identificada — ver Tension vinculada ou seção Limitações |
| `testada` | passou por Application real; aprendizado incorporado na nota |
| `revisada` | reescrita após tensão ou Application revelou falha |
| `superada` | ideia descartada; nota preservada (histórico), excluída da navegação ativa |

---

## Tensão — três níveis

1. **Seção `## Limitações`** na própria nota — objeções internas, casos que resistem. Obrigatória em permanentes e princípios.
2. **Nota `Tension`** — quando a objeção for forte, reutilizável ou afetar várias notas. Muda `status:` da nota afetada para `tensionada`; em decision, preserva o status e registra vínculo em `## Revisão`.
3. **Revisão estrutural** — quando a tensão mudar a tese central; produz nova permanent com `status: revisada`.

---

## Seções obrigatórias — Permanent e Principle

**`## Limitações`** — onde a tese encontra resistência: casos que não se aplicam, condições que a quebram, evidências contrárias conhecidas. Obrigatória em toda nota `permanent` e `principle`.

**`## Relações qualificadas`** — opcional, apenas quando a função da conexão não for óbvia pelos links normais. Qualificadores disponíveis:

```markdown
## Relações qualificadas

- fundamenta: [[Nota A]]
- tensiona: [[Nota B]]
- aplica: [[Nota C]]
- contradiz: [[Nota D]]
- supera parcialmente: [[Nota E]]
- atualiza: [[Nota F]]
```

**`## Revisão`** — obrigatória em `principle` e `decision`:

```markdown
## Revisão

Quando revisar: [evento concreto ou data]
O que mudaria este princípio/decisão: [condição específica]
```

---

## Research operacional

**Função:** fila curta de fontes externas pendentes por radar/tema. Research não é nota substantiva nem relatório; é triagem acionável.

**Arquivo ativo:** `vault/Knowledge/Research/Active/Radar — <tema>.md`

**Corpo:**
```markdown
# Radar — <tema>

Origem: [[Nota, brief, projeto ou decisão que motivou o radar]]
Handoff: [[Handoff — Radar <tema>]] ou —
Status: pendente de decisão | em ingestão | resolvido | arquivado
Próximo gatilho: <YYYY-MM-DD ou evento>

## Escopo

<1 frase sobre a pergunta que este radar cobre.>

## Fontes pendentes

- **[Título](URL)** `role: <role>` `prioridade: alta|média|baixa` `destino: Literature|PIC|Tension|Application|referência` — afeta: [[Nota A]], [[Nota B]] — relação: confirma|expande|tensiona|contradiz|atualiza|operacionaliza — gatilho: <data ou evento> — decisão: <o que Claude precisa decidir>

## Relações

- handoff: [[Handoff — Radar <tema>]]
- moc: [[MOC — Research]]
```

**Regras:**
- Toda entrada precisa ter `role:`, `prioridade:`, `destino:`, notas afetadas, relação, gatilho e decisão pendente.
- A fila curta deve permitir priorização sem ler o handoff inteiro.
- Referências sem gatilho ficam no handoff, não em Research.
- Quando a fonte for ingerida, descartada ou revalidada, atualize a linha em vez de duplicar entrada.

---

## Handoff operacional

**Função:** pacote analítico completo Codex → Claude. Handoff preserva contexto, raciocínio, fontes secundárias e recomendação para integração intelectual posterior.

**Arquivo ativo:** `vault/Knowledge/Handoffs/Active/Handoff — Radar <tema>.md`

**Corpo:**
```markdown
# Handoff — Radar <tema>

> Pacote produzido por Codex para integração intelectual posterior por Claude.

## Estado do handoff

- Radar: [[Radar — <tema>]]
- Research: [[Radar — <tema>]]
- Origem: [[Nota, brief, projeto ou decisão]]
- Status: aberto | aguardando Claude | parcialmente ingerido | resolvido | arquivado
- Próximo gatilho: <YYYY-MM-DD ou evento>

## Pergunta de radar

<pergunta que orientou a busca>

## Síntese executiva

<síntese curta do que importa e da recomendação geral>

## Mapa de decisão

- Ingerir primeiro: <fonte(s) e motivo>
- Manter na fila: <fonte(s) e motivo>
- Apenas referência: <fonte(s) e motivo>
- Possível tensão: <fonte(s) e nota afetada>

## Fontes na fila

### Fonte 1

- Fonte: [Título](URL)
- Role: `foundation|frontier|evidence|tension|method|reference`
- Prioridade: alta|média|baixa
- Afeta: [[Nota]]
- Relação com o vault: confirma|expande|tensiona|contradiz|atualiza|operacionaliza
- Por que entra: <1-2 frases>
- Gatilho: <data ou evento>
- Destino provável: `Literature|PIC|Tension|Application|referência`
- Recomendação para Claude: <ação sugerida>
- Status na fila: registrado|não registrado|ingerido|descartado

## Referências preservadas

<fontes úteis sem gatilho suficiente para Research>

## Próxima ação sugerida para Claude

<ação única ou lista curta>
```

**Regras:**
- Handoff pode ser longo; Research deve continuar curto.
- Handoff pode preservar fonte secundária sem colocá-la na fila.
- Handoff não cria nota substantiva por si só.

---

## Tópico

**Função:** unidade de estudo curada por tema. Tópico organiza PICs, Patterns e Permanents em sequência de aprendizado — é a camada entre PIC (atômico) e Permanent (argumentativa). Não argumenta nem sintetiza tese; organiza o conhecimento existente para que o estudo seja progressivo e o Permanent possa ser redigido com clareza.

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: topic
title: Tópico — <nome do tópico>
created: <YYYY-MM-DD>
tags: [<tags herdadas do cluster de PICs>]
domain: <domínio>
moc: [[MOC — <domínio>]]
requer: [[[Tópico — X]]] # opcional — dependências de aprendizado; omitir quando não houver
coverage: rascunho
permanent: [[Permanent — título]] # omitir até existir; preencher quando a síntese for criada
---
```

**Campo `coverage`:**
| Valor | Significado operacional |
|---|---|
| `rascunho` | Tópico criado, sequência montada, mas conteúdo ainda não estudado sistematicamente |
| `em-estudo` | Em revisão ativa — retornando às notas com frequência |
| `dominado` | Essência escrita com confiança; sinal de prontidão para `/synthesize --draft` |

**Corpo:**
- `## Essência` — 3–5 linhas em prosa: o núcleo do tema, inteligível sem abrir as notas. Quem lê deve entender o que é o tema, por que importa e qual insight central ele carrega.
- `## Sequência de estudo` — lista numerada de PICs e Patterns em ordem de aprendizado (do mais fundamental ao mais aplicado), com uma linha por item explicando por que vem naquele momento.
- `## Sínteses` — Permanents do cluster com `synthesis-stage` inline; "nenhuma ainda" se não houver.
- `## Tensões abertas` — Tensions que desafiam o tema; "nenhuma mapeada" se não houver.
- `## Próximo passo` — quando `coverage: dominado`, aponta para `/synthesize --draft "<tema>"`.

**Localização:** `vault/Navigation/Tópicos/<domínio>/Tópico — <título>.md`

---

## Situation

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: situation
title: Situation — <problema ou situação>
created: <YYYY-MM-DD>
tags: []
status: ativa|latente|resolvida|arquivada
domain: <área ou organização>
origin: experiência|literatura|ambos
---
```

**Corpo:**
- `## O problema`
- `## O que está em jogo`
- `## Conexões`

---

## MOC

**Função:** mapa de navegação. MOC não argumenta, não sintetiza tese nova e não substitui nota substantiva. Ele mostra onde cada nota está no domínio ou no fluxo intelectual.

**Localização:**
- MOCs de conteúdo/domínio: `vault/Navigation/MOC/Conteúdo/MOC — <tema>.md`
- MOCs de fluxo/controle do vault: `vault/Navigation/MOC/MOC — <fluxo>.md`

**Frontmatter:**
```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: moc
title: MOC — <domínio ou fluxo>
created: <YYYY-MM-DD>
tags: [<tags do domínio>, MOC]
---
```

**Corpo:**
- **H1:** use só o nome do domínio ou fluxo, sem repetir `MOC —`.
- **Frase orientadora:** 1 frase dizendo o que o mapa cobre e qual é a função dele.
- **Seções:** `## <cluster>` por tema, domínio, maturidade, severidade, tipo de artefato ou etapa do fluxo. Escolha o agrupamento que torna a navegação mais útil.
- **Contexto da seção** (opcional): 1 linha antes da lista, como `Derivadas de [[Nota]]` ou `Destilados de [[Nota]]`.
- **Entradas:** uma nota por bullet, sempre no formato `- [[Nota]] — <função neste MOC>`.
- **Estado inline** (quando necessário): use marcador curto logo após o link, como `` `tensionada` `` ou `status: pendente de decisão`, antes da descrição.
- **Seções finais opcionais:** `## Fonte`, `## Critérios`, `## Regra` e `## Conexões`, apenas quando ajudam o uso do MOC.

**Regras:**
- Não usar tabela como estrutura principal do MOC; use bullets para preservar o padrão do vault.
- Não listar notas sem descrição funcional.
- Não misturar mapas de naturezas diferentes no mesmo MOC; crie outro MOC e conecte em `## Conexões`.
- Não transformar o MOC em relatório. Análise longa deve ficar na nota substantiva, radar ou handoff.
