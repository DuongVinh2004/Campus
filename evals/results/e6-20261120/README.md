# E6: malware scanning through the API with the real ClamAV daemon (2026-11-20)

Runtime started with the scanner on (`/health/ready`: `upload-scanner` and `learning-scanner` ready; signatures 12.6 h old, engine 1.5.4). `python scripts/qa/scan_check.py`:

- a clean text file: **202 accepted**;
- the EICAR test string (built in memory from three pieces, never written to a disk by the client): **before this change HTTP 503 `SCANNER_UNAVAILABLE` after the 75 s retry window; now HTTP 422 `FILE_REJECTED` at once**.

Why it was 503: the API writes the upload to disk, then streams it to clamd. Windows Defender removes (or locks, error 225) a file holding the EICAR string as soon as it is closed, so the read failed and the failure was reported as "scanner unavailable" and retried. A file that the host's own protection removes or refuses to read is a detection, so `ClamdScanner` now raises `ScanRejected("HOST_PROTECTION_BLOCKED")` for a vanished file and for winerror 225/226; other read errors and a missing daemon stay "unavailable" (tested, 4 new tests; the 39 scanner unit tests pass).

Honest limit: on this machine the rejection of the EICAR upload comes from Defender's action plus this rule, not from a clamd `FOUND` verdict. The clamd verdict path (`INSTREAM` -> `Eicar-Test-Signature FOUND`) was proven earlier directly against the daemon and by the real-daemon tests.

Left behind by the check: two documents titled "QA-scan-check sạch" in state AWAITING_REVIEW (never published, never served). The owner cannot reject documents they submitted themselves; a second administrator can reject them from /knowledge/documents.
