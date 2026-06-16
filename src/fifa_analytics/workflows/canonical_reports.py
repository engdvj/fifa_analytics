from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fifa_analytics.utils.text import position_label, position_order, slugify
from fifa_analytics.paths import FINAL_REPORTS_DIR, GOLD_DIR, MANIFESTS_DIR, SILVER_DIR
from fifa_analytics.reporting.build_report import build_match_report
from fifa_analytics.reporting.fragments import render_template, write_fragment
from fifa_analytics.reporting.tournament_reports import format_standings_table
from fifa_analytics.utils.io import ensure_dir, read_dataframe, read_json, write_dataframe, write_json
from fifa_analytics.utils.time import utc_now_iso


SOURCE_PRIORITY = ["worldcup2026", "espn", "wikipedia"]
EVENT_SOURCE_PRIORITY = ["espn", "worldcup2026", "wikipedia"]

# Família de evento para fins de deduplicação entre fontes: fontes diferentes
# classificam o mesmo gol como "gol", "gol_penalti" ou "gol_contra" (ex: ESPN marca
# gol_contra corretamente, worldcup2026 só registra "gol") — tratar como
# equivalentes evita o mesmo gol aparecer duas vezes na timeline canônica.
# A versão mantida (com a classificação certa) vem da prioridade de fonte.
_EVENT_DEDUP_FAMILY = {
    "gol": "gol",
    "gol_penalti": "gol",
    "gol_contra": "gol",
    "cartao_amarelo": "cartao_amarelo",
    "cartao_vermelho": "cartao_vermelho",
}


