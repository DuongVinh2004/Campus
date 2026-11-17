"""Add source-page cohort scopes; never merge different cohort diagrams."""
import json
import re
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, read
from knowledge_platform import ROOT, checked_path, retain
from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot


def main():
    plan = read(SCOPE / "candidate-plan-04.json")
    folder = checked_path(SCOPE / "candidates-page-scopes-01", ROOT); folder.mkdir(exist_ok=False)
    partitioned = {"8d1a03a4-7cc5-7903-834a-05084fbb6ed0", "f634f981-e997-70dc-89ea-f78f8e327268"}
    calendar = "c2454951-46ce-7a56-8421-ca4927bf3339"
    changed = []
    for entry in plan["sources"]:
        if entry["source_id"] not in partitioned | {calendar}: continue
        candidate = read(ROOT / entry["candidate"]); scope = candidate["applicability"]
        scope["reviewed_at"] = datetime.now(UTC).isoformat()
        if entry["source_id"] in partitioned:
            found = set()
            for page in candidate["pages"]:
                block = candidate["extracted"]["blocks"][int(page["block_id"])]
                text = normalized_question(block["text"])
                cohorts = {"K" + value for value in re.findall(r"\bk\s*(\d{2})(?=\b|[a-z])", text)}
                cohorts |= {"K" + value for value in re.findall(r"ap dung (?:cho|tu) khoa\s*(\d{2})\b", text)}
                if len(cohorts) != 1: raise ValueError("Exactly one printed cohort per source page required")
                page["cohorts"] = sorted(cohorts); found |= cohorts
            scope.update(cohort_partitioned=True, cohorts=sorted(found))
            scope["limitations"].append("Each page has its own printed cohort; no union of different cohort totals or courses")
        else:
            scope["mixed_cohort_table"] = True
            scope["limitations"].append("One page mixes many cohorts; row/column schedule mapping not verified; reject cohort-specific lookups")
        validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=datetime.fromisoformat(scope["reviewed_at"]))
        target = checked_path(folder / (entry["source_id"] + ".json"), ROOT); retain(target, candidate)
        entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=digest(target.read_bytes()), cohorts=scope["cohorts"])
        changed.append(entry["source_id"])
    retain(SCOPE / "candidate-plan-05.json", plan)
    print(json.dumps({"page_partitioned": sorted(partitioned), "calendar_bound": calendar, "changed": len(changed)}))


if __name__ == "__main__": main()
