# Skill: /ingest

Ingere conteúdo bruto (texto de aula, artigo, livro, anotações) e processa em notas do vault.

## Uso

```
/ingest [--review | --auto] [--redo] [--literature "<título>"]
```

- `--review` — Claude propõe o plano e aguarda aprovação antes de salvar
- `--auto` — Claude processa e salva direto, sem interrupção
- `--redo` — fonte já ingerida: re-processa com os padrões atuais, melhorando PICs existentes e identificando lacunas
- `--literature "<título>"` — **você define a Literature de destino**. A ingestão usa exatamente essa Literature (criando-a no destino físico correto se não existir, ou atualizando-a se existir), em vez de inferir/classificar o destino automaticamente. Evita classificação errada quando a fonte poderia cair em mais de uma coleção. Aceita o título com ou sem o prefixo `Literature —`.
- Sem flag — Claude pergunta qual modo usar

## Idioma — sempre pt-BR

Todo conteúdo gerado pela ingestão é escrito em **português do Brasil**, independentemente do idioma da fonte. Fontes em inglês (ou qualquer outro idioma) são **traduzidas para pt-BR** ao virar Literature, PIC, Pattern ou MOC — a fonte crua fica no idioma original (na Fleeting/Archive), mas as notas do vault são sempre em português.

- Traduza títulos, `P:`, `I:`, resumos e descrições para pt-BR natural — não deixe trechos em inglês no corpo das notas.
- Termos técnicos consagrados sem tradução corrente (ex.: *skip connection*, *encoder*, *backbone*, *transfer learning*, *overfitting*, *loss*) podem ser mantidos em inglês em itálico quando traduzir soaria artificial; explique o termo em português na primeira ocorrência. Nomes próprios de arquiteturas/métricas (U-Net, IoU, Dice, EfficientNet, YOLO) permanecem como são.
- Citações literais curtas da fonte, quando necessárias, podem ficar no original entre aspas com atribuição — mas o texto que as cerca é em pt-BR.

## Comportamento

1. Receba o conteúdo bruto
2. Delimite o tema da ingestão em uma frase curta: assunto principal, fonte e pergunta implícita.
3. **Verifique existência e compare antes de criar** — para cada conceito candidato a PIC, use Grep com uma palavra-chave do título em `vault/indexes/`. Nunca leia os arquivos inteiros no grep.
   - **Sem resultado**: crie o PIC normalmente.
   - **Com correspondência**: leia o PIC existente e compare com o conteúdo novo. Há três saídas possíveis:
     - **Complementa** (ângulo novo, detalhe ausente, conexão não mapeada): atualize `I:` incorporando apenas o que for genuinamente adicional. Limite: `I:` deve continuar com no máximo 4 linhas após a atualização. Se o acréscimo não couber sem inflar, não atualize `I:` — em vez disso, adicione o ponto como link qualificado em `C:` ou sinalize como candidato a PIC complementar.
     - **Melhora** (formulação mais precisa, argumento mais claro): substitua a parte fraca sem crescer o tamanho total. `I:` não pode ficar mais longa do que estava.
     - **Igual ou mais fraco**: pule sem nenhuma alteração.
   - `P:` e o título são a identidade do PIC — nunca os altere. `C:` pode sempre ganhar links novos quando há conexão identificada.
   - Nunca crie PIC duplicado para conceito já coberto. Atualize, adicione link em `C:`, ou sinalize lacuna — não duplique.
