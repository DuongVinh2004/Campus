"""Local BM25 retrieval of immutable public HUCE sources with original citation reads."""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from campus247.domain.retrieval import RetrievalContext
from campus247.ports.citation_source import CitationSourceExcerpt
from campus247.infrastructure.llm.egress_policy import EMAIL_PATTERN, PHONE_PATTERN, IP_PATTERN


from campus247.application.knowledge.values import normalized, stable_id  # noqa: E402,F401 -- re-exported


def terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", normalized(text))
    return words + [a + "_" + b for a, b in zip(words, words[1:])]




def regulation_sections(pages: list[dict]) -> list[dict]:
    """Keep an article's conditions together when they cross a scanned page."""
    text, spans = "", []
    for page in pages:
        spans.append((len(text), page["page"]))
        text += page["text"] + "\n"
    matches = list(re.finditer(r"(?m)^\s*Đi[ềê]u\s+\d+\..*", text))
    if not matches:
        raise ValueError("readable regulation articles required")
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start():end].strip()
        first = max(page for offset, page in spans if offset <= match.start())
        last = max(page for offset, page in spans if offset < end)
        # Long articles stay in bounded consecutive paragraphs, with the
        # article heading repeated as locator data, never generated facts.
        while body:
            split = min(len(body), 5000)
            if split < len(body):
                split = body.rfind("\n", 1000, split) or split
            sections.append(dict(pages[0], text=body[:split], page=first, page_end=last,
                section=match.group().strip(), title="Quy chế đào tạo HUCE — Quyết định 1486 ngày 06/11/2023"))
            body = body[split:].strip()
    return sections


