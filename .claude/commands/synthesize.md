# Skill: /synthesize

Analisa o vault e identifica oportunidades de síntese entre notas existentes, criando notas do tipo `permanent`.

## O que é uma nota permanent

Uma nota permanent sintetiza **múltiplas notas** (PICs, fleetings, literature, outras permanentes) em um argumento intelectual desenvolvido. Não é resumo — é construção de conhecimento: o usuário sai da informação isolada e chega a uma posição própria, sustentada por evidências e raciocínio.

## Níveis de síntese

Toda permanent deve declarar `synthesis-level:` no frontmatter. O nível também define o destino físico dentro de `vault/Knowledge/Permanent/`, sem mudar a função intelectual da nota.

| Nível | Valor | Função | Fontes típicas |
|---|---|---|---|
| Síntese de cluster | `cluster` | Consolida um MOC, tag dominante ou conjunto local de PICs | PICs + Literature do cluster |
| Síntese de ponte | `bridge` | Conecta dois ou mais clusters já estabilizados | Permanents de cluster + PICs de apoio |
| Síntese arquitetural | `architectural` | Reorganiza vários clusters/bridges em uma tese estrutural maior | Permanents + Principles/Tensions quando existirem |

Use `cluster` quando a tese nasce dentro de um tema. Use `bridge` quando a tese só aparece ao cruzar temas diferentes. Use `architectural` quando a nota muda o mapa de compreensão do domínio inteiro.

Destino físico:

- `cluster` → `vault/Knowledge/Permanent/Cluster/<domínio>/Permanent — <título>.md`
- `bridge` → `vault/Knowledge/Permanent/Bridge/<domínio>/Permanent — <título>.md`
- `architectural` → `vault/Knowledge/Permanent/Architectural/<domínio>/Permanent — <título>.md`

