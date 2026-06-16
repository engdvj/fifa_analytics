# Skill: /pattern

Cria uma nota `pattern` a partir de PIC existente, trecho de código ou conteúdo descritivo. Patterns são prescrições técnicas reutilizáveis — diferente do PIC (que descreve *o que algo é*), o Pattern codifica *como fazer*, com código ou pseudo-código como conteúdo central.

## Uso

```
/pattern [--from-pic "<título completo do PIC>"] [--scan]
```

- Sem flag — recebe qualquer entrada (código de aplicação, snippet, arquivo, descrição) e identifica/propõe Patterns
- `--from-pic "<título>"` — promove PIC existente: lê o PIC e transforma em Pattern quando o conteúdo for prescritivo
- `--scan` — varre PICs do vault identificando candidatos a Pattern ainda não criados

## Entradas aceitas (sem flag)

O skill aceita qualquer forma de código ou descrição — não é restrito a notebooks:

- **Snippet colado**: trecho de código de qualquer linguagem
- **Arquivo de aplicação**: código de produção, script, módulo, query SQL, pipeline
- **Descrição textual**: "quero criar um padrão para X"
- **Referência a situação**: "no projeto Y usamos esse approach para Z"

Linguagem é **auto-detectada** pelo conteúdo — não precisa declarar. O campo `language:` no frontmatter é preenchido automaticamente (`python`, `javascript`, `typescript`, `sql`, `bash`, `go`, `java`, `pseudo`, `agnostic`, etc.).

## Comportamento padrão (sem flag)

1. Receba a entrada do usuário (qualquer forma acima)
2. **Se a entrada for código de aplicação** (múltiplas funções, classes, módulos): analise o código inteiro buscando padrões recorrentes — não trate o arquivo como um único Pattern, mas extraia cada padrão distinto identificado
3. Aplique o filtro de Pattern (abaixo) — só prossiga se o conteúdo for genuinamente prescritivo
4. Para cada candidato, verifique em `vault/indexes/INDEX-Pattern.md` se já existe Pattern com título idêntico ou semanticamente similar:
   - **Sem similar** → crie normalmente (se critérios claros) ou proponha e aguarde aprovação
   - **Similar encontrado** → leia o arquivo existente e avalie o que o novo conteúdo acrescenta:
     - Seção ausente (`## Quando NÃO usar`, `## Anti-padrão`) com conteúdo real
     - Exemplo de código mais claro, mais completo ou em variante técnica relevante
     - Nova condição em `## Quando usar` que amplia o escopo de aplicação
     - Nova conexão (PIC, Literature, Application ainda não listada)
     - Explicação de mecanismo mais precisa que substitui a atual
   - **Se há ganho** → proponha o complemento: mostre exatamente o que seria adicionado ou modificado, aguarde aprovação antes de editar o arquivo existente
   - **Se não há ganho** → informe "Pattern já cobre isso completamente" com uma linha explicando por quê, e avance para o próximo candidato
5. Se houver mais de um Pattern identificado, apresente a lista completa (novo vs. complemento vs. já coberto) antes de criar/editar em sequência
6. Após aprovação, salve ou edite no domínio correto

## Comportamento --from-pic

1. Leia o PIC indicado em `vault/Knowledge/PIC/<domínio>/`
2. Aplique o filtro de Pattern — se o conteúdo não for prescritivo + concreto, explique e pare
3. Verifique no INDEX se já existe Pattern cobrindo o mesmo conceito:
   - **Sem similar** → derive e proponha novo Pattern (passo 4)
   - **Similar encontrado** → leia o Pattern existente e compare com o PIC:
     - O PIC traz perspectiva, exemplo, condição ou conexão que o Pattern não tem?
     - Se sim → proponha complementar o Pattern existente com o que o PIC acrescenta
     - Se não → informe que o Pattern já cobre o conceito e encerre
4. Derive o Pattern (novo ou rascunho de complemento) a partir do PIC:
   - `## Problema` vem da pergunta P: reformulada como dor prática
   - `## Solução` vem da ideia I: convertida em código ou pseudo-código executável
   - `## Conexões` linkam de volta ao PIC de origem e à Literature source
5. Proponha o rascunho e aguarde aprovação antes de salvar ou editar

## Comportamento --scan

1. Leia todos os PICs em `vault/Knowledge/PIC/` (por domínio)
2. Para cada PIC, aplique o filtro de candidatura:
   - **Candidato forte**: título com verbo de ação técnica ("Converte", "Seleciona", "Encadeia", "Calcula", "Normaliza", "Filtra", "Agrupa") E I: descreve como fazer algo com código ou passos concretos
   - **Candidato médio**: I: contém nome de API, função ou biblioteca com descrição de uso ("usa `groupby`", "aplica `StandardScaler`", "chama `pivot_table`")
   - **Não candidato**: PIC puramente conceitual, definitório ou histórico (ex: "Machine Learning Aprende Padrões", "Álgebra Linear Expressa Modelos")
