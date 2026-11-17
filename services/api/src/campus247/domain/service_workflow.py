"""Versioned synthetic service definitions, shared by projections and validation.

These are local application rules, never institutional policy or proof of an
officer's review. Selection is explicit and fails on gaps or ambiguity.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType


@dataclass(frozen=True)
class ReviewCriterion:
    id: str
    label: str
    reviewer: str = "SUPPORT_OFFICER"
    required: bool = True


@dataclass(frozen=True)
class OutcomeTemplate:
    version: str
    title: str
    required_fields: tuple[str, ...]
    outcomes: tuple[str, ...]


@dataclass(frozen=True)
class ServiceWorkflow:
    kind: str
    version: str
    queue: str
    effective_from: datetime
    effective_until: datetime | None
    required_form_fields: tuple[str, ...]
    mandatory_reviews: tuple[ReviewCriterion, ...]
    template: OutcomeTemplate
    classification: str = "synthetic"
    applicability_milestone: str = "submitted_at_or_created_at"


EFFECTIVE_FROM = datetime(2026, 10, 13, tzinfo=timezone.utc)
TEMPLATE_VERSION = "service-outcome-demo-v1"
COMMON_REVIEWS = (
    ReviewCriterion("scope_assignment", "Đối chiếu đúng hồ sơ, hàng đợi và người phụ trách"),
    ReviewCriterion("source_applicability", "Đối chiếu nguồn và phiên bản áp dụng cho hồ sơ"),
    ReviewCriterion("evidence_review", "Đọc và đối chiếu bằng chứng liên quan"),
    ReviewCriterion("decision_reason", "Cán bộ xác định kết luận và lý do xử lý"),
)
WORKFLOWS = (
    ServiceWorkflow("GRADE_APPEAL", "service-workflow-demo-v1", "ACADEMIC_SERVICES", EFFECTIVE_FROM, None,
        ("course_record_id", "reason"), COMMON_REVIEWS + (
            ReviewCriterion("course_eligibility", "Đối chiếu học phần, dữ liệu điều kiện và hạn mô phỏng"),
            ReviewCriterion("academic_review", "Cán bộ thực hiện đối chiếu chuyên môn; AI không quyết định điểm"),),
        OutcomeTemplate(TEMPLATE_VERSION, "Kết quả phúc khảo mô phỏng", ("request_id", "student", "outcome", "reason"),
                        ("UNCHANGED", "CORRECTED", "UNABLE_TO_REVIEW", "REJECTED"))),
    ServiceWorkflow("GENERAL_SUPPORT", "service-workflow-demo-v1", "HUCE_GENERAL", EFFECTIVE_FROM, None,
        ("reason",), COMMON_REVIEWS,
        OutcomeTemplate(TEMPLATE_VERSION, "Kết quả hỗ trợ mô phỏng", ("request_id", "student", "outcome", "reason"),
                        ("RESPONDED", "REJECTED"))),
)


def workflow_at(kind, at, definitions=WORKFLOWS):
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("WORKFLOW_MILESTONE_UNRESOLVED")
    matches = [definition for definition in definitions if definition.kind == kind
               and definition.effective_from <= at
               and (definition.effective_until is None or at < definition.effective_until)]
    if len(matches) != 1:
        raise ValueError("WORKFLOW_VERSION_UNRESOLVED")
    return matches[0]


def record_workflow(record):
    anchor = record.get("submitted_at") or record.get("created_at")
    return workflow_at(record["document_type"], datetime.fromisoformat(anchor))


# Immutable common state rules preserve the existing service transitions.
TRANSITIONS = MappingProxyType({
    "claim": (frozenset({"SUBMITTED"}), "VALIDATING"),
    "assign": (frozenset({"SUBMITTED", "VALIDATING", "PROCESSING"}), "VALIDATING"),
    "transfer": (frozenset({"SUBMITTED", "VALIDATING", "PROCESSING", "WAITING_STUDENT"}), None),
    "respond": (frozenset({"VALIDATING", "PROCESSING"}), "PROCESSING"),
    "request_information": (frozenset({"VALIDATING", "PROCESSING"}), "WAITING_STUDENT"),
    "resolve": (frozenset({"VALIDATING", "PROCESSING"}), "READY"),
    "reject": (frozenset({"VALIDATING", "PROCESSING"}), "REJECTED"),
    "supplement": (frozenset({"WAITING_STUDENT"}), "VALIDATING"),
})


def staff_transition(status, action):
    rule = TRANSITIONS.get(action)
    if rule is None or status not in rule[0]:
        raise ValueError("INVALID_STATE")
    return rule[1] or status
