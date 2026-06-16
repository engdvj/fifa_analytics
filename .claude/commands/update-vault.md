# Skill: /update-vault

Verifica e corrige dívida operacional do vault sem fazer síntese intelectual nova. O comando serve para manter navegação, rastreabilidade e higiene estrutural em todos os tipos de nota: MOCs, backlinks, maturidade mecânica, tensions, research, handoffs, decisions, applications, patterns, topics, tradeoffs, situations, briefs e projects.

## Uso

```text
/update-vault [--scan | --review | --auto | --apply]
```

- `--scan` — diagnóstico padrão. Analisa o vault, salva uma review nova em `vault/Operations/Reviews/Update Vault/` e não altera notas de conteúdo.
- `--review` — faz o scan, propõe um plano de correções e espera aprovação explícita antes de aplicar.
- `--auto` — faz scan e aplica apenas correções de baixa ambiguidade, registrando o que exigiria julgamento.
- `--apply` — aplica correções mecânicas e inequívocas já identificadas pelo scan ou pelo pedido do usuário.

Sem flag, use `--scan`.

## Limite do comando

`/update-vault` não cria tese, princípio, limitação, aprendizado de application, defesa de tradeoff, prosa de tópico ou qualquer interpretação nova. Quando encontrar uma pendência substantiva, registre no relatório e recomende a skill certa:

| Pendência encontrada | Skill recomendada |
|---|---|
| Permanent/principle parada, tensionada sem resposta, pronta p/ avançar | `/maturity` |
| Permanent ou principle precisa de Limitações/Relações/status | `/review` |
| Cluster maduro sem síntese; síntese tensionada/comparativa pendente | `/synthesize` |
| Princípio, decision ou application a destilar | `/reflect` |
| Objeção forte e reutilizável ainda não registrada | `/tension` |
| Fonte na fila de Research/Handoff pronta p/ absorver | `/ingest` |
| Lacuna de cobertura que exige fonte externa | `/radar` |
| PIC/Literature com código reutilizável sem Pattern | `/pattern --from-pic` |
| Cluster de PICs dominado sem Tópico curado | `/topic --draft` |
| Situação real recorrente sem Situation registrada | `/situation` |
| Brief sem saída concreta; próximo passo de projeto | `/brief`, `/project-agent` |

**Fronteira com `/maturity` e `/periodic-review`:** `/update-vault` cuida de **higiene mecânica** (frontmatter, backlinks, links de MOC, ciclo de vida de arquivos). Diagnóstico de **maturidade por julgamento** (o que está pronto para virar permanent/principle, qual tensão exige resposta) é de `/maturity`. Cadência temporal (applications antigas sem teste, decisions sem revisão na janela, research vencido) é de `/periodic-review`. Quando um achado for de julgamento ou de cadência, **aponte e delegue** — não resolva aqui.

## Modos de execução

### `--scan`

Objetivo: descobrir dívida e salvar um relatório persistente.

Faça:
- mapear notas formais e MOCs;
- listar inconsistências;
- separar correções mecânicas de pendências substantivas;
- salvar review nova com timestamp;
- responder no chat com o resumo do arquivo salvo.

Não faça:
- editar notas substantivas;
- mover arquivos;
- corrigir MOCs;
- alterar frontmatter.

### `--review`

Objetivo: transformar o scan em plano aplicável.

Faça:
- executar o mesmo diagnóstico de `--scan`;
- agrupar achados por tipo de ação;
- marcar cada item como `mecânico`, `triagem necessária` ou `substantivo`;
- propor os arquivos que seriam editados.

Pare antes de editar, salvo se o usuário já tiver pedido explicitamente para aplicar tudo.

### `--auto`

Objetivo: aplicar manutenção simples quando o risco é baixo.

Pode aplicar:
- backlinks faltantes já inferidos por `affects:`;
- links de MOC quando o PIC pertence claramente ao tema;
- movimentação de Research/Handoff quando o próprio arquivo ou MOC já indica estado fechado;
- normalização de seções operacionais vazias em MOCs com links existentes;
- atualização de documentação operacional.

