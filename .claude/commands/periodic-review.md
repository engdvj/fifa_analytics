# Skill: /periodic-review

Executa revisão periódica do vault v2 para priorizar manutenção epistemológica: maturidade, tensions, applications, decisions sem teste e research operacional.

## Uso

```
/periodic-review [--weekly | --monthly | --quarterly] [--apply]
```

- `--weekly` — revisão operacional curta
- `--monthly` — revisão de governança do vault
- `--quarterly` — revisão epistemológica mais profunda
- `--apply` — aplica apenas correções mecânicas inequívocas após apresentar relatório

Sem flag, execute `--monthly`.

## Revisão semanal

Verifique:

- fleetings não processados;
- literature em andamento;
- applications `explorando` ou `ativa` com gatilho próximo;
- itens de `vault/Knowledge/Research/Active/` vencidos;
- projects ativos com deadline ou status desatualizado.

Resultado esperado: relatório curto com próximos 3 movimentos.

## Revisão mensal

Verifique:

- permanentes e princípios `em-formação` mais antigos;
- notas `tensionada` sem movimento recente;
- tensions estruturais;
- decisions ativas sem application;
- applications concluídas sem aprendizado incorporado;
- Research operacional: ingerir, adiar ou descartar fontes pendentes por radar, priorizando `prioridade: alta` e gatilhos vencidos.
- Handoffs abertos: verificar se ainda têm próxima ação útil ou se devem virar resolvidos/arquivados.

Resultado esperado: atualizar `vault/Operations/Reviews/Periódicas/Revisão Periódica — <YYYY-MM>.md` com prioridades.

## Revisão trimestral

Verifique:

- principles com `confidence: baixo` sem application;
- permanentes com limitações genéricas;
- tensions recorrentes que indiquem revisão estrutural;
- tensions sem estrutura rígida ou sem resolução possível clara;
- decisions ativas que deveriam virar playbook, project ou ser canceladas;
- necessidade de promover `Output` de experimento manual para tipo formal.

Resultado esperado: plano de revisão substantiva, não edição automática.

## Apply

Com `--apply`, só execute correções mecânicas:

- os índices em `vault/indexes/` são atualizados automaticamente pelo hook;
- adicionar link de volta quando a relação já é explícita;
- marcar item vencido de `vault/Knowledge/Research/Active/` como pendente de decisão;
- registrar itens pendentes no arquivo de revisão periódica, não em arquivos Status/ separados.

Não invente limitações, aprendizado, nova tese ou mudança de maturidade sem leitura substantiva.
