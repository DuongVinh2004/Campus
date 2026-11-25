"""Feature registry (F0.1): the one list of every product feature and the entry points it owns.

Pure domain code: no I/O and no environment access. Values come from `resolution` + the service; this module only declares
what a feature is, what it depends on, and which API paths, pages, jobs and agent tools belong to it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
FORBIDDEN_NAME_PARTS = ("confirm", "auth", "verify")  # a switch must never weaken a safety check (README §2, F0 §6)
AREAS = {"core", "chat", "assistant", "services", "campus", "learning", "knowledge", "admin", "web", "ai",
         "announcements", "policy", "agent", "proactive", "input", "output", "identity", "notifications", "tickets",
         "rooms", "schedule", "reminders", "ops"}


@dataclass(frozen=True)
class FeatureDefinition:
    key: str
    title: str
    description: str
    area: str
    kind: str = "module"  # module | job | ai | ops | ui
    default: bool = True
    locked: bool = False
    startup_wired: bool = False
    depends_on: tuple[str, ...] = ()
    api_prefixes: tuple[str, ...] = ()
    api_patterns: tuple[str, ...] = ()
    pages: tuple[str, ...] = ()
    nav_keys: tuple[str, ...] = ()
    jobs: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    client_visible: bool = True
    capability: str | None = None
    capability_scope: str = "write"
    env_alias: str | None = None
    variants: tuple[str, ...] = ()
    cost: str = "none"
    default_value: str | None = None  # variant default when `variants` is set


def _f(key, title, area, *, kind="module", default=True, **kw) -> FeatureDefinition:
    return FeatureDefinition(key=key, title=title, description=kw.pop("description", title), area=area, kind=kind, default=default, **kw)


def _learning(key, title, *patterns, **kw) -> FeatureDefinition:
    return _f(key, title, "learning", depends_on=kw.pop("depends_on", ("learning.core",)), api_patterns=patterns, **kw)


_LRN = "/v1/learning"
FEATURES: tuple[FeatureDefinition, ...] = (
    # ---- locked core
    _f("core.auth", "Đăng nhập và phiên", "core", locked=True, api_prefixes=("/v1/auth/logout", "/v1/users/me", "/v1/knowledge/platform/session"), pages=("login",), client_visible=False),
    _f("core.health", "Kiểm tra sức khỏe", "core", locked=True, api_prefixes=("/health",), client_visible=False),
    _f("core.privacy", "Quyền riêng tư", "core", locked=True, api_prefixes=("/v1/privacy/",), pages=("privacy",), nav_keys=("privacy",), client_visible=False),
    _f("core.features", "Quản trị cờ tính năng", "core", locked=True, api_prefixes=("/v1/features", "/v1/admin/features"), pages=("admin/features",), client_visible=False),
    _f("core.home", "Trang chủ và offline", "core", locked=True, pages=("", "offline"), nav_keys=("home",), client_visible=False),
    # ---- chat and assistant
    _f("chat.assistant", "Trợ lý học vụ (chat)", "chat", api_prefixes=("/v1/conversations",), pages=("chat",), nav_keys=("chat",), capability="chat_generation", cost="model_calls"),
    _f("chat.history", "Lịch sử hội thoại", "chat", depends_on=("chat.assistant",), api_prefixes=("/v1/assistant/conversations",)),
    _f("chat.feedback", "Đánh giá câu trả lời", "chat", depends_on=("chat.assistant",), api_patterns=(r"^/v1/conversations/[^/]+/messages/[^/]+/feedback(/.*)?$",)),
    _f("chat.gap_report", "Báo thiếu thông tin", "chat", depends_on=("chat.assistant",), api_prefixes=("/v1/answer-gap-reports",)),
    _f("chat.parallel_classify", "Phân loại song song", "chat", depends_on=("chat.assistant",), client_visible=False, env_alias="CAMPUS247_PARALLEL_CLASSIFY"),
    _f("chat.answer_cache", "Bộ nhớ đệm câu trả lời", "chat", default=False, depends_on=("chat.assistant",), client_visible=False, env_alias="CAMPUS247_RAG_ANSWER_CACHE"),
    _f("chat.verbatim_skip", "Bỏ qua kiểm ngữ nghĩa khi trích nguyên văn", "chat", depends_on=("chat.assistant",), client_visible=False,
       env_alias="CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", variants=("off", "shadow", "on"), default_value="off"),
    _f("assistant.personalization", "Cá nhân hóa trợ lý", "assistant", depends_on=("chat.assistant",),
       api_prefixes=("/v1/assistant/preferences", "/v1/assistant/chats", "/v1/assistant/consent", "/v1/assistant/consents", "/v1/assistant/context", "/v1/assistant/consumer-capabilities")),
    _f("assistant.memory", "Bộ nhớ trợ lý", "assistant", depends_on=("assistant.personalization",), api_prefixes=("/v1/assistant/memory",), pages=("memory",)),
    _f("assistant.tracking", "Theo dõi việc", "assistant", depends_on=("assistant.personalization",), api_prefixes=("/v1/assistant/tracking",)),
    _f("assistant.grants", "Cấp quyền dữ liệu cho trợ lý", "assistant", depends_on=("assistant.personalization",),
       api_prefixes=("/v1/assistant/grants", "/v1/assistant/resources:read", "/v1/assistant/resource-runs")),
    _f("assistant.legacy_import", "Nhập dữ liệu cũ", "assistant", depends_on=("assistant.personalization",), api_prefixes=("/v1/assistant/legacy-imports",)),
    _f("assistant.baseline", "Đường cơ sở trợ lý", "assistant", api_prefixes=("/v1/assistant/baseline", "/v1/assistant/contracts")),
    # ---- services and tickets
    _f("services.preparations", "Soạn thủ tục sinh viên", "services", capability="ticket_create",
       api_prefixes=("/v1/student-preparations", "/v1/assistant/student-actions", "/v1/assistant/student:", "/v1/assistant/proposals:prepare",
                     "/v1/assistant/surface:resolve", "/v1/assistant/receipts"), pages=("services",), nav_keys=("services",)),
    _f("services.case_workflow", "Quy trình hồ sơ cán bộ", "services",
       api_prefixes=("/v1/assistant/cases", "/v1/assistant/workflows", "/v1/assistant/staff-workspace", "/v1/assistant/staff-drafts")),
    _f("tickets.student", "Phiếu hỗ trợ của sinh viên", "tickets", capability="ticket_create", api_prefixes=("/v1/tickets",), pages=("tickets",), nav_keys=("tickets",)),
    _f("tickets.staff_queue", "Hàng đợi phiếu của cán bộ", "tickets", api_prefixes=("/v1/staff/tickets",), pages=("staff",), nav_keys=("staff",)),
    # ---- campus
    _f("rooms.booking", "Đặt phòng", "rooms", capability="room_booking", api_prefixes=("/v1/rooms",), pages=("rooms",), nav_keys=("rooms",)),
    _f("schedule.personal", "Thời khóa biểu cá nhân", "schedule", api_prefixes=("/v1/students/me/schedule",), pages=("schedule",), nav_keys=("schedule",)),
    _f("schedule.ics", "Xuất lịch ICS", "schedule", depends_on=("schedule.personal",), api_prefixes=("/v1/students/me/schedule.ics",)),
    _f("notifications.inbox", "Hộp thư thông báo", "notifications", api_prefixes=("/v1/notifications",), pages=("notifications",), nav_keys=("notifications",)),
    _f("reminders.exam", "Nhắc lịch thi", "reminders", kind="job", depends_on=("notifications.inbox", "schedule.personal"), jobs=("exam_reminders",)),
    # ---- learning
    _f("learning.core", "Học liệu", "learning", startup_wired=True, env_alias="CAMPUS_LEARNING_ENABLED", api_prefixes=(_LRN,), pages=("learning",), nav_keys=("learning",)),
    _learning("learning.upload_ocr", "Tải lên và OCR học liệu", rf"^{_LRN}/materials/[^/]+/upload-intents$", rf"^{_LRN}/upload-intents/.*$", rf"^{_LRN}/(ocr-jobs|ocr-releases)/.*$",
              rf"^{_LRN}/versions/[^/]+/ocr-jobs$", jobs=("learning_worker",)),
    _learning("learning.accessible_text", "Văn bản dễ tiếp cận", rf"^{_LRN}/reading-instructions/.*$", rf"^{_LRN}/versions/[^/]+/accessible-text.*$",
              rf"^{_LRN}/sessions/[^/]+/reading-instructions$", jobs=("accessible_text",)),
    _learning("learning.exit_tickets", "Phiếu ra lớp", rf"^{_LRN}/exit-tickets/.*$", rf"^{_LRN}/sessions/[^/]+/exit-tickets$"),
    _f("learning.exit_reminders", "Nhắc phiếu ra lớp", "learning", kind="job", depends_on=("learning.exit_tickets", "notifications.inbox"), jobs=("exit_ticket_reminders",)),
    _learning("learning.idea_cards", "Thẻ ý tưởng", rf"^{_LRN}/me/idea-.*$", rf"^{_LRN}/shared-idea-cards.*$"),
    _learning("learning.practice", "Ôn tập", rf"^{_LRN}/practice-(sets|items)/.*$", rf"^{_LRN}/sessions/[^/]+/practice-sets$"),
    _learning("learning.discussion", "Thảo luận", rf"^{_LRN}/(questions|replies)/.*$", rf"^{_LRN}/versions/[^/]+/questions$"),
    _learning("learning.page_feedback", "Phản hồi theo trang", rf"^{_LRN}/me/page-feedback.*$", rf"^{_LRN}/versions/[^/]+/pages/[^/]+/me/feedback$",
              rf"^{_LRN}/sessions/[^/]+/page-feedback-(window|summary)$"),
    _learning("learning.presentations", "Trình chiếu", rf"^{_LRN}/presentations/.*$", rf"^{_LRN}/offerings/[^/]+/presentations$"),
    _learning("learning.ai_explanations", "Giải thích trang bằng AI", rf"^{_LRN}/page-explanations/.*$", rf"^{_LRN}/sessions/[^/]+/page-explanations$",
              rf"^{_LRN}/versions/[^/]+/explain$", default=False, kind="ai", startup_wired=True, env_alias="CAMPUS_LEARNING_AI_ENABLED", cost="model_calls"),
    # ---- knowledge
    _f("knowledge.sources", "Nguồn tri thức", "knowledge",
       api_prefixes=("/v1/knowledge/sources", "/v1/knowledge/source-review-status", "/v1/knowledge/document-versions", "/v1/knowledge/platform/availability", "/v1/knowledge/platform/state"),
       pages=("knowledge", "knowledge/sources"), nav_keys=("knowledge",)),
    _f("knowledge.documents", "Tài liệu tri thức", "knowledge", depends_on=("knowledge.sources",),
       api_prefixes=("/v1/knowledge/platform/documents", "/v1/knowledge/platform/uploads", "/v1/knowledge/platform/intakes", "/v1/knowledge/platform/url-intakes",
                     "/v1/knowledge/platform/previews", "/v1/knowledge/platform/search-preview", "/v1/knowledge/platform/resolve-preview",
                     "/v1/knowledge/platform/confirmations", "/v1/knowledge/platform/jobs", "/v1/knowledge/platform/versions"),
       pages=("knowledge/documents",), nav_keys=("documents",)),
    _f("knowledge.corrections", "Đính chính tri thức", "knowledge", depends_on=("knowledge.documents",), api_prefixes=("/v1/knowledge/platform/corrections",)),
    _f("knowledge.editions", "Ấn bản tri thức", "knowledge", depends_on=("knowledge.documents",), api_prefixes=("/v1/knowledge/platform/edition-relations", "/v1/knowledge/platform/editions")),
    _f("knowledge.crawl", "Thu thập nguồn web", "knowledge", depends_on=("knowledge.documents",), api_prefixes=("/v1/knowledge/platform/crawl-sources",), pages=("knowledge/crawl",), nav_keys=("crawl",), jobs=("crawl",)),
    _f("knowledge.auto_publication", "Tự động phát hành", "knowledge", kind="job", depends_on=("knowledge.documents",), jobs=("auto_publication",)),
    _f("knowledge.schedules", "Lịch cập nhật tri thức", "knowledge", depends_on=("knowledge.documents",), api_prefixes=("/v1/knowledge/platform/schedules",), jobs=("knowledge_schedules",)),
    _f("knowledge.freshness", "Độ tươi của nguồn", "knowledge", depends_on=("knowledge.sources",), api_prefixes=("/v1/knowledge/freshness",), pages=("knowledge/freshness",), jobs=("freshness_reminders",)),
    _f("knowledge.answer_quality", "Chất lượng câu trả lời", "knowledge", depends_on=("knowledge.sources",), api_prefixes=("/v1/knowledge/answer-quality", "/v1/knowledge/gap-reports"), pages=("knowledge/quality",)),
    _f("knowledge.release_check", "Kiểm truy hồi khi đổi release", "knowledge", kind="job", depends_on=("knowledge.sources",), jobs=("release_check",)),
    _f("knowledge.policy_graph", "Đồ thị quy chế", "knowledge", default=False, depends_on=("knowledge.sources",), api_prefixes=("/v1/policy-graph",), pages=("knowledge/policy-graph",)),
    # ---- admin, identity, web
    _f("admin.overview", "Tổng quan quản trị", "admin", api_prefixes=("/v1/admin/overview",), pages=("admin",), nav_keys=("admin",)),
    _f("admin.operations", "Trang vận hành", "admin", depends_on=("admin.overview",), api_prefixes=("/v1/admin/operations/",)),
    _f("ops.alerts", "Cảnh báo vận hành", "ops", kind="ops", jobs=("alerts",)),
    _f("identity.oidc", "Đăng nhập tài khoản trường", "identity", default=False, startup_wired=True, env_alias="CAMPUS247_OIDC_CONFIG", api_prefixes=("/v1/auth/oidc", "/v1/auth/providers")),
    _f("web.pwa", "Ứng dụng web cài được (PWA)", "web", kind="ui", client_visible=True),
    _f("web.i18n_en", "Giao diện tiếng Anh", "web", kind="ui"),
    # ---- new in this series: all off by default
    _f("announcements.publish", "Soạn và gửi thông báo chính thức", "announcements", default=False, depends_on=("notifications.inbox",), api_prefixes=("/v1/announcements",), pages=("announcements/manage",), nav_keys=("announcementsManage",),
       jobs=("announcement_publisher", "announcement_reconcile", "announcement_expiry", "announcement_ack_reminders")),
    _f("announcements.inbox", "Xem thông báo chính thức", "announcements", default=False, depends_on=("notifications.inbox",),
       api_patterns=(r"^/v1/announcements/(mine|public)$", r"^/v1/announcements/(?!drafts$|authored$|approvals$)[^/:]+$", r"^/v1/announcements/[^/:]+/ack$"), pages=("announcements",), nav_keys=("announcements",)),
    _f("announcements.knowledge_sync", "Thông báo vào kho tri thức", "announcements", default=False, depends_on=("announcements.publish", "knowledge.documents")),
    _f("announcements.second_approval", "Gửi toàn trường cần người thứ hai duyệt", "announcements", default=False, depends_on=("announcements.publish",),
       api_patterns=(r"^/v1/announcements/approvals$", r"^/v1/announcements/[^/:]+:(approve|reject)$")),
    _f("announcements.chat_tool", "Chatbot tra thông báo", "announcements", kind="ai", default=False, depends_on=("announcements.inbox", "chat.assistant"), tools=("announcements_lookup",)),
    _f("policy.graph_v2", "Đồ thị quy chế trên v2", "policy", default=False, depends_on=("knowledge.policy_graph",)),
    _f("policy.rules", "Quy chế thành luật chạy được", "policy", default=False, depends_on=("policy.graph_v2",), api_prefixes=("/v1/policy-rules",)),
    _f("policy.simulator", "Mô phỏng nếu-thì", "policy", default=False, depends_on=("policy.rules", "chat.assistant"), api_prefixes=("/v1/policy-simulator",)),
    _f("policy.impact", "Tác động khi quy chế đổi", "policy", default=False, depends_on=("policy.graph_v2",), api_prefixes=("/v1/policy-impact",)),
    _f("policy.conflicts", "Phát hiện mâu thuẫn quy chế", "policy", default=False, depends_on=("policy.graph_v2",), api_prefixes=("/v1/policy-conflicts",)),
    _f("policy.impact_announcements", "Soạn thông báo từ tác động", "policy", default=False, depends_on=("policy.impact", "announcements.publish")),
    _f("policy.impact_user_notices", "Báo người dùng đã hỏi quy chế đổi", "policy", default=False, depends_on=("policy.impact", "notifications.inbox", "chat.history")),
    _f("chat.evidence_receipts", "Biên nhận bằng chứng câu trả lời", "chat", default=False, depends_on=("chat.assistant",), api_prefixes=("/v1/answer-receipts",)),
    _f("chat.evidence_ui", "Hiển thị bằng chứng", "chat", kind="ui", default=False, depends_on=("chat.evidence_receipts",)),
    _f("agent.procedures", "Agent làm thủ tục", "agent", kind="ai", default=False, depends_on=("policy.rules", "services.preparations", "tickets.student"), api_prefixes=("/v1/procedures",), tools=("procedure_check", "procedure_draft"), cost="model_calls"),
    _f("proactive.nudges", "Nhắc việc chủ động", "proactive", default=False, depends_on=("notifications.inbox",), api_prefixes=("/v1/nudges",), jobs=("proactive_nudges",)),
    _f("proactive.digest", "Bản tin tuần", "proactive", default=False, depends_on=("proactive.nudges",), jobs=("proactive_digest",)),
    _f("learning.tutor", "Gia sư hỏi gợi mở", "learning", kind="ai", default=False, depends_on=("learning.practice",), api_patterns=(rf"^{_LRN}/tutor/.*$",), cost="model_calls"),
    _f("learning.mastery_map", "Bản đồ nắm vững", "learning", default=False, depends_on=("learning.practice",), api_patterns=(rf"^{_LRN}/mastery/.*$",)),
    _f("input.image", "Hỏi bằng ảnh", "input", kind="ai", default=False, depends_on=("chat.assistant",), api_prefixes=("/v1/input/image",), cost="ram"),
    _f("input.voice", "Hỏi bằng giọng nói", "input", kind="ai", default=False, depends_on=("chat.assistant",), api_prefixes=("/v1/input/voice",), cost="ram"),
    _f("output.read_aloud", "Đọc câu trả lời thành tiếng", "output", kind="ui", default=False, depends_on=("chat.assistant",)),
)

BY_KEY: dict[str, FeatureDefinition] = {f.key: f for f in FEATURES}
LONGEST_FIRST_PREFIXES: tuple[tuple[str, str], ...] = tuple(sorted(
    ((p, f.key) for f in FEATURES for p in f.api_prefixes), key=lambda item: -len(item[0])))
_PATTERNS: tuple[tuple[re.Pattern, str], ...] = tuple((re.compile(p), f.key) for f in FEATURES for p in f.api_patterns)


def validate_registry(features=FEATURES) -> list[str]:
    """Return every structural problem (an empty list = valid). Used by tests and by startup."""
    problems: list[str] = []
    keys: dict[str, FeatureDefinition] = {}
    for f in features:
        if not KEY_PATTERN.match(f.key):
            problems.append(f"bad key {f.key}")
        if f.key in keys:
            problems.append(f"duplicate key {f.key}")
        keys[f.key] = f
        if f.area not in AREAS:
            problems.append(f"{f.key}: unknown area {f.area}")
        if not f.locked and any(part in f.key.split(".", 1)[1] for part in FORBIDDEN_NAME_PARTS):
            problems.append(f"{f.key}: a switch name must not weaken confirm/auth/verify")
        if f.locked and (not f.default or f.variants or any(not keys_locked(features, d) for d in f.depends_on)):
            problems.append(f"{f.key}: a locked feature must default on, have no variants and depend only on locked features")
        if f.variants and (f.default_value not in f.variants):
            problems.append(f"{f.key}: default_value must be one of the variants")
    for f in features:
        for dep in f.depends_on:
            if dep not in keys:
                problems.append(f"{f.key}: unknown dependency {dep}")
    # cycles
    state: dict[str, int] = {}

    def visit(key: str, trail: tuple[str, ...]) -> None:
        if state.get(key) == 2 or key not in keys:
            return
        if state.get(key) == 1:
            problems.append("dependency cycle: " + " -> ".join(trail + (key,)))
            return
        state[key] = 1
        for dep in keys[key].depends_on:
            visit(dep, trail + (key,))
        state[key] = 2

    for key in keys:
        visit(key, ())
    # one owner per prefix, page and job; nested prefixes only when the inner feature depends on the outer one
    owner: dict[str, str] = {}
    for f in features:
        for kind, values in (("prefix", f.api_prefixes), ("page", f.pages), ("job", f.jobs), ("tool", f.tools), ("nav", f.nav_keys)):
            for value in values:
                if (kind, value) in owner and owner[(kind, value)] != f.key:
                    problems.append(f"{kind} {value} owned by {owner[(kind, value)]} and {f.key}")
                owner[(kind, value)] = f.key
    return problems


def keys_locked(features, key: str) -> bool:
    return any(f.key == key and f.locked for f in features)


def _segment_prefix(path: str, prefix: str) -> bool:
    return path.startswith(prefix)


def feature_for_path(path: str) -> str | None:
    """Owner of an API path: the longest matching prefix, or a pattern (patterns win over the broad prefix they sit inside)."""
    for pattern, key in _PATTERNS:
        if pattern.match(path):
            return key
    for prefix, key in LONGEST_FIRST_PREFIXES:
        if _segment_prefix(path, prefix):
            return key
    return None


def feature_for_page(page: str) -> str | None:
    """Owner of a page (path without the leading slash); the longest matching page folder wins."""
    page = page.strip("/")
    best, best_len = None, -1
    for f in FEATURES:
        for p in f.pages:
            if (page == p or (p and page.startswith(p + "/"))) and len(p) > best_len:
                best, best_len = f.key, len(p)
    return best
