"""Migration preflight for the existing curated HUCE corpus.

The loader validates ready/withdrawn markers and original checksums. Legacy
review labels are recorded as provenance, never converted into human approvals.
The default only inspects and retains a new report. --stage adds unapproved
versions to the explicitly local DB; it never changes legacy source files,
activates a release, moves a file or performs embedding inference.
"""
from __future__ import annotations

import hashlib
import json
import argparse
import asyncio
import base64
import re
from collections import Counter
from datetime import UTC, datetime

from knowledge_platform import ROOT, STATE, checked_path, retain
from public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path


def original_references(corpus):
    """Resolve originals by independently retained inventory hashes, never by filename alone."""
    inventory_path = max(STATE.glob("inventory-*.json"),key=lambda p:p.name)
    inventory = json.loads(checked_path(inventory_path,ROOT).read_bytes())
    by_hash = {}
    for row in inventory["files"]:
        by_hash.setdefault(row["sha256"],[]).append(checked_path(ROOT / row["path"],ROOT))
    basic = {}
    directory = ROOT / "data/huce-public-20261013"
    for manifest_path in sorted(directory.glob("*.json")):
        manifest = json.loads(checked_path(manifest_path,ROOT).read_bytes())
        if not isinstance(manifest,dict) or manifest.get("public_only") is not True:
            continue
        sources = manifest.get("sources",[])
        for item in manifest.get("chunks",[]):
            if item.get("source_sha256") or not item.get("source_file"):
                continue
            filename = item["source_file"]
            source = next((s for s in sources if s.get("file")==filename),None)
            if source is None:
                source = next((s for s in sources if s.get("url")==item.get("url") and s.get("pdf_sha256")),None)
            checksum = (source or {}).get("sha256") or (source or {}).get("pdf_sha256")
            paths = by_hash.get(checksum,[])
            if not paths:
                continue
            path = next((p for p in paths if p.name==filename),paths[0])
            reference = {"path":path,"sha256":checksum,
                "download_url":item.get("download_url") or (source or {}).get("url") or item["url"]}
            basic.setdefault(item["url"],{})[(checksum,reference["download_url"])] = reference
    references = {}
    for ordinal,row in enumerate(corpus.rows):
        provenance = row.get("provenance")
        if provenance:
            paths = by_hash.get(provenance.get("source_sha256"),[])
            if paths:
                references[ordinal] = {"path":paths[0],"sha256":provenance["source_sha256"],"download_url":provenance["download_url"]}
        else:
            choices = basic.get(row["canonical_uri"],{})
            if choices and len({ref["sha256"] for ref in choices.values()})==1:
                references[ordinal] = sorted(choices.values(),key=lambda ref:(not ref["download_url"].endswith(".pdf"),ref["download_url"]))[0]
    # These supplemental sources have their own retained acquisition receipt,
    # outside the older inventory. Bind the exact HTML bytes and embedded scans;
    # a reconstructed PDF is not substituted for the original publication.
    directory = checked_path(ROOT / ".tooling/tuition-credit-rag-20261020-01", ROOT)
    receipt = json.loads((directory / "acquisition.json").read_text(encoding="utf-8"))
    hashes = {item["file"]: item["sha256"] for item in receipt["files"]}
    def verified(name):
        path = checked_path(directory / name, ROOT)
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError("Supplemental original checksum mismatch")
        return path
    tuition = verified("student-tuition-publication.html")
    html = tuition.read_text(encoding="utf-8")
    images = [hashlib.sha256(base64.b64decode(raw)).hexdigest()
              for raw in re.findall(r'data:image/jpeg;base64,([^"\s]+)', html)]
    for name in ("student-tuition-4.jpeg", "student-tuition-5.jpeg"):
        verified(name)
        if hashes[name] not in images:
            raise ValueError("Tuition scan not present in original publication")
    fit = verified("fit-publication.html")
    for ordinal, row in enumerate(corpus.rows):
        if ordinal in references:
            continue
        if row["canonical_uri"].startswith("https://sinhvien.huce.edu.vn/") and row.get("document_number") == "924/QĐ-ĐHXDHN":
            references[ordinal] = {"path": tuition, "sha256": hashes[tuition.name], "download_url": row["canonical_uri"],
                "media_type": "text/html", "provenance": {"acquisition_receipt_sha256": hashlib.sha256((directory / "acquisition.json").read_bytes()).hexdigest(),
                "embedded_document_page_sha256": {"1": hashes["student-tuition-4.jpeg"], "2": hashes["student-tuition-5.jpeg"]},
                "mapping": "Document pages 1/2 are embedded scans, not HTML pagination; agent visually checked 2026-10-23"}}
        elif row["canonical_uri"] == "https://fit.huce.edu.vn/chuong-trinh-dao-tao":
            from acquire_huce_public_knowledge import Text
            parser = Text()
            parser.feed(fit.read_text(encoding="utf-8"))
            text = " ".join(" ".join(parser.parts).split())
            if " ".join(row["content_text"].split()) not in text:
                raise ValueError("FIT excerpt not present in original HTML")
            references[ordinal] = {"path": fit, "sha256": hashes[fit.name], "download_url": row["canonical_uri"],
                "media_type": "text/html", "provenance": {"mapping": "Exact HTML paragraph under c) Khung chương trình đào tạo; no invented page"}}
    return references