Não aplique automaticamente:
- mudança de maturidade por julgamento;
- criação de `Permanent`, `Principle`, `Tension`, `Decision` ou `Application`;
- alteração de argumento de nota substantiva;
- ingestão ou descarte de fonte externa.

### `--apply`

Objetivo: executar correções mecânicas e inequívocas.

Use quando:
- um scan recente já listou os problemas;
- o usuário pediu explicitamente as correções;
- a ação não exige julgamento intelectual novo.

Antes de editar:
- crie checklist/status em `vault/Operations/` se o trabalho afetar múltiplos arquivos;
- confirme mentalmente que cada correção é rastreável a links, frontmatter ou MOCs existentes.

Depois de editar:
- valide os checks relevantes;
- consolide em `vault/Operations/Reviews/Update Vault/` quando houver registro operacional útil do próprio update-vault;
- remova checklist/status temporários ao fechar a operação.

## Passo 1 — Mapear o vault

Use busca recursiva sob as pastas do tipo. Não assuma arquivos na raiz de `Fleeting`, `Literature`, `PIC`, `Permanent`, `Principle` ou `Tension`.

Ao mapear áreas organizadas por domínio (`Capture/Fleeting`, `Archive/Fleeting`, `Literature`, `PIC` e `Permanent` em todos os níveis), trate novos subdiretórios como possíveis novas linhas de pensamento. Se o domínio novo for consistente e durável, valide se ele também foi documentado em `CLAUDE.md`, `AGENTS.md`, `.claude/commands/note-formats.md`, `.claude/commands/synthesize.md` e em MOC de conteúdo. Se parecer acidental, vazio ou pontual, registre como lacuna de organização.

Mapeie:
- `vault/Capture/Fleeting/` e `vault/Archive/Fleeting/` — domínio físico, título, status, tags e links;
- `vault/Knowledge/PIC/` — títulos, tags, created e links;
- `vault/Knowledge/Permanent/` — título, status, sources, synthesis-level, synthesis-stage, tags e links;
- `vault/Knowledge/Principle/` — título, status, confidence, sources, revisão e links;
- `vault/Knowledge/Tension/` — título, severity, affects, origin e links;
- `vault/Action/Decision/` — status, principles, revisão e links;
- `vault/Action/Application/` — status, decision, principle e aprendizado;
- `vault/Action/Brief/` — status, outputs e saídas concretas;
- `vault/Action/Projects/` — status, brief de origem e links;
- `vault/Knowledge/Pattern/` — language, context, domain, status, source e presença em MOC;
- `vault/Knowledge/Situation/` — status, domain, origin e conexões;
- `vault/Navigation/Tópicos/` — domain, coverage, moc e presença em [[MOC — Tópicos]];
- `vault/Navigation/Tradeoffs/` — domain, decisao, bloco Referências e presença em [[MOC — Tradeoffs]];
- `vault/Knowledge/Research/` e `vault/Knowledge/Handoffs/` — ciclo de vida operacional;
- `vault/Navigation/MOC/Conteúdo/` — cobertura de PICs, permanents e tensions por tema;
- `vault/Navigation/MOC/` — MOCs de fluxo (`MOC — Tópicos`, `MOC — Tradeoffs`, `MOC — Situações`, `MOC — Research`, `MOC — Handoffs`) refletem o conjunto real de notas do tipo.

## Passo 2 — Checks obrigatórios

> Execute todos os checks A–N antes de produzir o relatório. Não pule nenhum — marque cada letra concluída antes de passar à próxima. Um relatório com apenas A e B executados é diagnóstico incompleto. Os checks I–N cobrem patterns, topics, tradeoffs, situations, briefs e projects; se um tipo não tiver notas no vault, registre "sem notas do tipo" e siga.

### A) MOCs

Para cada MOC de conteúdo:
- identificar PICs claramente pertencentes ao tema e ausentes no MOC;
- identificar se `## Conhecimento sintetizado` está vazio apesar de haver permanents relevantes;
- identificar se `## Tensões abertas` está vazio apesar de haver tensions relevantes;
- classificar candidatos por clareza: `claro`, `triagem`, `fraco`.

