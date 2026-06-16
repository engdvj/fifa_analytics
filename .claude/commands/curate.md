# Skill: /curate

Faz os pós-passos de curadoria de um PIC recém-criado: catalogá-lo como candidato a Tópico (`_Candidatos.md`) e vinculá-lo a um MOC de conteúdo (`--moc`). Fecha o vazamento em que PICs criados fora do `/ingest` (via `/reflect`, `/brief`, `/synthesize`, runner do watcher, edição no Obsidian) nunca chegavam a esses pós-passos.

## O problema que resolve

`_Candidatos.md` historicamente só era alimentado por `/ingest`, `/pic` e `/ingest-batch`. Conteúdo que entra por outros caminhos — um cluster inteiro de visão computacional nascido de um Brief→Project→Tradeoff, por exemplo — gera dezenas de PICs no disco que ficam **invisíveis** para `/topic`, porque nunca foram catalogados como cluster. O resultado é a sensação de "tanto conteúdo e nenhum candidato".

`/curate` é a etapa de **captura + curadoria centralizada**, independente do caminho de entrada. Trabalha em duas frentes:

1. **Fila de captura** (`vault/Operations/Status/pics-capturados.md`) — alimentada automaticamente pelo hook `index-hook.py` a cada PIC criado **via Claude** (qualquer skill). É o sinal barato e contínuo: "estes PICs são novos desde a última curadoria". Limite: o hook não vê edição direta no Obsidian (não passa pelo Claude) — esse caso cai na frente 2.
2. **Varredura do disco** — cruza os PICs reais de cada domínio contra os clusters já catalogados em `_Candidatos-<DOMINIO>.md`, pegando o acúmulo histórico, o que entrou antes do hook existir, E os PICs criados direto no Obsidian que a fila não capturou.

## Posição no fluxo

```
PIC criado (por qualquer caminho: /ingest, /reflect, /brief, edição manual)
    ↓  (hook index-hook.py registra na fila de captura — automático, sem julgamento)
pics-capturados.md  +  acúmulo histórico no disco
    ↓  /curate  (agrupa em clusters nomeados — julgamento, sob demanda)
_Candidatos.md
    ↓  /topic --pick <código>
Tópico curado
```

Divisão de responsabilidade deliberada: o **hook captura** (mecânico, automático, à prova de falha — só conta, não classifica); a **`/curate` cataloga** (julgamento de agrupamento e nomeação, sob demanda, com gate). Espelha a fronteira `index-hook.py` × `/update-vault` que já existe no vault.

## A fila e os dois pós-passos

Um PIC criado precisa de dois pós-processamentos com julgamento, e ambos saem da mesma fila `pics-capturados.md`:

- **candidato** — agrupar o PIC num cluster candidato a Tópico em `_Candidatos-<DOMINIO>.md` (curadoria de candidato, padrão);
- **moc** — vincular o PIC a um MOC de conteúdo do domínio (curadoria de MOC, `--moc`).

Cada linha da fila tem um campo `pendente:` que lista o que ainda falta (ex.: `pendente: candidato, moc`). Quando uma curadoria processa um PIC, ela **remove só o seu termo**; o PIC sai da fila quando `pendente` fica vazio. Assim um único ponto de captura (hook + runner) alimenta os dois consumidores sem que um atropele o outro.

## Uso

```
/curate [--scan | --drain | --apply]        # curadoria de CANDIDATO (padrão)
/curate --moc [--scan | --drain | --apply]  # curadoria de MOC
```

Curadoria de **candidato** (sem `--moc`):
- `--scan` — diagnóstico padrão. Lê a fila (PICs com `candidato` pendente) E varre o disco, identifica clusters órfãos, e **propõe** nome + keywords + PICs de cada um. Não grava. Espera aprovação.
- `--drain` — só a fila (PICs com `candidato` pendente), sem varredura de disco. Recorrente e rápido.
- `--apply` — grava clusters aprovados em `_Candidatos-<DOMINIO>.md` (arquivo do domínio do cluster) e remove `candidato` do `pendente` dos PICs catalogados.

Curadoria de **MOC** (`--moc`):
- `--moc --scan` — lê a fila (PICs com `moc` pendente) E varre o disco por PICs que não aparecem em nenhum MOC do seu domínio; **propõe** o MOC e a seção de destino de cada um. Não grava. Espera aprovação.
- `--moc --drain` — só a fila (PICs com `moc` pendente).
- `--moc --apply` — insere os PICs aprovados nos MOCs e remove `moc` do `pendente`.

Sem flag — executa `--scan` (candidato).

