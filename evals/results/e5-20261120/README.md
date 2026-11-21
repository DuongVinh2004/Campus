# E5: release trial on the live runtime (2026-11-20)

`node scripts/qa/release_trial.mjs`: the owner publishes a synthetic QA text (made-up opening hours of a made-up laboratory) directly, the chatbot is asked, the document is revoked, the index is checked.

**Clean run (`clean-run.log`): 8/8.** Accepted (202); PROCESSING -> READY_TO_PUBLISH 5 s -> INDEXING 35 s -> **ACTIVE 70 s**; index 9173 -> 9176 units (release/generation changed); the chatbot answered "mở cửa lúc 06:45 và đóng cửa lúc 19:15" with a citation to the document; revoked (200); index back to **9173 units** (generation advanced 30 -> 31, a revoke is a new release); after the revocation the chatbot no longer knows the fact.

**First attempt (`first-attempt-and-resume.log`)** published the document too (index 9176) but the script died on one `ECONNRESET` while the API swapped the index, before it could revoke; the QA document stayed ACTIVE until `scripts/qa/revoke_qa_documents.mjs --apply` / the resumed run revoked it (index back to 9173). The script now retries a request up to 8 times and revokes in `finally`. The resumed run's "becomes usable" FAIL is a bug of the `--resume` path (it looked for a new URI); the clean run is the evidence.

Needs the ingest worker (start the runtime without `--defer-worker`); free RAM stayed at 2.9-3.0 GB during the trial.
