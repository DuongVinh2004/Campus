"""F8.4/F8.5 without the model: the API side of voice input and the recognizer's RAM gate."""
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from campus247.application.input_media.voice import VoiceService
from campus247.ports.campus_ops import OpsError

ROOT = Path(__file__).resolve().parents[2]


def service(tmp_path, handler, **kw):
    token = tmp_path / "asr.token"
    token.write_text("t" * 40, encoding="ascii")
    return VoiceService("http://asr.local", token, client=httpx.Client(transport=httpx.MockTransport(handler)), **kw)


def test_the_text_comes_back_and_the_token_is_sent(tmp_path):
    seen = {}

    def handler(request):
        seen["token"], seen["bytes"] = request.headers["X-Internal-Token"], request.content
        return httpx.Response(200, json={"text": "học phí bao nhiêu", "segments": [], "language": "vi", "duration_s": 2.1, "rtf": 0.3})

    out = service(tmp_path, handler).transcribe("s1", b"RIFFxxxx", "audio/wav")
    assert out == {"text": "học phí bao nhiêu", "segments": [], "language": "vi", "duration_s": 2.1}     # nothing else passes through
    assert seen == {"token": "t" * 40, "bytes": b"RIFFxxxx"}


@pytest.mark.parametrize("status,body,code", [(413, {"code": "VOICE_TOO_LONG"}, "VOICE_TOO_LONG"), (422, {"code": "VOICE_UNREADABLE"}, "VOICE_UNREADABLE"),
                                              (503, {"code": "VOICE_UNAVAILABLE", "reason": "RAM"}, "VOICE_UNAVAILABLE")])
def test_recognizer_refusals_become_clear_errors(tmp_path, status, body, code):
    with pytest.raises(OpsError) as error:
        service(tmp_path, lambda request: httpx.Response(status, json=body)).transcribe("s1", b"x", "audio/webm;codecs=opus")
    assert error.value.code == code


def test_a_stopped_recognizer_is_503_and_bad_input_never_reaches_it(tmp_path):
    def down(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(OpsError) as error:
        service(tmp_path, down).transcribe("s1", b"x", "audio/wav")
    assert error.value.status == 503 and error.value.code == "VOICE_UNAVAILABLE"
    calls = []
    svc = service(tmp_path, lambda request: calls.append(1) or httpx.Response(200, json={"text": ""}))
    for audio, kind, code in ((b"", "audio/wav", "VOICE_EMPTY"), (b"x" * (2 * 1024 * 1024 + 1), "audio/wav", "VOICE_TOO_LARGE"),
                              (b"x", "video/mp4", "VOICE_TYPE")):
        with pytest.raises(OpsError) as error:
            svc.transcribe("s1", audio, kind)
        assert error.value.code == code
    assert calls == []


def test_thirty_recordings_a_day_per_person(tmp_path):
    svc = service(tmp_path, lambda request: httpx.Response(200, json={"text": "a"}), daily_limit=2, clock=lambda: 1000.0)
    svc.transcribe("s1", b"x", "audio/wav")
    svc.transcribe("s1", b"x", "audio/wav")
    with pytest.raises(OpsError) as error:
        svc.transcribe("s1", b"x", "audio/wav")
    assert error.value.code == "VOICE_RATE"
    assert svc.transcribe("s2", b"x", "audio/wav")["text"] == "a"


def load_server():
    spec = importlib.util.spec_from_file_location("serve_asr", ROOT / "scripts/serve_asr.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(module)
    return module


def test_the_ram_gate_refuses_to_load_the_model_when_memory_is_short():
    server = load_server()
    recognizer = server.Recognizer(700, memory=lambda: 1100)            # below 700 + 500
    with pytest.raises(MemoryError):
        recognizer._load()
    assert recognizer.model is None and recognizer.state() == "idle"


def test_an_idle_model_is_unloaded():
    server = load_server()
    now = [0.0]
    recognizer = server.Recognizer(700, memory=lambda: 99999, clock=lambda: now[0])
    recognizer.model = object()
    now[0] = server.IDLE_UNLOAD_S - 1
    recognizer.unload_if_idle()
    assert recognizer.model is not None
    now[0] = server.IDLE_UNLOAD_S + 1
    recognizer.unload_if_idle()
    assert recognizer.model is None