**Gate obrigatório (ambos os modos):** `/curate` nunca grava sem aprovação explícita na conversa. Agrupar cluster e escolher MOC/seção é julgamento; candidato ou vínculo errado contamina `/topic` e a navegação. Proponha, espere o "pode gravar", só então `--apply`.

---

## Passo 1 — Coletar PICs a catalogar

Duas fontes, combine ambas em `--scan` (só a primeira em `--drain`):

**Fonte A — fila de captura.** Leia `vault/Operations/Status/pics-capturados.md`. Cada linha é `- [[PIC — ...]] | domínio: X | pendente: candidato, moc`. **Considere apenas as linhas cujo `pendente:` contém `candidato`** (no modo candidato) — as demais já foram catalogadas. Se o arquivo não existe, só tem cabeçalho, ou nenhuma linha tem `candidato` pendente, a fila está vazia para este modo — siga para a Fonte B em `--scan`, ou encerre com "fila vazia" em `--drain`.

**Fonte B — varredura do disco** (só em `--scan`). Para cada domínio:

```
find "vault/Knowledge/PIC/<domínio>/" -name '*.md' | sed 's|.*/PIC — ||;s|\.md$||'
```

Use busca recursiva. Os domínios vigentes: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`.

Para domínios com muitos PICs (Direito Constitucional ~1000, Administração ~900), considere dividir a varredura por domínio em subagentes `Explore` paralelos — cada um cruza os PICs reais de um domínio contra os clusters catalogados e devolve só os clusters órfãos. Peça a conclusão (cluster proposto + ~contagem + 5-8 exemplos + keywords), não o dump de títulos.

**Trava anti-duplicação obrigatória no prompt do subagente** (sem ela, subagentes inflam o resultado em ~10×, agrupando PICs que já cabem em clusters existentes): instrua explicitamente que, ANTES de declarar um grupo órfão, confirme que cada PIC do grupo não se encaixa em NENHUM cluster catalogado do domínio. Cluster existente que está "crescendo" (ganhando PICs) NÃO é órfão. Liste os clusters catalogados próximos do tema e justifique por que o grupo não pertence a eles. Domínios com muitos clusters de carreira/estratégia/gestão (Administração tem ADM26-53 cobrindo carreira, promoção, escopo, estratégia) são os que mais geram falso positivo — peça ceticismo redobrado ali. Ao receber o retorno do subagente, **sempre valide cada cluster proposto** com um grep contra `_Candidatos-<DOMINIO>.md` e contra os títulos reais antes de levá-lo ao usuário; descarte os que já têm cobertura.

## Passo 2 — Ler os clusters já catalogados

Leia o arquivo do domínio relevante: `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md`. Mapeamento de prefixo para arquivo: `ADM`→`_Candidatos-ADM.md`, `DC`→`_Candidatos-DC.md`, `HW`→`_Candidatos-HW.md`, `INF`→`_Candidatos-INF.md`, `LIB`→`_Candidatos-LIB.md`, `OP`→`_Candidatos-OP.md`, `SI`→`_Candidatos-SI.md`, `SW`→`_Candidatos-SW.md`. Em varreduras multi-domínio, leia cada arquivo separadamente. Cada linha `<PREFIXO><NN>. Nome — keywords` é um cluster já catalogado. Anote o maior número usado em cada prefixo (para numerar os novos em sequência) — está no comentário `<!-- Alcance: ... -->` do cabeçalho de cada arquivo.

## Passo 3 — Identificar clusters órfãos

Um **cluster órfão** é um grupo de **5+ PICs com tema coeso** que não se encaixa em nenhum cluster catalogado. Critérios:

- mínimo ~5 PICs; abaixo disso, registre como observação, não como cluster (pode amadurecer depois);
- tema coeso e nomeável no estilo dos clusters existentes (uma lente de estudo, não um amontoado);
- não duplicar um cluster existente — se os PICs se encaixam num cluster catalogado mas ele estava subpreenchido, isso não é cluster novo, é o cluster existente crescendo;
- desconfiar de falsos positivos de keyword: um título com "vínculo" pode ser trabalhista, previdenciário ou de nacionalidade. Confirme o tema lendo os títulos, não só batendo palavra.

Para cada cluster órfão, monte: **código** (próximo número livre do prefixo do domínio), **nome** curto no estilo dos existentes, **~contagem** de PICs, **keywords centrais** (extraídas dos títulos reais no disco, não inventadas), **subseção** de destino dentro do domínio (ou nova subseção `### <tema>` se nenhuma servir).

Registre também, fora dos clusters: **clusters fantasma** (catalogados em `_Candidatos.md` sem nenhum PIC no disco — candidatos a remoção ou a `/radar`) e **subclusters pequenos** (<5 PICs, ainda imaturos).

