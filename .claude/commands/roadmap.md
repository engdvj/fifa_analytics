# Skill: /roadmap

Cria e mantém um plano de estudo executável sobre um tema: etapas sequenciais com checkboxes, critérios de conclusão por etapa e diagnóstico do vault como base. O mapa é salvo em `vault/Operations/Status/` e atualizado conforme o tema avança — deletado quando dominado.

## Posição no fluxo

```
Você quer estudar ou dominar um tema
            ↓
        /roadmap       ← cria o plano de execução
            ↓
  você executa etapa por etapa
  (ingest, topic, synthesize, reflect…)
            ↓
     /roadmap --revisao ← marca o que foi feito, revela próxima etapa
            ↓
     tema dominado → deletar o mapa
```

Diferente de `/situation` (parte de problema real), `/topic --scan` (lista clusters) e `/maturity` (olha permanents paradas): o roadmap parte de um tema de estudo, mapeia o vault e entrega um plano sequencial rastreável.

## Uso

```
/roadmap "<tema>"           ← cria plano completo para um tema
/roadmap --domain <domínio> ← panorama de todo um domínio
/roadmap --gaps             ← só os gaps críticos, sem salvar (ação rápida)
/roadmap --revisao "<tema>" ← atualiza checkboxes e descobre próxima etapa
```

---

## Comportamento: `"<tema>"` e `--domain`

### Passo 1 — Delimitar o escopo

1. Se `"<tema>"` for recebido, pergunte (ou infira pelo contexto):
   - Qual é o objetivo? (`entender` / `aplicar` / `sintetizar` / `dominar`)
   - Há Tópico, MOC ou Literature já identificados como ponto de partida?
   - Se o tema for muito amplo (ex: "Administração"), proponha delimitação antes de prosseguir.
2. Se `--domain` for recebido, use o domínio para escopo global e infira subáreas pelos MOCs e índices.

### Passo 2 — Varrer o vault

**Fontes a ler (nesta ordem, mínimo necessário de cada):**

1. **Índices de PIC do domínio** em `vault/indexes/INDEX-PIC-<domínio>.md` — título, tags, wikilink.
2. **Índice de Literature** em `vault/indexes/INDEX-Literature.md` — filtrar por domínio e tags do tema.
3. **MOC do domínio** em `vault/Navigation/MOC/Conteúdo/<domínio>/` — seções e entradas.
4. **`_Candidatos-<DOMINIO>.md`** em `vault/Navigation/Tópicos/` — candidatos pendentes e Tópicos existentes com coverage. Leia apenas o arquivo do domínio relevante.
5. **Índice de Permanents** em `vault/indexes/INDEX-Permanent.md` — filtrar por domínio.
6. **Índice de Tensions** em `vault/indexes/INDEX-Tension.md` — tensions abertas no tema.
7. **Research/Active** via grep — fontes enfileiradas sobre o tema.

Para notas relevantes, leia apenas frontmatter + primeiras 30 linhas.

### Passo 3 — Avaliar profundidade

**Literature:**
- `sólida` — seções completas, PICs gerados, MOC vinculado
- `rasa` — poucas seções, PICs ausentes ou frontmatter incompleto
- `enfileirada` — em Research/Active, não ingerida

**Tópico:** usar o campo `coverage:` (rascunho / em-estudo / dominado)

**Permanent:**
- `consolidada` — `status: consolidada`, sources completo, sem Tension aberta
- `em-formação` — status em-formação há menos de 30 dias
- `parada` — em-formação há mais de 30 dias ou tensionada sem resposta

### Passo 4 — Identificar gaps

Separe claramente:
- **Gap identificado**: ausência detectada no vault (seção sem PIC, Tension sem resposta, cluster sem Tópico, Literature rasa).
- **Gap inferido**: ausência sugerida pelo tema — marque sempre como `[inferido]`.

**Como inferir gaps:**
1. Blocos conceituais que qualquer fonte séria do tema cobriria e que não aparecem no vault.
2. Literatures com seções sem PICs correspondentes.
3. Tensions abertas sem PIC ou Permanent respondendo.
4. Clusters de candidatos catalogados mas sem Tópico.
5. Conceito avançado no vault sem o fundamento que o sustenta.

### Passo 5 — Montar as etapas

Organize o plano em etapas sequenciais. Cada etapa deve:
- Ter entre 2 e 5 ações concretas (checkboxes)
- Ter um critério de conclusão explícito ("Concluída quando: X")
- Respeitar a sequência epistemológica: fonte → PIC → Tópico → Permanent → Principle
- Não propor síntese sem Tópico dominado; não propor Tópico sem PICs suficientes

**Tabela de ações por situação:**

| Situação | Ação |
|---|---|
| Literature rasa ou não ingerida | `/ingest --literature "<título>"` |
| Fleeting em Research/Active | `/ingest` |
| PICs prontos, sem Tópico | `/topic --pick <código>` ou `/topic --draft "<tema>"` |
| Tópico em rascunho | Ler o Tópico → `/topic --coverage em-estudo` |
| Tópico em-estudo | Aprofundar → `/topic --coverage dominado` |
| Tópico dominado, sem Permanent | `/synthesize --draft "<tema>"` |
| Tensions abertas bloqueando síntese | `/maturity` ou `/reflect` |
| Gap identificado sem fonte | `/radar "<conceito>"` |
| Gap inferido | Avaliar se já sabe; se não: `/radar "<conceito>"` |

**Número de etapas:** entre 3 e 6. Menos de 3 indica tema estreito demais para roadmap; mais de 6 indica que deve ser dividido em dois roadmaps.