Em `--apply`, adicione apenas candidatos `claro`. Candidatos por tag genérica entram no relatório, não no MOC.

**Densidade e candidatos a split:**

Para cada MOC de conteúdo, contar:
- número de seções temáticas (excluindo "Como usar", "Fontes", "Conhecimento sintetizado", "Tensões abertas" e "Conexões");
- número estimado de PICs linkados.

Marcar como **split candidato** quando qualquer condição for verdadeira:
- ≥ 6 seções temáticas com foco de uso claramente distinto (lentes, literaturas ou fluxos diferentes), OU
- ≥ 60 PICs linkados no mesmo MOC, OU
- presença de literaturas de sub-áreas muito distintas compartilhando o mesmo MOC-raiz.

Ao identificar split candidato, registrar em `## Candidatos a split de MOC` no relatório:
- proposta de fronteira (qual seção vai para qual MOC novo);
- PICs de fronteira que devem aparecer nos dois MOCs (não escolher um lado);
- se o novo MOC precisa de Literature nova ou se o conteúdo já existe;
- quais MOCs novos **não** devem ser criados ainda por falta de Literature ingerida no domínio.

Em `--apply` ou `--auto`, **nunca dividir MOC automaticamente** — apenas registrar como candidato no relatório.

### B) Permanents

Verifique:
- `status:` válido;
- `sources:` presente;
- `synthesis-level: cluster | bridge | architectural`;
- `synthesis-stage: base | tensioned | comparative`;
- `## Limitações` presente;
- se `status: tensionada`, há link direto para alguma `Tension`;
- se há novas conexões mecânicas óbvias vindas de tensions ou MOCs.

Não altere o argumento da permanent em `/update-vault`. Edite apenas frontmatter ou seções de conexão quando a correção for mecânica.

### C) Principles

Verifique:
- `status:` válido;
- `confidence:` presente;
- `sources:` presente;
- `## Limitações` presente;
- `## Revisão` presente;
- se `status: tensionada`, há link direto para alguma `Tension`;
- se aparece no grupo correto de [[MOC — Princípios]].

### D) Tensions

Para cada `Tension`, verifique:
- `affects:` aponta para notas existentes;
- cada permanent/principle em `affects:` está com `status: tensionada`;
- cada nota afetada tem backlink direto para a tension;
- `severity:` está em `leve | moderada | estrutural`;
- o corpo contém os rótulos obrigatórios atuais: `**Objeção**`, `**Argumento**`, `**Impacto**`, `**Resolução possível**`;
- há `## Conexões`.

Não exija headings `## Objeção`, `## Argumento`, `## Impacto` ou `## Resolução possível`; o padrão atual usa rótulos em negrito.

Para decisions afetadas por tension, preserve o status operacional e exija link em `## Revisão` ou `## Relações qualificadas`.

### E) PICs órfãos

Liste PICs que não aparecem em nenhum MOC e não aparecem em `sources:` de permanent.

Em `--apply`, não crie MOC nem permanent automaticamente. Sugira destino.

### F) Decisions e Applications

Liste:
- decisions `status: ativa` sem application apontando para elas;
- decisions sem `## Revisão` ou sem critério de revisão (sem isso é intenção, não decisão);
- applications `status: explorando` sem decision/principle de origem;
- applications `status: concluída` cujo `aprendizado` ainda não foi incorporado ou referenciado.

Não invente aprendizado nem critério de revisão. Apenas aponte a pendência. "Application antiga sem teste há muito tempo" é diagnóstico de cadência — delegue a `/periodic-review`, não trate como dívida mecânica aqui.

### G) Research

Verifique:
- radares em `Research/Active` têm entradas acionáveis;
- entradas têm `role:`, `prioridade:`, `destino:`, `relação:`, `gatilho:` e `decisão:` quando forem filas de fonte;
- radares já usados, ingeridos ou fechados estão em `Research/Resolved`;
- radares obsoletos estão em `Research/Archived` ou listados como candidatos a arquivamento;
- [[MOC — Research]] reflete o ciclo de vida.

Em `--apply`, mover de `Active` para `Resolved` apenas quando o estado fechado já estiver explícito no radar, handoff ou MOC.

