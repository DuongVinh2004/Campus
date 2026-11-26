"""F8.6 voice test set (D6b): word error rate and speed of a local Vietnamese speech model on 100 FLEURS clips.

  .tooling/asr-20261126/.venv/Scripts/python.exe -B evals/runners/asr_eval.py --model .tooling/asr-20261126/models/faster-whisper-small

Test set: FLEURS vi_vn dev (Google, CC-BY 4.0; downloaded from huggingface.co/datasets/google/fleurs, SHA-256 checked), 100
recordings of 100 different sentences chosen by a fixed seed. The reference is FLEURS's own normalised transcription (read
speech by native speakers, so the gold is human). WER is computed on words after the same normalisation of both sides
(lower case, punctuation removed). Speed: processing time divided by clip length (RTF) on this machine's CPU; target p95 of
the ratio <= 1.5 and WER <= 20 % (docs/design-20261125/09-multimodal-input.md §3.4). Campus-style questions are not in FLEURS:
the result says how well the model hears Vietnamese, not how well it hears our users (unmeasured).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import tarfile
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / ".tooling/asr-20261126/fleurs-vi"
DEV_SHA256 = "8821a394c99069409b3ce7bb5cd14b10b709f2ee2fea16f42b4701e1cc9ef673"
SEED = 20261126


def normalise(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.casefold())
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def select(n: int) -> list[dict]:
    rows = list(csv.reader((DATA / "dev.tsv").open(encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    by_sentence: dict[str, list[list[str]]] = {}
    for row in rows:
        by_sentence.setdefault(row[0], []).append(row)
    rng = random.Random(SEED)
    sentences = sorted(by_sentence)
    rng.shuffle(sentences)
    chosen = []
    for sentence in sentences[:n]:
        row = sorted(by_sentence[sentence], key=lambda r: r[1])[0]
        chosen.append({"sentence_id": sentence, "file": row[1], "reference": row[3], "seconds": int(row[5]) / 16000})
    return chosen


def extract(clips: list[dict]) -> Path:
    archive = DATA / "dev.tar.gz"
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != DEV_SHA256:
        raise SystemExit("FLEURS archive checksum mismatch")
    target = DATA / "clips"
    target.mkdir(exist_ok=True)
    wanted = {"dev/" + c["file"] for c in clips}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if member.name in wanted and member.isfile() and not (target / Path(member.name).name).exists():
                (target / Path(member.name).name).write_bytes(tar.extractfile(member).read())
    return target


def to_webm(wav: bytes, bitrate: int):
    """The clip as a browser would upload it (WebM/Opus, 48 kHz mono), decoded again by the recognizer."""
    import io
    import av
    source, out = av.open(io.BytesIO(wav)), io.BytesIO()
    target = av.open(out, mode="w", format="webm")
    stream = target.add_stream("libopus", rate=48000)
    stream.bit_rate = bitrate
    resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
    for frame in source.decode(audio=0):
        for resampled in resampler.resample(frame):
            for packet in stream.encode(resampled):
                target.mux(packet)
    for packet in stream.encode(None):
        target.mux(packet)
    target.close()
    out.seek(0)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--beam", type=int, default=1)
    parser.add_argument("--out", default=None)
    parser.add_argument("--webm-bitrate", type=int, default=0, help="first re-encode each clip as WebM/Opus at this bit rate (what a browser sends)")
    args = parser.parse_args()
    from faster_whisper import WhisperModel
    clips = select(args.n)
    folder = extract(clips)
    model_dir = (ROOT / args.model).resolve()
    started = time.monotonic()
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", cpu_threads=args.threads)
    load_s = time.monotonic() - started
    rows, errors, words = [], 0, 0
    for clip in clips:
        source = str(folder / clip["file"]) if not args.webm_bitrate else to_webm((folder / clip["file"]).read_bytes(), args.webm_bitrate)
        t0 = time.monotonic()
        segments, info = model.transcribe(source, language="vi", beam_size=args.beam, vad_filter=False,
                                          condition_on_previous_text=False)
        hypothesis = " ".join(s.text.strip() for s in segments)
        took = time.monotonic() - t0
        ref, hyp = normalise(clip["reference"]), normalise(hypothesis)
        e = edit_distance(ref, hyp)
        errors, words = errors + e, words + len(ref)
        rows.append({"sentence_id": clip["sentence_id"], "seconds": round(clip["seconds"], 2), "took": round(took, 2), "rtf": round(took / clip["seconds"], 3),
                     "errors": e, "words": len(ref), "reference": clip["reference"], "hypothesis": hypothesis})
    ratios = sorted(r["rtf"] for r in rows)
    report = {"model": model_dir.name, "clips": len(rows), "wer": round(errors / words, 4), "words": words,
              "rtf_p50": ratios[len(ratios) // 2], "rtf_p95": ratios[max(0, int(len(ratios) * 0.95) - 1)], "load_seconds": round(load_s, 1),
              "threads": args.threads, "beam": args.beam, "compute_type": "int8", "webm_opus_bitrate": args.webm_bitrate or None,
              "targets": {"wer_max": 0.20, "rtf_p95_max": 1.5},
              "evidence": "FLEURS vi_vn dev (human-read, human transcription), 100 different sentences by fixed seed; this machine's CPU"}
    out = Path(args.out) if args.out else ROOT / "evals/results/asr-20261126" / model_dir.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
