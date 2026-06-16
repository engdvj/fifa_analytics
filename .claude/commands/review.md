# Skill: /review

Revisa criticamente nota existente (permanent ou principle), adicionando ou corrigindo os campos v2: `status:`, `## Limitações` e `## Relações qualificadas`. Não é migração mecânica: a revisão deve avaliar a tese, seus limites reais e sua maturidade.

## Uso

```
/review [<título da nota> | --scan | --limitations]
```

- `<título da nota>` — revisa uma nota específica
- `--scan` — lista todas as permanentes e princípios sem campo `status:` (backlog de migração v2)
- `--limitations` — revisa limitações de permanents e transforma limitações promissoras em perguntas de radar/tensão
- Sem flag — pergunta qual nota revisar

## Comportamento: --scan

1. Grep recursivo por `type: permanent` em `vault/Knowledge/Permanent/` — lista todas as permanentes
2. Para cada permanente, verifica se `status:` consta no frontmatter
3. Faz o mesmo recursivamente para `vault/Knowledge/Principle/`
4. Apresenta o backlog:

```
## Notas sem status (migração v2 pendente)

### Permanentes
- [[<nota>]] — criada em <data>
...

### Princípios
- [[<nota>]] — criada em <data>
...

Qual quer revisar primeiro? (título ou "todas")
```

## Comportamento: --limitations

Use este modo depois de criar permanents `synthesis-stage: base`.

1. Liste permanents recursivamente em `vault/Knowledge/Permanent/`, priorizando:
   - `synthesis-stage: base`;
   - `status: em-formação`;
   - notas com `## Limitações` genéricas ou pouco acionáveis.
2. Para cada permanent candidata, leia `## Tese`, `## Desenvolvimento` e `## Limitações`.
3. Classifique cada limitação:
   - `escopo` — delimita o que a tese não cobre;
   - `lacuna` — aponta tema que precisa de fonte externa;
   - `tensão` — ameaça a tese e pode virar Tension;
   - `trilha` — pode gerar uma permanent `synthesis-stage: tensioned`;
   - `baixo valor` — ressalva fraca, sem ação imediata.

   **Âncora:** identifique ao menos 2 limitações acionáveis por permanent. Se não conseguir nenhuma com base no conteúdo, registre como "revisão substantiva pendente" — não invente limitações genéricas nem deixe em branco.

4. Apresente o relatório:

```
## Limitações acionáveis

### [[Permanent — A]]
- Limitação: <texto>
- Classe: lacuna | tensão | trilha | escopo | baixo valor
- Pergunta de radar: <pergunta, se aplicável>
- Possível tension: <título, se aplicável>
- Próximo passo: /radar --from-limitations | /tension | manter em Limitações
```

5. Não crie radar, tension ou permanent automaticamente. Aguarde escolha do usuário.
6. Se o usuário aprovar uma melhoria textual de limitação, edite apenas `## Limitações`, preservando a tese base.

## Comportamento: revisão de uma nota

1. Leia a nota na íntegra
2. Avalie criticamente:
   - **Status atual**: com base no conteúdo e histórico, qual status melhor representa a maturidade desta nota? (`em-formação | estável | tensionada | testada | revisada | superada`)
   - **Limitações identificadas**: onde a tese encontra resistência real — casos que não se aplicam, condições que a quebram, evidências contrárias ou fontes que a tensionam. Não use ressalvas genéricas.
   - **Trilhas futuras**: há limitações que poderiam gerar radar, tension ou uma permanent `synthesis-stage: tensioned`?
   - **Relações qualificadas**: há links na nota cujas funções não são óbvias e merecem ser explicitadas?
3. Proponha as três adições antes de qualquer edição:

```
## Proposta de revisão para [[<título>]]

**Status sugerido:** <status> — <justificativa em 1 linha>

**Limitações identificadas:**
- <limitação 1>
- <limitação 2>

**Relações qualificadas (se houver):**
- <tipo>: [[Nota]] — <razão>

Aplica? (s/n ou ajustes)
```

4. Após aprovação, edite a nota:
   - Adicione `status: <valor>` no frontmatter após `sources:` (ou após `confidence:` em princípios)
   - Adicione seção `## Limitações` antes de `## Referências` (em permanentes) ou antes de `## Conexões` (em princípios)
   - Adicione seção `## Relações qualificadas` após `## Conexões` — apenas se houver relações com função não óbvia
   - Em princípios: adicione `## Revisão` após `## Limitações` se não existir

5. O hook atualiza `vault/indexes/` automaticamente ao salvar — o campo `status:` será refletido na próxima edição do arquivo

## Regras

- Nunca reescreva o conteúdo existente da nota — apenas adicione as seções novas e o campo de frontmatter
- `## Limitações` deve ter conteúdo real, não placeholder — pense sobre a nota antes de escrever
- Se não houver limitação real identificável com base no conteúdo da nota, registre a pendência como revisão substantiva em vez de inventar uma limitação genérica
- Se a nota claramente não tem limitações internas (raro), ainda assim crie a seção com uma linha honesta sobre os limites do escopo
- Status `em-formação` é o default conservador — use `estável` só se a tese estiver claramente consolidada
- Se durante a revisão identificar uma objeção forte o suficiente para uma nota Tension, sinalize ao usuário mas não crie automaticamente — use `/tension` separadamente
