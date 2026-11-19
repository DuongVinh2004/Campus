"""Disconnected clients cannot flood a model serving thread's stderr pipe."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.serve_rag_models import LoopbackHTTPServer


@pytest.mark.parametrize("error", [BrokenPipeError, ConnectionAbortedError, ValueError])
def test_model_boundary_keeps_finite_diagnostics_without_raw_traceback(capsys, error):
    server = LoopbackHTTPServer.__new__(LoopbackHTTPServer)
    server.server_port = 18082
    try:
        raise error("PRIVATE_MODEL_INPUT")
    except error:
        server.handle_error(None, ("127.0.0.1", 12345))
    captured = capsys.readouterr()
    assert not captured.err
    assert "model_http_failure" in captured.out and "18082" in captured.out
    assert "PRIVATE_MODEL_INPUT" not in captured.out and "Traceback" not in captured.out
    assert ("MODEL_HTTP_BOUNDARY_FAILURE" if error is ValueError else error.__name__) in captured.out
