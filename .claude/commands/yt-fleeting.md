# Skill: /yt-fleeting

Busca a transcrição de um vídeo do YouTube e cria uma `Fleeting — <Título>.md` em `vault/Capture/Fleeting/<domínio>/`, pronta para o fluxo `/inbox` → `/ingest`.

## Uso

```
/yt-fleeting <url> [--domain <domínio>]
```

- `<url>` — URL do YouTube (obrigatório)
- `--domain <domínio>` — domínio do vault onde salvar a Fleeting (opcional; se omitido, pergunta ao usuário)

## Comportamento

### Passo 1 — Parsear argumentos

Extraia a URL e, se `--domain` estiver presente, o domínio. Domínios válidos: `Hardware`, `Software`, `Infraestrutura`, `Sistemas de Informação`, `Orçamento Público`, `Direito Constitucional`, `Administração`, `Libras`, `Não Classificados`. Se não informado, pergunte ao usuário antes de continuar.

### Passo 2 — Obter título do vídeo

Execute via Bash:

```bash
yt-dlp --print "%(title)s" --no-playlist "<url>"
```

Se yt-dlp falhar ou não estiver instalado, derive o video ID via regex `(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})` e use-o como título provisório. Informe o usuário sobre o título provisório.

### Passo 3 — Tentar legenda do YouTube

Execute via Bash:

```bash
python -c "
import sys, re
from youtube_transcript_api import YouTubeTranscriptApi
url = sys.argv[1]
m = re.search(r'(?:v=|youtu\\.be/)([A-Za-z0-9_-]{11})', url)
vid = m.group(1) if m else url.strip()
api = YouTubeTranscriptApi()
t = api.fetch(vid, languages=['pt', 'pt-BR', 'en'])
print(' '.join(s.text for s in t))
" "<url>"
```

- **Sucesso** → prossiga para **Passo 4**.
- **Erro** (qualquer exceção, incluindo `NoTranscriptFound`, `TranscriptsDisabled`) → prossiga para **Passo 5**.

### Passo 4 — Criar Fleeting via legenda

Sanitize o título para uso como nome de arquivo: remova os caracteres `\ / : * ? " < > |`, substitua múltiplos espaços por um único espaço, limite a 80 caracteres.

Gere o ID como `YYYYMMDDHHmmss` (data/hora atual). Crie o arquivo:

```
vault/Capture/Fleeting/<domínio>/Fleeting — <título sanitizado>.md
```

Conteúdo:

```markdown
---
id: <id>
type: fleeting
title: Fleeting — <título original>
created: <YYYY-MM-DD>
domain: <domínio>
source: <url>
tags: [fleeting]
status: open
---

# <título original>

<transcrição completa>
```

Informe o arquivo criado e vá para **Passo 6**.

### Passo 5 — Fallback: yt-dlp + Whisper

Informe o usuário que não há legenda disponível e que será feito download do áudio para transcrição local.

1. Derive `<slug>` do título sanitizado (ou use o video ID se o título não estiver disponível).

2. Baixe o áudio:
   ```bash
   yt-dlp -x --audio-format mp3 -o "vault/Capture/Fleeting/<domínio>/<slug>.mp3" "<url>"
   ```

3. Transcreva com Whisper via `transcribe.py` (usando Python 3.10):
   ```bash
   py -3.10 transcribe.py "vault/Capture/Fleeting/<domínio>/<slug>.mp3" --title "<título>" --domain "<domínio>"
   ```
   O script cria a Fleeting com frontmatter correto e apaga o áudio automaticamente.

4. Se `transcribe.py` não estiver disponível ou Whisper não estiver instalado, informe:
   > Não foi possível transcrever automaticamente. O áudio foi salvo em `vault/Capture/Fleeting/<domínio>/<slug>.mp3`. Instale o Whisper e rode `/transcribe` para concluir.
   
   Encerre sem criar a Fleeting.

### Passo 6 — Relatório final

```
## Resultado /yt-fleeting

**Vídeo:** <título>
**URL:** <url>
**Domínio:** <domínio>
**Método:** legenda YouTube | Whisper (fallback) | áudio salvo (pendente /transcribe)
**Arquivo:** [[Fleeting — <título>]]

---
Próximo passo: /inbox para classificar ou /ingest para ingerir diretamente.
```
