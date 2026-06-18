import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: str | Path, data: Any) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    return path


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_yaml(path: str | Path, data: Any) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
    return path


def read_yaml(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def write_dataframe(path: str | Path, dataframe: pd.DataFrame) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    dataframe.to_parquet(path, index=False)
    return path


def read_dataframe(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)

