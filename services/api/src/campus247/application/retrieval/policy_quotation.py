"""Present a public numbered policy clause verbatim without relaxing its guards."""
import json
import re
from dataclasses import replace

from campus247.application.conversation.followup import normalized_question
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def present_policy_quotation(response, bundle, question):
    if (not isinstance(response, LlmResponse) or response.status != LlmResponseStatus.COMPLETED
            or response.tool_candidates or not re.search(r"\bquy che\s+\d+\b", normalized_question(question))):
        return response
    try:
        draft = parse_grounded_claims(response.output_text or "")
    except (ValueError, TypeError, KeyError):
        return response
    claims, changed = [], False
    for claim in draft.claims:
        text, kind = claim.text, claim.claim_type
        if "kỷ luật" in text.casefold() and kind in {"policy", "procedure"} and len(claim.citation_ids) == 1:
            record = bundle.resolve(claim.citation_ids[0])
            source = record.content_text if record else ""
            if re.match(r"^Điều \d+\.", source) and not record.simulation_label:
                numbered = re.search(r"(?m)^\d+\.\s+", source)
                if numbered:
                    body = source[numbered.end():].strip()
                    bullets = list(re.finditer(r"(?m)^[a-zđ]\)\s+", body))
                    # A causal phrase explicitly in the question can identify
                    # one branch. Keep its common introduction and every word
                    # of that complete branch, including disciplinary exclusions.
                    words = re.findall(r"\w+", question.casefold())
                    anchors = [" ".join(words[i:i+5]) for i, word in enumerate(words)
                        if word in {"vì", "do"} and len(words[i:i+5]) == 5]
                    chosen = []
                    for i, bullet in enumerate(bullets):
                        end = bullets[i+1].start() if i+1 < len(bullets) else len(body)
                        branch = body[bullet.start():end].strip()
                        plain = " ".join(re.findall(r"\w+", branch.casefold()))
                        if any(anchor in plain for anchor in anchors):
                            chosen.append(branch)
                    if len(chosen) == 1:
                        body = body[:bullets[0].start()].strip() + "\n" + chosen[0]
                    # Quotation is still subject to the existing 100% lexical
                    # discipline check, official-source binding and semantic
                    # verification. It grants no individual eligibility verdict.
                    if body and "kỷ luật" in body.casefold():
                        text, kind, changed = body, "policy", True
        claims.append({"text": text, "citation_ids": list(claim.citation_ids), "claim_type": kind})
    if not changed or sum(len(c["text"].split()) for c in claims) > 160:
        return response
    return replace(response, output_text=json.dumps({"claims": claims}, ensure_ascii=False))