4. **Defina a Literature de destino.** Se o usuário passou `--literature "<título>"`, esse é o destino — pule a inferência (ver seção **Modo Literature dirigida** abaixo). Caso contrário, **identifique se a fonte já pertence a uma Literature existente** — antes de criar nova Literature ou arquivar a captura como `Archive/<domínio>/Fleeting`, busque por título da fonte, coleção, curso, autor, domínio e MOC relacionado em `vault/Knowledge/Literature/`. Se já houver uma Literature que representa a fonte maior, atualize essa Literature e arquive o bruto na pasta da coleção em `vault/Archive/<domínio>/<título da fonte>/`, seguindo o padrão já existente. Use `Archive/<domínio>/Fleeting` apenas para capturas avulsas que não pertencem a uma fonte ou coleção já consolidada.
5. **Consulte contexto relacionado sem varrer o vault inteiro**:
   - Busque em `vault/Knowledge/Research/Active/` e, se necessário, `Resolved/` por `Radar — *.md` relacionado ao tema, título da fonte ou palavras-chave centrais.
   - Busque em `vault/Knowledge/Handoffs/Active/` e, se necessário, `Completed/` por handoff relacionado ao mesmo tema.
   - Se houver `Situation` explicitamente indicada pelo usuário, ou uma situação claramente relacionada nos índices em `vault/indexes/`/`MOC — Situações`, leia essa nota.
   - Trate Research, Handoff e Situation como contexto auxiliar: eles informam `role`, conexões, lacunas e pendências, mas não mudam o objeto principal da ingestão.
6. **Enumere todos os conceitos em bruto — sem filtrar ainda** — leia o conteúdo completo e liste cada conceito com nome próprio, modelo, framework, taxonomia, mecanismo ou princípio que apareça. Liste por ideia candidata, não por seção do texto. Não descarte nada nesta fase.

   **Âncora de volume:** uma fonte de 45–60 min ou 20–30 páginas tipicamente gera entre 6–15 candidatos brutos. Se você listou menos de 4, releia o conteúdo — provavelmente agrupou indevidamente.

   **Cobertura de estruturas enumerativas:** se a fonte apresentar lista de erros, passos, pilares, critérios, fases, checklist, framework ou componentes numerados, cada item entra na lista bruta individualmente — não funda nem resuma nesta fase. (Ver **Regra de cobertura estrutural** abaixo para instruções de criação.)

7. **Curadoria — filtre a lista bruta** — aplique o gate de qualidade (seção **Qualidade dos PICs gerados** abaixo) a cada candidato enumerado no passo anterior:
   - **Criar PIC** — o conceito expressa ideia reutilizável com insight não-óbvio ainda não coberto no vault.
   - **Incorporar em outro PIC** — é nomenclatura, definição de ferramenta ou etapa de processo sem insight próprio; adicione como contexto no `I:` do PIC mais central.
   - **Registrar só na Literature** — é detalhe contextual, exemplo ou repetição de ideia já coberta.
   Confirme via Grep em `vault/indexes/` antes de criar qualquer PIC — nunca duplique conceito já existente.

8. Identifique:
   - **Fonte** — título, tipo (book/article/video/podcast/class), URL ou referência
   - **Role da fonte** — classifique: `foundation` (base conceitual) | `frontier` (pesquisa recente/emergente) | `evidence` (evidência empírica) | `tension` (limita ou contradiz tese existente) | `method` (método de investigação) | `reference` (consulta ou consolidação)
   - **Conexões** — PICs, MOCs, Research, Handoffs ou Situations existentes que se relacionam diretamente
   - **Pendências externas** — se a fonte resolve, confirma ou deixa aberta alguma entrada de Research/Handoff relacionada
   - **Situação de origem** — se a fonte veio de uma Situation, Brief ou Project, registre se ela é apenas referência do caso ou se traz conceito/método/evidência reutilizável.
9. Decida quais notas criar:
   - Uma nota `literature` para a fonte (se ainda não existir), nomeada `Literature — <título da fonte>` — incluir campo `role:` com a classificação identificada e `ingest-flow: normal|radar`
   - Um PIC por conceito aprovado na curadoria (Passo 7), nomeado `PIC — <título do conceito>`
   - Um MOC de conteúdo em `vault/Navigation/MOC/Conteúdo/MOC — <tema>.md` quando houver 3 ou mais PICs do mesmo tema
   - **Patterns**: quando a fonte for notebook, código ou método técnico (`source-type: notebook` ou `role: method`), identifique PICs recém-criados que atendam aos três critérios simultâneos: (1) **prescritivo** — diz *o que fazer*, não apenas *o que é*; (2) **concreto** — existe código, API ou sequência de passos como elemento central; (3) **reutilizável** — aplica-se em mais de um contexto. Quando os três critérios forem claros, crie o Pattern junto com o PIC. Quando houver dúvida em algum critério, liste como sugestão ao final com `/pattern --from-pic`
