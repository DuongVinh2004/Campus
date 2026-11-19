---
document_id: "DOC-DATA-002"
version: "1.2.0"
status: "approved"
owner: "Data Architect"
approvers: ["Solution Architect", "Security Lead", "Privacy Lead"]
last_updated: "2026-10-03"
---

# Data dictionary V1

## 1. Quy ước

- `uuid` nghĩa là UUIDv7 theo `DATA-MOD-001`.
- `timestamp` nghĩa là UTC `timestamptz`.
- `json` nghĩa là `jsonb` đã validate bằng JSON Schema/domain validator trước khi ghi.
- `class` nhận một trong `PUBLIC`, `INTERNAL`, `PERSONAL`, `SENSITIVE`.
- Mọi bảng mutable mặc định có `created_at timestamp NOT NULL`, `updated_at timestamp NOT NULL`, `version integer NOT NULL DEFAULT 1 CHECK(version >= 1)` trừ khi ghi khác.
- Tên vật lý SHOULD là `snake_case`; API fields MUST là `snake_case` để giảm mapping mơ hồ cho coding agent.

## 2. Identity tables

### DATA-DIC-001 `user_identity`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK, opaque internal subject |
| `display_name` | varchar(160) | No | PERSONAL | Synthetic display name in demo |
| `primary_email` | varchar(254) | Yes | PERSONAL | normalized lowercase; unique when non-null |
| `status` | enum | No | INTERNAL | `ACTIVE`, `SUSPENDED`, `DISABLED` |
| `is_synthetic` | boolean | No | INTERNAL | MUST be `true` in demo deployment |
| `last_authenticated_at` | timestamp | Yes | PERSONAL | authentication audit hint; not authorization source |

### DATA-DIC-002 `identity_link`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `user_id` | uuid | No | INTERNAL | FK `user_identity.id` |
| `issuer` | varchar(255) | No | INTERNAL | exact verified issuer URI/string |
| `subject` | varchar(255) | No | SENSITIVE | opaque provider subject; unique with issuer |
| `provider_type` | enum | No | INTERNAL | `SYNTHETIC`, `ENTRA_OIDC` |
| `claims_version` | varchar(32) | No | INTERNAL | parser/mapping version |

### DATA-DIC-003 `role_binding`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `user_id` | uuid | No | INTERNAL | FK |
| `role` | enum | No | INTERNAL | four DEC-006 roles only |
| `scope_type` | enum | No | INTERNAL | `INSTITUTION`, `FACULTY`, `QUEUE` |
| `scope_key` | varchar(100) | No | INTERNAL | e.g. `HUCE_FIT`, `STUDENT_SERVICES` |
| `valid_from` | timestamp | No | INTERNAL | authorization start |
| `valid_until` | timestamp | Yes | INTERNAL | exclusive end; null means until revoked |
| `revoked_at` | timestamp | Yes | INTERNAL | immutable revocation evidence |

### DATA-DIC-004 `student_profile`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `user_id` | uuid | No | INTERNAL | PK/FK user identity |
| `student_code` | varchar(32) | No | PERSONAL | unique synthetic code |
| `faculty_code` | varchar(32) | No | INTERNAL | default `FIT` in demo |
| `program_code` | varchar(64) | No | INTERNAL | synthetic catalog code |
| `cohort_year` | smallint | No | PERSONAL | valid 2000..2100 |
| `academic_status` | enum | No | PERSONAL | `ACTIVE`, `LEAVE`, `GRADUATED`, `WITHDRAWN` |

## 3. Student operations tables

