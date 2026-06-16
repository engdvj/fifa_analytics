# Skill: /book

Prepara um livro EPUB para ingestão por partes: extrai os capítulos como Fleetings, cria a **Literature-mãe** do livro (a partir dos metadados do EPUB) e deixa os capítulos prontos na fila de ingestão. **Não ingere o livro inteiro de uma vez** — a ingestão acontece capítulo a capítulo, sob comando do usuário.

## Por que assim

Um livro não é 91 fontes soltas — é **uma fonte** (a Literature do livro) com vários capítulos que a alimentam. Ingerir tudo de uma vez gera um lote enorme e Literature fragmentada. O fluxo correto: criar a Literature-mãe primeiro (espinha do livro), extrair os capítulos ligados a ela, e ingerir por partes. Cada capítulo ingerido cria PICs e marca sua entrada no Sumário da mãe de `pendente` → `ingerida`.

## Uso

```
/book <path-epub> [--domain <domínio>] [--chapter <n>]
```

- `<path-epub>` — caminho para o `.epub` (obrigatório)
- `--domain <domínio>` — domínio do vault; se omitido, detecta pelo nome ou pergunta
- `--chapter <n>` — extrai apenas o capítulo de índice N (base 0); útil para recuperar falhas pontuais

## Comportamento

### Passo 1 — Detectar domínio

Se `--domain` foi passado, use-o. Senão, inspecione o nome: padrão `<Domínio> — <Título>.epub` extrai o domínio do prefixo. Se não detectável, pergunte.

Domínios: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`, `Não Classificados`.

Atenção: os metadados do EPUB (Passo 2) podem sugerir um domínio melhor que o nome do arquivo. Se houver divergência clara, proponha o domínio do conteúdo.

### Passo 2 — Ler metadados e listar capítulos

```bash
python3 .claude/book-extract.py "<epub_path>" --meta-json
python3 .claude/book-extract.py "<epub_path>" --list
```

Exiba: título, autor, editora, ano, ISBN (alguns podem vir vazios — comum em EPUBs), e a lista numerada de capítulos. Aguarde confirmação antes de extrair (aceite ajuste de domínio ou capítulos a pular).

### Passo 3 — Criar a Literature-mãe

Crie a Literature do livro em `vault/Knowledge/Literature/Livros/<domínio>/Literature — <título curto>.md` com:
- frontmatter `type: literature`, `source-type: book`, `role: reference`, `status: reading`, `tags: [livro, <domínio-slug>]`, e os campos de metadados (`author`, `publisher`, `year`, `isbn`, `language`). Campos ausentes nos metadados ficam vazios com marca `# preencher` — não bloqueiam.
- `## Resumo` (placeholder — preenchido depois ou consolidado pela ingestão)
- `## Sumário` listando cada capítulo: `- [[Fleeting — <título curto> — <label do capítulo>]] — pendente`
- `## Conteúdo ingerido` (placeholder)

### Passo 4 — Extrair capítulos ligados à Literature-mãe

Extraia para o **staging de fleetings** (`~/PKM-fleetings/`), com `--literature` apontando para a Literature-mãe — assim cada Fleeting carrega `literature: <mãe>` no frontmatter e o `/ingest` saberá o destino:

```bash
python3 .claude/book-extract.py "<epub_path>" \
  --domain "<domínio>" \
  --outdir "$HOME/PKM-fleetings" \
  --literature "Literature — <título curto>"
```

Adicione `--chapter <n>` se foi passado. Parse o stdout: `OK [N]` = extraído, `SKIP [N]` = vazio, `ERRO` = falha. Se N = 0, interrompa.

Ao cair em `~/PKM-fleetings/`, o watcher de fleetings enfileira cada capítulo como job de ingest **aguardando clique** (não processa sozinho, salvo se o toggle de continuidade do painel estiver ligado).

### Passo 5 — Arquivar o EPUB

Após a extração bem-sucedida, mova o EPUB para a coleção do livro:

```bash
mkdir -p "vault/Archive/<domínio>/<título curto>"
mv "<epub_path>" "vault/Archive/<domínio>/<título curto>/"
```

### Passo 6 — Relatório final

```
## /book — <título curto>

**Domínio:** <domínio>
**Autor:** <autor> · **Ano:** <ano ou "preencher">
**Literature-mãe:** [[Literature — <título curto>]] (criada)
**Capítulos extraídos:** N → ~/PKM-fleetings/ (aguardando ingestão)
**Capítulos pulados:** M
**EPUB arquivado em:** vault/Archive/<domínio>/<título curto>/

Próximo passo: ingerir os capítulos por partes — pelo painel do watcher
(clique a clique, ou ligue a continuidade para automático), ou
`/ingest --literature "Literature — <título curto>"` por capítulo.
Cada capítulo ingerido marca sua linha no Sumário da Literature-mãe como
`ingerida` e cria os PICs.
```

## Regras

- **Não ingere o livro.** `/book` só extrai + cria a Literature-mãe + enfileira. A ingestão é por partes, sob comando do usuário.
- A Literature-mãe é criada ANTES da extração — é a espinha; os capítulos a referenciam por `literature:` no frontmatter.
- Capítulos vão para `~/PKM-fleetings/` (staging), não direto no vault — o watcher os enfileira.
- Metadados incompletos não bloqueiam: marque `# preencher` e siga.
- Não arquive o EPUB se a extração falhar (N = 0).
- `book-extract.py` fica em `.claude/book-extract.py` (caminho relativo à raiz do vault).
- No watcher, o `run_book` do `pkm-codex-runner.py` faz esse mesmo fluxo automaticamente quando um `.epub` cai no `~/PKM-inbox`.
