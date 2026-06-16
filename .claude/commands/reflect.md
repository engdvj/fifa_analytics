# Skill: /reflect

Trabalha os níveis superiores do vault — `principle`, `decision`, `application` — transformando conhecimento sintetizado em convicções operacionais, decisões rastreáveis e aplicações reais.

## Hierarquia dos tipos superiores

```
Permanent   ← conhecimento argumentado (status: em-formação → estável → testada)
    ↑
Principle   ← convicção destilada em terceira pessoa, transferível entre contextos
    ↑
Decision    ← escolha rastreável (o que vou fazer, por quê, como revisar)
    ↑
Application ← onde o conhecimento encontra a realidade
    ↓
(novo Fleeting — o ciclo reinicia)

Para mobilizar o vault em torno de um problema específico → use /brief
Brief → Decision/Application → Project (execução sustentada)
```

## Uso

```
/reflect [--scan | --principle | --decision | --application]
```

- `--scan` — mostra o estado dos níveis superiores: permanentes sem princípio, princípios sem decisão, decisões sem aplicação
- `--principle` — deriva um ou mais princípios de permanentes existentes
- `--decision` — documenta uma decisão apoiada em princípios
- `--application` — registra aplicação real ou mapeia oportunidade de aplicação
- Sem flag — executa `--scan` por padrão

---

## Comportamento: --scan

1. Mapeie os níveis superiores com Grep cirúrgico — não leia INDEX.md:
   - Glob recursivo em `vault/Knowledge/Permanent/` → lista de permanentes existentes
   - Grep recursivo por `sources:` em `vault/Knowledge/Principle/` → quais permanentes já geraram princípios
   - Grep por `principles:` em `vault/Action/Decision/` → quais princípios já geraram decisões
   - Glob em `vault/Action/Application/` → lista de aplicações existentes
   - Grep recursivo por `status:` em `vault/Knowledge/Permanent/` → permanentes sem status (backlog de migração v2)
2. Liste:
   - Permanentes que ainda não geraram nenhum `principle`
   - Permanentes sem campo `status:` (precisam de migração v2)
   - Principles que ainda não geraram nenhuma `decision`
   - Decisions com `status: ativa` sem `application` vinculada
3. Apresente o relatório no formato:

```
## Estado dos níveis superiores

### Permanentes sem princípio derivado
- [[<nota>]] — <ideia central em meia linha>
...

### Permanentes sem status (migração v2 pendente)
- [[<nota>]]
...

### Princípios sem decisão vinculada
- [[<princípio>]] — <posição em meia linha>
...

### Decisões sem aplicação registrada
- [[<decisão>]] — status: <status> | criada em <data>
...

O que quer trabalhar? (principle / decision / application / nenhum)
```

---

## Comportamento: --principle

> Formato completo em `.claude/commands/note-formats.md` — seção **Principle**.

### Processo

1. Pergunte de qual permanent (ou cluster) o usuário quer extrair princípios
2. Leia a permanent na íntegra
3. Identifique a tese central e todas as implicações práticas — extraia o máximo possível

   **Âncora:** uma permanent rica tipicamente gera 2–4 princípios. Se identificou menos de 2, releia as implicações operacionais e práticas da tese — provavelmente agrupou em um único candidato ideias que merecem princípios separados.

4. Proponha todos os candidatos com título e posição em uma única listagem
5. Aguarde o usuário aprovar, cortar ou refinar
6. Redija todos os rascunhos aprovados de uma vez — cada princípio inclui obrigatoriamente:
   - `status: em-formação`
   - Seção `## Limitações`
   - Seção `## Revisão` com gatilho concreto
7. Aguarde aprovação em bloco
8. Salve em `vault/Knowledge/Principle/<grupo>/Principle — <título>.md`
9. Atualize `vault/Navigation/MOC/MOC — Princípios.md`:
   - Determine a seção temática pela permanent de origem
   - Adicione cada princípio novo no formato `- [[Principle — título]] — <descrição em meia linha>`
10. Após salvar princípios e atualizar o MOC, **anuncie ao usuário** antes de iniciar o próximo fluxo:
    ```
    Princípios salvos. Iniciando o fluxo --decision para mapear decisões derivadas. Continua? (s/n)
    ```
    Se confirmado, **inicia o fluxo `--decision`**:
    - Identifique as decisões que os princípios sugerem
    - Proponha todos os candidatos em uma única listagem
    - Redija todos os rascunhos de uma vez e aguarde aprovação em bloco
    - Salve os aprovados em `vault/Action/Decision/Decision — <título>.md`
    - Atualize `vault/Navigation/MOC/MOC — Decisões.md`
    - Execute `/commit` ao final cobrindo todos os arquivos criados na sessão

---

## Comportamento: --decision

> Formato completo em `.claude/commands/note-formats.md` — seção **Decision**.

### Processo

1. Pergunte qual decisão o usuário quer documentar e em que contexto
2. Pergunte quais princípios ou permanentes sustentam a escolha
3. Redija o rascunho completo — incluindo `status: ativa` e seção `## Revisão` obrigatória
4. Aguarde aprovação
5. Salve em `vault/Action/Decision/Decision — <título>.md`

---

## Comportamento: --application

> Formato completo em `.claude/commands/note-formats.md` — seção **Application**.

### Processo

1. Pergunte se é registro retrospectivo (algo que já aconteceu) ou exploração prospectiva (oportunidade identificada)
2. Pergunte qual decisão ou princípio está sendo aplicado
3. Redija o rascunho com o frontmatter v2:
   ```yaml
   status: explorando | ativa | concluída | abandonada
   decision: [[decisão que originou esta aplicação]]
   principle: [[princípio testado]] (se relevante)
   ```
4. Aguarde aprovação
5. Salve em `vault/Action/Application/Application — <título>.md`
6. Após salvar: sugira atualizar o `status:` da Decision vinculada para `aplicada` (se aplicação concluída)
7. Se o aprendizado gerou novos dados que merecem captura, sugira criar um Fleeting

---

## Regras

- `principle` nunca argumenta — argumentos ficam na `permanent`. O princípio conclui.
- `principle` usa terceira pessoa e formula uma regra transferível; contexto técnico entra no fundamento, não como limite do título.
- `principle` sempre inclui `## Limitações` e `## Revisão` — sem isso não está completo
- `decision` sempre tem `status:` e sempre tem critério de revisão — sem isso não é decisão, é intenção
- `application` sempre aponta de volta: o campo `aprendizado` deve indicar o que muda no sistema
- Nunca crie `decision` sem pelo menos um `principle` vinculado — decisão sem fundamento é opinião
- Nunca crie `application` sem `decision` vinculada — aplicação sem rastreabilidade não alimenta o ciclo
- O id é gerado com o timestamp do momento da criação
- Todo título/filename criado por este fluxo usa o prefixo do tipo: `Principle —`, `Decision —` ou `Application —`.
