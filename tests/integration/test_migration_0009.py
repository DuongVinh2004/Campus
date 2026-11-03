from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "services" / "api" / "alembic.ini"
MIGRATION_0009_PATH = ROOT / "services" / "api" / "migrations" / "versions" / "0009_schedule_and_vectors.py"


def test_migration_0009_file_exists():
    assert MIGRATION_0009_PATH.is_file(), "0009_schedule_and_vectors.py must exist"


def test_migration_0009_attributes():
    spec = importlib.util.spec_from_file_location("migration_0009", str(MIGRATION_0009_PATH))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "0009"
    assert mod.down_revision == "0008"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


def test_historical_0009_0010_ancestry_is_preserved():
    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    assert script.get_revision("0009").down_revision == "0008"
    assert script.get_revision("0010").down_revision == "0009"
    assert [rev.revision for rev in script.walk_revisions("base", "0010")] == [
        "0010", "0009", "0008", "0007", "0006", "0005", "0004", "0003", "0002", "0001"
    ]
    # A new head is valid only through the additive manifest descendant, with
    # separate live schema/data preservation evidence in the manifest suite.
    heads = script.get_heads()
    assert len(heads) == 1
    descendants = list(script.iterate_revisions(heads[0], "0010"))
    # FILTER-001 has independent live schema/data/index preservation evidence. Later additive
    # revisions (0014 onward) extend the same single linear chain; none may fork it or re-parent
    # 0011-0013.
    chain = [(rev.revision, rev.down_revision) for rev in descendants]
    assert chain[-3:] == [("0013", "0012"), ("0012", "0011"), ("0011", "0010")]
    assert all(isinstance(down, str) for _, down in chain)
    assert [down for _, down in chain][:-1] == [revision for revision, _ in chain][1:]
