"""The learning module's use of the shared scanner: error mapping, receipts on versions and the cloud guard."""
import asyncio
import json
import sys
from pathlib import Path

import pytest
from campus247.bootstrap.learning import load_local_learning
from campus247.domain.learning import LearningError
from campus247.infrastructure.learning.blob import PortScannerAdapter
from campus247.ports.file_scanner import ScanReceipt, ScanRejected, ScannerUnavailable

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from learning_local_setup import setup  # noqa: E402


class Stub:
    name = "stub"

    def __init__(self, outcome):
        self.outcome = outcome

    async def scan(self, path):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def attempt(outcome):
    return asyncio.run(PortScannerAdapter(Stub(outcome)).scan(Path("x")))


def test_a_hit_becomes_a_generic_rejection_without_the_signature():
    with pytest.raises(LearningError) as raised:
        attempt(ScanRejected("MALWARE_DETECTED", "Pdf.Exploit.Secret-Name"))
    assert (raised.value.status, raised.value.code) == (422, "FILE_REJECTED")
    assert "Pdf.Exploit" not in raised.value.detail


@pytest.mark.parametrize("code,expected", [("SCANNER_STALE", "SCANNER_STALE"), ("SCANNER_ERROR", "SCANNER_UNAVAILABLE"),
                                           ("SCANNER_UNAVAILABLE", "SCANNER_UNAVAILABLE")])
def test_no_verdict_is_a_503(code, expected):
    with pytest.raises(LearningError) as raised:
        attempt(ScannerUnavailable(code))
    assert (raised.value.status, raised.value.code) == (503, expected)


def test_a_clean_receipt_passes_through():
    receipt = ScanReceipt("clamav", "1.5.4", "28173", "2026-11-03T13:27:52+00:00", "a" * 64, 10, 3, "2026-11-17T00:00:00+00:00")
    assert attempt(receipt) is receipt


@pytest.fixture
def bundle(tmp_path):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError("Use an explicit new --basetemp inside the authorized repository")
    directory = tmp_path / "local"
    setup(directory, "scanner-wiring-test")
    return directory, json.loads((directory / "config.json").read_text())


def write(directory, name, value):
    path = directory / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def load(path):
    return load_local_learning(path, workspace=ROOT, tenant_id="scanner-wiring-test")


def test_clamd_mode_builds_the_adapter_with_the_configured_freshness(bundle):
    directory, value = bundle
    service, _ = load(write(directory, "clamd.json", value | {"scanner_mode": "clamd", "scanner_port": 33100,
                                                              "scanner_max_database_age_hours": 24}))
    assert isinstance(service.scanner, PortScannerAdapter)
    assert service.scanner.scanner.port == 33100 and service.scanner.scanner.max_database_age.total_seconds() == 24 * 3600


@pytest.mark.parametrize("extra", [
    {"scanner_mode": "clamd"},
    {"scanner_mode": "clamd", "scanner_port": 33100, "scanner_socket": "/run/clamav/clamd.ctl"},
    {"scanner_mode": "clamd", "scanner_port": 33100, "scanner_host": "10.1.2.3"},
    {"scanner_mode": "clamd", "scanner_port": 33100, "scanner_max_database_age_hours": 0},
    {"scanner_mode": "clamd", "scanner_socket": "relative/clamd.ctl"},
])
def test_clamd_mode_rejects_unsafe_or_ambiguous_settings(bundle, extra):
    directory, value = bundle
    with pytest.raises(ValueError):
        load(write(directory, "bad.json", value | extra))


@pytest.mark.parametrize("mode", ["fixture", "unavailable"])
def test_the_cloud_profile_refuses_any_scanner_but_clamd(bundle, monkeypatch, mode):
    directory, value = bundle
    path = write(directory, "cloud.json", value | {"scanner_mode": mode})
    load(path)  # fine locally
    monkeypatch.setenv("CAMPUS247_PROFILE", "cloud")
    with pytest.raises(ValueError, match="cloud profile requires scanner_mode 'clamd'"):
        load(path)
    cloud = write(directory, "cloud-clamd.json", value | {"scanner_mode": "clamd", "scanner_port": 33100})
    load(cloud)
