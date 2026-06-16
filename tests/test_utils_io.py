import pandas as pd
import pytest

from fifa_analytics.utils.io import (
    ensure_dir,
    read_dataframe,
    read_json,
    write_dataframe,
    write_json,
    write_yaml,
)


def test_ensure_dir_creates_nested(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    result = ensure_dir(target)
    assert result == target
    assert target.is_dir()


def test_ensure_dir_idempotent(tmp_path):
    ensure_dir(tmp_path)
    ensure_dir(tmp_path)
    assert tmp_path.is_dir()


def test_write_and_read_json(tmp_path):
    path = tmp_path / "sub" / "data.json"
    data = {"match_id": "copa_2026_jogo_001", "status": "finalizado"}
    write_json(path, data)
    assert path.exists()
    result = read_json(path)
    assert result == data


def test_write_json_creates_parent_dirs(tmp_path):
    path = tmp_path / "deep" / "nested" / "file.json"
    write_json(path, {"ok": True})
    assert path.exists()


def test_write_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    write_yaml(path, {"fonte": "worldcup2026", "status": "finalizado"})
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "worldcup2026" in content


def test_write_and_read_dataframe(tmp_path):
    path = tmp_path / "matches.parquet"
    df = pd.DataFrame([
        {"match_id": "copa_2026_jogo_001", "home_team": "Brasil", "away_team": "Alemanha"},
        {"match_id": "copa_2026_jogo_002", "home_team": "Argentina", "away_team": "França"},
    ])
    write_dataframe(path, df)
    assert path.exists()
    result = read_dataframe(path)
    assert list(result["match_id"]) == ["copa_2026_jogo_001", "copa_2026_jogo_002"]
    assert len(result) == 2


def test_write_dataframe_creates_parent_dirs(tmp_path):
    path = tmp_path / "gold" / "dim_match" / "canonical_matches.parquet"
    df = pd.DataFrame([{"match_id": "copa_2026_jogo_001"}])
    write_dataframe(path, df)
    assert path.exists()
