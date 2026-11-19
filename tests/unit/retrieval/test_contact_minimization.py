"""Synthetic fixtures; no external calls. Contact values stay local for every approved source."""
import pytest

from campus247.agent.prompts.composer import PromptBlock, TrustDomain
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.contact_minimization import (
    evidence_contact_redactor,
    present_without_contact_markers,
)
from campus247.application.retrieval.prompt_evidence import compose_bounded_inputs, evidence_prompt_blocks
from campus247.infrastructure.llm.egress_policy import EgressPolicy, EgressViolationError

PHONE = "0900000001"
EMAIL = "ktx-contact@huce.edu.vn"
TEXT = (f"Sinh viên đăng ký ở ký túc xá tại Ban quản lý KTX, điện thoại {PHONE}, email {EMAIL}. "
        "Mức thu 580.500 đồng/tín chỉ theo Quyết định 924/QĐ-ĐHXDHN.")
QUESTION = "Sinh viên muốn đăng ký ở ký túc xá thì làm thế nào?"


def row(text=TEXT):
    return {"source_id": "s", "document_version_id": "v", "release_id": "r", "content_text": text,
            "title": "Sổ tay sinh viên (synthetic)", "section_path": "Ký túc xá",
            "canonical_uri": "https://huce.edu.vn/synthetic.pdf", "simulation_label": False}


def validate(text):
    return EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", "model": "synthetic",
                                                 "messages": [{"role": "user", "content": text}]})


@pytest.mark.parametrize("semantic", [False, True])
def test_unpinned_source_contacts_never_reach_the_model_view(semantic):
    bundle = CitationBundle.build([row()])
    text = "\n".join(b.content for b in evidence_prompt_blocks(bundle, query=QUESTION, semantic=semantic))
    assert PHONE not in text and EMAIL not in text
    assert "PUBLIC_CONTACT_PHONE_" in text and "PUBLIC_CONTACT_EMAIL_" in text
    assert "580.500" in text and "924/QĐ-ĐHXDHN" in text
    validate(text)
    assert bundle.resolve("CIT-001").content_text == TEXT


def test_raw_source_and_user_contacts_still_hit_the_unchanged_denial_boundary():
    with pytest.raises(EgressViolationError):
        validate(TEXT)
    bundle = CitationBundle.build([row()])
    blocks = evidence_prompt_blocks(bundle, query=QUESTION)
    blocks.append(PromptBlock(TrustDomain.USER_INPUT, "Số của em là 0912345678, gọi em nhé"))
    _, inputs = compose_bounded_inputs(blocks)
    with pytest.raises(EgressViolationError):
        validate("\n".join(x["content"] for x in inputs))


def test_source_without_contacts_is_unchanged():
    plain = "Sinh viên nộp hồ sơ tại phòng Đào tạo trong 5 ngày làm việc."
    bundle = CitationBundle.build([row(plain)])
    assert evidence_contact_redactor(bundle)(plain) == plain


def test_markers_are_replaced_by_a_pointer_to_the_original_document():
    shown = present_without_contact_markers("Liên hệ PUBLIC_CONTACT_PHONE_A hoặc PUBLIC_CONTACT_EMAIL_B.")
    assert "PUBLIC_CONTACT" not in shown and "tài liệu gốc" in shown