10. Execute no modo selecionado

## Escopo do contexto relacionado

O ingest não deve virar uma revisão geral do vault. Use esta regra:

- Leia contexto indicado pelo usuário ou encontrado por correspondência direta de tema/título.
- Não varra todo `vault/Knowledge/` tentando encontrar relações indiretas.
- Não rode `/radar` automaticamente; apenas sinalize quando uma lacuna pedir radar.
- Não crie `Situation`, `Tension`, `Decision` ou `Application` durante ingestão salvo pedido explícito.
- Se uma `Situation` relacionada existir, linke ou recomende `/brief`; se não existir, apenas sugira criar quando o problema for recorrente ou prático.
- Se a fonte veio de um radar originado em Situation, não tente absorver todo o radar. Ingira apenas a fonte selecionada e preserve as demais como referência, pendência, tension ou application futura.
- Não crie `Principle` a partir de fonte recém-ingerida. Primeiro gere PICs; depois use `/synthesize` para formar permanent e só então `/reflect --principle`.

## Qualidade dos PICs gerados

> Gate aplicado no **Passo 7 (Curadoria)** — após enumeração completa, antes de criar qualquer nota.

O PIC deve fazer sentido completo sem que o leitor abra nenhuma fonte. Este é o critério central — tudo abaixo deriva dele.

**P:** é uma pergunta conceitual sobre o domínio, não sobre o material. Nunca nomeia aula, arquivo, curso, autor ou número de aula. Funciona como pergunta filosófica independente. Prefira "por que" e "o que muda quando" a "como" — perguntas procedurais geram respostas descritivas, não insights.

**I:** sintetiza a essência da ideia com as próprias palavras. Não cita, não parafraseia, não resume "o que foi dito". Explica por que a ideia é verdadeira, não-óbvia ou muda como alguém pensa sobre o domínio — não apenas o que ela é. Densidade média: 2–3 frases.

**C:** é onde a fonte aparece — como link para a Literature note. Nunca em P: ou I:. Deve ter ao menos uma conexão com outro PIC além da Literature e do MOC; se não houver PIC relacionado ainda, sinalize a lacuna explicitamente.

**Exemplos do que NÃO fazer:**

```
P: O que a aula 35 explica sobre créditos adicionais?
I: Conforme a aula, créditos adicionais são autorizações de despesa não previstas...
```

**Exemplos do que fazer:**

```
P: Por que créditos adicionais existem se a LOA já autoriza o gasto anual?
I: A LOA congela a autorização no momento da aprovação. Eventos imprevisíveis ou
   subestimados exigem abertura de crédito adicional para que o gasto ocorra
   legalmente — sem ele, a despesa não tem cobertura orçamentária.
C: [[Literature — Orçamento Público Gran Cursos Online]] — fonte
   [[PIC — LOA Define o Teto de Gasto Anual por Categoria]] — contexto
```

**Gate de qualidade — aplique a cada PIC antes de salvar:**

1. P: nomeia aula, arquivo, curso ou autor? → reescreva como pergunta conceitual.
2. P: começa com "como"? → reformule como "por que" ou "o que muda quando" — perguntas procedurais geram respostas procedurais, não insights.
3. I: usa "conforme", "segundo", "a aula", "o material", "foi apresentado"? → reescreva como síntese direta.
4. I: faz sentido lido isoladamente, sem o material? → se não, aprofunde.
5. I: diz apenas o que o título já diz com outras palavras? → aprofunde ou descarte o candidato. O I: deve acrescentar argumento ao título, não parafraseá-lo.
6. I: contém lista de 3 ou mais elementos conectados por vírgula ou "e"? → escolha o elemento central e crie PICs separados para os demais, ou transforme a lista em argumento.
7. C: tem ao menos um link para outro PIC além de Literature e MOC? → se não, sinalize a lacuna.
8. Vale um PIC? — este conceito tem insight não-óbvio que vale preservar? Nomenclatura, definição de ferramenta e listas de etapas de processo geralmente não merecem PIC próprio — merecem uma linha no I: de um PIC mais central. Se o conteúdo não muda como alguém pensa sobre o domínio, não crie o PIC.

