"""F0.7/F0.2: the generated TypeScript registry matches the Python registry, and feature profile files only name real features."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from campus247.features.registry import BY_KEY
from campus247.infrastructure.feature_profile import load_feature_profile

ROOT = Path(__file__).resolve().parents[2]


def test_generated_registry_is_current():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/export_feature_registry.py"), "--check"], capture_output=True)
    assert result.returncode == 0, "out of date: run python scripts/export_feature_registry.py"


def test_profile_files_only_name_known_features():
    for name in ("local", "cloud"):
        values = load_feature_profile(name, ROOT / "infra/profiles")
        assert set(values) <= set(BY_KEY)
    assert load_feature_profile("cloud", ROOT / "infra/profiles")["learning.core"] is False
