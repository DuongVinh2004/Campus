"""Stage6 synthetic runtime; no Gateway, no ledger, same business database."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from identities import generate_identities

from campus247.application.document_request.service_requests import (
    ServiceAgentTools,
    ServiceRequestService,
)
from campus247.application.knowledge.operations import KnowledgeOperations, digest
from campus247.bootstrap.certificate_demo import create_certificate_demo_app
from campus247.bootstrap.settings import Settings
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.service_request import SourceInput, VersionInput
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.repositories.sqlite_service_operations import (
    SQLiteServiceOperationsRepository,
)
from campus247.presentation.service_operations import create_service_operations_router


def initialize_demo(repository, knowledge, settings, directory):
    with repository.transaction() as tx:
        if tx.item("initialization", "stage6-demo-v1"):
            return
    students = [r["user_id"] for r in directory["student_profile"][:2]]
    courses = []
    # Simulated deadlines are relative to initialization: fixed dates expired on 2026-11-01 and turned the demo
    # (and its tests) into "deadline passed" for every course.
    seeded = datetime.now(UTC).replace(microsecond=0)
    open_until, closed_at = (seeded + timedelta(days=30)).isoformat(), (seeded - timedelta(days=30)).isoformat()
    for index, owner in enumerate(students):
        for code, eligible, deadline, exam in (
            ("CS101", True, open_until, "WRITTEN"),
            ("CS102", False, open_until, "ORAL"),
            ("CS103", True, closed_at, "WRITTEN"),
            ("CS104", None, None, "WRITTEN"),
        ):
            courses.append({"id": f"demo-student{index+1}-{code}", "owner": owner, "course_code": code,
                "semester": "2026-DEMO-1", "exam_type": exam, "eligible": eligible, "deadline": deadline,
                "score": "6.0 (mô phỏng)", "version": 1, "fixture_id": "stage6-courses-v1",
                "source_locator": "stage6-courses-v1 / " + code, "is_simulation": True})
    content = json.dumps({"simulation": True, "real_deadline": "unknown", "real_fee": "unknown", "courses": courses}, ensure_ascii=False, sort_keys=True)
    # Retained immutable dataset, not a grant or fabricated school record.
    with repository.transaction() as tx:
        if not tx.item("fixture", "stage6-courses-v1"):
            tx.insert("fixture", {"id": "stage6-courses-v1", "content": content, "sha256": digest(content.encode()), "locator": "server-generated synthetic fixture v1"})
            for course in courses:
                tx.insert("course", course)
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment="development", tenant_id="huce-local-public")
    admins = list(dict.fromkeys(r["user_id"] for r in directory["role_binding"] if r["role"] == "KNOWLEDGE_ADMIN"))
    editor, reviewer = [adapter.resolve_token(adapter.mint_token(uid)) for uid in admins[:2]]
    for kind, text in (
        ("GRADE_APPEAL", "MÔ PHỎNG: phúc khảo học phần thi viết thuộc student hiện tại; hạn và eligibility lấy từ fixture stage6-courses-v1. Chọn học phần, nhập lý do, xem trước và xác nhận gửi đến queue ACADEMIC_SERVICES. Cán bộ yêu cầu bổ sung và trả kết luận demo; AI không chấm điểm. Phí, hạn và mẫu chính thức HUCE chưa được xác minh."),
        ("GENERAL_SUPPORT", "MÔ PHỎNG: chia sẻ câu hỏi, lý do và phần chưa giải quyết theo lựa chọn của sinh viên; không chuyển toàn bộ transcript. Xem trước, xác nhận rồi tạo queue record HUCE_GENERAL. Chỉ cán bộ được cấp quyền tiếp nhận, chuyển, trả lời và giải quyết. Không hứa SLA hoặc nhân sự trực."),
    ):
        with repository.transaction() as tx:
            if tx.item("knowledge_active", kind):
                continue  # Keep any already committed publication or withdrawal on recovery.
        source = knowledge.upload(editor, SourceInput(title="Hướng dẫn demo " + kind, filename=kind.lower() + ".txt",
            content=text, locator="Campus 24/7 stage6 synthetic configuration v1"))
        version = knowledge.create_version(editor, VersionInput(source_id=source["id"], procedure=kind,
            text=text, mapping="ORIGINAL_TEXT", effective_from=datetime(2026, 10, 13, tzinfo=UTC)))
        version = knowledge.review(reviewer, version["id"], version["revision"], "approved", "Bootstrap development review of synthetic text; not independent human/institutional approval")
        version = knowledge.build(reviewer, version["id"], version["revision"])
        preview = knowledge.preview(reviewer, version["id"], version["revision"])
        knowledge.publish(reviewer, version["id"], preview["preview_id"], preview["confirmation_token"], "stage6-bootstrap:" + kind, True)
    with repository.transaction() as tx:
        tx.insert("initialization", {"id": "stage6-demo-v1", "complete": True,
            "review_kind": "Codex authored synthetic bootstrap, not independent human review"})


def create_service_demo_app(database, *, settings=None, frontend_port=None, rag_transport=None, initialize=True):
    settings = settings or Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    app = create_certificate_demo_app(database, settings=settings, frontend_port=frontend_port,
                                      rag_transport=rag_transport, service_operations=True)
    repository = SQLiteServiceOperationsRepository(database)
    base = app.state.certificate_service
    directory = generate_identities()["records"]
    users = {r["id"]: r for r in directory["user_identity"]}
    staff_directory = {r["user_id"]: {"display_name": users[r["user_id"]]["display_name"], "queues": [r["scope_key"]]}
        for r in directory["role_binding"] if r["role"] == "SUPPORT_OFFICER"}
    tokens = ConfirmationTokenService(settings.CONFIRMATION_SIGNING_KEY)
    knowledge = KnowledgeOperations(repository, base.authorize, tokens)
    service = ServiceRequestService(repository, tokens, base.profile_reader, staff_directory, knowledge)
    if initialize:
        initialize_demo(repository, knowledge, settings, directory)
    app.include_router(create_service_operations_router(service, knowledge))
    # Keep API routes ahead of the frontend catch-all inherited from the shell.
    app.router.routes.sort(key=lambda route: getattr(route, "path", "") == "/{page_path:path}")
    app.state.service_requests, app.state.knowledge_operations = service, knowledge
    app.state.service_agent_tools = ServiceAgentTools(service)
    from campus247.presentation.middleware.abuse_limits import (
        AbuseLimiterMiddleware,
        InMemoryRateLimiterStore,
        RateLimitRule,
    )
    app.add_middleware(AbuseLimiterMiddleware, store=InMemoryRateLimiterStore(), rules=[
        RateLimitRule(path_prefix="/v1/service", max_requests=120, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/knowledge-operations", max_requests=120, window_seconds=60, fail_closed=True),
    ])
    app.state.owns_paid_ledger = False
    return app
