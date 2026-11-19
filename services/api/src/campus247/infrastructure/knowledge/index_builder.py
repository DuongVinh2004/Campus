"""Builds a candidate RAG v2 index by running scripts/refresh_rag_v2_index.py (existing tools, unchanged settings)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


class SubprocessIndexBuilder:
    def __init__(self, root: Path, *, timeout_seconds: int = 1500, python: str | None = None):
        self.root, self.timeout, self.python = Path(root), timeout_seconds, python or sys.executable

    async def build(self, base, *, tag: str) -> dict:
        environment = {**os.environ, "PYTHONPATH": os.pathsep.join(["data/rag_v2_vendor", "services/api/src", "."])}
        process = await asyncio.create_subprocess_exec(
            self.python, "-B", "-X", "utf8", "scripts/refresh_rag_v2_index.py", "--base", str(base), "--tag", tag, "--json",
            cwd=self.root, env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(process.communicate(), self.timeout)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("index build timed out") from None
        if process.returncode:
            raise RuntimeError("index build failed: " + (err or out).decode("utf-8", "replace")[-300:])
        lines = [line for line in out.decode("utf-8", "replace").splitlines() if line.strip()]
        result = json.loads(lines[-1])
        if not result.get("candidate_index") or result.get("embedding_status") != "complete":
            raise RuntimeError("index build produced no complete index")
        return result