Para todos os níveis, escolha `<domínio>` pelo MOC principal, eixo dominante da tese ou fontes dominantes: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`. Em `bridge` e `architectural`, use o domínio dominante mesmo quando a tese tocar vários domínios.

Se a síntese pertencer a uma linha de pensamento durável que não cabe nos domínios vigentes, proponha ou crie o novo domínio físico antes de salvar a permanent. Exemplo: uma trilha consistente de finanças deve ir para `Finanças`, com o mesmo domínio disponível em `Capture/Fleeting`, `Archive`, `Literature`, `PIC`, `Permanent/Cluster`, `Permanent/Bridge` e `Permanent/Architectural` conforme o material existir.

## Estágios de síntese

Toda permanent também deve declarar `synthesis-stage:` no frontmatter. O estágio registra a posição epistemológica da tese dentro de uma trilha de maturação.

| Estágio | Valor | Função | Quando usar |
|---|---|---|---|
| Síntese base | `base` | Primeira tese construída a partir do material ingerido | Após `/ingest` e PICs de um cluster |
| Síntese tensionada | `tensioned` | Nova tese construída após limitações, radar, tensions, handoffs ou novas fontes | Quando a permanent base gerou investigação crítica |
| Síntese comparativa | `comparative` | Tese que compara sínteses base/tensioned ou múltiplas trilhas | Quando há duas ou mais versões/trilhas a contrastar |

`synthesis-level` e `synthesis-stage` são independentes. Uma nota pode ser `cluster/base`, `cluster/tensioned`, `bridge/comparative` ou `architectural/comparative`.

Uma permanent base não deve ser sobrescrita por uma síntese tensionada. Preserve a base como camada histórica e crie nova permanent quando a investigação a partir das limitações produzir tese substantivamente nova.

**O que diferencia uma permanent medíocre de uma boa:**
- Medíocre: reformula o que os PICs já dizem, em prosa um pouco mais longa
- Boa: usa os PICs como degraus para um argumento que vai além deles — questiona, contrasta, situa em debate mais amplo, abre implicações
- Medíocre: cada seção é um mini-ensaio independente; o leitor não sabe por que está lendo a seção B depois da A
- Boa: a tese atravessa o texto inteiro — cada seção empurra a próxima, e o argumento ao final é mais forte do que no início

**Elementos obrigatórios de uma nota permanent de qualidade:**
- **Tese autoral**: uma posição defendível, não apenas uma descrição
- **Desenvolvimento em prosa densa**: argumento estruturado, com tensões, contra-argumentos e resolução
- **Fontes externas**: autores, obras, pesquisas ou dados fora do vault — citar pelo menos 2–3 referências externas relevantes
- **Comparativo**: tabela quando houver conceitos paralelos, mas só se revelar algo que prosa não revelaria
- **Limitações** (obrigatória): onde a tese encontra resistência — casos que não se aplicam, condições que a quebram, evidências contrárias conhecidas
- **Conexões vivas**: links para notas do vault que expandem ou contestam pontos específicos do argumento

## Uso

```
/synthesize [--scan | --tensioned | --compare | --bridges | --architecture | --draft "<tema>"]
```

- `--scan` — analisa o vault e sugere oportunidades de síntese de cluster/base
- `--tensioned` — sugere novas sínteses a partir de uma permanent base, suas limitações, tensions, research/handoffs e fontes novas
- `--compare` — compara duas ou mais sínteses de uma mesma trilha ou de trilhas relacionadas para propor uma síntese comparativa
- `--bridges` — analisa permanents e MOCs existentes para sugerir sínteses entre clusters
- `--architecture` — analisa permanents de cluster/ponte para sugerir sínteses estruturais maiores
- `--draft "<tema>"` — drafta uma nota permanent sobre um tema específico, buscando notas relacionadas e escolhendo `synthesis-level` e `synthesis-stage`
- Sem flag — executa `--scan` por padrão

## Comportamento: --scan

1. Use Grep por `type: pic` em `vault/indexes/` — extrai todos os PICs com suas tags em uma operação (busca nos arquivos INDEX-PIC-<domínio>.md)
2. Agrupe os PICs por tags compartilhadas — cada grupo de 3+ notas com a mesma tag é um cluster candidato. Não leia o conteúdo completo nesta etapa.
3. Para cada cluster, use Grep por `type: pattern` em `vault/indexes/INDEX-Pattern.md` com as mesmas tags — adicione os Patterns encontrados ao cluster como evidência aplicada.
4. Para cada cluster, use Grep recursivo pela tag dominante em `vault/Knowledge/Permanent/` para verificar se já existe uma permanent `synthesis-level: cluster` cobrindo o tema. Se existir, leia apenas seu frontmatter + `## Tese` + `## Limitações` para verificar se o terreno está coberto ou se há ângulo novo.
5. Para cada cluster, use Grep por `type: tension` em `vault/indexes/INDEX-Tension.md` com as mesmas tags — identifique Tensions que já desafiam o tema; elas afetam o `synthesis-stage` (se há tension relevante, a síntese provavelmente nasce como `tensioned`, não `base`).
6. Para cada cluster, calcule um "potencial de síntese":
   - Alto: 3+ PICs com tema bem definido, sem permanent já existente sobre o tema
   - Médio: 2 PICs relacionados, tema parcialmente coberto por permanent existente mas com ângulo novo
7. Apresente os clusters encontrados no formato abaixo e pergunte qual o usuário quer sintetizar

### Formato do relatório --scan

```
## Oportunidades de síntese

### 1. <tema identificado> — potencial: alto/médio
PICs envolvidos:
- [[<PIC 1>]] — <ideia central em meia linha>
- [[<PIC 2>]] — <ideia central em meia linha>
Patterns do cluster:
- [[<Pattern 1>]] — <o que implementa> (ou "nenhum")
Permanent adjacente: [[<Permanent existente>]] — <o que já cobre> (ou "nenhuma")
Tensions relevantes: [[<Tension>]] — <objeção> (ou "nenhuma")
Sugestão de título: "Permanent — <título da nota permanent>"
Nível: `cluster`
Estágio: `base` ou `tensioned` (se houver tension relevante)

### 2. ...

Qual você quer sintetizar? (número ou "nenhum")
```

## Comportamento: --tensioned

1. Leia `vault/Navigation/MOC/MOC — Permanentes.md` e liste permanents `synthesis-stage: base`.
2. Para cada base candidata, leia:
   - frontmatter;
   - `## Tese`;
   - `## Limitações`;
   - `## Conexões vivas`;
   - `## Relações qualificadas`, se existir.
3. Busque material crítico ligado à base:
   - busca recursiva em `vault/Knowledge/Tension/` com `affects:` apontando para a permanent;
   - busca recursiva em `vault/Knowledge/Research/Active/` e `Resolved/` que cite a permanent ou suas limitações;
   - busca recursiva em `vault/Knowledge/Handoffs/Active/` e `Completed/` que cite a permanent, radar ou tensão;
   - Literature/PICs criados depois da permanent e relacionados às suas tags, fontes ou limitações.