### DATA-DIC-010 `schedule_entry`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK; stable source record ID |
| `student_user_id` | uuid | No | PERSONAL | owner FK; mandatory query predicate |
| `source_system` | varchar(64) | No | INTERNAL | `SYNTHETIC_SIS` initially |
| `source_record_id` | varchar(128) | No | INTERNAL | unique with source system |
| `course_code` | varchar(32) | No | INTERNAL | exact searchable identifier |
| `course_name` | varchar(200) | No | INTERNAL | Vietnamese display name |
| `starts_at` | timestamp | No | PERSONAL | start < end |
| `ends_at` | timestamp | No | PERSONAL | end > start |
| `location_label` | varchar(160) | Yes | PERSONAL | room/campus display |
| `instructor_display_name` | varchar(160) | Yes | PERSONAL | synthetic only in demo |
| `sync_version` | bigint | No | INTERNAL | monotonic source version |

### DATA-DIC-011 `ticket`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK/public ticket ID |
| `requester_user_id` | uuid | No | PERSONAL | owner FK |
| `category` | enum | No | INTERNAL | `GENERAL_SUPPORT`, `ACADEMIC_POLICY`, `DOCUMENT_REQUEST_SUPPORT`, `FACILITY`, `COMPLAINT`, `OTHER` |
| `priority` | enum | No | INTERNAL | `LOW`, `NORMAL`, `HIGH`, `CRITICAL` |
| `status` | enum | No | INTERNAL | schema `ticket-state.schema.json` |
| `subject` | varchar(200) | No | PERSONAL | no secrets; sanitized display text |
| `description_redacted` | text | No | PERSONAL | redacted user description |
| `queue_key` | varchar(100) | No | INTERNAL | routing destination |
| `assigned_user_id` | uuid | Yes | PERSONAL | staff assignee; required in assigned states |
| `sla_due_at` | timestamp | Yes | INTERNAL | null if operating model lacks target |
| `resolved_at` | timestamp | Yes | INTERNAL | required for `RESOLVED`/`CLOSED` |
| `closed_at` | timestamp | Yes | INTERNAL | required only for `CLOSED` |

### DATA-DIC-012 `ticket_event`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `ticket_id` | uuid | No | INTERNAL | FK, indexed with `sequence_no` |
| `sequence_no` | bigint | No | INTERNAL | unique per ticket, starts 1 |
| `event_type` | enum | No | INTERNAL | `CREATED`, `STATUS_CHANGED`, `ASSIGNED`, `COMMENTED`, `ESCALATED`, `ATTACHMENT_LINKED` |
| `actor_user_id` | uuid | Yes | PERSONAL | null only for system actor |
| `from_status` | enum | Yes | INTERNAL | required for status change |
| `to_status` | enum | Yes | INTERNAL | required for status change |
| `comment_redacted` | text | Yes | PERSONAL | client-visible depending visibility |
| `visibility` | enum | No | INTERNAL | `REQUESTER_AND_STAFF`, `STAFF_ONLY`, `AUDIT_ONLY` |
| `occurred_at` | timestamp | No | INTERNAL | immutable event time |

### DATA-DIC-013 `document_request`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `student_user_id` | uuid | No | PERSONAL | owner FK |
| `document_type` | varchar(64) | No | PERSONAL | allowlisted service catalog code |
| `purpose_code` | varchar(64) | No | PERSONAL | allowlisted, no free-form unless approved |
| `delivery_method` | enum | No | PERSONAL | `DIGITAL`, `PICKUP` |
| `status` | enum | No | INTERNAL | lifecycle section DATA-LIFE-004 |
| `action_execution_id` | uuid | No | INTERNAL | proves confirmed creation |
| `ticket_id` | uuid | Yes | INTERNAL | optional linked support ticket |
| `submitted_at` | timestamp | Yes | INTERNAL | required after `SUBMITTED` |

### DATA-DIC-014 `room`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `room_code` | varchar(32) | No | INTERNAL | unique exact identifier |
| `display_name` | varchar(160) | No | INTERNAL | user-facing name |
| `capacity` | integer | No | INTERNAL | >0 |
| `features` | json | No | INTERNAL | array of allowlisted feature codes |
| `status` | enum | No | INTERNAL | `AVAILABLE`, `MAINTENANCE`, `INACTIVE` |

