from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Requirement(StrictRecord):
    id: StrictStr = Field(pattern=r"^R[1-9][0-9]?$", max_length=3)
    question: StrictStr = Field(min_length=1, max_length=500)


class CoverageItem(StrictRecord):
    id: StrictStr = Field(pattern=r"^Q[1-4]$")
    question: StrictStr = Field(min_length=1, max_length=700)
    requirements: list[Requirement] = Field(min_length=1, max_length=4)


class InitialPlan(StrictRecord):
    items: list[CoverageItem] = Field(min_length=1, max_length=4)
    query: StrictStr = Field(min_length=1, max_length=700)
    clarification: StrictStr | None = Field(default=None, min_length=1, max_length=500)


class Support(StrictRecord):
    requirement_id: StrictStr = Field(pattern=r"^R[1-9][0-9]?$")
    evidence_id: StrictStr = Field(min_length=1, max_length=64)
    quote: StrictStr = Field(min_length=8, max_length=700)


class CoverageFinding(StrictRecord):
    item_id: StrictStr = Field(pattern=r"^Q[1-4]$")
    status: Literal["supported", "missing_user_fact", "missing_source", "conflicting", "out_of_scope"]
    supports: list[Support] = Field(max_length=16)


class Decision(StrictRecord):
    action: Literal["search", "read", "clarify", "answer", "handover"]
    coverage: list[CoverageFinding] = Field(min_length=1, max_length=4)
    query: StrictStr | None = Field(default=None, min_length=1, max_length=700)
    evidence_ids: list[StrictStr] = Field(default_factory=list, max_length=6)
    clarification: StrictStr | None = Field(default=None, min_length=1, max_length=500)


@dataclass(frozen=True)
class SingleAgentPolicy:
    """An additive per-run profile. Underlying paid/native ceilings still apply.

    Reservations include safety/intent, planner, generation, repair and verifier.
    Failed/uncertain model dispatches retain their conservative token reservation.
    """
    version: str = "single-agent-v1"
    max_steps: int = 4
    max_model_calls: int = 7
    max_searches: int = 3
    max_tool_calls: int = 15
    max_candidates: int = 12
    max_evidence: int = 6
    max_context_bytes: int = 15000
    max_reserved_tokens: int = 90000
    max_no_progress: int = 2
    deadline_seconds: float = 30.0
    model_timeout_ms: int = 5000
    tool_timeout_ms: int = 12000

    def __post_init__(self):
        ceilings = {"max_steps": 4, "max_model_calls": 7, "max_searches": 3,
                    "max_tool_calls": 15, "max_candidates": 12, "max_evidence": 6,
                    "max_context_bytes": 15000, "max_reserved_tokens": 90000,
                    "max_no_progress": 2, "model_timeout_ms": 5000, "tool_timeout_ms": 12000}
        if self.version != "single-agent-v1":
            raise ValueError("unsupported agent profile")
        for name, cap in ceilings.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= cap:
                raise ValueError("agent ceiling exceeded")
        if type(self.deadline_seconds) not in {float, int} or not 0 < self.deadline_seconds <= 30:
            raise ValueError("invalid run deadline")

    @property
    def fingerprint(self):
        return digest(asdict(self))


def digest(value):
    encoded = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()
