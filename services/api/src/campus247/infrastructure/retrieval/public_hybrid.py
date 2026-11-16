"""Real-model hybrid retrieval over public immutable sources, with parent evidence."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from campus247.application.conversation.followup import question_topics
from campus247.application.conversation.understanding import (
    DatedCalendarRequest,
    dated_calendar_request,
    retrieval_subqueries,
)
from campus247.application.retrieval.rerank import StrictRerankOutputValidator
from campus247.application.retrieval.programme_scope import matches_programme_scope
from campus247.application.retrieval.structure import structured_spans
from campus247.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
    RetrievalQuery,
)
from campus247.infrastructure.retrieval.public_knowledge import (
    PublicKnowledgeStore,
    normalized,
    stable_id,
    terms,
)
from campus247.ports.embedding import EmbeddingProfile, validate_embedding_vector
from campus247.ports.reranker import RerankRequest


def _calendar_source_spans(content: str, request: DatedCalendarRequest) -> tuple[str, ...]:
    # Never join unrelated paragraphs or sentences to bind a year to an event.
    # Returned strings remain exact source excerpts, within the reranking cap.
    return tuple(span.text for passage in re.split(r"\n\s*\n|(?<=[.!?;])\s+", content)
                 for span in structured_spans(passage, max_chars=420, overlap_chars=40)
                 if request.matches_source_span(span.text))


def _program_credit_span(text: str) -> bool:
    """Identify a stated program total, excluding semester loads/GPA thresholds."""
    return bool(re.search(
        r"(?:chuong trinh\s+(?:dao tao\s+)?(?:gom|co)|tong (?:so )?khoi luong|"
        r"khoi luong (?:toan khoa|chuong trinh))[^.!?\n]{0,100}\b\d{2,3}\s+tin chi\b|"
        r"tong (?:so )?tin chi\s*(?:la|:)?\s*\d{2,3}\b|"
        r"\btong\s*:\s*\d{2,3}\s*(?:tc|tin chi)\b",
        normalized(text)))


def _schedule_locator_match(query: str, row: dict) -> bool:
    """Discover an explicitly requested schedule slot from its reviewed locator.

    A conflict note can mention other speakers and times. It cannot establish
    that its containing row is the slot requested by the reader.
    """
    query=normalized(query); locator=normalized(row['section_path'])
    committee=re.search(r'\btieu ban\s+(\d+)\b',query)
    times=re.findall(r'\b(\d{1,2})(?:h|:)(\d{2})\b',query)
    if 'chuong trinh' not in query or not committee or not times:
        return False
    if not re.search(r'\btieu ban\s+'+committee[1]+r'\b',locator):
        return False
    slot=re.search(r'(\d{1,2})(?:h|:)(\d{2})\s*[–-]',locator)
    if not slot or (int(slot[1]),int(slot[2]))!=(int(times[0][0]),int(times[0][1])):
        return False
    if 'trong ky yeu' in query and 'chuong trinh trong ky yeu' not in locator:
        return False
    if 'ban roi' in query or 'roi 3 trang' in query:
        if 'ban roi' not in normalized(row['title']):
            return False
    return True


def _annex_locator_match(query: str, row: dict) -> bool:
    """Match an explicitly named notice and annex row, including its full number."""
    query=normalized(query); locator=normalized(row['section_path'])
    notice=re.search(r'\bthong bao\s*(\d+)\b',query)
    requested=re.search(r'\bphu luc\s*[—-]?\s*(iii|ii|iv|i|v)\.(\d+(?:\.\d+)*)\b',query)
    actual=re.search(r'\bphu luc\s*[—-]?\s*(iii|ii|iv|i|v)\.(\d+(?:\.\d+)*)\b',locator)
    return bool(notice and requested and actual and requested.groups()==actual.groups()
                and re.search(r'\bthong bao\s*'+notice[1]+r'\b',locator))


@dataclass(frozen=True)
class PublicRetrievalPolicy:
    child_chars: int = 1000
    lexical_k: int = 24
    semantic_k: int = 24
    fusion_k: int = 12
    parent_k: int = 4
    context_bytes: int = 15000
    query_limit: int = 3
    deadline_seconds: float = 12.0
    # Raw logits are rankings, not calibrated evidence confidence. An absolute
    # cut-off is optional and must be calibrated on the domain before use.
    min_rerank_logit: float | None = None

    def __post_init__(self):
        if (not 200 <= self.child_chars <= 1400 or not 1 <= self.query_limit <= 3
                or not 1 <= self.parent_k <= 8 or not 1000 <= self.context_bytes <= 18000
                or not 1 <= self.fusion_k <= 20 or not 1 <= self.lexical_k <= 50
                or not 1 <= self.semantic_k <= 50 or not 0 < self.deadline_seconds <= 20
                or self.min_rerank_logit is not None and not math.isfinite(self.min_rerank_logit)):
            raise ValueError("invalid public retrieval policy")


class PublicHybridKnowledgeStore(PublicKnowledgeStore):
    """Authorization/temporal filtering precedes both rankings and every requery.

    Children are index records only. Returned evidence and citation readback
    remain exact original parent records, including conditions and exceptions.
    No model-generated context is accepted as source text.
    """

    def __init__(self, *args, embed_query, embedding_profile: EmbeddingProfile,
                 embedding_artifact_sha256: str, reranker, policy=None, diagnostics=None, **kwargs):
        super().__init__(*args, **kwargs)
        if (not callable(embed_query) or not isinstance(embedding_profile, EmbeddingProfile)
                or not callable(getattr(reranker, "rerank", None))
                or re.fullmatch(r"[0-9a-f]{64}", embedding_artifact_sha256) is None
                or embedding_artifact_sha256 == "0" * 64):
            raise ValueError("real model bindings required")
        self.embed_query = embed_query
        self.embedding_profile = embedding_profile
        self.reranker = reranker
        self.policy = policy or PublicRetrievalPolicy()
        self.diagnostics = diagnostics
        self.children = []
        for parent_index, parent in enumerate(self.rows):
            aliases = []
            for entry in self.faq_index.entries if self.faq_index else ():
                if any(source["url"] == parent["canonical_uri"] and
                       (source["pdf_page"] is None and parent["page_start"] is None or
                        source["pdf_page"] is not None and parent["page_start"] is not None and
                        parent["page_start"] <= source["pdf_page"] <= parent["page_end"]) for source in entry["sources"]):
                    aliases.append(entry["question"][:140])
            alias_text = "\n".join(dict.fromkeys(aliases))[:500]
            prefix = f"{parent['title']}\n{parent['section_path']}\nCâu hỏi liên quan: {alias_text}\n"
            for span in structured_spans(parent["content_text"], max_chars=self.policy.child_chars, overlap_chars=100):
                child_id = stable_id(parent["chunk_id"] + f":{span.start}:{span.end}:structure-v1")
                self.children.append({"id": child_id, "parent": parent_index, "start": span.start,
                                      "end": span.end, "text": span.text, "index_text": prefix + span.text})
        binding = {"embedding": embedding_profile.model_id, "revision": embedding_profile.model_revision,
                   "artifact_sha256": embedding_artifact_sha256, "dimension": embedding_profile.dimension,
                   "chunking": "structure-v1", "child_chars": self.policy.child_chars,
                   "children": [(c["id"], hashlib.sha256(c["index_text"].encode()).hexdigest()) for c in self.children]}
        self.fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
        self.vectors = None
        self.term_counts = [Counter(terms(c["index_text"])) for c in self.children]
        self.term_df = Counter(term for counts in self.term_counts for term in counts)
        self.term_lengths = [sum(c.values()) for c in self.term_counts]
        self.average_length = sum(self.term_lengths) / max(1, len(self.term_lengths))
        self._query_vectors = {}
        self._search_lock = asyncio.Lock()

    def load_vectors(self, manifest: dict):
        if (manifest.get("fingerprint") != self.fingerprint
                or manifest.get("model_id") != self.embedding_profile.model_id
                or manifest.get("model_revision") != self.embedding_profile.model_revision
                or manifest.get("child_ids") != [c["id"] for c in self.children]
                or len(manifest.get("vectors", [])) != len(self.children)):
            raise ValueError("index corpus/model/chunking mismatch")
        self.vectors = tuple(validate_embedding_vector(v, self.embedding_profile).values for v in manifest["vectors"])

    async def build_vectors(self) -> dict:
        # The caller publishes this manifest exclusively only after all real
        # model outputs validate. A partial build never replaces a usable index.
        vectors = []
        for child in self.children:
            vector = await self.embed_query(child["index_text"])
            vectors.append(list(validate_embedding_vector(vector.values, self.embedding_profile,
                model_id=vector.model_id, model_revision=vector.model_revision).values))
        manifest = {"fingerprint": self.fingerprint, "child_ids": [c["id"] for c in self.children],
                    "vectors": vectors, "model_id": self.embedding_profile.model_id,
                    "model_revision": self.embedding_profile.model_revision,
                    "contextual_index": "trusted_title_section_and_source_bound_question_aliases", "source_text_unchanged": True}
        self.load_vectors(manifest)
        return manifest

    def _eligible(self, context: RetrievalContext) -> set[int]:
        self._authorized(context)
        RetrievalContext.from_dict(context.to_dict())
        at = context.effective_at
        return {index for index, row in enumerate(self.rows) if row["source_status"] == "CURRENT"
                and (not row.get("effective_from") or datetime.fromisoformat(row["effective_from"]) <= at)
                and (not row.get("effective_until") or at < datetime.fromisoformat(row["effective_until"]))}

    def _lexical(self, query: str, eligible: set[int], *, eligible_children: set[int] | None = None) -> list[int]:
        stop = {"toi", "minh", "em", "ban", "cho", "hoi", "la", "va", "cua", "co", "duoc",
                "khong", "nhu", "the", "nao", "muon", "can", "xin", "ve", "bao", "nhieu"}
        query_terms = set(terms(query)) - stop
        aliases = self.faq_index.source_matches(query) if self.faq_index else []
        n, scores = len(self.children), []
        for index, (child, counts, length) in enumerate(zip(self.children, self.term_counts, self.term_lengths)):
            if child["parent"] not in eligible or eligible_children is not None and index not in eligible_children:
                continue
            parent = self.rows[child["parent"]]
            score = 0.0
            for term in query_terms:
                tf = counts[term]
                if tf:
                    idf = math.log(1 + (n - self.term_df[term] + .5) / (self.term_df[term] + .5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * length / self.average_length))
            if any(source["url"] == parent["canonical_uri"] and
                   (source["pdf_page"] is None and parent["page_start"] is None or
                    source["pdf_page"] is not None and parent["page_start"] is not None and
                    parent["page_start"] <= source["pdf_page"] <= parent["page_end"]) for source, _ in aliases):
                score += 8.0  # Alias is a ranking hint, never a factual answer.
            if score > 0:
                scores.append((score, index))
        return [index for _, index in sorted(scores, key=lambda v: (-v[0], self.children[v[1]]["id"]))[:self.policy.lexical_k]]

    async def _vector(self, query: str, eligible: set[int], *, eligible_children: set[int] | None = None) -> list[int]:
        if self.vectors is None:
            raise ValueError("real embedding index unavailable")
        if query not in self._query_vectors:
            vector = await self.embed_query(query)
            values = validate_embedding_vector(vector.values, self.embedding_profile,
                model_id=vector.model_id, model_revision=vector.model_revision).values
            if len(self._query_vectors) >= 128:
                self._query_vectors.pop(next(iter(self._query_vectors)))
            self._query_vectors[query] = values
        values = self._query_vectors[query]
        scores = [(sum(a * b for a, b in zip(values, vector)), index) for index, vector in enumerate(self.vectors)
                  if self.children[index]["parent"] in eligible
                  and (eligible_children is None or index in eligible_children)]
        return [index for _, index in sorted(scores, key=lambda v: (-v[0], self.children[v[1]]["id"]))[:self.policy.semantic_k]]

    def _candidate(self, index: int, query: str):
        child = self.children[index]
        row = self.rows[child["parent"]]
        spans = structured_spans(child["text"], max_chars=420, overlap_chars=40)
        relevant = set(terms(query)) - {"sinh", "vien", "em", "toi", "co", "duoc", "khong", "la", "va"}
        calendar = dated_calendar_request(query)
        excerpts = _calendar_source_spans(child["text"], calendar) if calendar else tuple(span.text for span in spans)
        if not excerpts:
            raise ValueError("calendar candidate lacks the requested year and event")
        credit_total = "tin chi tot nghiep" in question_topics(query)
        focused = max(excerpts, key=lambda text: (
            credit_total and _program_credit_span(text), len(relevant & set(terms(text)))))
        if _schedule_locator_match(query,row):
            slot=re.search(r'(?m)^\d{1,2}(?:h|:)\d{2}[^\n]*(?:\nBáo cáo viên:[^\n]*)?',child['text'])
            if slot and len(slot[0])<=420:
                # Keep the speaker beside the time/title. A generic 420-char
                # window can spend its budget on repeated document headings.
                focused=slot[0]
        clause=re.search(r'—\s*khoan\s*(\d+)\b',normalized(row['section_path']))
        if clause:
            literal=re.search(r'(?m)^'+clause[1]+r'\. [^\n]+',child['text'])
            if literal:
                focused=max(structured_spans(literal[0],max_chars=420,overlap_chars=40),
                            key=lambda span:len(relevant & set(terms(span.text)))).text
        # The cross-encoder sees a bounded exact excerpt plus trusted locator
        # context. Citation evidence still expands to the unchanged full parent.
        locator=row["section_path"][-180:] if _annex_locator_match(query,row) else row["section_path"]
        if not _annex_locator_match(query,row) and len(locator)>100:
            locator=locator[:45]+"\n"+locator[-54:]
        ranking_text = locator + "\n" + focused
        return RetrievalCandidate(row["source_id"], row["document_version_id"], child["id"], ranking_text,
            row["title"], row["issuer"], row["canonical_uri"], hashlib.sha256(ranking_text.encode()).hexdigest(),
            (row["section_path"],), page_start=row["page_start"], page_end=row["page_end"],
            version_label=row["version_label"], source_status=row["source_status"])

    async def _rank_subquery(self, subquery: str, context: RetrievalContext, candidate_limit: int, relation_lookup=None):
        eligible = self._eligible(context)  # Rechecked for every additional retrieval.
        calendar = dated_calendar_request(subquery)
        if calendar:
            eligible = {index for index in eligible if _calendar_source_spans(self.rows[index]["content_text"], calendar)}
        anchors = {"hoan thi": ("hoan thi", "vang thi"),
                   "rut hoc phan": ("rut hoc phan", "rut bot hoc phan", "huy dang ky hoc phan"),
                   "hoc cai thien": ("cai thien",), "thu vien": ("thu vien",),
                   "hai chuong trinh": ("hai chuong trinh", "chuong trinh thu hai"),
                   "khoi luong hoc tap": ("khoi luong hoc tap", "tin chi"),
                   "tin chi tot nghiep": ("khung chuong trinh", "chuong trinh gom", "tong so tin chi", "khoi luong toan khoa")}
        topics = question_topics(subquery)
        focused_topic = normalized(subquery.split(":", 1)[0]) if ":" in subquery else None
        if focused_topic in topics:
            topics = frozenset({focused_topic})
        required_terms = [term for topic in topics for term in anchors.get(topic, (topic,))]
        scoped = {i for i in eligible if any(term in normalized(self.rows[i]["content_text"])
                                           for term in required_terms)}
        if "tin chi tot nghiep" in topics:
            eligible = {i for i in eligible if matches_programme_scope(subquery, self.rows[i])}
            scoped &= eligible
            totals = {i for i in eligible if _program_credit_span(self.rows[i]["content_text"])}
            if totals:
                scoped = totals
        if scoped:
            eligible = scoped
        if "ha nam" not in normalized(subquery):
            eligible = {i for i in eligible if not ("CƠ SỞ" in self.rows[i]["content_text"]
                                                   and "HÀ NAM" in self.rows[i]["content_text"])}
        if not eligible:
            return {}, None, 0
        eligible_children = None
        if calendar:
            eligible_children = {index for index, child in enumerate(self.children)
                                 if child["parent"] in eligible and _calendar_source_spans(child["text"], calendar)}
            if not eligible_children:
                return {}, None, 0
        lexical = self._lexical(subquery, eligible, eligible_children=eligible_children)
        vector = await self._vector(subquery, eligible, eligible_children=eligible_children)
        # A source can become unavailable while an embedding call is in flight.
        # Revalidate before supplying any source excerpt to the cross-encoder.
        eligible &= self._eligible(context)
        fused = {}
        for branch in (lexical, vector):
            for rank, index in enumerate(branch, 1):
                if self.children[index]["parent"] in eligible:
                    fused[index] = fused.get(index, 0.0) + 1 / (60 + rank)
        graph_children = []
        if relation_lookup is not None:
            seeds = list(dict.fromkeys(self.rows[self.children[i]["parent"]]["chunk_id"]
                for i in sorted(fused, key=lambda i: -fused[i])))[:4]
            originals = await relation_lookup(subquery, context, seeds)
            # Only freshly read, hash-checked source bytes enter the existing
            # reranker. Keep its shared pair/deadline/native budget unchanged.
            for original in originals:
                parent = next((i for i in eligible if all(self.rows[i][key] == original.get(key)
                    for key in ("source_id", "document_version_id", "chunk_id", "quote_span_hash", "content_text"))), None)
                if parent is None:
                    continue
                children = [i for i, child in enumerate(self.children) if child["parent"] == parent
                    and (eligible_children is None or i in eligible_children)]
                if children:
                    graph_children.append(max(children, key=lambda i: len(set(terms(subquery)) & set(terms(self.children[i]["text"])))))
        selected, per_parent = [], Counter()
        # Share up to half the existing pool with graph discovery. Hybrid
        # anchors remain present and all sources undergo the same real rerank.
        # A direct program total must reach the real reranker even when generic
        # regulations share more syllables with a colloquial credit question.
        # This is candidate discovery only: no fixed total or answer is injected.
        direct_totals = [i for i in fused if "tin chi tot nghiep" in topics
                         and _program_credit_span(self.children[i]["text"])]
        direct_totals.sort(key=lambda i: (-fused[i], self.children[i]["id"]))
        schedule_parents={i for i in eligible if _schedule_locator_match(subquery,self.rows[i])}
        schedule_children=[i for i,child in enumerate(self.children) if child['parent'] in schedule_parents
                           and (eligible_children is None or i in eligible_children)]
        # Reserve one existing reranker pair for the exact source slot. Original
        # evidence, authorization, deadlines and the total pair budget stay intact.
        schedule_children.sort(key=lambda i:(self.children[i]['start'],self.children[i]['id']))
        annex_parents=[i for i in sorted(eligible) if _annex_locator_match(subquery,self.rows[i])]
        # Identical annex bytes may belong to different official source IDs.
        # Discover one child per matching parent within the existing pair cap;
        # keep both identities available for real reranking and citation readback.
        annex_children=[]
        for parent in annex_parents:
            candidates=[i for i,c in enumerate(self.children) if c['parent']==parent
                        and (eligible_children is None or i in eligible_children)]
            if candidates:
                annex_children.append(max(candidates,key=lambda i:(
                    len(set(terms(subquery)) & set(terms(self.children[i]['text']))),-self.children[i]['start'])))
        priority = annex_children[:min(2,candidate_limit)] + schedule_children[:1] + direct_totals[:1] + graph_children[:candidate_limit//2] + sorted(fused,
            key=lambda index: (-fused[index], self.children[index]["id"]))
        for index in dict.fromkeys(priority):
            parent = self.children[index]["parent"]
            if per_parent[parent] >= 2:
                continue
            selected.append(index)
            per_parent[parent] += 1
            if len(selected) == candidate_limit:
                break
        if not selected:
            return {}, None, 0
        request = RerankRequest(self.reranker.profile, RetrievalQuery(subquery), context,
                               tuple(self._candidate(index, subquery) for index in selected))
        ranked = await self.reranker.rerank(request)
        StrictRerankOutputValidator().validate(request, ranked)
        if len(ranked.ranked) != len(selected):
            raise ValueError("incomplete real reranking")
        lookup = {self.children[index]["id"]: index for index in selected}
        parent_scores, accepted = {}, []
        eligible &= self._eligible(context)
        for item in sorted(ranked.ranked, key=lambda item: (-item.score, item.chunk_id)):
            if self.policy.min_rerank_logit is not None and item.score < self.policy.min_rerank_logit:
                continue
            parent = self.children[lookup[item.chunk_id]]["parent"]
            if parent not in eligible:
                continue
            parent_scores[parent] = max(item.score, parent_scores.get(parent, -math.inf))
            if parent not in accepted:
                accepted.append(parent)
        return parent_scores, accepted[0] if accepted else None, len(selected)

    async def search(self, query: str, context: RetrievalContext, *, relation_lookup=None) -> list[dict]:
        self._authorized(context)
        started = monotonic()
        expires_at = started + self.policy.deadline_seconds
        async with asyncio.timeout(self.policy.deadline_seconds), self._search_lock:
            queries = retrieval_subqueries(query, limit=min(self.policy.query_limit, self.policy.fusion_k))
            parent_scores, picked_by_query, rerank_candidates = {}, [], 0
            for position, subquery in enumerate(queries):
                # fusion_k is a total cross-encoder budget, rather than a fresh
                # allocation per subquery. Share both work and remaining time.
                candidate_limit = min(self.reranker.profile.max_candidates,
                    self.policy.fusion_k // len(queries) + (position < self.policy.fusion_k % len(queries)))
                seconds = (expires_at - monotonic()) / (len(queries) - position)
                if seconds <= 0:
                    raise TimeoutError("public retrieval deadline exceeded")
                async with asyncio.timeout(seconds):
                    scores, first, count = await self._rank_subquery(subquery, context, candidate_limit, relation_lookup)
                rerank_candidates += count
                for parent, score in scores.items():
                    parent_scores[parent] = max(score, parent_scores.get(parent, -math.inf))
                if first is not None:
                    picked_by_query.append(first)
            # Reserve a source for each explicit subquestion before filling by score.
            ordered = list(dict.fromkeys(picked_by_query + sorted(parent_scores, key=lambda i: (-parent_scores[i], self.rows[i]["chunk_id"]))))
            results, size = [], 0
            for parent in ordered:
                row = self.rows[parent]
                if parent not in self._eligible(context):
                    continue
                length = len(row["content_text"].encode())
                if len(results) >= self.policy.parent_k or size + length > self.policy.context_bytes:
                    continue
                results.append(dict(row, score=parent_scores[parent], retrieval_mode="hybrid_cross_encoder",
                                    index_version=self.fingerprint, profile_version="public-advanced-v1"))
                size += length
            if self.diagnostics:
                self.diagnostics({"query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                    "index_version": self.fingerprint, "subqueries": len(queries), "selected_parents": len(results),
                    "rerank_candidates": rerank_candidates,
                    "context_bytes": size, "total_ms": round((monotonic() - started) * 1000),
                    "real_vector_and_reranker": True})
            return results
