# Local speech recognizer (F8.4)

- Runtime: an isolated venv at `.tooling/asr-20261126/.venv` (Python 3.12), packages pinned in `requirements.lock.txt`
  (installed from PyPI on 2026-11-26; `av` is held at 13.1.0 because faster-whisper 1.1.1 passes `metadata_errors`, which
  PyAV 14+ removed; `requests` is added because faster-whisper 1.1.1 imports it).
- Model: `Systran/faster-whisper-small` at revision `536b0662742c02347bc0e980a01041f333bce120` (MIT), files in
  `.tooling/asr-20261126/models/faster-whisper-small`; `model.bin` SHA-256
  `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` (equals the Hugging Face LFS hash; checked again by
  `scripts/serve_asr.py` before loading).
- Test set (D6b): FLEURS vi_vn dev from `huggingface.co/datasets/google/fleurs` (CC-BY 4.0), `dev.tar.gz` SHA-256
  `8821a394c99069409b3ce7bb5cd14b10b709f2ee2fea16f42b4701e1cc9ef673`; 100 sentences chosen by `evals/runners/asr_eval.py`.
- Run: `.tooling/asr-20261126/.venv/Scripts/python.exe -B scripts/serve_asr.py serve --port 18083` (loopback only; RAM gate
  asr_mb + 500 MB from `infra/profiles/<profile>.toml`; lazy load, unloaded after 10 idle minutes).