## Regra de cobertura estrutural

> Aplica-se durante a enumeração (**Passo 6**) e a criação (**Passo 9**).

Quando a fonte tiver estrutura enumerativa explícita — lista de erros, passos, pilares, critérios, fases, perguntas, checklist, framework, método ou componentes — a ingestão deve preservar essa estrutura antes de sintetizar.

### Literature

A nota Literature deve registrar a estrutura completa da fonte, mesmo que alguns itens sejam depois agrupados em PICs. Por exemplo:

- se a aula apresenta "10 erros", listar os 10 erros;
- se apresenta "5 pilares", listar os 5 pilares;
- se apresenta um método em etapas, listar todas as etapas;
- se apresenta perguntas de diagnóstico, preservar as perguntas principais.

Essa lista fica em subseção própria dentro de `## Conteúdo ingerido`, como `#### Os 10 erros`, `#### Etapas do método` ou nome equivalente.

### PICs

PICs continuam atômicos. Não criar um PIC-lista apenas para reproduzir todos os itens.

Para cada item da estrutura, decidir:

1. **Criar PIC novo** quando o item expressa uma ideia reutilizável ainda não coberta.
2. **Reaproveitar PIC existente** quando a ideia já está suficientemente coberta.
3. **Registrar só na Literature** quando o item é apenas detalhe contextual, exemplo, aviso operacional ou repetição de ideia já coberta.

Fusões são aceitáveis apenas quando dois itens dizem essencialmente a mesma coisa ou quando um item é exemplo subordinado de outro.

### Checklist de cobertura — antes de concluir a ingestão (qualquer modo)

- todas as estruturas enumerativas da fonte aparecem na Literature;
- cada item tem destino explícito: PIC novo, PIC existente ou somente Literature;
- estruturas enumerativas da fonte não foram achatadas em resumo genérico;
- nenhum PIC criado virou nota-lista ampla demais;
- lacunas de cobertura foram resolvidas ou registradas como pendência.

### Critério de granularidade

A granularidade dos PICs deve seguir o conteúdo da fonte. Se a fonte diferencia dez erros, cinco pilares ou sete etapas, a ingestão não deve fundir itens que tenham causas, consequências ou ações corretivas diferentes.

## Modo Reedição (--redo)

Use quando a fonte já foi ingerida anteriormente e você quer re-processar com os padrões atuais de qualidade.

### O que o --redo faz

1. **Localiza a Literature existente** — busca em `vault/Knowledge/Literature/` pelo título da fonte. Se não encontrar, trata como ingestão nova (ignora o flag).
2. **Coleta os PICs vinculados** — grep por `[[Literature — <título>]]` em `vault/Knowledge/PIC/` para encontrar todos os PICs que citam essa fonte.
3. **Aplica o gate de qualidade a cada PIC existente** — os mesmos 8 critérios da seção "Qualidade dos PICs gerados". Reescreve apenas os campos problemáticos (P, I ou C), sem alterar frontmatter nem título.
4. **Identifica e cria lacunas** — relê o conteúdo bruto da fonte e verifica se há conceitos relevantes que não viraram PIC. Para cada candidato, confirma via grep em `vault/indexes/` e nos MOCs do domínio que o conceito não existe ainda. Se não existir, cria o PIC direto aplicando o gate de qualidade completo. Não cria PIC para conceito já coberto por nota existente, mesmo que com título diferente.
5. **Atualiza a Literature** — se a estrutura da Literature estiver desatualizada (sem `## Resumo`, `## Sumário` ou `## Conteúdo ingerido`), propõe atualização estrutural.
6. **Verifica cobertura estrutural** — se a fonte tiver estrutura enumerativa explícita e a Literature existente não registrar a lista completa, identifica e adiciona a subseção correspondente.