class PublicKnowledgeStore:
    def __init__(self, directory: Path, *, tenant_id: str, campus_id: str,
                 faq_directory: Path | None = None, include_reviewed_expansion: bool = True,
                 include_reviewed_services: bool = True, include_reviewed_course_review: bool = True,
                 include_reviewed_withdrawal: bool = True, include_reviewed_batch3_verified: bool = True,
                 include_reviewed_services_02: bool = True,
                 include_reviewed_corrections: bool = True,
                 reviewed_corrections_version: int | None = None, **kwargs):
        self.tenant_id, self.campus_id = tenant_id, campus_id
        if not include_reviewed_services:
            include_reviewed_services_02 = False
            include_reviewed_batch3_verified = False
        self.rows = []
        self.legacy_rows = []
        seen = set()
        course_release = directory / "reviewed-course-review-20261021.json"
        retired_excerpts = set()
        retired_handbook_excerpts = set()
        retired_batch3_titleonly_excerpts = set()
        if reviewed_corrections_version is not None and reviewed_corrections_version not in {3, 4, 6, 7} and reviewed_corrections_version < 8:
            raise ValueError("unsupported correction version")
        if reviewed_corrections_version is not None and (directory / f"reviewed-corrections-20261021-v{reviewed_corrections_version}.withdrawn.json").exists():
            raise ValueError("withdrawn unindexed pipeline candidate; retain as evidence only")
        pipeline_versions = []
        for marker in directory.glob("reviewed-corrections-20261021-v*.ready.json"):
            match = re.fullmatch(r"reviewed-corrections-20261021-v(\d+)\.ready\.json", marker.name)
            if match and int(match[1]) >= 8:
                if (directory / marker.name.replace('.ready.json','.withdrawn.json')).exists():
                    raise ValueError("withdrawn pipeline candidate cannot be activated")
                if reviewed_corrections_version is not None and int(match[1]) > reviewed_corrections_version:
                    continue
                receipt = json.loads(marker.read_text(encoding="utf-8"))
                release = directory / marker.name.replace(".ready.json", ".json")
                if hashlib.sha256(release.read_bytes()).hexdigest() != receipt["release_sha256"]:
                    raise ValueError("pipeline release changed after index verification")
                workspace = directory.parent.parent.resolve()
                index = (workspace / receipt["index"]).resolve()
                if (not index.is_relative_to(workspace) or not index.is_file()
                        or hashlib.sha256(index.read_bytes()).hexdigest() != receipt["index_sha256"]):
                    raise ValueError("pipeline index receipt mismatch")
                pipeline_versions.append(int(match[1]))
        if reviewed_corrections_version is not None and reviewed_corrections_version >= 8:
            # Explicit versions are used while building, before a ready receipt exists.
            if not (directory / f"reviewed-corrections-20261021-v{reviewed_corrections_version}.json").is_file():
                raise ValueError("pipeline release not found")
            pipeline_versions.append(reviewed_corrections_version)
        versions = sorted({3, 4, 6, 7, *pipeline_versions})
        corrections_names = tuple(f"reviewed-corrections-20261021-v{v}.json"
                                  for v in versions if reviewed_corrections_version is None or v <= reviewed_corrections_version)
        retired_correction_excerpts = set()
        correction_replacers = defaultdict(set)
        corrections_enabled = (include_reviewed_corrections and include_reviewed_expansion
                               and include_reviewed_services and include_reviewed_services_02
                               and include_reviewed_batch3_verified)
        for correction_name in corrections_names:
            if corrections_enabled and (directory / correction_name).exists():
                corrections = json.loads((directory / correction_name).read_text(encoding="utf-8"))
                if corrections.get("public_only") is not True or corrections.get("verification") != "source_verified_excerpts":
                    raise ValueError("source-verified corrections required")
                retired_correction_excerpts.update(item["replaces_excerpt_text_sha256"] for item in corrections["chunks"] if item.get("replaces_excerpt_text_sha256") is not None)
                for item in corrections["chunks"]:
                    if item.get("replaces_excerpt_text_sha256") is not None:
                        correction_replacers[item["replaces_excerpt_text_sha256"]].add(correction_name)
        withdrawal_release = directory / "reviewed-withdrawal-20261021.json"
        b3_verified_release = directory / "reviewed-curricula-batch3-verified-20261021.json"
        if include_reviewed_expansion and include_reviewed_batch3_verified and b3_verified_release.exists():
            b3_corr = json.loads(b3_verified_release.read_text(encoding="utf-8"))
            if b3_corr.get("public_only") is not True or b3_corr.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed batch3 correction required")
            retired_batch3_titleonly_excerpts = {item["replaces_excerpt_text_sha256"] for item in b3_corr["chunks"]}
        if include_reviewed_expansion and include_reviewed_services and include_reviewed_withdrawal and withdrawal_release.exists():
            correction = json.loads(withdrawal_release.read_text(encoding="utf-8"))
            if correction.get("public_only") is not True or correction.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed withdrawal correction required")
            retired_handbook_excerpts = {item["replaces_excerpt_text_sha256"] for item in correction["chunks"]}
        if include_reviewed_expansion and include_reviewed_services and include_reviewed_course_review and course_release.exists():
            correction = json.loads(course_release.read_text(encoding="utf-8"))
            if correction.get("public_only") is not True or correction.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed course correction required")
            retired_excerpts = {item["replaces_excerpt_text_sha256"] for item in correction["chunks"]}
        active = next(name for name in ("handbook-human-reviewed.json", "handbook-reviewed.json", "handbook-visible.json", "corpus.json")
                      if (directory / name).exists())
        regulations = "regulations-human-reviewed.json" if (directory / "regulations-human-reviewed.json").exists() else "regulations-ocr.json"
        legacy = tuple(name for name in ("corpus.json", "handbook-visible.json", "handbook-reviewed.json", "regulations-ocr.json")
                       if name not in {active, regulations} and (directory / name).exists())
        for name in (active, regulations, "supplemental-20261020.json", "reviewed-expansion-20261020.json",
                     "reviewed-expansion-20261020-batch2.json",
                     "reviewed-expansion-20261020-batch3-titleonly.json",
                     "reviewed-curricula-batch3-verified-20261021.json",
                     "reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json",
                     "reviewed-course-review-20261021.json",
                     "reviewed-withdrawal-20261021.json", *corrections_names, *legacy):
            if name in corrections_names and not corrections_enabled:
                continue
            if name == "reviewed-withdrawal-20261021.json" and not (include_reviewed_expansion and include_reviewed_services and include_reviewed_withdrawal):
                continue
            if name == "reviewed-course-review-20261021.json" and not (include_reviewed_expansion and include_reviewed_services and include_reviewed_course_review):
                continue
            if name == "reviewed-services-20261020-01.json" and (not include_reviewed_expansion or not include_reviewed_services):
                continue
            if name == "reviewed-services-20261021-02.json" and (not include_reviewed_expansion or not include_reviewed_services or not include_reviewed_services_02):
                continue
            if name == "reviewed-expansion-20261020.json" and not include_reviewed_expansion:
                continue
            if name == "reviewed-expansion-20261020-batch2.json" and not include_reviewed_expansion:
                continue
            if name == "reviewed-expansion-20261020-batch3-titleonly.json" and not include_reviewed_expansion:
                continue
            if name == "reviewed-curricula-batch3-verified-20261021.json" and not (include_reviewed_expansion and include_reviewed_batch3_verified):
                continue
            path = directory / name
            if not path.exists():
                continue
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("public_only") is not True:
                raise ValueError("public manifest required")
            reviewed_release = name in corrections_names or name in ("reviewed-expansion-20261020.json", "reviewed-expansion-20261020-batch2.json",
                                       "reviewed-expansion-20261020-batch3-titleonly.json",
                                       "reviewed-curricula-batch3-verified-20261021.json",
                                       "reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json",
                                       "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json")
            if name == "reviewed-withdrawal-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed withdrawal correction required")
            if name == "reviewed-course-review-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed course correction required")
            if name in ("reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json") and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed service release required")
            if reviewed_release and name == "reviewed-curricula-batch3-verified-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed batch3 verified release required")
            if reviewed_release and name == "reviewed-expansion-20261020.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed release required")
            if reviewed_release and name == "reviewed-expansion-20261020-batch2.json" and manifest.get("verification") != "automated_layout_extraction_verbatim_total_with_spot_check":
                raise ValueError("batch2 reviewed release required")
            if reviewed_release and name == "reviewed-expansion-20261020-batch3-titleonly.json" and manifest.get("verification") != "automated_layout_extraction_title_only_no_total_confirmed":
                raise ValueError("batch3 title-only release required")
            items = regulation_sections(manifest["chunks"]) if name.startswith("regulations-") else manifest["chunks"]
            for item in items:
                if reviewed_release:
                    snapshot = (directory.parent / item["source_file"]).resolve()
                    if (not snapshot.is_relative_to(directory.parent.resolve())
                            or hashlib.sha256(snapshot.read_bytes()).hexdigest() != item["source_sha256"]
                            or hashlib.sha256(item["text"].encode()).hexdigest() != item["text_sha256"]):
                        raise ValueError("reviewed original/excerpt hash mismatch")
                url = item["url"]
                if urlparse(url).scheme != "https" or not urlparse(url).hostname.endswith(".huce.edu.vn") and urlparse(url).hostname != "huce.edu.vn":
                    raise ValueError("official HUCE publication required")
                # Remove contact identifiers from model-facing excerpts; their
                # published originals remain in the retained source snapshot.
                content = EMAIL_PATTERN.sub("[liên hệ trên trang nguồn]", item["text"])
                content = PHONE_PATTERN.sub("[liên hệ trên trang nguồn]", content)
                content = IP_PATTERN.sub("[địa chỉ hệ thống]", content)
                # The booklet repeats the same two-page spread twice. Dedup it.
                content = re.sub(r"Trang\s+\d+", "", content).strip()
                digest = hashlib.sha256(content.encode()).hexdigest()
                pipeline_release = name in corrections_names and int(re.search(r"-v(\d+)\.json$", name)[1]) >= 8
                # Byte/text equality is a cache key, not proof of source identity.
                seen_key = (digest, item["download_url"]) if pipeline_release else digest
                # A replacement may preserve the exact excerpt while updating
                # its source review. Keep both versioned citations; the earlier
                # row is retired below rather than silently dropping its successor.
                replacement = pipeline_release and item.get("replaces_excerpt_text_sha256") == item.get("text_sha256")
                if seen_key in seen and name not in legacy and not replacement:
                    continue
                seen.add(seen_key)
                source_id = stable_id(url)
                version_id = stable_id(url + manifest["acquired_at"][:10])
                if reviewed_release:
                    source_id = stable_id(url + item["source_sha256"])
                    version_id = stable_id(url + item["source_sha256"] + manifest["acquired_at"])
                if pipeline_release:
                    source_id = stable_id(url + item["download_url"] + item["source_sha256"])
                    version_id = stable_id(url + item["download_url"] + item["source_sha256"] + manifest["acquired_at"])
                section = item["section"]
                row = {"source_id": source_id, "document_version_id": version_id,
                    "chunk_id": stable_id(url + digest + (item["download_url"] if pipeline_release else "")), "title": item["title"], "issuer": "HUCE",
                    "canonical_uri": url, "version_label": manifest.get("version_label", "public-20261013"), "source_status": "CURRENT",
                    "section_path": section, "locator": {"section_path": section},
                    "content_text": content, "quote_span_hash": digest, "simulation_label": False,
                    "effective_from": item.get("effective_from", "2026-10-13T00:00:00+07:00"), "effective_until": item.get("effective_until"),
                    "document_number": item.get("document_number"), "page_start": item.get("page"), "page_end": item.get("page_end", item.get("page"))}
                if item.get("page"):
                    row["locator"].update(page_start=item["page"], page_end=row["page_end"])
                if reviewed_release:
                    row["provenance"] = {"download_url": item["download_url"], "source_sha256": item["source_sha256"],
                                         "review_scope": item["review_scope"]}
                    if name in corrections_names or name in {"reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json", "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json", "reviewed-curricula-batch3-verified-20261021.json"}:
                        row["issuer"] = item["issuer"]
                        row["provenance"].update({key: item[key] for key in (
                            "source_file", "published_at", "collected_at", "applicability",
                            "legal_effective_from", "supersedes", "limitations", "ocr_quality",
                            "visual_evidence", "review_status")})
                if (name in legacy
                        or (item.get("text_sha256") or hashlib.sha256(item["text"].encode()).hexdigest()) in retired_correction_excerpts
                        and name not in correction_replacers[item.get("text_sha256") or hashlib.sha256(item["text"].encode()).hexdigest()]
                        or name == "reviewed-expansion-20261020-batch2.json" and item["text_sha256"] in retired_excerpts
                        or name == "reviewed-expansion-20261020-batch3-titleonly.json" and item["text_sha256"] in retired_batch3_titleonly_excerpts
                        or name == active and hashlib.sha256(item["text"].encode()).hexdigest() in retired_handbook_excerpts):
                    self.legacy_rows.append(row)
                else:
                    self.rows.append(row)
        if not self.rows:
            raise ValueError("nonempty official corpus required")
        self.counts = [Counter(terms(r["content_text"])) for r in self.rows]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / len(self.lengths)
        self.df = Counter(term for counts in self.counts for term in counts)
        self.faq_index = None
        if faq_directory is not None:
            from campus247.infrastructure.retrieval.public_faq_index import PublicFaqIndex
            self.faq_index = PublicFaqIndex(faq_directory, directory)

    def _authorized(self, context: RetrievalContext):
        if (not isinstance(context, RetrievalContext) or context.authorized_scope.tenant_id != self.tenant_id
                or context.authorized_scope.campus_id != self.campus_id
                or "STUDENT" not in context.authorized_scope.audiences):
            raise ValueError("trusted public-source scope required")

    async def search(self, query: str, context: RetrievalContext) -> list[dict]:
        self._authorized(context)
        stop = {"toi", "minh", "em", "ban", "cho", "hoi", "la", "thi", "va", "cua", "co", "duoc",
                "khong", "nhu", "the", "nao", "muon", "can", "xin", "ve", "bao", "nhieu",
                "quy", "che", "thu", "tuc", "dieu", "kien", "quy_che", "thu_tuc", "dieu_kien"}
        query_terms = set(terms(query)) - stop
        aliases = self.faq_index.source_matches(query) if self.faq_index else []
        scores = []
        n = len(self.rows)
        for row, counts, length in zip(self.rows, self.counts, self.lengths):
            if ("CƠ SỞ" in row["content_text"] and "HÀ NAM" in row["content_text"]
                    and "ha nam" not in normalized(query)):
                continue
            score = 0.0
            for term in query_terms:
                tf = counts[term]
                if tf:
                    idf = math.log(1 + (n - self.df[term] + .5) / (self.df[term] + .5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * length / self.average)) * (2 if "_" in term else 1)
            boosts = [boost for source, boost in aliases
                      if source["url"] == row["canonical_uri"]
                      and (source["pdf_page"] is None and row["page_start"] is None
                           or source["pdf_page"] is not None and row["page_start"] is not None
                           and row["page_start"] <= source["pdf_page"] <= row["page_end"])]
            if boosts:
                score += max(boosts)
            elif aliases and any(boost == 100.0 for _, boost in aliases):
                # An exact authored question already has complete original
                # source bindings. Do not dilute it with unrelated pages that
                # happen to share generic student/library vocabulary.
                continue
            if score > 0:
                # Accents distinguish chuyển ngành from chuyên ngành. An
                # exact phrase in the official section is stronger than the
                # shared syllables scattered over a department introduction.
                for phrase in ("chuyển ngành", "hoãn thi", "học bổng", "bảng điểm", "tự học", "học phí"):
                    if phrase in query.lower() and phrase in row["content_text"].lower():
                        score += 10
                scores.append((score, row))
        scores.sort(key=lambda pair: pair[0], reverse=True)
        # Bound source context by characters as well as count, with no invented
        # semantic vectors or fabricated reranker scores.
        results, size = [], 0
        for score, row in scores:
            if len(results) >= 3:
                break
            encoded_size = len(row["content_text"].encode("utf-8"))
            if size + encoded_size > 15000:
                continue
            results.append(dict(row, score=score))
            size += encoded_size
        return results

    async def read(self, source_id: str, version_id: str, chunk_id: str, *, context: RetrievalContext):
        self._authorized(context)
        row = next((r for r in (*self.rows, *self.legacy_rows) if (r["source_id"], r["document_version_id"], r["chunk_id"])
                    == (source_id, version_id, chunk_id)), None)
        if row is None:
            return None
        return CitationSourceExcerpt(source_id, version_id, chunk_id, row["title"], row["canonical_uri"],
            row["version_label"], row["source_status"], row["locator"], row["issuer"],
            datetime.fromisoformat(row["effective_from"]), None, row["content_text"], row["quote_span_hash"])
