# Skill: /ata

Recebe uma transcrição de reunião e gera automaticamente uma ATA formal em `.doc`, preservando o cabeçalho institucional do template SESAB.

## Uso

```
/ata <caminho-da-transcrição>
```

- `<caminho-da-transcrição>` — caminho relativo ou absoluto para o arquivo `.md` com a transcrição bruta

## Comportamento

### Passo 1 — Ler e analisar a transcrição

Leia o arquivo indicado. Extraia:

- **Data** da reunião (formato: `DD de <mês por extenso> de AAAA`)
- **Local** (default: `Vitória da Conquista`)
- **Participantes** com função: nome (função)
- **Pauta resumida**: tópicos discutidos, com decisões objetivas e regras definidas
- **Avisos finais**: pendências, tarefas e próximos passos

### Passo 2 — Apresentar rascunho e aguardar aprovação

Exiba o rascunho do conteúdo da ATA em texto simples antes de gerar o `.doc`:

```
## Rascunho da ATA — <data>

**Local/data:** Vitória da Conquista, <mês> de <ano>

**Participantes:** ...

**Abertura:** parágrafo de abertura...

**Seções:**
1. <título> — <resumo>
2. <título> — <resumo>
...

**Avisos:**
- ...

Confirma? (ou corrija antes de gerar o .doc)
```

Aguarde confirmação explícita. Aceite correções inline.

### Passo 3 — Gerar o .doc via PowerShell

Use PowerShell com Word COM automation. Siga rigorosamente as regras abaixo.

**Template:** sempre copie `vault/Outros/tático/03 - Atas/ata-base.doc` para o destino antes de editar. Nunca edite o template diretamente.

**Destino:** `vault/Outros/tático/03 - Atas/Ata <título resumido> — <Mês Ano>.doc`

**Posicionamento do cursor:** após abrir o `.doc`, use `$word.Selection.EndKey(6, 0)` para mover para o final (depois das imagens do cabeçalho).

**Constantes de alinhamento:** use os valores inteiros diretamente — não use nomes simbólicos:
- `0` = alinhamento à esquerda (`wdAlignParagraphLeft`)
- `3` = justificado (`wdAlignParagraphJustify`)

**Funções auxiliares obrigatórias** — use exatamente estes nomes (nunca `H`, `P`, `Li`, `Br` — são aliases reservados do PowerShell 5.1):

```powershell
function Sec([int]$n, [string]$t) {
    # Seção com título em negrito. $n=0 = sem numeração (ex: Revisão, Avisos)
    $sel.ParagraphFormat.Alignment = 3
    $sel.ParagraphFormat.LeftIndent = 0
    $sel.Font.Bold = 1
    if ($n -gt 0) { $sel.TypeText("$n. $t") } else { $sel.TypeText($t) }
    $sel.Font.Bold = 0
    $sel.TypeParagraph(); $sel.TypeParagraph()
}

function Par([string]$t) {
    # Parágrafo justificado com linha em branco após
    $sel.ParagraphFormat.Alignment = 3
    $sel.ParagraphFormat.LeftIndent = 0
    $sel.TypeText($t); $sel.TypeParagraph(); $sel.TypeParagraph()
}

function Itm([string]$t) {
    # Item de lista com recuo de 0,5cm
    $sel.ParagraphFormat.Alignment = 3
    $sel.ParagraphFormat.LeftIndent = $word.CentimetersToPoints(0.5)
    $sel.TypeText("- $t"); $sel.TypeParagraph()
}

function Esp {
    # Linha em branco
    $sel.ParagraphFormat.LeftIndent = 0
    $sel.ParagraphFormat.Alignment = 3
    $sel.TypeParagraph()
}
```

**Estrutura obrigatória do documento:**

```
[Alinhamento esquerdo] "Vitória da Conquista, <mês> de <ano>"
[linha em branco]
[Alinhamento esquerdo, negrito] "ATA DA <TÍTULO EM MAIÚSCULAS>"
[linha em branco]
[Par] Parágrafo de abertura: data, participantes e contexto.
[Sec 0] "Revisão da reunião anterior"
[Par] Breve retomada da reunião anterior (se houver).
[Sec 1..N] Seções numeradas — cada tema com título em negrito
[Par ou Itm] Conteúdo conciso: decisões, regras e critérios
[Sec 0] "Avisos"
[Itm] Uma linha por aviso/pendência/próxima ação
```

**Regras de conteúdo:**
- Texto conciso: decisões e regras, sem prosa desnecessária
- Cada decisão em no máximo duas linhas
- Listas de itens quando houver 3 ou mais pontos do mesmo tipo
- Alvo: 2 páginas. Máximo: 3 páginas

**Script completo mínimo:**

```powershell
$base = "C:\Users\HGVC\Desktop\Repositórios\PKM\vault\Outros\tático\03 - Atas"
$template = "$base\ata-base.doc"
$dest = "$base\Ata <título> — <Mês Ano>.doc"

Copy-Item $template $dest -Force

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

$doc = $word.Documents.Open($dest)
$word.Selection.EndKey(6, 0)
$sel = $word.Selection

# ... funções Sec, Par, Itm, Esp aqui ...

# Cabeçalho (esquerda)
$sel.ParagraphFormat.Alignment = 0; $sel.ParagraphFormat.LeftIndent = 0
$sel.TypeText("Vitória da Conquista, <mês> de <ano>"); $sel.TypeParagraph(); Esp

$sel.ParagraphFormat.Alignment = 0; $sel.ParagraphFormat.LeftIndent = 0
$sel.Font.Bold = 1; $sel.TypeText("ATA DA <TÍTULO>"); $sel.Font.Bold = 0
$sel.TypeParagraph(); Esp

# ... conteúdo ...

$doc.Save(); $doc.Close(); $word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
Write-Host "ATA salva: $dest"
```

### Passo 4 — Confirmar e reportar

Após execução bem-sucedida:

```
## ATA gerada

**Arquivo:** vault/Outros/tático/03 - Atas/Ata <título> — <Mês Ano>.doc
**Seções:** N seções numeradas + Revisão + Avisos
**Template usado:** ata-base.doc (cabeçalho SESAB preservado)
```

## Limite

Não cria notas no vault (Literature, PIC, etc.). Não modifica a transcrição de origem. Gera apenas o `.doc` da ATA no diretório `03 - Atas/`.
