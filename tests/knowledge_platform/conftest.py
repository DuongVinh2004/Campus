"""All test output is retained under a fresh, task-owned workspace namespace."""
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services/worker/src"), str(ROOT / "scripts"),
               str(ROOT / ".tooling/knowledge-platform-20261023/site-packages")]


@pytest.fixture
def retained_directory():
    from campus247.infrastructure.knowledge.storage import checked_path
    path = checked_path(ROOT / "infra/local/knowledge-platform-20261023/tests" / ("case-" + uuid4().hex), ROOT)
    path.mkdir(parents=True)
    return path  # No cleanup: failed cases and evidence remain recoverable.
