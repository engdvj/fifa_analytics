# Skill: /maturity

Diagnóstico focado de maturidade epistemológica: varre permanents e principles em busca de notas paradas, tensionadas sem resposta, ou prontas para avançar. Produz fila de ação priorizada.

Este skill é complementar ao `/periodic-review`: onde o periodic-review faz varredura ampla do vault, o /maturity foca exclusivamente na camada de síntese (Permanent + Principle) e produz uma fila acionável por nota.

## Uso

```
/maturity [--scan | --queue | --apply]
```

- `--scan` — diagnóstico completo por nota, sem alterar nada, sem produzir fila
- `--queue` — produz fila de ação priorizada por nota (padrão)
- `--apply` — aplica apenas correções mecânicas: `## Limitações` ausente, `## Revisão` ausente, backlinks de tension faltantes, `sources:` vazio
- Sem flag — usa `--queue`

## Comportamento

### Passo 1 — Mapear

Varre recursivamente:
- `vault/Knowledge/Permanent/` — todos os níveis (Cluster, Bridge, Architectural) e todos os domínios
- `vault/Knowledge/Principle/` — todos os grupos

Para cada nota, leia apenas o frontmatter e as seções `## Limitações`, `## Revisão` e `## Conexões` ou `## Relações qualificadas`.

### Passo 2 — Avaliar por critério

| Critério | Classificação | Ação sugerida |
|---|---|---|
| `status: em-formação` + `created` há mais de 30 dias + sem tension vinculada | parada | revisar ou tensionar |
| `status: tensionada` + sem nota `Tension` vinculada em `affects:` | tensão implícita | criar nota Tension com /tension |
| `status: tensionada` + Tension existente + sem sinal de resolução | tensão aberta | decidir: revisão estrutural ou manter |
| `sources:` vazio ou ausente | rastreabilidade quebrada | completar sources |
| `## Limitações` ausente | estrutura incompleta | adicionar seção (mecânico) |
| `## Revisão` ausente em principle ou decision | estrutura incompleta | adicionar seção (mecânico) |
| `synthesis-stage: base` + 3 ou mais PICs do mesmo tema sem nova síntese | pronta para avançar | sugerir /synthesize |
| `confidence: baixo` em principle + sem application vinculada | princípio não testado | sugerir /reflect --application |
| `status: superada` aparecendo em MOC ativo | navegação quebrada | remover do MOC |

### Passo 3 — Saída --queue

```
## Fila de maturidade — <YYYY-MM-DD>

### Prioridade alta

- [[Permanent — X]] — em-formação há 45 dias, sem tension → revisar ou /synthesize
- [[Principle — Y]] — tensionada, sem Tension vinculada → /tension

### Prioridade média

- [[Permanent — Z]] — synthesis-stage: base, 4 PICs relacionados → /synthesize
- [[Principle — W]] — confidence: baixo, sem application → /reflect --application

### Mecânicos (aplicáveis com --apply)

- [[Permanent — A]] — ## Limitações ausente
- [[Principle — B]] — ## Revisão ausente
- [[Permanent — C]] — sources: vazio

### Sem ação necessária

- [[Permanent — D]] — estável, sources completo, Limitações presente
...

## Resumo

Total mapeado: N permanents + M principles
Prioridade alta: X | Prioridade média: Y | Mecânicos: Z | Sem ação: W
```

### Passo 4 — Aplicar com --apply

Aplica apenas os itens da lista **Mecânicos**:

- Adicionar `## Limitações\n\n[Sem limitações identificadas ainda.]` quando ausente
- Adicionar `## Revisão\n\nQuando revisar: [definir]\nO que mudaria este princípio: [definir]` em principles sem a seção
- Adicionar backlink `- tensionada por: [[Tension — X]]` quando `affects:` da Tension aponta para a nota mas a nota não tem o link de volta

Não altere argumento, status de maturidade ou tese. Reporte cada arquivo editado.

## Limite

Diagnóstico e correções mecânicas. Não muda status de maturidade por julgamento, não cria Permanent, Principle ou Tension, não decide o mérito de nenhuma tese.
