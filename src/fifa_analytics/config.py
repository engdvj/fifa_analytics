from pathlib import Path
from typing import Any

import yaml

from fifa_analytics.paths import CONFIG_DIR, SCHEMAS_DIR


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return an empty dict for empty files."""
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_config(name: str) -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / name)


def load_schema(name: str) -> dict[str, Any]:
    return load_yaml(SCHEMAS_DIR / name)

