# Skill: /copa

Watcher da Copa 2026. Detecta jogos novos finalizados, processa a fila e mantém o ranking_race.html atualizado.

## Uso

```
/copa              — mostra fila e aguarda aprovação
/copa --atualizar  — roda o pipeline completo antes de mostrar a fila
/copa --processar  — processa o próximo jogo da fila (um por vez)
/copa --tudo       — processa todos os jogos pendentes da fila
/copa --html       — apenas regenera o HTML e abre no browser
```

## Comportamento

### Passo 1 — Detectar estado atual

Sempre ao iniciar, leia:
- `data/gold/dim_match/canonical_matches.parquet` → jogos com status = "finalizado"
- `data/gold/analytics/snapshots/` → quais snapshots já existem (`snapshot_jogo_NNN.parquet`)
- `reports/tournament/ranking_race.html` → mtime para saber quando foi gerado

Derive:
- **Jogos finalizados**: status == "finalizado", ordenados por data
- **Jogos processados**: snapshots existentes (N de `snapshot_jogo_NNN.parquet`)
- **Fila pendente**: finalizados cujo número de ordem não tem snapshot correspondente

O número de ordem do jogo segue `data/gold/analytics/snapshots/match_order.json` (ordem cronológica),
não o sufixo numérico do match_id. Se match_order.json não existir, gere com
`fifa-analytics reprocessar-snapshots --jogo 1`.

### Passo 2 — Apresentar diagnóstico

```
## Copa 2026 · <data>

Processados  (N): Jogo 01 · México 2–0 África do Sul ✓ ... Jogo 17 · França 3–1 Senegal ✓
Pendentes    (M): Jogo 18 · Iraque ? Noruega  ← próximo
Agendados    (K): jogos sem resultado ainda

HTML: reports/tournament/ranking_race.html — gerado em <timestamp>

/copa --processar   → processa Jogo 18
/copa --tudo        → processa os M pendentes
/copa --html        → só regenera o HTML
```

Se não houver pendentes: "Tudo em dia — N jogos processados."

### Passo 3 — --atualizar

Rode antes de mostrar o diagnóstico:

```bash
source .venv/bin/activate && fifa-analytics atualizar
```

Reporte quantos jogos novos foram coletados e qualquer erro. Depois vá para Passo 2.

### Passo 4 — --processar / --tudo

Para cada jogo da fila, processe o snapshot pelo número de ordem N (não use
`fifa-analytics scores` — ele não adiciona jogos novos ao snapshot):

```bash
source .venv/bin/activate
fifa-analytics reprocessar-snapshots --jogo N    # um por jogo pendente
python3 scripts/bar_chart_race.py                # uma vez ao final do lote
```

Mostre após cada jogo:
```
✓ Jogo 18 — França 3–1 Senegal
  Top 5 após este jogo:
   1. Alemanha   79.9
   2. França     76.1  ▲+1
   3. Suécia     75.8  ▼-1
   ...
```

Com `--processar`: para após o primeiro jogo e mostra estado atualizado.
Com `--tudo`: processa todos em sequência, mostra progresso a cada um.

Ao terminar qualquer processamento, vá para Passo 5.

### Passo 5 — Abrir HTML

```bash
xdg-open reports/tournament/ranking_race.html
```

Se falhar, informe o caminho absoluto para o usuário abrir manualmente.

## App nativo (alternativa à skill)

Para um fluxo sem Claude, há o watcher em `watcher/` — janela flutuante (tkinter)
+ daemon que coleta jogos novos e atualiza o ranking sozinho:

```bash
bash watcher/install.sh        # instala e ativa os serviços systemd (usuário)
bash watcher/run-window.sh     # abre só a janela, avulso, sem serviço
journalctl --user -u fifa-watcher -f   # logs do daemon
```

O daemon faz polling (`FIFA_POLL_SECS`, default 600s): roda `atualizar`, detecta
jogos finalizados sem snapshot e processa a fila via `reprocessar-snapshots`,
reportando o progresso para a janela por socket (`/tmp/fifa-copa.sock`).