### DATA-DIC-015 `room_booking`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `room_id` | uuid | No | INTERNAL | FK room |
| `requester_user_id` | uuid | No | PERSONAL | owner FK |
| `starts_at` | timestamp | No | PERSONAL | start < end |
| `ends_at` | timestamp | No | PERSONAL | conflict-enforced interval |
| `purpose_redacted` | varchar(300) | No | PERSONAL | safe display value |
| `attendee_count` | integer | No | PERSONAL | 1..room.capacity |
| `status` | enum | No | INTERNAL | `CONFIRMED`, `CANCELLED`, `COMPLETED` |
| `action_execution_id` | uuid | No | INTERNAL | confirmed action proof |
| `cancelled_at` | timestamp | Yes | INTERNAL | required for cancelled |

## 4. Conversation and handover tables

### DATA-DIC-020 `conversation`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `owner_user_id` | uuid | No | PERSONAL | requester owner |
| `status` | enum | No | INTERNAL | `ACTIVE`, `HANDED_OVER`, `CLOSED`, `ARCHIVED` |
| `channel` | enum | No | INTERNAL | V1 only `WEB` |
| `last_message_at` | timestamp | Yes | PERSONAL | list ordering |
| `retention_expires_at` | timestamp | No | INTERNAL | default from ASM-007 |

### DATA-DIC-021 `message`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `conversation_id` | uuid | No | INTERNAL | FK |
| `sequence_no` | bigint | No | INTERNAL | unique per conversation |
| `sender_type` | enum | No | INTERNAL | `USER`, `ASSISTANT`, `STAFF`, `SYSTEM` |
| `sender_user_id` | uuid | Yes | PERSONAL | required for USER/STAFF |
| `content_redacted` | text | No | PERSONAL | rendered content after safety redaction |
| `content_format` | enum | No | INTERNAL | `PLAIN_TEXT`, `MARKDOWN_SAFE` |
| `citation_set_id` | uuid | Yes | INTERNAL | citations for assistant message |
| `created_at` | timestamp | No | PERSONAL | immutable |
| `redacted_at` | timestamp | Yes | INTERNAL | audit-only redaction marker |

### DATA-DIC-022 `handover`

Fields MUST conform to `handover.schema.json` for wire values. Persistent fields: `id`, `conversation_id`, `requester_user_id`, `queue_key`, `reason_code`, `risk_level`, `status`, `summary_redacted`, `context_reference_ids`, `assigned_user_id`, `created_at`, `accepted_at`, `resolved_at`, `version`. Raw prompt, hidden chain-of-thought and unrestricted model context MUST NOT be stored.

## 5. Knowledge tables

### DATA-DIC-030 `knowledge_source`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `source_type` | enum | No | INTERNAL | `OFFICIAL_DOCUMENT`, `OFFICIAL_WEB`, `SYNTHETIC_DOCUMENT` |
| `canonical_uri` | text | No | PUBLIC | unique normalized URI or synthetic URN |
| `title` | varchar(300) | No | PUBLIC | source title |
| `owner_unit` | varchar(160) | No | INTERNAL | responsible unit |
| `authority_level` | smallint | No | INTERNAL | 1..100; higher means more authoritative |
| `approval_status` | enum | No | INTERNAL | `DRAFT`, `APPROVED`, `REJECTED` |
| `is_synthetic` | boolean | No | INTERNAL | provenance marker |
| `campus_scope` | varchar(64) | No* | INTERNAL | V1 exact value `HUCE`; SQL authorization predicate |
| `faculty_scope` | varchar(32)[] | No* | INTERNAL | non-empty approved faculties; V1 includes `FIT` |
| `program_scope` | varchar(64)[] | No* | INTERNAL | empty means no program is authorized, never allow-all |
| `audiences` | varchar(64)[] | No* | INTERNAL | non-empty allowlisted roles/cohorts; SQL authorization predicate |