### H) Handoffs

Verifique:
- handoffs ativos têm estado do handoff, pergunta de radar, síntese executiva, mapa de decisão, fontes na fila e próxima ação sugerida;
- handoffs integrados estão em `Handoffs/Completed`;
- handoffs superados estão em `Handoffs/Archived`;
- [[MOC — Handoffs]] está coerente.

### I) Patterns

Para cada `Pattern` em `vault/Knowledge/Pattern/<domínio>/`, verifique:
- `language:`, `context:` e `domain:` presentes (sem os três é trecho, não padrão);
- `status:` em `rascunho | estável | superado`;
- `source:` aponta para Literature ou PIC existente **quando houver origem rastreável** (campo opcional — não exigir quando o pattern não tem origem no vault);
- pattern aparece no MOC de conteúdo do seu domínio (pattern órfão de MOC entra no relatório);
- pattern com `status: superado` não foi deletado — confirme que continua arquivado como histórico.

Não promova `rascunho → estável` em `/update-vault`: a transição exige teste real (julgamento). Apenas registre patterns `rascunho` antigos como candidatos a validação via `/reflect --application`.

### J) Topics

Para cada `Tópico` em `vault/Navigation/Tópicos/<domínio>/`, verifique:
- `domain:` e `coverage:` presentes; `coverage:` em `rascunho | em-progresso | dominado`;
- `moc:` aponta para o MOC de conteúdo do domínio;
- o corpo termina com bloco `## Referências` (tópico sem referências é incompleto);
- o tópico aparece em [[MOC — Tópicos]] sob o domínio correto (a regra do vault exige atualizar esse MOC após salvar tópico);
- `permanent:` foi preenchido se já existe síntese de origem; caso contrário, o campo pode estar ausente.

Tópico com `coverage: dominado` sem permanent vinculada é **candidato a `/synthesize --draft`** — registre como pendência substantiva, não corrija aqui. Não escreva nem reorganize a prosa do tópico (é conteúdo substantivo).

### K) Tradeoffs

Para cada `Tradeoff` em `vault/Navigation/Tradeoffs/<domínio>/`, verifique:
- `domain:` e `decisao:` presentes (a escolha vencedora em poucas palavras);
- a estrutura fixa do corpo: `## O problema` → `## As alternativas` (uma subseção por abordagem) → `## Onde ainda falha` → `## Referências`;
- o bloco `## Referências` aponta para os PICs atômicos das abordagens e para a Tension da objeção central, quando houver;
- o tradeoff aparece em [[MOC — Tradeoffs]] sob o domínio correto (regra do vault exige atualizar esse MOC após salvar tradeoff).

Não altere a defesa nem a escolha do tradeoff (é micro-tese de engenharia, substantiva). Apenas frontmatter, link de MOC e referências mecânicas.

### L) Situations

Para cada `Situation` em `vault/Knowledge/Situation/`, verifique:
- `domain:` e `origin:` preenchidos (sem isso é comentário solto, não situação);
- `status:` em `ativa | latente | resolvida | arquivada`;
- `origin: literatura` linka à fonte em `## Conexões → Fontes`;
- `origin: experiência` linka a pelo menos um Brief ou Decision em `## Conexões → Ações vinculadas`;
- a situação aparece em [[MOC — Situações]].

Situation `ativa`/`latente` sem nenhum Radar, Brief ou Decision de saída é **candidata a `/radar` ou `/brief`** — registre como pendência, não force a saída aqui.

### M) Briefs

Para cada `Brief` em `vault/Action/Brief/`, verifique:
- `status:` presente;
- `outputs:` não está vazio quando `status` indica brief ativo/concluído (brief sempre termina em saídas concretas: decisions, applications e/ou project — brief que fica só em análise é dívida);
- cada item de `outputs:` aponta para nota existente (decision, application ou project).

Brief ativo sem `outputs` é pendência substantiva: recomende `/brief` para fechar com saídas. Não invente as saídas.

### N) Projects

