"""Learning child processes (PDF inspection, scanner) must run under the selector loop uvicorn uses for --workers on Windows."""
import asyncio
import sys
import time

import pytest

from campus247.infrastructure.learning.blob import run_bounded


def _on_selector_loop(coroutine):
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def test_child_output_and_exit_code_under_selector_loop():
    code, out = _on_selector_loop(run_bounded([sys.executable, "-c", "print('ok'); raise SystemExit(3)"], timeout=30, capture=True))
    assert code == 3 and out.strip() == b"ok"


def test_time_limit_kills_the_child():
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        _on_selector_loop(run_bounded([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1))
    assert time.monotonic() - started < 15


def test_without_capture_returns_no_output():
    code, out = _on_selector_loop(run_bounded([sys.executable, "-c", "print('hidden')"], timeout=30))
    assert code == 0 and out is None
