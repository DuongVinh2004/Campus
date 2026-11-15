"""Owned loopback BGE services, reusing signed local ONNX and existing resource guards."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "infra/local/rag-fixture"
sys.path[:0] = [str(ROOT / "services/api/src"), str(FIXTURE)]
PORTS = {18081: "embedding", 18082: "reranker"}
REVISIONS = {"embedding": "5617a9f61b028005a4858fdac845db406aefb181",
             "reranker": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"}


class LoopbackHTTPServer(HTTPServer):
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "localhost", self.server_address[1]

    def handle_error(self, request, client_address):
        # A disconnected client must not block a serving thread writing a
        # traceback into the controller's stderr pipe. Keep finite diagnostics
        # on stdout, which the controller continuously drains; never log input.
        kind = type(sys.exception()).__name__
        allowed = {"BrokenPipeError", "ConnectionAbortedError", "ConnectionResetError", "TimeoutError", "OSError"}
        print(json.dumps({"model_http_failure": {"port": self.server_port,
            "error_type": kind if kind in allowed else "MODEL_HTTP_BOUNDARY_FAILURE"}}), flush=True)


def peer_closed(connection) -> bool:
    """True when the client has already hung up (it gave up waiting): there is nobody left to answer.

    Requests queue behind one lock; a client that timed out closes its socket but the request stays queued, and the
    model would still run it. Under load that wasted work made the queue longer and caused more timeouts.
    Only peeks (nothing is consumed) and never raises."""
    import select
    import socket as _socket
    try:
        readable, _, _ = select.select([connection], [], [], 0)
        if not readable:
            return False
        return connection.recv(1, _socket.MSG_PEEK) == b""
    except (BlockingIOError, InterruptedError):
        return False
    except (OSError, ValueError):  # ValueError: the socket object is already closed
        return True


def checked(path: Path) -> Path:
    path = path.absolute()
    if path.resolve() == ROOT or not path.resolve().is_relative_to(ROOT):
        raise ValueError("path outside workspace")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()
                              or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse path denied")
        if parent == ROOT:
            break
    return path


def retain(state: Path, name: str, data: dict):
    with checked(state / (name + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def worker(state: Path, predecessor: Path | None = None, resource_authorization: Path | None = None,
           recover_stale_successor: bool = False, accounting_only: bool = False):
    state = checked(state)
    model_roots = [FIXTURE / "onnx-models-20261011-30", FIXTURE / "runtime-acquisition-20261004"]
    def protect(event, args):
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).absolute()
            if path.name == ".env" or path.name.startswith(".env.") or path.name == ".fixture-state.json":
                raise RuntimeError("credential read denied")
            mode, flags = args[1:3]
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if writing:
                checked(path)
                if any(path.resolve().is_relative_to(root.resolve()) for root in model_roots):
                    raise RuntimeError("model write denied")
                if not path.resolve().is_relative_to(state):
                    raise RuntimeError("write outside owned state denied")
        if event in {"os.remove", "os.rmdir", "shutil.rmtree"}:
            raise RuntimeError("deletion denied")
        if event in {"socket.connect", "socket.sendto"}:
            raise RuntimeError("outbound network denied")
        if event == "socket.bind" and args[1] not in {("127.0.0.1", p) for p in PORTS}:
            raise RuntimeError("unexpected bind denied")
        if event in {"socket.gethostbyname", "socket.gethostbyaddr"}:
            raise RuntimeError("DNS denied")
        if event == "socket.getaddrinfo" and args[0] != "127.0.0.1":
            raise RuntimeError("DNS denied")
    sys.addaudithook(protect)
    from m1_spin_policy_20261011_51 import CPU
    from m2_inference_20261012_74 import Session
    from onnx_capi_20261011_30 import digest
    from onnx_graph_20261011_30 import DEST
    from token_envelope_20261007_25 import TokenEnvelope
    envelope = TokenEnvelope()
    expected = {"model.onnx_data": "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4",
                "reranker.weights.safetensors": "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286"}
    for name, checksum in expected.items():
        if digest(DEST / name) != checksum:
            raise ValueError("model artifact mismatch")
    engine = CPU()
    sessions = {}
    lock = threading.Lock()
    counts = {"http": 0, "inference": 0, "tokens": 0}
    caps = {"http": 6000, "inference": 2000, "tokens": 750000}
    from model_usage_accounting import native_snapshot, accounting_continuation, exceeds
    if predecessor is not None:
        prior = checked(predecessor)
        last = native_snapshot(prior, checked)
        if last:
            if (not accounting_only and resource_authorization is None and last["caps"] != caps) or set(last["counts"]) != set(counts):
                raise ValueError("native ledger mismatch")
            counts.update(last["counts"])
        retain(state, "predecessor", {"path": str(prior), "retained_counts": dict(counts), "reset": False})
    if accounting_only:
        if predecessor is None or resource_authorization is not None or recover_stale_successor:
            raise ValueError("Accounting mode requires an exact retained predecessor")
        counts, caps = accounting_continuation(last)
        retain(state, "resource-transition", {"counts": dict(counts), "caps": caps, "reset": False,
            "human_request": "bỏ ngân sách mô hình đi, dùng bao nhiêu thì dùng",
            "authorized_on": "2026-10-23", "aggregate_limits": "removed",
            "per_request_and_physical_guards": "unchanged"})
    if resource_authorization is not None:
        from multi_agent_live_resources import AUTHORIZATION, NATIVE_STATE, NATIVE_PRIOR, load_authorization, native_transition, continue_native, recover_native_successor
        if checked(resource_authorization) != AUTHORIZATION or predecessor is None or last is None:
            raise ValueError("exact authorized native transition required")
        if recover_stale_successor:
            counts, caps, recovery = recover_native_successor(last, load_authorization(), state, checked(predecessor))
            retain(state, "stale-successor-recovery", recovery)
        elif state == NATIVE_STATE and checked(predecessor) == NATIVE_PRIOR:
            counts, caps = native_transition(last, load_authorization())
        else:
            counts, caps = continue_native(last, load_authorization(), state, predecessor)
        retain(state, "resource-transition", {"counts": counts, "caps": caps, "reset": False,
            "authorization": str(AUTHORIZATION), "http_prior_actual": None,
            "http_prior_conservative_envelope": 6000, "inference_tokens_exact": True})
    def reserve_http():
        counts["http"] += 1
        retain(state, f"http-{counts['http']:05d}-reservation", {"counts": dict(counts), "caps": caps,
            "before_dispatch": True, "input_logged": False})
    def reserve(kind, sequences):
        tokens = sum(map(len, sequences))
        if exceeds(counts["inference"] + 1, caps["inference"]) or exceeds(counts["tokens"] + tokens, caps["tokens"]):
            raise ValueError("native session cap reached")
        counts["inference"] += 1
        counts["tokens"] += tokens
        retain(state, f"native-{counts['inference']:05d}-reservation", {"kind": kind, "counts": dict(counts),
            "caps": caps, "before_inference": True, "input_logged": False})
        return counts["inference"]
    try:
        for kind, name in (("embedding", "model.onnx"), ("reranker", "reranker-logits.onnx")):
            sessions[kind] = Session(engine, DEST / name)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, code, value):
                data = json.dumps(value, allow_nan=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                with lock:
                    reserve_http()
                    if self.path != "/info" or exceeds(counts["http"], caps["http"]):
                        return self.respond(403, {"error": "REQUEST_DENIED"})
                    kind = PORTS[self.server.server_port]
                    self.respond(200, {"model_id": "BAAI/bge-m3" if kind == "embedding" else "BAAI/bge-reranker-v2-m3",
                        "model_sha": REVISIONS[kind], "model_type": {kind: {}}, "auto_truncate": False,
                        "usage_counts": dict(counts), "aggregate_caps": caps})

            def do_POST(self):
                with lock:
                    kind = PORTS[self.server.server_port]
                    reserve_http()
                    try:
                        if exceeds(counts["http"], caps["http"]) or self.headers.get("Transfer-Encoding"):
                            raise ValueError("request cap")
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 65536:
                            raise ValueError("request size")
                        self.connection.settimeout(5)
                        payload = json.loads(self.rfile.read(length))
                        if peer_closed(self.connection):
                            # The caller timed out while queued. No inference, no reservation, nothing to send.
                            retain(state, f"http-{counts['http']:05d}-abandoned", {"counts": dict(counts), "abandoned": True,
                                "before_inference": True, "input_logged": False})
                            return
                        if payload.get("truncate") is not False:
                            raise ValueError("truncation forbidden")
                        if kind == "embedding":
                            if self.path != "/embed" or set(payload) != {"inputs", "normalize", "truncate"} or payload["normalize"] is not True:
                                raise ValueError("invalid embedding request")
                            texts = payload["inputs"]
                            if not isinstance(texts, list) or len(texts) != 1 or not isinstance(texts[0], str):
                                raise ValueError("bounded embedding required")
                            sequences = [envelope.models[kind].encode(texts[0], add_special_tokens=True).ids]
                        else:
                            if self.path != "/rerank" or set(payload) != {"query", "texts", "raw_scores", "return_text", "truncate"}:
                                raise ValueError("invalid reranking request")
                            texts = payload["texts"]
                            if (not isinstance(texts, list) or not 1 <= len(texts) <= 20 or not isinstance(payload["query"], str)
                                    or payload["raw_scores"] is not True or payload["return_text"] is not False
                                    or any(not isinstance(text, str) for text in texts)):
                                raise ValueError("bounded reranking required")
                            sequences = [envelope.models[kind].encode(payload["query"], text, add_special_tokens=True).ids for text in texts]
                        if any(not 2 <= len(row) <= envelope.limit for row in sequences):
                            raise ValueError("token envelope exceeded")
                        values = []
                        # One sequence keeps each native call within the existing
                        # 3s guard under observed CPU load. All sequences still run
                        # and retain their reservations; nothing is truncated.
                        for offset in range(len(sequences)):
                            batch = sequences[offset:offset + 1]
                            ordinal = reserve(kind, batch)
                            result, elapsed = sessions[kind].run(batch, b"sentence_embedding" if kind == "embedding" else b"logits")
                            retain(state, f"native-{ordinal:05d}-result", {"kind": kind, "elapsed_ms": elapsed * 1000,
                                "actual_checkpoint_inference": True, "output_sha256": hashlib.sha256(json.dumps(result).encode()).hexdigest()})
                            values.extend(result)
                        self.respond(200, values if kind == "embedding" else
                            [{"index": i, "score": row[0]} for i, row in enumerate(values)])
                    except Exception as error:  # noqa: BLE001 -- safe HTTP boundary records no input/exception text
                        retain(state, f"http-{counts['http']:05d}-failure", {"error_type": type(error).__name__, "counts": dict(counts)})
                        self.respond(503, {"error": "MODEL_RUNTIME_UNAVAILABLE"})
        servers = [LoopbackHTTPServer(("127.0.0.1", port), Handler) for port in PORTS]
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        print(json.dumps({"ready": True, "ports": list(PORTS), "models": list(REVISIONS), "caps": caps}), flush=True)
        threading.Event().wait()
    finally:
        for session in sessions.values():
            session.close()
        engine.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--predecessor", type=Path)
    parser.add_argument("--resource-authorization", type=Path)
    parser.add_argument("--recover-stale-successor", action="store_true")
    parser.add_argument("--accounting-only", action="store_true", help="User-authorized removal of aggregate model limits; retains usage and per-request guards")
    args = parser.parse_args()
    state = checked(args.state)
    if args.worker:
        return worker(state, args.predecessor, args.resource_authorization, args.recover_stale_successor, args.accounting_only)
    if state.exists():
        raise ValueError("fresh owned model namespace required")
    state.mkdir(parents=True)
    from bounded_physical_process_20261011_30 import BoundedProcess
    env = {k: v for k, v in os.environ.items() if not any(part in k.upper() for part in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", TEMP=str(state), TMP=str(state))
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", "--state", str(state)]
    if args.predecessor:
        command += ["--predecessor", str(checked(args.predecessor))]
    if args.resource_authorization:
        command += ["--resource-authorization", str(checked(args.resource_authorization))]
    if args.recover_stale_successor:
        command += ["--recover-stale-successor"]
    if args.accounting_only:
        command += ["--accounting-only"]
    owned = BoundedProcess(command, cwd=ROOT, env=env)
    retain(state, "launch", {"owned_pid": owned.process.pid, "controls": owned.controls,
        "model_protection": "read_only", "outbound_network": "denied", "exact_binds": list(PORTS)})
    # Drain both pipes while the worker runs. Preserve fatal diagnostics in an
    # additive file rather than allowing a full stderr pipe to stall a server.
    def drain_stderr():
        with checked(state / "stderr.log").open("x", encoding="utf-8") as stream:
            for line in owned.process.stderr:
                stream.write(line)
                stream.flush()
    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()
    try:
        for line in owned.process.stdout:
            print(line.rstrip(), flush=True)
        code = owned.process.wait()
        stderr_thread.join(timeout=5)
        retain(state, "exit", {"exit_code": code, "stderr_preserved": "stderr.log",
            "stderr_drain_completed": not stderr_thread.is_alive()})
        raise SystemExit(code)
    finally:
        owned.close()


if __name__ == "__main__":
    main()
