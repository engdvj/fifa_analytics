# Skill: /project-agent

Lê projetos ativos, decisions e checklists e produz visão de próximos passos, pendências, riscos e gatilhos de Application por projeto.

## Uso

```
/project-agent [<nome do projeto>] [--all]
```

- `<nome do projeto>` — foca em um projeto específico (busca por título parcial)
- `--all` — varre todos os projetos com status ativo
- Sem argumento — lista projetos ativos e pergunta qual analisar

## Comportamento

### Passo 1 — Mapear projetos

Leia `vault/Action/Projects/` e liste projetos cujo `status:` não seja `concluído`, `cancelado` ou `arquivado`.

Se `--all`, processe todos. Se `<nome>`, localize por título. Sem argumento, liste e aguarde escolha.

### Passo 2 — Para cada projeto

1. Leia a nota do projeto completa.
2. Leia o `brief:` de origem em `vault/Action/Brief/`.
3. Leia as decisions vinculadas em `vault/Action/Decision/` com `status: ativa`.
4. Leia checklists abertos em `vault/Operations/Checklists/` relacionados ao projeto.
5. Se houver `situation:` de origem, verifique se a situação foi resolvida ou ainda está ativa.
6. **Para identificar lacunas de conhecimento:** extraia os termos técnicos e conceitos centrais do projeto e do brief; Grep cada um nos índices em `vault/indexes/`. O que não tiver PIC, Literature ou Permanent correspondente é candidato a lacuna.

### Passo 3 — Produzir relatório por projeto

```
## Projeto — <título>

**Status:** <status atual>
**Brief de origem:** [[Brief — X]]
**Decisions ativas vinculadas:** [[Decision — A]], [[Decision — B]]
**Situação de origem:** [[Situation — Z]] — <ativa | resolvida>

### Próximos passos

1. <passo concreto derivado do brief, checklist ou decision>
2. <passo concreto>

### Pendências

- <item pendente com contexto ou gatilho>
- <item que estava no checklist mas não tem progresso visível>

### Riscos

- <risco identificado a partir de Tensions vinculadas ou Limitações de Permanents relacionadas>

### Gatilhos de Application

- [[Decision — A]] pode ser testada em <contexto concreto do projeto> → /reflect --application
- <aprendizado acumulado que ainda não virou Application mas deveria>

### Lacunas de conhecimento

- <tema sem PIC, Literature ou Permanent no vault que bloquearia ou enriqueceria o projeto>
- Sugestão: /radar "<tema>" ou /ingest se já houver fonte
```

### Passo 4 — Resumo consolidado (com --all)

```
## Visão geral de projetos — <data>

| Projeto | Status | Próximo passo prioritário | Gatilho de Application |
|---|---|---|---|
| [[Project — A]] | em andamento | <passo> | [[Decision — X]] |
| [[Project — B]] | bloqueado | <dependência> | — |

Projetos sem checklist ativo: [[Project — C]], [[Project — D]]
Decisions sem application há mais de 60 dias: [[Decision — Y]]
```

## Limite

Não altera notas de projeto, decision ou checklist. Não cria Application, Brief ou Decision automaticamente. Produz diagnóstico e lista de próximos passos para o usuário decidir. Para criar Application, use `/reflect --application`. Para criar novo Brief, use `/brief`.
