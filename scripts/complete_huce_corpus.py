"""Resumable, additive HUCE corpus processing. No activation is implicit."""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import sys
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, retain
from campus247.application.knowledge.platform_models import EMBED_ARTIFACT, EMBED_MODEL, EMBED_REVISION, IntakeMetadata, digest
from campus247.application.knowledge.source_snapshot import PROCESSOR, validate_snapshot
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter
from campus247.infrastructure.retrieval.public_knowledge import normalized

SCOPE = checked_path(ROOT / "infra/local/huce-corpus-completion-20261024-01", ROOT)


def read(path):
    return json.loads(checked_path(path, ROOT).read_text(encoding="utf-8"))


def actors():
    adapter = LocalOwnerIdentityAdapter(checked_path(STATE / "owner-identity.json", ROOT), TENANT)
    directory = adapter.directory()
    return adapter.resolve_token(adapter.mint_token(directory["agent_id"])), adapter.resolve_token(adapter.mint_token(directory["owner_id"]))


def windows(text, max_bytes=10000):
    """Exact non-overlapping parent spans; no rewritten headings or facts."""
    start = 0
    while start < len(text):
        end = min(len(text), start + 4500)
        while len(text[start:end].encode()) > max_bytes:
            end -= 100
        if end < len(text):
            newline = text.rfind("\n", start + max(1, (end-start)//2), end)
            if newline > start:
                end = newline + 1
        if text[start:end].strip():
            yield start, end
        start = end


def cohorts_for(header, publication_scopes):
    explicit = sorted(set("K" + value for value in re.findall(r"\bK\s*(\d{2})\b", header, re.I)))
    codes = sorted(set(re.findall(r"\b(?:6\d|7[01])[A-Z][A-Z0-9]{1,9}\b", header)))
    if not explicit and "K71" in publication_scopes:
        # The exact official table row, not a generic filename, supplies K71.
        explicit = ["K71"]
    return explicit, codes


def publication_bindings(publication, original_sha256, uri):
    """Files are deduplicated; applicability belongs to every publication row."""
    files = [row for row in publication["files"]
        if row.get("sha256") == original_sha256 and row.get("url") == uri]
    drive_ids = {row["drive_id"] for row in files}
    return [row for row in publication["rows"] if row.get("drive_id") in drive_ids
        and row.get("url") == uri
        and row.get("publication_sha256") == publication["publication"]["sha256"]]


def reviewed_records():
    result = {}
    files = list((ROOT / "data/huce-public-20261013").glob("reviewed-corrections-20261021-v*.json"))
    files = [p for p in files if re.search(r"-v(\d+)\.json$", p.name)]
    for path in sorted(files, key=lambda p: int(re.search(r"-v(\d+)\.json$", p.name)[1])):
        for coverage in read(path).get("pipeline_coverage", []):
            record_path = checked_path(ROOT / coverage["review_file"], ROOT)
            record = read(record_path)
            if record.get("source_sha256"):
                result[record["source_sha256"]] = (record_path, record)
    return result


async def prepare():
    import pypdfium2 as pdfium
    from acquire_huce_public_knowledge import Text
    from huce_public_document_pipeline import Article, normalize
    inventory = read(SCOPE / "inventory-01.json")
    extraction_index = {row["original_sha256"]: row for row in read(SCOPE / "extraction-03-manifest.json")["originals"]}
    folder = checked_path(SCOPE / "candidates-02", ROOT)
    folder.mkdir(exist_ok=False)
    publication = read(ROOT / "data/huce-discovery-20261020/curricula-20261020T153323371137Z/manifest.json")
    pub = publication["publication"]
    publication_raw = checked_path(ROOT / pub["original_file"], ROOT).read_bytes()
    if digest(publication_raw) != pub["sha256"]:
        raise ValueError("Official curriculum publication changed")
    records = reviewed_records()
    pool, _, platform, _ = await components()
    results = []
    try:
        for source in inventory["sources"]:
            entry = {"source_id": source["source_id"], "title": source["title"], "uri": source["uri"]}
            if source["serving_version"]:
                results.append({**entry, "status": "SERVING_UNCHANGED", "version_id": source["serving_version"]})
                continue
            versions = [v for v in inventory["versions"] if v["source_id"] == source["source_id"]]
            old = versions[-1]
            async with pool.acquire() as conn:
                previous = await platform.repo.version(conn, old["version_id"])
                original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", previous["original_id"], TENANT)
            raw = platform.storage.read(original)
            if digest(raw) != old["original_sha256"]:
                raise ValueError("Inventory original changed")
            extraction = read(ROOT / extraction_index[old["original_sha256"]]["extraction"])
            title = source["title"].lower()
            curriculum = any(term in title for term in ("kế hoạch giảng dạy", "k70_and_earlier", "k71 —", "ngành kiến trúc nội thất", "sơ đồ cấu trúc"))
            kind = "COHORT_SNAPSHOT" if curriculum else "EVENT_SNAPSHOT" if "hội nghị" in title or "fit_cma" in title else "INFORMATION_SNAPSHOT"
            if "quy chế đào tạo" in title:
                results.append({**entry, "status": "LEGAL_EFFECT_REVIEW", "reason": "Source decision and OCR need an explicitly verified effectivity clause; snapshot admission is not used for this regulation.", "original_sha256": old["original_sha256"]})
                continue
            pages = extraction.get("pages", [])
            witness = None
            record = records.get(old["original_sha256"])
            if record and record[1].get("kind") == "reviewed_public_document":
                try:
                    checked = normalize(record[1]["review_dossier"])
                    if checked != record[1]:
                        raise ValueError("Retained review no longer reproduces")
                except (AssertionError, ValueError, KeyError, ImportError) as error:
                    results.append({**entry, "status": "REVIEW_REPRODUCTION_REQUIRED", "error": type(error).__name__,
                        "review_file": str(record[0].relative_to(ROOT)), "original_sha256": old["original_sha256"]})
                    continue
                pages = [{"page": unit.get("page"), "text": unit["text"]} for unit in checked["units"]]
                witness = {"path": str(record[0].relative_to(ROOT)), "sha256": digest(record[0].read_bytes()),
                    "verification": "normalizer rerun; exact record reproduced; not university approval"}
            elif not raw.startswith(b"%PDF-") and raw.startswith(b"PK"):
                with ZipFile(io.BytesIO(raw)) as archive:
                    info = archive.getinfo("word/document.xml")
                    if info.file_size > 8 * 1024**2:
                        raise ValueError("DOCX_XML_LIMIT")
                    document = ET.fromstring(archive.read(info))
                namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                text = "\n".join("".join(p.itertext()) for p in document.findall(".//w:body/w:p", namespace))
                pages = [{"page": None, "text": text}]
            elif extraction["kind"] == "HTML":
                parser = Article(); parser.feed(raw.decode("utf-8-sig"))
                if parser.found == 1 and len(parser.text().strip()) >= 50:
                    pages = [{"page": None, "text": parser.text()}]
                else:
                    # Keep only exact legacy spans when the page lacks the known
                    # article container, avoiding navigation/recent-news pollution.
                    visible = pages[0]["text"] if pages else ""
                    async with pool.acquire() as conn:
                        chunks = await conn.fetch("SELECT DISTINCT content_text FROM knowledge_chunk WHERE document_version_id=$1", old["version_id"])
                    exact = [row["content_text"] for row in chunks if row["content_text"] in visible and len(row["content_text"].strip()) >= 50]
                    if exact:
                        pages = [{"page": None, "text": value} for value in sorted(set(exact), key=visible.find)]
                    else:
                        results.append({**entry, "status": "ARTICLE_OR_ATTACHMENT_REVIEW", "reason": "No unique article region or exact clean source span; linked attachment must be bound separately.", "original_sha256": old["original_sha256"]})
                        continue
            omitted = [p["page"] for p in pages if len(p["text"].strip()) < 50]
            usable = [p for p in pages if len(p["text"].strip()) >= 50]
            if not usable:
                results.append({**entry, "status": "OCR_OR_DIAGRAM_REVIEW", "reason": "No sufficient native source text; reuse a source-bound verified transcript or review original images.", "original_sha256": old["original_sha256"]})
                continue
            blocks = [{"block_id": str(i), **page} for i, page in enumerate(usable)]
            selectors = []
            for block in blocks:
                for start, end in windows(block["text"]):
                    text = block["text"][start:end]
                    selectors.append({"block_id": block["block_id"], "page": block["page"], "char_start": start, "char_end": end,
                        "text": text, "text_sha256": digest(text.encode()), "section": f"{source['title']} · " + (f"trang {block['page']}" if block["page"] else "nội dung nguồn") + f" · chars {start}:{end}"})
            pub_rows = publication_bindings(publication, old["original_sha256"], source["uri"])
            pub_scopes = {r["scope"] for r in pub_rows}
            header = usable[0]["text"].split("Học kỳ", 1)[0][:1200]
            cohorts, codes = cohorts_for(header, pub_scopes)
            at = datetime.now(UTC).isoformat()
            scope = {"kind": kind, "reviewed_at": at, "admission_only": True, "legal_effective_from": None,
                "cohorts": cohorts, "programme_codes": codes, "relations_verified": False,
                "limitations": ["No inferred arrow relationships; not a claim of full diagram interpretation"] if curriculum else [],
                "omitted_sparse_pages": omitted}
            extracted = {"original_sha256": old["original_sha256"], "extractor": extraction["processor"], "blocks": blocks,
                "review_witness": witness, "publisher_witness": {"uri": pub["url"], "sha256": pub["sha256"], "rows": pub_rows} if pub_rows else None}
            candidate = {**entry, "status": "PREPARED", "previous_version_id": old["version_id"], "original_sha256": old["original_sha256"],
                "applicability": scope, "extracted": extracted, "pages": selectors, "issues": [], "processor": PROCESSOR}
            validate_snapshot(candidate, extracted, original_sha256=old["original_sha256"], effective_from=datetime.fromisoformat(at))
            path = checked_path(folder / (source["source_id"] + ".json"), ROOT)
            retain(path, candidate)
            results.append({**entry, "status": "PREPARED", "candidate": str(path.relative_to(ROOT)), "candidate_sha256": digest(path.read_bytes()),
                "kind": kind, "parents": len(selectors), "sparse_pages": omitted, "cohorts": cohorts})
        retain(SCOPE / "candidate-plan-01.json", {"sources": results, "counts": dict(Counter(r["status"] for r in results))})
        print(json.dumps({"counts": dict(Counter(r["status"] for r in results)), "parents": sum(r.get("parents", 0) for r in results),
            "remaining": [r for r in results if r["status"] not in {"PREPARED", "SERVING_UNCHANGED"}]}, ensure_ascii=False), flush=True)
    finally:
        await pool.close()


async def stage(limit=None, plan_name="candidate-plan-01.json"):
    sys.path.insert(0, str(ROOT / "infra/local/rag-fixture"))
    from token_envelope_20261007_25 import TokenEnvelope
    from campus247.ports.embedding import EmbeddingContractError
    envelope = TokenEnvelope()
    pool, _, platform, runtime = await components()
    author, _ = actors()
    receipts = checked_path(SCOPE / "staged", ROOT); receipts.mkdir(exist_ok=True)
    cache = checked_path(SCOPE / "embedding-cache", ROOT); cache.mkdir(exist_ok=True)
    planned = read(SCOPE / plan_name)["sources"]
    done = 0
    try:
        for planned_source in planned:
            if planned_source["status"] != "PREPARED":
                continue
            receipt_path = checked_path(receipts / (planned_source["source_id"] + ".json"), ROOT)
            if receipt_path.is_file():
                if read(receipt_path)["candidate_sha256"] == planned_source["candidate_sha256"]:
                    continue
                receipt_path = checked_path(receipts / (planned_source["source_id"] + "-" + planned_source["candidate_sha256"][:12] + ".json"), ROOT)
                if receipt_path.is_file():
                    continue
            if limit is not None and done >= limit:
                break
            candidate_path = checked_path(ROOT / planned_source["candidate"], ROOT)
            if digest(candidate_path.read_bytes()) != planned_source["candidate_sha256"]:
                raise ValueError("Candidate changed")
            candidate = read(candidate_path)
            async with pool.acquire() as conn:
                previous = await platform.repo.version(conn, candidate["previous_version_id"])
                original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", previous["original_id"])
            old_raw = platform.storage.read(original)
            replacement = None
            if candidate.get("replacement_original"):
                binding = candidate["replacement_original"]
                if (digest(old_raw) != binding["publisher_sha256"] or binding["published_attachment"].encode() not in old_raw
                        or not previous["canonical_uri"].startswith("https://ctsv.huce.edu.vn/")
                        or previous["revoked_at"]):
                    raise ValueError("Linked original publisher binding mismatch")
                replacement = platform.storage.copy_original(checked_path(ROOT / binding["file"], ROOT), candidate["original_sha256"], "application/pdf")
                previous = {**dict(previous), "original_sha256": replacement.sha256, "original_id": replacement.id,
                    "object_key": replacement.object_key, "filename": "notice-1106-2025-original.pdf"}
            elif digest(old_raw) != candidate["original_sha256"] or previous["revoked_at"]:
                raise ValueError("Source changed or revoked")
            chunks = []
            for page_number, page in enumerate(candidate["pages"]):
                text = page["text"]
                header = candidate["extracted"]["blocks"][int(page["block_id"])]["text"][:150]
                start = 0
                while start < len(text):
                    end = min(len(text), start + 650)
                    if end < len(text):
                        cut = text.rfind("\n", start + 350, end)
                        if cut > start: end = cut + 1
                    index_text = normalized(header + "\n" + text[start:end])
                    while envelope.count("embedding", index_text) > 300 and end - start > 80:
                        end = start + (end - start) * 3 // 4
                        index_text = normalized(header + "\n" + text[start:end])
                    input_sha = digest(index_text.encode())
                    vector_path = checked_path(cache / (input_sha + ".json"), ROOT)
                    if vector_path.is_file():
                        vector_record = read(vector_path)
                        if vector_record["input_sha256"] != input_sha or vector_record["model"] != EMBED_MODEL + "@" + EMBED_REVISION:
                            raise ValueError("Cached embedding identity mismatch")
                        vector = vector_record["values"]
                    else:
                        try:
                            batch = await runtime.embedding._embed((index_text,))
                        except EmbeddingContractError:
                            retain(SCOPE / ("embedding-failure-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json"),
                                {"source_id": candidate["source_id"], "input_sha256": input_sha, "response": "embedding rejected; no vector accepted",
                                 "repair": "smaller exact span; deadline and native guards unchanged"})
                            end = start + max(40, (end-start)//2)
                            index_text = normalized(header + "\n" + text[start:end])
                            input_sha = digest(index_text.encode())
                            vector_path = checked_path(cache / (input_sha + ".json"), ROOT)
                            if vector_path.exists():
                                batch = None
                                vector = read(vector_path)["values"]
                            else:
                                batch = await runtime.embedding._embed((index_text,))
                        if batch is not None:
                            vector = list(batch.vectors[0].values)
                            retain(vector_path, {"input_sha256": input_sha, "model": EMBED_MODEL + "@" + EMBED_REVISION, "values": vector})
                        await asyncio.sleep(.05)
                    chunks.append({"text": text, "page": page["page"], "page_end": page.get("page_end", page["page"]),
                        "section": page["section"], "index_text": index_text,
                        "input_sha256": input_sha, "vector": vector, "provenance": {"original_sha256": candidate["original_sha256"],
                            "evidence_sha256": page["text_sha256"], "index_header": header, "source_block": page["block_id"],
                            "rerank_span": {"char_start": start, "char_end": end}}})
                    if end == len(text): break
                    start = max(start + 1, end - 120)
            identifier = generate_uuid7()
            source_artifact = platform.storage.write_json(json.dumps(candidate["extracted"], ensure_ascii=False, sort_keys=True).encode(), "verified_source_text")
            rendition = {k: candidate[k] for k in ("processor", "original_sha256", "pages", "issues", "applicability")}
            rendition.update(source_extraction_id=source_artifact.id, source_extraction_sha256=source_artifact.sha256)
            artifact = platform.storage.write_json(json.dumps(rendition, ensure_ascii=False, sort_keys=True).encode(), "verified_snapshot")
            metadata = IntakeMetadata(title=previous["title"], owner_unit=previous["owner_unit"], canonical_uri=previous["canonical_uri"],
                campus=previous["campus_scope"], faculties=previous["faculty_scope"], programs=previous["program_scope"],
                audiences=previous["audiences"], authority_level=previous["authority_level"], effective_from=datetime.fromisoformat(
                    candidate["applicability"].get("legal_effective_from") or candidate["applicability"]["reviewed_at"]))
            metadata_sha = digest(metadata.model_dump(mode="json", exclude={"source_id"}))
            validate_snapshot(rendition, candidate["extracted"], original_sha256=previous["original_sha256"], effective_from=metadata.effective_from)
            index_id = "verified-snapshot-" + identifier
            async with platform.repo.transaction() as conn:
                fingerprint = digest({"candidate": planned_source["candidate_sha256"], "processor": PROCESSOR})
                key = "corpus-20261024:" + candidate["source_id"] + ":" + planned_source["candidate_sha256"][:12]
                replay = await platform.repo.replay(conn, author.subject_id, key, fingerprint)
                if replay:
                    retain(receipt_path, replay); done += 1; continue
                if replacement is not None:
                    await platform.repo.artifact(conn, replacement)
                await platform.repo.artifact(conn, source_artifact); await platform.repo.artifact(conn, artifact)
                await conn.execute("""INSERT INTO document_version(id,knowledge_source_id,version_label,content_checksum,status,storage_object_key,effective_from)
                    VALUES($1,$2,$3,$4,'DRAFT',$5,$6)""", identifier, previous["source_id"],
                    ("verified-effective-" if candidate["applicability"]["kind"] == "LEGAL_EFFECT" else "public-snapshot-") + identifier,
                    previous["original_sha256"], previous["object_key"], metadata.effective_from)
                await conn.execute("""INSERT INTO knowledge_ingest_version(version_id,tenant_id,original_id,filename,created_by,metadata_sha256,
                    processor_profile,rendition_id,rendition_sha256,review_state) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,'NEEDS_REVIEW')""",
                    identifier, TENANT, previous["original_id"], previous["filename"], author.subject_id, metadata_sha, PROCESSOR, artifact.id, artifact.sha256)
                for ordinal, chunk in enumerate(chunks):
                    chunk_id = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_chunk(id,document_version_id,ordinal,section_path,page_start,page_end,content_text,
                        content_checksum,content_tsv,embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at)
                        VALUES($1,$2,$3,$4,$5,$11,$6,$7,to_tsvector('simple',$8),$9::vector(1024),$10,1024,clock_timestamp())""",
                        chunk_id, identifier, ordinal, chunk["section"], chunk["page"], chunk["text"], digest(chunk["text"].encode()),
                        chunk["index_text"], "[" + ",".join(str(v) for v in chunk["vector"]) + "]", EMBED_MODEL + "@" + EMBED_REVISION,
                        chunk["page_end"])
                    await conn.execute("""INSERT INTO knowledge_chunk_input(chunk_id,index_text,input_sha256,processor_profile,provenance)
                        VALUES($1,$2,$3,$4,$5::jsonb)""", chunk_id, chunk["index_text"], chunk["input_sha256"], PROCESSOR, json.dumps(chunk["provenance"]))
                profile = asdict(load_retrieval_profile()); fields = list(profile)
                await conn.execute("INSERT INTO retrieval_profile(" + ",".join(fields) + ",created_at,approved_at,approval_reference) VALUES (" +
                    ",".join("$"+str(i+1) for i in range(len(fields))) + ",clock_timestamp(),clock_timestamp(),'HUCE_CORPUS_COMPLETION_20261024') ON CONFLICT DO NOTHING", *profile.values())
                await conn.execute("""INSERT INTO embedding_index_manifest(index_version,profile_version,embedding_model_id,embedding_model_revision,
                    artifact_sha256,dimension,normalization,distance_metric,corpus_version,document_count,chunk_count,content_checksum,build_status,built_at,validated_at)
                    VALUES($1,$2,$3,$4,$5,1024,'l2','cosine',$6,1,$7,$8,'READY',clock_timestamp(),clock_timestamp())""", index_id,
                    profile["profile_version"], EMBED_MODEL, EMBED_REVISION, EMBED_ARTIFACT, previous["original_sha256"], len(chunks), fingerprint)
                await conn.execute("UPDATE document_version SET index_version=$2 WHERE id=$1", identifier, index_id)
                job = generate_uuid7()
                await conn.execute("INSERT INTO knowledge_ingestion_job(id,tenant_id,version_id,state,stage,progress) VALUES($1,$2,$3,'SUCCEEDED','SOURCE_REVIEW',100)", job, TENANT, identifier)
                result = {"source_id": candidate["source_id"], "version_id": identifier, "candidate_sha256": planned_source["candidate_sha256"],
                    "chunks": len(chunks), "parents": len(candidate["pages"]), "kind": candidate["applicability"]["kind"], "review_state": "NEEDS_REVIEW"}
                await platform.repo.audit(conn, author.subject_id, "knowledge.snapshot.version", identifier,
                    {"original_sha256": previous["original_sha256"], "rendition_sha256": artifact.sha256, "admission_is_not_legal_effectivity": True})
                await platform.repo.remember(conn, author.subject_id, key, fingerprint, result)
                await platform.repo.outbox(conn, "knowledge.snapshot.prepared", identifier, result)
            retain(receipt_path, result)
            done += 1
            print(json.dumps({"staged": done, **result}, ensure_ascii=False), flush=True)
    finally:
        await pool.close()


async def review_and_build(build=False, plan_name="candidate-plan-01.json"):
    from campus247.application.knowledge.platform_models import ReviewInput
    from campus247.application.knowledge.source_snapshot import read_snapshot
    from campus247.ports.embedding import validate_embedding_vector
    pool, _, platform, runtime = await components()
    _, reviewer = actors()
    folder = checked_path(SCOPE / "technical-reviews", ROOT); folder.mkdir(exist_ok=True)
    results = []
    desired = {entry["source_id"]: entry.get("candidate_sha256") for entry in read(SCOPE / plan_name)["sources"] if entry["status"] == "PREPARED"}
    try:
        for receipt_path in sorted((SCOPE / "staged").glob("*.json")):
            receipt = read(receipt_path)
            if desired.get(receipt["source_id"]) != receipt["candidate_sha256"]:
                continue
            target = checked_path(folder / (receipt["version_id"] + ".json"), ROOT)
            if target.is_file():
                results.append(read(target)); continue
            async with pool.acquire() as conn:
                row = await platform.repo.version(conn, receipt["version_id"])
                scope = await read_snapshot(platform, conn, row)
                chunks = await conn.fetch("""SELECT c.content_text,c.content_checksum,c.embedding_rag_v1::text AS vector,
                    ci.index_text,ci.input_sha256 FROM knowledge_chunk c JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id
                    WHERE c.document_version_id=$1""", receipt["version_id"])
                for chunk in chunks:
                    if (digest(chunk["content_text"].encode()) != chunk["content_checksum"]
                            or chunk["content_checksum"] not in scope["_evidence_hashes"]
                            or digest(chunk["index_text"].encode()) != chunk["input_sha256"]):
                        raise ValueError("Candidate source/input integrity mismatch")
                    validate_embedding_vector(json.loads(chunk["vector"]), runtime.embedding.profile)
                if len(chunks) != receipt["chunks"]:
                    raise ValueError("Candidate index count mismatch")
            note = ("Duyệt kỹ thuật TỰ ĐỘNG theo ủy quyền chủ hệ thống trong chat; KHÔNG phải xác nhận của cán bộ HUCE. "
                "Đã kiểm hash original/extraction/rendition, đoạn nguyên văn và locator, input/model/vector thật; giữ giới hạn phạm vi trong bản nguồn. "
                "Ngày admission của bản chụp KHÔNG được coi là ngày hiệu lực pháp lý. "
                "Native text không tự chứng minh quan hệ mũi tên hoặc toàn bộ bố cục; các phần đó vẫn giữ ngoài phạm vi xác nhận.")
            if row["review_state"] != "APPROVED":
                await platform.review(reviewer, receipt["version_id"], ReviewInput(expected_revision=row["revision"], verdict="APPROVED", note=note))
            async with pool.acquire() as conn:
                await platform._eligible(conn, receipt["version_id"], publisher=reviewer.subject_id)
            result = {**receipt, "review_state": "APPROVED", "review_note": note,
                "source_integrity": True, "embedding_integrity": True, "university_approval_claimed": False}
            retain(target, result); results.append(result)
        if build:
            identifiers = [row["version_id"] for row in results]
            attempt = plan_name.removeprefix("candidate-plan-").removesuffix(".json")
            result = await platform.build_batch_release(reviewer, identifiers, "corpus-completion-20261024-candidate-" + attempt)
            retain(SCOPE / ("candidate-release-" + attempt + ".json"), result)
            print(json.dumps({"release_id": result["release_id"], "members": len(result["members"]), "expected_generation": result["expected_generation"], "activated": False}))
        else:
            print(json.dumps({"technically_reviewed": len(results), "activated": False}))
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "stage", "review", "build"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--plan", default="candidate-plan-01.json")
    args = parser.parse_args()
    if not re.fullmatch(r"candidate-plan-\d{2}\.json", args.plan):
        raise ValueError("Exact task-owned plan filename required")
    asyncio.run(prepare() if args.mode == "prepare" else stage(args.limit, args.plan) if args.mode == "stage" else review_and_build(args.mode == "build", args.plan))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