def run_canonical_index() -> dict[str, Path | int]:
    source_matches = _load_source_matches()
    if not source_matches:
        raise FileNotFoundError("Nenhuma fonte de partidas encontrada. Rode worldcup2026 ou wikipedia primeiro.")

    canonical_matches, source_map = build_canonical_index(source_matches)
    canonical_events = build_canonical_events(source_map)
    canonical_team_stats = build_canonical_dataset(source_map, "fact_team_match_stats", "team_stats")
    canonical_lineups = build_canonical_dataset(source_map, "lineups", "lineups")
    canonical_player_stats = build_canonical_dataset(source_map, "fact_player_match_stats", "player_stats")
    canonical_match_info = build_canonical_dataset(source_map, "match_info", "match_info")
    canonical_commentary = build_canonical_dataset(source_map, "fact_commentary", "commentary")
    canonical_shots = build_canonical_dataset(source_map, "fact_shots", "shots")

    matches_path = write_dataframe(GOLD_DIR / "dim_match" / "canonical_matches.parquet", canonical_matches)
    source_map_path = write_dataframe(GOLD_DIR / "dim_match" / "source_match_map.parquet", source_map)
    events_path = write_dataframe(GOLD_DIR / "fact_events" / "canonical_events.parquet", canonical_events)
    team_stats_path = write_dataframe(GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet", canonical_team_stats)
    lineups_path = write_dataframe(GOLD_DIR / "lineups" / "canonical_lineups.parquet", canonical_lineups)
    player_stats_path = write_dataframe(GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet", canonical_player_stats)
    match_info_path = write_dataframe(GOLD_DIR / "match_info" / "canonical_match_info.parquet", canonical_match_info)
    commentary_path = write_dataframe(GOLD_DIR / "fact_commentary" / "canonical_commentary.parquet", canonical_commentary)
    shots_path = write_dataframe(GOLD_DIR / "fact_shots" / "canonical_shots.parquet", canonical_shots)
    metadata_path = write_json(
        GOLD_DIR / "dim_match" / "canonical_sources_metadata.json",
        {
            "generated_at": utc_now_iso(),
            "sources": sorted(source_matches),
            "canonical_matches": len(canonical_matches),
            "source_links": len(source_map),
            "canonical_events": len(canonical_events),
            "canonical_team_stats": len(canonical_team_stats),
            "canonical_lineups": len(canonical_lineups),
            "canonical_player_stats": len(canonical_player_stats),
            "canonical_match_info": len(canonical_match_info),
            "canonical_commentary": len(canonical_commentary),
            "canonical_shots": len(canonical_shots),
        },
    )

    return {
        "matches_path": matches_path,
        "source_map_path": source_map_path,
        "events_path": events_path,
        "team_stats_path": team_stats_path,
        "lineups_path": lineups_path,
        "player_stats_path": player_stats_path,
        "match_info_path": match_info_path,
        "commentary_path": commentary_path,
        "shots_path": shots_path,
        "metadata_path": metadata_path,
        "matches": len(canonical_matches),
        "source_links": len(source_map),
        "events": len(canonical_events),
        "team_stats": len(canonical_team_stats),
        "lineups": len(canonical_lineups),
        "player_stats": len(canonical_player_stats),
        "match_info": len(canonical_match_info),
        "commentary": len(canonical_commentary),
        "shots": len(canonical_shots),
    }


def run_canonical_reports(status: str = "finalizado") -> dict[str, Path | str | int | list | None]:
    index_result = run_canonical_index()
    matches = read_dataframe(GOLD_DIR / "dim_match" / "canonical_matches.parquet")
    source_map = read_dataframe(GOLD_DIR / "dim_match" / "source_match_map.parquet")
    events_path = GOLD_DIR / "fact_events" / "canonical_events.parquet"
    events = read_dataframe(events_path) if events_path.exists() else pd.DataFrame()
    team_stats_path = GOLD_DIR / "fact_team_match_stats" / "canonical_team_stats.parquet"
    team_stats = read_dataframe(team_stats_path) if team_stats_path.exists() else pd.DataFrame()
    match_info_path = GOLD_DIR / "match_info" / "canonical_match_info.parquet"
    match_info = read_dataframe(match_info_path) if match_info_path.exists() else pd.DataFrame()
    lineups_path = GOLD_DIR / "lineups" / "canonical_lineups.parquet"
    lineups = read_dataframe(lineups_path) if lineups_path.exists() else pd.DataFrame()
    player_stats_path = GOLD_DIR / "fact_player_match_stats" / "canonical_player_stats.parquet"
    player_stats = read_dataframe(player_stats_path) if player_stats_path.exists() else pd.DataFrame()
    selected_matches = _filter_matches(matches, status)

    report_results = []
    for _, match in selected_matches.iterrows():
        match_dict = match.to_dict()
        match_sources = source_map[source_map["canonical_match_id"] == match_dict["canonical_match_id"]].copy()
        data_quality_status, checks = _data_quality_checks(match_dict, match_sources, events)
        write_canonical_fragments(
            match_dict,
            events,
            team_stats,
            match_info,
            lineups,
            player_stats,
            data_quality_status,
            checks,
        )
        report_subdir, report_filename = _report_location(match_dict)
        report_results.append(
            build_match_report(
                match_dict["canonical_match_id"],
                data_quality_status=data_quality_status,
                extra_manifest={
                    "canonical_match_id": match_dict["canonical_match_id"],
                    "sources_used": match_sources["source"].tolist(),
                    "source_match_ids": _source_ids_for_manifest(match_sources),
                    "primary_source": match_dict.get("primary_source"),
                },
                report_subdir=report_subdir,
                report_filename=report_filename,
            )
        )

    return {
        "fonte": "canonical",
        "status_processado": status,
        "partidas_encontradas": len(selected_matches),
        "relatorios_gerados": len(report_results),
        "primeiro_relatorio": report_results[0]["report_path"] if report_results else None,
        **index_result,
    }


def rebuild_match_report(match_id: str) -> dict[str, Path | str | int | list | None]:
    """Remonta o relatorio final de um unico jogo a partir dos fragmentos atuais
    em reports/fragments/{match_id}/, sem recalcular nada — usado apos editar
    manualmente um fragmento (ex: 01b_story.md reescrito por uma narrativa
    melhor) para refletir a mudanca no relatorio final sem rodar o pipeline todo."""
    manifest_path = MANIFESTS_DIR / f"{match_id}.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest nao encontrado para {match_id}: rode 'fifa-analytics relatorios-basicos' primeiro.")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    final_report_path = Path(manifest["final_report_path"])
    report_subdir = str(final_report_path.parent.relative_to(FINAL_REPORTS_DIR))
    report_filename = final_report_path.stem

    return build_match_report(
        match_id,
        data_quality_status=manifest.get("data_quality_status", "desconhecido"),
        extra_manifest={
            "canonical_match_id": manifest.get("canonical_match_id"),
            "sources_used": manifest.get("sources_used"),
            "source_match_ids": manifest.get("source_match_ids"),
            "primary_source": manifest.get("primary_source"),
        },
        report_subdir=report_subdir,
        report_filename=report_filename,
    )


def build_canonical_index(source_matches: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    source_rows = _prepare_source_rows(source_matches)
    primary_source = _primary_source(source_matches)
    primary_rows = source_rows[source_rows["source"] == primary_source].copy()
    primary_rows = primary_rows.sort_values(
        ["source_match_number", "date", "source_match_id_text"],
        na_position="last",
    )

    canonical_rows: list[dict[str, Any]] = []
    source_map_rows: list[dict[str, Any]] = []
    matched_source_indexes: set[int] = set()

    for _, primary in primary_rows.iterrows():
        canonical_match_id = _canonical_match_id(primary)
        same_match = _matching_rows(source_rows, primary)
        source_records = same_match.sort_values("source_priority").to_dict("records")
        chosen = _choose_best_record(source_records)

        canonical_rows.append(_canonical_row(canonical_match_id, chosen, source_records))
        for source_record in source_records:
            matched_source_indexes.add(source_record["_row_index"])
            source_map_rows.append(_source_map_row(canonical_match_id, source_record))

    remaining = source_rows[~source_rows["_row_index"].isin(matched_source_indexes)].copy()
    for _, row in remaining.sort_values(["source_priority", "source_match_number", "source_match_id_text"]).iterrows():
        source_record = row.to_dict()
        canonical_match_id = _canonical_match_id(row) if row["source"] == primary_source else _unmatched_source_match_id(row)
        canonical_rows.append(_canonical_row(canonical_match_id, source_record, [source_record]))
        source_map_rows.append(_source_map_row(canonical_match_id, source_record))

    canonical = pd.DataFrame(canonical_rows).drop_duplicates(subset=["canonical_match_id"]).reset_index(drop=True)
    canonical = _add_temporal_order(canonical)
    source_map = pd.DataFrame(source_map_rows).drop_duplicates(subset=["canonical_match_id", "source"]).reset_index(drop=True)
    return canonical, source_map


def build_canonical_events(source_map: pd.DataFrame) -> pd.DataFrame:
    event_frames = []
    for source in EVENT_SOURCE_PRIORITY:
        path = _events_path(source)
        if not path.exists():
            continue
        events = read_dataframe(path)
        if events.empty:
            continue
        mappings = source_map[source_map["source"] == source][["canonical_match_id", "source_match_id"]].rename(
            columns={"source_match_id": "source_event_match_id"}
        )
        events = events.merge(mappings, left_on="match_id", right_on="source_event_match_id", how="inner")
        if events.empty:
            continue
        events = events.drop(columns=["match_id", "source_event_match_id"]).rename(columns={"canonical_match_id": "match_id"})
        events["event_source"] = source
        event_frames.append(events)

    if not event_frames:
        return pd.DataFrame()

    events = pd.concat(event_frames, ignore_index=True)
    events["source_priority"] = events["event_source"].map({source: index for index, source in enumerate(EVENT_SOURCE_PRIORITY)})
    events["_minute_base"] = (pd.to_numeric(events["minute_sort"], errors="coerce").fillna(0) // 100).astype(int)
    events["_event_family"] = events["event_type"].map(_EVENT_DEDUP_FAMILY).fillna(events["event_type"])
    events = events.sort_values(["match_id", "source_priority", "minute_sort"]).reset_index(drop=True)

    # Dedup com tolerância de 1' entre fontes: mesmo time + mesma família de
    # evento + minuto a no máximo 1' de distância de um evento já mantido
    # (ex: Wikipedia=50' / ESPN=51' para o mesmo gol não casam em minuto exato).
    keep_mask = pd.Series(True, index=events.index)
    kept_minute_by_key: dict[tuple[Any, Any, Any], list[int]] = {}
    for idx, row in events.iterrows():
        key = (row["match_id"], row["team"], row["_event_family"])
        minute = row["_minute_base"]
        kept_minutes = kept_minute_by_key.setdefault(key, [])
        if any(abs(minute - m) <= 1 for m in kept_minutes):
            keep_mask.loc[idx] = False
        else:
            kept_minutes.append(minute)

    events = (
        events[keep_mask]
        .sort_values(["match_id", "minute_sort"])
        .drop(columns=["source_priority", "_minute_base", "_event_family"])
        .reset_index(drop=True)
    )
    return events


def build_canonical_dataset(source_map: pd.DataFrame, gold_subdir: str, filename_suffix: str) -> pd.DataFrame:
    frames = []
    for source in SOURCE_PRIORITY:
        path = GOLD_DIR / gold_subdir / f"{source}_{filename_suffix}.parquet"
        if not path.exists():
            continue
        dataset = read_dataframe(path)
        if dataset.empty:
            continue
        mappings = source_map[source_map["source"] == source][["canonical_match_id", "source_match_id"]].rename(
            columns={"source_match_id": "source_dataset_match_id"}
        )
        dataset = dataset.merge(mappings, left_on="match_id", right_on="source_dataset_match_id", how="inner")
        if dataset.empty:
            continue
        dataset = dataset.drop(columns=["match_id", "source_dataset_match_id"]).rename(columns={"canonical_match_id": "match_id"})
        dataset["dataset_source"] = source
        frames.append(dataset)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def write_canonical_fragments(
    match: dict[str, Any],
    events: pd.DataFrame,
    team_stats: pd.DataFrame,
    match_info: pd.DataFrame,
    lineups: pd.DataFrame,
    player_stats: pd.DataFrame,
    data_quality_status: str,
    checks: list[dict[str, str]],
) -> None:
    match_id = match["canonical_match_id"]
    home_team = _display_team(match.get("home_team"))
    away_team = _display_team(match.get("away_team"))
    scoreline = None
    if pd.notna(match.get("home_score")) and pd.notna(match.get("away_score")):
        scoreline = f"{int(match['home_score'])} x {int(match['away_score'])}"

    info = _match_info_for_match(match_info, match_id)
    sources_used = next((c["status"] for c in checks if c["field"] == "fontes_vinculadas"), "")
    write_fragment(
        match_id,
        "00_metadata",
        render_template(
            "fragments/00_metadata.md.j2",
            {
                "match_id": match_id,
                "generated_at": utc_now_iso(),
                "status": match.get("status", "desconhecido"),
                "group": match.get("group"),
                "date": match.get("date"),
                "stadium": match.get("stadium"),
                "city": match.get("city"),
                "country": match.get("country"),
                "referee": info.get("referee"),
                "attendance": info.get("attendance"),
                "broadcasts": info.get("broadcasts"),
                "sources": sources_used,
                "data_quality_status": data_quality_status,
            },
        ),
    )
    write_fragment(
        match_id,
        "01_match_summary",
        render_template(
            "fragments/01_match_summary.md.j2",
            {
                "home_team": home_team,
                "away_team": away_team,
                "scoreline": scoreline,
                "status": match.get("status", "desconhecido"),
            },
        ),
    )

    match_team_stats = _team_stats_for_match(team_stats, match_id)
    match_events = _events_for_match(events, match_id)
    match_lineups = _lineups_for_match(lineups, match_id)
    match_player_stats = _player_stats_for_match(player_stats, match_id)
    write_fragment(
        match_id,
        "01b_story",
        render_template(
            "fragments/01b_story.md.j2",
            {"story": _build_match_story(match, match_team_stats, match_events, match_player_stats)},
        ),
        skip_if_manual=True,
    )
    write_fragment(
        match_id,
        "05_team_stats",
        render_template("fragments/05_team_stats.md.j2", {"team_stats": _format_match_team_stats(match, match_team_stats)}),
    )
    write_fragment(
        match_id,
        "03_lineups",
        render_template("fragments/03_lineups.md.j2", {"lineups": _format_lineups(match_lineups, match_player_stats)}),
    )


def _load_source_matches() -> dict[str, pd.DataFrame]:
    frames = {}
    for source in SOURCE_PRIORITY:
        path = _matches_path(source)
        if path.exists():
            frames[source] = read_dataframe(path)
    return frames


def _prepare_source_rows(source_matches: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for source, matches in source_matches.items():
        frame = matches.copy()
        for column in _optional_match_columns():
            if column not in frame.columns:
                frame[column] = None
        frame["source"] = source
        frame["source_priority"] = SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)
        frame["source_match_id_text"] = frame["source_match_id"].astype(str)
        frame["source_match_number"] = frame["source_match_id_text"].str.extract(r"(\d+)")[0].astype(float)
        frame["match_key"] = frame.apply(_match_key, axis=1)
        frame["knockout_order_key"] = None
        knockout = frame[frame.apply(_is_knockout_placeholder, axis=1)].copy()
        if not knockout.empty:
            knockout = knockout.sort_values(["date", "source_match_number", "source_match_id_text"], na_position="last")
            frame.loc[knockout.index, "knockout_order_key"] = [
                f"mata_mata_{index:03d}" for index in range(1, len(knockout) + 1)
            ]
        frames.append(frame)

    rows = pd.concat(frames, ignore_index=True)
    rows["_row_index"] = rows.index
    return rows


def _optional_match_columns() -> list[str]:
    return [
        "source_match_id",
        "home_team",
        "away_team",
        "date",
        "kickoff_time",
        "timezone",
        "group",
        "stage",
        "round",
        "stadium",
        "city",
        "country",
        "status",
        "home_score",
        "away_score",
        "winner",
    ]


def _primary_source(source_matches: dict[str, pd.DataFrame]) -> str:
    for source in SOURCE_PRIORITY:
        if source in source_matches:
            return source
    return next(iter(source_matches))


def _matching_rows(source_rows: pd.DataFrame, primary: pd.Series) -> pd.DataFrame:
    if pd.notna(primary.get("match_key")) and primary.get("match_key"):
        return source_rows[source_rows["match_key"] == primary["match_key"]].copy()
    if pd.notna(primary.get("knockout_order_key")) and primary.get("knockout_order_key"):
        return source_rows[source_rows["knockout_order_key"] == primary["knockout_order_key"]].copy()
    return source_rows[(source_rows["source"] == primary["source"]) & (source_rows["source_match_id_text"] == primary["source_match_id_text"])].copy()


def _choose_best_record(source_records: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(source_records, key=lambda row: row["source_priority"])[0]


def _canonical_match_id(row: pd.Series | dict[str, Any]) -> str:
    source_number = row.get("source_match_number")
    if pd.notna(source_number):
        return f"copa_2026_jogo_{int(source_number):03d}"
    match_key = row.get("match_key")
    if match_key:
        return f"copa_2026_{_slug(match_key)}"
    return f"copa_2026_{_slug(str(row.get('source_match_id_text') or row.get('match_id')))}"


def _unmatched_source_match_id(row: pd.Series | dict[str, Any]) -> str:
    source = _slug(str(row.get("source") or "fonte"))
    source_number = row.get("source_match_number")
    if pd.notna(source_number):
        return f"copa_2026_{source}_jogo_{int(source_number):03d}"
    return f"copa_2026_{source}_{_slug(str(row.get('source_match_id_text') or row.get('match_id')))}"


def _canonical_row(canonical_match_id: str, chosen: dict[str, Any], source_records: list[dict[str, Any]]) -> dict[str, Any]:
    row = {
        "canonical_match_id": canonical_match_id,
        "match_id": canonical_match_id,
        "match_number": chosen.get("source_match_number"),
        "match_number_source": chosen.get("source"),
        "home_team": chosen.get("home_team"),
        "away_team": chosen.get("away_team"),
        "date": chosen.get("date"),
        "kickoff_time": chosen.get("kickoff_time"),
        "timezone": chosen.get("timezone"),
        "group": chosen.get("group"),
        "stage": chosen.get("stage"),
        "round": chosen.get("round"),
        "stadium": chosen.get("stadium"),
        "city": chosen.get("city"),
        "country": chosen.get("country"),
        "status": chosen.get("status", "desconhecido"),
        "home_score": chosen.get("home_score"),
        "away_score": chosen.get("away_score"),
        "winner": chosen.get("winner"),
        "primary_source": chosen.get("source"),
        "sources_count": len(source_records),
        "sources_json": json.dumps(_source_records_for_json(source_records), ensure_ascii=False),
        "last_updated_at": utc_now_iso(),
    }
    for source_record in source_records:
        source = source_record["source"]
        row[f"{source}_match_id"] = source_record.get("match_id")
        row[f"{source}_source_match_id"] = source_record.get("source_match_id")
    return row


def _add_temporal_order(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        canonical["temporal_order"] = pd.Series(dtype="int64")
        return canonical

    ordered_indexes = canonical.sort_values(
        ["date", "kickoff_time", "canonical_match_id"],
        na_position="last",
    ).index
    canonical = canonical.copy()
    canonical["temporal_order"] = 0
    canonical.loc[ordered_indexes, "temporal_order"] = range(1, len(canonical) + 1)
    return canonical.sort_values(["temporal_order", "canonical_match_id"]).reset_index(drop=True)


def _source_map_row(canonical_match_id: str, source_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_match_id": canonical_match_id,
        "source": source_record["source"],
        "source_match_id": source_record.get("match_id"),
        "source_source_match_id": source_record.get("source_match_id"),
        "source_match_number": source_record.get("source_match_number"),
        "match_key": source_record.get("match_key"),
        "home_team": source_record.get("home_team"),
        "away_team": source_record.get("away_team"),
        "status": source_record.get("status"),
        "home_score": source_record.get("home_score"),
        "away_score": source_record.get("away_score"),
    }


def _source_records_for_json(source_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for record in sorted(source_records, key=lambda row: row["source_priority"]):
        records.append(
            {
                "source": record.get("source"),
                "source_match_id": record.get("source_match_id"),
                "match_id": record.get("match_id"),
                "status": record.get("status"),
            }
        )
    return records


def _match_key(row: pd.Series) -> str | None:
    home_team = row.get("home_team")
    away_team = row.get("away_team")
    group = row.get("group")
    if pd.isna(home_team) or pd.isna(away_team) or not home_team or not away_team:
        return None
    if _is_placeholder_team(home_team) or _is_placeholder_team(away_team):
        return None
    teams = sorted([_slug(str(home_team)), _slug(str(away_team))])
    return "|".join([_slug(str(group)), *teams])


def _is_knockout_placeholder(row: pd.Series) -> bool:
    stage = str(row.get("stage") or "").lower()
    if stage in {"fase_de_grupos", "group-stage", "group"}:
        return False
    home_team = row.get("home_team")
    away_team = row.get("away_team")
    return (
        pd.isna(home_team)
        or pd.isna(away_team)
        or not home_team
        or not away_team
        or _is_placeholder_team(home_team)
        or _is_placeholder_team(away_team)
    )


def _is_placeholder_team(value: Any) -> bool:
    text = _slug(str(value))
    markers = [
        "group_",
        "round_of_",
        "quarterfinal",
        "semifinal",
        "winner",
        "loser",
        "third_place",
        "2nd_place",
        "a_definir",
    ]
    return any(marker in text for marker in markers)


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def _matches_path(source: str) -> Path:
    return SILVER_DIR / "matches" / f"{source}_matches.parquet"


def _events_path(source: str) -> Path:
    return GOLD_DIR / "fact_events" / f"{source}_events.parquet"


def _filter_matches(matches: pd.DataFrame, status: str) -> pd.DataFrame:
    if status == "todos":
        return matches
    return matches[matches["status"] == status].copy()


def _data_quality_checks(
    match: dict[str, Any], match_sources: pd.DataFrame, events: pd.DataFrame | None = None
) -> tuple[str, list[dict[str, str]]]:
    checks = [
        {"field": "id_canonico", "status": str(match["canonical_match_id"])},
        {"field": "fonte_primaria", "status": str(match.get("primary_source"))},
        {"field": "fontes_vinculadas", "status": ", ".join(match_sources["source"].tolist())},
        {"field": "oficial", "status": "nao"},
    ]
    for _, row in match_sources.iterrows():
        checks.append({"field": f"{row['source']}_id_fonte", "status": str(row.get("source_source_match_id"))})

    differences = _source_differences(match_sources)
    for difference in differences:
        checks.append({"field": "divergencia_entre_fontes", "status": difference})

    goal_mismatch = _goal_count_mismatch(match, events) if events is not None else None
    if goal_mismatch:
        checks.append({"field": "divergencia_gols_x_eventos", "status": goal_mismatch})

    has_warning = bool(differences) or len(match_sources) < 2 or bool(goal_mismatch)
    return ("aviso" if has_warning else "ok"), checks


def _goal_count_mismatch(match: dict[str, Any], events: pd.DataFrame) -> str | None:
    """Confere se o numero de gols na timeline canonica bate com o placar oficial.

    Util para detectar erros pontuais de fonte (ex: minuto errado faz o mesmo gol
    escapar da deduplicacao e aparecer 2x) que nao sao capturados por
    _source_differences, que so compara o placar declarado entre fontes."""
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if pd.isna(home_score) or pd.isna(away_score) or events.empty:
        return None
    match_id = match["canonical_match_id"]
    match_events = events[events["match_id"] == match_id]
    goal_events = match_events[match_events["event_type"].isin(["gol", "gol_penalti", "gol_contra"])]
    expected_total = int(home_score) + int(away_score)
    actual_total = len(goal_events)
    if expected_total != actual_total:
        return f"placar soma {expected_total} gol(s), timeline tem {actual_total} evento(s) de gol"
    return None


def _source_differences(match_sources: pd.DataFrame) -> list[str]:
    finished_sources = match_sources[match_sources["status"] == "finalizado"].copy()
    if len(finished_sources) < 2:
        return []
    differences = []
    for field in ["home_score", "away_score"]:
        values = finished_sources[field].dropna().astype(int).unique().tolist()
        if len(values) > 1:
            differences.append(f"{field}: {values}")
    return differences


def _source_ids_for_manifest(match_sources: pd.DataFrame) -> dict[str, str]:
    return {row["source"]: str(row.get("source_source_match_id")) for _, row in match_sources.iterrows()}


_KNOCKOUT_STAGE_LABELS = {
    "r32": "r32", "r16": "r16", "qf": "qf", "sf": "sf", "third": "terceiro_lugar", "final": "final",
}


def _report_location(match: dict[str, Any]) -> tuple[str, str]:
    """Subdiretorio e nome de arquivo do relatorio final: agrupado por rodada
    na fase de grupos e por fase no mata-mata, com nome descritivo (numero + selecoes)."""
    match_id = str(match["canonical_match_id"])
    home = slugify(_display_team(match.get("home_team")))
    away = slugify(_display_team(match.get("away_team")))
    number = match_id.split("_")[-1]
    filename = f"{number}_{home}_x_{away}"

    stage = match.get("stage")
    if stage == "fase_de_grupos":
        round_number = match.get("round")
        subdir = f"fase_de_grupos/rodada_{int(round_number)}" if pd.notna(round_number) else "fase_de_grupos/rodada_desconhecida"
    elif stage in _KNOCKOUT_STAGE_LABELS:
        subdir = f"mata_mata/{_KNOCKOUT_STAGE_LABELS[stage]}"
    else:
        subdir = "outros"
    return subdir, filename


def _events_for_match(events: pd.DataFrame, match_id: str) -> list[dict[str, Any]]:
    if events.empty:
        return []
    match_events = events[events["match_id"] == match_id].copy()
    if match_events.empty:
        return []
    match_events["description"] = match_events.apply(_linked_event_description, axis=1)
    return match_events.sort_values(["minute_sort", "team"]).to_dict("records")


def _linked_event_description(event: pd.Series) -> str:
    description = event.get("description")
    event_type = event.get("event_type")
    player = event.get("player")
    team = event.get("team")
    related_player = event.get("related_player")

    if player and pd.notna(player):
        if event_type == "gol":
            description = f"Gol: {_player_link(player, team)} ({_team_link(team)})"
        elif event_type == "gol_penalti":
            description = f"Gol de penalti: {_player_link(player, team)} ({_team_link(team)})"
        elif event_type == "gol_contra":
            description = f"Gol contra: {_player_link(player, team)} ({_team_link(team)})"
        elif event_type == "cartao_amarelo":
            description = f"Cartao amarelo: {_player_link(player, team)} ({_team_link(team)})"
        elif event_type == "cartao_vermelho":
            description = f"Cartao vermelho: {_player_link(player, team)} ({_team_link(team)})"
        else:
            description = f"{description or event_type}: {_player_link(player, team)} ({_team_link(team)})"
    elif team and pd.notna(team):
        description = f"{description or event_type}: {_team_link(team)}"

    if related_player and pd.notna(related_player):
        description = f"{description}; relacionado: {_player_link(related_player, team)}"
    return str(description or event_type or "")


def _team_stats_for_match(team_stats: pd.DataFrame, match_id: str) -> pd.DataFrame:
    if team_stats.empty:
        return pd.DataFrame()
    return team_stats[team_stats["match_id"] == match_id].copy()


def _lineups_for_match(lineups: pd.DataFrame, match_id: str) -> pd.DataFrame:
    if lineups.empty:
        return pd.DataFrame()
    return lineups[lineups["match_id"] == match_id].copy()


def _player_stats_for_match(player_stats: pd.DataFrame, match_id: str) -> pd.DataFrame:
    if player_stats.empty:
        return pd.DataFrame()
    return player_stats[player_stats["match_id"] == match_id].copy()


def _match_info_for_match(match_info: pd.DataFrame, match_id: str) -> dict[str, Any]:
    if match_info.empty:
        return {}
    rows = match_info[match_info["match_id"] == match_id]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()





# (coluna, rotulo, sufixo de exibicao, multiplicador) — possession ja vem em
# escala percentual (64.6 = 64.6%) mas pass_accuracy vem fracionaria (0.9 =
# 90%) na mesma fonte; o multiplicador normaliza as duas para "%" de fato.
_TEAM_STAT_DISPLAY = [
    ("possession", "posse", "%", 1),
    ("shots", "chutes", "", 1),
    ("shots_on_target", "chutes no alvo", "", 1),
    ("passes", "passes", "", 1),
    ("pass_accuracy", "precisao de passe", "%", 100),
    ("corners", "escanteios", "", 1),
    ("fouls", "faltas", "", 1),
    ("yellow_cards", "cartoes amarelos", "", 1),
    ("red_cards", "cartoes vermelhos", "", 1),
]


def _format_match_team_stats(match: dict[str, Any], match_team_stats: pd.DataFrame) -> str:
    """Tabela frente-a-frente com as estatisticas-chave da partida, para
    'bater o olho' — poucas metricas, uma linha por metrica, time casa vs
    visitante. Estatisticas detalhadas (desarmes, cortes, etc) ficam de fora
    para manter a secao rapida de ler; quem quiser o detalhe completo encontra
    no relatorio de cada selecao."""
    home_team = _display_team(match.get("home_team"))
    away_team = _display_team(match.get("away_team"))

    rows = []
    home_score, away_score = match.get("home_score"), match.get("away_score")
    if pd.notna(home_score) and pd.notna(away_score):
        rows.append([str(int(home_score)), "gols", str(int(away_score))])

    if not match_team_stats.empty:
        stats_by_team = match_team_stats.set_index("team")
        if home_team in stats_by_team.index and away_team in stats_by_team.index:
            home_row = stats_by_team.loc[home_team]
            away_row = stats_by_team.loc[away_team]
            for column, label, suffix, multiplier in _TEAM_STAT_DISPLAY:
                if column not in home_row.index:
                    continue
                home_value = home_row.get(column)
                away_value = away_row.get(column)
                if pd.isna(home_value) and pd.isna(away_value):
                    continue
                rows.append([
                    _format_stat_value(home_value, suffix, multiplier),
                    label,
                    _format_stat_value(away_value, suffix, multiplier),
                ])

    if not rows:
        return ""
    table = pd.DataFrame(rows, columns=[_team_link(home_team), "estatistica", _team_link(away_team)])
    return table.to_markdown(index=False)


def _format_stat_value(value: Any, suffix: str, multiplier: float = 1) -> str:
    if pd.isna(value):
        return ""
    numeric = float(value) * multiplier
    text = f"{numeric:g}"
    return f"{text}{suffix}"


def _format_lineups(lineups: pd.DataFrame, player_stats: pd.DataFrame | None = None) -> str:
    """Escalacao titular por time: camisa, jogador, posicao. Sem estatisticas —
    isso fica nos relatorios de time/jogador; aqui o foco e quem comecou o jogo."""
    if lineups.empty:
        return ""
    starters = lineups.copy()
    if "is_starter" in starters.columns:
        starters = starters[starters["is_starter"].fillna(False)].copy()

    # Ordena por posição tática (goleiro -> defesa -> meio -> ataque), não pela
    # ordem bruta da fonte — formation_slot segue a numeração interna da ESPN
    # e nao corresponde a posicao em campo.
    if "position" in starters.columns:
        starters["_position_order"] = starters["position"].apply(position_order)
    sort_columns = [column for column in ["_position_order", "shirt_number", "player_name"] if column in starters.columns]
    columns = ["shirt_number", "player_name", "position"]
    available = [column for column in columns if column in starters.columns]
    labels = {"shirt_number": "camisa", "player_name": "jogador", "position": "posicao"}

    parts = []
    for team, team_lineup in starters.groupby("team", sort=False):
        parts.append(f"### {_team_link(team)}")
        formation = _first_valid(team_lineup.get("formation"))
        if formation:
            parts.append("")
            parts.append(f"Formacao: `{formation}`")
        parts.append("")
        if sort_columns:
            team_lineup = team_lineup.sort_values(sort_columns, na_position="last")
        team_lineup = team_lineup.copy()
        if "player_name" in team_lineup.columns:
            team_lineup["player_name"] = team_lineup["player_name"].apply(lambda player: _player_link(player, team))
        if "position" in team_lineup.columns:
            team_lineup["position"] = team_lineup["position"].apply(position_label)
        table = _normalize_markdown_table_values(team_lineup[available])
        parts.append(table.rename(columns=labels).fillna("").to_markdown(index=False))
        parts.append("")
    return "\n".join(parts).strip()


def _build_match_story(
    match: dict[str, Any],
    team_stats: pd.DataFrame,
    events: list[dict[str, Any]],
    player_stats: pd.DataFrame,
) -> str:
    """Narrativa do jogo: abertura em prosa, lances decisivos em bullets
    cronologicos com placar parcial, e fechamento em prosa. Os bullets
    incorporam o que antes era a timeline separada — cada um traz minuto,
    quem fez, e o efeito no placar, nao so o nome cru do evento."""
    home_team = _display_team(match.get("home_team"))
    away_team = _display_team(match.get("away_team"))
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if pd.isna(home_score) or pd.isna(away_score):
        return ""
    home_score, away_score = int(home_score), int(away_score)

    goals = [e for e in events if e.get("event_type") in ("gol", "gol_penalti", "gol_contra")]
    red_cards = [e for e in events if e.get("event_type") == "cartao_vermelho"]

    # --- Abertura: domínio de posse, se houve, mais o tom geral do confronto ---
    dominance = ""
    if not team_stats.empty and len(team_stats) >= 2:
        teams = team_stats.set_index("team")
        if home_team in teams.index and away_team in teams.index:
            home_poss = teams.loc[home_team].get("possession")
            away_poss = teams.loc[away_team].get("possession")
            if pd.notna(home_poss) and pd.notna(away_poss) and abs(home_poss - away_poss) >= 10:
                dominant_team = home_team if home_poss > away_poss else away_team
                leader_poss = max(home_poss, away_poss)
                dominance = f"{_team_link(dominant_team)} controlou o ritmo da partida, com {leader_poss:g}% de posse de bola. "

    if not goals:
        if dominance:
            opening = f"{dominance}Apesar da superioridade, o jogo ficou travado e terminou sem gols, em {home_score} x {away_score}."
        else:
            opening = f"Partida disputada e sem favoritismo claro, que terminou em {home_score} x {away_score} sem que nenhuma das equipes balancasse as redes."
        return opening

    first = goals[0]
    first_minute = first.get("minute", "")
    first_scorer = first.get("player")
    first_team = first.get("team")
    early = int(str(first_minute).split("+")[0]) <= 15
    opener_phrase = "saiu na frente logo aos" if early else "abriu o placar aos"
    scorer_part = f" com gol de {_player_link(first_scorer, first_team)}" if first_scorer and pd.notna(first_scorer) else ""
    dominant_scored_first = dominance and _team_link(first_team) in dominance
    if dominant_scored_first:
        opening = f"{dominance}E foi justamente quem mandava no jogo que {opener_phrase} {first_minute}'{scorer_part}."
    elif dominance:
        opening = f"{dominance}Mas quem abriu o placar foi {_team_link(first_team)}, {opener_phrase.replace('saiu na frente logo aos', 'logo aos').replace('abriu o placar aos', 'aos')} {first_minute}'{scorer_part}."
    else:
        opening = f"{_team_link(first_team)} {opener_phrase} {first_minute}'{scorer_part}."

    # --- Desenvolvimento: cada lance decisivo vira um bullet cronologico com
    # placar parcial, entrelacando gols e cartoes vermelhos na ordem real ---
    bullets: list[str] = []
    score_balance: dict[str, int] = {home_team: 0, away_team: 0}
    score_balance[first_team] = 1
    bullets.append(
        f"**{first_minute}'** — {_player_link(first_scorer, first_team)} {'abre' if not early else 'inaugura'} o placar para "
        f"{_team_link(first_team)} ({_partial_score(home_team, away_team, score_balance)})."
        if first_scorer and pd.notna(first_scorer)
        else f"**{first_minute}'** — {_team_link(first_team)} abre o placar ({_partial_score(home_team, away_team, score_balance)})."
    )

    remaining_goals = goals[1:]
    tagged_events = [("gol", g) for g in remaining_goals] + [("cartao", c) for c in red_cards]
    tagged_events.sort(key=lambda item: item[1].get("minute_sort", 0))

    for kind, event in tagged_events:
        minute = event.get("minute", "")
        team = event.get("team")
        player = event.get("player")
        if kind == "cartao":
            if player and pd.notna(player):
                bullets.append(f"**{minute}'** — {_player_link(player, team)} e expulso, e {_team_link(team)} passa a jogar com um a menos.")
            continue
        opponent = away_team if team == home_team else home_team
        scorer_link = _player_link(player, team) if player and pd.notna(player) else _team_link(team)
        was_behind_or_tied = score_balance.get(team, 0) <= score_balance.get(opponent, 0)
        score_balance[team] = score_balance.get(team, 0) + 1
        partial = _partial_score(home_team, away_team, score_balance)
        if score_balance[team] == score_balance[opponent]:
            bullets.append(f"**{minute}'** — {scorer_link} deixa tudo igual para {_team_link(team)} ({partial}).")
        elif was_behind_or_tied:
            bullets.append(f"**{minute}'** — virada! {scorer_link} coloca {_team_link(team)} na frente ({partial}).")
        else:
            bullets.append(f"**{minute}'** — {scorer_link} amplia o placar para {_team_link(team)} ({partial}).")

    # --- Fechamento: leitura do resultado final ---
    diff = abs(home_score - away_score)
    winner = home_team if home_score > away_score else (away_team if away_score > home_score else None)
    if winner and diff >= 4:
        loser = away_team if winner == home_team else home_team
        closing = f"No apagar das luzes, {winner} confirmou a goleada sobre {loser}: {home_score} x {away_score}."
    elif winner:
        loser = away_team if winner == home_team else home_team
        closing = f"No fim, {winner} levou a melhor sobre {loser} por {home_score} x {away_score}."
    else:
        closing = f"A partida terminou empatada em {home_score} x {away_score}."

    if not player_stats.empty and "goals" in player_stats.columns:
        top_scorer = player_stats.loc[player_stats["goals"].fillna(0).idxmax()]
        if top_scorer.get("goals", 0) >= 2:
            n = int(top_scorer["goals"])
            closing += f" {_player_link(top_scorer['player_name'], top_scorer['team'])} foi o nome da partida, com {n} gols marcados."

    bullet_list = "\n".join(f"- {b}" for b in bullets)
    return f"{opening}\n\n{bullet_list}\n\n{closing}"


def _partial_score(home_team: str, away_team: str, score_balance: dict[str, int]) -> str:
    return f"{score_balance.get(home_team, 0)} x {score_balance.get(away_team, 0)}"


def _first_valid(values: Any) -> Any:
    if values is None:
        return None
    if isinstance(values, pd.Series):
        for value in values:
            if pd.notna(value) and value != "":
                return value
        return None
    return values if pd.notna(values) and values != "" else None


def _normalize_markdown_table_values(table: pd.DataFrame) -> pd.DataFrame:
    normalized = table.copy()
    for column in normalized.columns:
        if column == "player_name":
            normalized[column] = normalized[column].fillna("")
            continue
        numeric_values = pd.to_numeric(normalized[column], errors="coerce")
        if numeric_values.notna().any():
            numeric_values = numeric_values.fillna(0)
            if bool((numeric_values % 1).eq(0).all()):
                normalized[column] = numeric_values.astype(int)
            else:
                normalized[column] = numeric_values.round(2)
        else:
            normalized[column] = normalized[column].fillna("")
    return normalized


def _obsidian_link(target: str, label: Any) -> str:
    return f"[[{target}\\|{label}]]"


def _team_link(team: Any) -> str:
    if pd.isna(team) or not team:
        return "A definir"
    team_name = str(team)
    return _obsidian_link(f"reports/teams/{slugify(team_name)}", team_name)


def _player_link(player_name: Any, team: Any) -> str:
    if pd.isna(player_name) or not player_name:
        return ""
    player = str(player_name)
    return _obsidian_link(f"reports/players/{slugify(team)}/{slugify(player)}", player)


def _display_team(value: Any) -> str:
    if pd.isna(value) or not value:
        return "A definir"
    return str(value)
