---
document_id: "DOC-GOV-CHAT-STREAM-20261004"
version: "1.0.0"
status: "approved"
owner: "Product and Architecture Governance"
approvers: ["Direct human approval in the implementation chat"]
last_updated: "2026-10-04"
---

# Accepted binding P-CONTRACT-STREAM-001

The human replied “phê duyệt” on 2026-10-04 to the concrete proposal in
`docs/10-delivery/RAG_CHAT_STREAM_IMPLEMENTATION_20261004.md`, after being told
that contract changes require human approval. This record documents that scoped
approval, not an independent security review or a production release approval.

Objective: API/UI faithfully serialize/display the validated chat streaming
outcome. Approved scope: OpenAPI capability traceability repair, an exact SSE
schema and API_CONVENTIONS binding, API/RAG citation identity mapping, restoration
of the response-class reference in PRD, then ordinary scoped implementation and
deterministic verification. Earlier evidence remains immutable.

## Accepted representations

- Keep the five approved SSE events; do not invent error/abstention events.
- Reserve one assistant message ID at started; persist that ID with safe final
  content and the final status/class/citation mapping before completed.
- Completed carries whole final content; clients replace provisional content,
  including after abstention/rejection. Failed carries a direct safe problem.
- The UUIDv7 `citation_id` in the public API is a durable server-issued identity.
  RAG's `CIT-<sequence>` is a turn-local claim reference, represented on the stream
  as `turn_citation_id`. A stream mapping contains that local ID plus the existing
  API citation object. This explicitly reconciles the differently named identity
  domains in RAG_PIPELINE section 7 and the API citation schema; neither ID may
  masquerade as the other. The map is persisted with the immutable final message.
- Metadata originates from the server-side evidence bundle/current candidates,
  never model-invented title/URI/version/page. Missing required provenance fails
  closed; do not synthesize authority, confidence or a source's validity.
- PRD section 6.1 names the existing capability response classes. The schema
  binds their valid combinations with graph finish status. Unknown/invalid
  results produce system_error, not a successful answer.
- Application code owns graph/guard-to-response decisions. Routes serialize;
  UI displays. No automatic graph retry, provider regeneration or write retry.

Trace: REQ-F-CHAT-001..006; REQ-NF-REL-004; API-CONV-004; DATA-DIC-021;
AI-SYS-001,006,011; API-ERR-006,009; RAG_PIPELINE section 7;
SEC-CTRL-006,013,014. Capability metadata references REQ-NF-REL-004 because the
existing endpoints expose declared normal/degraded/unavailable capability state,
and SEC-CTRL-017/020 for bounded/degraded operation. No endpoint behavior changes.

Exact added implementation helpers: application/conversation/stream_result.py
for typed conversion; conversation/messages.py for reserved IDs and immutable
final metadata; chat SSE parser and chat UI/tests. They are necessary to the
approved ID/persistence/replacement behavior. Paths are captured in the fresh
execution baseline; this is a direct-request packet, not a catalog-state change.

No change to AGENTS, safety/permission controls, StreamGuardrail, security policy,
auth/ownership, retrieval thresholds, models, migrations or dependency pins.
No authorization to access production, DB/container/provider runtime, install,
commit, push, deploy, delete or rewrite history. Frontend runtime evidence remains
separate from a source implementation when no verified runtime is available.
