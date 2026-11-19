"""The out-of-process watchdog: it judges probes with the same alert engine, needs two minutes to fire, and imports no application code."""
import configparser
import importlib.util
import logging
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
CLOUD = ROOT / "infra/cloud"
sys.path.insert(0, str(ROOT / "services/api/src"))
spec = importlib.util.spec_from_file_location("campus_watchdog", CLOUD / "watchdog.py")
watchdog = importlib.util.module_from_spec(spec)
sys.modules["campus_watchdog"] = watchdog
spec.loader.exec_module(watchdog)

T0 = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


def client(down=()):
    def handler(request: httpx.Request):
        if request.url.port in down:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={})

    return httpx.Client(transport=httpx.MockTransport(handler))


def space(free_pct):
    return lambda path: SimpleNamespace(free=free_pct, total=100)


def run(tmp_path, minute, down=(), free_pct=40):
    # Disk space is injected: the real drive's free space must not decide whether a test passes.
    return watchdog.check(tmp_path / "state", tmp_path, environ={}, client=client(down), now=T0 + timedelta(minutes=minute), usage=space(free_pct))


def test_probes_report_each_service_and_the_disk(tmp_path):
    with client(down=(18082,)) as http:
        results = watchdog.probe_all(http, tmp_path, space(40))
    assert results == {"api_ready": True, "gateway": True, "embedding": True, "reranker": False, "disk": True}


def test_a_down_service_alerts_only_after_two_minutes_and_recovery_needs_two_good_minutes(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
        assert run(tmp_path, 0, down=(8015,)) == [] and run(tmp_path, 1, down=(8015,)) == []
        assert run(tmp_path, 2, down=(8015,)) == ["watchdog_api_ready"]
        assert run(tmp_path, 3, down=(8015,)) == []                      # already said so
        assert run(tmp_path, 4) == [] and run(tmp_path, 5) == ["watchdog_api_ready"]  # resolved after two good runs
    assert "[CRITICAL] Campus 24/7 · API không sẵn sàng" in caplog.text and "[ĐÃ ỔN]" in caplog.text


def test_a_one_minute_blip_is_silent(tmp_path):
    assert run(tmp_path, 0, down=(18081,)) == [] and run(tmp_path, 1) == [] and run(tmp_path, 2) == []


def test_each_service_has_its_own_alert(tmp_path):
    run(tmp_path, 0, down=(8025, 18081))
    assert sorted(run(tmp_path, 2, down=(8025, 18081))) == ["watchdog_embedding", "watchdog_gateway"]


def test_a_nearly_full_disk_alerts_at_once_and_resolves_after_two_good_runs(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
        assert run(tmp_path, 0, free_pct=4) == ["watchdog_disk"]  # a full disk does not blip: no waiting period
        assert run(tmp_path, 1, free_pct=5) == [] and run(tmp_path, 2, free_pct=5) == ["watchdog_disk"]  # exactly 5 % is not below the line
    assert "Sắp hết dung lượng đĩa" in caplog.text and "[ĐÃ ỔN]" in caplog.text


def test_unit_failed_accepts_only_campus_units(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
        watchdog.unit_failed("campus247-api.service", environ={}, now=T0)
    assert "Một dịch vụ đã dừng hẳn · campus247-api.service" in caplog.text
    for bad in ("sshd.service", "campus247-api.service; rm -rf /", "campus247-$(id).service", ""):
        with pytest.raises(SystemExit):
            watchdog.unit_failed(bad, environ={}, now=T0)


def test_the_watchdog_imports_no_application_code():
    code = ("import sys; sys.path.insert(0, r'%s'); import importlib.util as u; s = u.spec_from_file_location('w', r'%s'); m = u.module_from_spec(s); "
            "s.loader.exec_module(m); bad = [n for n in sys.modules if n.startswith(('campus247.bootstrap', 'campus247.presentation', 'campus247.agent', 'fastapi'))]; print(bad)"
            % (ROOT / "services/api/src", CLOUD / "watchdog.py"))
    out = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


def unit(name):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read(CLOUD / name, encoding="utf-8")
    return parser


def test_systemd_files_run_as_the_service_user_every_minute_with_a_failure_hook():
    service = unit("campus247-watchdog.service")["Service"]
    assert service["User"] == "campus247" and service["ExecStart"].endswith("watchdog.py check") and service["StateDirectory"] == "campus247/watchdog"
    assert watchdog.DEFAULT_STATE == Path("/var/lib/campus247/watchdog")
    timer = unit("campus247-watchdog.timer")
    assert timer["Timer"]["OnUnitActiveSec"] == "1min" and timer["Install"]["WantedBy"] == "timers.target"
    alert = unit("campus247-alert@.service")["Service"]
    assert alert["ExecStart"].endswith("watchdog.py unit-failed %i") and alert["User"] == "campus247"
    assert unit("campus247-onfailure.conf")["Unit"]["OnFailure"] == "campus247-alert@%n.service"