### Passo 6 — Montar diagnóstico compacto

O diagnóstico (o que existe, o que está incompleto, gaps) vai em bloco colapsável no final do arquivo — útil para consulta mas não é o foco visual. Inclua:
- O que existe e está sólido (Literature, PICs, MOCs, Patterns prontos)
- O que está incompleto (Tópicos em rascunho, Permanents paradas, Tensions abertas)
- Gaps identificados e inferidos
- Conexões laterais relevantes de outros domínios

### Passo 7 — Apresentar e salvar

Apresente o rascunho completo para aprovação. Após aprovação, salve em:
`vault/Navigation/Roadmaps/<domínio>/Roadmap — <tema>.md`

Após salvar, adicione entrada em `vault/Navigation/MOC/MOC — Roadmaps.md` sob o domínio correspondente:
`- [[Roadmap — <tema>]] — objetivo: <objetivo> | etapa atual: 1 — <nome da etapa 1>`

---

## Formato do mapa

```markdown
---
id: <timestamp YYYYMMDDHHmmss>
type: roadmap
title: Roadmap — <tema>
created: <YYYY-MM-DD>
domain: <domínio(s)>
objetivo: entender | aplicar | sintetizar | dominar
status: ativo
etapa-atual: 1
---

## Progresso

**Objetivo:** <objetivo>
**Tema dominado quando:** <critério final — ex: Permanent consolidada + 3 Tópicos dominados + Tensions respondidas>

| Etapa | Descrição | Status |
|---|---|---|
| 1 | <nome curto> | ⬜ pendente |
| 2 | <nome curto> | ⬜ pendente |
| 3 | <nome curto> | ⬜ pendente |
| ... | | |

---

## Etapa 1 — <nome>

- [ ] <ação concreta com skill ou link de nota>
- [ ] <ação concreta>
- [ ] <ação concreta>

**Concluída quando:** <critério verificável — ex: "3 Tópicos com coverage: em-estudo">
**Próxima etapa:** Etapa 2

---

## Etapa 2 — <nome>

- [ ] <ação>
- [ ] <ação>

**Concluída quando:** <critério>
**Próxima etapa:** Etapa 3

---

[demais etapas no mesmo formato]

---

## Diagnóstico do vault

<detalhes block — pode ser lido para entender o estado mas não é o foco operacional>

### Sólido
- [[Literature — X]] — sólida, N seções ingeridas
- [[MOC — X]] — bem estruturado, N PICs vinculados
- Patterns: N patterns em [[MOC — Modelagem Preditiva]]

### Incompleto
- [[Tópico — X]] — coverage: rascunho
- [[Permanent — X]] — tensionada, stage: base
- [[Tension — X]] — aberta, sem resposta

### Gaps identificados
- <gap verificado no vault>

### Gaps inferidos
- <gap inferido> [inferido]

### Conexões laterais
- [[Nota]] (domínio: X) — <relação clara com o tema>

### Critério de encerramento
Deletar quando: <critério específico> → remover entrada de `MOC — Roadmaps.md`.
Próxima revisão: `/roadmap --revisao "<tema>"`
```

---

## Comportamento: `--revisao "<tema>"`

1. Leia o `Roadmap — <tema>.md` em `vault/Operations/Status/`.
2. Identifique a etapa atual pelo campo `etapa-atual:` no frontmatter.
3. Para cada item da etapa atual, verifique o estado real no vault:
   - Tópico com coverage mudou? → marcar checkbox como `[x]`
   - Literature ingerida? → marcar checkbox como `[x]`
   - Permanent criada ou avançou de stage? → marcar checkbox como `[x]`
4. Se todos os checkboxes da etapa atual estiverem marcados:
   - Marque a etapa como `✅ concluída` na tabela de progresso
   - Avance `etapa-atual:` para a próxima etapa
   - Destaque a próxima etapa a ser trabalhada
5. Se o critério final de domínio for atingido: proponha deletar o arquivo e remover a entrada de `MOC — Roadmaps.md`.
6. Se houver novos gaps descobertos desde a criação: proponha adicioná-los ao diagnóstico ou como nova etapa.
7. Apresente o diff para aprovação antes de salvar.

---

## Comportamento: `--gaps`

Modo rápido. Não salva arquivo.

1. Execute os Passos 1–4 normalmente.
2. Apresente apenas:
   - Lista de gaps identificados (com referência à nota de origem)
   - Lista de gaps inferidos (marcados como `[inferido]`)
   - Próximas 3 ações prioritárias
3. Pergunte: "Quer o plano completo? `/roadmap "<tema>"`"

---

## Regras

- O foco visual do arquivo é o progresso e as etapas — o diagnóstico é suporte, não destaque
- Cada etapa tem critério de conclusão verificável; sem critério, não é etapa, é intenção
- `--revisao` não avança etapas por julgamento — só marca o que for verificável no vault
- Nunca afirme que gap inferido existe como fato — use sempre `[inferido]`
- Não crie PICs, Literature, Tópico ou qualquer nota substantiva — roadmap mapeia e orienta
- Não rode `/radar` automaticamente — apenas sugira; radar tem custo e exige decisão
- A trilha respeita a sequência epistemológica: não proponha síntese sem Tópico dominado
- Se o escopo for muito amplo (50+ PICs), divida em dois roadmaps separados por subárea
- Roadmap é transiente: deletar quando dominado; não acumular roadmaps antigos
- Conexões laterais só entram quando a relação com o tema for clara — não liste "pode ser relevante"
- Gaps inferidos são julgamento: se não houver confiança suficiente, não inclua
