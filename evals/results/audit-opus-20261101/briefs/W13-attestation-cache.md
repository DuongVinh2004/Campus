# W13 — INJ-06 latency: stop re-attesting the same source many times per turn

Workspace: C:\Users\Duong Vinh\Vinh (branch rag-v2-hardening). Report in Vietnamese. Owner approved fixing the INJ-06 latency (2026-11-03).

## Measured problem (do not re-measure with paid calls)
The multi-part audit question INJ-06 (case file `evals/results/audit-opus-20261101/inj06.jsonl`) hits the 12 s node deadline in `services/api/src/campus247/agent/nodes/rag_v2.py` (`asyncio.timeout(12)`) and the user gets an error. Temporary timing logs showed: generation done at ~7.4 s, semantic verification done at ~10.0 s, service returned at ~10.5 s, then the node's post-service steps (`live = await revalidate(cited_chunks)` and the final `await revalidate(cited_chunks)`) add ~1.5 s, so the timeout fires at 12 s just before the answer is returned.
The extra time is `verified_attachment` (`services/api/src/campus247/infrastructure/knowledge/publication.py`), called from `infrastructure/knowledge/runtime.py` (`attest=True` read path, around lines 664-672, and the search path around 527-531) every time a source is revalidated. For the student handbook (the pinned receipt added for L-12) each call costs ~120 ms (reads 710 KB HTML + viewer HTML + PDF/rendition from disk, hashes them, queries artifacts) and it runs once per cited chunk per revalidation, i.e. dozens of times per turn.

## Do
1. Add a small in-process, time-bounded memo around `verified_attachment` in `publication.py` so the identical attestation is not recomputed within a short window. Key it by everything the result depends on: `row["id"]` (or chunk id), `row["content_checksum"]`, `row["document_version_id"]`, `release_id`, `row["canonical_uri"]`. Store both successes and `None` (fail closed). TTL 30 seconds (a module constant), monotonic clock, max 512 entries (drop the oldest). Never cache an exception. The memo must be per `platform` instance or include `id(platform.storage.workspace)`/the workspace path in the key so tests with different roots never share entries. Keep it thread/async safe enough (single event loop; a plain dict is fine, no await between check and set that could return a stale result for a different key).
2. Do not change what `verified_attachment` verifies (hash-pinned receipts, official publisher, link mapping, original hash, rendition check). A cache miss behaves exactly as today. Provide a way for tests to bypass or clear the memo (`clear_attachment_cache()`).
3. Tests (new file `tests/knowledge_platform/test_attachment_cache.py`, no network, no paid calls): (a) two identical calls within the TTL perform the underlying verification once (count reads/DB calls with a fake platform or a counter patched into the inner function); (b) a different checksum / version / release / canonical uri does not reuse the entry; (c) after the TTL (patch the clock) it recomputes; (d) a `None` result is cached but also expires; (e) existing `tests/knowledge_platform/test_stem_publication_binding.py`, `test_regulation_publication_binding.py`, `test_handbook_publication_binding.py` still pass untouched.
4. Run `.venv/Scripts/python.exe -B -m pytest tests/knowledge_platform tests/rag_v2 tests/unit/retrieval -q -p no:cacheprovider --basetemp=.pytest-tmp-w13`. All must pass.
5. Do NOT restart or stop any service; the owner restarts the API and measures INJ-06.

## Do not
- Do not change the 12 s deadline, any verification or guard logic, retrieval, prompts, other receipts, or test expectations of existing tests.
- Do not commit, push, reset, clean or delete anything. Do not print secrets. Do not call any paid model.

## Report
Write `evals/results/audit-opus-20261101/impl/W13-report.md`: files changed (short diff summary), the key and TTL chosen and why it is safe (what could be stale for at most 30 s and why that does not weaken the attestation), the tests added and the pytest result.
