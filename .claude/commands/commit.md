# Skill: /commit

Cria commits git semânticos pontuais, com título claro e corpo explicativo.

## Comportamento

1. Execute `git status` e `git diff --stat` para mapear tudo que mudou
2. Se existir `.claude/commands/commit-config.md`, leia-o para escopos e convenções específicos do projeto — ele tem precedência sobre os padrões abaixo
3. Agrupe as mudanças por tipo:
   - Nova funcionalidade ou arquivo → `feat(<escopo>):`
   - Alteração em configuração/infraestrutura → `feat(config):`
   - Correção de bug → `fix:`
   - Refatoração sem mudança de comportamento → `refactor:`
   - Documentação → `docs:`
   - Reorganização/limpeza → `chore:`
   - Testes → `test:`
4. **Crie um commit separado por grupo** — nunca agrupe tipos diferentes
5. Cada commit tem: título na primeira linha + linha em branco + corpo com 1–3 linhas explicando o que foi feito e por quê
6. Para cada commit: stage os arquivos do grupo, commite, avance para o próximo
7. Ao final, liste todos os commits com hash + título
8. Exiba exatamente este bloco após a listagem:

```
---
Commits concluídos. Execute /compact para compactar o contexto.
---
```

## Formato da mensagem

```
<tipo>(<escopo>): <título direto, máx 72 chars>

<corpo: o que foi feito e por quê, 1–3 linhas>
```

## Regras

- **Um commit por tipo — nunca misture**
- Título objetivo: descreve o que foi adicionado, não "criar arquivo X"
- Corpo obrigatório: explica o que foi feito e por quê em 1–3 linhas
- Nunca use `git add -A` ou `git add .` — sempre por arquivo ou diretório específico
- Se um grupo tiver arquivos de subtemas diferentes, divida por subtema
