from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

from fifa_analytics.analytics.scores import build_player_match_features, build_team_match_features, build_team_scores
from fifa_analytics.utils.text import slugify
from fifa_analytics.paths import GOLD_DIR, SILVER_DIR
from fifa_analytics.reporting.build_report import build_match_report
from fifa_analytics.reporting.fragments import render_template, write_fragment
from fifa_analytics.reporting.tournament_reports import format_standings_table
from fifa_analytics.utils.io import ensure_dir, read_dataframe, read_json, write_dataframe, write_json
from fifa_analytics.utils.time import utc_now_iso


SOURCE_PRIORITY = ["worldcup2026", "espn", "wikipedia"]
EVENT_SOURCE_PRIORITY = ["espn", "worldcup2026", "wikipedia"]
SOURCE_DESCRIPTIONS = {
    "worldcup2026": "API publica worldcup26.ir",
    "espn": "ESPN",
    "wikipedia": "Wikipedia",
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
    shots_path = GOLD_DIR / "fact_shots" / "canonical_shots.parquet"
    shots = read_dataframe(shots_path) if shots_path.exists() else pd.DataFrame()
    standings = _load_best_standings()
    selected_matches = _filter_matches(matches, status)

    # Pré-computa scores de todos os times no contexto do torneio inteiro.
    # Necessário para que a comparação da partida use z-score entre os 32 times,
    # não entre os 2 times desta partida (o que produziria notas artificialmente simétricas).
    all_team_features = build_team_match_features(matches, team_stats if not team_stats.empty else None)
    all_team_scores = build_team_scores(all_team_features) if not all_team_features.empty else pd.DataFrame()

    report_results = []
    for _, match in selected_matches.iterrows():
        match_dict = match.to_dict()
        match_sources = source_map[source_map["canonical_match_id"] == match_dict["canonical_match_id"]].copy()
        data_quality_status, checks = _data_quality_checks(match_dict, match_sources)
        write_canonical_fragments(
            match_dict,
            standings,
            events,
            team_stats,
            match_info,
            lineups,
            player_stats,
            shots,
            match_sources,
            data_quality_status,
            checks,
            all_team_scores=all_team_scores,
        )
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
    events = (
        events.sort_values(["match_id", "minute_sort", "source_priority"])
        .drop_duplicates(subset=["match_id", "minute", "team", "event_type"])
        .drop(columns=["source_priority"])
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
    standings: pd.DataFrame,
    events: pd.DataFrame,
    team_stats: pd.DataFrame,
    match_info: pd.DataFrame,
    lineups: pd.DataFrame,
    player_stats: pd.DataFrame,
    shots: pd.DataFrame,
    match_sources: pd.DataFrame,
    data_quality_status: str,
    checks: list[dict[str, str]],
    all_team_scores: pd.DataFrame | None = None,
) -> None:
    match_id = match["canonical_match_id"]
    home_team = _display_team(match.get("home_team"))
    away_team = _display_team(match.get("away_team"))
    scoreline = None
    if pd.notna(match.get("home_score")) and pd.notna(match.get("away_score")):
        scoreline = f"{int(match['home_score'])} x {int(match['away_score'])}"

    info = _match_info_for_match(match_info, match_id)
    extra_context = _match_info_context(info)
    write_fragment(
        match_id,
        "00_metadata",
        render_template(
            "fragments/00_metadata.md.j2",
            {
                "match_id": match_id,
                "generated_at": utc_now_iso(),
                "status": match.get("status", "desconhecido"),
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
                "date": match.get("date"),
                "stadium": match.get("stadium"),
                "city": match.get("city"),
                "country": match.get("country"),
            },
        ),
    )
    write_fragment(
        match_id,
        "02_context",
        render_template(
            "fragments/02_context.md.j2",
            {
                "context": (
                    f"{_match_number_context(match)} do Grupo {match.get('group')} na fase de grupos. "
                    f"Fonte primaria: {match.get('primary_source')}. "
                    f"Fontes vinculadas: {_source_summary(match_sources)}."
                    f"{extra_context}"
                )
            },
        ),
    )

    match_team_stats = _team_stats_for_match(team_stats, match_id)
    group_standings = standings[standings["group"] == match.get("group")] if not standings.empty else pd.DataFrame()
    team_score_comparison = _format_team_score_comparison(match, match_team_stats, all_team_scores)
    write_fragment(
        match_id,
        "05_team_stats",
        render_template(
            "fragments/05_team_stats.md.j2",
            {"team_stats": _format_match_team_stats(match_team_stats, group_standings, team_score_comparison)},
        ),
    )
    write_fragment(
        match_id,
        "04_timeline",
        render_template("fragments/04_timeline.md.j2", {"events": _events_for_match(events, match_id)}),
    )
    match_lineups = _lineups_for_match(lineups, match_id)
    match_player_stats = _player_stats_for_match(player_stats, match_id)
    write_fragment(
        match_id,
        "03_lineups",
        render_template("fragments/03_lineups.md.j2", {"lineups": _format_lineups(match_lineups, match_player_stats)}),
    )
    write_fragment(
        match_id,
        "06_player_stats",
        render_template("fragments/06_player_stats.md.j2", {"player_stats": _format_player_stats(match_player_stats)}),
    )
    match_shots = _shots_for_match(shots, match_id)
    write_fragment(
        match_id,
        "07_key_insights",
        render_template(
            "fragments/07_key_insights.md.j2",
            {"insights": _build_key_insights(match, match_team_stats, match_player_stats, match_shots)},
        ),
    )
    write_fragment(
        match_id,
        "08_data_quality",
        render_template(
            "fragments/08_data_quality.md.j2",
            {
                "data_quality_status": data_quality_status,
                "checks": checks,
            },
        ),
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


def _match_number_context(match: dict[str, Any]) -> str:
    match_number = match.get("match_number")
    temporal_order = match.get("temporal_order")
    if pd.notna(match_number) and pd.notna(temporal_order):
        return f"Partida {int(match_number)} na numeracao da fonte primaria; ordem temporal {int(temporal_order)}"
    if pd.notna(match_number):
        return f"Partida {int(match_number)} na numeracao da fonte primaria"
    if pd.notna(temporal_order):
        return f"Partida de ordem temporal {int(temporal_order)}"
    return f"Partida {match.get('canonical_match_id') or match.get('match_id')}"


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


def _load_best_standings() -> pd.DataFrame:
    for path in [
        GOLD_DIR / "standings" / "worldcup2026_calculated_group_standings.parquet",
        GOLD_DIR / "standings" / "wikipedia_calculated_group_standings.parquet",
    ]:
        if path.exists():
            return read_dataframe(path)
    return pd.DataFrame()


def _filter_matches(matches: pd.DataFrame, status: str) -> pd.DataFrame:
    if status == "todos":
        return matches
    return matches[matches["status"] == status].copy()


def _data_quality_checks(match: dict[str, Any], match_sources: pd.DataFrame) -> tuple[str, list[dict[str, str]]]:
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

    return ("aviso" if differences or len(match_sources) < 2 else "ok"), checks


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


def _source_summary(match_sources: pd.DataFrame) -> str:
    parts = []
    for _, source in match_sources.iterrows():
        description = SOURCE_DESCRIPTIONS.get(source["source"], source["source"])
        parts.append(f"{description} ({source.get('source_source_match_id')})")
    return ", ".join(parts)


def _source_ids_for_manifest(match_sources: pd.DataFrame) -> dict[str, str]:
    return {row["source"]: str(row.get("source_source_match_id")) for _, row in match_sources.iterrows()}


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


def _shots_for_match(shots: pd.DataFrame, match_id: str) -> pd.DataFrame:
    if shots.empty:
        return pd.DataFrame()
    return shots[shots["match_id"] == match_id].copy()


def _match_info_for_match(match_info: pd.DataFrame, match_id: str) -> dict[str, Any]:
    if match_info.empty:
        return {}
    rows = match_info[match_info["match_id"] == match_id]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _match_info_context(info: dict[str, Any]) -> str:
    if not info:
        return ""
    parts = []
    if pd.notna(info.get("attendance")):
        parts.append(f"publico informado: {int(info['attendance'])}")
    if info.get("referee") and pd.notna(info.get("referee")):
        parts.append(f"arbitro: {info['referee']}")
    if info.get("broadcasts") and pd.notna(info.get("broadcasts")):
        parts.append(f"transmissao: {info['broadcasts']}")
    if not parts:
        return ""
    return " " + "; ".join(parts) + "."


def _format_match_team_stats(match_team_stats: pd.DataFrame, group_standings: pd.DataFrame, score_comparison: str = "") -> str:
    parts = []
    if score_comparison:
        parts.append("### Comparativo de notas da partida")
        parts.append("")
        parts.append(score_comparison)
        parts.append("")

    if not match_team_stats.empty:
        display_columns = [
            "team",
            "possession",
            "shots",
            "shots_on_target",
            "blocked_shots",
            "passes",
            "pass_accuracy",
            "corners",
            "fouls",
            "offsides",
            "saves",
            "yellow_cards",
            "red_cards",
            "tackles",
            "interceptions",
        ]
        available_columns = [column for column in display_columns if column in match_team_stats.columns]
        labels = {
            "team": "selecao",
            "possession": "posse",
            "shots": "chutes",
            "shots_on_target": "chutes_no_alvo",
            "blocked_shots": "chutes_bloqueados",
            "passes": "passes",
            "pass_accuracy": "precisao_passes",
            "corners": "escanteios",
            "fouls": "faltas",
            "offsides": "impedimentos",
            "saves": "defesas",
            "yellow_cards": "amarelos",
            "red_cards": "vermelhos",
            "tackles": "desarmes",
            "interceptions": "interceptacoes",
        }
        display = match_team_stats[available_columns].copy()
        if "team" in display.columns:
            display["team"] = display["team"].apply(_team_link)
        for percentage_column in ["pass_accuracy"]:
            if percentage_column in display.columns:
                display[percentage_column] = display[percentage_column].apply(
                    lambda value: round(value * 100, 1) if pd.notna(value) and value <= 1 else value
                )
        parts.append("### Estatisticas da partida")
        parts.append("")
        parts.append(display.rename(columns=labels).to_markdown(index=False))
        parts.append("")

    if not group_standings.empty:
        parts.append("### Classificacao do grupo")
        parts.append("")
        standings_display = group_standings.copy()
        if "team" in standings_display.columns:
            standings_display["team"] = standings_display["team"].apply(_team_link)
        parts.append(format_standings_table(standings_display))

    return "\n".join(parts).strip()


def _format_team_score_comparison(
    match: dict[str, Any],
    match_team_stats: pd.DataFrame,
    all_team_scores: pd.DataFrame | None = None,
) -> str:
    if match_team_stats.empty:
        return ""

    # Usa scores pré-computados no contexto do torneio inteiro (z-score entre 32 times).
    # Sem isso, comparar 2 times entre si produziria notas artificialmente simétricas (33/67).
    match_features = build_team_match_features(pd.DataFrame([match]), match_team_stats)
    if match_features.empty:
        return ""

    if all_team_scores is not None and not all_team_scores.empty:
        home_team = match.get("home_team")
        away_team = match.get("away_team")
        # Scores do torneio (notas no contexto dos 32 times)
        tournament_scores = all_team_scores[all_team_scores["team"].isin([home_team, away_team])].copy()
        # Stats desta partida (pontos, gols, chutes, posse — valores do jogo, não acumulados)
        match_scores = build_team_scores(match_features)
        match_game_cols = ["team", "points", "gols_pro", "gols_contra", "chutes_no_alvo", "posse_media"]
        match_game = match_scores[[c for c in match_game_cols if c in match_scores.columns]].copy()
        # Merge: notas do torneio + stats desta partida
        score_cols = [c for c in tournament_scores.columns if c.startswith("score_")]
        team_scores = match_game.merge(tournament_scores[["team"] + score_cols], on="team", how="left")
    else:
        team_scores = build_team_scores(match_features)

    if team_scores.empty:
        return ""

    summary_columns = [
        "team",
        "score_geral",
        "score_resultado",
        "score_ataque",
        "score_defesa",
        "score_eficiencia",
        "score_controle",
        "points",
        "gols_pro",
        "gols_contra",
        "chutes_no_alvo",
        "posse_media",
    ]
    available = [column for column in summary_columns if column in team_scores.columns]
    summary = team_scores[available].copy()
    summary["team"] = summary["team"].apply(_team_link)
    summary = summary.rename(
        columns={
            "team": "selecao",
            "score_geral": "nota_jogo",
            "score_resultado": "resultado",
            "score_ataque": "ataque",
            "score_defesa": "defesa",
            "score_eficiencia": "eficiencia",
            "score_controle": "controle",
            "points": "pontos",
            "gols_pro": "gols",
            "gols_contra": "gols_contra",
            "chutes_no_alvo": "no_alvo",
            "posse_media": "posse",
        }
    )

    parts = [
        "Nota de 0-100 no contexto do torneio (z-score entre as 32 selecoes). Pontos, gols e chutes referentes a esta partida.",
        "",
        "#### Resumo por selecao",
        "",
        _normalize_markdown_table_values(summary).to_markdown(index=False),
    ]

    ordered = _order_match_teams(team_scores, match)
    if len(ordered) >= 2:
        home = ordered.iloc[0]
        away = ordered.iloc[1]
        rows = []
        for column, label in [
            ("score_geral", "nota_jogo"),
            ("score_resultado", "resultado"),
            ("score_ataque", "ataque"),
            ("score_defesa", "defesa"),
            ("score_eficiencia", "eficiencia"),
            ("score_controle", "controle"),
            ("points", "pontos"),
            ("chutes_no_alvo", "chutes_no_alvo"),
            ("posse_media", "posse"),
        ]:
            if column not in ordered.columns:
                continue
            rows.append(
                {
                    "metrica": label,
                    str(home["team"]): _format_numeric(home.get(column)),
                    str(away["team"]): _format_numeric(away.get(column)),
                    "vantagem": _comparison_leader(home, away, column),
                }
            )
        parts.extend(["", "#### Frente a frente", "", pd.DataFrame(rows).to_markdown(index=False)])

    return "\n".join(parts).strip()


def _format_lineups(lineups: pd.DataFrame, player_stats: pd.DataFrame | None = None) -> str:
    if lineups.empty:
        return ""
    lineup_players = lineups.copy()
    player_notes = _player_match_notes(player_stats)
    if not player_notes.empty:
        lineup_players = lineup_players.merge(player_notes, on=["match_id", "team", "player_name"], how="left")
    if "is_starter" in lineup_players.columns:
        impact_columns = [
            column
            for column in ["contribuicao_partida", "goals", "assists", "shots_on_target", "saves", "yellow_cards", "red_cards"]
            if column in lineup_players.columns
        ]
        if impact_columns:
            impact_mask = lineup_players[impact_columns].apply(pd.to_numeric, errors="coerce").fillna(0).gt(0).any(axis=1)
            lineup_players = lineup_players[lineup_players["is_starter"].fillna(False) | impact_mask].copy()

    sort_columns = [column for column in ["is_starter", "formation_slot", "shirt_number", "player_name"] if column in lineup_players.columns]
    columns = [
        "shirt_number",
        "player_name",
        "position",
        "is_starter",
        "nota_jogo",
        "contribuicao_partida",
        "goals",
        "assists",
        "shots_on_target",
        "saves",
        "yellow_cards",
        "red_cards",
    ]
    available = [column for column in columns if column in lineup_players.columns]
    labels = {
        "shirt_number": "camisa",
        "player_name": "jogador",
        "position": "posicao",
        "is_starter": "titular",
        "nota_jogo": "nota_jogo",
        "contribuicao_partida": "contrib",
        "goals": "gols",
        "assists": "assist",
        "shots_on_target": "no_alvo",
        "saves": "defesas",
        "yellow_cards": "amarelos",
        "red_cards": "vermelhos",
    }
    parts = ["Nota do jogador em escala 0-100, relativa ao maior contribuidor individual registrado nesta partida.", ""]
    sort_ascending = [True] + ([False] + [True] * (len(sort_columns) - 1) if sort_columns else [])
    sorted_lineups = lineup_players.sort_values(["team", *sort_columns], ascending=sort_ascending, na_position="last")
    for team, team_lineup in sorted_lineups.groupby("team", sort=False):
        parts.append(f"### {_team_link(team)}")
        formation = _first_valid(team_lineup.get("formation"))
        if formation:
            parts.append("")
            parts.append(f"Formacao: `{formation}`")
        parts.append("")
        if sort_columns:
            team_lineup = team_lineup.sort_values(sort_columns, ascending=[False, *([True] * (len(sort_columns) - 1))], na_position="last")
        team_lineup = team_lineup.copy()
        if "player_name" in team_lineup.columns:
            team_lineup["player_name"] = team_lineup["player_name"].apply(lambda player: _player_link(player, team))
        if "is_starter" in team_lineup.columns:
            team_lineup["is_starter"] = team_lineup["is_starter"].apply(lambda value: "sim" if bool(value) else "nao")
        table = _normalize_markdown_table_values(team_lineup[available])
        parts.append(table.rename(columns=labels).fillna("").to_markdown(index=False))
        parts.append("")
    return "\n".join(parts).strip()


def _player_match_notes(player_stats: pd.DataFrame | None) -> pd.DataFrame:
    if player_stats is None or player_stats.empty:
        return pd.DataFrame()
    features = build_player_match_features(player_stats)
    if features.empty:
        return pd.DataFrame()

    # Contribuição bruta por partida: soma ponderada de eventos observáveis
    contrib = (
        features.get("goals", 0) * 5
        + features.get("assists", 0) * 3
        + features.get("shots_on_target", 0) * 1.5
        + features.get("saves", 0) * 1.2
        + features.get("tackles", 0) * 0.4
        + features.get("interceptions", 0) * 0.4
        - features.get("yellow_cards", 0) * 0.5
        - features.get("red_cards", 0) * 2
    ).clip(lower=0)
    features["contribuicao_partida"] = contrib
    max_contrib = float(contrib.max())
    features["nota_jogo"] = (0.0 if max_contrib <= 0 else (contrib / max_contrib * 100)).round(1)

    columns = [
        "match_id", "team", "player_name", "nota_jogo", "contribuicao_partida",
        "goals", "assists", "shots_on_target", "saves", "yellow_cards", "red_cards",
    ]
    available = [c for c in columns if c in features.columns]
    notes = features[available].copy()
    for col in ["nota_jogo", "contribuicao_partida"]:
        if col in notes.columns:
            notes[col] = notes[col].round(1)
    return notes


def _order_match_teams(team_scores: pd.DataFrame, match: dict[str, Any]) -> pd.DataFrame:
    order = {match.get("home_team"): 0, match.get("away_team"): 1}
    ordered = team_scores.copy()
    ordered["_match_order"] = ordered["team"].map(order).fillna(99)
    return ordered.sort_values(["_match_order", "team"]).drop(columns=["_match_order"]).reset_index(drop=True)


def _comparison_leader(home: pd.Series, away: pd.Series, column: str) -> str:
    home_value = pd.to_numeric(pd.Series([home.get(column)]), errors="coerce").iloc[0]
    away_value = pd.to_numeric(pd.Series([away.get(column)]), errors="coerce").iloc[0]
    if pd.isna(home_value) or pd.isna(away_value):
        return ""
    if home_value == away_value:
        return "empate"
    return _team_link(home["team"] if home_value > away_value else away["team"])


def _format_numeric(value: Any) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return ""
    if float(numeric).is_integer():
        return str(int(numeric))
    return f"{float(numeric):.1f}"


def _format_player_stats(player_stats: pd.DataFrame) -> str:
    if player_stats.empty:
        return ""
    stats = build_player_match_features(player_stats)
    for column in ["goals", "assists", "shots", "shots_on_target", "saves", "tackles", "interceptions", "yellow_cards", "red_cards"]:
        if column not in stats.columns:
            stats[column] = 0
    contrib = (
        stats.get("goals", 0) * 5 + stats.get("assists", 0) * 3
        + stats.get("shots_on_target", 0) * 1.5 + stats.get("saves", 0) * 1.2
        + stats.get("tackles", 0) * 0.4 + stats.get("interceptions", 0) * 0.4
        - stats.get("yellow_cards", 0) * 0.5 - stats.get("red_cards", 0) * 2
    ).clip(lower=0)
    stats["impact_score"] = contrib
    max_impact = float(contrib.max())
    stats["nota_jogo"] = (0.0 if max_impact <= 0 else (contrib / max_impact * 100)).round(1)
    if "minutes_played" not in stats.columns:
        stats["minutes_played"] = 0
    columns = [
        "player_name",
        "nota_jogo",
        "impact_score",
        "minutes_played",
        "goals",
        "assists",
        "shots",
        "shots_on_target",
        "saves",
        "tackles",
        "interceptions",
        "yellow_cards",
        "red_cards",
    ]
    available = [column for column in columns if column in stats.columns]
    labels = {
        "team": "selecao",
        "player_name": "jogador",
        "nota_jogo": "nota_jogo",
        "impact_score": "impacto",
        "minutes_played": "min",
        "goals": "gols",
        "assists": "assist",
        "shots": "chutes",
        "shots_on_target": "no_alvo",
        "saves": "defesas",
        "tackles": "desarmes",
        "interceptions": "intercept",
        "yellow_cards": "amarelos",
        "red_cards": "vermelhos",
    }
    parts = []
    sort_columns = ["impact_score", "minutes_played", "player_name"]
    for team, team_stats in stats.sort_values(["team", *sort_columns], ascending=[True, False, False, True]).groupby("team", sort=False):
        display = team_stats[team_stats["impact_score"] > 0].sort_values(sort_columns, ascending=[False, False, True]).head(8)
        if display.empty:
            continue
        team_available = [column for column in available if column == "player_name" or _has_meaningful_values(display[column])]
        table = _normalize_markdown_table_values(display[team_available])
        if "player_name" in table.columns:
            table["player_name"] = table["player_name"].apply(lambda player: _player_link(player, team))
        parts.append(f"### {_team_link(team)}")
        parts.append("")
        parts.append(table.rename(columns=labels).to_markdown(index=False))
        parts.append("")
    return "\n".join(parts).strip()


def _build_key_insights(match: dict[str, Any], team_stats: pd.DataFrame, player_stats: pd.DataFrame, shots: pd.DataFrame) -> str:
    sections: list[tuple[str, list[str]]] = []
    if not team_stats.empty and len(team_stats) >= 2:
        teams = team_stats.set_index("team")
        home_team = match.get("home_team")
        away_team = match.get("away_team")
        if home_team in teams.index and away_team in teams.index:
            home = teams.loc[home_team]
            away = teams.loc[away_team]
            sections.append(("Comparacao das selecoes", _team_stat_insights(home_team, away_team, home, away)))

    if not shots.empty:
        shot_insights = []
        shot_counts = shots.groupby("team").size().sort_values(ascending=False)
        on_target = shots[shots["outcome"].isin(["gol", "no_alvo"])].groupby("team").size()
        if len(shot_counts) >= 2:
            leader = shot_counts.index[0]
            shot_insights.append(f"{leader} liderou o volume de finalizacoes com {int(shot_counts.iloc[0])} chutes registrados no lance a lance.")
        for team, total in shot_counts.items():
            target = int(on_target.get(team, 0))
            shot_insights.append(f"{team} colocou {target} de {int(total)} finalizacoes no alvo ou no gol.")
        sections.append(("Finalizacoes", shot_insights))

    if not player_stats.empty:
        player_insights = []
        top = player_stats.copy()
        for column in ["goals", "assists", "shots", "shots_on_target", "saves"]:
            if column not in top.columns:
                top[column] = 0
        top["impact_score"] = top["goals"].fillna(0) * 5 + top["assists"].fillna(0) * 3 + top["shots_on_target"].fillna(0) * 1.5 + top["saves"].fillna(0)
        top = top.sort_values("impact_score", ascending=False)
        if not top.empty and top.iloc[0]["impact_score"] > 0:
            row = top.iloc[0]
            player_insights.append(
                f"Destaque estatistico: {_player_link(row['player_name'], row['team'])} ({_team_link(row['team'])}) "
                "combinou gols/assistencias/chutes no alvo/defesas com maior impacto simples."
            )
        sections.append(("Destaques individuais", player_insights))

    rendered = []
    for title, insights in sections:
        if not insights:
            continue
        rendered.append(f"### {title}")
        rendered.append("")
        rendered.extend(f"- {insight}" for insight in insights)
        rendered.append("")
    return "\n".join(rendered).strip() or "Dados enriquecidos disponiveis, mas ainda sem insight automatico relevante para esta partida."


def _team_stat_insights(home_team: str, away_team: str, home: pd.Series, away: pd.Series) -> list[str]:
    insights = []
    comparisons = [
        ("possession", "posse"),
        ("shots", "chutes"),
        ("shots_on_target", "chutes no alvo"),
        ("passes", "passes"),
        ("fouls", "faltas"),
    ]
    for column, label in comparisons:
        if column not in home.index or pd.isna(home.get(column)) or pd.isna(away.get(column)):
            continue
        home_value = home.get(column)
        away_value = away.get(column)
        if home_value == away_value:
            continue
        leader = home_team if home_value > away_value else away_team
        leader_value = home_value if home_value > away_value else away_value
        other_value = away_value if home_value > away_value else home_value
        verb = "cometeu mais" if column == "fouls" else "liderou em"
        insights.append(f"{leader} {verb} {label}: {leader_value:g} contra {other_value:g}.")
    return insights


def _first_valid(values: Any) -> Any:
    if values is None:
        return None
    if isinstance(values, pd.Series):
        for value in values:
            if pd.notna(value) and value != "":
                return value
        return None
    return values if pd.notna(values) and values != "" else None


def _has_meaningful_values(values: pd.Series) -> bool:
    if values.empty:
        return False
    numeric_values = pd.to_numeric(values, errors="coerce")
    if numeric_values.notna().any():
        return bool(numeric_values.fillna(0).ne(0).any())
    return bool(values.fillna("").astype(str).str.strip().ne("").any())


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
    return _obsidian_link(f"reports/players/{slugify(f'{player}_{team}')}", player)


def _display_team(value: Any) -> str:
    if pd.isna(value) or not value:
        return "A definir"
    return str(value)
