"""Deterministic, scoped business-edition resolution; never latest-upload wins.

Admission, current authorization and release/citation binding remain separate
checks. An admin preview does not turn unverified candidates into serving data.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from itertools import product
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from campus247.application.knowledge.document_identity import (
    ApplicabilityScope, EditionIdentity, EffectiveInterval, SourceWitness, StrictModel,
)


class ResolutionQuery(StrictModel):
    family_ids: tuple[UUID, ...] = Field(min_length=1, max_length=30)
    at_day: date
    known_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    programmes: tuple[str, ...] = ()
    cohorts: tuple[str, ...] = ()
    academic_years: tuple[str, ...] = ()

    @model_validator(mode="after")
    def check_time(self):
        if self.known_at.tzinfo is None or self.known_at.utcoffset() is None:
            raise ValueError("Knowledge time needs an explicit timezone")
        if any(not value.strip() for name in ("programmes", "cohorts", "academic_years") for value in getattr(self, name)):
            raise ValueError("Scope members must be explicit")
        if max(1, len(self.programmes))*max(1, len(self.cohorts))*max(1, len(self.academic_years)) > 128:
            raise ValueError("Scope query requires a smaller explicit partition")
        return self


class EditionCandidate(StrictModel):
    edition_id: UUID
    identity: EditionIdentity
    recorded_at: datetime
    # Unit IDs are versioned evidence occurrences. '*' means no verified unit map.
    unit_ids: frozenset[str] = frozenset({"*"})
    currently_authorized: bool = True
    blocking_issues: tuple[str, ...] = ()
    dependencies: dict[str, frozenset[str]] = Field(default_factory=dict)
    dependency_graph_verified: bool = False

    @model_validator(mode="after")
    def check_time(self):
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("Recorded time needs an explicit timezone")
        return self


class EditionRelation(StrictModel):
    from_edition: UUID
    to_edition: UUID
    kind: Literal["REPLACES", "PARTIAL_AMEND", "SUPPLEMENTS", "ALIAS"]
    effective: EffectiveInterval
    recorded_at: datetime
    witness: SourceWitness
    target_unit_ids: frozenset[str] = frozenset()
    decision_state: Literal["PROPOSED", "VERIFIED"] = "PROPOSED"
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def check_relation(self):
        if self.from_edition == self.to_edition:
            raise ValueError("A business relation cannot target itself")
        if self.kind == "PARTIAL_AMEND" and not self.target_unit_ids:
            raise ValueError("Partial amendment requires exact target unit occurrences")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("Relation recorded time needs an explicit timezone")
        return self


def interval_reason(interval, day):
    if interval.from_day is None:
        return "EFFECTIVE_START_UNKNOWN"
    if day < interval.from_day:
        return "FUTURE_EDITION"
    if interval.until_day is not None and day >= interval.until_day:
        return "EXPIRED_FOR_QUERY"
    if interval.end_kind == "UNKNOWN":
        return "EFFECTIVE_END_UNKNOWN"
    return None


def scope_reason(scope: ApplicabilityScope, atom):
    missing = []
    for name, value in atom.items():
        axis = getattr(scope, name)
        if axis.kind == "UNKNOWN":
            missing.append(name)
        elif axis.kind == "VALUES":
            if value is None:
                missing.append("query."+name)
            elif value not in axis.values:
                return "OUTSIDE_SCOPE", []
    return ("SCOPE_NEEDS_INFORMATION", missing) if missing else (None, [])


def cyclic_component(graph):
    """Iterative cycle detection, confined to related replacement components."""
    colours, cyclic = {}, set()
    for root in graph:
        if colours.get(root):
            continue
        path, positions = [root], {root: 0}
        colours[root] = 1
        stack = [(root, iter(graph.get(root, ())))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop(); path.pop(); positions.pop(node); colours[node] = 2
            elif colours.get(child) == 1:
                cyclic.update(path[positions[child]:])
            elif not colours.get(child):
                positions[child] = len(path); path.append(child); colours[child] = 1
                stack.append((child, iter(graph.get(child, ()))))
    adjacency = {}
    for source, targets in graph.items():
        for target in targets:
            adjacency.setdefault(source, set()).add(target)
            adjacency.setdefault(target, set()).add(source)
    affected, pending = set(cyclic), list(cyclic)
    while pending:
        for neighbour in adjacency.get(pending.pop(), ()):
            if neighbour not in affected:
                affected.add(neighbour); pending.append(neighbour)
    return affected


def resolve_editions(query: ResolutionQuery, candidates, relations=()):
    if len({c.edition_id for c in candidates}) != len(candidates):
        raise ValueError("One immutable candidate per business edition is required")
    segments = []
    axes = ("programmes", "cohorts", "academic_years")
    for values in product(*(getattr(query, axis) or (None,) for axis in axes)):
        atom = dict(zip(axes, values))
        selected, excluded, issues = {}, [], []
        family_uncertain = set()
        for candidate in candidates:
            identifier, identity = str(candidate.edition_id), candidate.identity
            family = str(identity.family_id)
            if identity.family_id not in query.family_ids:
                continue
            if not candidate.currently_authorized:
                excluded.append({"edition_id": identifier, "reason": "CURRENT_AUTHORIZATION_DENIED"}); continue
            if candidate.recorded_at > query.known_at:
                excluded.append({"edition_id": identifier, "reason": "NOT_KNOWN_AT_QUERY_TIME"}); continue
            reason, missing = scope_reason(identity.scope, atom)
            if reason == "OUTSIDE_SCOPE":
                excluded.append({"edition_id": identifier, "reason": reason}); continue
            if reason:
                issues.append({"edition_id": identifier, "reason": reason, "fields": missing})
                family_uncertain.add(family); continue
            temporal = interval_reason(identity.effective, query.at_day)
            if temporal in {"FUTURE_EDITION", "EXPIRED_FOR_QUERY"}:
                excluded.append({"edition_id": identifier, "reason": temporal}); continue
            if identity.verification != "VERIFIED" or temporal or candidate.blocking_issues:
                issues.append({"edition_id": identifier, "reason": temporal or ("DEPENDENCY_UNRESOLVED" if candidate.blocking_issues else "IDENTITY_UNVERIFIED"),
                    "fields": list(candidate.blocking_issues)})
                family_uncertain.add(family); continue
            selected[identifier] = {"edition_id": identifier, "family_id": family, "unit_ids": set(candidate.unit_ids)}
        for relation in relations:
            new, old = str(relation.from_edition), str(relation.to_edition)
            if (relation.recorded_at <= query.known_at and new in selected and old not in selected
                and relation.kind == "PARTIAL_AMEND" and interval_reason(relation.effective, query.at_day) not in {"FUTURE_EDITION", "EXPIRED_FOR_QUERY"}):
                issues.append({"reason": "AMENDMENT_CONTEXT_UNAVAILABLE", "edition_ids": [new, old]})
                family_uncertain.add(selected[new]["family_id"])
        applicable = [r for r in relations if r.recorded_at <= query.known_at
            and str(r.from_edition) in selected and str(r.to_edition) in selected and interval_reason(r.effective, query.at_day) not in {"FUTURE_EDITION", "EXPIRED_FOR_QUERY"}]
        compatible = set()
        removed = set()
        replacements = {}
        by_id = {str(candidate.edition_id): candidate for candidate in candidates}
        for relation in applicable:
            new, old = str(relation.from_edition), str(relation.to_edition)
            family = selected[new]["family_id"]
            if relation.decision_state != "VERIFIED" or interval_reason(relation.effective, query.at_day):
                issues.append({"reason": "RELATION_UNVERIFIED", "edition_ids": [new, old]})
                family_uncertain.update((family, selected[old]["family_id"])); continue
            compatible.add(frozenset((new, old)))
            if relation.kind == "REPLACES":
                replacements.setdefault(new, set()).add(old); removed.add(old)
            elif relation.kind == "PARTIAL_AMEND":
                if not by_id[new].dependency_graph_verified or not by_id[old].dependency_graph_verified:
                    issues.append({"reason": "DEPENDENCY_GRAPH_UNVERIFIED", "edition_ids": [new, old]})
                    family_uncertain.update((family, selected[old]["family_id"]))
                elif "*" in selected[old]["unit_ids"] or not relation.target_unit_ids.issubset(selected[old]["unit_ids"]):
                    issues.append({"reason": "AMENDMENT_TARGET_UNRESOLVED", "edition_ids": [new, old]})
                    family_uncertain.update((family, selected[old]["family_id"]))
                else:
                    selected[old]["unit_ids"].difference_update(relation.target_unit_ids)
        cycle_affected = cyclic_component(replacements)
        if cycle_affected:
            issues.append({"reason": "REPLACEMENT_CYCLE", "edition_ids": sorted(cycle_affected)})
            family_uncertain.update(selected[identifier]["family_id"] for identifier in cycle_affected)
        for old in removed:
            excluded.append({"edition_id": old, "reason": "EXPLICIT_REPLACEMENT"})
            selected.pop(old, None)
        all_units = set().union(*(row["unit_ids"] for row in selected.values()))
        for identifier, row in selected.items():
            for unit in row["unit_ids"]:
                missing = by_id[identifier].dependencies.get(unit, frozenset()) - all_units
                if missing:
                    family_uncertain.add(row["family_id"])
                    issues.append({"reason": "EVIDENCE_DEPENDENCY_MISSING", "edition_id": identifier, "unit_id": unit, "missing": sorted(missing)})
        values = list(selected.values())
        for index, first in enumerate(values):
            for second in values[index+1:]:
                if first["family_id"] == second["family_id"] and frozenset((first["edition_id"], second["edition_id"])) not in compatible:
                    issues.append({"reason": "EDITION_CONFLICT", "edition_ids": [first["edition_id"], second["edition_id"]]})
                    family_uncertain.add(first["family_id"])
        for row in selected.values():
            if row["family_id"] in family_uncertain:
                excluded.append({"edition_id": row["edition_id"], "reason": "FAMILY_CONCLUSION_BLOCKED"})
        # A condition supplied by another blocked family cannot keep a unit
        # apparently complete. Propagate the missing dependency to a fixed point.
        changed = True
        while changed:
            changed = False
            available_units = set().union(*(row["unit_ids"] for row in selected.values() if row["family_id"] not in family_uncertain))
            for identifier, row in selected.items():
                if row["family_id"] in family_uncertain:
                    continue
                for unit in row["unit_ids"]:
                    missing = by_id[identifier].dependencies.get(unit, frozenset()) - available_units
                    if missing:
                        family_uncertain.add(row["family_id"]); changed = True
                        issues.append({"reason": "EVIDENCE_DEPENDENCY_MISSING", "edition_id": identifier, "unit_id": unit, "missing": sorted(missing)})
        chosen = [{**row, "unit_ids": sorted(row["unit_ids"])} for row in selected.values() if row["family_id"] not in family_uncertain and row["unit_ids"]]
        segments.append({"scope": atom, "selected": chosen, "excluded": excluded, "issues": issues})
    return {"at_day": query.at_day.isoformat(), "known_at": query.known_at.isoformat(), "segments": segments,
        "state": "NEEDS_INFORMATION" if any(s["issues"] for s in segments) else "RESOLVED" if any(s["selected"] for s in segments) else "NO_APPLICABLE_EDITION",
        "admission_granted": False, "serving_ack_checked": False}


async def load_resolution_state(platform, conn, query, *, admitted_only=False, member_version_ids=(), include_prepared=False):
    """Read one source-bound decision snapshot without conferring admission.

    Serving considers independently content-reviewed members and published history.
    An arbitrary unreviewed intake must not invalidate an admitted source.
    """
    from campus247.application.knowledge.platform_models import PlatformError, digest
    from campus247.application.knowledge.platform_models import json_value
    if not await conn.fetchval("SELECT to_regclass('knowledge_document_edition') IS NOT NULL"):
        raise PlatformError(503, "IDENTITY_SCHEMA_NOT_READY", "Chưa có mapping định danh phiên bản cho nguồn này.")
    rows = await conn.fetch("""SELECT e.*,NOT EXISTS(SELECT 1 FROM knowledge_version_lineage l
        JOIN knowledge_ingest_version v ON v.version_id=l.version_id WHERE l.edition_id=e.id
        AND l.tenant_id=e.tenant_id AND v.revoked_at IS NOT NULL) AS not_revoked
        FROM knowledge_document_edition e JOIN knowledge_source_scope s ON s.source_id=e.source_id AND s.tenant_id=e.tenant_id
        WHERE e.tenant_id=$1 AND e.source_id=ANY($2::uuid[]) ORDER BY e.recorded_at,e.id""", platform.repo.tenant, list(query.family_ids))
    admitted = []
    if admitted_only:
        admitted = await conn.fetch("""SELECT l.edition_id,x.version_id,x.rendition_sha256,x.metadata_sha256,
            x.revoked_at FROM knowledge_version_lineage l
            JOIN knowledge_ingest_version x ON x.version_id=l.version_id AND x.tenant_id=l.tenant_id
            JOIN document_version v ON v.id=x.version_id
            JOIN knowledge_document_edition e ON e.id=l.edition_id AND e.tenant_id=l.tenant_id
            WHERE l.tenant_id=$1 AND e.source_id=ANY($2::uuid[]) AND x.review_state='APPROVED'
            AND (v.published_at IS NOT NULL OR x.version_id=ANY($3::uuid[]) OR $4::boolean) AND EXISTS(
                SELECT 1 FROM knowledge_review rv WHERE rv.version_id=x.version_id AND rv.verdict='APPROVED'
                AND rv.reviewer_id<>x.created_by AND rv.rendition_sha256=x.rendition_sha256
                AND rv.metadata_sha256=x.metadata_sha256) ORDER BY l.edition_id,x.version_id""", platform.repo.tenant, list(query.family_ids), list(member_version_ids), include_prepared)
        admitted_ids = {row['edition_id'] for row in admitted}
        rows = [row for row in rows if row['id'] in admitted_ids]
    candidates = []
    bindings = []
    decision_history = await conn.fetchval("SELECT to_regclass('knowledge_edition_decision') IS NOT NULL")
    from campus247.application.knowledge.edition_decisions import EditionDecisions
    decisions = EditionDecisions(platform)
    for row in rows:
        identity = json_value(row["identity"])
        if digest(identity) != row["identity_sha256"]:
            raise PlatformError(409, "IDENTITY_INTEGRITY", "Định danh phiên bản không khớp binding.")
        recorded_at, blocking = row["recorded_at"], []
        if decision_history:
            decision = await conn.fetchrow("""SELECT * FROM knowledge_edition_decision WHERE edition_id=$1 AND tenant_id=$2
                AND recorded_at<=$3 ORDER BY revision DESC LIMIT 1""", row["id"], platform.repo.tenant, query.known_at)
            if decision:
                identity = json_value(decision["identity"])
                if digest(identity) != decision["identity_sha256"]:
                    raise PlatformError(409, "IDENTITY_INTEGRITY", "Quyết định định danh không khớp binding.")
                recorded_at = decision["recorded_at"]
        parsed = EditionIdentity.model_validate(identity)
        if parsed.tenant_id != platform.repo.tenant or parsed.family_id != row["source_id"]:
            raise PlatformError(409, "IDENTITY_INTEGRITY", "Định danh không thuộc nguồn hoặc tenant hiện tại.")
        if parsed.verification == "VERIFIED":
            edition = await decisions.edition(conn, row["id"])
            for witness in (parsed.identity_basis, parsed.effective.basis):
                if witness:
                    try:
                        await decisions.witness(conn, edition, witness)
                    except PlatformError as error:
                        blocking.append(error.code)
        candidates.append(EditionCandidate(edition_id=row["id"], identity=parsed,
            recorded_at=recorded_at, currently_authorized=row["not_revoked"], blocking_issues=tuple(blocking)))
        bindings.append({"edition_id": str(row["id"]), "decision_id": str(decision["id"]) if decision_history and decision else None,
            "identity_sha256": digest(identity), "recorded_at": recorded_at.isoformat()})
    relations = []
    if decision_history and candidates:
        ids = [candidate.edition_id for candidate in candidates]
        history = await conn.fetch("""SELECT DISTINCT ON (relation_id) * FROM knowledge_edition_relation_decision
            WHERE tenant_id=$1 AND recorded_at<=$2 AND (from_edition=ANY($3::uuid[]) OR to_edition=ANY($3::uuid[]))
            ORDER BY relation_id,revision DESC""", platform.repo.tenant, query.known_at, ids)
        for row in history:
            if admitted_only and row["from_edition"] not in ids:
                continue  # A new draft relation cannot invalidate a serving edition.
            payload = json_value(row["relation"])
            if digest(payload) != row["relation_sha256"]:
                raise PlatformError(409, "RELATION_INTEGRITY", "Quan hệ phiên bản không khớp binding.")
            bindings.append({"relation_id": str(row["relation_id"]), "decision_id": str(row["id"]),
                "relation_sha256": row["relation_sha256"], "decision_state": row["decision_state"]})
            if row["decision_state"] == "REJECTED":
                continue
            relation = EditionRelation.model_validate(payload).model_copy(update={"recorded_at": row["recorded_at"]})
            edition = await decisions.edition(conn, relation.from_edition)
            try:
                await decisions.witness(conn, edition, relation.witness)
                if relation.effective.basis:
                    await decisions.witness(conn, edition, relation.effective.basis)
            except PlatformError:
                relation = relation.model_copy(update={"decision_state": "PROPOSED"})
            relations.append(relation)
    candidate_ids = {candidate.edition_id for candidate in candidates}
    # Candidate validity (including re-read source witnesses) is itself bound.
    binding = {"decisions": bindings, "candidates": [c.model_dump(mode="json") | {"unit_ids": sorted(c.unit_ids),
        "dependencies": {key: sorted(value) for key, value in c.dependencies.items()}} for c in candidates],
        "relations": [r.model_dump(mode="json") | {"target_unit_ids": sorted(r.target_unit_ids)} for r in relations],
        "admitted_versions": [dict(row) | {"edition_id": str(row["edition_id"]), "version_id": str(row["version_id"]),
            "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None} for row in admitted if row["edition_id"] in candidate_ids]}
    return candidates, relations, binding, decision_history


async def preview_resolution(platform, actor, query):
    platform.admin(actor)
    async with platform.repo.transaction() as conn:
        candidates, relations, _, decision_history = await load_resolution_state(platform, conn, query)
        result = resolve_editions(query, candidates, relations)
        mapped = {candidate.identity.family_id for candidate in candidates}
        result["unmapped_families"] = [str(value) for value in query.family_ids if value not in mapped]
        if result["unmapped_families"]:
            result["state"] = "NEEDS_INFORMATION"
            result["mapping_reason"] = "LEGACY_IDENTITY_NOT_MAPPED"
        result["relation_persistence"] = "append-only decisions as of known_at" if decision_history else "schema not available; no relation inferred from upload order"
        return result
