# Skill: /radar

Opera como radar externo do vault: encontra fontes, verifica acesso, salva o conteúdo real e registra o que foi capturado em `vault/Knowledge/Research/Active/`.

**Regra central:** fonte que não pode ser lida não entra no radar. O radar só registra o que já foi buscado e salvo.

```text
buscar → fetch da fonte original → salvar como Fleeting
→ registrar no radar (só o que tem Fleeting)
→ /ingest → Literature + PICs
→ arquivar Fleeting em Archive/Fleeting/<domínio>/
```

## Uso

```
/radar [<tema>] [--scan | --queue | --from-limitations]
```

- `<tema>` — tema, nota ou problema que orienta a busca
- `--scan` — levanta candidatas, tenta fetch, apresenta apenas o que foi capturado
- `--queue` — registra fontes capturadas no arquivo de radar em `vault/Knowledge/Research/Active/`
- `--from-limitations` — transforma limitações de permanents em perguntas de pesquisa externas
- Sem flag — faz `--scan` e aguarda confirmação antes de registrar

## Comportamento

### Passo 1 — Definir alvo

1. Identifique a nota, MOC, decision, tension ou projeto que motivou o radar.
2. Leia apenas o necessário no vault para entender:
   - tese ou decisão afetada;
   - lacuna de pesquisa;
   - tipo de fonte desejado.
3. Se o alvo for genérico demais, delimite por domínio, data ou pergunta.

### Passo 2 — Buscar, verificar acesso e salvar

Para cada fonte candidata identificada:

1. **Verifique se existe fonte primária acessível** — URL, documento público, arquivo local.
2. **Capture o conteúdo INTEGRAL da fonte — não um resumo.** A Fleeting é a fonte crua que será processada depois no `/ingest`; resumir aqui destrói a matéria-prima antes do processamento. Por isso:
   - **NÃO use `WebFetch` para capturar o conteúdo** — ele roda um modelo pequeno que **sumariza** a página antes de devolver (resumo de resumo) e recusa texto longo. Use-o no máximo para localizar a URL/verificar acesso, nunca como corpo da Fleeting.
   - **USE download direto via `Bash`:**
     - HTML (papers recentes, páginas): `curl -sL "<url>" -o doc.html` e extraia o texto (strip de tags). Para arXiv: `https://arxiv.org/html/<id>`.
     - PDF (papers antigos, relatórios): `curl -sL "<url-pdf>" -o doc.pdf && pdftotext doc.pdf doc.txt`.
     - arquivo local: `Read` direto.
   - Aplique apenas **limpeza mecânica mínima** ao texto extraído (remover números de página soltos, headers/rodapés repetidos, ruído de diagrama em `…`/`{}`). **Nunca condense, reescreva ou parafraseie o conteúdo** — o corpo da Fleeting é o texto extraído tal como veio.
3. **Se a captura falhar** (HTTP 4xx/5xx, paywall, PDF só-imagem/binário ilegível, JS pesado sem texto, arquivo físico sem cópia digital): **descarte a fonte.** Não registre no radar, não crie Fleeting, não mencione como pendente. Uma fonte inacessível não existe para o vault.
4. **Se a captura for bem-sucedida:** salve o texto integral extraído como Fleeting em `vault/Capture/Fleeting/<domínio>/Fleeting — <título>.md` antes de continuar.

Frontmatter da Fleeting:

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: fleeting
title: Fleeting — <título da ideia ou fonte>
created: <YYYY-MM-DD>
tags: [radar, <tema>]
status: em-formação
---
```

Corpo da Fleeting:

```markdown
> Texto integral extraído da fonte (com limpeza mecânica mínima). Conteúdo bruto para processamento no /ingest — não editado/condensado.

[Conteúdo INTEGRAL do documento, extraído via download direto (curl + pdftotext / strip de HTML) — o texto real e completo da fonte, na ordem em que aparece, não um resumo nem uma descrição. Preserve seções, equações, números e tabelas tal como extraídos. Aplique apenas limpeza mecânica (remover lixo de extração). Nunca incluir conexão com o vault, hipótese de destino, fonte-gatilho, próximo uso ou qualquer conteúdo que não esteja no documento.]

