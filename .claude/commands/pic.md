# Skill: /pic

Cria um PIC (nota permanente atômica) a partir de conteúdo fornecido pelo usuário.

## O que é um PIC

Um PIC captura **uma única ideia** nas próprias palavras do usuário, no formato P/I/C:
- **P** — Pergunta que a ideia responde
- **I** — Ideia em 2–3 linhas
- **C** — Conexões com outros PICs existentes

## Comportamento

1. Receba o conteúdo bruto do usuário (texto livre, trecho de livro, anotação, etc.)
2. Grep o título candidato em `vault/indexes/` para verificar se o PIC já existe (busca nos arquivos INDEX-PIC-<domínio>.md)
3. Destile **uma única ideia** central do conteúdo
4. Proponha o título, P/I/C e pelo menos uma conexão com PICs existentes
5. **Aguarde aprovação** antes de salvar — mostre o rascunho e pergunte se está correto
6. Após aprovação, salve em `vault/Knowledge/PIC/<domínio>/PIC — <título>.md` com o frontmatter correto
7. **Atualizar candidatos a Tópico** — após salvar:
   - Determine o domínio do PIC e leia `vault/Navigation/Tópicos/_Candidatos-<DOMINIO>.md` (mapeamento: `ADM`→ADM, `DC`→DC, `HW`→HW, `INF`→INF, `LIB`→LIB, `OP`→OP, `SI`→SI, `SW`→SW)
   - Verifique se o tema do novo PIC já está coberto por algum candidato existente (pelo título ou descrição da entrada)
   - Se nenhum candidato cobrir esse cluster, consulte o índice do domínio para contar quantos PICs compartilham o mesmo tema
   - Se houver 3 ou mais PICs com temas sobrepostos sem candidato correspondente:
     - Identifique o cluster temático (`### <Cluster>`) dentro do arquivo de candidatos do domínio
     - Se o cluster já existir, adicione a entrada dentro dele; se não existir, crie `### <Cluster>` no local correto
     - Formato: `XXnn. <Título descritivo> — <conceitos principais separados por vírgula>` onde `XX` é o prefixo do domínio (`HW`, `SW`, `SI`, `INF`, `OP`, `DC`, `ADM`, `LIB`) e `nn` é o próximo número sequencial (ver `<!-- Alcance: ... -->` no cabeçalho do arquivo)
     - Nunca adicione sufixo `— N+ PICs` nem agrupe temas distintos em uma única entrada

## Frontmatter obrigatório

```yaml
---
id: <timestamp YYYYMMDDHHmmss>
type: pic
title: PIC — <título>
created: <data YYYY-MM-DD>
tags: []
---
```

## Destino físico

Escolha o domínio pelo campo `moc:`:

- MOCs em `Navigation/MOC/Conteúdo/Hardware/` → `vault/Knowledge/PIC/Hardware/`
- MOCs em `Navigation/MOC/Conteúdo/Software/` → `vault/Knowledge/PIC/Software/`
- MOCs em `Navigation/MOC/Conteúdo/Infraestrutura/` → `vault/Knowledge/PIC/Infraestrutura/`
- MOCs em `Navigation/MOC/Conteúdo/Sistemas de Informação/` → `vault/Knowledge/PIC/Sistemas de Informação/`
- MOCs em `Navigation/MOC/Conteúdo/Orçamento Público/` → `vault/Knowledge/PIC/Orçamento Público/`
- MOCs em `Navigation/MOC/Conteúdo/Direito Constitucional/` → `vault/Knowledge/PIC/Direito Constitucional/`
- MOCs em `Navigation/MOC/Conteúdo/Administração/` → `vault/Knowledge/PIC/Administração/`
- MOCs em `Navigation/MOC/Conteúdo/Libras/` → `vault/Knowledge/PIC/Libras/`

Se ainda não houver MOC claro, registre a lacuna no rascunho e só salve após escolher um domínio conservador.

## Regras

- Título: `PIC — <título nominal, curto, em português>`. Ex: `PIC — Orçamento Público como Instrumento de Política Fiscal`
- Se o conteúdo contiver múltiplas ideias, crie múltiplos PICs (um por vez, em sequência)
- Para conteúdo com 5 ou mais candidatos a PIC, prefira `/ingest` — ele tem Literature + cobertura estrutural + gate de duplicatas integrados; o `/pic` é para capturas pontuais de 1–4 ideias
- Conexões em **C:** usam `[[título completo com prefixo]]` — sem ID
- Se não houver PICs existentes suficientes para conectar, registre no **C:** a lacuna e sugira um tema futuro para MOC
- O id é gerado com o timestamp do momento da criação (use a data/hora atual)

## Autonomia do PIC — regra central

O PIC deve fazer sentido completo sem que o leitor abra nenhuma fonte. Isso significa:

**P:** — a pergunta é conceitual, não contextual. Não nomeia aula, arquivo, curso, autor ou data. Funciona como pergunta filosófica sobre o domínio.

**I:** — a resposta sintetiza a essência da ideia com as próprias palavras. Não cita, não parafraseia, não resume "o que foi dito". Explica por que a ideia é verdadeira ou relevante.

**C:** — a fonte aparece aqui, como link para a Literature note. Nunca em P: ou I:.

**Exemplos de P: errado vs. certo:**

| Errado | Certo |
|--------|-------|
| O que a aula 35 explica sobre créditos adicionais? | Por que créditos adicionais existem se a LOA já autoriza o gasto anual? |
| Como o curso define administração? | O que distingue uma atividade administrada de uma conduzida pelo fluxo dos acontecimentos? |
| O que foi apresentado sobre FP16 no material? | Por que redes neurais treinam em FP16 mas inferem em FP32? |

**Exemplos de I: errado vs. certo:**

| Errado | Certo |
|--------|-------|
| Conforme a aula, créditos adicionais são autorizações... | A LOA congela a autorização no momento da aprovação. Eventos imprevisíveis ou subestimados exigem abertura de crédito adicional para que o gasto ocorra legalmente. |
| O material explica que administração é... | Administrar é substituir o improviso por objetivos: a atividade passa a responder a um fim deliberado, não ao acaso das circunstâncias. |

## Gate de qualidade antes de propor

Antes de mostrar o rascunho ao usuário, verifique mentalmente cada campo:

1. **P:** contém nome de aula, arquivo, curso, autor ou fonte? → reescreva como pergunta conceitual.
2. **I:** usa "conforme", "segundo", "a aula", "o material", "foi apresentado"? → reescreva como síntese direta.
3. **I:** faz sentido lido isoladamente, sem contexto do material? → se não, aprofunde a ideia.
4. **C:** tem ao menos uma conexão com outro PIC (não só Literature e MOC)? → se não, sinalize a lacuna explicitamente.
