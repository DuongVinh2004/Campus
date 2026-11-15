#!/usr/bin/env bash
# Fetch the two Linux runtime components that are pinned by hash in the repository but not stored in it, and verify them:
#   - ONNX Runtime 1.30.0 (Microsoft release tarball), checked against the digest in infra/local/rag-fixture/onnx-linux-20261115/linux-release.json
#   - tokenizers 0.21.4 (PyPI wheel), every file of the package checked against infra/local/rag-fixture/tokenizers-linux-20261115.json
# Run as the service user (or root) from install.sh. A mismatch aborts: the model server refuses unverified bytes anyway.
set -euo pipefail
ROOT="${CAMPUS247_ROOT:-/opt/campus247}"
FIX="$ROOT/infra/local/rag-fixture"
ONNX_DIR="$FIX/onnx-linux-20261115"
mkdir -p "$ONNX_DIR/download"

read -r URL EXPECTED < <(python3 - <<PY
import json
r = json.load(open("$ONNX_DIR/linux-release.json"))
print(r["source"], r["tgz_sha256"])
PY
)
if [ ! -d "$ONNX_DIR/onnxruntime-linux-x64-1.30.0" ]; then
  curl -fsSL --retry 5 --retry-delay 3 --retry-connrefused -o "$ONNX_DIR/download/onnxruntime-linux-x64-1.30.0.tgz" "$URL"
  echo "$EXPECTED  $ONNX_DIR/download/onnxruntime-linux-x64-1.30.0.tgz" | sha256sum -c -
  tar -xzf "$ONNX_DIR/download/onnxruntime-linux-x64-1.30.0.tgz" -C "$ONNX_DIR"
fi

if [ ! -d "$FIX/tokenizers-linux-20261115/tokenizers" ]; then
  mkdir -p "$FIX/tokenizers-linux-20261115"
  "${CAMPUS247_UV:-/opt/uv/bin/uv}" pip install --python "${CAMPUS247_PYTHON:-$ROOT/.venv/bin/python}" --target "$FIX/tokenizers-linux-20261115" "tokenizers==0.21.4"
fi
python3 - <<PY
import hashlib, json, pathlib
site = pathlib.Path("$FIX/tokenizers-linux-20261115")
record = json.load(open("$FIX/tokenizers-linux-20261115.json"))
bad = [name for name, digest in record["hashes"].items() if hashlib.sha256((site / name).read_bytes()).hexdigest() != digest]
if bad:
    raise SystemExit(f"tokenizers files differ from the pinned hashes: {bad[:3]}")
print("runtime dependencies verified")
PY