#### Ngoại lệ chuyển tiếp legacy cho FILTER-001

`No*` giữ yêu cầu NOT NULL cho nguồn mới và nguồn đã được review scope. Chỉ
những source tồn tại trước migration FILTER-001, chưa có scope metadata được
knowledge owner phê duyệt, MAY giữ **cả bốn** field scope là NULL. Không cho phép
tuple scope chỉ có một phần NULL hoặc dùng ngoại lệ này cho INSERT mới.

Storage MUST reject nguồn mới thiếu scope; scope review MUST cung cấp toàn bộ
tuple hợp lệ. Mọi faculty/audience phải thuộc approved allowlist và campus phải
là `HUCE`; `program_scope` rỗng vẫn nghĩa không program nào được authorized.
Update không liên quan scope MAY giữ tuple legacy NULL; thao tác review/enrich
scope phải qua knowledge-owner authorization và audit hiện có, không được suy
ra quyền từ title, owner_unit, approval_status hay ngày publish.

Production SQL MUST exclude tuple legacy NULL và mọi missing/empty authorized
intersection trước ranking/LIMIT. Ngoại lệ này chỉ biểu diễn metadata chưa biết
trong storage, không cấp quyền retrieval. Migration MUST giữ nguyên mọi cột,
vector, index và dữ liệu cũ; không tự backfill `HUCE`, `FIT`, `STUDENT`, `ALL`,
program hoặc audience, không đổi approval/publication state để che thiếu scope.
Chỉ thêm field/constraint/index phù hợp và dùng recovery forward-only.

Approval evidence: direct human instruction ngày 2026-10-03, “tiếp tục theo đề
xuất tốt nhất, phù hợp nhất”, sau proposal `B-FILTER-LEGACY-NULL` về legacy NULL
và fail closed trong phiên triển khai. Approval chỉ áp dụng ngoại lệ chuyển tiếp
này; không đổi production profile `rag-prod-v1.0.0`, model/revision/dimension,
threshold, dependency, live provider hoặc quyền production/destructive operation.

### DATA-DIC-031 `document_version`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `knowledge_source_id` | uuid | No | INTERNAL | FK |
| `version_label` | varchar(64) | No | PUBLIC | source-local immutable version |
| `content_checksum` | char(64) | No | INTERNAL | lowercase SHA-256 hex |
| `effective_from` | timestamp | Yes | PUBLIC | inclusive |
| `effective_until` | timestamp | Yes | PUBLIC | exclusive |
| `status` | enum | No | INTERNAL | DATA-LIFE-006 |
| `storage_object_key` | text | No | SENSITIVE | private object locator, never public API |
| `published_at` | timestamp | Yes | PUBLIC | required when published/superseded |
| `published_by` | uuid | Yes | PERSONAL | knowledge admin actor |
| `applicability_reviewed_at` | timestamp | Yes | INTERNAL | required for production retrieval when `effective_until` is null |
| `index_version` | varchar(128) | Yes | INTERNAL | exact immutable index manifest version; required when indexed/published |

### DATA-DIC-032 `knowledge_chunk`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `document_version_id` | uuid | No | INTERNAL | FK |
| `ordinal` | integer | No | INTERNAL | unique within version |
| `section_path` | varchar(500) | Yes | PUBLIC | stable heading hierarchy |
| `page_start` / `page_end` | integer | Yes | PUBLIC | positive; end >= start |
| `content_text` | text | No | PUBLIC/INTERNAL | class inherited from source |
| `content_checksum` | char(64) | No | INTERNAL | chunk SHA-256 |
| `search_vector` | tsvector | No | INTERNAL | generated/indexed lexical value |
| `embedding` | vector | Yes | INTERNAL | dimension fixed by approved embedding model |
| `embedding_model_version` | varchar(128) | Yes | INTERNAL | required when embedding non-null |
| `embedding_dimension` | integer | Yes | INTERNAL | `1024` for `rag-prod-v1.0.0`; must match manifest |
| `embedded_at` | timestamp | Yes | INTERNAL | required when embedding non-null |

