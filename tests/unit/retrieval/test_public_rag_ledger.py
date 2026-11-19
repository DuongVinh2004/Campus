"""Writer exclusivity and restart recovery, without credentials or paid calls."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import run_public_rag as public
from scripts.public_rag_ledger import MARKER, PaidLedgerWriterLease


def test_second_process_cannot_own_the_same_ledger(tmp_path):
    path = tmp_path / "lease.lock"
    lease = PaidLedgerWriterLease(path)
    try:
        result = subprocess.run([sys.executable, "-B", "-c",
            ("from pathlib import Path; from scripts.public_rag_ledger import PaidLedgerWriterLease; "
             "import sys; PaidLedgerWriterLease(Path(sys.argv[1]))"), str(path)],
            cwd=ROOT, capture_output=True, timeout=10, check=False)
        assert result.returncode != 0 and b"PermissionError" in result.stderr
    finally:
        lease.close()
    assert path.read_bytes() == MARKER
    reacquired = PaidLedgerWriterLease(path)
    reacquired.close()
    assert path.read_bytes() == MARKER


def test_unknown_existing_file_is_preserved(tmp_path):
    path = tmp_path / "lease.lock"
    path.write_bytes(b"user-owned-data")
    with pytest.raises(ValueError, match="unrecognized"):
        PaidLedgerWriterLease(path)
    assert path.read_bytes() == b"user-owned-data"


def test_outside_workspace_is_rejected_before_creation():
    with pytest.raises(ValueError, match="outside workspace"):
        PaidLedgerWriterLease(ROOT.parent / "campus-paid-ledger-test.lock")


def test_failed_gateway_initialization_releases_lease_without_touching_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(public, "STATE", tmp_path)
    def fail(_):
        raise RuntimeError("offline initialization failure")
    monkeypatch.setattr(public.Gateway, "_initialize", fail)
    with pytest.raises(RuntimeError, match="offline initialization"):
        public.Gateway()
    lease = PaidLedgerWriterLease(tmp_path / "paid-ledger-writer.lock")
    lease.close()
    assert list(tmp_path.iterdir()) == [tmp_path / "paid-ledger-writer.lock"]
