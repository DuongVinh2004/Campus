"""Freeze the independently viewed page anchors before any live answers.

This records the coding agent's technical visual comparison, not a university
review, legal currency check, source admission, or independent human reviewer.
"""
import copy
import hashlib
import json
from datetime import UTC, datetime

from knowledge_platform import ROOT, checked_path, retain


def main():
    old_path=checked_path(ROOT / "evals/datasets/knowledge-independent-20261026.json",ROOT)
    old=json.loads(old_path.read_text(encoding="utf-8"))
    reviewed_path=checked_path(ROOT / "infra/local/huce-completion-20261025-02/regulation-reviewed-pages-01.json",ROOT)
    reviewed=json.loads(reviewed_path.read_text(encoding="utf-8"))
    original=checked_path(ROOT / reviewed["original"],ROOT)
    if hashlib.sha256(original.read_bytes()).hexdigest()!=reviewed["original_sha256"]:
        raise ValueError("Original changed; do not rewrite gold to compensate")
    witness=checked_path(ROOT / old["witness_file"],ROOT)
    if hashlib.sha256(witness.read_bytes()).hexdigest()!=old["witness_file_sha256"]:
        raise ValueError("Frozen transcription witness changed")
    inspected={4,5,10,18,22,23,24}
    pages=[]
    for page in reviewed["pages"]:
        if page["page"] in inspected:
            image=checked_path(ROOT / page["image"],ROOT)
            if hashlib.sha256(image.read_bytes()).hexdigest()!=page["image_sha256"]:
                raise ValueError("Viewed page image changed")
            pages.append({"page":page["page"],"image":image.relative_to(ROOT).as_posix(),"image_sha256":page["image_sha256"]})
    if {page["page"] for page in pages}!=inspected: raise ValueError("Exact inspected image set required")
    gold=copy.deepcopy(old)
    gold.update(revision="knowledge-independent-20261026-v2",previous_gold_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
        frozen_at=datetime.now(UTC).isoformat(),original_file=original.relative_to(ROOT).as_posix(),original_sha256=reviewed["original_sha256"],
        image_witnesses=pages,visual_review_kind="coding-agent technical check in this turn; not institutional/human admission",
        limitations=["Regulation text shard; table/diagram, multi-document and follow-up shards remain",
            "Seven cached original page images visually inspected; not all26 pages or later amendments",
            "Literal material/condition checks can flag paraphrases and negated forbidden phrases; flags need manual semantic adjudication",
            "Gold frozen before the live answers; no result is implied by this file"])
    anchors={"fresh_online_emergency":[10],"fresh_transfer_ceiling":[18],"fresh_exchange_permission":[22],
        "fresh_second_programme_warning":[23],"fresh_no_registration_reason":[24],"fresh_credit_workload":[4],
        "fresh_prerequisite_pass":[5],"fresh_prior_distinction":[5],"fresh_corequisite_cancel":[5]}
    for case in gold["cases"]:
        if case["status"]=="answered": case["witness_pages"]=anchors[case["name"]]
    target=checked_path(ROOT / "evals/datasets/knowledge-independent-20261026-v2.json",ROOT)
    retain(target,gold)
    print(json.dumps({"gold":str(target),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"case_count":len(gold["cases"]),"pages_inspected":sorted(inspected)}))


if __name__=="__main__": main()
