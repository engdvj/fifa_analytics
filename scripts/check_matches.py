#!/usr/bin/env python3
"""Verificador simples e rápido de jogos da Copa 2026.

Bate direto no scoreboard público da ESPN (sem chave, sem reconciliação pesada,
sem depender da worldcup26.ir que vive caindo) e responde duas perguntas:

  1. Qual o placar/estado de cada jogo AGORA (agendado / ao vivo / finalizado),
     com horário já convertido para o fuso de Brasília.
  2. Quais jogos FINALIZADOS ainda NÃO foram processados (sem snapshot) —
     ou seja, prontos para você iniciar o processo.

Uso:
    python scripts/check_matches.py                # hoje
    python scripts/check_matches.py 2026-06-19     # uma data
    python scripts/check_matches.py --pendentes    # só os finalizados não processados (1 por linha)
    python scripts/check_matches.py --json         # saída estruturada p/ outro script consumir

A fonte é a mesma que o pipeline já usa (site.api.espn.com). Isto NÃO substitui
o pipeline — é o "termômetro" rápido pra saber o que dá pra processar.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from fifa_analytics.transforms.team_names import traduzir_selecao
except Exception:  # pragma: no cover — fallback se rodar fora do venv
    def traduzir_selecao(name: str) -> str:
        return name

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
)
BRT = ZoneInfo("America/Sao_Paulo")
SNAPSHOTS_DIR = ROOT / "data" / "gold" / "analytics" / "snapshots"
MATCH_ORDER_PATH = SNAPSHOTS_DIR / "match_order.json"
CANONICAL_MATCHES = ROOT / "data" / "gold" / "dim_match" / "canonical_matches.parquet"

# estado da ESPN -> rótulo + chave estável
_STATE = {
    "pre": ("agendado", "📅"),
    "in": ("ao_vivo", "🔴"),
    "post": ("finalizado", "✅"),
}


def _fetch(d: date) -> dict:
    url = f"{ESPN_SCOREBOARD}?dates={d.strftime('%Y%m%d')}"
    req = urllib.request.Request(url, headers={"User-Agent": "fifa-analytics/checker"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _kickoff_brt(iso_utc: str | None) -> str:
    if not iso_utc:
        return ""
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(BRT).strftime("%d/%m %H:%M")
    except ValueError:
        return ""


def _name_key(a: str, b: str) -> frozenset[str]:
    """Chave do confronto independente de ordem casa/fora e de acento/caixa."""
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    return frozenset({norm(a), norm(b)})


def _processed_match_keys() -> set[frozenset[str]]:
    """Confrontos já processados = têm snapshot. Lê o canônico para mapear
    a posição cronológica (match_order) ao par de times."""
    if not (MATCH_ORDER_PATH.exists() and CANONICAL_MATCHES.exists()):
        return set()
    try:
        import pandas as pd

        order = json.loads(MATCH_ORDER_PATH.read_text())
        snaps = {
            int(os.path.basename(f).split("_")[-1].split(".")[0])
            for f in glob.glob(str(SNAPSHOTS_DIR / "snapshot_jogo_*.parquet"))
        }
        m = pd.read_parquet(CANONICAL_MATCHES).set_index("match_id")
        keys: set[frozenset[str]] = set()
        for pos, mid in enumerate(order, start=1):  # snapshot N = order[N-1]
            if pos in snaps and mid in m.index:
                row = m.loc[mid]
                h, a = row.get("home_team"), row.get("away_team")
                if isinstance(h, str) and isinstance(a, str):
                    keys.add(_name_key(h, a))
        return keys
    except Exception:
        return set()


def _collect(d: date) -> list[dict]:
    data = _fetch(d)
    processed = _processed_match_keys()
    out = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        st = comp["status"]["type"]
        state = st.get("state")
        status, icon = _STATE.get(state, ("desconhecido", "❔"))
        comps = comp["competitors"]
        home = next((x for x in comps if x.get("homeAway") == "home"), comps[0])
        away = next((x for x in comps if x.get("homeAway") == "away"), comps[-1])
        h_name = traduzir_selecao(home["team"]["displayName"])
        a_name = traduzir_selecao(away["team"]["displayName"])
        finished = status == "finalizado"
        key = _name_key(h_name, a_name)
        out.append({
            "home": h_name,
            "away": a_name,
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "status": status,
            "icon": icon,
            "detail": st.get("detail", ""),
            "kickoff_brt": _kickoff_brt(e.get("date")),
            "finished": finished,
            "processed": key in processed,
            "ready_to_process": finished and key not in processed,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?", help="Data YYYY-MM-DD (padrão: hoje em Brasília)")
    ap.add_argument("--pendentes", action="store_true", help="Só os finalizados não processados")
    ap.add_argument("--json", action="store_true", help="Saída JSON")
    args = ap.parse_args()

    d = date.fromisoformat(args.data) if args.data else datetime.now(BRT).date()

    try:
        matches = _collect(d)
    except Exception as exc:
        print(f"erro ao consultar a ESPN: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"date": d.isoformat(), "matches": matches}, ensure_ascii=False, indent=2))
        return 0

    if args.pendentes:
        ready = [m for m in matches if m["ready_to_process"]]
        if not ready:
            print("nenhum jogo finalizado pendente de processamento.")
            return 0
        for m in ready:
            print(f"{m['home']} {m['home_score']}-{m['away_score']} {m['away']}")
        return 0

    print(f"Jogos em {d.strftime('%d/%m/%Y')} (fuso de Brasília):\n")
    for m in matches:
        score = (
            f"{m['home_score']}-{m['away_score']}"
            if m["home_score"] is not None and m["status"] != "agendado"
            else "  ·  "
        )
        when = m["kickoff_brt"] or m["detail"]
        flag = ""
        if m["ready_to_process"]:
            flag = "  ⟵ PRONTO PARA PROCESSAR"
        elif m["finished"] and m["processed"]:
            flag = "  (já processado)"
        elif m["status"] == "ao_vivo":
            flag = f"  ({m['detail']})"
        print(f"  {m['icon']} {m['home']:>26} {score:^7} {m['away']:<26}  {when}{flag}")

    ready = [m for m in matches if m["ready_to_process"]]
    print()
    if ready:
        print(f"➡  {len(ready)} jogo(s) finalizado(s) pronto(s) para processar.")
    else:
        print("nenhum jogo finalizado pendente de processamento.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