4. Identifique trilhas tensionadas. Uma mesma permanent base pode gerar várias trilhas, por exemplo:
   - limitação técnica;
   - limitação social;
   - limitação de escala;
   - limitação de governança;
   - limitação de representação;
   - limitação de contexto prático.
5. Só proponha uma síntese tensionada quando houver tese nova, não apenas uma seção de limitações melhor.
6. Apresente oportunidades no formato:

```
## Oportunidades de síntese tensionada

### 1. <trilha crítica> — potencial: alto/médio
Permanent base:
- [[Permanent — A]] — <tese base>

Material crítico:
- [[Tension — X]] — <objeção>
- [[Radar — Y]] ou [[Handoff — Z]] — <fonte externa ou pergunta>
- [[PIC — N]] — <novo conceito, se houver>

Limitação de origem: <limitação que abriu a trilha>
Tese tensionada provável: <1 frase>
Sugestão de título: "Permanent — <título>"
Nível: `cluster` ou `bridge`
Estágio: `tensioned`
```

7. Se houver limitação promissora sem research/tension suficiente, não force permanent. Recomende `/radar --from-limitations` ou `/tension`.

## Comportamento: --compare

1. Receba explicitamente ou detecte um conjunto de permanents comparáveis:
   - uma `base` e uma ou mais `tensioned` do mesmo tema;
   - várias `tensioned` derivadas da mesma base;
   - duas trilhas amadurecidas que tratam o mesmo problema por ângulos diferentes.
2. Leia as permanents comparadas integralmente.
3. Leia tensions, research/handoffs e PICs que estejam em `sources:` ou `Conexões vivas` dessas permanents.
4. Compare em seis eixos:
   - o que a base enxergava;
   - o que a tensão revelou;
   - o que permanece válido;
   - o que foi limitado ou contradito;
   - que tese nova aparece apenas na comparação;
   - que bridge ou arquitetura essa comparação pode sustentar.
5. Apresente oportunidades no formato:

```
## Oportunidades de síntese comparativa

### 1. <comparação> — potencial: alto/médio
Sínteses comparadas:
- [[Permanent — A]] `base` — <papel>
- [[Permanent — B]] `tensioned` — <papel>
- [[Permanent — C]] `tensioned` — <papel, se houver>

Contraste central: <diferença que importa>
Tese comparativa provável: <1 frase>
Sugestão de título: "Permanent — <título>"
Nível: `bridge` ou `architectural`
Estágio: `comparative`
```

## Comportamento: --bridges

1. Leia `vault/Navigation/MOC/MOC — Permanentes.md` e liste permanents existentes por `synthesis-level`.
2. Leia os MOCs de conteúdo em `vault/Navigation/MOC/Conteúdo/` para identificar conexões explícitas entre clusters.
3. Leia o frontmatter e as seções `## Tese`, `## Limitações` e `## Conexões vivas` das permanents candidatas.
4. Procure oportunidades de ponte usando estes sinais:
   - uma permanent cita outra em `## Conexões vivas`;
   - dois MOCs de conteúdo se referenciam mutuamente;
   - duas permanents compartilham tags, mas defendem teses em camadas diferentes;
   - a limitação de uma permanent é resolvida ou aprofundada por outra;
   - existe uma pergunta que só pode ser respondida cruzando os clusters.
5. Não proponha ponte fraca. Uma ponte precisa ter uma tensão ou ganho claro: mediação, dependência, inversão, escala, governança, materialização, abstração, risco, contexto ou decisão.
6. Apresente oportunidades no formato:

```
## Oportunidades de síntese de ponte

### 1. <relação entre clusters> — potencial: alto/médio
Permanents envolvidas:
- [[Permanent — A]] — <papel na ponte>
- [[Permanent — B]] — <papel na ponte>

Pergunta de ponte: <pergunta que só aparece ao cruzar os clusters>
Tese provável: <1 frase>
Sugestão de título: "Permanent — <título>"
Nível: `bridge`
Estágio: `comparative`
```

## Comportamento: --architecture

1. Leia todas as permanents com `synthesis-level: cluster` e `synthesis-level: bridge`.
2. Leia `MOC — Permanentes`, `MOC — Princípios`, `MOC — Tensões` e MOCs de conteúdo relevantes.
3. Só proponha síntese arquitetural quando houver base suficiente:
   - 4+ permanents de cluster relacionadas; ou
   - 2+ permanents de ponte; ou
   - uma tensão recorrente atravessando vários clusters.
