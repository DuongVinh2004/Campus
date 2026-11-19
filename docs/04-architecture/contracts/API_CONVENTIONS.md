---
document_id: "DOC-API-002"
version: "1.1.1"
status: "reviewed"
owner: "API Architect"
approvers: ["Solution Architect", "Security Lead", "Frontend Lead"]
last_updated: "2026-10-12"
---

# API conventions V1

## Citation source read (API-CONV-005, local implementation authority DEC-023)

`GET /v1/conversations/{conversation_id}/messages/{message_id}/citations/{citation_id}/source`
resolves source/version/chunk only from an immutable validated final in the actor's
unexpired own conversation. The saved citation does not grant access: current
trusted scope, actor grants, publication, applicability and simulation policy MUST
be checked before returning the original cited chunk. Verify checksum, locator,
metadata and saved quote; conceal absent/denied resources with 404. Missing policy
or storage dependencies fail closed with 503. Responses are bounded, allowlisted,
plain text, `Cache-Control: no-store`; decisions are audited without tokens or text.
This read performs no inference, message mutation, arbitrary URI fetch or admin
knowledge access. It exposes the cited chunk, not a full-document representation.

## 1. Protocol và representation

| ID | Rule |
|---|---|
| API-CONV-001 | Public application API MUST use HTTPS and JSON UTF-8. Plain HTTP chỉ được phép trong isolated local development. |
| API-CONV-002 | Base path MUST là `/v1`; URI dùng plural kebab-case resources, fields dùng `snake_case`. |
| API-CONV-003 | Request/response JSON MUST validate theo OpenAPI/JSON Schema; unknown request properties MUST bị từ chối bằng `422`. |
| API-CONV-004 | Timestamps MUST là RFC 3339 UTC (`...Z`); date-only dùng `YYYY-MM-DD`. |
| API-CONV-005 | IDs MUST là lowercase canonical UUID text; clients treat opaque. |
| API-CONV-006 | Success media type là `application/json`; errors là `application/problem+json`. |
| API-CONV-007 | API MUST set `X-Request-Id`; accept caller value chỉ khi valid UUID, nếu không tạo mới. |
| API-CONV-008 | `traceparent` MAY propagate theo observability standard; API MUST NOT expose internal stack trace. |

## 2. Authentication và actor resolution

- Secured operation MUST require bearer token through `bearerAuth` in OpenAPI.
- API gateway/auth middleware MUST verify signature, issuer, audience, expiration and environment/provider policy before creating `IdentityContext`.
- Domain service MUST receive `{user_id, roles, scopes, auth_time, provider_type, is_synthetic}` from trusted context.
- Student-facing endpoint path MUST use `/students/me`, không `/students/{student_id}`.
- Client-supplied `user_id`, `actor_id`, role hoặc scope MUST NOT override auth context.
- `401` dùng khi thiếu/invalid authentication; `403` khi authenticated nhưng không được phép.

## 3. Resource và operation naming

| Pattern | Example | Rule |
|---|---|---|
| Collection | `GET /v1/tickets` | cursor paginated |
| Create | `POST /v1/tickets/actions/preview` | write preview, no side effect |
| Read | `GET /v1/tickets/{ticket_id}` | object-level authorization |
| Command | `POST /v1/tickets/{ticket_id}/transitions` | explicit domain transition |
| Confirmation | `POST /v1/actions/{preview_id}/confirm` | generic confirmed action boundary |
| Current user | `GET /v1/users/me` | identity from token only |

Endpoint MUST NOT dùng generic `PATCH status`. State change uses command/transition schema with `expected_version`.

## 4. HTTP methods và status codes

| Scenario | Status |
|---|---:|
| Read success | `200` |
| Synchronous create success | `201` + `Location` |
| Accepted async execution | `202` + status resource/location |
| Successful command with body | `200` |
| Successful command no body | `204` |
| Invalid/missing auth | `401` |
| Authenticated but forbidden | `403` |
| Resource absent or concealed by object authorization | `404` |
| Version/idempotency/state/conflict | `409` |
| Expired preview/confirmation | `410` |
| Semantic validation failure | `422` |
| Rate limited | `429` + `Retry-After` when known |
| Dependency unavailable | `503` + retryability metadata |

Use HTTP semantics consistent with [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html). API MUST NOT return `200` with `{success:false}` for failure.

## 5. Request headers

| Header | Required | Meaning |
|---|---:|---|
| `Authorization: Bearer …` | secured operations | user/service token |
| `X-Request-Id` | SHOULD | caller correlation UUID |
| `Idempotency-Key` | write confirmation/create commands | duplicate protection; 16–128 visible ASCII chars |
| `If-Match` | mutable existing aggregate | quoted version ETag, e.g. `"7"` |
| `Accept-Language` | MAY | V1 supports `vi`; fallback `vi` |
| `Last-Event-ID` | SSE resume | last delivered stream event ID |

Sensitive headers MUST be redacted from logs.

## 6. Response envelope

Single resources are returned directly, not under `data`. Collections use:

```json
{
  "items": [],
  "page": {
    "next_cursor": null,
    "has_more": false,
    "limit": 20
  }
}
```

Mutable resource response MUST include `ETag: "<version>"`. Server MAY also include `version` in JSON; if present values MUST match.

