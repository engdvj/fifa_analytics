# Skill: /ingest-batch

Ingere um lote de fleetings em sequência, spawning um sub-agente por item via Agent tool para preservar qualidade independente do tamanho do lote.

## Uso

```
/ingest-batch [--review | --auto] [--domain <domínio>] [--dir <caminho>]
```

- `--review` — cada item apresenta plano e aguarda aprovação antes de salvar
- `--auto` — cada item processa e salva direto, sem interrupção
- `--domain <domínio>` — restringe o lote a um domínio específico dentro de `Capture/Fleeting/`
- `--dir <caminho>` — usa um diretório arbitrário como fonte em vez de `Capture/Fleeting/`; processa todos os arquivos `.md` e `.ipynb` encontrados nele
- Sem flag — pergunta qual modo usar

## Por que sub-agentes

Cada fleeting é processada por um agente isolado com contexto limpo. Isso evita que o contexto do vault acumulado durante ingestões anteriores degrade a qualidade das seguintes. O agente orquestrador (este skill) coordena a fila e consolida o relatório; os sub-agentes fazem o trabalho substantivo.

## Comportamento

### Passo 1 — Montar a fila

1. Determine a fonte:
   - Se `--dir <caminho>`: use o diretório informado. Liste todos os arquivos `.md` e `.ipynb` encontrados nele diretamente (não recursivo, salvo se o caminho terminar com `**`). Não filtra por `status:` — todo arquivo no diretório é candidato. Para `.ipynb`, use o Read tool para obter o conteúdo; o resultado já vem interpretado (células de código, markdown e outputs combinados).
   - Se `--domain`: restrinja a `vault/Capture/Fleeting/<domínio>/`.
   - Sem nenhum dos dois: varre `vault/Capture/Fleeting/` recursivamente e lista fleetings sem `status: processed`.
2. Apresente a fila antes de processar:

```
## Fila de ingestão

1. Fleeting — Título A (vault/Capture/Fleeting/Domínio/...)
2. Fleeting — Título B (vault/Capture/Fleeting/Domínio/...)
...

N itens encontrados. Modo: <--review | --auto>. Continua? (s/n)
```

Se a fila estiver vazia, informe e encerre.

### Passo 2 — Processar cada item com sub-agente

Para cada item na fila, use o Agent tool para spawnar um sub-agente com o seguinte prompt:

```
Você está executando uma ingestão isolada de um arquivo no vault PKM.

Leia as instruções completas do /ingest em:
.claude/commands/ingest.md

Arquivo a ingerir:
- Caminho: <caminho completo>
- Tipo: <"fleeting .md" | "notebook .ipynb">
- Conteúdo: <conteúdo do arquivo — para .ipynb, use o Read tool para obter o conteúdo interpretado>

Modo: <--review | --auto>

Se o arquivo for um notebook `.ipynb`: trate-o como fonte de conhecimento (Literature + PICs), não como fleeting. Células markdown são o conteúdo principal; células de código são evidência de método ou implementação e podem gerar PICs de método quando relevante. Não arquive o notebook — apenas ingira o conteúdo.

Se o arquivo for uma fleeting `.md`: siga o fluxo padrão do /ingest.

Execute o /ingest para este arquivo. Ao final, reporte exatamente:
- Notas criadas (tipo + caminho)
- Notas atualizadas (tipo + caminho)
- Caminho de destino do arquivo bruto arquivado (apenas para fleetings)
- Pendências ou itens que exigiram decisão
```

Execute os sub-agentes **sequencialmente**, não em paralelo. Cada um pode atualizar `vault/indexes/` e MOCs; paralelismo causaria conflito.

Em modo `--review`: apresente o plano retornado pelo sub-agente ao usuário antes de prosseguir para o próximo item. Aguarde confirmação.

### Passo 3 — Atualizar candidatos a Tópico — **obrigatório; nunca pule**

Após consolidar os resultados de todos os sub-agentes:
- Leia os arquivos de candidatos relevantes para os domínios do lote: `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md` (mapeamento: `ADM`→ADM, `DC`→DC, `HW`→HW, `INF`→INF, `LIB`→LIB, `OP`→OP, `SI`→SI, `SW`→SW)
- Releia `vault/indexes/INDEX-PIC-*.md` para confirmar tags dos PICs criados; não dependa apenas do relatório textual dos sub-agentes
- Para cada grupo de 3+ PICs criados no lote com tema comum, verifique se já existe candidato **específico** para esse subcluster — candidato amplo **não** cobre subclusters específicos; trate como ausente e adicione
- Agrupe PICs por afinidade temática usando tags compartilhadas não genéricas, subtítulos da Literature, seções de MOC e termos recorrentes dos títulos — cada grupo distinto vira uma entrada separada; nunca reúna temas diferentes em uma única entrada
- Ignore tags puramente de domínio (`direito-constitucional`, `administração`, `hardware`, `software`, `infraestrutura`, `sistemas-de-informação`, `orçamento-público`, `libras`) como tag dominante, mas preserve-as para escolher o domínio
- Para cada entrada a adicionar: escreva no arquivo do domínio correto (`_Candidatos-<DOMINIO>.md`) e no cluster (`### <Cluster>`); crie o cluster se não existir
- Formato: `XXnn. <Título descritivo> — <conceitos principais separados por vírgula>` onde `XX` é o prefixo do domínio (`HW`, `SW`, `SI`, `INF`, `OP`, `DC`, `ADM`, `LIB`) e `nn` é o próximo número sequencial dentro do domínio (ex.: `ADM35.`)
- Nunca adicione sufixo `— N+ PICs`
- Atualize o comentário `<!-- Alcance: ... -->` do cabeçalho do arquivo do domínio quando avançar a numeração
- **Liste os candidatos adicionados no resumo final — se a lista estiver vazia, justifique explicitamente com uma razão verificável: menos de 3 PICs no subcluster, candidato específico já existente, Tópico existente ou ausência real de tema comum**

### Passo 4 — Resumo consolidado

Ao final do lote, apresente:

```
## Resumo do lote — /ingest-batch

Processados: N/M
Pulados ou pendentes: X

### Criações
- Literature: [[Título A]], [[Título B]]
- PICs: [[PIC — X]], [[PIC — Y]], [[PIC — Z]]
- MOCs atualizados: [[MOC — Tema]]

### Arquivamentos
- vault/Archive/Fonte/Aula NN.md
- vault/Archive/Fleeting/Domínio/Fleeting — Título B.md

### Candidatos adicionados a _Candidatos-<DOMINIO>.md
- N. Título do candidato — tags

### Pendências
- [[Fleeting — X]]: <motivo pelo qual não foi processada>

---
Quer rodar /synthesize sobre algum tema, ou /inbox para revisar o que sobrou?
```

## Regras

- Nunca processe em paralelo — sempre sequencial.
- Não crie Permanent, Principle, Tension ou Decision dentro deste fluxo. O ingest vai até Literature + PIC.
- Se um sub-agente falhar ou retornar erro, registre na pendência e continue com o próximo item.
- Se a fila tiver mais de 10 itens sem `--dir`, sugira usar `--domain` para processar por partes.
- Com `--dir`, não há limite sugerido — o usuário já escolheu o escopo explicitamente.