async def stage(corpus,references,index_sha):
    from knowledge_platform import components,TENANT
    from campus247.application.knowledge.legacy_import import stage_legacy
    pool,settings,platform,_=await components()
    try:
        from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter
        adapter = LocalOwnerIdentityAdapter(checked_path(STATE / "owner-identity.json", ROOT), TENANT)
        actor = adapter.resolve_token(adapter.mint_token(adapter.directory()["agent_id"]))
        from public_rag_retrieval import EMBED_SHA
        return await stage_legacy(platform,actor,corpus,references,legacy_index_sha256=index_sha,embedding_artifact_sha256=EMBED_SHA)
    finally:
        await pool.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",action="store_true",help="Add unapproved versions to the task-owned PostgreSQL DB; never activate")
    args=parser.parse_args()
    report = {"at": datetime.now(UTC).isoformat(), "mode": "stage_unapproved" if args.stage else "dry_run_only", "source_mutations": False,
              "legacy_approval_is_human_approval": False, "automatic_activation": False}
    target = STATE / ("huce-import-preflight-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json")
    try:
        corpus = create_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE",
            faq_directory=ROOT / "data/huce-faq-20261013")
        report.update(corpus_fingerprint=corpus.fingerprint, parent_count=len(corpus.rows), child_count=len(corpus.children),
            source_count=len({r["source_id"] for r in corpus.rows}), version_count=len({r["document_version_id"] for r in corpus.rows}),
            uri_count=len({r["canonical_uri"] for r in corpus.rows}),
            status_counts=dict(Counter(r["source_status"] for r in corpus.rows)),
            locator_counts=dict(Counter("page" if r.get("page_start") else "section" for r in corpus.rows)))
        index = public_hybrid_index_path(corpus)
        report["matching_legacy_index"] = str(index.relative_to(ROOT)) if index.is_file() else None
        report["vector_reuse"] = "requires exact index input/profile hashes; no dimensionality-only reuse"
        if index.is_file():
            raw = index.read_bytes()
            manifest = json.loads(raw)
            corpus.load_vectors(manifest)
            report["legacy_index_sha256"] = hashlib.sha256(raw).hexdigest()
            report["verified_legacy_vector_count"] = len(manifest["vectors"])
        else:
            report["verified_legacy_vector_count"] = 0
        # The new parser/index input is deliberately a different processor profile.
        # A separate legacy import adapter is needed before copying those vectors.
        report["new_processor_reusable_vector_count"] = 0
        references = original_references(corpus)
        report["original_mapping_verified_parent_count"] = len(references)
        report["original_mapping_unverified_parent_count"] = len(corpus.rows)-len(references)
        report["full_rebuild_calls_without_legacy_reuse"] = len(corpus.children)
        report["required_before_serving"] = [
            "explicit applicability/scope and independent review binding, preserving UNKNOWN dates",
            "original file mapping + exact page/block locator migration",
            "profile/input-compatible reuse adapter or queued BGE rebuild",
            "candidate quality checks and explicit preview/confirmation; no silent cutover"]
        report["rows"] = [{key: row.get(key) for key in ("source_id", "document_version_id", "chunk_id", "title", "issuer",
            "canonical_uri", "version_label", "source_status", "quote_span_hash", "page_start", "page_end", "section_path",
            "effective_from", "effective_until", "provenance")} for row in corpus.rows]
        report["index_inputs"] = [{"child_id": child["id"], "input_sha256": hashlib.sha256(child["index_text"].encode()).hexdigest()}
                                   for child in corpus.children]
        if args.stage:
            if not report.get("legacy_index_sha256"):
                raise ValueError("Verified full index required before staging existing vectors")
            report["staging"] = asyncio.run(stage(corpus,references,report["legacy_index_sha256"]))
        report["complete"] = True
    except Exception as error:
        report.update(complete=False, error_code=type(error).__name__)
        raise
    finally:
        retain(target, report)
        summary = {k:v for k,v in report.items() if k not in {"rows","index_inputs","staging"}}
        if "staging" in report:
            staging = report["staging"]
            summary["staging"] = {"version_count":len(staging["versions"]),"staged_vectors":staging["staged_vectors"],
                "states":dict(Counter(r["state"] for r in staging["versions"])),
                "skipped_by_reason":dict(Counter(r["reason"] for r in staging["skipped"])),
                "new_model_calls":staging["new_model_calls"],"new_human_approvals":0,"release_activations":0}
        print(json.dumps(summary | {"report":str(target)}),flush=True)


if __name__ == "__main__":
    main()
