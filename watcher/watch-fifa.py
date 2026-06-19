#!/usr/bin/env python3
"""
Watch-Fifa — daemon do watcher da Copa 2026.

Diferente do PKM (que observa arquivos numa inbox), aqui o gatilho é a chegada de
resultados nas fontes. O daemon faz polling: a cada N minutos roda
`fifa-analytics atualizar`, detecta jogos finalizados que ainda não entraram no
ranking, e processa a fila um a um — gerando os snapshots e regenerando o HTML.
O progresso é reportado para a janela flutuante (fifa_progress) via socket.

Config por ambiente:
  FIFA_POLL_SECS         intervalo entre coletas (default 600 = 10 min)
  FIFA_IDLE_EXIT_SECS    encerra após X s sem nada a fazer (0 = nunca; default 0)
  FIFA_SKIP_UPDATE       "1" pula o `atualizar` e só processa a fila existente
  FIFA_SKIP_NARRATIVE    "1" pula a reescrita da narrativa por Claude
  FIFA_CLAUDE_BIN        caminho do binário `claude` (default: PATH ou ~/.local/bin)
  FIFA_*_TIMEOUT         timeout por etapa em s (UPDATE/SNAPSHOT/NARRATIVE/HTML)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "watcher"))
sys.path.insert(0, str(ROOT / "scripts"))

import fifa_progress as ui  # noqa: E402
from flags import flag  # noqa: E402

# Detector de status leve: bate direto na ESPN (sem reconciliar worldcup2026, que
# vive caindo). É a FONTE DE VERDADE do estado ao vivo/finalizado do watcher.
try:
    from check_matches import _collect as _espn_collect  # noqa: E402
except Exception:  # pragma: no cover — se faltar, cai no canônico (modo antigo)
    _espn_collect = None

VENV_BIN = ROOT / ".venv" / "bin"
FIFA_CLI = VENV_BIN / "fifa-analytics"
PY = VENV_BIN / "python"
BAR_CHART = ROOT / "scripts" / "bar_chart_race.py"
CLAUDE_BIN = os.environ.get("FIFA_CLAUDE_BIN") or shutil.which("claude") or str(
    Path.home() / ".local" / "bin" / "claude"
)

MATCHES_PATH = ROOT / "data" / "gold" / "dim_match" / "canonical_matches.parquet"
SOURCE_MAP_PATH = ROOT / "data" / "gold" / "dim_match" / "source_match_map.parquet"
SNAPSHOTS_DIR = ROOT / "data" / "gold" / "analytics" / "snapshots"
MATCH_ORDER_PATH = SNAPSHOTS_DIR / "match_order.json"
STOP_FILE = "/tmp/fifa-copa-stop"  # janela pede encerramento ao fechar
LOG_FILE = ROOT / "logs" / "watcher.log"

POLL_SECS = int(os.environ.get("FIFA_POLL_SECS", "600"))
LIVE_POLL_SECS = int(os.environ.get("FIFA_LIVE_POLL_SECS", "60"))  # mais rápido com jogo ao vivo
IDLE_EXIT_SECS = int(os.environ.get("FIFA_IDLE_EXIT_SECS", "0"))
SKIP_UPDATE = os.environ.get("FIFA_SKIP_UPDATE") == "1"
SKIP_NARRATIVE = os.environ.get("FIFA_SKIP_NARRATIVE") == "1"  # "1" pula a reescrita por Claude

# Timeouts por etapa (segundos). Coleta de fontes e narrativa por LLM são lentas;
# snapshot e remontagem são rápidos. Override por ambiente se necessário.
UPDATE_TIMEOUT = int(os.environ.get("FIFA_UPDATE_TIMEOUT", "900"))      # 15 min
SNAPSHOT_TIMEOUT = int(os.environ.get("FIFA_SNAPSHOT_TIMEOUT", "300"))  # 5 min
NARRATIVE_TIMEOUT = int(os.environ.get("FIFA_NARRATIVE_TIMEOUT", "600"))  # 10 min
HTML_TIMEOUT = int(os.environ.get("FIFA_HTML_TIMEOUT", "300"))         # 5 min

# Pulso para manter a janela mostrando "processando" durante etapas longas. Tem que
# ser bem menor que a guarda de estado-preso da janela (20s) para o ts nunca envelhecer.
HEARTBEAT_SECS = int(os.environ.get("FIFA_HEARTBEAT_SECS", "5"))


def log(msg: str):
    line = f"[watch-fifa] {time.strftime('%Y-%m-%d %H:%M:%S')} · {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # log em arquivo é best-effort; nunca derruba o daemon


def _env() -> dict:
    return {**os.environ, "PATH": str(VENV_BIN) + ":" + os.environ.get("PATH", "")}


def _heartbeat(stop: "threading.Event", pct: int | None, msg: str) -> None:
    """Republica o progresso a cada HEARTBEAT_SECS enquanto `stop` não é sinalizado.
    Anexa o tempo decorrido à mensagem para deixar visível que a etapa está viva."""
    started = time.monotonic()
    while not stop.wait(HEARTBEAT_SECS):
        elapsed = int(time.monotonic() - started)
        suffix = f" ({elapsed//60}m{elapsed%60:02d}s)" if elapsed >= 60 else f" ({elapsed}s)"
        ui.progress_update(pct, msg + suffix)


def _run(cmd: list[str], timeout: int | None = None, retries: int = 0,
         heartbeat: tuple[int | None, str] | None = None) -> tuple[int, str]:
    """Roda um comando com timeout e retry opcional.

    timeout=None → sem limite (compatível com o comportamento antigo).
    retries=N → tenta até N vezes adicionais em caso de timeout ou returncode!=0.
    heartbeat=(pct, msg) → enquanto o comando roda, republica esse progresso a cada
        HEARTBEAT_SECS para manter o `ts` fresco. Sem isso, etapas longas (coleta de
        fontes, narrativa) passam dos 20s sem novidade e a janela as confunde com
        "daemon parou" e volta a mostrar o estado ocioso (bug visual).
    Retorna (returncode, saída combinada). returncode 124 = timeout (convenção do `timeout`).
    """
    attempt = 0
    while True:
        stop = threading.Event()
        pulse = None
        if heartbeat is not None:
            hb_pct, hb_msg = heartbeat
            pulse = threading.Thread(target=_heartbeat, args=(stop, hb_pct, hb_msg), daemon=True)
            pulse.start()
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(ROOT),
                env=_env(), timeout=timeout,
            )
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired as e:
            partial = (e.stdout or "") + (e.stderr or "") if e.stdout or e.stderr else ""
            code, out = 124, f"TIMEOUT após {timeout}s\n{partial}"
        finally:
            stop.set()
            if pulse is not None:
                pulse.join(timeout=1)
        if code == 0 or attempt >= retries:
            return code, out
        attempt += 1
        log(f"retry {attempt}/{retries} (code={code}) → {' '.join(str(c) for c in cmd[:3])}…")
        time.sleep(3)


# ── narrativa (reescrita por Claude) ───────────────────────────────────────────

def _match_id_for(n: int) -> str | None:
    """Mapeia a posição cronológica N (a mesma usada por reprocessar-snapshots e
    pelo botão da janela) para o canonical_match_id, via match_order.json."""
    try:
        order = json.loads(MATCH_ORDER_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    ids = order.get("match_ids") if isinstance(order, dict) else order
    if not isinstance(ids, list) or not (1 <= n <= len(ids)):
        return None
    return ids[n - 1]


def _rewrite_narrative(n: int, hb_pct: int | None = None, hb_msg: str = "") -> tuple[bool, str]:
    """Reescreve a narrativa do jogo N com Claude headless, seguindo a skill
    atualizar-jogo. Retorna (sucesso, mensagem). Best-effort: se o Claude falhar,
    o relatório continua válido com o texto template — não trava o pipeline.

    hb_pct/hb_msg alimentam o heartbeat para a janela não achar que travou enquanto
    o Claude trabalha (etapa de ~1-2 min sem progresso intermediário)."""
    match_id = _match_id_for(n)
    if not match_id:
        return False, f"não consegui mapear jogo {n} → match_id"

    story_path = ROOT / "reports" / "fragments" / match_id / "01b_story.md"
    # Se já tem narrativa manual protegida, não regasta créditos reescrevendo.
    if story_path.exists() and story_path.read_text(encoding="utf-8").lstrip().startswith(
        "<!-- narrativa-manual -->"
    ):
        return True, "narrativa já manual (preservada)"

    prompt = (
        f"Use a skill atualizar-jogo para reescrever APENAS a narrativa "
        f"('A historia do jogo') do jogo {match_id}. Pule o passo 1 (não rode "
        f"`fifa-analytics atualizar` nem `relatorios-basicos` — os dados já estão "
        f"prontos e os snapshots já foram gerados). Faça: leia os dados reais do "
        f"jogo (passo 3), escreva a narrativa em prosa (passo 4), grave em "
        f"reports/fragments/{match_id}/01b_story.md com o marcador "
        f"<!-- narrativa-manual --> na primeira linha (passo 5), e rode "
        f"`fifa-analytics remontar-relatorio {match_id}`. Não toque em outros jogos."
    )
    code, out = _run(
        [CLAUDE_BIN, "-p", prompt, "--permission-mode", "acceptEdits"],
        timeout=NARRATIVE_TIMEOUT,
        heartbeat=(hb_pct, hb_msg) if hb_msg else None,
    )
    if code != 0:
        log(f"narrativa jogo {n} ({match_id}) falhou (code={code}):\n{out[-800:]}")
        return False, f"Claude falhou (code={code})"

    # Verifica que o marcador realmente entrou — prova de que a reescrita aconteceu.
    if story_path.exists() and story_path.read_text(encoding="utf-8").lstrip().startswith(
        "<!-- narrativa-manual -->"
    ):
        return True, "narrativa reescrita"
    return False, "Claude rodou mas o marcador não apareceu"


# ── leitura de estado ─────────────────────────────────────────────────────────

def _extract_snapshot_error(out: str) -> str:
    """Extrai o MOTIVO legível da falha do reprocessar-snapshots para mostrar na
    janela. A porta de qualidade imprime '• <motivo>' (ex.: 'eventos têm 4 gol(s),
    placar soma 5'); se não achar, cai num resumo da última linha não-vazia."""
    bullets = [ln.strip(" •\t") for ln in out.splitlines() if ln.strip().startswith("•")]
    if bullets:
        joined = "; ".join(bullets)
        return joined[:160] + ("…" if len(joined) > 160 else "")
    if "dados incompletos" in out or "inconsistente" in out:
        return "dados incompletos/inconsistentes na fonte (placar ≠ eventos)"
    tail = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return (tail[-1][:160] if tail else "erro desconhecido no snapshot")


def _match_key(a: str, b: str) -> frozenset:
    """Confronto independente de ordem casa/fora e de acento/caixa."""
    norm = lambda s: "".join(ch for ch in str(s).lower() if ch.isalnum())
    return frozenset({norm(a), norm(b)})


def _espn_status_by_match(days_back: int = 2) -> dict:
    """Mapa {confronto -> status ESPN} para hoje e os últimos dias (jogos podem
    virar finalizado depois da meia-noite). Fonte direta da ESPN — não depende de
    reconciliar a worldcup2026 (que vive caindo). Retorna {} se a ESPN falhar."""
    if _espn_collect is None:
        return {}
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    result: dict = {}
    for delta in range(days_back + 1):
        d = today - timedelta(days=delta)
        try:
            for m in _espn_collect(d):
                result[_match_key(m["home"], m["away"])] = m
        except Exception as exc:
            log(f"check_matches ESPN falhou para {d}: {exc}")
    return result


def _load_pending() -> list[tuple[int, str]]:
    """Retorna [(n_jogo, label)] dos jogos finalizados sem snapshot.

    CRÍTICO: o n_jogo é a posição em `match_order.json` — EXATAMENTE a mesma chave
    que `reprocessar-snapshots --jogo N` usa (`match_order[N-1]`). Numerar por
    ordem cronológica recalculada na hora era um bug latente: quando um jogo
    anterior finalizava tarde (ex.: Suíça via ESPN), todos os índices seguintes
    deslocavam e o clique processava o jogo errado. match_order é estável
    (preserva posições, só anexa novos), então é a única fonte segura do n.

    Placar exibido prefere a ESPN (mais fresco que o canônico). Jogos que a ESPN
    já dá como finalizados mas ainda não entraram no match_order aparecem assim
    que o `_process` reconciliar (ele roda indice-canonico + snapshot, que
    reconstrói o match_order).
    """
    import pandas as pd

    if not MATCHES_PATH.exists():
        return []

    # match_order pela MESMA função do pipeline (single source of truth): preserva
    # posições já processadas e ANEXA jogos recém-finalizados na ordem cronológica.
    # Reconstruir aqui (em vez de só ler o arquivo) garante que um jogo que acabou
    # de finalizar já apareça como pendente, sem esperar um snapshot run.
    try:
        from fifa_analytics.workflows.snapshot_pipeline import _load_match_order
        order = _load_match_order()
    except Exception:
        if not MATCH_ORDER_PATH.exists():
            return []
        try:
            order = json.loads(MATCH_ORDER_PATH.read_text())
        except (OSError, ValueError):
            return []

    matches = pd.read_parquet(MATCHES_PATH).set_index("match_id")
    espn = _espn_status_by_match()
    done = {int(p.stem.split("_")[-1]) for p in SNAPSHOTS_DIR.glob("snapshot_jogo_*.parquet")}

    pending = []
    for n, match_id in enumerate(order, 1):  # n = posição em match_order (= pipeline)
        if n in done or match_id not in matches.index:
            continue
        row = matches.loc[match_id]
        home, away = row.get("home_team", "?"), row.get("away_team", "?")
        m = espn.get(_match_key(home, away))
        if m is not None and m.get("home_score") is not None:
            score = f"{m['home_score']}–{m['away_score']}"  # placar fresco da ESPN
        else:
            hs, as_ = row.get("home_score"), row.get("away_score")
            score = f"{int(hs)}–{int(as_)}" if pd.notna(hs) and pd.notna(as_) else "?"
        label = f"Jogo {n:02d} · {home} {flag(home)} {score} {flag(away)} {away}"
        pending.append((n, label))
    return sorted(pending)


def _load_live() -> list[str]:
    """Retorna labels dos jogos acontecendo agora (ao vivo), com placar parcial.

    Direto da ESPN (`check_matches`) — em tempo real, sem depender de reconciliar
    a worldcup2026. Fallback: status do canônico se a ESPN falhar."""
    espn = _espn_status_by_match(days_back=1)
    if espn:
        labels = []
        for m in espn.values():
            if m.get("status") != "ao_vivo":
                continue
            hs, as_ = m.get("home_score") or "0", m.get("away_score") or "0"
            minute = f" ({m.get('detail')})" if m.get("detail") else ""
            labels.append(f"{m['home']} {flag(m['home'])} {hs}–{as_} {flag(m['away'])} {m['away']}{minute}")
        return labels

    # fallback: canônico (modo antigo)
    import pandas as pd

    if not MATCHES_PATH.exists():
        return []
    matches = pd.read_parquet(MATCHES_PATH)
    live = matches[matches["status"] == "ao_vivo"]
    labels = []
    for _, row in live.iterrows():
        home, away = row.get("home_team"), row.get("away_team")
        if pd.isna(home) or pd.isna(away):
            continue
        hs, as_ = row.get("home_score"), row.get("away_score")
        score = f"{int(hs)}–{int(as_)}" if pd.notna(hs) and pd.notna(as_) else "0–0"
        labels.append(f"{home} {flag(home)} {score} {flag(away)} {away}")
    return labels


def _schedule_sort_overrides() -> dict[str, tuple[str | None, str | None]]:
    """Best-effort schedule keys by canonical match id.

    The canonical index deliberately prioritizes worldcup2026 for operational
    fields, but that feed stores some kickoff times as local venue time. For
    ordering the watcher queue, ESPN's timestamp is a better common clock when
    available. This affects display order only; scores/status still come from the
    canonical table.
    """
    import pandas as pd

    if not SOURCE_MAP_PATH.exists():
        return {}

    try:
        source_map = pd.read_parquet(SOURCE_MAP_PATH)
    except Exception:
        return {}

    source_paths = [
        ("espn", ROOT / "data" / "silver" / "matches" / "espn_matches.parquet"),
        ("worldcup2026", ROOT / "data" / "silver" / "matches" / "worldcup2026_matches.parquet"),
    ]
    overrides: dict[str, tuple[str | None, str | None]] = {}

    for source, path in source_paths:
        if not path.exists():
            continue
        try:
            src = pd.read_parquet(path)
        except Exception:
            continue
        if src.empty or "match_id" not in src.columns:
            continue

        cols = [c for c in ["match_id", "date", "kickoff_time"] if c in src.columns]
        merged = source_map[source_map["source"] == source].merge(
            src[cols],
            left_on="source_match_id",
            right_on="match_id",
            how="left",
            suffixes=("", "_source"),
        )
        for _, row in merged.iterrows():
            canonical_id = row.get("canonical_match_id")
            if not canonical_id or canonical_id in overrides:
                continue
            date = row.get("date")
            time_text = row.get("kickoff_time")
            if pd.isna(date) and pd.isna(time_text):
                continue
            overrides[str(canonical_id)] = (
                None if pd.isna(date) else str(date)[:10],
                None if pd.isna(time_text) else str(time_text)[:5],
            )

    return overrides


def _load_agendados(limit: int = 12) -> list[str]:
    """Retorna labels dos próximos jogos agendados (sem placar), em ordem real.

    Exclui finalizados e ao_vivo — só os que ainda não começaram.
    Usados só para exibição na janela — não entram na fila de processamento.
    """
    import pandas as pd

    if not MATCHES_PATH.exists():
        return []

    matches = pd.read_parquet(MATCHES_PATH)
    agendados = matches[matches["status"] == "agendado"].copy()
    if agendados.empty:
        return []

    agendados["_sort_date"] = agendados["date"].astype("string") if "date" in agendados.columns else ""
    agendados["_sort_time"] = agendados["kickoff_time"].astype("string") if "kickoff_time" in agendados.columns else ""

    overrides = _schedule_sort_overrides()
    id_col = "canonical_match_id" if "canonical_match_id" in agendados.columns else "match_id"
    for idx, row in agendados.iterrows():
        date_time = overrides.get(str(row.get(id_col)))
        if not date_time:
            continue
        sort_date, sort_time = date_time
        if sort_date:
            agendados.at[idx, "_sort_date"] = sort_date
        if sort_time:
            agendados.at[idx, "_sort_time"] = sort_time

    sort_cols = [
        c for c in ["_sort_date", "_sort_time", "temporal_order", "match_number", "match_id"]
        if c in agendados.columns
    ]
    agendados = agendados.sort_values(sort_cols, na_position="last")

    labels = []
    for _, row in agendados.iterrows():
        home, away = row.get("home_team"), row.get("away_team")
        if pd.isna(home) or pd.isna(away):
            continue  # mata-mata ainda sem confronto definido
        date_str = str(row.get("date", ""))[:10]
        labels.append(f"{date_str} · {home} {flag(home)} × {flag(away)} {away}")
        if len(labels) >= limit:
            break
    return labels


# ── publicação do estado (sem processar) ──────────────────────────────────────

def _publish_lists_only():
    """Atualiza as listas (ao vivo/prontos/agendados) SEM tocar no estado de
    progresso — as setters usam o caminho list_only, que preserva o flag de erro.
    Usado após uma falha p/ refrescar as listas sem apagar a mensagem de erro."""
    ui.set_live(_load_live())
    ui.set_ready([{"n": n, "label": lbl} for n, lbl in _load_pending()])
    ui.set_scheduled(_load_agendados())


def _publish_state():
    """Coleta o estado atual e publica na janela: ao vivo + prontos + agendados."""
    live = _load_live()              # [label]
    pending = _load_pending()        # [(n, label)]
    agendados = _load_agendados()    # [label]
    ui.set_live(live)
    ui.set_ready([{"n": n, "label": lbl} for n, lbl in pending])
    ui.set_scheduled(agendados)
    if pending:
        ui.progress_idle(f"{len(pending)} jogo(s) pronto(s) para processar")
    elif live:
        ui.progress_idle(f"{len(live)} jogo(s) ao vivo")
    else:
        ui.progress_idle("Aguardando próximos jogos…")
    return pending, agendados


def _refresh_match_index(start_pct: int | None, label_prefix: str = "") -> bool:
    """Atualiza só o necessário para o watcher enxergar ao vivo/finalizados.

    Resiliência a ponto único de falha: a fonte operacional primária
    (worldcup2026) vive caindo com erro de TLS — quando isso acontecia, o método
    abortava e o watcher NUNCA via o jogo ao vivo, mesmo com ESPN funcionando e
    cobrindo o mesmo jogo (status ao_vivo, placar). Agora: tenta worldcup2026;
    se falhar, cai para a ESPN como fonte de status ao vivo. Só aborta se NENHUMA
    fonte operacional atualizar — aí não há o que reconciliar. O indice-canonico
    reconcilia com qualquer combinação de fontes disponíveis.
    """
    prefix = f"{label_prefix} · " if label_prefix else ""
    ui.progress_update(start_pct, f"{prefix}Atualizando jogos ao vivo…")

    # 1) fonte operacional primária (instável — SSL cai com frequência)
    log("atualizando fonte operacional")
    code, out = _run(
        [str(FIFA_CLI), "worldcup2026"],
        timeout=UPDATE_TIMEOUT,
        heartbeat=(start_pct, f"{prefix}Atualizando jogos ao vivo…"),
    )
    operacional_ok = code == 0
    if not operacional_ok:
        log(f"fonte operacional (worldcup2026) falhou (code={code}) — caindo para ESPN:\n{out[-300:]}")
        # 2) FALLBACK: ESPN também traz status ao_vivo + placar parcial. É a fonte
        #    que mantém o watcher funcional quando a worldcup26.ir está fora.
        ui.progress_update(start_pct, f"{prefix}Fonte primária fora · usando ESPN…")
        log("fallback: atualizando status pela ESPN")
        code, out = _run(
            [str(FIFA_CLI), "espn"],
            timeout=UPDATE_TIMEOUT,
            heartbeat=(start_pct, f"{prefix}Fonte primária fora · usando ESPN…"),
        )
        if code != 0:
            log(f"fallback ESPN também falhou (code={code}) — sem fonte de status ao vivo:\n{out[-300:]}")
            return False
        log("fallback ESPN ok — status ao vivo virá da ESPN nesta reconciliação")

    # 3) reconcilia o que houver (worldcup2026 OU ESPN) no índice canônico
    reconcile_pct = None if start_pct is None else min(95, start_pct + 45)
    ui.progress_update(reconcile_pct, f"{prefix}Reconciliando calendário…")
    log("reconciliando índice canônico")
    code, out = _run(
        [str(FIFA_CLI), "indice-canonico"],
        timeout=SNAPSHOT_TIMEOUT,
        heartbeat=(reconcile_pct, f"{prefix}Reconciliando calendário…"),
    )
    if code != 0:
        log(f"índice canônico falhou (code={code}):\n{out[-500:]}")
        return False
    return True


def _process(ns: list[int] | None) -> None:
    """Ciclo completo disparado pelo clique. Etapas por jogo, todas visíveis na
    janela: coleta → snapshot → narrativa (Claude) → HTML.

    Robustez: a coleta de fontes (etapa de rede, instável) NÃO bloqueia mais o
    snapshot — se ela falhar/expirar, seguimos com os dados já em disco. Cada etapa
    tem timeout próprio; o snapshot tem retry. A narrativa é best-effort: se o
    Claude falhar, o relatório continua válido com o texto template."""
    # ── Etapa 1/N · coleta as fontes (lenta, instável) — não bloqueante ──
    if not SKIP_UPDATE:
        _refresh_match_index(2, "Etapa 1")
        ui.progress_update(8, "Etapa 1 · Coletando detalhes das fontes…")
        log("coletando detalhes (atualizar)")
        code, out = _run(
            [str(FIFA_CLI), "atualizar", "--sem-worldcup2026"], timeout=UPDATE_TIMEOUT,
            heartbeat=(8, "Etapa 1 · Coletando detalhes das fontes…"),
        )
        if code != 0:
            log(f"coleta falhou (code={code}) — seguindo com dados em disco:\n{out[-500:]}")
            ui.progress_update(8, "Coleta falhou · usando dados em disco")
            time.sleep(1)

    # ── descobre os jogos prontos DEPOIS da coleta (placar pode ter finalizado agora) ──
    pending = _load_pending()
    if ns is not None:
        pending = [(n, lbl) for n, lbl in pending if n in ns]
    if not pending:
        log("não há jogos prontos para processar")
        ui.progress_done("Nada novo para processar")
        time.sleep(2)
        _publish_state()
        return

    total = len(pending)
    ok_count = 0
    for i, (n, label) in enumerate(pending):
        # Cada jogo ocupa uma faixa de 10%→90%; dentro dela, snapshot e narrativa.
        lo = 10 + int(i / total * 80)
        hi = 10 + int((i + 1) / total * 80)
        mid = lo + (hi - lo) // 2

        # ── Etapa 2 · snapshot (rápido, com retry — é o que marca o jogo como feito) ──
        ui.progress_update(lo, f"Snapshot · {label}")
        log(f"snapshot jogo {n}: {label}")
        code, out = _run(
            [str(FIFA_CLI), "reprocessar-snapshots", "--jogo", str(n)],
            timeout=SNAPSHOT_TIMEOUT, retries=1,
        )
        if code != 0:
            reason = _extract_snapshot_error(out)
            log(f"erro reprocessar-snapshots --jogo {n} (code={code}):\n{out[-500:]}")
            # atualiza as listas (o jogo continua pendente) SEM limpar o erro, e
            # publica o estado de ERRO por último p/ ficar visível e persistente.
            _publish_lists_only()
            ui.progress_error(f"Jogo {n} não processado — {reason}")
            return
        log(f"jogo {n} · snapshot ok")

        # ── Etapa 3 · narrativa por Claude (lenta, best-effort) ──
        if SKIP_NARRATIVE:
            log(f"jogo {n} · narrativa pulada (FIFA_SKIP_NARRATIVE=1)")
        else:
            narr_msg = f"Reescrevendo narrativa · {label}"
            ui.progress_update(mid, narr_msg)
            log(f"narrativa jogo {n}: chamando Claude…")
            success, msg = _rewrite_narrative(n, hb_pct=mid, hb_msg=narr_msg)
            log(f"jogo {n} · narrativa: {msg}")
            if not success:
                ui.progress_update(mid, f"Narrativa do jogo {n}: {msg}")
                time.sleep(1)  # mostra o aviso, mas não interrompe

        ok_count += 1
        ui.progress_update(hi, f"Jogo {n} concluído")

    # ── Etapa final · regenera o HTML ──
    ui.progress_update(95, "Gerando ranking_race.html…")
    code, out = _run([str(PY), str(BAR_CHART)], timeout=HTML_TIMEOUT)
    if code != 0:
        log(f"erro bar_chart_race (code={code}):\n{out[-500:]}")
        ui.progress_update(95, "Erro ao gerar HTML")
    else:
        ui.progress_done(f"{ok_count} jogo(s) processado(s) · HTML atualizado")
        log(f"HTML regenerado — {ok_count} jogo(s)")
    time.sleep(2)
    _publish_state()


def _refresh() -> None:
    """Só coleta as fontes e republica o estado (atualiza a lista de prontos/ao
    vivo/agendados), sem processar. Acionado pelo botão 'Atualizar'."""
    if not SKIP_UPDATE:
        _refresh_match_index(5)
    _publish_state()
    ui.progress_idle("Atualizado")


# Concorrência: um worker por vez (processo OU refresh). _working evita disparar
# dois ao mesmo tempo. Nada roda sozinho — tudo parte de um comando da janela.
_working = threading.Event()


def _run_worker(fn, *args):
    """Roda fn(*args) numa thread, com feedback imediato. Ignora se já há trabalho."""
    if _working.is_set():
        log("já há uma operação em andamento — ignorando comando")
        return

    def _job():
        _working.set()
        try:
            fn(*args)
        except Exception as e:
            log(f"erro no worker: {e}")
        finally:
            _working.clear()
    threading.Thread(target=_job, daemon=True).start()


def main():
    log(f"iniciado · skip_update={SKIP_UPDATE} · modo=sob-demanda (nada automático)")

    # limpa sinal de stop e comando órfão de uma execução anterior
    for f in (STOP_FILE, "/tmp/fifa-copa-cmd.json"):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass

    # publica o estado local na hora (sem coletar — nada automático)
    _publish_state()

    # loop: lê comandos da janela (processar / atualizar). Sem coleta periódica.
    while True:
        try:
            if os.path.exists(STOP_FILE):
                log("janela fechada — encerrando daemon.")
                os.unlink(STOP_FILE)
                return

            cmd = ui.read_command()
            if cmd:
                action = cmd.get("action")
                if action == "process":
                    log(f"comando: processar {cmd.get('ns') or 'todos'}")
                    ui.progress_update(0, "Iniciando…")
                    _run_worker(_process, cmd.get("ns"))
                elif action == "refresh":
                    log("comando: atualizar fontes")
                    _run_worker(_refresh)
        except Exception as e:
            log(f"exceção no ciclo: {e}")

        time.sleep(1)  # responde a cliques em ~1s


if __name__ == "__main__":
    main()
