from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("campus247_worker")


@dataclass
class WorkerConfig:
    """Worker runtime configuration."""
    service_name: str = "campus247-worker"
    version: str = "0.1.0"
    poll_interval_seconds: float = 1.0
    running: bool = field(default=False, init=False)


class WorkerProcess:
    """Worker process managing outbox polling, event dispatching, and ingestion."""

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or WorkerConfig()

    def start(self) -> None:
        """Start worker loop."""
        self.config.running = True
        logger.info("Worker process %s (v%s) started", self.config.service_name, self.config.version)

    def stop(self) -> None:
        """Stop worker loop safely."""
        self.config.running = False
        logger.info("Worker process %s stopped", self.config.service_name)


def create_worker() -> WorkerProcess:
    """Factory creating worker process instance."""
    return WorkerProcess()


def main() -> None:
    """Run the durable knowledge queue against its explicitly configured local DB."""
    import asyncio
    import runpy
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    entrypoint = root / "scripts/knowledge_platform.py"
    if not entrypoint.is_file() or entrypoint.resolve().parent != root / "scripts":
        raise RuntimeError("Explicit knowledge worker composition missing")
    composition = runpy.run_path(str(entrypoint), run_name="knowledge_worker_composition")
    try:
        asyncio.run(composition["work"]())
    except KeyboardInterrupt:
        logger.info("Durable knowledge worker stopped; committed checkpoints retained")


if __name__ == "__main__":
    main()