Physical compatibility mapping for current M1 preparation (DEC-022): migration
`0013` stores the logical profile embedding in `embedding_rag_v1 vector(1024)`;
the legacy `embedding vector(1536)` remains intact and is not eligible for the
current 1024 profile. Model-version/dimension/timestamp metadata is all-or-none
with `embedding_rag_v1`; the database checks exact current model revision and L2
norm within float32 tolerance `1e-4`. Readers/writers must select storage through
explicit profile binding; migration alone does not activate an index or wire a
retriever. A better future model uses a new evaluated profile/storage mapping,
not conversion or relabeling of old vectors.

### DATA-DIC-033 `retrieval_run`

Store: `id`, `conversation_id`, `message_id`, `query_redacted`, `authorization_scope_hash`, `campus_scope`, `faculty_scope`, `audience_scope`, `effective_at`, `filter_json`, `lexical_candidate_count`, `vector_candidate_count`, `reranked_count`, `retrieval_profile_version`, `embedding_model_version`, `reranker_model_version`, `index_version`, `degraded_reason`, `duration_ms`, `created_at`. Candidate scores live in child `retrieval_candidate(run_id, chunk_id, lexical_rank, vector_rank, fused_score, rerank_score, selected)`. Raw query, unrestricted identity claims và unauthorized candidate metadata MUST NOT được lưu.

### DATA-DIC-034 `retrieval_profile`

Immutable fields: `profile_version` (PK), `embedding_model_id`, `embedding_model_revision`, `embedding_dimension`, `normalization`, `distance_metric`, `lexical_k`, `semantic_k`, `rrf_constant`, `fusion_k`, `rerank_k`, `context_k`, `context_token_budget`, branch/reranker/overall timeouts, retry limit, fallback policy, evidence threshold, release thresholds, `created_at`, `approved_at`, `approval_reference`. `rag-prod-v1.0.0` MUST equal the accepted values in `DOC-RAG-001`; no nullable production field is allowed.

### DATA-DIC-035 `embedding_index_manifest`

Immutable fields: `index_version` (PK), `profile_version` (FK), `embedding_model_id`, `embedding_model_revision`, `artifact_sha256`, `dimension`, `normalization`, `distance_metric`, `corpus_version`, `document_count`, `chunk_count`, `content_checksum`, `build_status`, `built_at`, `validated_at`, `activated_at`. `build_status`: `BUILDING`, `VALIDATING`, `READY`, `ACTIVE`, `RETIRED`, `FAILED`. Activation MUST atomically change a separate active pointer; it MUST NOT overwrite or delete the previous active manifest/index.

## 6. Action, reliability and audit tables

### DATA-DIC-040 `action_preview`

Fields MUST match `action-preview.schema.json`; persistence adds `confirmation_secret_hash` (never return), `consumed_at`, `cancelled_at`, `created_at`, `version`. `normalized_payload` is encrypted at rest when classified PERSONAL/SENSITIVE.

### DATA-DIC-041 `action_confirmation`

Fields MUST match `action-confirmation.schema.json`; persistence stores only hash of one-time token after issue. Plain confirmation token MUST NOT be logged or persisted after verification.

### DATA-DIC-042 `action_execution`

| Field | Type | Null | Class | Constraint/meaning |
|---|---|---:|---|---|
| `id` | uuid | No | INTERNAL | PK |
| `preview_id` | uuid | No | INTERNAL | unique FK after success |
| `status` | enum | No | INTERNAL | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `COMPENSATION_REQUIRED` |
| `target_type` | varchar(64) | Yes | INTERNAL | resulting aggregate type |
| `target_id` | uuid | Yes | INTERNAL | resulting aggregate ID |
| `attempt_count` | integer | No | INTERNAL | >=0 |
| `last_error_code` | varchar(100) | Yes | INTERNAL | stable safe code only |
| `completed_at` | timestamp | Yes | INTERNAL | terminal state time |

