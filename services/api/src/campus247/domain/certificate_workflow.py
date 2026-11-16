"""Local certificate template rules; public guidance does not prove eligibility."""
from datetime import datetime
from campus247.domain.service_workflow import (
    COMMON_REVIEWS, EFFECTIVE_FROM, OutcomeTemplate, ReviewCriterion, ServiceWorkflow, workflow_at,
)

CERTIFICATE_WORKFLOWS = (
    ServiceWorkflow("STUDENT_CERTIFICATE", "certificate-workflow-demo-v1", "HUCE_GENERAL", EFFECTIVE_FROM, None,
        ("purpose", "recipient", "quantity", "delivery_method"), COMMON_REVIEWS + (
            ReviewCriterion("student_profile", "Đối chiếu danh tính và tình trạng sinh viên"),
            ReviewCriterion("purpose_recipient", "Đối chiếu mục đích và nơi nhận được người dùng khai báo"),
            ReviewCriterion("issuance_authority", "Xác minh mẫu, điều kiện cấp và thẩm quyền hiện hành trước việc cấp giấy thật"),),
        OutcomeTemplate("certificate-outcome-demo-v1", "Giấy xác nhận sinh viên",
                        ("student_code", "display_name", "program_code", "purpose", "recipient", "issued_at"),
                        ("APPROVED", "REJECTED"))),
)


def certificate_workflow(record):
    anchor = record.get("submitted_at") or record.get("created_at")
    return workflow_at(record["document_type"], datetime.fromisoformat(anchor), CERTIFICATE_WORKFLOWS)
