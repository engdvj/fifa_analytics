# Skill: /topic

Cria e mantém unidades de estudo curadas por tema — notas `Tópico` que organizam o conhecimento do vault em prosa contínua para leitura direta, sem precisar navegar nota a nota.

## Posição no fluxo

```
PIC (atômico)
    ↓
Tópico (curado — leitura direta, contexto e organização do tema)
    ↓
Permanent (sintetizado — "qual é minha tese sobre X")
```

Tópico é a camada entre PIC e Permanent. Não faz teses — explica e organiza. Um Tópico bem escrito permite estudar o tema sem abrir nenhuma das notas referenciadas. Quando você consegue escrever a Essência com confiança (`coverage: dominado`), o Permanent pode ser redigido. Tópico sem `coverage: dominado` indica conhecimento parcial; Permanent gerado sem Tópico costuma ser superficial ou prematuro.

## Uso

```
/topic [--scan | --pick <código> | --draft "<tema>" | --update "<tópico>" | --coverage <status>]
```

- `--scan` — lista clusters de 3+ PICs sem Tópico correspondente e Tópicos existentes com status de cobertura
- `--pick <código>` — cria o Tópico do candidato com o código informado (ex.: `ADM11`, `HW03`) em `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md`
- `--draft "<tema>"` — cria um novo Tópico curado sobre o tema especificado
- `--update "<tópico>"` — atualiza Tópico existente com notas adicionadas após a criação
- `--coverage <rascunho|em-estudo|dominado>` — atualiza o campo `coverage:` de um Tópico existente
- Sem flag — executa `--scan` por padrão

---

## Comportamento: --pick

1. Determine o arquivo de domínio pelo prefixo do código (ex.: `ADM11` → `_Candidatos-ADM.md`, `HW03` → `_Candidatos-HW.md`). Mapeamento de prefixos: `ADM`→ADM, `DC`→DC, `HW`→HW, `INF`→INF, `LIB`→LIB, `OP`→OP, `SI`→SI, `SW`→SW.
2. Leia `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md`
3. Localize a entrada com o código informado — entradas já concluídas têm `→ [[...]]` ao final
4. Exiba a entrada encontrada e confirme com o usuário:
   ```
   Candidato <código>: <título do candidato>
   Tags: <tags>
   
   Prosseguir com `/topic --draft "<tema>"`? (s/n)
   ```
5. Se confirmado, execute o comportamento `--draft` com o tema derivado da entrada
6. Após salvar o Tópico, atualize `_Candidatos-<DOMINIO>.md`:
   - Localize a linha da entrada com o código e adicione ` → [[Tópico — <tema>]]` ao final dela
   - Não remova a entrada; não renumere nada

---

## Comportamento: --scan

1. Leia os arquivos de candidatos por domínio em `vault/Navigation/Tópicos/_Candidatos-*.md` (um por domínio: ADM, DC, HW, INF, LIB, OP, SI, SW).
   - Liste entradas pendentes por domínio e código.
   - Liste entradas concluídas apenas como referência curta, quando houver `→ [[Tópico — ...]]`.
   - Se um domínio tiver PICs no índice mas arquivo `_Candidatos-<DOMINIO>.md` vazio ou inexistente, marque isso como dívida de candidatos.
2. Leia os arquivos de índice em `vault/indexes/` para obter todos os PICs com suas tags.
3. Agrupe por tags compartilhadas, ignorando tags puramente de domínio como dominante (`direito-constitucional`, `administração`, `hardware`, `software`, `infraestrutura`, `sistemas-de-informação`, `orçamento-público`, `libras`).
4. Complemente o agrupamento com:
   - `moc:` dos PICs quando disponível nos arquivos;
   - seções dos MOCs de conteúdo que já agrupam esses PICs;
   - blocos `####` da Literature quando vários PICs da mesma fonte foram ingeridos juntos.
5. Cada grupo de 3+ PICs com tag, MOC ou seção temática comum vira cluster candidato.
6. Para cada cluster, verifique recursivamente em `vault/Navigation/Tópicos/` se já existe Tópico correspondente (busca por título, tag dominante e entrada concluída em `_Candidatos.md`).
7. Ao apresentar candidatos novos, não oculte subclusters específicos só porque existe candidato amplo no mesmo domínio.
8. Apresente o relatório no formato:

```
## Estado dos Tópicos

### Candidatos pendentes em _Candidatos-<DOMINIO>.md
- **<código>. <tema>** — <conceitos> | sugestão: `/topic --pick <código>`
...

### Clusters sem Tópico (prioridade)
- **<tema>** — <N> PICs | tags: <tags> | sugestão: `/topic --draft "<tema>"`
  PICs: [[PIC — A]], [[PIC — B]], [[PIC — C]]
...

### Dívida de candidatos
- <domínio> — há <N> PICs no índice, mas nenhuma entrada pendente em `_Candidatos-<DOMINIO>.md`
...

### Tópicos existentes
- [[Tópico — X]] — coverage: <status> | domain: <domínio>
...

O que quer trabalhar? (número do cluster ou "nenhum")
```

---

## Comportamento: --draft

1. Receba o tema via flag ou escolha do usuário após `--scan`
2. Determine o domínio pelo MOC ou tags dos PICs envolvidos
3. Reúna todas as notas relacionadas ao tema:
   - Grep nos índices por tag, título ou palavra-chave do tema em PICs, Patterns e Permanents
   - Para cada PIC encontrado, leia as primeiras 30 linhas (garante captura completa de frontmatter + P: + I:)
   - Para cada Pattern, leia `## Problema` e `## Quando usar`
   - Para Permanents existentes, leia frontmatter + `## Tese`
   - Verifique Tensions e Principles com as mesmas tags
4. Antes de escrever, mapeie:
   - Qual é o núcleo do tema? (para a Essência)
   - Qual é a narrativa de aprendizado? (do problema que o tema resolve até suas limitações)
   - Como organizar em seções temáticas que façam sentido sozinhas?
   - Quais são os pontos contraintuitivos que merecem destaque em prosa?
   - Quais exemplos concretos tornam conceitos abstratos compreensíveis?

   **Âncora de volume:** um Tópico bem organizado tem entre 4–8 seções temáticas. Menos de 3 indica agrupamento excessivo ou tema estreito demais para Tópico; mais de 8 indica que o tema deve ser dividido em dois Tópicos separados.

5. Redija o rascunho completo e apresente para aprovação
6. Após aprovação, salve em `vault/Navigation/Tópicos/<domínio>/Tópico — <tema>.md`
7. Atualize o MOC do domínio:
   - Se já existe seção `## Tópicos`, adicione a entrada lá
   - Se não existe, crie a seção `## Tópicos` antes de `## Sínteses` (ou antes de `## Fontes`, ou ao final se nenhum existir)
   - Formato: `- [[Tópico — <tema>]] — <descrição em meia linha>`
8. Adicione entrada em `vault/Navigation/MOC/MOC — Tópicos.md` sob o domínio correspondente
9. **Atualizar _Candidatos-<DOMINIO>.md** — determine o domínio do Tópico criado e verifique se o tema corresponde a alguma entrada em `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md`:
   - Se houver correspondência (por título ou tags sobrepostas), adicione ` → [[Tópico — <tema>]]` ao final da linha correspondente
   - Não remova entradas; não renumere nada
   - Se não houver correspondência (tema novo não listado), nenhuma alteração no arquivo de candidatos

### Critérios de organização das seções

As seções do Tópico não são listas de links com uma linha cada — são blocos de prosa temática que o leitor consegue ler sem abrir nenhuma nota referenciada. Use estes critérios para organizar e escrever cada seção:

- **Comece pelo problema**: a primeira seção explica por que o tema existe e o que acontece sem ele
- **Fundamentos antes de aplicações**: conceitos que explicam *o que é* antes de técnicas que explicam *como fazer*
- **Contraintuitivo merece parágrafo próprio**: se há algo que a maioria erra ou assume errado, destaque em prosa — não sepulte em lista
- **Exemplos concretos ancoram abstrações**: prefira um exemplo real a uma definição genérica
- **Linguagem simples (técnica Feynman)**: explique como se estivesse ensinando alguém inteligente que não conhece o tema. Evite jargão quando possível; quando inevitável, defina em contexto

---

## Comportamento: --update

