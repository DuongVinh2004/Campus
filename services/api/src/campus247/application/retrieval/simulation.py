"""Render provenance disclosure from validated server citation metadata."""
from collections.abc import Sequence

SIMULATION_NOTICE = "Dữ liệu mô phỏng; không phải quy định chính thức."


def label_grounded_answer(text: str, *, cited_statuses: Sequence[str]) -> str:
    if any(status == "SYNTHETIC" for status in cited_statuses) and not text.startswith(SIMULATION_NOTICE):
        return SIMULATION_NOTICE + "\n" + text
    return text
