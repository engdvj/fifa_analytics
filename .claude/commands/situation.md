# Skill: /situation

Registra situações reais ou potenciais, conecta ao conhecimento do vault e prepara o caminho para ação.

## Posição no fluxo

```
Experiência real ou problema implícito no vault
            ↓
        Situation      ← estrutura o contexto concreto
            ↓
    [vault check]      ← o que o vault já cobre
            ↓
  /radar (se gaps)     ← preenche lacunas antes de agir
            ↓
         /brief        ← analisa e decide com o vault como parceiro
            ↓
  Decision / Application → Project
            ↓
 triagem pós-brief/pós-project
            ↓
 /ingest → /synthesize → /reflect
```

## Uso

```
/situation "<descrição>"     ← registra situação a partir de relato
/situation --scan            ← identifica situações implícitas nos temas do vault
```

---

## Comportamento: relato ("descrição")

### 1. Estruturar a situação

A partir da descrição do usuário, identifique:
- **Tipo**: problema ativo (enfrenta agora), latente (pode acontecer), exploratório (quer entender antes de agir)
- **Domínio**: área técnica, organizacional ou pessoal onde ocorre
- **Origem**: `experiência` (vivenciada), `literatura` (problema que fontes abordam), ou `ambos`
- **O que está em jogo**: por que é difícil ou relevante — o que piora se não for resolvida

Se algum desses elementos for ambíguo, pergunte antes de rascunhar.

### 2. Varrer o vault

1. Grep os índices em `vault/indexes/` para identificar permanents, principles, PICs e tensions relevantes ao problema
3. Leia as notas identificadas na íntegra
4. Avalie a cobertura:
   - **boa**: vault tem permanents/principles diretamente aplicáveis → sugira `/brief` como próximo passo
   - **parcial**: vault cobre parte do problema → mapeie o que está descoberto, sugira `/radar` para lacunas específicas e ofereça `/brief` com o que existe
   - **fraca**: vault tem pouco material relevante → recomende `/radar` primeiro, depois `/brief`

### 3. Rascunhar a nota

Apresente o rascunho completo para aprovação antes de salvar:

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: situation
title: Situation — <título nominal curto>
created: <YYYY-MM-DD>
tags: []
status: ativa | latente
domain: <área>
origin: experiência | literatura | ambos
---
```

Corpo:

```markdown
## O problema

[O que é a situação — concreto, sem jargão.]

## O que está em jogo

[Por que é difícil ou relevante — o que muda se não for resolvida.]

## Conexões

**Conhecimento relevante**
- [[Permanent — ...]] — como se aplica
- [[Principle — ...]] — como orienta

**Lacunas identificadas**
- [Aspecto X não coberto pelo vault — candidato a /radar]

**Ações vinculadas**
(vazio — preencher após /brief)

**Fontes**
(vazio se origin: experiência)
```

### 4. Salvar e propor próximo passo

Após aprovação:
- Salve em `vault/Knowledge/Situation/Situation — <título>.md`
- Exiba o diagnóstico de cobertura e proponha:
  - Se cobertura boa → `/brief "<problema>"`
  - Se cobertura parcial → `/radar` para lacunas específicas + `/brief` com o que existe
  - Se cobertura fraca → `/radar` primeiro, depois `/brief`
- Quando houver radar ou handoff ligado à situação, registre que a absorção formal do material só acontece depois de uma triagem pós-brief ou pós-project:
  - `referência` → manter em Research/Handoff;
  - `Literature/PIC` → ingerir fonte reutilizável;
  - `Tension` → criar objeção quando fonte desafiar nota existente;
  - `Application` → registrar teste real após execução;
  - `Permanent/Principle` → criar apenas depois de maturação por PICs, tensions ou applications.

---

## Comportamento: --scan

### 1. Varrer o vault

1. Glob recursivo em `vault/Knowledge/Permanent/` → lista de permanentes
2. Glob recursivo em `vault/Knowledge/Principle/` → lista de princípios
3. Grep por `title:` em `vault/Knowledge/Situation/` → situações já registradas
4. Identifique permanents e principles sem situação vinculada

### 2. Inferir situações implícitas

Para cada permanent/principle sem situação, **priorizando**:
- permanents com `synthesis-stage: base` e `status: em-formação`
- principles com `confidence: médio` ou `alto`

Para cada candidato priorizado:
- Identifique o problema real que aquela nota resolveria se aplicada
- Avalie se é situação `experiência`, `literatura` ou `ambos`
- Avalie se é concreta o suficiente para valer um Brief

### 3. Propor candidatos

Apresente lista de candidatos:

```
## Situações implícitas identificadas

- **Situation — <título>** `origin: experiência | literatura | ambos` — <problema em uma linha> — baseada em: [[Permanent — ...]]
```

Aguarde o usuário selecionar quais quer formalizar.

### 4. Criar as selecionadas

Para cada situação selecionada:
- Redija o rascunho completo
- Aguarde aprovação individual ou em bloco
- Salve em `vault/Knowledge/Situation/Situation — <título>.md`
- Após salvar, proponha próximo passo: `/brief` ou `/radar`

---

## Regras

- Situation nunca é genérica — deve descrever contexto concreto onde o conhecimento do vault é aplicável
- `status: latente` para situações potenciais; `status: ativa` para situações que o usuário enfrenta agora
- `origin:` obrigatório — sem ele a situação não tem rastreabilidade
- `domain:` obrigatório — sem ele não há contexto de onde a situação ocorre
- Lacunas identificadas durante o relato são candidatos diretos a `/radar` — não ignore
- Lacunas de uma situação real devem alimentar ação primeiro; conhecimento formal vem depois de triagem explícita, não automaticamente.
- Itens qualificados em Research/Handoff não viram `Fleeting` por padrão. Use `Fleeting` apenas para insight bruto novo surgido durante o processo.
- `origin: literatura` deve linkar à fonte em `## Conexões → Fontes`
- `origin: experiência` deve linkar a pelo menos um Brief ou Decision após o fluxo avançar
- O id é gerado com o timestamp do momento da criação
- Todo título/filename usa o prefixo `Situation —`
