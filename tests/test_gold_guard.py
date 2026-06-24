from fifa_analytics.utils.gold_guard import (
    KNOWN_GOLD_PARQUETS,
    find_unknown_gold,
    prune_unknown_gold,
)


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PAR1")


def test_finds_and_prunes_only_unknown_parquets(tmp_path):
    # canônicos
    _touch(tmp_path / "dim_match.parquet")
    _touch(tmp_path / "analytics/snapshot_timeline.parquet")
    # legados / stale
    _touch(tmp_path / "dim_match/canonical_matches.parquet")
    _touch(tmp_path / "analytics/snapshots/snapshot_timeline.parquet")

    unknown = find_unknown_gold(tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in unknown}
    assert rel == {
        "dim_match/canonical_matches.parquet",
        "analytics/snapshots/snapshot_timeline.parquet",
    }

    prune_unknown_gold(tmp_path, remove=True)
    assert (tmp_path / "dim_match.parquet").exists()
    assert (tmp_path / "analytics/snapshot_timeline.parquet").exists()
    assert not (tmp_path / "dim_match/canonical_matches.parquet").exists()
    assert not (tmp_path / "analytics/snapshots/snapshot_timeline.parquet").exists()
    # diretório que ficou vazio é removido
    assert not (tmp_path / "dim_match").exists()


def test_warn_only_mode_keeps_files(tmp_path):
    _touch(tmp_path / "lixo/canonical_x.parquet")
    found = prune_unknown_gold(tmp_path, remove=False)
    assert len(found) == 1
    assert (tmp_path / "lixo/canonical_x.parquet").exists()


def test_does_not_touch_non_parquet(tmp_path):
    _touch(tmp_path / "analytics/weights.json")
    prune_unknown_gold(tmp_path, remove=True)
    assert (tmp_path / "analytics/weights.json").exists()


def test_known_set_covers_player_artifacts():
    assert "analytics/snapshots/player_snapshot_timeline.parquet" in KNOWN_GOLD_PARQUETS
    assert "analytics/player_match_wide.parquet" in KNOWN_GOLD_PARQUETS