### DATA-DIC-043 `idempotency_record`

Store: `id`, `actor_user_id`, `operation_id`, `idempotency_key`, `request_fingerprint`, `state`, `http_status`, `response_reference`, `locked_until`, `expires_at`, timestamps. Unique `(actor_user_id, operation_id, idempotency_key)`. `state`: `IN_PROGRESS`, `COMPLETED`, `FAILED_RETRYABLE`, `FAILED_FINAL`.

### DATA-DIC-044 `audit_event`

Append-only fields: `id`, `occurred_at`, `actor_type`, `actor_id`, `action_code`, `resource_type`, `resource_id`, `outcome`, `reason_code`, `correlation_id`, `request_id`, `metadata_safe`. Update/delete MUST be denied to application role.

### DATA-DIC-045 `outbox_event` / `inbox_receipt`

- `outbox_event`: `id`, `event_type`, `event_version`, `aggregate_type`, `aggregate_id`, `partition_key`, `payload`, `occurred_at`, `published_at`, `publish_attempts`, `last_error_code`.
- `inbox_receipt`: `(consumer_name, event_id)` composite PK, `received_at`, `processed_at`, `outcome`.

## 7. Index tối thiểu

| ID | Index/constraint |
|---|---|
| DATA-IDX-001 | `identity_link(issuer, subject)` unique. |
| DATA-IDX-002 | `schedule_entry(student_user_id, starts_at, id)`. |
| DATA-IDX-003 | `ticket(requester_user_id, updated_at DESC, id DESC)` và `ticket(queue_key, status, priority, created_at)`. |
| DATA-IDX-004 | `message(conversation_id, sequence_no)` unique. |
| DATA-IDX-005 | `knowledge_chunk` GIN lexical; vector index chỉ sau benchmark và dimension chốt. |
| DATA-IDX-005A | production lexical/vector queries MUST apply `approval_status`, version `status`, effective/applicability, campus, faculty/program, audience và simulation predicates in SQL before rank and `LIMIT`. |
| DATA-IDX-006 | `room_booking` exclusion theo room và `[starts_at, ends_at)` cho status `CONFIRMED`. |
| DATA-IDX-007 | `idempotency_record(actor_user_id, operation_id, idempotency_key)` unique. |
| DATA-IDX-008 | `outbox_event(published_at, occurred_at)` partial cho unpublished. |

## 8. Acceptance evidence và failure behavior

Implementation MUST cung cấp migration/schema evidence ánh xạ từng bảng/trường bắt buộc, constraint tests và data-classification review. Nếu kiểu cơ sở dữ liệu không thể biểu diễn một constraint, task MUST dừng với `DATA_CONSTRAINT_UNIMPLEMENTABLE`; không được tự giảm constraint hoặc đổi field nullability.

Ngoại lệ nullability duy nhất được phê duyệt ở version 1.2.0 là tuple legacy
scope trong DATA-DIC-030 như mô tả ở trên; implementation MUST chứng minh nguồn
mới bị reject khi thiếu scope và nguồn legacy không thể là production candidate.

Production filter semantics fail closed: source phải `APPROVED`, version phải `PUBLISHED`, `effective_from <= effective_at`, `effective_until > effective_at`; nếu `effective_until` null thì `applicability_reviewed_at` phải có giá trị. Campus, audience và faculty/program scope phải intersect với trusted authorized context; empty/missing scope không bao giờ là allow-all. Synthetic source chỉ được candidate khi profile và trusted context cùng cho phép simulation. Các predicate này phải nằm trong cùng SQL candidate relation trước lexical/vector ranking và `LIMIT`.

Approval evidence: direct human approval ngày 2026-09-29 cho `TASK-RAGUP-GOV-001`, bao phủ contract, authorization-filter semantics, model/index manifest và release thresholds của `rag-prod-v1.0.0`.
