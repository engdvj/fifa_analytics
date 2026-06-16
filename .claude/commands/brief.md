# Skill: /brief

Mobiliza todo o vault para entender um problema, tema ou situação. Não é síntese de fontes — é pensamento estruturado com o vault como parceiro. O resultado é sempre acionável: decisions, applications e/ou um project de execução.

## Posição no fluxo

```
[Todo o vault — qualquer tipo de nota]
            ↓
          Brief        ← entende o problema com o que já se sabe
            ↓
 Decision / Application → Project (se exigir execução sustentada)
            ↓
       Application → novo Fleeting
            ↓
 triagem de Research/Handoff usado
            ↓
 /ingest → /synthesize → /reflect
```

O `brief` é o ponto de entrada para **usar** o vault, não para construir mais conhecimento. A diferença:
- `synthesize` → constrói conhecimento a partir de informação
- `reflect` → extrai convicções e decisões do conhecimento
- `brief` → **resolve** um problema usando tudo que o vault acumulou

## Uso

```
/brief "<problema, tema ou situação>"
```

Exemplos:
- `/brief "como estruturar um sistema de dados para uma startup early-stage"`
- `/brief "entender por que nosso dashboard não está sendo usado"`
- `/brief "qual abordagem de ensino faz mais sentido para este conteúdo"`

---

## Comportamento

### 1. Receber e clarificar o problema

Reescreva o problema em uma frase precisa:
- **Tipo**: compreensão (entender algo), decisão (escolher entre opções) ou execução (como fazer algo)
- **Escopo**: o que está dentro e fora da pergunta
- **Critério de resolução**: como saberemos que o brief foi resolvido?

### 2. Varrer o vault

**2a. Liste os candidatos** — Grep os índices em `vault/indexes/` e liste títulos de notas relevantes ao problema (de qualquer tipo: pic, permanent, principle, decision, application). Não leia conteúdo ainda.

**Âncora:** um problema bem delimitado tipicamente envolve 3–8 notas do vault. Se listou menos de 2, expanda as palavras-chave da busca; se listou mais de 15, filtre pelas diretamente relacionadas ao problema central.

**2b. Leia os candidatos** — leia cada nota identificada na íntegra.

**2c. Mapeie a cobertura** — registre o que o vault cobre diretamente, o que cobre parcialmente e o que está descoberto. Este mapa alimenta a seção **Tensões e lacunas** do brief; não aparece no documento final, mas deve ser completado antes de escrever.

### 3. Construir o brief

O brief é um documento profissional de análise e recomendação. Deve ler como o pensamento claro de alguém que conhece profundamente o problema — não como citações de notas ou referências ao sistema de conhecimento. O vault informa o raciocínio; não aparece como autor.

**Regras de linguagem**:
- Nunca use "o vault sabe", "o vault sugere", "o brief anterior dizia", "conforme os princípios do vault"
- Nunca use citações inline estilo `([[nome da nota]])` no corpo do texto
- Links para notas do vault ficam apenas na seção **Referências** ao final — para rastreabilidade, fora da análise
- O conhecimento do vault aparece como análise direta: "Os controles paralelos de cada setor são shadow systems — não o problema a eliminar, mas a inteligência a incorporar", não "segundo o princípio X, shadow systems são..."
- A voz é sempre do analista sobre o problema, nunca do sistema sobre si mesmo

Estrutura do documento:

```
## Problema
[Reescrita precisa do problema + tipo + critério de resolução]

## Análise
[Diagnóstico da situação. Prosa densa e direta, sem subcabeçalhos excessivos.
Integra o conhecimento do vault como raciocínio próprio, sem citá-lo.]

## Tensões e lacunas
[Onde a análise cria tensão entre caminhos possíveis, e o que ainda não se sabe]

## Síntese
[A resposta, recomendação ou ordem de operação — denso, com posição, acionável]

## Saídas propostas
[Lista de decisions, applications e/ou project que emergem deste brief]

## Referências do vault
[Links para as notas que informaram a análise — para rastreabilidade, não para leitura inline]
```

### 4. Propor saídas concretas

Todo brief termina com pelo menos uma saída acionável:
- **Decision**: se o brief resolve uma escolha entre opções
- **Application**: se o brief identifica uma oportunidade de teste imediato
- **Project**: se a execução exige planejamento sustentado com prazo e etapas