## 7. Validation

Validation order SHOULD be:

1. transport/media type and body size;
2. authentication;
3. syntax/schema;
4. authorization including object scope;
5. business/state/policy rules;
6. idempotency/concurrency;
7. execution.

Security MAY intentionally return `404` before revealing resource existence. Validation detail uses JSON Pointer in `errors[].pointer`; message is safe Vietnamese user guidance, code is stable English identifier.

## 8. Chat streaming

V1 chat response MAY use Server-Sent Events at `POST /v1/conversations/{conversation_id}/messages:stream` because browser clients need incremental output. Contract rules:

- `Content-Type: text/event-stream`; each event has `id`, `event`, `data`.
- Event names: `message.started`, `message.delta`, `citation.added`, `message.completed`, `message.failed`.
- `message.delta` is presentation text only and MUST NOT be treated as final grounded answer.
- `message.completed` carries final message ID, citations and finish status.
- On disconnect, client MAY reconnect with `Last-Event-ID`; server either resumes from bounded buffer or returns a normal GET link. It MUST NOT regenerate a write action silently.
- Streaming errors after headers are emitted use `message.failed` with safe problem object; pre-stream errors use HTTP problem response.

OpenAPI documents the stream media type at skeleton level; exact AI response semantics belong to AI package.

### 8.1 Approved payload binding — P-CONTRACT-STREAM-001

Direct human approval ngày 2026-10-04 trong chat triển khai: “phê duyệt”, sau
proposal P-CONTRACT-STREAM-001. Decision record:
`docs/00-governance/CHAT_STREAM_CONTRACT_DECISION_20261004.md`.
`contracts/json-schema/chat/stream-event.schema.json` defines the parsed
`{id, event, data}` envelope; wire `data` is JSON, bounded by an SSE blank line.

- `message.started.data = {conversation_id, message_id}`. The server reserves
  this assistant UUIDv7; completion and the immutable saved message use it.
- `message.delta.data = {seq, delta}`. Sequence is a positive integer increasing
  within this attempt. Clients ignore duplicates/reordered deltas and event IDs;
  they never enable citations, actions or feedback based on provisional text.
- `citation.added.data = {message_id, citation}`. A stream citation is
  `{turn_citation_id, citation}`: turn ID matches `CIT-<sequence>` used in claims,
  nested `citation` follows the existing UUIDv7 API citation schema. These are
  distinct identity domains, joined by an immutable server-generated mapping.
  Do not invent missing source/version/locator/status metadata.
- `message.completed.data = {conversation_id, message_id, status,
  response_class, content, citations}`. `status` is
  `answered | abstained | completed | cancelled | handed_over`, preserving the
  validated graph outcome. `response_class` follows PRD section 6.1. `content`
  replaces the entire provisional text. `citations` is the authoritative final
  array of stream citations; rejected/abstained content has no grounded citations.
  Persist only the validated final text and the same immutable ID/mapping.
- `message.failed.data` is directly the existing safe problem object, without a
  custom wrapper. `safe_failure`, missing/invalid graph output and unexpected
  exceptions never become completed/answered. No raw exception, stack, provider
  body or guard rejection pattern appears in the payload. Retryability requires
  proof that a retry cannot duplicate side effects; clients do not retry silently.
- Unknown fields are ignored. Unknown event/status/class, malformed JSON,
  wrong message binding and EOF without a terminal produce explicit UNKNOWN or
  failed UI behavior, withdraw provisional text/citations and record only a safe
  telemetry code. CR/LF/CRLF, fragmented UTF-8, comments and multiline `data`
  must be decoded by event boundary, not individual network chunks/data lines.
- After a terminal, ignore duplicate terminal delivery; do not overwrite the
  saved result with trailing data. Cancellation/disconnect before validation or
  persistence does not commit partial assistant text. No graph regeneration on
  stream resume; unsupported resume is a pre-stream problem with an alternate
  transcript GET link, rather than a second execution.

This binding does not change authentication, authorization, evidence thresholds,
RAG retrieval/model behavior or database migrations. Runtime/storage promotion
still requires its own evidence and approval.

## 9. Caching

- Personalized resources (`/users/me`, schedules, tickets, conversations, actions) MUST send `Cache-Control: no-store`.
- Public/static knowledge metadata MAY use ETag and short private/public cache policy only after data classification review.
- Responses containing signed URLs MUST be `private, no-store`.

## 10. Versioning và compatibility

- URL major version; backward-compatible changes remain `/v1`.
- Consumers MUST ignore unknown response fields but MUST NOT ignore unknown enum values blindly; map to explicit `UNKNOWN` UI behavior and record telemetry.
- Server rejects unsupported request content type with `415` and oversized payload with `413`.
- Deprecated operation MUST include OpenAPI `deprecated: true`, migration guidance and an announced removal window before a new major version.

## 11. Acceptance evidence và failure behavior

Evidence cho mỗi endpoint: OpenAPI validation, positive contract test, authentication/authorization negative tests, schema rejection test, stable problem type, request ID propagation, cache-header check và idempotency/concurrency test nếu write. Nếu operation cần hành vi không được convention quy định, coding agent MUST dừng với `API_CONVENTION_GAP`; không được tạo response envelope/status/header riêng.
