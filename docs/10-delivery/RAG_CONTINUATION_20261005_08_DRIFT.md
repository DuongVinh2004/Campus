# Post-verification frontend drift, 2026-10-05

Final preservation audit `infra/local/rag-fixture/chat-stream-20261005-08-final-scope.json` (SHA256 `9fc5831b8c47d397079852149a370df94c23acdc9f5c08ab30b835347f74f643`) records21 pre-existing frontend files changed after the successful browser checkpoint. The executor changed only `services/api/src/campus247/infrastructure/llm/openai_adapter.py`; reverse-patch hashing proves preservation of all other bytes in that file. External changes were preserved, not restored or overwritten.

Affected files include `ChatPanel.tsx`, `ChatPanel.test.tsx`, `AppShell.tsx`, `AppShell.test.tsx`, application/login pages/layout, e2e specs, handover/privacy/schedule components, `VinUniForm.tsx`, certificate service, next-env and tsbuildinfo. Full exact before/current hashes are in the audit, including each path.

The browser passed21/21 against its tested client bundle and the baseline source, and the immediate post-browser checkpoint found no pre-existing drift. That result establishes browser environment recovery and the tested streaming behavior. It does **not** certify the later changed frontend. Current frontend acceptance is `not_verified`; do not promote its state from the historical successful run.

P-FE-BROWSER-007 authorized one additional startup attempt, which succeeded. No further browser attempt or frontend mutation was performed in this continuation. A subsequent verification must bind a stable current source snapshot and preserve the external work; it must not silently reset to the old tested version.

The backend request-limit patch and the standalone live DeepSeek receipt retain their recorded scope. Overall M1/M2/M3, runtime clearance and corpus production publication remain `not_verified`. The final audit found zero persisted configured API-key values in new artifacts and no changes to308 verified browser-cache files.

This addendum is a new standalone explanation of the immutable final audit; historical report, receipts and final-scope files remain unchanged.