1. Pergunte qual Tópico atualizar (ou receba via flag)
2. Leia o Tópico existente na íntegra
3. Verifique nos índices por novas notas com as mesmas tags criadas após a data do Tópico
4. Classifique cada nova nota:
   - **PIC que enriquece seção existente**: proponha expansão da prosa da seção relevante
   - **PIC que abre novo tema**: proponha nova seção com prosa própria
   - **Novo Pattern**: adicione ao bloco de referências (Padrões) e, se relevante, expanda a prosa da seção correspondente
   - **Nova Permanent**: adicione ao bloco de referências (Sínteses)
   - **Nova Tension**: adicione ao bloco de referências (Tensões)
   - **Irrelevante**: ignora
5. Apresente as propostas de atualização e aguarde aprovação
6. Salve as mudanças aprovadas

---

## Comportamento: --coverage

1. Pergunte qual Tópico atualizar (ou receba via flag)
2. Pergunte ou receba o novo status: `rascunho | em-estudo | dominado`
3. Atualize o campo `coverage:` no frontmatter
4. Se `coverage: dominado`, exiba:
   ```
   Tópico marcado como dominado.
   Próximo passo natural: /synthesize --draft "<tema>"
   ```
5. Se `coverage: em-estudo`, exiba:
   ```
   Tópico marcado como em estudo.
   Quando se sentir confortável com a Essência, rode /topic --coverage dominado.
   ```

---

## Frontmatter obrigatório

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: topic
title: Tópico — <nome do tópico>
created: <YYYY-MM-DD>
tags: [<tags herdadas do cluster de PICs>]
domain: <domínio>
moc: [[MOC — <domínio>]]
requer: [[Tópico — X]] # opcional — dependências de aprendizado; omitir quando não houver
coverage: rascunho
permanent: [[Permanent — título]] # omitir até existir; preencher quando a síntese for criada
---
```

## Estrutura do corpo

```markdown
## Essência
[3–5 linhas em prosa: o núcleo do tema — o que é, por que importa, qual insight central carrega.
Inteligível sem abrir nenhuma nota referenciada.]

## [Seção 1 — título que descreve o conteúdo, não "Camada 1"]
[1–3 parágrafos de prosa expositiva. Nenhum link inline — o leitor não precisa clicar para
entender. Exemplos concretos antes de definições abstratas. Linguagem direta.]

## [Seção 2 — título temático]
[idem]

## [Mais seções conforme a narrativa do tema exigir...]

## Referências

**Conceitos**
- [[PIC — A]]
- [[PIC — B]]

**Padrões**
- [[Pattern — A]]

**Sínteses**
- [[Permanent — A]]

**Princípios**
- [[Principle — A]]

**Tensões**
- [[Tension — A]]

## Próximo passo
→ Quando coverage: dominado → `/synthesize --draft "<tema>"`
```

## Campo `coverage`

| Valor | Significado operacional |
|---|---|
| `rascunho` | Tópico criado, prosa escrita, mas conteúdo ainda não estudado sistematicamente |
| `em-estudo` | Em revisão ativa — relendo e testando o entendimento |
| `dominado` | Essência escrita com confiança; sinal de prontidão para `/synthesize --draft` |

---

## Regras

- Tópico explica e organiza — não faz teses. Teses ficam na Permanent; o Tópico prepara o terreno para elas
- A Essência é prosa inteligível sem abrir as notas — quem lê entende o tema pelo parágrafo sozinho
- Cada seção é autossuficiente: o leitor deve entender o conteúdo sem precisar clicar em nenhum link
- Nenhum link inline no corpo — todos os links ficam no bloco `## Referências` ao final
- Linguagem simples (Feynman): explique como ensinaria alguém inteligente que não conhece o tema. Jargão inevitável deve ser definido em contexto, na primeira ocorrência
- Exemplos concretos antes de abstrações — o que é tangível ancora o que é conceitual
- Pontos contraintuitivos merecem destaque — não os enterre em lista; dê-lhes parágrafo próprio
- Nunca crie Tópico se já houver Permanent bem estabelecida e sem lacunas sobre o mesmo tema — a Permanent é mais completa e já cumpre o papel
- `coverage: dominado` é o sinal de prontidão para `/synthesize --draft` — sem esse sinal, a síntese pode ser prematura
- Tópico pode ter `requer:` apontando para outros Tópicos que devem ser lidos antes — use para criar trilha de aprendizado
- O id é gerado com o timestamp do momento da criação
- Todo título/filename criado por este fluxo usa o prefixo `Tópico —`
- Após salvar o Tópico, sempre atualizar `vault/Navigation/MOC/MOC — Tópicos.md`
