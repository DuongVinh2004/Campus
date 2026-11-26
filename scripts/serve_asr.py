"""Local Vietnamese speech recognition for F8.4 (input.voice): one loopback HTTP service, nothing leaves the machine.

  .tooling/asr-20261126/.venv/Scripts/python.exe -B scripts/serve_asr.py serve [--port 18083]

Model: faster-whisper small (OpenAI Whisper weights converted by Systran, MIT), int8 on CPU, 4 threads, beam 5, Vietnamese.
Chosen on the D6b test set (evals/runners/asr_eval.py: FLEURS vi dev, 100 sentences): WER 18.96 %, processing time p95
0.593 x clip length on this machine. Files are checked against their pinned SHA-256 before the model loads.

The model loads on the first request and only while the OS reports at least asr_mb + 500 MB free (the RAM gate; otherwise
503 VOICE_UNAVAILABLE and nothing is loaded); it is unloaded after IDLE_UNLOAD_S without requests. Requests carry the internal
token (STATE/asr-sidecar.token, created on first start, never printed) and one audio file of at most 2 MB and 60 s. Audio is
decoded in memory, transcribed once and dropped; no audio and no text is written anywhere.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import hmac
import io
import json
import logging
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts")]
from runtime_profile import available_memory_mb, load_profile  # noqa: E402

MODEL_DIR = ROOT / ".tooling/asr-20261126/models/faster-whisper-small"
PINS = {  # Systran/faster-whisper-small @ 536b0662742c02347bc0e980a01041f333bce120 (model.bin = its LFS sha256)
    "model.bin": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
}
STATE = ROOT / "infra/local/knowledge-platform-20261023"
TOKEN_FILE = STATE / "asr-sidecar.token"
MAX_BYTES = 2 * 1024 * 1024
MAX_SECONDS = 60.0
IDLE_UNLOAD_S = 600
HEADROOM_MB = 500
log = logging.getLogger("campus247.asr")


def token() -> str:
    if not TOKEN_FILE.is_file():
        TOKEN_FILE.write_text(secrets.token_urlsafe(32), encoding="ascii")
    return TOKEN_FILE.read_text(encoding="ascii").strip()


class Recognizer:
    def __init__(self, need_mb: int, *, memory=available_memory_mb, clock=time.monotonic):
        self.need_mb, self.memory, self.clock = need_mb, memory, clock
        self.model = None
        self.lock = threading.Lock()
        self.last_used = clock()

    def state(self) -> str:
        return "loaded" if self.model is not None else "idle"

    def _load(self):
        free = self.memory()
        if free < self.need_mb + HEADROOM_MB:
            log.warning("asr_ram_refused free_mb=%d need_mb=%d", free, self.need_mb + HEADROOM_MB)
            raise MemoryError("not enough free memory for the speech model")
        for name, pin in PINS.items():
            with open(MODEL_DIR / name, "rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != pin:
                    raise RuntimeError("speech model file does not match its pinned hash")
        from faster_whisper import WhisperModel
        self.model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8", cpu_threads=4)

    def unload_if_idle(self):
        with self.lock:
            if self.model is not None and self.clock() - self.last_used > IDLE_UNLOAD_S:
                self.model = None
                gc.collect()
                log.info("asr_unloaded")

    def transcribe(self, audio: bytes) -> dict:
        from faster_whisper.audio import decode_audio
        samples = decode_audio(io.BytesIO(audio), sampling_rate=16000)
        duration = len(samples) / 16000
        if duration > MAX_SECONDS + 0.5:
            raise OverflowError("audio longer than 60 seconds")
        if duration < 0.2:
            raise ValueError("audio too short")
        with self.lock:
            if self.model is None:
                self._load()
            self.last_used = self.clock()
            started = self.clock()
            segments, _ = self.model.transcribe(samples, language="vi", beam_size=5, vad_filter=False, condition_on_previous_text=False)
            parts = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
            took = self.clock() - started
        return {"text": " ".join(p["text"] for p in parts).strip(), "segments": parts, "language": "vi", "duration_s": round(duration, 2),
                "rtf": round(took / duration, 3) if duration else None}


def make_handler(recognizer: Recognizer, secret: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # no request lines (they carry nothing useful and must not carry content)
            return

        def reply(self, status: int, body: dict):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self) -> bool:
            return hmac.compare_digest(self.headers.get("X-Internal-Token", ""), secret)

        def do_GET(self):
            if self.path != "/health":
                return self.reply(404, {"code": "NOT_FOUND"})
            self.reply(200, {"status": "ready", "model": MODEL_DIR.name, "state": recognizer.state()})

        def do_POST(self):
            if self.path != "/transcribe":
                return self.reply(404, {"code": "NOT_FOUND"})
            if not self.authorized():
                return self.reply(401, {"code": "UNAUTHORIZED"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BYTES:
                return self.reply(413, {"code": "VOICE_TOO_LARGE"})
            audio = self.rfile.read(length)
            try:
                result = recognizer.transcribe(audio)
            except MemoryError:
                return self.reply(503, {"code": "VOICE_UNAVAILABLE", "reason": "RAM"})
            except OverflowError:
                return self.reply(413, {"code": "VOICE_TOO_LONG"})
            except Exception as error:  # noqa: BLE001 -- undecodable audio or a model failure: no detail leaves the process
                log.warning("asr_failed kind=%s", type(error).__name__)
                return self.reply(422, {"code": "VOICE_UNREADABLE"})
            self.reply(200, result)
    return Handler


def serve(port: int, profile: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    recognizer = Recognizer(load_profile(profile).asr_mb)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(recognizer, token()))

    def janitor():
        while True:
            time.sleep(30)
            recognizer.unload_if_idle()

    threading.Thread(target=janitor, daemon=True).start()
    log.info("asr_listening port=%d", port)
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("serve")
    run.add_argument("--port", type=int, default=18083)
    run.add_argument("--profile", default="local")
    args = parser.parse_args()
    serve(args.port, args.profile)
