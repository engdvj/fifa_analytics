# Skill: /tension

Cria uma nota do tipo `tension` quando uma objeção identificada em `## Limitações`, radar, handoff ou fonte ingerida escala para Level 2: forte, reutilizável ou que afeta múltiplas notas.

## Uso

```
/tension [<título da nota de origem> | --scan]
```

- `<título da nota de origem>` — cria uma Tension a partir de uma nota específica
- `--scan` — lista permanentes e princípios com `status: tensionada` que ainda não têm Tension formal vinculada
- Sem flag — pergunta de qual nota extrair a tensão

## Quando usar

Use `/tension` quando uma limitação identificada em `## Limitações` de uma permanent ou principle:
- For reutilizável (a mesma objeção aparece ou poderia afetar outras notas)
- Tiver evidência ou argumento externo que sustente a objeção
- For estrutural (questiona a tese central, não um caso de borda)
- Abrir uma trilha que pode gerar uma permanent `synthesis-stage: tensioned`

**Não use** para ressalvas pequenas ou casos de borda que pertencem apenas à seção `## Limitações` da nota original (Level 1).

## Comportamento

1. Leia a nota de origem na íntegra
2. Busque radar ou handoff relacionado ao tema em `vault/Knowledge/Research/` e `vault/Knowledge/Handoffs/` — se existir, leia o trecho que sustenta a objeção antes de continuar. Esta leitura é obrigatória quando houver material relacionado; não pule mesmo que o contexto pareça claro pela nota de origem.
3. Identifique a limitação que escalona — pergunte ao usuário se não estiver claro
4. Proponha o rascunho da Tension antes de salvar:

```
## Rascunho de Tension

**Título sugerido:** Tension — <"X Também Pode Ser Y" ou "Limite de Z em Contexto W">
**Severity:** leve | moderada | estrutural
**Affects:** [[<nota de origem>]] + [[<outras notas afetadas se houver>]]
**Origem da limitação:** <trecho, radar ou handoff>
**Pode gerar synthesis-stage tensioned:** sim/não

**Conteúdo:**
[rascunho completo]

Cria? (s/n ou ajustes de título/severity)
```

5. Após aprovação, salve em `vault/Knowledge/Tension/<severity>/Tension — <título>.md` com:
   ```yaml
   ---
   id: <timestamp>
   type: tension
   title: Tension — <título>
   created: <data>
   tags: [<tags da nota de origem>]
   affects:
     - "[[<nota afetada 1>]]"
     - "[[<nota afetada 2>]]"
   origin: [[<Permanent/Radar/Handoff de origem>]]
   severity: <leve|moderada|estrutural>
   ---
   ```

6. Atualize a(s) nota(s) afetada(s):
   - Para `Permanent` e `Principle`: mude `status:` para `tensionada` no frontmatter
   - Para `Decision`: preserve o status operacional (`ativa`, `aplicada`, `revisada`, `cancelada`, `superada`) e registre a tensão em `## Revisão` ou `## Relações qualificadas`
   - Adicione link para a Tension na seção adequada:
     ```
     - tensiona: [[<título da Tension>]]
     ```

7. O hook atualiza `vault/indexes/` automaticamente ao salvar a Tension e as notas afetadas — nenhuma ação manual necessária.

## Regras

- Diretório por `severity:`: `estrutural` → `Estrutural`, `moderada` → `Moderada`, `leve` → `Leve`.
- Título deve ser autoexplicativo sem ler a nota e usar prefixo: `Tension — Shadow Systems Também Podem Ser Risco de Accountability` é bom; `Tension — Limitação da nota X` não é
- A nota deve ser autocontida: `Objeção`, `Argumento` e `Impacto` precisam desenvolver a tensão sem exigir que a nota afetada seja aberta.
- Evite abrir com "A tese de que..."; apresente primeiro o conflito conceitual, depois use links para rastrear origem e impacto.
- `severity: estrutural` → questiona a tese central da nota; considere sugerir revisão da permanent/principle
- `severity: moderada` → limita o escopo mas não invalida a tese
- `severity: leve` → caso de borda ou contexto específico — considere se não é apenas Level 1 (seção Limitações)
- Nunca crie Tension sem link de volta para a nota afetada
- Uma Tension pode afetar múltiplas notas — prefira uma nota Tension com múltiplos `affects:` a criar notas duplicadas
- Uma Tension pode afetar decisions quando a objeção muda uma decisão operacional; nesse caso, a tension não cria `status: tensionada` na decision, apenas gatilho explícito de revisão
- Quando uma Tension nasce de uma limitação que pode gerar nova tese, sinalize o próximo passo: `/synthesize --tensioned`
