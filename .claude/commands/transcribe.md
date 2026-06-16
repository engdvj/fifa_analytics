# Skill: /transcribe

Escaneia `vault/Capture/Fleeting/` em busca de arquivos de áudio, transcreve cada um com Whisper local via `transcribe.py` e salva como Fleeting `.md` com frontmatter correto.

## Uso

```
/transcribe [--domain <domínio>] [--keep]
```

- `--domain <domínio>` — restringe a um domínio específico
- `--keep` — preserva os arquivos de áudio após transcrição (padrão: apaga)
- Sem flags — processa todos os áudios encontrados em todos os domínios

O modelo Whisper é detectado automaticamente com base na GPU/VRAM disponível. Não pergunte ao usuário sobre isso.

## Comportamento

### Passo 1 — Mapear áudios

Use PowerShell para varrer `vault/Capture/Fleeting/` recursivamente e coletar arquivos com extensões: `.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.aac`, `.wma`, `.mp4`, `.webm`.

Para cada arquivo encontrado:
- **Domínio**: subdiretório imediato dentro de `Fleeting/` (ex.: `Orçamento Público` de `Fleeting/Orçamento Público/aula.mp3`). Se o áudio estiver direto em `Fleeting/` sem subdiretório de domínio → `Não Classificados`.
- **Título**: stem do arquivo, com hífens e underscores trocados por espaços, capitalizado por palavra, usando dois dígitos para aulas de 1 a 9 (ex.: `aula-03-creditos` → `Aula 03 Creditos`; `aula-33-creditos` → `Aula 33 Creditos`).
- **Já transcrito**: verificar se existe `.md` com o mesmo stem no mesmo diretório — se sim, pular e informar.

Se não houver nenhum áudio pendente, informe e encerre.

### Passo 2 — Apresentar lista e aguardar confirmação

Exiba a lista de áudios pendentes antes de transcrever:

```
## Áudios para transcrever (<data>)

| Arquivo | Título derivado | Domínio |
|---------|----------------|---------|
| vault/Capture/Fleeting/Orçamento Público/aula-33.mp3 | Aula 33 | Orçamento Público |
| vault/Capture/Fleeting/Não Classificados/reuniao.m4a | Reuniao | Não Classificados |

Confirma? (ou corrija título/domínio por item antes de prosseguir)
```

Aguarde confirmação explícita do usuário. Aceite correções inline (ex.: "o segundo chama 'Reunião de Projeto', domínio Administração").

### Passo 3 — Transcrever

Para cada áudio confirmado, execute via Bash em sequência usando **Python 3.10** (torch/Whisper não suportam Python 3.12+):

```bash
py -3.10 transcribe.py "<caminho_absoluto_audio>" --title "<título corrigido>" --domain "<domínio>"
```

Se o usuário passou `--keep`, adicione a flag ao comando. Caso contrário, o script apaga o áudio automaticamente após salvar a Fleeting. O script detecta e imprime qual modelo foi escolhido — inclua essa informação no relatório final.

Exiba progresso a cada arquivo concluído:
```
[1/2] ✓ Fleeting — Aula 33.md → vault/Capture/Fleeting/Orçamento Público/
[2/2] ✓ Fleeting — Reunião de Projeto.md → vault/Capture/Fleeting/Administração/
```

Se `transcribe.py` retornar erro (Whisper não instalado, ffmpeg ausente, arquivo corrompido), exiba a mensagem de erro por item e continue os demais. Não interrompa o lote por falha individual.

### Passo 4 — Relatório final

```
## Resultado /transcribe — <data>

**Transcritos:** N
**Já existentes (pulados):** M
**Erros:** K

### Transcritos
- [[Fleeting — Aula 33]] — Orçamento Público
- [[Fleeting — Reunião de Projeto]] — Administração

### Erros
- reuniao-antiga.mp3 — ffmpeg não encontrado

---
Próximo passo: /inbox para classificar as novas fleetings ou /ingest para ingerir diretamente.
```

## Limite

Não edita o conteúdo transcrito. Não cria Literature, PIC ou qualquer nota além da Fleeting gerada pelo script. O áudio original é apagado após transcrição bem-sucedida, exceto com `--keep`.
