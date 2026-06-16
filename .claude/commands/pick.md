# Skill: /pick

Cria um PICK (nota permanente atômica) a partir de conteúdo fornecido pelo usuário.

## O que é um PICK

Um PICK captura **uma única ideia** nas próprias palavras do usuário, no formato P/I/C:
- **P** — Pergunta que a ideia responde
- **I** — Ideia em 2–3 linhas
- **C** — Conexões com outros PICs existentes

## Comportamento

1. Receba o conteúdo bruto do usuário (texto livre, trecho de livro, anotação, etc.)
2. Leia o índice do vault em `vault/INDEX.md` para conhecer os PICs existentes
3. Destile **uma única ideia** central do conteúdo
4. Proponha o título, P/I/C e pelo menos uma conexão com PICs existentes
5. **Aguarde aprovação** antes de salvar — mostre o rascunho e pergunte se está correto
6. Após aprovação, salve em `vault/Knowledge/PICK/<título>.md` com o frontmatter correto

## Frontmatter obrigatório

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: pick
title: <título>
created: <data YYYY-MM-DD>
tags: []
---
```

## Regras

- Título: nominal, curto, em português. Ex: "Orçamento Público como Instrumento de Política Fiscal"
- Se o conteúdo contiver múltiplas ideias, crie múltiplos PICs (um por vez, em sequência)
- Conexões em **C:** usam `[[nome do arquivo]]` — sem ID, só o título
- Se não houver PICs existentes suficientes para conectar, registre no **C:** a lacuna e sugira um tema futuro para MOC
- O id é gerado com o timestamp do momento da criação (use a data/hora atual)
