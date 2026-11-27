from __future__ import annotations

from pathlib import Path
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "services" / "api" / "alembic.ini"
MIGRATIONS_DIR = ROOT / "services" / "api" / "migrations"


def test_alembic_configuration_valid():
    """Verify alembic.ini is present and correctly loads script directory."""
    assert ALEMBIC_INI.is_file(), "services/api/alembic.ini must exist"
    assert (MIGRATIONS_DIR / "env.py").is_file(), "services/api/migrations/env.py must exist"

    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    assert script.dir == str(MIGRATIONS_DIR.resolve())


def test_alembic_script_directory_discovery():
    """Verify script directory discovers migration environment and versions location."""
    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() is not None


def test_invalid_alembic_config_failure_path(tmp_path: Path):
    """Verify attempting to load ScriptDirectory with missing script_location fails."""
    bad_ini = tmp_path / "bad_alembic.ini"
    bad_ini.write_text("[alembic]\nscript_location = nonexistent_dir_12345\n", encoding="utf-8")

    config = Config(str(bad_ini))
    with pytest.raises((CommandError, FileNotFoundError)):
        ScriptDirectory.from_config(config)


def test_env_creates_pgvector_only_for_a_database_without_a_revision():
    """Migration 0009 adds a VECTOR column: a brand-new database needs the extension first (found by the 2026-11-25 audit)."""
    source = (MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8")
    guarded = source[source.index("def do_run_migrations"):source.index("async def run_async_migrations")]
    assert "get_current_revision() is None" in guarded
    assert guarded.index("get_current_revision() is None") < guarded.index("CREATE EXTENSION IF NOT EXISTS vector") < guarded.index("run_migrations()")
