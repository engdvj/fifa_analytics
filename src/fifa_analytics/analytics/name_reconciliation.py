"""Reconciliação de nomes de jogador entre fontes (roster x estatísticas).

A ESPN nem sempre escreve o nome igual no elenco e nas estatísticas da partida
(ex.: roster "Agustín Canobbio", stats "Agustín Cano"). Isso quebra o casamento
por nome e o jogador aparece duplicado no dashboard. Aqui ficam duas coisas:

1. `apply_player_aliases` — aplica correções manuais de `config/player_aliases.yaml`
   ao nome do jogador ANTES de qualquer casamento por nome.
2. `detect_name_mismatches` — encontra nomes de stats que não casam com nenhum
   nome do roster mas se parecem MUITO com algum (provável truncamento/inconsistência),
   loga um WARNING e persiste num relatório de qualidade para revisão. Assim, novos
   casos como o "Cano(bbio)" não passam despercebidos.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd

from fifa_analytics.paths import CONFIG_DIR, GOLD_DIR
from fifa_analytics.utils.io import read_yaml, write_dataframe
from fifa_analytics.utils.logging import get_logger

logger = get_logger("name_reconciliation")

ALIASES_PATH = CONFIG_DIR / "player_aliases.yaml"
# Relatório de inconsistências de nome detectadas — uma linha por par suspeito.
# Vive no gold (saída de qualidade), não em manifests. Consumido por quem quiser
# revisar/curar os apelidos; o WARNING no log é o aviso imediato.
MISMATCH_REPORT_PATH = GOLD_DIR / "quality" / "player_name_mismatches.parquet"


def _name_key(value: object) -> str:
    """Chave de comparação: minúsculas, sem acento, hífen→espaço, espaços colapsados."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ASCII", "ignore").decode()
    return " ".join(text.lower().replace("-", " ").split())


@lru_cache(maxsize=1)
def _load_aliases() -> dict[tuple[str, str], str]:
    """Carrega `config/player_aliases.yaml` → {(team_key, name_key_origem): nome_canonico}.

    Formato do YAML: ``{Seleção: {"Nome nas stats": "Nome canônico"}}``. A chave de
    busca é normalizada (acento/caixa/hífen) para tolerar variações triviais."""
    raw = read_yaml(ALIASES_PATH) or {}
    aliases: dict[tuple[str, str], str] = {}
    for team, mapping in raw.items():
        if not isinstance(mapping, dict):
            continue
        for origem, canonico in mapping.items():
            aliases[(_name_key(team), _name_key(origem))] = str(canonico)
    return aliases


def apply_player_aliases(frame: pd.DataFrame, *, team_col: str = "team", name_col: str = "player_name") -> pd.DataFrame:
    """Reescreve `name_col` segundo `config/player_aliases.yaml` (casado por team+nome).

    Não falha se o arquivo não existir ou as colunas faltarem — retorna o frame
    como está. Idempotente: aplicar o nome canônico de novo não muda nada."""
    if frame is None or frame.empty or team_col not in frame.columns or name_col not in frame.columns:
        return frame
    aliases = _load_aliases()
    if not aliases:
        return frame

    out = frame.copy()

    def _fix(row: pd.Series) -> object:
        key = (_name_key(row.get(team_col)), _name_key(row.get(name_col)))
        return aliases.get(key, row.get(name_col))

    out[name_col] = out.apply(_fix, axis=1)
    return out


def _looks_truncated(stats_key: str, roster_key: str) -> bool:
    """True se `stats_key` parece uma versão truncada de `roster_key`: mesmos tokens
    iniciais e o último token do stats é prefixo do último token do roster.
    Ex.: 'agustin cano' ⊂ 'agustin canobbio'. Evita falso positivo com nomes curtos."""
    s, r = stats_key.split(), roster_key.split()
    if not s or not r or s == r:
        return False
    if s[:-1] != r[:-1]:
        return False
    last_s, last_r = s[-1], r[-1]
    return len(last_s) >= 3 and last_r.startswith(last_s) and last_s != last_r


def detect_name_mismatches(
    player_stats: pd.DataFrame,
    rosters: pd.DataFrame,
    *,
    persist: bool = True,
) -> pd.DataFrame:
    """Detecta nomes de stats que não casam com o roster mas parecem truncamentos.

    Para cada (team, nome) em `player_stats` sem correspondência exata no roster,
    procura um nome do roster que seja claramente o mesmo jogador (ver
    `_looks_truncated`). Cada caso vira uma linha do relatório, com um WARNING no
    log. Retorna o DataFrame de casos (vazio se nenhum). Já-aliasados não aparecem:
    chame DEPOIS de `apply_player_aliases`."""
    cols = ["team", "stats_name", "roster_name", "detected_at"]
    if player_stats is None or player_stats.empty or rosters is None or rosters.empty:
        return pd.DataFrame(columns=cols)
    if "player_name" not in player_stats.columns or "player_name" not in rosters.columns:
        return pd.DataFrame(columns=cols)

    roster_by_team: dict[str, dict[str, str]] = {}
    for _, r in rosters.dropna(subset=["team", "player_name"]).iterrows():
        roster_by_team.setdefault(str(r["team"]), {})[_name_key(r["player_name"])] = str(r["player_name"])

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for _, p in player_stats.dropna(subset=["team", "player_name"]).iterrows():
        team, sname = str(p["team"]), str(p["player_name"])
        skey = _name_key(sname)
        roster_map = roster_by_team.get(team, {})
        if skey in roster_map:  # casa exato — ok
            continue
        if (team, skey) in seen:
            continue
        for rkey, rname in roster_map.items():
            if _looks_truncated(skey, rkey):
                rows.append({"team": team, "stats_name": sname, "roster_name": rname, "detected_at": now})
                seen.add((team, skey))
                logger.warning(
                    "Nome inconsistente entre stats e roster (%s): stats='%s' ~ roster='%s'. "
                    "Adicione em config/player_aliases.yaml para corrigir.",
                    team, sname, rname,
                )
                break

    report = pd.DataFrame(rows, columns=cols)
    if persist and not report.empty:
        write_dataframe(MISMATCH_REPORT_PATH, report)
    return report