4. Procure uma tese que reorganize o domínio inteiro, não apenas conecte dois temas. A síntese arquitetural deve dizer algo sobre o sistema de conhecimento como um todo.
5. Apresente oportunidades no formato:

```
## Oportunidades de síntese arquitetural

### 1. <tema estrutural> — potencial: alto/médio
Permanents envolvidas:
- [[Permanent — A]] — <função na arquitetura>
- [[Permanent — B]] — <função na arquitetura>
- [[Permanent — C]] — <função na arquitetura>

Problema estrutural: <qual problema maior a tese resolve>
Tese provável: <1 frase>
Sugestão de título: "Permanent — <título>"
Nível: `architectural`
Estágio: `comparative`
```

## Comportamento: --draft

1. Receba o tema (via flag ou escolha do usuário após `--scan`, `--tensioned`, `--compare`, `--bridges` ou `--architecture`).
2. Determine o `synthesis-level` antes de escrever:
   - `cluster` se as fontes principais forem PICs de um único MOC/tag;
   - `bridge` se as fontes principais forem permanents de clusters diferentes;
   - `architectural` se a tese reorganizar várias permanents/bridges.
3. Determine o `synthesis-stage` antes de escrever:
   - `base` se é a primeira síntese a partir do material ingerido;
   - `tensioned` se nasce de limitações, radar, handoffs, tensions ou novas fontes críticas;
   - `comparative` se compara duas ou mais sínteses já existentes.
4. Reúna as fontes de análise antes de escrever:
   - **Para `cluster/base`**: verifique primeiro se existe `Tópico — <tema>` em `vault/Navigation/Tópicos/` com `coverage: em-estudo` ou `dominado` — se existir, leia-o integralmente como primeira fonte: ele já contém a sequência de PICs organizada e uma Essência que pode servir de rascunho para a tese. Depois leia as primeiras 25 linhas de cada PIC do cluster; leia integralmente os Patterns com as mesmas tags; leia frontmatter + `## Tese` + `## Limitações` de qualquer Permanent existente no mesmo domínio que compartilhe tags; verifique Tensions com as mesmas tags.
   - **Para `tensioned`, `bridge`, `architectural` e `comparative`**: leia integralmente as permanents envolvidas; depois leia PICs, Patterns, tensions e handoffs como apoio.
5. **Produza o outline antes de escrever** — este passo tem saída obrigatória e verificável:

   **a. Espinha do argumento** (responda primeiro, é o mais crítico): liste em sequência o que cada seção vai afirmar e como empurra a próxima. Se não conseguir traçar essa sequência, a nota vai sair como lista de tópicos disfarçada de prosa.

   **Âncora de volume:** uma permanent de cluster típica tem 4–6 seções de desenvolvimento. Menos de 3 indica agrupamento excessivo; mais de 7 indica que o tema precisa ser dividido em duas permanents.

   **b. Complete antes de escrever:**
   - Qual tensão intelectual atravessa o cluster?
   - Se for `tensioned`: qual limitação da base gerou esta trilha e o que a investigação crítica mudou?
   - Se for `comparative`: o que a comparação revela que nenhuma síntese isolada revelava?
   - Se for `bridge`: qual relação entre clusters não aparece dentro de nenhum cluster isolado?
   - Se for `architectural`: qual estrutura maior a tese reorganiza?
   - Que autores ou pesquisas externas são relevantes? (trazer pelo menos 2–3)
   - Qual é a tese que o usuário poderia defender, apoiado nas notas + fontes externas?

   Em modo `--review`: apresente o outline (tese em 1 frase + sequência de seções com o que cada uma afirma) e aguarde aprovação antes de redigir o rascunho completo.
   Em modo `--auto` (via `--draft` direto): prossiga para o rascunho após completar o outline.
6. Construa o rascunho da nota permanent:
   - **Tese**: 1–2 frases defendendo uma posição — não descrevendo um tema
   - **Desenvolvimento**: argumento em prosa densa onde cada seção empurra a próxima
   - **Comparativo** (quando revelar algo que prosa não revelaria): tabela com conceitos paralelos
   - **Limitações** (obrigatória): onde a tese encontra resistência ou casos que o desafiam
   - **Referências externas**: autores e obras situados no argumento (não em lista solta no fim)
   - **Conexões vivas**: links para notas do vault que expandem pontos específicos