3. Para cada candidato forte ou médio, verifique no INDEX:
   - **Sem Pattern correspondente** → candidato a criação
   - **Pattern similar existe** → leia ambos e avalie se o PIC acrescenta algo concreto ao Pattern (seção ausente, variante técnica, condição nova). Se sim → candidato a complemento. Se não → excluir da lista.
4. Apresente o resultado agrupado por domínio, com coluna de ação:

```
## Candidatos a Pattern — /scan

### Sistemas de Informação (N itens)
- [[PIC — Título A]] → `Pattern — <título sugerido>` (forte) — **criar**
- [[PIC — Título B]] → `Pattern — <título existente>` (médio) — **complementar**: adicionar `## Quando NÃO usar`

### Software (N itens)
- [[PIC — Título C]] → `Pattern — <título sugerido>` (forte) — **criar**

Quer criar/complementar algum? Use `/pattern --from-pic "<título>"` ou me diga quais processar.
```

## Filtro de Pattern — critérios obrigatórios

Antes de propor qualquer Pattern, verifique os três critérios:

1. **Prescritivo**: o conteúdo diz *o que fazer*, não apenas *o que é*. Deve ser possível escrever "Quando X, faça Y usando Z."
2. **Concreto**: existe código, pseudo-código, fórmula ou sequência de passos como elemento central — não apenas descrição abstrata.
3. **Reutilizável**: o padrão se aplica em mais de um contexto. Uma solução específica para um projeto não é Pattern.

Se qualquer critério falhar, explique o motivo e sugira PIC ou Principle como destino alternativo.

## Frontmatter obrigatório

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: pattern
title: Pattern — <nome descritivo do padrão>
created: <YYYY-MM-DD>
tags: []
language: python|javascript|sql|bash|pseudo|agnostic
context: <onde se aplica — 1 linha>
domain: <domínio do vault>
status: rascunho|estável|superado
source: [[PIC ou Literature de origem]] # omitir se não houver
---
```

**Status:**
- `rascunho` — identificado mas não validado em uso real
- `estável` — confirmado por uso ou referência sólida
- `superado` — substituído por abordagem melhor — nunca deletar

## Corpo obrigatório

- `## Problema` — 2–4 frases: quando o padrão aparece, qual dor resolve
- `## Solução` — bloco de código ou pseudo-código como elemento central + explicação breve do mecanismo
- `## Quando usar` — condições ideais, 2–4 bullets
- `## Quando NÃO usar` (opcional) — mal-uso comum ou anti-condição relevante
- `## Anti-padrão` (opcional) — contra-exemplo de código quando torna o erro concreto
- `## Conexões` — links para PICs conceituais de base, Literature de origem, Applications onde foi testado

## Destino físico

`vault/Knowledge/Pattern/<domínio>/Pattern — <título>.md`

Domínio pelo MOC principal do conteúdo: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`.

Após salvar, verifique se o Pattern deve ser listado no `MOC — Padrões de Código` em `vault/Navigation/MOC/Conteúdo/Software/`.

## Vínculo bidirecional com a literature de origem

Toda vez que um Pattern for salvo com campo `source:` apontando para uma Literature, o **arquivo da literature deve ser atualizado** para incluir o pattern na seção `## Patterns gerados`.

**Procedimento:**

1. Identifique o arquivo da literature referenciada no `source:` do pattern.
2. Abra a literature e localize a seção `## Patterns gerados`:
   - **Seção existe** → adicione a entrada `- [[Pattern — <título>]]` no grupo temático mais adequado. Se não houver grupo temático óbvio, adicione ao fim da seção.
   - **Seção não existe** → crie-a imediatamente antes de `## MOC relacionado` (ou ao final do corpo se não houver MOC relacionado). Use agrupamentos temáticos (`### <tema>`) quando já houver 4+ patterns da mesma literatura.
3. Não duplique entradas — verifique se o pattern já está listado antes de adicionar.
4. Este passo é obrigatório para `source:` apontando para Literature. Para `source:` apontando para PIC, o vínculo via `## Conexões` no pattern já é suficiente.

## Gatilhos — quando criar um Pattern

| Gatilho | Como chegar aqui |
|---|---|
| Qualquer código colado | `/pattern` com o código — funciona com qualquer linguagem ou tipo de arquivo |
| Durante `/ingest` de notebook ou código | ingest cria automaticamente para candidatos fortes; lista sugestões para os incertos |
| De PIC existente | `/pattern --from-pic "<título>"` |
| Revisão periódica | `/pattern --scan` varre PICs e apresenta candidatos agrupados |
| Pós-Application | técnica usada em projeto real → atualizar `status: rascunho` → `estável` |
