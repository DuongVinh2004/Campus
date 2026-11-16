"""Produce an honest inventory/matrix from immutable acquisitions and live observations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services/api/src")]
from huce_source_registry import BASE, TOPICS, Page, canonical, checked, norm, official, save
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore


def social_identity(url):
    p = urlsplit(url)
    path = p.path.rstrip("/")
    if (not path or re.search(r"^/(?:sharer|share|plugins|tr|hashtag|results|intent)(?:/|\.|$)", path)
            or "/watch/hashtag/" in path):
        return None, "widget_or_tracking"
    host = (p.hostname or "").lower()
    host = "facebook.com" if host.endswith("facebook.com") else host.removeprefix("www.")
    kind = "community" if "/groups/" in path or path.startswith("/g/") else "channel_candidate"
    if any(marker in path for marker in ("/posts/", "/videos/", "/reel/", "/shorts/", "/embed/")) or path == "/watch" or host == "youtu.be":
        kind = "content_permalink"
    if host == "zalo.me" and re.fullmatch(r"/\d{9,12}", path):
        kind = "contact_link_not_verified_oa"
    keep = {key: values[0] for key, values in parse_qs(p.query).items() if key in {"id", "v"}}
    return urlunsplit(("https", host, path, urlencode(keep), "")), kind


def main(args):
    discovery = checked(Path(args.discovery))
    curricula = checked(Path(args.curricula))
    output = checked(BASE / datetime.now(UTC).strftime("audit-%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True, exist_ok=False)
    records = json.loads((discovery / "registry.json").read_text(encoding="utf-8"))
    frontier = json.loads((discovery / "frontier.json").read_text(encoding="utf-8"))
    links = json.loads((discovery / "links.json").read_text(encoding="utf-8"))
    cm = json.loads((curricula / "manifest.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "data/huce-public-20261013/reviewed-expansion-20261020.json").read_text(encoding="utf-8"))
    reviewed_hashes = {r["source_sha256"] for r in release["chunks"]}
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    save(output / "active-rag-inventory.json", [{k: row[k] for k in (
        "source_id", "document_version_id", "chunk_id", "title", "canonical_uri", "version_label", "source_status",
        "section_path", "page_start", "page_end", "quote_span_hash", "effective_from", "effective_until")} for row in store.rows])
    rows = []
    for record in records:
        row = dict(record)
        row["kind"] = "html_page" if "html" in row.get("content_type", "") else "pdf" if "pdf" in row.get("content_type", "") or row.get("pages") else "image_resource" if row.get("content_type", "").startswith("image/") else "other_resource"
        row["rag_matching_publication_chunks"] = sum(r["canonical_uri"] == row["url"] for r in store.rows)
        row["rag_status"] = "publication_has_admitted_excerpts" if row["rag_matching_publication_chunks"] else "not_admitted"
        rows.append(row)
    rows.extend(dict(item, status="not_processed", kind="discovered_url", rag_status="not_admitted") for item in frontier)
    for file in cm["files"]:
        rows.append(dict(file, kind="curriculum_attachment", rag_status="reviewed_total_excerpt_admitted" if file.get("sha256") in reviewed_hashes else "not_admitted",
                         source_row_bindings=[r for r in cm["rows"] if r["drive_id"] == file["drive_id"]]))
    save(output / "source-registry.json", rows)
    save(output / "supersession-review.json", {
        "confirmed_from_original_clause": [{"document": "924/QĐ-ĐHXDHN", "effective_date": "2026-06-10",
            "replaces": ["960/QĐ-ĐHXDHN ngày 21/06/2024", "1010/QĐ-ĐHXDHN ngày 02/07/2024"],
            "evidence": "data/huce-public-20261013/supplemental-20261020.json, Điều 2, trang 1"}],
        "candidates_not_legally_resolved": [{"url": r["url"], "title": r.get("title"), "status": "needs_original_clause_and_scope_review"}
            for r in records if re.search(r"thay the|sua doi|dieu chinh|quy che", norm(r.get("title", "")))],
        "policy": "No legal replacement/expiry inferred from URL/date/hash alone; raw discoveries are not active RAG evidence."})
    # Reparse the official organization menus so unit names are not guessed from hostnames.
    units = {}
    for record in records:
        if urlsplit(record["url"]).hostname not in {"huce.edu.vn", "www.huce.edu.vn"} or not record.get("original_file"):
            continue
        if not any(key in record["url"] for key in ("khoa-truc-thuoc", "phong-chuc-nang", "co-cau-to-chuc", "Chuong-trinh-dao-tao-va-cap-bang")):
            continue
        if "html" not in record.get("content_type", ""):
            continue
        page = Page(); page.feed(checked(ROOT / record["original_file"]).read_text(encoding="utf-8", errors="replace"))
        for href, label, tag in page.links:
            label = " ".join(label.split()).lstrip("•·- "); url = canonical(href, record["url"])
            if norm(label) in {"khoa truc thuoc", "phong chuc nang", "khoa hoc cong nghe", "vien nghien cuu"}:
                continue
            if url and re.match(r"^(?:khoa |phong |ban |bo mon |vien |trung tam |tram )", norm(label)):
                key = (norm(label), url)
                units.setdefault(key, {"name": label, "url": url, "domain": urlsplit(url).hostname,
                    "official_organization_page": record["url"], "source_snapshot_sha256": record["sha256"],
                    "identity_status": "listed_by_official_organization_page", "public_crawl_supported": official(url)})
    save(output / "units.json", list(units.values()))
    social = {}
    for link in links:
        host = urlsplit(link["to"]).hostname or ""
        if not any(host == s or host.endswith("." + s) for s in ("facebook.com", "youtube.com", "youtu.be", "tiktok.com", "zalo.me", "instagram.com")):
            continue
        url, kind = social_identity(link["to"])
        if not url: continue
        row = social.setdefault(url, {"url": url, "kind": kind, "website_backlinks": [], "verification": "linked_not_identity_verified",
                                      "collection": "not_scraped_platform_access_review_required", "rag_status": "not_admitted"})
        proof = {"url": link["from"], "label": link["label"][:300]}
        if proof not in row["website_backlinks"]: row["website_backlinks"].append(proof)
    verified = {
        "https://facebook.com/truongdhxaydung": "HUCE institutional information",
        "https://facebook.com/cnttdhxd": "Faculty of Information Technology official information",
        "https://youtube.com/channel/UCzsYk_GlL5IYG6wVUkyO_pQ/videos": "Communication and Admissions office",
    }
    for url, unit in verified.items():
        if url in social:
            social[url].update(verification="identity_reviewed_official_website_backlink", issuer=unit)
    # Actual public access checks through the browsing tool, not inferred login access.
    for url, row in social.items():
        if url == "https://facebook.com/truongdhxaydung": row["collection"] = "public_open_redirected_to_login_no_bypass"
        if "UCzsYk_GlL5IYG6wVUkyO_pQ" in url: row["collection"] = "public_channel_title_only_video_text_unavailable"
        if "fit.huce" in url and "tiktok.com" in url: row["verification"] = "official_website_identifies_student_media_not_institutional_policy"
    save(output / "social-registry.json", list(social.values()))
    observations = []
    for folder in ("verified-browser-02", "coverage-browser-02", "coverage-browser-03", "followup-browser-04"):
        for path in (ROOT / ".tooling/huce-expansion-20261020-01" / folder).rglob("*.json"):
            if path.name != "observation.json" and not re.fullmatch(r"answer-\d+\.json", path.name): continue
            value = json.loads(path.read_text(encoding="utf-8"))
            observations.append({"topic": value.get("topic", "original_three" if folder == "verified-browser-02" else "followup"), "question": value["question"],
                "response_class": value["final"]["response_class"], "content": value["final"]["content"],
                "citations": value["final"].get("citations", []), "evidence_file": str(path.relative_to(ROOT)),
                "readback_statuses": [r["http_status"] for r in value.get("readbacks", [])],
                "content_review": "pending_beyond_original_three"})
    save(output / "e2e-observations.json", observations)
    latest = {o["question"]: o for o in observations}
    save(output / "e2e-latest-observations.json", list(latest.values()))
    domains = sorted({urlsplit(r["url"]).hostname for r in rows if official(r["url"])})
    with checked(output / "coverage-matrix.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["topic", "unit_domain", "cohort", "system", "academic_year", "candidate_documents", "rag_candidate_chunks", "scope_verified", "e2e_grounded_observations", "gap"])
        for topic, pattern in TOPICS.items():
            for domain in domains:
                raw = [r for r in records if urlsplit(r["url"]).hostname == domain and topic in r.get("topic_candidates", [])]
                admitted = [r for r in store.rows if urlsplit(r["canonical_uri"]).hostname == domain and re.search(pattern, norm(r["content_text"]))]
                for cohort in ["UNRESOLVED", *[f"K{i}" for i in range(64, 72)]]:
                    for system in ["UNRESOLVED", "chinh_quy", "VLVH"]:
                        # Scope is verified here only for the three K71 chart totals.
                        verified_scope = cohort == "K71" and system == "chinh_quy" and domain == "huce.edu.vn" and topic in {"curriculum", "credits"}
                        e2e = sum(o["topic"] == topic and o["response_class"] == "grounded_answer"
                                  and any(urlsplit(c["citation"]["canonical_uri"]).hostname == domain for c in o["citations"])
                                  for o in latest.values()) if cohort == "UNRESOLVED" and system == "UNRESOLVED" else 0
                        writer.writerow([topic, domain, cohort, system, "2026-2027", len(raw), len(admitted), verified_scope, e2e,
                            "scope_unreviewed" if raw or admitted else "no_source_in_current_acquisition"])
    with checked(output / "curriculum-coverage.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["cohort", "programme_cells", "public_url", "acquisition", "pages", "reviewed_total_only", "courses_and_prerequisites"])
        for row in cm["rows"]:
            file = next(f for f in cm["files"] if f["drive_id"] == row["drive_id"])
            writer.writerow([row["scope"], " | ".join(row["row_cells"]), row["url"], file["status"], file.get("page_count", 0),
                             file.get("sha256") in reviewed_hashes, "not_reviewed_not_admitted"])
    stats = {
        "created_at": datetime.now(UTC).isoformat(), "discovery": str(discovery.relative_to(ROOT)),
        "unit_entities_listed": len(units), "official_domains_discovered": len(domains),
        "official_domains_attempted": len({urlsplit(r["url"]).hostname for r in records}),
        "attempted_urls": len(records), "frontier_remaining": len(frontier),
        "acquisition_statuses": dict(Counter(r["status"] for r in records)),
        "resource_types": dict(Counter(r["kind"] for r in rows if r["kind"] not in {"discovered_url", "curriculum_attachment"})),
        "unique_resource_hashes": len({r["sha256"] for r in rows if r.get("sha256")}),
        "curriculum_table_rows": len(cm["rows"]), "curriculum_files": len(cm["files"]),
        "curriculum_downloaded": sum(r["status"] == "downloaded" for r in cm["files"]),
        "curriculum_pages": sum(r.get("page_count", 0) for r in cm["files"]),
        "curriculum_access_statuses": dict(Counter(r["status"] for r in cm["files"])),
        "new_reviewed_rag_excerpts": len(release["chunks"]), "active_rag_chunks": len(store.rows),
        "social_links_classified": dict(Counter(r["kind"] for r in social.values())),
        "social_identity_reviewed": sum(r["verification"] == "identity_reviewed_official_website_backlink" for r in social.values()),
        "e2e_observations": len(observations), "e2e_classes": dict(Counter(o["response_class"] for o in observations)),
        "e2e_latest_saved_classes": dict(Counter(o["response_class"] for o in latest.values())),
        "e2e_unresolved": [
            {"topic": "academic_standing", "outcome": "No persisted final within 100s; run checkpoint failed AI_PARTIAL_COVERAGE, system_error content guard.",
             "evidence": ".tooling/huce-expansion-20261020-01/coverage-browser-03"},
            {"topic": "registration", "outcome": "EVIDENCE_BUDGET_EXHAUSTED; existing evidence limit preserved."},
        ],
        "pdf_layout": "data/huce-discovery-20261020/layout-20261020T153253945901Z/manifest.json",
        "pdf_sparse_page_assessment": "data/huce-discovery-20261020/layout-20261020T153253945901Z/assessment.json",
        "ocr": {"manifest": "data/huce-discovery-20261020/ocr-2026-10-20T15-38-18-054Z/manifest.json",
                "scan_pages": 2, "engine_confidence": [61, 59], "complete_visual_table_review": False, "rag_admitted": False},
        "complete": False,
        "limitations": ["Frontier and domain search are open-ended; no all-web completeness claim.",
            "Units and domains are different counts; aliases and organizational identities still need deduplication.",
            "Matrix candidate counts are discovery signals, not verified subject/cohort applicability.",
            "Only title/total/exclusion of three K71 charts newly admitted; remaining curriculum tables need visual structuring.",
            "Social backlinks do not establish account ownership by themselves; no comments/groups/private content collected.",
            "No active synchronizer has been scheduled; incremental CLI is available.",
            "One old wiring test pins pre-expansion fingerprint 903531...; it remains unchanged and fails against the expanded corpus."]}
    save(output / "summary.json", stats)
    with checked(output / "REPORT.md").open("x", encoding="utf-8") as stream:
        stream.write("# HUCE acquisition and RAG evidence\n\nStatus: incomplete; measured scope only.\n\n```json\n" + json.dumps(stats, ensure_ascii=False, indent=2) + "\n```\n\n"
            "Source registry: source-registry.json. Units: units.json. Social: social-registry.json. Active source chunks: active-rag-inventory.json. "
            "Matrices: coverage-matrix.csv and curriculum-coverage.csv. Live outcomes: e2e-observations.json.\n\n"
            "## Incremental update\n\nRun scripts/huce_source_registry.py --resume <previous run> --limit <bounded batch>. "
            "Use --refresh to conditionally recheck retained URLs (ETag/Last-Modified where provided); otherwise only continue the frontier. "
            "Each run is new, raw bytes are content-addressed and never replaced. Compare previous_sha256/content_changed to identify changed snapshots. "
            "304 retains original bytes; a different hash creates a new version and requires scope, expiry and replacement review before RAG admission. "
            "No automatic legal supersession is inferred from date or hash. Decision 924 explicitly replaces 960/2024 and 1010/2024; "
            "the current tuition supplement retains that clause. New fees/calendar notices must be reviewed for year, cohort, deadlines and superseding identifiers. "
            "Expired notices remain evidence; they must not enter the current-answer candidate set.\n\n"
            "The append-only event log preserves per-URL progress if interrupted. The resume CLI currently requires a completed run's frontier; "
            "an interrupted run requires rebuilding the frontier from retained links before resumption.\n")
    print(json.dumps({"audit": str(output), **stats}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", required=True); parser.add_argument("--curricula", required=True)
    main(parser.parse_args())