### O que o --redo NÃO faz

- Não apaga PICs existentes — apenas melhora os fracos.
- Não muda títulos de PICs nem renomeia arquivos.
- Não cria PIC para conceito já coberto por nota existente no vault ou no MOC.
- Não descarta conceitos que já estão bem sintetizados.

### Relatório do --redo

```
## Reedição — <título da fonte>

**PICs revisados:** N
**PICs corrigidos:** X (campos: P/I/C)
**PICs ok:** Y
**PICs criados para lacunas:**
- [[PIC — <título A>]] — conceito novo, não encontrado no vault
- [[PIC — <título B>]] — conceito novo, não encontrado no vault

**Lacunas não criadas (conceito já coberto):**
- <conceito C> → já existe [[PIC — <título equivalente>]]
```

---

## Modo Literature dirigida (--literature "<título>")

Use quando você quer **garantir o destino** da fonte, em vez de deixar a ingestão classificar — útil quando a fonte poderia cair em mais de uma coleção, quando o título/autor é ambíguo, ou quando você quer agrupar várias fontes na mesma Literature.

Comportamento:

1. **Normalize o título** — aceite com ou sem o prefixo `Literature —`. O alvo é `Literature — <título>`.
2. **Procure a Literature pelo título** em `vault/Knowledge/Literature/` (busca recursiva).
   - **Se existir**: use-a como destino. Não crie outra, não reclassifique. Atualize-a seguindo a estrutura padrão (novo item no `## Sumário`, resumo local + PICs no `## Conteúdo ingerido`). Os PICs apontam para ela em `C:`.
   - **Se não existir**: crie-a. Pergunte/infira apenas o `source-type` e o domínio para resolver o **destino físico** correto (ver seção "Destino físico"), mas mantenha o **título exatamente** como o usuário pediu. Em `--auto`, infira `source-type`/domínio do conteúdo sem perguntar; em `--review`, mostre o destino físico no plano para confirmação.
3. **Respeite o destino mesmo que a inferência discordaria** — o flag é uma instrução explícita. Se a classificação automática apontaria outra coleção, registre isso como nota no resumo final (uma linha), mas não mude o destino.
4. O resto do fluxo (enumeração, curadoria, PICs, cobertura estrutural, pós-ingestão) segue igual.

Combina com `--review` e `--auto`. Não combina com `--redo` (o redo já localiza a Literature pela própria fonte); se ambos forem passados, `--literature` define qual Literature o redo reprocessa.

## Modo Revisão (--review)

Antes de salvar, apresente o plano:
```
## Plano de ingestão

**Fonte:** <título>
**Tipo:** <tipo>
**Role:** <foundation|frontier|evidence|tension|method|reference>

**Contexto relacionado consultado:**
- Research/Handoff: nenhum / [[Radar — tema]] / [[Handoff — Radar tema]]
- Situation: nenhuma / [[Situação]]

**Nota Literature:** vault/Knowledge/Literature/<Tipo>/<domínio>/Literature — <título>.md (Tipo = Artigos|Livros|Notebooks|Projetos; para course: Cursos/<curso>/<domínio>/) — se `--literature` foi usado, marque **(destino dirigido pelo usuário)** e indique se é Literature nova ou existente
**PICs a criar:**
1. PIC — <título PIC 1>
2. PIC — <título PIC 2>

**Patterns a criar** (só aparece quando fonte for notebook/código):
1. Pattern — <título Pattern 1> (de [[PIC — título]])
2. Pattern — <título Pattern 2> (de [[PIC — título]])

**Conexões identificadas:**
- PIC — <PIC 1> → [[<nota existente com prefixo>]] — <relação>

Confirma? (s/n ou ajustes)
```

## Modo Autônomo (--auto)

Processa e salva todas as notas sem interrupção. Ao final, lista o que foi criado.

Autonomia não significa comprimir a fonte: significa tomar decisões de criação e reaproveitamento de PICs mantendo cobertura verificável da estrutura original.

## Literatura note — frontmatter obrigatório v2