Fonte: <referência — autor/publicação/organização, ano, URL>
```

O volume importa: a Fleeting de um paper denso deve ter o conteúdo do paper (tipicamente dezenas de milhares de caracteres), não alguns parágrafos. Se a Fleeting ficou curta para uma fonte densa, a captura foi resumida indevidamente — refaça com download direto.

A conexão com o vault (o que afeta, qual nota tensiona, qual destino proposto) vive no registro de Research/Active, não na Fleeting.

Priorize fontes primárias e institucionais:

- normas, manuais e relatórios oficiais;
- artigos acadêmicos ou working papers com autoria clara;
- bases oficiais de dados;
- documentação técnica de ferramentas.

Evite:

- fonte sem autoria ou data;
- resumo de terceiros quando houver documento primário;
- notícia que não afeta nenhuma nota;
- fonte sem gatilho claro de ingestão ou descarte.

### Passo 3 — Montar pacote de fontes

**Apenas fontes com Fleeting salva entram no pacote.**

**Âncora de volume:** um radar típico inclui 3–5 fontes. Se fetchou apenas 1, verifique se a busca foi ampla o suficiente; se a escassez for real, documente-a explicitamente no pacote: "fontes primárias acessíveis sobre este tema são escassas — busca esgotada com N candidatas."

Apresente cada fonte assim:

```markdown
## Pacote radar — <tema>

### Fonte 1
- Fonte: [título](URL)
- Fleeting: [[Fleeting — <título>]]
- Role: foundation | frontier | evidence | tension | method | reference
- Afeta: [[Nota]]
- Limitação de origem: [[Permanent — X]] / <trecho ou seção>
- Relação com o vault: confirma | expande | tensiona | contradiz | atualiza | operacionaliza
- Por que entra: <1-2 frases>
- Gatilho: <data YYYY-MM-DD ou evento concreto>
- Prioridade: alta | média | baixa
- Destino provável: Literature | PIC | Tension | Application | referência
- Recomendação para Claude: <ignorar | manter na fila | ingerir | revisar nota | criar tensão | abrir aplicação>
```

### Passo 4 — Registrar em Knowledge/Research

Ao aprovar uma fonte:

1. Atualize ou crie `vault/Knowledge/Research/Active/Radar — <tema>.md`.
2. Atualize `vault/Navigation/MOC/MOC — Research.md` com origem, handoff, status e próximo gatilho.
3. Se houver pacote completo ou ciclo maior, salve ou atualize o handoff em `vault/Knowledge/Handoffs/Active/`.
4. Quando houver handoff, atualize `vault/Navigation/MOC/MOC — Handoffs.md`.

Formato da fonte no arquivo de radar:

```markdown
- **[Título](URL)** `role: <role>` `prioridade: alta|média|baixa` `destino: Literature|PIC|Tension|Application|referência` — afeta: [[Nota A]], [[Nota B]] — relação: confirma|expande|tensiona|contradiz|atualiza|operacionaliza — gatilho: <data ou evento> — decisão: <decisão de ingestão/descarte/revisão> — Fleeting: [[Fleeting — <título>]]
```

### Após o radar — fluxo de ingestão

Fontes registradas no radar com Fleetings salvas seguem para `/ingest`:

1. `/ingest` lê a Fleeting e cria `Literature` + PICs.
2. Após ingestão: marque `status: processed` na Fleeting e mova para `vault/Archive/Fleeting/<domínio>/`.
3. Mova o radar de `Research/Active` para `Research/Resolved` e atualize [[MOC — Research]].

Fontes com `destino: referência` ou `Application` não precisam de Fleeting e não passam por `/ingest`.

---

### Radar originado em Situation

Quando o radar nascer de uma `Situation`, serve a dois fins em tempos diferentes:

1. **Ação**: reduzir lacunas para o `/brief`, decisions e project.
2. **Conhecimento**: depois do brief ou da execução, selecionar o que merece virar `Literature`, `PIC`, `Tension`, `Application`, `Permanent` ou `Principle`.

O mesmo critério se aplica: só entra no radar o que foi fetchado. Fontes úteis apenas para o caso mas sem fetch viável permanecem como referência informal no Brief/Decision, nunca no radar.

Use esta classificação de aproveitamento ao registrar ou revisar o radar:

- `referência` — útil para o caso, mas sem conceito reutilizável forte; manter em Research/Handoff.
- `Literature/PIC` — fonte traz método, norma, taxonomia, conceito, evidência ou linguagem reaproveitável; encaminhar para `/ingest`.
- `Tension` — fonte desafia permanent, principle ou decision existente; encaminhar para `/tension` ou revisão.
- `Application` — a situação ou project testou uma decisão/princípio na prática; encaminhar para `/reflect --application`.
- `Permanent/Principle` — só depois de PICs, tensions ou applications amadurecerem a tese; não saltar direto do radar para princípio.

### Modo --from-limitations

Use quando o objetivo for tensionar uma permanent base antes de criar novas sínteses.

1. Leia recursivamente `vault/Knowledge/Permanent/` e priorize permanents com `synthesis-stage: base`.
2. Para cada permanent escolhida, leia:
   - `## Tese`;
   - `## Limitações`;
   - `## Conexões vivas`;
   - tensions ou research já vinculados.