7. O rascunho deve ter densidade intelectual — um leitor externo sem acesso ao vault deve conseguir seguir o argumento.
8. Mostre o rascunho completo e aguarde aprovação.
9. Após aprovação, salve no destino físico definido por `synthesis-level` e domínio: `Cluster/<domínio>/`, `Bridge/<domínio>/` ou `Architectural/<domínio>/`, com `status: em-formação`, `synthesis-level: <cluster|bridge|architectural>` e `synthesis-stage: <base|tensioned|comparative>`.
10. Atualize `vault/Navigation/MOC/MOC — Permanentes.md`:
   - Determine a seção pelo nível: `## Permanents de Cluster`, `## Permanents de Ponte` ou `## Permanents Arquiteturais`
   - Dentro da seção, localize o subgrupo `### <domínio>` correto. O domínio de MOC segue o domínio físico da permanent, com uma exceção: permanents em `Sistemas de Informação/` com tema de dados, análise, ML ou visualização vão em `### Dados e Análise`; as de teoria de SI/TI vão em `### Sistemas de Informação`
   - Domínios disponíveis: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Dados e Análise`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`
   - Se o `### <domínio>` não existir ainda na seção, crie-o ao final dela
   - Adicione a entrada no formato: `- [[Permanent — <título>]] \`<status>\` \`<stage>\` — <descrição em meia linha>`
10b. Atualize o MOC de conteúdo do domínio (`vault/Navigation/MOC/Conteúdo/<domínio>/MOC — <domínio>.md`):
   - Se já existir uma seção `## Sínteses`, adicione a entrada lá.
   - Se não existir, crie a seção `## Sínteses` logo antes de `## Fontes` (ou no fim do arquivo se não houver `## Fontes`).
   - Formato da entrada: `- [[Permanent — <título>]] \`<stage>\` — <descrição em meia linha da tese>`
   - Para permanents de `bridge` ou `architectural` com domínios múltiplos, adicione ao MOC do domínio dominante.
11. Use marcador inline de estágio após o status, quando útil: `` `base` ``, `` `tensioned` `` ou `` `comparative` ``.
12. O hook atualiza `vault/indexes/` automaticamente ao salvar — nenhuma ação manual necessária.
13. Não inicie `/reflect` automaticamente. Ao final, sugira o próximo movimento adequado:
   - após `base`: `/review --limitations`;
   - após limitações maduras: `/radar --from-limitations`;
   - após tensions/research/fontes novas: `/synthesize --tensioned`;
   - após várias sínteses da mesma trilha: `/synthesize --compare`;
   - após `comparative`: `/synthesize --bridges` ou `/synthesize --architecture`, conforme o alcance;
   - após qualquer permanent: `/reflect --principle` quando o usuário quiser desdobrar convicções.

> Formato completo em `.claude/commands/note-formats.md` — seção **Permanent**.

## Frontmatter obrigatório

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: permanent
title: Permanent — <título>
created: <data YYYY-MM-DD>
tags: [<tags herdadas do cluster>]
sources: [[[<nota 1>]], [[<nota 2>]], ...]
synthesis-level: cluster | bridge | architectural
synthesis-stage: base | tensioned | comparative
status: em-formação
---
```

## Regras

- Título: `Permanent — <título nominal, curto, em português>`
- O campo `sources` lista todas as notas que alimentaram a síntese
- O campo `synthesis-level` é obrigatório em permanents novas
- O campo `synthesis-stage` é obrigatório em permanents novas
- Uma permanent `tensioned` deve apontar em `sources:` para a permanent base e para tensions, handoffs, literature ou PICs que sustentam a mudança
- Uma permanent `comparative` deve apontar em `sources:` para as permanents comparadas
- Nunca crie uma nota permanent se já existir uma cobrindo o mesmo tema — sugira expandir a existente
- Nunca crie uma permanent de ponte se ela apenas resumir duas permanents; ela precisa produzir uma tese nova a partir da relação entre elas
- Nunca crie uma permanent arquitetural se ela for só uma ponte ampliada; ela precisa reorganizar uma parte significativa do mapa
- Se o cluster for muito amplo, proponha dividir em duas permanentes menores
- `## Limitações` é obrigatória — não omitir mesmo que a tese pareça sólida
- O id é gerado com o timestamp do momento da criação (use a data/hora atual)