```yaml
---
id: <timestamp>
type: literature
title: Literature — <título>
created: <data>
tags: []
source-type: <book|article|video|course|podcast|notebook>
role: <foundation|frontier|evidence|tension|method|reference>
status: reading
ingest-flow: <normal|radar>
research: [[Radar — <tema>]] # use apenas se ingest-flow: radar
---
```

Use `source-type: notebook` para notebooks Jupyter (`.ipynb`). Para esses arquivos: células markdown são o conteúdo principal a sintetizar em PICs; células de código são evidência de método ou implementação e só viram PIC quando o padrão de código for reutilizável (ex.: pipeline de dados, rotina de análise). Outputs muito longos (logs, dataframes extensos) podem ser ignorados ou sumarizados — não os inclua literalmente nos PICs.

Use `ingest-flow: normal` para ingestão direta de fonte sem fila de Research/Handoff. Use `ingest-flow: radar` quando a fonte foi promovida a partir de `Knowledge/Research` ou `Knowledge/Handoffs`; nesse caso, preencha `research:` com o radar de origem.

## Destino físico

Salve a nota `Literature` por TIPO e depois domínio (escolha o domínio pelo MOC relacionado principal):
- `source-type: article` → `vault/Knowledge/Literature/Artigos/<domínio>/`
- `source-type: book` → `vault/Knowledge/Literature/Livros/<domínio>/`
- `source-type: notebook` → `vault/Knowledge/Literature/Notebooks/<domínio>/`
- `source-type: course` → `vault/Knowledge/Literature/Cursos/<curso>/<domínio>/`, onde `<curso>` é o curso-mãe (faculdade, residência, bootcamp, certificado — ex: `ADS Senac`, `Gran Pós-Graduação em Gestão Pública`, `Residência IA UniSENAI`). Uma aula/matéria de um curso consolida na Literature-coleção desse curso, não vira nota solta.

Se a Literature já existir e o conteúdo recebido for parte dessa fonte maior, não crie nova Literature e não deixe o bruto em `Archive/<domínio>/Fleeting`. Atualize a Literature existente e mova o arquivo bruto para a pasta de arquivo da própria fonte em `vault/Archive/<domínio>/<título da fonte>/`, preservando o padrão de nomes da coleção. Exemplo: uma aula nova de um curso já ingerido deve ir para `vault/Archive/<domínio>/<nome do curso>/Aula NN — <título>.md`.

Domínios vigentes:

- `Hardware`
- `Software`
- `Infraestrutura`
- `Sistemas de Informação`
- `Orçamento Público`
- `Direito Constitucional`
- `Administração`
- `Libras`

Ao criar PICs derivados, salve em `vault/Knowledge/PIC/<domínio>/` usando o mesmo domínio do MOC principal do PIC.

## Literature note — estrutura padrão

A nota `Literature` deve separar três camadas:

- `## Resumo` — resumo geral da fonte inteira, sem resumos por capítulo, aula ou seção.
- `## Sumário` — lista dos capítulos, aulas ou itens da fonte; quando houver bruto arquivado, cada item deve linkar o arquivo correspondente. Inclua uma linha `Fonte:` abaixo da lista com a referência breve e o caminho de arquivo da coleção quando houver.
- `## Conteúdo ingerido` — para cada capítulo, aula ou seção, inclua primeiro um resumo local curto e depois os PICs agrupados por temas com subtítulos `####`.

Não registre pendências, observações de ingestão, decisões de descarte, gabaritos ignorados ou status operacional dentro da `Literature`. Quando esse registro precisar ser preservado, use `Knowledge/Research`, `Knowledge/Handoffs` ou `Operations/Reviews/Qualidade`, conforme o ciclo de vida do item.

Quando a fonte for um capítulo de livro e o arquivo original estiver em `vault/Archive/`:
- No sumário da literature note, link o capítulo ingerido para o arquivo: `[[nome-do-arquivo.pdf|Nome do capítulo]]`
- Capítulos ainda não processados ficam como texto simples
- O MOC **não** vai no sumário — já aparece em "## MOC relacionado" abaixo
- Não crie `## Fonte` separado quando o sumário já lista os arquivos da fonte; use a linha `Fonte:` no próprio sumário.

