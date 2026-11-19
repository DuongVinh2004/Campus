"""Nightly retrieval check: metrics, regression detection, never overwriting earlier results, and skipping when the models are down."""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("nightly_retrieval", ROOT / "evals/runners/nightly_retrieval.py")
nightly = importlib.util.module_from_spec(spec)
sys.modules["nightly_retrieval"] = nightly
spec.loader.exec_module(nightly)

T = lambda day=17: datetime(2026, 11, day, 2, 30, tzinfo=timezone.utc)  # noqa: E731


def probe_output(n=120, any_hit=114, top8=108, final=102):
    return {"summary": {"dev|answer": {"n": n // 2, "any_hit": any_hit // 2, "fused_top8_hit": top8 // 2, "final_hit": final // 2},
                        "dev|paraphrase": {"n": n - n // 2, "any_hit": any_hit - any_hit // 2, "fused_top8_hit": top8 - top8 // 2, "final_hit": final - final // 2}},
            "rows": [], "rerank_mode": "http", "embedding_mode": "http"}


def fake_probe(output):
    def run(out, limit, index):
        out.write_text(json.dumps(output), encoding="utf-8")
        return output
    return run


UP = lambda url: True  # noqa: E731
DOWN = lambda url: False  # noqa: E731


def test_metrics_are_shares_of_the_cases_across_all_variants():
    metrics = nightly.metrics_from(probe_output())
    assert metrics["cases"] == 120 and metrics["any"] == pytest.approx(0.95) and metrics["fused_top8"] == pytest.approx(0.9)
    assert metrics["survive"] == pytest.approx(0.85) and metrics["rerank"] == "http"


def test_a_probe_with_no_cases_is_an_error_not_a_perfect_score():
    with pytest.raises(ValueError):
        nightly.metrics_from({"summary": {}})


@pytest.mark.parametrize(("drop", "flagged"), [({"fused_top8": 0.03}, False), ({"fused_top8": 0.031}, True), ({"survive": 0.05}, False),
                                              ({"survive": 0.06}, True), ({}, False)])
def test_regression_thresholds(drop, flagged):
    base = {"fused_top8": 0.90, "survive": 0.85}
    now = {key: base[key] - drop.get(key, 0.0) for key in base}
    assert bool(nightly.regressions(now, base)) is flagged
    assert nightly.regressions(now, None) == []


def test_an_improvement_is_not_a_regression():
    assert nightly.regressions({"fused_top8": 0.95, "survive": 0.9}, {"fused_top8": 0.90, "survive": 0.85}) == []


def test_a_run_records_everything_and_appends_one_trend_line(tmp_path):
    latest = nightly.run(tmp_path, probe=fake_probe(probe_output()), check=UP, now=T)
    assert latest["ok"] and latest["folder"] == "20261117" and latest["regressions"] == [] and latest["baseline"] is False
    assert (tmp_path / "20261117" / "retrieval.json").is_file() and json.loads((tmp_path / "20261117" / "run.json").read_text(encoding="utf-8"))["ok"]
    lines = (tmp_path / "trend.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["fused_top8"] == pytest.approx(0.9) and json.loads(lines[0])["regressed"] is False
    assert json.loads((tmp_path / "LATEST.json").read_text(encoding="utf-8"))["folder"] == "20261117"


def test_a_second_run_on_the_same_day_gets_a_new_folder_and_nothing_is_overwritten(tmp_path):
    first = nightly.run(tmp_path, probe=fake_probe(probe_output()), check=UP, now=T)
    before = (tmp_path / first["folder"] / "retrieval.json").read_text(encoding="utf-8")
    second = nightly.run(tmp_path, probe=fake_probe(probe_output(top8=60)), check=UP, now=T)
    assert second["folder"] == "20261117-02" and (tmp_path / "20261117" / "retrieval.json").read_text(encoding="utf-8") == before
    assert len((tmp_path / "trend.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_a_drop_against_the_baseline_is_reported_and_trended_as_regressed(tmp_path):
    good = nightly.run(tmp_path, probe=fake_probe(probe_output()), check=UP, now=T)
    nightly.adopt_baseline(tmp_path, tmp_path / good["folder"])
    bad = nightly.run(tmp_path, probe=fake_probe(probe_output(top8=96, final=90)), check=UP, now=lambda: T(18))
    assert bad["baseline"] is True and len(bad["regressions"]) == 2 and "fused_top8 fell 10.0 points" in bad["regressions"][0]
    assert json.loads((tmp_path / "trend.jsonl").read_text(encoding="utf-8").splitlines()[-1])["regressed"] is True


def test_adopting_a_baseline_keeps_the_previous_one_and_refuses_an_unfinished_run(tmp_path):
    first = nightly.run(tmp_path, probe=fake_probe(probe_output()), check=UP, now=T)
    nightly.adopt_baseline(tmp_path, tmp_path / first["folder"])
    second = nightly.run(tmp_path, probe=fake_probe(probe_output(top8=100)), check=UP, now=lambda: T(18))
    nightly.adopt_baseline(tmp_path, tmp_path / second["folder"])
    assert len(list(tmp_path.glob("baseline-before-*.json"))) == 2  # the automatic first baseline, then the one adopted by hand
    assert json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))["from"] == second["folder"]
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "run.json").write_text(json.dumps({"ok": False}), encoding="utf-8")
    with pytest.raises(SystemExit):
        nightly.adopt_baseline(tmp_path, tmp_path / "broken")


def test_models_down_skips_the_run_and_says_why_without_creating_a_result_folder(tmp_path):
    calls = []
    latest = nightly.run(tmp_path, probe=lambda *a: calls.append(a), check=DOWN, now=T)
    assert latest["skipped"] == "models_down" and latest["ok"] is False and calls == []
    assert [p.name for p in tmp_path.iterdir()] == ["LATEST.json"]


def test_a_probe_that_crashes_is_recorded_by_error_type_and_does_not_add_a_trend_line(tmp_path):
    def broken(out, limit, index):
        raise subprocess.CalledProcessError(1, "probe", stderr="secret details")

    latest = nightly.run(tmp_path, probe=broken, check=UP, now=T)
    assert latest["ok"] is False and latest["error"] == "CalledProcessError" and "secret" not in json.dumps(latest)
    assert not (tmp_path / "trend.jsonl").exists()


def test_the_real_probe_is_the_existing_script_and_never_calls_a_model_that_writes_answers():
    text = (ROOT / "evals/runners/rag_v2_retrieval_probe.py").read_text(encoding="utf-8").lower()
    assert nightly.PROBE.is_file() and "--split" in text and "--limit" in text
    assert "gateway" not in text and "deepseek" not in text and "llmrequest" not in text
    assert nightly.MODEL_URLS == ("http://127.0.0.1:18081/info", "http://127.0.0.1:18082/info")


def test_the_systemd_files_run_the_script_at_low_priority_before_the_backup():
    import configparser

    def unit(name):
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        parser.optionxform = str
        parser.read(ROOT / "infra/cloud" / name, encoding="utf-8")
        return parser

    service, timer = unit("campus247-retrieval-check.service"), unit("campus247-retrieval-check.timer")
    assert service["Service"]["ExecStart"].endswith("nightly_retrieval.py run --trigger schedule") and service["Service"]["User"] == "campus247"
    assert service["Service"]["Nice"] == "15" and service["Service"]["IOSchedulingClass"] == "idle"
    assert timer["Timer"]["OnCalendar"] == "*-*-* 02:30:00" and timer["Timer"]["Persistent"] == "true" and timer["Install"]["WantedBy"] == "timers.target"


def test_the_first_successful_run_becomes_the_baseline_and_no_later_run_replaces_it(tmp_path):
    first = nightly.run(tmp_path, probe=fake_probe(probe_output()), check=UP, now=T)
    baseline = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    assert baseline["auto"] is True and baseline["from"] == first["folder"] and baseline["metrics"]["fused_top8"] == pytest.approx(0.9)
    worse = nightly.run(tmp_path, probe=fake_probe(probe_output(top8=60)), check=UP, now=lambda: T(18))
    assert worse["baseline"] is True and worse["regressions"]  # compared with the first run, which stays the reference
    assert json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8")) == baseline


def test_a_run_that_is_skipped_or_crashes_does_not_create_a_baseline(tmp_path):
    nightly.run(tmp_path, probe=fake_probe(probe_output()), check=DOWN, now=T)
    def crash(out, limit, index):
        raise subprocess.SubprocessError("boom")
    nightly.run(tmp_path, probe=crash, check=UP, now=T)
    assert not (tmp_path / "baseline.json").exists()
