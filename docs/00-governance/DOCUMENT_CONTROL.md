---
document_id: "DOC-GOV-CONTROL-001"
version: "1.1.0"
status: "approved"
owner: "Documentation Chief Editor"
approvers: ["Product Owner", "Architecture Owner", "Security Owner", "Quality Owner"]
last_updated: "2026-10-07"
---

# Document control policy

[DEC-023](LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) supplies standing human authority for assigned local/synthetic changes. The executor performs the affected technical review, versions the artifact and records traceability without asking for a new document-owner/product/security approval. Approval roles in the classification table describe responsibility; they do not create another execution checkpoint in this scope.

## Purpose

This policy prevents human authors and implementation agents from producing contradictory behavior. Every normative artifact MUST have a stable ID, status, owner, review evidence and traceable downstream consumers.

## Artifact lifecycle

`draft -> reviewed -> approved -> superseded`

- `draft`: incomplete and not safe for implementation.
- `reviewed`: internally checked but not yet authoritative.
- `approved`: normative and may be referenced by `ready` tasks.
- `superseded`: retained for audit but no longer authoritative.

Atomic tasks use a separate lifecycle:

`draft -> reviewed -> ready -> in_progress -> verification -> accepted | blocked | failed`

The authorized executor may record local/synthetic technical readiness or acceptance under DEC-023 after verifying dependencies and evidence. A changed workflow does not promote an artifact or task without that evidence.

## Required document header

Every normative document MUST include:

```yaml
document_id: "DOC-..."
version: "x.y.z"
status: "draft|reviewed|approved|superseded"
owner: "role"
approvers: ["role"]
last_updated: "YYYY-MM-DD"
```

## Change classification

| Class | Examples | Approval |
|---|---|---|
| Editorial | Typo, formatting, non-normative clarification | Document owner |
| Compatible | New optional field, additional test, tighter explanation without behavior change | Owner plus affected engineering reviewer |
| Behavioral | Requirement, workflow, threshold, API or state change | Product/architecture approval and traceability update |
| Security/privacy | Authorization, identity, retention, encryption, data transfer | Security/privacy approval |
| Breaking | Contract removal, schema incompatibility, destructive migration | Formal change request, migration and rollback plan |

## Agent conflict policy

An agent MUST stop and emit a structured blocker when:

- referenced artifacts are missing or not approved;
- requirement and contract disagree;
- a dependency task is not accepted;
- the change requires files outside the task allowlist;
- necessary technical dependency or architecture evidence cannot be resolved within the assigned objective;
- verification cannot be performed as specified.

The agent MUST NOT resolve a normative conflict by guessing, silently broadening scope or weakening a test/control.
