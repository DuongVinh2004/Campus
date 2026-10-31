"""A bounded, allowlisted trace: no text, identifiers, exception strings or PII."""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field

from campus247.rag_v2.verification.deterministic import REASON_CODES

STAGES = ("understanding", "facts", "retrieval", "rerank", "generation",
          "deterministic", "semantic", "verification", "outcome", "total")
KINDS = frozenset({"answer", "partial", "clarify", "refuse", "transient_error"})


@dataclass
class TurnTrace:
    candidate_count: int = 0
    rerank_scores: list[float] = field(default_factory=list)
    statement_rejections: dict[int, tuple[str, ...]] = field(default_factory=dict)
    outcome_kind: str | None = None
    latency_ms: dict[str, float] = field(default_factory=dict)

    def payload(self) -> dict:
        return {
            "candidate_count": min(max(self.candidate_count, 0), 1_000_000)
                if type(self.candidate_count) is int else 0,
            "rerank_scores": [round(max(-1_000_000, min(score, 1_000_000)), 4)
                              for score in self.rerank_scores[:60]
                              if type(score) in (int, float) and math.isfinite(score)],
            "statement_rejections": [
                {"i": index, "reasons": sorted({reason for reason in reasons
                                               if reason in REASON_CODES})}
                for index, reasons in list(self.statement_rejections.items())[:32]
                if type(index) is int and 0 <= index < 32],
            "outcome_kind": self.outcome_kind if self.outcome_kind in KINDS else None,
            "latency_ms": {stage: round(min(max(self.latency_ms[stage], 0), 3_600_000), 3)
                           for stage in STAGES if stage in self.latency_ms
                           and type(self.latency_ms[stage]) in (int, float)
                           and math.isfinite(self.latency_ms[stage])},
        }


def emit(trace: TurnTrace) -> None:
    logging.getLogger("campus247.rag_v2").warning(
        "rag_v2_trace %s", json.dumps(trace.payload(), ensure_ascii=True, separators=(",", ":"), allow_nan=False))
