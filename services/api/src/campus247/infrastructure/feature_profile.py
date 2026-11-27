"""Load infra/profiles/features.<profile>.toml (F0.3). Own schema so the strict runtime profile files stay untouched."""
from __future__ import annotations

import tomllib
from pathlib import Path

SCHEMA = "campus247-features-v1"


def load_feature_profile(name: str, directory: Path) -> dict:
    if not name.isidentifier():
        raise ValueError("feature profile name must be a plain identifier")
    path = Path(directory) / f"features.{name}.toml"
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or data.get("profile") != name or set(data) - {"schema", "profile", "features"}:
        raise ValueError(f"{path.name}: schema/profile mismatch")
    features = data.get("features", {})
    if not isinstance(features, dict) or any(not isinstance(v, (bool, str)) for v in features.values()):
        raise ValueError(f"{path.name}: [features] values must be booleans or variant names")
    return features