## Passo 4 — Propor e esperar aprovação

Apresente no chat, por domínio, cada cluster órfão proposto: código, nome, contagem, keywords, exemplos de PIC. Deixe claro em qual arquivo (`_Candidatos-<DOMINIO>.md`) e subseção cada um entraria. **Pare aqui.** Não grave nada até o usuário aprovar (pode ajustar nome, fronteira ou descartar). Esta skill respeita gate de revisão sempre — agrupar é julgamento.

## Passo 5 — Aplicar (`--apply`, após aprovação)

Depois do "pode gravar":

1. Para cada cluster aprovado, insira a linha `<CÓDIGO>. Nome — keywords` na subseção correta do arquivo do domínio em `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md`. Crie a subseção `### <tema>` se necessário. Não reordene nem remova entradas existentes.
2. Atualize o comentário `<!-- Alcance: ... -->` do cabeçalho do arquivo com os novos intervalos (ex.: `SI01–53` → `SI01–55`).
4. **Resolva o pendente:** para cada PIC catalogado nesta rodada que estava na fila, remova o termo `candidato` do seu campo `pendente:` em `vault/Operations/Status/pics-capturados.md`. Se o `pendente:` do PIC ficar vazio, remova a linha inteira. Se a fila ficar sem nenhuma linha de PIC, delete o arquivo (o hook/runner o recriam no próximo PIC). Não toque nas linhas com `moc` pendente que não foram catalogadas agora — elas aguardam `--moc`. (A varredura de disco também cataloga PICs que nunca estiveram na fila; esses não têm linha a atualizar.)
5. Valide: `git diff --check` limpo; novos códigos presentes; contagens do cabeçalho coerentes.

---

## Curadoria de MOC (`--moc`)

Vincula PICs órfãos de MOC ao MOC de conteúdo do domínio. Mesma estrutura captura→fila→curadoria com gate, alvo diferente: em vez de agrupar em cluster, **insere o link do PIC na seção certa de um MOC existente**.

### Passo M1 — Coletar PICs sem MOC

- **Fonte A (fila):** linhas de `pics-capturados.md` cujo `pendente:` contém `moc`.
- **Fonte B (disco, só `--scan`):** para cada domínio, liste os PICs e cruze contra os wikilinks de todos os MOCs de conteúdo do domínio (`vault/Navigation/MOC/Conteúdo/<domínio>/MOC — *.md`). PIC cujo título não aparece em nenhum MOC do domínio é órfão de MOC. Para domínios densos, delegue a subagentes `Explore` (mesma trava anti-duplicação: confirme que o PIC realmente não está em nenhum MOC antes de declará-lo órfão; valide o retorno por grep).

### Passo M2 — Escolher MOC e seção de destino

Para cada PIC órfão, determine **qual MOC** do domínio e **qual seção** dele recebe o link. Critério: o MOC e a seção cujo tema o PIC concretiza. Se nenhum MOC do domínio cobre o tema, registre como **lacuna de MOC** (candidato a novo MOC ou a `/synthesize`/`/topic`) — não force um vínculo ruim. Um PIC de fronteira pode entrar em dois MOCs; não escolha um lado arbitrariamente.

### Passo M3 — Propor e esperar aprovação

Apresente, por domínio: cada PIC órfão → MOC e seção propostos, com a entrada `- [[PIC — ...]] — <função neste MOC>`. **Pare.** Escolher MOC/seção é julgamento. Espere o "pode gravar".

### Passo M4 — Aplicar (`--moc --apply`)

1. Insira `- [[PIC — Título]] — <função neste MOC>` na seção correta do MOC, seguindo o padrão de entradas do MOC (link + função). Não reordene nem remova entradas; não crie seção sem necessidade.
2. Para cada PIC vinculado que estava na fila, remova `moc` do seu `pendente:`; remova a linha se ficar vazio; delete o arquivo se a fila esvaziar.
3. Valide: `git diff --check` limpo; o PIC agora aparece como wikilink no MOC.

## Limites

- Não cria Tópico — isso é `/topic --pick`. `/curate` só popula a fila de candidatos.
- Não cria, edita ou move PICs. Lê PICs e escreve em `_Candidatos-<DOMINIO>.md`, nos MOCs e na fila de captura.
- Não cria MOC novo nem escreve prosa/tese de MOC — só insere link de navegação em MOC existente. MOC faltante vira lacuna registrada (→ `/synthesize`/`/topic`).
- Não promove cluster a Tópico nem decide `coverage`.
- Não grava sem aprovação (gate sempre, ambos os modos).
- Subcluster com menos de 5 PICs não vira candidato — registra-se como observação.