3. Transforme cada limitação acionável em uma pergunta de radar:
   - limite técnico → buscar fonte técnica primária, documentação, paper ou livro avançado;
   - limite social/organizacional → buscar pesquisa, relatório institucional ou estudo de caso;
   - limite de segurança/governança → buscar norma, framework, relatório oficial ou incidente documentado;
   - limite conceitual → buscar fonte fundacional ou debate acadêmico.
4. Agrupe perguntas por trilha. Uma permanent pode gerar vários radares, um por limitação forte.
5. Para cada pergunta, tente o fetch antes de incluir no pacote. Limitação sem fonte acessível não gera entrada no radar — registre a lacuna na seção `## Limitações` da permanent ou sinalize para busca posterior.
6. Monte pacote com campos extras (apenas fontes fetchadas):

```markdown
## Pacote radar — limitações de [[Permanent — A]]

### Trilha 1 — <nome da limitação>
- Limitação de origem: <trecho da permanent>
- Pergunta de radar: <pergunta externa>
- Hipótese de tensão: <o que poderia contradizer ou limitar a tese>
- Destino provável: Research | Handoff | Tension | Literature/PIC
- Fleeting: [[Fleeting — <título>]]
```

7. Ao registrar, use `Radar — Limitações de <tema>` ou `Radar — <tema específico da limitação>`.
8. Se houver 3+ fontes relacionadas ou uma trilha crítica ampla, crie Handoff em `vault/Knowledge/Handoffs/Active/`.
9. Radar continua sem criar `Literature`, `PIC`, `Tension` ou `Permanent`; ele prepara a camada crítica.

---

## Regras

- **Fonte sem fetch bem-sucedido não entra no radar.** Não há "pendente", "inacessível" ou "para buscar depois" no arquivo de radar — só o que foi buscado e salvo existe.
- **Fleeting é o gatekeeper:** nenhuma entrada no arquivo de radar sem [[Fleeting — <título>]] correspondente com conteúdo real.
- Fontes com `destino: referência` ou `Application` são exceção: não precisam de Fleeting, apenas de registro em Research/Active.
- Após promover Fleeting para nota formal: marcar `status: processed` e mover para `vault/Archive/Fleeting/<domínio>/`.
- Quando uma fonte do radar virar `Literature`, a nota deve receber `ingest-flow: radar` e `research: [[Radar — <tema>]]` no frontmatter. Literature de ingestão direta usa `ingest-flow: normal` e não usa `research:`.
- Radar de Situation deve preservar a diferença entre fonte útil para decidir o caso e fonte madura para ingestão formal.
- Research guarda o mínimo acionável para decidir sem abrir o handoff; handoff guarda a análise longa.
- Quando um radar for ingerido/resolvido, mova de `Research/Active` para `Research/Resolved`; quando perder relevância, mova para `Research/Archived` ou apague se não houver valor de rastreabilidade.
- Quando um handoff for integrado, mova de `Handoffs/Active` para `Handoffs/Completed`; quando ficar superado, mova para `Handoffs/Archived`.
- Codex pode dizer que uma fonte tensiona ou contradiz uma tese, mas não altera a nota afetada nesse fluxo.
- Se a fonte for urgente ou mudar decisão ativa, sinalize no pacote, mas não altere a decision sem fluxo próprio.