Quando o brief usar Radar/Handoff originado em uma Situation, adicione também uma triagem de aproveitamento intelectual:

- Fontes que só sustentaram a decisão do caso → manter como `referência`.
- Fontes com método, norma, taxonomia, conceito ou evidência reutilizável → encaminhar para `/ingest`.
- Fontes que tensionam nota existente → encaminhar para `/tension` ou revisão.
- Aprendizado que só aparecerá na execução → registrar como futura `Application`.
- Candidatos a `Permanent` e `Principle` ficam como backlog; só avançam depois de PICs, tensions ou applications.

Pergunte ao usuário quais saídas quer criar antes de redigir.

### 5. Salvar

**Gate de linguagem — aplique antes de apresentar o rascunho ao usuário:**
Releia o documento e elimine qualquer frase que:
- mencione "o vault", "o vault sabe", "o vault sugere", "conforme o princípio X", "conforme os princípios do vault"
- use citações inline com `([[nome da nota]])` no corpo do texto
- use "o brief anterior dizia", "o sistema indica" ou qualquer construção que faça o vault aparecer como autor
A voz é sempre do analista sobre o problema — o vault informa o raciocínio, não aparece como fonte citada.

Após aprovação do brief: salve em `vault/Action/Brief/Brief — <título>.md`

Após aprovação das saídas:
- Crie as notas em seus respectivos diretórios
- Para cada `decision` criada: atualize `vault/Navigation/MOC/MOC — Decisões.md`
  - Leia o MOC atual
  - Determine a seção temática pelo domínio do brief:
    - Brief sobre dados/informação → seção "Dados e Informação"
    - Brief sobre TI e sociedade → seção "TI e Sociedade"
    - Brief sobre SI e organizações → seção "Sistemas de Informação Organizacional"
    - Brief sobre contexto específico (ex: hospital) → seção própria pelo nome do contexto
  - Adicione cada decisão no formato `- [[Decision — título]] — <descrição em meia linha>`
  - Inclua referência à fonte: `Derivadas de [[<brief de origem>]]`
- Execute `/commit` ao final cobrindo todos os arquivos criados na sessão

---

## Frontmatter do `brief`

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: brief
title: Brief — <o problema em forma nominal — ex: "Estrutura de Dados para Startup Early-Stage">
created: <YYYY-MM-DD>
tags: []
status: aberto|em-progresso|resolvido|suspenso
outputs: [[[decision 1]], [[project 1]], ...]
---
```

## Frontmatter do `project` (reformulado)

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: project
title: Project — <o que será executado>
created: <YYYY-MM-DD>
tags: []
status: planejamento|ativo|pausado|concluído|cancelado
brief: [[brief que originou este projeto]]
principles: [[[principle 1]], ...]
decisions: [[[decision 1]], ...]
deadline: <YYYY-MM-DD ou null>
---
```

**Corpo do project**:

```
**Objetivo**: o que este projeto entrega ao ser concluído — concreto e verificável.

**Contexto**: por que existe — link para o brief que o originou e o problema que resolve.

**Etapas**:
- [ ] Etapa 1
- [ ] Etapa 2
- ...

**Critério de conclusão**: como saberemos que está pronto.

**Riscos**: o que pode travar ou invalidar o projeto.

**Conexões**
- [[brief de origem]]
- [[decisions que guiam a execução]]
```

---

## Regras

- O brief nunca termina em análise pura — sempre propõe saídas acionáveis
- Brief não transforma Radar/Handoff diretamente em `Literature`, `PIC`, `Permanent` ou `Principle`; ele pode classificar o aproveitamento e encaminhar para os fluxos adequados.
- Brief originado em Situation deve diferenciar saída de ação (`Decision`, `Project`, `Application`) de absorção intelectual posterior (`/ingest`, `/synthesize`, `/reflect`).
- Síntese do brief deve ter posição: não "existem dois lados", mas "a resposta é X"
- Se aspectos críticos do problema não têm cobertura analítica suficiente, sinalize na seção de tensões e lacunas
- Se o problema for muito amplo para um único brief, proponha dividir em sub-briefs menores antes de continuar
- `project` sem `brief:` no frontmatter indica projeto sem fundamentação — avisar o usuário
- O id é gerado com o timestamp do momento da criação
- Todo título/filename criado por este fluxo usa o prefixo do tipo: `Brief —`, `Decision —`, `Application —` ou `Project —`.