Se a literature note já existir, atualize apenas a linha do capítulo, aula ou item recém-ingerido, usando o link do bruto arquivado na pasta da coleção quando houver, e coloque o resumo específico dentro da seção desse capítulo, aula ou item.

## Atualização do índice

O hook atualiza `vault/indexes/` automaticamente após cada Write/Edit em `vault/` — nenhuma ação manual necessária.

## Pós-ingestão automática

**Vínculo a MOC e candidatos a Tópico não são mais responsabilidade do `/ingest`.** Cada PIC criado é capturado automaticamente na fila `vault/Operations/Status/pics-capturados.md` (pelo hook `index-hook.py`, em qualquer Write do Claude), com `pendente: candidato, moc`. A curadoria desses dois pós-passos é centralizada em `/curate` — evita que `/ingest` reimplemente a lógica de MOC/candidato (que divergia de skill para skill) e garante que PICs criados por qualquer caminho recebam o mesmo tratamento.

Após salvar todas as notas, **dispare a curadoria sobre o que acabou de ser criado**, sem ação manual do usuário:

1. Execute `/curate --moc --drain` — vincula os PICs recém-criados ao MOC de conteúdo do domínio (drena as linhas da fila com `moc` pendente). Em `--auto`, aplique os vínculos claros direto; em `--review`, mostre a proposta de MOC/seção e aguarde aprovação. Segue o protocolo de seção da própria `/curate` (casar por tema, não duplicar seção, não inserir wikilink repetido).
2. Execute `/curate --drain` — cataloga os PICs recém-criados como candidatos a Tópico (drena as linhas com `candidato` pendente). Em `--auto`, registra os clusters claros; em `--review`, propõe e aguarda. Subcluster com menos de 5 PICs não vira candidato (fica na fila para amadurecer).

Não reimplemente aqui a lógica de seção de MOC nem de agrupamento de candidato — ela vive em `/curate`. O `/ingest` apenas a aciona ao final.

A seguir, a **integração da fonte** (isto continua sendo responsabilidade do `/ingest`, pois depende do contexto da ingestão, não do PIC isolado):

3. Verifique `vault/Knowledge/Research/Active/` — se a fonte ingerida estava em algum arquivo `Radar — *.md`, remova ou marque a entrada correspondente como ingerida/descartada; quando o radar ficar resolvido, mova para `vault/Knowledge/Research/Resolved/` e atualize [[MOC — Research]]
4. Se havia handoff relacionado e a fonte ingerida resolve uma recomendação dele, marque isso no handoff ou registre a pendência restante; quando o handoff for integrado, mova para `vault/Knowledge/Handoffs/Completed/` e atualize [[MOC — Handoffs]]
5. Se havia `Situation` relacionada, mantenha a ligação como contexto: adicione link quando fizer sentido na Literature/PIC ou recomende `/brief` se a situação exigir decisão ou aplicação
6. Se havia `Brief` ou `Project` relacionado, registre no resumo se a ingestão alimenta:
   - conceito reutilizável (`PIC`);
   - tese futura (`/synthesize`);
   - tensão (`/tension`);
   - aplicação prática futura (`/reflect --application`);
   - ou apenas referência preservada.

Apresente um resumo compacto ao final:

```
## Vault atualizado

MOCs atualizados: X
PICs adicionados ao [[MOC — Y]]: [[PIC A]], [[PIC B]]
PICs órfãos: nenhum / [[PIC C]] (sem MOC ainda)

Patterns criados: [[Pattern — Título A]], [[Pattern — Título B]]
(omitir se nenhum foi criado)

Candidatos a Pattern (critério incerto — aguardam decisão):
- [[PIC — Título C]] → `Pattern — <título sugerido>` — use `/pattern --from-pic "PIC — Título C"`
(omitir se nenhum)

Quer rodar /synthesize sobre "<tema>"?

---
Commits concluídos. Execute /compact para compactar o contexto.
---
```
