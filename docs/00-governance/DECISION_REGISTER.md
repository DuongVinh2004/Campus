---
document_id: "DOC-GOV-DECISIONS-001"
version: "1.2.0"
status: "approved"
owner: "Product and Architecture Governance"
approvers: ["Product Owner", "Architecture Owner", "Security Owner"]
last_updated: "2026-10-07"
---

# Decision register

Status values: `accepted`, `proposed`, `superseded`, `rejected`.

| ID | Status | Decision | Rationale and implementation consequence |
|---|---|---|---|
| DEC-001 | accepted | V1 serves one university only. | Do not implement SaaS billing, tenant onboarding or shared multi-tenant runtime. Keep clear domain and adapter boundaries so a later product phase can revisit tenancy through an ADR. |
| DEC-002 | accepted | The reference institution is the Faculty of Information Technology, Hanoi University of Civil Engineering. | Use tenant label `HUCE Demo`; the product MUST display that it is an unofficial simulation until the university authorizes otherwise. |
| DEC-003 | accepted | The product is designed as a commercial, production-grade system. | Architecture, security, observability, tests and runbooks MUST meet production standards even when integrations and data are simulated. |
| DEC-004 | accepted | Development and demonstration use no real student records. | Use deterministic synthetic identities, schedules, tickets, room bookings and conversations. Public HUCE content may inform taxonomy and provenance but MUST NOT imply institutional endorsement. |
| DEC-005 | accepted | V1 prioritizes grounded FAQ, personal schedule, ticketing, document requests, room booking, HITL, staff queue, knowledge administration and operations metrics. | Lower-value modules are placed in the future roadmap and MUST NOT expand V1 task scope. |
| DEC-006 | accepted | V1 has four roles: student, support officer, knowledge administrator and system/operations administrator. | Guest, parent, lecturer and advisor experiences are out of scope unless a later accepted requirement adds them. |
| DEC-007 | accepted | Authentication is simulated initially but the boundary MUST support Microsoft Entra ID through OIDC Authorization Code with PKCE later. | Domain services MUST consume an internal identity/claims contract and MUST NOT depend on mock-auth implementation details. |
| DEC-008 | accepted | DeepSeek is the first production LLM provider behind a provider-neutral LLM gateway. | Provider endpoint, model and credentials are configuration. Tests MUST use a deterministic fake provider. Domain logic MUST NOT import provider SDKs directly. |
| DEC-009 | accepted | AWS is the preferred production platform. | Use a container-first design, private networking, managed data services and infrastructure as code. The exact service topology is fixed by approved ADRs. |
| DEC-010 | accepted | Simulated reference deployment may use AWS `ap-southeast-1`. | No real personal data may be deployed cross-border without a separate privacy/legal review and explicit approval. |
| DEC-011 | accepted | The system uses Next.js, FastAPI, PostgreSQL with pgvector, Redis and LangGraph. | Versions and supporting libraries are pinned in architecture/build specifications after compatibility review. |
| DEC-012 | accepted | PostgreSQL lexical search and pgvector semantic search are combined, then reranked. | Vector-only retrieval is not acceptable for identifiers, exact policy wording, form names and document numbers. |
| DEC-013 | accepted | Every answer that asserts policy or procedure MUST carry verifiable citations. | When evidence is insufficient, the system abstains, asks a bounded clarification or offers a ticket/handover. |
| DEC-014 | accepted | LLMs never receive direct database access and never perform side effects directly. | All capabilities are typed tools behind authorization, validation, idempotency and audit controls. |
| DEC-015 | accepted | Every write action requires an action preview and explicit user confirmation. | A confirmation token binds the actor, normalized payload, policy decision and expiry. Retries MUST be idempotent. |
| DEC-016 | accepted | Sensitive and emergency cases use deterministic rules plus a classifier and are handed over. | The AI does not diagnose, promise intervention or invent contacts. Until official contacts exist, use clearly marked configuration placeholders. |
| DEC-017 | accepted | Documentation is the implementation source of truth. | Gemini 3.8 Flash receives only reviewed atomic tasks that reference approved requirements and contracts. It may not rewrite its own source requirements. |
| DEC-018 | accepted | Atomic tasks default to one objective, one layer, 1-3 product files and about 150 added lines. | Tasks may exceed the guideline only through a reviewed exception. Database, backend, frontend and infrastructure changes remain separate tasks. |
| DEC-019 | accepted | Implementation agents may work continuously and up to four tasks may run in parallel when write scopes are disjoint. | A task starts only after every dependency is `accepted`; the orchestrator owns task selection and conflict prevention. |
| DEC-020 | accepted | Sensitive actions outside standing delegation require human authority. | [DEC-023](LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) supersedes per-step approval for assigned local/synthetic engineering. Production/real-data/destructive boundaries remain outside that delegation. |
| DEC-021 | accepted | Documentation is created locally first with no automatic commit or push. | Git commit, push and PR creation require a later explicit user request. |
| DEC-022 | accepted | For current synthetic M1-M3 acceptance, the human owner removes artifact/acceptance signatures and independent review, accepts primary accountability and delegates technical execution; configurations may change on comparative evidence. | Direct human decision 2026-10-06; [exact scope and controls](RAG_ACCEPTANCE_AUTHORITY_DECISION_20261006.md). Preserve evidence and verify remaining technical gates; no production or destructive authority is inferred. |
| DEC-023 | accepted | The human removes additional execution-approval checkpoints throughout this repository for assigned local/synthetic work and delegates necessary engineering and technical review. | Direct human instructions 2026-10-07; [standing authority and scope](LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md). Resolve older task/package approval fields against this decision and continue without reapproval; preserve data, history and actual technical verification. |
