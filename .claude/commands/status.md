# Skill: /status

Exibe o estado atual do vault em formato compacto — o que está pendente, aberto ou aguardando ação.

## Uso

```
/status
```

Sem flags. Roda sempre completo.

## Comportamento

Execute as buscas abaixo em paralelo e monte o relatório final.

### 1 — Fleetings ativas

Glob recursivo em `vault/Capture/Fleeting/` por `*.md`.

Liste cada arquivo com domínio e nome. Fleetings ativas = pendentes de ingestão ou descarte.

### 2 — Research aberto

Glob em `vault/Knowledge/Research/Active/` por `*.md`.

Liste cada radar com nome. Se vazio: "nenhum".

### 3 — Handoffs ativos

Glob em `vault/Knowledge/Handoffs/Active/` por `*.md`.

Para cada handoff, leia apenas as primeiras 30 linhas e extraia:
- `## Estado do handoff` → status e próximo gatilho
- Pendências explícitas (ações mencionadas como "manter na fila", "aplicar", "criar tensão")

### 4 — Permanents tensionadas

Grep por `status: tensionada` em `vault/Knowledge/Permanent/` recursivo.

Liste com título curto (sem o prefixo "Permanent —"). Se nenhuma: "nenhuma".

### 5 — Principles sem Decision

Grep por `type: principle` em `vault/Knowledge/Principle/` → coleta nomes.
Grep por `principles:` em `vault/Action/Decision/` → coleta quais principles aparecem.
Subtraia: principles sem nenhuma Decision vinculada.

Se todos tiverem Decision: "todos cobertos".

### 6 — Decisions sem Application

Grep por `type: decision` em `vault/Action/Decision/` → conta total.
Glob em `vault/Action/Application/` → conta total de Applications.

Se Applications = 0: reportar "N decisions — nenhuma application".
Se Applications > 0: grep por `decision:` em `vault/Action/Application/` → quais decisions estão cobertas.

### 7 — Checklists abertos

Glob em `vault/Operations/Checklists/` por `*.md`. Liste os que existirem.

---

## Formato do relatório

```
## Vault status — <data YYYY-MM-DD>

### Fleetings ativas  (<N>)
- [<domínio>] <título>
- ...

### Research aberto  (<N>)
- <nome> ou "nenhum"

### Handoffs ativos  (<N>)
- [[<Handoff>]] — próximo gatilho: <gatilho>
  pendências: <lista curta>

### Permanents tensionadas  (<N>)
- <título curto> ou "nenhuma"

### Principles sem Decision  (<N>)
- <título curto> ou "todos cobertos"

### Decisions sem Application
- <N> decisions — <M> applications

### Checklists abertos  (<N>)
- <nome> ou "nenhum"
```

## Regras

- Não leia arquivos inteiros desnecessariamente — use Glob e Grep para contar e listar; leia apenas o mínimo (primeiras linhas) quando precisar de contexto
- Não proponha ações nem sugira próximos passos — apenas reporta o estado
- Não rode sub-skills automaticamente
- Se uma pasta não existir, reporte "0" para aquele item sem erro
