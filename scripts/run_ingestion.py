from __future__ import annotations

import asyncio
import os
from pathlib import Path

# Ensure path resolution
ROOT = Path(__file__).resolve().parents[1]


def load_database_url() -> str:
    """Load DATABASE_URL from .env file or environment."""
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("DATABASE_URL="):
                val = line.split("=", 1)[1].strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                return val
    return os.getenv("DATABASE_URL", "postgresql://campus247:campus247_local_dev@localhost:5433/campus247_local")


def normalize_asyncpg_url(url: str) -> str:
    """Convert SQLAlchemy async URL to standard asyncpg connection URL."""
    prefix = "postgresql+asyncpg://"
    if url.startswith(prefix):
        return "postgresql://" + url[len(prefix):]
    return url


async def run_ingestion() -> int:
    # Re-enable only with approved adapter/manifest wiring and a versioned,
    # non-destructive ingestion path. Never overwrite active data with a fake.
    raise RuntimeError("ingestion requires an approved embedding adapter and verified active manifest")


def main() -> None:
    asyncio.run(run_ingestion())


if __name__ == "__main__":
    main()
