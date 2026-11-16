"""Review/publish and bounded authorized discovery over immutable versions."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone

from campus247.domain.policy_graph import ReviewVerdict, TraversalBounds, fingerprint
from campus247.domain.retrieval import RetrievalContext, SimulationPolicy


class PolicyGraphError(ValueError):
    """Fixed codes only; never include inaccessible IDs, aliases or source text."""


def normalize(text):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(c) != "Mn").replace("đ", "d").split())


def structural_issues(proposal):
    issues = []
    nodes = {n.id: n for n in proposal.nodes}
    all_ids = [r.id for r in (*proposal.nodes, *proposal.edges)]
    if len(set(all_ids)) != len(all_ids):
        issues.append({"code": "DUPLICATE_ID", "target": proposal.id})
    aliases = {}
    for node in proposal.nodes:
        if node.predicate:
            predicate, text = node.predicate, normalize(node.source.quote)
            cues = {">": ("vuot qua",), ">=": ("tro len", "it nhat"),
                "<": ("duoi",), "<=": ("khong qua", "toi da"), "=": ("bang",)}
            comparator_present = bool(re.search(r"(?<![<>=])"+re.escape(predicate.comparator)+r"(?![=])", text))
            if (not re.search(r"(?<![0-9.])"+re.escape(normalize(predicate.value))+r"(?![0-9.])", text)
                    or normalize(predicate.unit) not in text
                    or not (comparator_present or any(c in text for c in cues[predicate.comparator]))):
                issues.append({"code": "PREDICATE_SOURCE_MISMATCH", "target": node.id})
        for alias in set(normalize(a) for a in (node.label, *node.aliases)):
            key = (fingerprint(node.scope.model_dump()), alias)
            if key in aliases and aliases[key] != node.id:
                issues.append({"code": "DUPLICATE_ALIAS", "target": node.id})
            aliases[key] = node.id
        if node.kind == "ConditionGroup":
            text = normalize(node.source.quote)
            cue = ("du cac dieu kien" in text or "tat ca" in text or "all" in text) if node.operator == "ALL" else (
                "mot trong" in text or "hoac" in text or "any" in text)
            prefix = normalize(re.split(r"(?m)^\s*[a-zđ]\)\s", node.source.quote, maxsplit=1)[0])
            if not cue or node.operator == "ANY" and any(cue in prefix for cue in ("du cac dieu kien", "tat ca")):
                issues.append({"code": "QUANTIFIER_SOURCE_MISMATCH", "target": node.id})
            members = [nodes.get(key) for key in node.members]
            outgoing = {e.to_id for e in proposal.edges if e.from_id == node.id and e.relation == "requires"}
            if (outgoing != set(node.members) or any(m is None or m.kind not in {"Condition", "ConditionGroup"}
                    or m.source.quote not in node.source.quote or m.scope != node.scope for m in members)):
                issues.append({"code": "INCOMPLETE_CONDITION_GROUP", "target": node.id})
            if len({m.source.quote for m in members if m is not None}) != len(members):
                issues.append({"code": "DUPLICATE_CONDITION_SPAN", "target": node.id})
            # Enumerated a/b/c/d clauses must all survive extraction, including
            # OCR's e) for c). Count only the modeled group's original span.
            enumerated = re.findall(r"(?m)^\s*[a-zđ]\)\s", node.source.quote)
            if enumerated and len(enumerated) != len(node.members):
                issues.append({"code": "INCOMPLETE_CONDITION_GROUP", "target": node.id})
    adjacency = {key: [] for key in nodes}
    signatures = set()
    for edge in proposal.edges:
        signature = (edge.from_id, edge.to_id, edge.relation, fingerprint(edge.scope.model_dump()),
            edge.source.chunk_id, fingerprint(edge.interval.model_dump(mode="json")))
        if signature in signatures:
            issues.append({"code": "DUPLICATE_EDGE", "target": edge.id})
        signatures.add(signature)
        left, right = nodes.get(edge.from_id), nodes.get(edge.to_id)
        if left is None or right is None:
            issues.append({"code": "DANGLING_EDGE", "target": edge.id})
            continue
        if left.scope != edge.scope or right.scope != edge.scope:
            issues.append({"code": "EDGE_SCOPE_MISMATCH", "target": edge.id})
        if edge.relation == "requires" and left.kind == "ConditionGroup" and right.id not in left.members:
            issues.append({"code": "INCOMPLETE_CONDITION_GROUP", "target": edge.id})
        if edge.interval.status == "reviewed":
            quote = edge.interval.basis.quote
            for date in (edge.interval.start, edge.interval.end):
                if date is not None and not any(token in quote for token in (
                        date.strftime("%Y-%m-%d"), date.strftime("%d/%m/%Y"),
                        f"{date.day}/{date.month}/{date.year}")):
                    issues.append({"code": "EFFECTIVE_DATE_SOURCE_MISMATCH", "target": edge.id})
        adjacency[left.id].append(right.id)
    # Iterative DFS; hostile candidate depth cannot overflow Python recursion.
    color = {}
    for start in nodes:
        if color.get(start):
            continue
        stack = [(start, False)]
        while stack:
            key, closing = stack.pop()
            if closing:
                color[key] = 2
                continue
            if color.get(key) == 1:
                issues.append({"code": "DIRECTED_CYCLE", "target": key})
                continue
            if color.get(key) == 2:
                continue
            color[key] = 1
            stack.append((key, True))
            stack.extend((child, False) for child in adjacency[key])
    groups = {}
    for edge in proposal.edges:
        if edge.conflict_key:
            groups.setdefault((edge.conflict_key, fingerprint(edge.scope.model_dump())), []).append(edge)
    for group in groups.values():
        for i, left in enumerate(group):
            for right in group[i+1:]:
                if left.to_id == right.to_id:
                    continue
                a, b = left.interval, right.interval
                if (a.status == "unknown" or b.status == "unknown" or
                    (a.end is None or b.start < a.end) and (b.end is None or a.start < b.end)):
                    issues.append({"code": "TEMPORAL_CONFLICT", "target": right.id})
    return issues


class PolicyGraphService:
    def __init__(self, repository, reader, *, index_fingerprint, source_fingerprint, graph_id=None):
        self.repository, self.reader = repository, reader
        self.index_fingerprint, self.source_fingerprint = index_fingerprint, source_fingerprint
        self.graph_id = graph_id

    @property
    def snapshot(self):
        manifest = self.repository.publication(self.graph_id) if self.graph_id else None
        return {"graph_id": self.graph_id, "publication": fingerprint(manifest) if manifest else None,
            "index_fingerprint": self.index_fingerprint, "source_fingerprint": self.source_fingerprint}

    @staticmethod
    def context(context):
        if not isinstance(context, RetrievalContext):
            raise PolicyGraphError("GRAPH_AUTHORIZATION_UNAVAILABLE")
        try:
            return RetrievalContext.from_dict(context.to_dict())
        except ValueError:
            raise PolicyGraphError("GRAPH_AUTHORIZATION_UNAVAILABLE") from None

    def proposal(self, graph_id, context, *, review=False):
        context = self.context(context)
        proposal = self.repository.get(graph_id)
        if proposal is None:
            raise PolicyGraphError("GRAPH_UNAVAILABLE")
        if not any(n.scope.permits(context) for n in proposal.nodes):
            raise PolicyGraphError("GRAPH_UNAVAILABLE")
        if review and (not all(n.scope.permits(context) for n in proposal.nodes)
                or not all(e.scope.permits(context) for e in proposal.edges)):
            raise PolicyGraphError("GRAPH_UNAVAILABLE")
        if (proposal.index_fingerprint != self.index_fingerprint or
                proposal.source_fingerprint != self.source_fingerprint):
            raise PolicyGraphError("GRAPH_SNAPSHOT_MISMATCH")
        if review and not all(n.scope.permits(context) for n in proposal.nodes):
            raise PolicyGraphError("GRAPH_UNAVAILABLE")
        return proposal

    async def source(self, ref, context, reader=None):
        # A public reader retains legacy citation rows for old conversations.
        # Those bytes remain readable there, but cannot enter a graph bound to
        # the current source/index snapshot merely because their hash is valid.
        current_rows = getattr(self.reader, "rows", None)
        if isinstance(current_rows, list) and not any(
                (row["source_id"], row["document_version_id"], row["chunk_id"],
                 row["quote_span_hash"].removeprefix("sha256:"), row["locator"]) ==
                (ref.source_id, ref.document_version_id, ref.chunk_id, ref.content_sha256, ref.locator)
                for row in current_rows):
            return None
        try:
            excerpt = await (reader or self.reader).read(ref.source_id, ref.document_version_id,
                ref.chunk_id, context=context)
        except (PermissionError, ValueError):
            return None
        except Exception as failure:
            from campus247.application.single_agent.resources import AgentStop
            if isinstance(failure, AgentStop):
                raise
            raise PolicyGraphError("GRAPH_SOURCE_UNAVAILABLE") from None
        if excerpt is None:
            return None
        if (excerpt.source_id != ref.source_id or excerpt.document_version_id != ref.document_version_id
                or excerpt.chunk_id != ref.chunk_id or excerpt.locator != ref.locator
                or hashlib.sha256(excerpt.content_text.encode()).hexdigest() != ref.content_sha256
                or excerpt.content_sha256 != ref.content_sha256 or ref.quote not in excerpt.content_text):
            raise PolicyGraphError("GRAPH_SOURCE_MISMATCH")
        if (excerpt.effective_from.tzinfo is None or excerpt.effective_from > context.effective_at
                or excerpt.effective_until is not None and excerpt.effective_until <= context.effective_at
                or excerpt.source_status not in {"CURRENT", "SYNTHETIC"}
                or excerpt.source_status == "SYNTHETIC" and context.simulation_policy != SimulationPolicy.ALLOW_LABELED):
            return None
        return excerpt

    @staticmethod
    def reviewer(context, reviewer):
        if (context.authorized_scope.actor_id != reviewer or not
                context.authorized_scope.roles & {"KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"}):
            raise PolicyGraphError("GRAPH_REVIEW_DENIED")

    async def validate(self, graph_id, context):
        proposal = self.proposal(graph_id, context, review=True)
        issues = structural_issues(proposal)
        for row in (*proposal.nodes, *proposal.edges):
            refs = [row.source]
            if hasattr(row, "interval") and row.interval.basis:
                refs.append(row.interval.basis)
            for ref in refs:
                try:
                    if await self.source(ref, context) is None:
                        issues.append({"code": "SOURCE_UNAVAILABLE", "target": row.id})
                except PolicyGraphError as failure:
                    issues.append({"code": str(failure), "target": row.id})
        return issues

    async def review(self, graph_id, context, *, target, verdict, note, expected_revision):
        self.reviewer(context, context.authorized_scope.actor_id)
        proposal = self.proposal(graph_id, context, review=True)
        row = next((r for r in (*proposal.nodes, *proposal.edges) if r.id == target), None)
        if row is None or not row.scope.permits(context):
            raise PolicyGraphError("GRAPH_UNAVAILABLE")
        if verdict == "approved":
            issues = await self.validate(graph_id, context)
            if issues:
                raise PolicyGraphError("GRAPH_VALIDATION_FAILED")
        value = ReviewVerdict(target=target, verdict=verdict, note=note,
            reviewer=context.authorized_scope.actor_id, at=datetime.now(timezone.utc))
        return self.repository.review(graph_id, value, expected_revision=expected_revision)

    def publication_preview(self, graph_id, context, *, expected_revision, session_binding=""):
        self.reviewer(context, context.authorized_scope.actor_id)
        proposal = self.proposal(graph_id, context, review=True)
        history = self.repository.reviews(graph_id)
        if not history or history[-1][0] != expected_revision:
            raise PolicyGraphError("GRAPH_REVIEW_INCOMPLETE")
        return {"graph_id": graph_id, "revision": expected_revision,
            "proposal_sha256": fingerprint(proposal.model_dump(mode="json")),
            "review_sha256": fingerprint([r.model_dump(mode="json") for _, r in history]),
            "publisher": context.authorized_scope.actor_id,
            "session_binding": session_binding,
            "scope": context.to_dict()["authorized_scope"],
            "effect": "publish_immutable_source_discovery_version"}

    async def publish(self, graph_id, context, *, expected_revision, confirmation, session_binding=""):
        self.reviewer(context, context.authorized_scope.actor_id)
        preview = self.publication_preview(graph_id, context, expected_revision=expected_revision, session_binding=session_binding)
        if confirmation != fingerprint(preview):
            raise PolicyGraphError("GRAPH_CONFIRMATION_CHANGED")
        proposal = self.proposal(graph_id, context, review=True)
        if proposal.author == context.authorized_scope.actor_id:
            raise PolicyGraphError("AUTHOR_CANNOT_PUBLISH")
        history = self.repository.reviews(graph_id)
        latest = {review.target: review for _, review in history}
        if (not history or history[-1][0] != expected_revision or
            any(latest.get(row.id) is None or latest[row.id].verdict != "approved"
                for row in (*proposal.nodes, *proposal.edges))):
            raise PolicyGraphError("GRAPH_REVIEW_INCOMPLETE")
        if await self.validate(graph_id, context):
            raise PolicyGraphError("GRAPH_VALIDATION_FAILED")
        manifest = {"schema_version": 1, "graph_id": graph_id,
            "proposal_sha256": fingerprint(proposal.model_dump(mode="json")),
            "review_sha256": fingerprint([r.model_dump(mode="json") for _, r in history]),
            "review_revision": expected_revision, "index_fingerprint": proposal.index_fingerprint,
            "source_fingerprint": proposal.source_fingerprint,
            "publisher": context.authorized_scope.actor_id, "published_at": datetime.now(timezone.utc).isoformat(),
            "confirmation_sha256": confirmation,
            "interval_semantics": "[start,end)", "legal_effective_dates_unknown":
                any(e.interval.status == "unknown" for e in proposal.edges),
            "use": "source_discovery_only_not_business_rules"}
        self.repository.publish(graph_id, manifest, expected_revision=expected_revision)
        return manifest

    async def review_view(self, graph_id, context):
        self.reviewer(context, context.authorized_scope.actor_id)
        proposal = self.proposal(graph_id, context, review=True)
        # Revalidate all sources before returning counts/aliases/errors/raw text.
        for row in (*proposal.nodes, *proposal.edges):
            if await self.source(row.source, context) is None:
                raise PolicyGraphError("GRAPH_UNAVAILABLE")
        history = self.repository.reviews(graph_id)
        return {"proposal": proposal.model_dump(mode="json"), "raw_proposal": self.repository.raw(graph_id),
            "issues": await self.validate(graph_id, context),
            "reviews": [{"revision": rev, **v.model_dump(mode="json")} for rev, v in history],
            "revision": history[-1][0] if history else 0,
            "publication": self.repository.publication(graph_id)}

    async def traverse(self, *, context, query="", seeds=(), bounds=None, reader=None):
        context = self.context(context)
        bounds = bounds or TraversalBounds()
        if not self.graph_id or not self.repository.publication(self.graph_id):
            return {"status": "unavailable", "code": "GRAPH_NOT_PUBLISHED", "nodes": [], "edges": [], "sources": []}
        try:
            proposal = self.proposal(self.graph_id, context)
        except PolicyGraphError as failure:
            if str(failure) != "GRAPH_UNAVAILABLE":
                raise
            return {"status": "empty", "nodes": [], "edges": [], "sources": []}
        # Only current, reviewed graph versions. Historical mode is deliberately
        # not silently inferred from user query or a client-supplied timestamp.
        nodes = {n.id: n for n in proposal.nodes if n.scope.permits(context)}
        history = self.repository.reviews(proposal.id)
        latest = {v.target: v for _, v in history}
        manifest = self.repository.publication(proposal.id)
        if (manifest["proposal_sha256"] != fingerprint(proposal.model_dump(mode="json")) or
                manifest["review_sha256"] != fingerprint([v.model_dump(mode="json") for _, v in history])):
            raise PolicyGraphError("GRAPH_SNAPSHOT_MISMATCH")
        eligible = [e for e in proposal.edges if e.scope.permits(context) and e.interval.contains(context.effective_at)
            and e.from_id in nodes and e.to_id in nodes
            and all(key in latest and latest[key].verdict == "approved" for key in (e.id, e.from_id, e.to_id))]
        cache, reads = {}, 0

        async def allowed(ref):
            nonlocal reads
            key = (ref.source_id, ref.document_version_id, ref.chunk_id, ref.content_sha256,
                fingerprint(ref.locator))
            if key not in cache:
                if reads >= bounds.source_reads:
                    return None
                reads += 1
                cache[key] = await self.source(ref, context, reader)
            excerpt = cache[key]
            if excerpt is not None and ref.quote not in excerpt.content_text:
                raise PolicyGraphError("GRAPH_SOURCE_MISMATCH")
            return excerpt

        selected, queue = {}, deque()
        text = normalize(query)
        seed_set = set(seeds[:64])
        for node in nodes.values():
            if (node.source.chunk_id in seed_set or node.id in seed_set or
                any(normalize(alias) in text for alias in (node.label, *node.aliases))):
                if len(selected) >= bounds.nodes:
                    break
                if await allowed(node.source):
                    selected[node.id] = node
                    queue.append((node.id, 0))
        edges, source_rows, visited = {}, {}, set()
        while queue:
            key, depth = queue.popleft()
            if key in visited:
                continue
            visited.add(key)
            if depth >= bounds.depth:
                continue
            for edge in eligible:
                if edge.from_id != key and edge.to_id != key:
                    continue
                other = edge.to_id if edge.from_id == key else edge.from_id
                if len(edges) >= bounds.edges or other not in selected and len(selected) >= bounds.nodes:
                    continue
                # Source eligibility precedes neighbor count and suggestion.
                excerpt = await allowed(edge.source)
                neighbor = await allowed(nodes[other].source)
                basis = await allowed(edge.interval.basis) if edge.interval.basis else True
                if not excerpt or not neighbor or not basis:
                    continue
                edges[edge.id] = edge
                for original in (excerpt, neighbor):
                    row = asdict(original)
                    row["effective_from"] = original.effective_from.isoformat()
                    row["effective_until"] = original.effective_until.isoformat() if original.effective_until else None
                    row["quote_span_hash"] = row.pop("content_sha256")
                    row["section_path"] = original.locator.get("section_path")
                    source_rows[original.chunk_id] = row
                if other not in selected:
                    selected[other] = nodes[other]
                    queue.append((other, depth+1))
        # Drop isolated seeds: they are discovery anchors, not source evidence.
        connected = {key for edge in edges.values() for key in (edge.from_id, edge.to_id)}
        return {"status": "completed" if edges else "empty", **({"graph_id": proposal.id} if edges else {}),
            "nodes": [n.model_dump(mode="json") for key, n in selected.items() if key in connected],
            "edges": [{**e.model_dump(mode="json"), "review": latest[e.id].model_dump(mode="json")}
                for e in edges.values()], "sources": list(source_rows.values()),
            "bounds": bounds.model_dump(), "legal_effective_dates_unknown": any(e.interval.status == "unknown" for e in edges.values())}
