"""F8.5: speech -> text for the chat composer, through the local recognizer (scripts/serve_asr.py on loopback).

The person records at most 60 s; the audio goes to the local service only, is transcribed once and is not kept, and the
text comes back for the person to read, edit and send themselves. Nothing is sent to the chat automatically.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable

import httpx

from campus247.ports.campus_ops import OpsError

MAX_BYTES = 2 * 1024 * 1024
DAILY_LIMIT = 30
ALLOWED_TYPES = ("audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp4")


class VoiceService:
    def __init__(self, base_url: str, token_file: Path, *, client: httpx.Client | None = None, clock: Callable[[], float] = time.time,
                 daily_limit: int = DAILY_LIMIT):
        self.base_url, self.token_file = base_url.rstrip("/"), token_file
        self.client = client or httpx.Client(timeout=httpx.Timeout(130.0, connect=2.0), trust_env=False)
        self.clock, self.daily_limit = clock, daily_limit
        self._hits: dict[str, deque] = defaultdict(deque)

    def _limit(self, subject: str) -> None:
        now, window = self.clock(), self._hits[subject]
        while window and now - window[0] > 86400:
            window.popleft()
        if len(window) >= self.daily_limit:
            raise OpsError(429, "VOICE_RATE", "Bạn đã dùng hết lượt nhận dạng giọng nói hôm nay.")
        window.append(now)

    def transcribe(self, subject_id: str, audio: bytes, content_type: str) -> dict:
        if not audio:
            raise OpsError(422, "VOICE_EMPTY", "Chưa có đoạn ghi âm.")
        if len(audio) > MAX_BYTES:
            raise OpsError(413, "VOICE_TOO_LARGE", "Đoạn ghi âm lớn hơn 2 MB.")
        if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_TYPES:
            raise OpsError(415, "VOICE_TYPE", "Định dạng âm thanh không được hỗ trợ.")
        self._limit(subject_id)
        try:
            token = self.token_file.read_text(encoding="ascii").strip()
            reply = self.client.post(f"{self.base_url}/transcribe", content=audio,
                                     headers={"X-Internal-Token": token, "Content-Type": "application/octet-stream"})
        except (OSError, httpx.HTTPError):
            raise OpsError(503, "VOICE_UNAVAILABLE", "Nhận dạng giọng nói chưa sẵn sàng.") from None
        try:
            body = reply.json()
        except ValueError:
            body = {}
        if reply.status_code == 200:
            return {k: body[k] for k in ("text", "segments", "language", "duration_s") if k in body}
        code = body.get("code")
        if reply.status_code == 413:
            raise OpsError(413, code or "VOICE_TOO_LONG", "Đoạn ghi âm dài hơn 60 giây." if code == "VOICE_TOO_LONG" else "Đoạn ghi âm quá lớn.")
        if reply.status_code == 422:
            raise OpsError(422, "VOICE_UNREADABLE", "Không nghe được đoạn ghi âm, hãy thử lại.")
        raise OpsError(503, "VOICE_UNAVAILABLE", "Nhận dạng giọng nói chưa sẵn sàng.")
