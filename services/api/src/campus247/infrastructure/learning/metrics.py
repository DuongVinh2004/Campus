"""Emit bounded learning measurements (the function lives in the application layer so every layer can use it)."""
from campus247.application.learning.telemetry import logger, record

__all__ = ["logger", "record"]
