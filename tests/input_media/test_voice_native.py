"""F8.4/F8.5 end to end with the real local recognizer (scripts/serve_asr.py on 18083) and real FLEURS recordings.

Opt-in (CAMPUS247_ASR_NATIVE=1): needs the recognizer running and the D6b clips extracted by evals/runners/asr_eval.py.
Checks a WAV and the same audio as WebM/Opus (what a browser's MediaRecorder sends), and that the text is close to the
human transcription (a sanity bound of 60 % word error per clip: one clip varies a lot between encodings, so quality is the set-level figure in evals/results/asr-20261126).
"""
import io
import json
import os
from pathlib import Path

import pytest

from campus247.application.input_media.voice import VoiceService

ROOT = Path(__file__).resolve().parents[2]
CLIPS = ROOT / ".tooling/asr-20261126/fleurs-vi/clips"
pytestmark = pytest.mark.skipif(os.environ.get("CAMPUS247_ASR_NATIVE") != "1" or not CLIPS.is_dir(),
                                reason="needs the local recognizer and the FLEURS clips; set CAMPUS247_ASR_NATIVE=1")


def wer(reference: str, hypothesis: str) -> float:
    import re
    import unicodedata
    norm = lambda t: re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFC", t.casefold())).split()
    a, b = norm(reference), norm(hypothesis)
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1] / max(1, len(a))


def first_clip():
    rows = [json.loads(line) for line in (ROOT / "evals/results/asr-20261126/faster-whisper-small-beam5/rows.jsonl").read_text(encoding="utf-8").splitlines()]
    import csv
    files = {r[0]: (r[1], r[3]) for r in csv.reader((CLIPS.parent / "dev.tsv").open(encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)}
    sentence = rows[0]["sentence_id"]
    return CLIPS / files[sentence][0], files[sentence][1]


def test_a_wav_and_a_browser_style_webm_are_transcribed_locally():
    service = VoiceService("http://127.0.0.1:18083", ROOT / "infra/local/knowledge-platform-20261023/asr-sidecar.token")
    clip, reference = first_clip()
    wav = clip.read_bytes()
    out = service.transcribe("synthetic-student", wav, "audio/wav")
    print("wav:", round(wer(reference, out["text"]), 3), out["duration_s"])
    assert out["language"] == "vi" and wer(reference, out["text"]) <= 0.6
    webm = to_webm(wav)
    sample = ROOT / ".pytest-tmp/voice-sample.webm"         # the same clip as WebM/Opus, made with the recognizer's own PyAV
    if webm is None and sample.is_file():
        webm = sample.read_bytes()
    if webm is None:
        pytest.skip("no WebM sample: PyAV is not importable here and .pytest-tmp/voice-sample.webm is missing")
    again = service.transcribe("synthetic-student", webm, "audio/webm;codecs=opus")
    print("webm:", round(wer(reference, again["text"]), 3))
    assert wer(reference, again["text"]) <= 0.6


def to_webm(wav: bytes):
    try:
        import av
    except ImportError:
        return None
    source, out = av.open(io.BytesIO(wav)), io.BytesIO()
    target = av.open(out, mode="w", format="webm")
    stream = target.add_stream("libopus", rate=48000)
    for frame in source.decode(audio=0):
        frame.pts = None
        for packet in stream.encode(frame):
            target.mux(packet)
    for packet in stream.encode(None):
        target.mux(packet)
    target.close()
    return out.getvalue()
