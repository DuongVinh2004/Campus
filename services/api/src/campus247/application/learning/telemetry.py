"""Emit bounded learning measurements without actor, file or content identifiers."""
import json
import logging

logger = logging.getLogger("campus247.learning.metrics")


def record(metric: str, **measurements: int | str) -> None:
    if logger.isEnabledFor(logging.INFO):
        logger.info("%s", json.dumps({"metric": metric, **measurements}, separators=(",", ":")))
