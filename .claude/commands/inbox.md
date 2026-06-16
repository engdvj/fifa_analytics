# Skill: /inbox

Classifica e triagem as fleetings ativas do vault. Produz uma decisão por item — ingerir, arquivar, manter ou descartar — sem criar conteúdo substantivo.

## Uso

```
/inbox [--domain <domínio>] [--apply]
```

- `--domain <domínio>` — restringe a análise a um domínio específico
- `--apply` — executa as ações mecânicas aprovadas (arquivar, descartar, marcar)
- Sem flag — diagnóstico com proposta de ação por item, aguarda aprovação antes de qualquer mudança

## Comportamento

### Passo 1 — Mapear inbox

Varre `vault/Capture/Fleeting/` recursivamente (ou o subdiretório de domínio se `--domain`). Coleta dois grupos:

- **Notas `.md`**: fleetings sem `status: processed`
- **Arquivos não-`.md`** (PDFs, etc.): todos os arquivos com extensão diferente de `.md`

Se não houver nenhum item nos dois grupos, informe e encerre.

### Passo 2 — Classificar cada item

**Notas `.md`:** leia o conteúdo e grep `vault/indexes/` para verificar se já existe Literature, PIC ou nota equivalente.

| Classificação | Critério |
|---|---|
| `ingerir` | contém conceito, método, evidência ou fonte sem equivalente no vault |
| `arquivar` | conteúdo já absorvido em Literature ou PIC existente; ou pertence a coleção já consolidada |
| `manter` | tem valor mas destino ainda incerto; não está pronta para ingestão |
| `descartar` | duplicata exata, vazia ou sem valor de rastreabilidade |

**Arquivos não-`.md`:** PDFs não têm frontmatter. A checagem é baseada no nome do arquivo e na existência de Literature equivalente no vault.

| Classificação | Critério |
|---|---|
| `ingerir` | não existe Literature correspondente à fonte ou coleção no vault |
| `arquivar` | já existe Literature correspondente; o PDF é bruto já processado |

PDFs de uma mesma pasta ou coleção são agrupados e tratados como lote — um item de lote, não um item por arquivo.

### Passo 3 — Apresentar diagnóstico

```
## Inbox — Fleetings ativas (<data>)

### Notas

### vault/Capture/Fleeting/Domínio/Fleeting — Título A.md
**Classificação:** ingerir
**Motivo:** contém conceito X não coberto por nenhum PIC ou Literature no vault
**Próximo passo:** /ingest-batch ou /ingest --auto

### vault/Capture/Fleeting/Domínio/Fleeting — Título B.md
**Classificação:** arquivar
**Motivo:** conteúdo equivalente já em [[Literature — Y]]
**Próximo passo:** mover para vault/Archive/Fleeting/Domínio/ com status: processed

---

### PDFs e outros arquivos

### vault/Capture/Fleeting/Nome da Coleção/ (N arquivos)
**Arquivos:** arquivo1.pdf, arquivo2.pdf, ...
**Classificação:** ingerir
**Motivo:** nenhuma Literature correspondente a esta coleção no vault
**Próximo passo:** /ingest --review para processar o lote

### vault/Capture/Fleeting/Outra Coleção/ (M arquivos)
**Arquivos:** arquivo1.pdf, ...
**Classificação:** arquivar
**Motivo:** [[Literature — X]] já cobre esta fonte
**Próximo passo:** mover para vault/Archive/<nome da coleção>/

---
## Resumo

Notas — ingerir: X | arquivar: Y | manter: Z | descartar: W
PDFs — ingerir: A lote(s) | arquivar: B lote(s)

Confirma as ações? (ou ajuste por item antes do --apply)
```

### Passo 4 — Aplicar com --apply

Após aprovação explícita do usuário:

**Notas `.md`:**
- **arquivar**: mova para `vault/Archive/Fleeting/<domínio>/`, adicione `status: processed` ao frontmatter
- **descartar**: apague apenas se o usuário confirmar explicitamente cada item marcado para descarte
- **ingerir**: adicione `status: pronto-para-ingestão` ao frontmatter como sinal para `/ingest-batch`
- **manter**: não toque

**PDFs e outros arquivos:**
- **arquivar**: mova para `vault/Archive/<nome da coleção>/`, preservando os nomes de arquivo originais
- **ingerir**: não mova — o arquivo fica em `Capture/Fleeting/` até ser processado via `/ingest`

Reporte os arquivos movidos, marcados e apagados ao final. Ao concluir o `--apply`, apague o checklist correspondente em `vault/Operations/Checklists/`.

## Checklist de handoff

Após apresentar o diagnóstico (com ou sem `--apply`), salve sempre o resultado em:

```
vault/Operations/Checklists/Inbox — <YYYY-MM-DD>.md
```

Os itens de ingestão devem ser **autocontidos e paralelos**: cada item precisa ter informação suficiente para ser processado por qualquer agente de forma independente, sem que o agente precise reler outros itens do checklist ou refazer a varredura do vault. Isso permite execução paralela — múltiplos agentes processando itens simultaneamente sem perda de qualidade.

Formato do checklist:

```markdown
# Inbox — <YYYY-MM-DD>

Gerado por /inbox. Itens independentes — podem ser processados em paralelo por agentes separados.
Ao concluir todos os itens, apague este arquivo.

## Ingerir

- [ ] vault/Capture/Fleeting/Domínio/Fleeting — Título A.md
  - Ação: /ingest --auto
  - Domínio: <domínio físico>
  - Tipo: <book|article|video|course|podcast>
  - Role sugerida: <foundation|frontier|evidence|tension|method|reference>
  - Literature destino: vault/Knowledge/Literature/<Tipo>/<domínio>/Literature — <título>.md (Tipo por source-type: Artigos|Livros|Notebooks; course → Cursos/<curso>/<domínio>/)
  - Conexões vault: [[Nota X]] — <relação>, [[Nota Y]] — <relação>
  - Motivo: <motivo da classificação>

- [ ] vault/Capture/Fleeting/Coleção/ (N PDFs)
  - Ação: /ingest --review (lote — processar como coleção única)
  - Domínio: <domínio físico>
  - Tipo: course
  - Role sugerida: <role>
  - Literature destino: vault/Knowledge/Literature/Cursos/<curso>/<domínio>/Literature — <título da coleção>.md
  - Conexões vault: [[Nota X]] — <relação>
  - Motivo: <motivo>

## Arquivar

- [ ] vault/Capture/Fleeting/Domínio/Fleeting — Título B.md
  - Ação: mover para vault/Archive/Fleeting/Domínio/, status: processed
  - Motivo: <motivo>

## Descartar

- [ ] vault/Capture/Fleeting/Domínio/Fleeting — Título D.md
  - Ação: apagar
  - Motivo: <motivo>

## Manter

- vault/Capture/Fleeting/Domínio/Fleeting — Título C.md — aguardar
```

O checklist é a interface de handoff: Claude usa para continuar na mesma sessão ou em nova sessão; Codex usa para executar os itens mecânicos (arquivar, descartar) ou os ingests quando autorizado. Os campos `Domínio`, `Tipo`, `Role sugerida`, `Literature destino` e `Conexões vault` eliminam a necessidade de re-varrer o vault por item.

## Limite

Não cria PICs, Literature, Permanent ou qualquer nota substantiva. Não decide o conteúdo das notas. Classifica e executa movimentações mecânicas apenas.
