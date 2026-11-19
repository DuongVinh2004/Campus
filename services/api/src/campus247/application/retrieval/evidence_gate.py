from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from campus247.application.retrieval.citations import CitationBundle


@dataclass(frozen=True)
class GroundedClaim:
    claim_id: str
    text: str
    citation_ids: tuple[str, ...]
    claim_type: str


@dataclass(frozen=True)
class GroundedDraft:
    response_text: str
    claims: tuple[GroundedClaim, ...] = ()


@dataclass(frozen=True)
class EvidenceGateResult:
    passed: bool
    unsupported_claims: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    diagnostics: tuple[dict, ...] = ()


def parse_grounded_claims(text: str) -> GroundedDraft:
    """Strict claim output; the server renders only the claims it will verify.

    Plain prose remains a single conservative claim for existing callers.
    JSON-like output is never repaired or silently treated as prose.
    """
    if not text.lstrip().startswith(("{", "[", "```")):
        return GroundedDraft(text, (GroundedClaim("draft_claim", text,
            tuple(sorted(set(re.findall(r"\[(CIT-\d{3})\]", text)))), "implicit"),))
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != {"claims"}:
        raise ValueError("invalid grounded claim output")
    values = data["claims"]
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise ValueError("bounded material claims required")
    claims = []
    for i, value in enumerate(values, 1):
        if not isinstance(value, dict) or set(value) != {"text", "citation_ids", "claim_type"}:
            raise ValueError("invalid material claim")
        body, refs, kind = value["text"], value["citation_ids"], value["claim_type"]
        if (not isinstance(body, str) or not body.strip() or len(body) > 2000
                or not isinstance(refs, list) or not 1 <= len(refs) <= 20
                or any(not isinstance(r, str) or re.fullmatch(r"CIT-\d{3}", r) is None for r in refs)
                or len(refs) != len(set(refs))
                or kind not in {"policy", "procedure", "deadline", "fee", "contact", "personal_data"}
                or re.search(r"CIT-|https?://", body)):
            raise ValueError("invalid material claim fields")
        claims.append(GroundedClaim(f"CLM-{i:03}", body.strip(), tuple(refs), kind))
    rendered = "\n".join(c.text + " " + " ".join(f"[{r}]" for r in c.citation_ids) for c in claims)
    return GroundedDraft(rendered, tuple(claims))


class EvidenceGate:
    """Verifies that all material claims have valid citations and lexical grounding in cited chunks."""

    def __init__(self, min_token_overlap_ratio: float = 0.25) -> None:
        self._min_token_overlap_ratio = min_token_overlap_ratio

    def verify(self, draft: GroundedDraft, bundle: CitationBundle) -> EvidenceGateResult:
        unsupported: list[str] = []
        reasons: list[str] = []
        diagnostics: list[dict] = []

        for claim in draft.claims:
            diag = {"claim_id_sha256": hashlib.sha256(claim.claim_id.encode()).hexdigest(),
                "claim_sha256": hashlib.sha256(claim.text.encode()).hexdigest(),
                "cited_ids": [r if re.fullmatch(r"CIT-\d{3}", r) else "INVALID" for r in claim.citation_ids],
                "citation_validity": [bundle.resolve(r) is not None for r in claim.citation_ids],
                "threshold": self._min_token_overlap_ratio, "overlap_ratio": None,
                "claim_token_count": 0, "matching_token_count": 0, "reason_code": "SUPPORTED",
                "source_hashes": [bundle.resolve(r).quote_span_hash for r in claim.citation_ids if bundle.resolve(r)]}
            diagnostics.append(diag)
            # 1. Check claim has citation
            if not claim.citation_ids:
                diag["reason_code"] = "MISSING_CITATION"
                unsupported.append(claim.claim_id)
                reasons.append(f"Claim '{claim.claim_id}' has no citations")
                continue

            # 2. Check citation IDs exist in bundle
            cited_records = []
            has_unknown_citation = False
            for cit_id in claim.citation_ids:
                rec = bundle.resolve(cit_id)
                if rec is None:
                    diag["reason_code"] = "UNKNOWN_CITATION"
                    has_unknown_citation = True
                    unsupported.append(claim.claim_id)
                    reasons.append(f"Claim '{claim.claim_id}' references unknown citation '{cit_id}'")
                    break
                cited_records.append(rec)

            if has_unknown_citation:
                continue

            # 3. Check lexical grounding in cited content
            # Citation syntax is metadata, not part of a material assertion.
            material_text = re.sub(r"\[CIT-\d{3}\]", "", claim.text)
            claim_tokens = set(t.lower() for t in re.findall(r"\w+", material_text) if len(t) > 2)
            diag["claim_token_count"] = len(claim_tokens)
            if not claim_tokens:
                continue

            combined_cited_text = " ".join(r.content_text.lower() for r in cited_records)
            from campus247.application.retrieval.material_support import support_issues
            material_issues = support_issues(material_text, combined_cited_text)
            if material_issues:
                diag["reason_code"] = material_issues[0]
                unsupported.append(claim.claim_id)
                reasons.append(f"Claim '{claim.claim_id}' failed factual support checks")
                continue
            # Printed numeric credit labels use TC in curriculum charts. Expand
            # that explicit unit for lexical matching only; quantity, unit and
            # semantic checks still validate the unchanged source separately.
            lexical_source = re.sub(r"(?<=\d)\s*tc\b", " tín chỉ", combined_cited_text)
            matching_tokens = {t for t in claim_tokens if t in lexical_source}
            overlap_ratio = len(matching_tokens) / len(claim_tokens)
            diag.update(overlap_ratio=overlap_ratio, matching_token_count=len(matching_tokens))

            if overlap_ratio < self._min_token_overlap_ratio:
                diag["reason_code"] = "LOW_SUPPORT"
                unsupported.append(claim.claim_id)
                reasons.append(
                    f"Claim '{claim.claim_id}' lacks grounding (overlap {overlap_ratio:.2f} < {self._min_token_overlap_ratio})"
                )

        passed = len(unsupported) == 0
        return EvidenceGateResult(
            passed=passed,
            unsupported_claims=tuple(unsupported),
            reasons=tuple(reasons),
            diagnostics=tuple(diagnostics),
        )