Para cada `Project` em `vault/Action/Projects/`, verifique:
- `brief:` presente, rastreando a origem (projeto sem brief não rastreia de onde veio);
- `status:` presente e atualizado;
- links de `principles:` e `decisions:` apontam para notas existentes;
- backlink: o brief de origem referencia o projeto em seus `outputs`.

Próximos passos, riscos e gatilhos de Application de projetos ativos são diagnóstico de `/project-agent` — delegue, não produza aqui.

## Passo 3 — Review de scan

Todo `--scan`, `--review`, `--auto` e `--apply` com diagnóstico deve salvar review quando produzir achados relevantes:

```text
vault/Operations/Reviews/Update Vault/Review — Vault Scan <YYYY-MM-DD HHmmss>.md
```

Não salve scans de update-vault diretamente na raiz de `vault/Operations/Reviews/`. A raiz é apenas contêiner de categorias.

Frontmatter:

```yaml
---
type: review
title: Review — Vault Scan <YYYY-MM-DD HHmmss>
created: <YYYY-MM-DD>
tags: [review, vault-scan, update-vault]
---
```

Estrutura mínima:

```markdown
# Review — Vault Scan <YYYY-MM-DD HHmmss>

## Resumo

- X MOCs com candidatos de atualização (+ N split candidatos).
- Y tensions com backlink faltante.
- Z notas tensionadas sem link direto para tension.
- Inconsistências de research e handoffs.
- Issues em decisions, applications, briefs e projects.
- Patterns sem `language/context/domain` ou órfãos de MOC.
- Topics/tradeoffs fora do MOC de fluxo correspondente.
- Situations sem `domain/origin` ou sem conexão exigida.

## Correções mecânicas possíveis

> Frontmatter, backlinks, links de MOC, ciclo de vida de arquivos. Aplicáveis em `--auto`/`--apply`.

## Pendências que exigem triagem

> Itens substantivos. Para cada um, indique a skill recomendada (ver tabela em "Limite do comando"): `/maturity`, `/review`, `/synthesize`, `/reflect`, `/tension`, `/ingest`, `/radar`, `/pattern`, `/topic`, `/situation`, `/brief`, `/project-agent`.

## Candidatos a split de MOC

## Delegado a outras skills

> Achados de maturidade por julgamento → `/maturity`. Achados de cadência temporal → `/periodic-review`. Não resolver aqui.

## Validações sugeridas
```

Se não houver achados, registre "Vault em dia" no arquivo e no chat.

## Passo 4 — Aplicar correções

Em `--auto` e `--apply`, siga estes limites:

- adicionar PIC em MOC apenas quando a seção correta for clara;
- adicionar permanent/tension em MOC apenas como link de navegação, sem criar argumento novo;
- adicionar backlink de tension usando `- tensionada por: [[Tension — ...]]`;
- adicionar topic/tradeoff faltante em [[MOC — Tópicos]] / [[MOC — Tradeoffs]] sob o domínio correto (link de navegação, sem escrever conteúdo);
- adicionar situation faltante em [[MOC — Situações]];
- adicionar pattern claramente pertencente ao tema no MOC de conteúdo do domínio;
- adicionar backlink do brief de origem no `outputs` quando o project já o referencia (e vice-versa);
- mover Research/Handoff apenas quando o estado estiver documentado;
- preservar conteúdo substantivo de notas;
- nunca escrever prosa de tópico, defesa de tradeoff, saída de brief ou aprendizado de application;
- nunca promover `status` de pattern, permanent, principle, situation, decision ou project (transição exige julgamento);
- nunca remover links existentes em MOCs;
- nunca apagar ou arquivar material sem sinal explícito de fechamento — pattern/decision/permanent `superado` é histórico, jamais deletar.

Validações recomendadas:
- backlinks de `affects:` para tension;
- notas `status: tensionada` com link direto para `Tension`;
- patterns com `language/context/domain`; topics em [[MOC — Tópicos]]; tradeoffs em [[MOC — Tradeoffs]];
- situations com `domain/origin` e conexão exigida pelo `origin`;
- briefs ativos com `outputs` não vazio; projects com `brief` e `status`;
- research fechado fora de `Active`;
- wikilinks dos arquivos alterados;
- `git diff --check`.
