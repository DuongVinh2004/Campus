---
document_id: "DOC-DELIVERY-RAG-RESULT-20261005"
version: "0.4.35"
status: "draft"
owner: "Implementation executor"
last_updated: "2026-10-12"
---

# Kết quả triển khai Campus 24/7

Đây là báo cáo kết quả duy nhất, cập nhật đến lượt `m2-20261012-71`. Giữ nguyên hồ sơ
và bằng chứng lịch sử theo lựa chọn trực tiếp của người dùng. Báo cáo không thay
requirements hoặc thresholds. Điều kiện chữ ký/review độc lập đã được người dùng
bỏ trực tiếp trong scope hiện tại theo [DEC-022](../00-governance/RAG_ACCEPTANCE_AUTHORITY_DECISION_20261006.md).

**Hiện tại: đã quan sát đủ 1.828/1.828 khóa benchmark M2 synthetic theo các
giai đoạn được đối chiếu; 1.807 đạt, 21 câu nối tiếp lỗi claim rỗng. M2 vẫn
not_verified; M1 completed trong phạm vi đã nghiệm thu; release toàn hệ thống NO-GO.**
Hội thoại đạt129/150 (86%), dưới ngưỡng90%. Hai lần sửa hội thoại cải thiện kết
quả nhưng chưa đóng được lỗi; không đổi expected facts, grader hoặc thresholds.
756 offline tests và scoped lint PASS. Native3.000ms, adapter5.000ms,
retrieval10.500ms; classifier/intent/generation request deadlines5.000ms.
Ở lượt71, retrieval thành công và provider kết thúc bình thường cho các21 lỗi;
đây là lỗi output, không phải timeout. Whole-M2 conservative costUSD0,9357615/1,
cònUSD0,0642385; actual invoice unknown, giữ full caps cho5 unknown reservations.

Bằng chứng gồm1.444 lượt reference còn tương đương,234 lượt security/regression/
first-turn của70 và150 follow-ups mới ở71. Có2.084 lượt benchmark thực tế qua
các giai đoạn, giữ cả lỗi cũ. Follow-ups71 được thêm vào hội thoại70 đã lưu,
có lịch sử của lượt lỗi; **không tuyên bố một lần chạy lại toàn bộ final build
hoặc hội thoại mới chỉ có hai lượt**. Corpus gồm628 chunks/608 nguồn hư cấu,
8 mẫu scalar dùng chung và câu hỏi chủ yếu chỉ đích danh văn bản; chưa chứng minh
QA tổng quát, corpus quy định thật, M3 hoặc production. DEC-023 và chỉ dẫn linh
hoạt của người dùng áp dụng cho engineering local/synthetic, giữ bảo toàn dữ liệu.

Public M1 vẫn3 conversations/27 messages và accepted index cũ. Read-only audit
đối chiếu nguyên vẹn public rows/indexes, schemas61/62/64,8 finals của66 và
2.048 finals của67/68/70/71;628 vectors FP32 và nội dung nguồn không đổi.
Owned fixture/runtime đã dừng, volume và mọi evidence được giữ. Xem
[kết quả71](../../infra/local/rag-fixture/m2-20261012-71/M2-closure.json),
[21 lỗi còn lại](../../infra/local/rag-fixture/m2-20261012-71/remaining-defects.json)
và chi tiết65–71 cuối báo cáo. Toàn bộ nội dung lịch sử từ mục đầu tiên phía dưới
được giữ nguyên từng byte.

**Trạng thái lịch sử lượt29/30, trước khi hoàn tất source-open:** đã review và chạy ONNX
Runtime1.30.0 signed Microsoft C API, chạy embedding/reranker checkpoint thật,
tạo **15 vectors1024**, publish additive10 rows và activate **1-source tuition
smoke index** trong owned PostgreSQL. Chỉ1/15 vectors được publish; 14 vectors
còn ở artifact, không tuyên bố full corpus đã activate. Native runtime/index
không còn ở trạng thái0 như hồ sơ lượt28 phía dưới. Không bypass Windows policy
đã chặn Rust, không launch original TEI/wheels chưa clearance.

**Trạng thái lịch sử lượt56: timeout đã tháo trong phạm vi synthetic đo được;
M1 vẫn not_verified / NO-GO vì source-open qua authorization chưa đạt.**
Candidate native1,600ms / adapter2,100ms / retrieval4,700ms đạt cả Q1/Q2, hai
retrieval lặp không ghi messages và Q3 no-source. Grounded answers480.000 VNĐ/tín
chỉ và1.440.000 VNĐ cho3 tín chỉ qua EvidenceGate0.78; ba finals/citations còn
nguyên sau refresh, SSE khớp journal/DB. Citation drawer mở đúng trích đoạn/version,
nhưng synthetic URI chưa có nút mở bản gốc; knowledge API dành cho admin. Không
thay authorization để ép nghiệm thu. Chưa chứng minh root cause biến động latency.
Ledger hiện hành native75/76 calls,9.190/10.000 tokens,70/72 HTTP; static338/400,
24.782.675/33.554.432 bytes; provider còn2 generations/2 HTTP,91.113 input/17.861
output tokens và USD0,2447671 conservative reservation. Global3 conversations/27
messages; đúng conversation có12 USERs gồm9 historical failures,3 ASSISTANT finals.
Runtime owned đã dừng, preservation PASS. Chỉ một source synthetic, không full
corpus/production. [Analysis56](../../infra/local/rag-fixture/acceptance-20261012-56-analysis.json)
và chi tiết53–56 ở cuối giữ cả kết quả chưa đạt.

**Trạng thái lịch sử lượt52, trước chu kỳ mới: M1 not_verified / NO-GO.** Người dùng trực tiếp
cho phép tự tăng caps; không còn checkpoint xin tăng ngân sách lặp lại. Lượt44–47
đối chứng cold embedding, API/Next coexistence, HTTP adapter và nested job đều đạt
với cùng payload42-token; chúng chưa giải thích được timeout lịch sử. Lượt48 phát
hiện collector thread quá nặng; sửa cách đo bằng cached query-only handles đã
giảm overhead xuống dưới1ms ở lượt50/52, nhưng full-stack reranker vẫn timeout.
Hướng sửa thứ hai là bounded active intra-op spinning: đối chứng51 đạt, vector và
logit trùng hoàn toàn; trên browser/API thật lượt52 embedding50-token đạt303,14ms,
reranker209-token timeout734,49ms. Chưa có generation/gate/citation/final đạt.

Chu kỳ dừng sau đúng hai hướng sửa theo yêu cầu ban đầu. Đây là giới hạn chu kỳ,
không phải thiếu quyền chi phí DeepSeek hoặc caps. Chưa chứng minh root mechanism;
không tuyên bố một đối chứng cô lập là sửa triệt để. Ledger hiện hành **63/66 calls,
7645/7945 tokens,48/54 native HTTP**; static **250/280 requests,18.264.149/20.971.520
bytes**; provider còn6 generations/6 HTTP. Hội thoại giữ8 failed USERs,0 assistant
final mới; global3 conversations/20 messages. API/models graceful stop, Next owned
process được dừng; read-only post-stop preservation PASS. Chi tiết44–52 ở cuối.

Các đoạn31–43 sau đây mô tả trạng thái lịch sử, không thay ledger mới nhất trên.

Lượt36–38 thêm QPC/native resource diagnostics, chạy sáu phép đo cô lập và hai
lần nghiệm thu UI/API thật. Reranker cô lập185 tokens đạt454,95–509,67ms; embedding
cô lập26 tokens đạt163,69–185,07ms. Trên stack đầy đủ, lượt36 embedding26 tokens
timeout718,04ms; lượt38 embedding34 tokens đạt235,22ms nhưng reranker193 tokens
timeout715,75ms. Chưa chứng minh cơ chế gây timeout hoặc một hướng sửa latency.
Hai lượt giữ thêm hai USER thất bại; không có accepted assistant final/citation.
Lượt39 tái hiện cùng reranker193-token timeout721,42ms trong dual-model process
cô lập, sau embedding34-token đạt194,55ms native. Không có HTTP/API/frontend/
provider ở đối chứng này; chúng không phải điều kiện cần để lỗi đó xảy ra.
Độ dài/input, thứ tự Run và scheduling vẫn chưa được tách; chưa chọn bản sửa.
Lượt40–42 dùng gói50 calls/6390 tokens/10 messages/static190/provider+2 được
người dùng chấp thuận chính xác. Cùng payload193 tokens, fresh unprofiled control
timeout714,60ms; cố định vị trí caller/workers trên bốn cores đã cấp đạt488,76ms,
rồi614,32ms khi hai model resident, logit trùng hoàn toàn. Đây là lợi ích trong
đối chứng đã thử, chưa chứng minh một root cause duy nhất hoặc full-stack PASS.
Lượt43 có93 offline tests PASS, nhưng câu đầu trên browser/API thật dừng ở
embedding42-token native timeout712,11ms; không tới reranker/generation/gate.
Ledger mới nhất: **46/50 calls,5889/6390 tokens,30/40 HTTP**; provider còn6
generations/6 HTTP. Hội thoại giữ5 failed USERs, không có assistant final mới.
Chi phí DeepSeek được người dùng cho phép nhưng mọi reservation/cap và bằng
chứng thất bại vẫn được giữ. Không mở M2/M3; M1 vẫn **not_verified / NO-GO**.

Lượt31 đã xử lý workspace-only TEMP/idempotency và UTF-8, chạy startup/lifespan
thật cùng Next/model/API trong job CPU4/5GiB. User đã xác nhận concrete DeepSeek
payload; browser auth, POST tạo conversation, persisted USER message, hai
DeepSeek classifier/intent calls và query embedding/reranker thật đã chạy.
Reranker native656ms đạt native cap nhưng whole HTTP vượt deadline700ms;
retrieval/grounded FAQ chưa hoàn tất. UI nhận `DEPENDENCY_UNAVAILABLE` đúng,
không có assistant final/citation mới được lưu.

Bản sửa TLS context, idle CPU spinning và query encoder đã qua68 offline tests.
Lượt32 nhận direct human xác nhận toàn bộ một lần kiểm chứng/egress cụ thể,
chạy lại trên hội thoại hiện có. Retrieval hoàn tất922ms/812ms; native reranker
609ms/594ms đạt700ms. Hai grounded FAQ generations thật đã chạy nhưng
EvidenceGate từ chối; không có accepted grounded answer/citation. Ca thiếu
nguồn và refresh ba persisted abstained finals PASS. Lexical có thực thi nhưng
zero hits, chưa chứng minh positive lexical contribution. Exact gate reasons
không được giữ trong safe receipts; chưa kết luận nguyên nhân chi tiết.
Giữ nguyên thresholds, payload/resource/budget caps; không tự retry thêm.

Lượt33 đã sửa lexical natural-language matching và bổ sung claim/citation
diagnostics an toàn;94 targeted tests và5 additive-journal tests PASS. PostgreSQL
read-only chứng minh lexical positive hit. Browser thật gửi câu đầu trong đúng
một hội thoại mới; embedding đạt nhưng native reranker timeout700ms. Chưa tới
grounded generation/EvidenceGate; không có accepted final/citation. Dừng trước
câu2/3 vì ngân sách và message scope còn lại không đủ; xem exact deficit cuối báo cáo.

Lượt34 nhận direct human “ok” cho một lượt sửa/kiểm chứng tiếp, native caps32/
4045 và tối đa7 messages trong chính hội thoại mới. Dynamic CPU scheduling đã
áp nhưng real reranker vẫn timeout700ms ở câu đầu; chưa tới grounded generation/
gate. Native29/32 calls,3777/4045 tokens; không tiếp tục live retry. Dữ liệu
cũ giữ nguyên, API/native graceful shutdown; chi tiết và ledger mới ở cuối.

Phần dưới đây giữ nguyên trạng thái lịch sử từng lượt; các con số0 và blocker
Rust của lượt28 không mô tả trạng thái ONNX/index hiện tại. Chi tiết mới ở cuối báo cáo.

Lượt 28 đã khép tải compiler: probe ngoài sandbox PASS, full Rust1.99.0 archive
khớp published checksum, toolchain/source malware scans PASS. Candle CPU có
locked closure99 packages, source inventory83 packages, exact notice supplements
và finding-level maintenance disposition. Actual offline build chạy trong job
4 CPU/5 GiB; repair1 sửa host linker rồi bị **Windows Application Control chặn
unsigned `quote` build script, OS4551**, đối chiếu CodeIntegrity3033/3077.
Harness chưa build hoàn chỉnh hoặc chạy weights; compiled inventory chỉ partial.
**M1 chưa hoàn tất, not_verified / NO-GO**: real vectors0, active index0, browser
full-path chưa chạy. Đây là host code-integrity blocker, không phải thiếu quyền
engineering local/synthetic theo DEC-023. Không đổi hoặc bypass protection.
Actual PostgreSQL/container restart PASS ở lượt27 và toàn bộ historical evidence
được giữ nguyên; lượt28 không ghi DB, sửa guard hoặc gọi provider.

Lượt 26 thực hiện yêu cầu **“bỏ việc cần phê duyệt đi”**, **“chưa làm vội…”** và
**“tiếp”** bằng [DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md):
quyền tự thực thi công việc local/synthetic đã giao có hiệu lực toàn repository.
Đã sửa root AGENTS, governance, executor/orchestrator/escalation/prompt,
dependency allowlist, task/documentation entry points và change control. Các
task/package/role approval cũ được giải quyết bằng standing direct human authority,
không cần hỏi lại từng gói. Giữ nguyên historical receipts/task flags, dữ liệu và
requirements/technical verification. Lượt này chỉ sửa policy: runtime launch0,
index activation0, DB writes0, provider calls0. **M1 vẫn not_verified, NO-GO** do
các bằng chứng runtime/index/browser chưa có; thiếu approval không còn là blocker
cho engineering local/synthetic trong mục tiêu đã giao.

Lượt 25 đã thực thi lời phê duyệt **“Phê duyệt cả 3 exact scope”**: áp đúng guard
patch, commit đúng 1 synthetic owner/1 conversation/5 messages; ba independent
pools ghi đồng thời, duplicate-ID rejection và new-process READ ONLY readback
PASS, dữ liệu/schema cũ giữ nguyên. Áp optional `Message.final_result`; GET/SSE
dùng chung projection từ persisted fields, bốn final results đọc từ PostgreSQL
validate đúng schema. **806 tests PASS**, thêm **7 token-envelope tests PASS**;
cap 900 đã được adopt và kiểm bằng exact tokenizers, chưa launch runtime.
Runtime compiled SBOM/license/finding closure, active index và actual authenticated
browser full path vẫn **not_verified**. Restart proof chỉ ở mức new Python
process/connections; chưa kiểm PostgreSQL server restart/crash recovery. **M1
not_verified, NO-GO**. Các trạng thái chờ phê duyệt ba gói ở lượt 24 trở xuống là
lịch sử, đã được giải quyết trong lượt 25; không yêu cầu phê duyệt lại.

Lượt 24 hoàn tất engineering cho refresh history: URL chỉ lưu conversation ID;
GET có xác thực/no-store, tối đa 20 trang và deadline 10 giây; khôi phục nguyên
final ID/status/class/citation mapping khi metadata tồn tại, giữ legacy assistant
ở UNKNOWN, không công bố partial history hay tự gửi lại yêu cầu. **60/60 frontend
tests PASS**, typecheck/containment PASS; kiểm PostgreSQL READ ONLY xác nhận tất cả
fingerprints cũ và guard không đổi. Tests dùng mocked GET/SSE, chưa phải browser
full-path proof. Contract `Message.final_result`, committed fixture/guard và token
cap 128→900 vẫn chưa áp vì câu hỏi phê duyệt exact scope chưa được trả lời. Runtime
technical clearance/index activation chưa có bằng chứng mới đủ để đóng. **M1
not_verified, NO-GO**; không nghiệm thu M2/M3. Chi tiết và failures giữ ở mục lượt 24.

Lượt 23 chỉ thực hiện mục tiêu **M1**. Gói PostgreSQL outer-rollback được người
dùng phê duyệt đúng SHA đã thực thi: **8/8 checks PASS**, rollback toàn bộ, đọc
READ ONLY độc lập xác nhận preservation và guard không đổi. Đã nối bounded
history vào application/graph qua trust domain MEMORY và triển khai GET messages
theo contract hiện hành. Regression **794 passed, 2 warnings / 9,18s**. Ba gói
exact committed durability/guard, optional final-result read contract và token
envelope đã chuẩn bị, chưa áp/thực thi, đang chờ quyết định riêng. **M1 vẫn
`not_verified`, NO-GO**: chưa có committed durability/restart/concurrency,
runtime technical clearance, published active index hoặc actual authenticated
browser → full RAG proof. Không nghiệm thu M2/M3 trong lượt này. Các đoạn
“chưa chạy/chờ phê duyệt” của gói outer-rollback lượt 22 bên dưới là lịch sử.

Lượt 22 đã kiểm actual asyncpg/PostgreSQL trong READ ONLY: tám repository SQL
statements PREPARE thành công, ba empty reads đúng và virtual-row UUID/JSONB/
timestamp/citation codec round-trip pass; không chạy INSERT/UPDATE. Sửa deadline
repository để chờ pool và toàn bộ transaction dùng một budget, giữ cap cũ.
Regression **785 passed, 2 warnings / 9,10s**, có ba cumulative-deadline/cancel
rollback checks. Gói actual PostgreSQL transient-write test đã chuẩn bị và chốt
hash; chưa chạy vì scope ghi thử đang chờ xác nhận riêng. **M1/M2/M3 vẫn
`not_verified`, NO-GO**; READ ONLY codecs, SQLite rollback hoặc synthetic pilot
không thay actual committed persistence/full-RAG/release/pilot evidence.

Lượt 21 đã thực thi đúng gói schema/guard được người dùng trả lời **“Phê duyệt
đúng gói này”**: cài source 0014 đúng hash, thêm duy nhất hash này vào
`REVIEWED_ADDITIONS`, migrate owned synthetic fixture **0013 → 0014**, commit
thành công. READ ONLY độc lập xác nhận head 0014, ba trường metadata chat và
hai constraints; fingerprint toàn bộ dữ liệu/cột/index/constraints cũ khớp
trước/sau. Không có application row writes, publish/index activation hoặc
provider calls. Actual PostgreSQL conversation round-trip vẫn chưa kiểm;
repository chưa bật mặc định. **M1/M2/M3 `not_verified`, NO-GO**. Các đoạn chờ
phê duyệt schema lượt 20 bên dưới là lịch sử, đã được giải quyết ở lượt 21.

Lượt 20 tiếp tục theo yêu cầu xử lý toàn bộ phần thiếu và mô phỏng pilot khi
chưa có người thử thật. Đã bổ sung explicit PostgreSQL conversation repository,
atomic append và optional application injection. **782 tests passed, 2 warnings
/ 9,71s**, gồm sáu persistence checks bằng retained relational test transport;
actual PostgreSQL round-trip chưa chạy. Pilot mô phỏng thực thi **120 phiên,
240 message requests, concurrency 1/4/12**, expected scripted outcomes và
persisted/completed mapping khớp 240/240; six auth/ownership negatives trả
401/403. Đây là actual in-process API/SSE checks với scripted runner; modeled
feedback không phải CSAT thật. Schema 0014 và exact migration-guard patch đã
compile/review, chưa apply hoặc migrate. **M1/M2/M3 `not_verified`, NO-GO**;
không dùng mô phỏng thay actual RAG/provider/release quality/pilot evidence.

Lượt 19 đã áp dụng đúng patch opt-in `thinking.type=disabled` được người dùng
xác nhận, giới hạn `deepseek-flash` tại HTTPS `api.deepseek.com`. Regression
**778 passed, 2 warnings / 12,28s**. Một actual component re-probe trả đúng
**“OK”, finish stop, 22 input / 1 output / 0 reasoning tokens, 1.093 ms**,
trong deadline 5s. Corpus hiện tại qua Defender custom scan không có threat,
hash giữ nguyên; **15/15** source/locator/injection/prohibited-data checks và sáu
development gold hợp lệ, có technical review mới theo DEC-022. Corpus chưa
publish/index; embedding/reranker runtime chưa clearance. **M1/M2/M3 vẫn
`not_verified`, NO-GO**. Không còn chờ phê duyệt patch non-thinking hay quyền
DeepSeek đã cấp; các đoạn lượt 18 trở về trước là lịch sử.

Lượt 18 đã dùng quyền cụ thể người dùng vừa xác nhận: DeepSeek `/models` trả
**HTTP 200**, có `deepseek-flash` và `deepseek-v4-pro`. Một actual LLM component
probe qua adapter/egress hiện hành **failed**: cả 16 capped output tokens là
reasoning, finish `length`, chưa trả được “OK”. Đã sửa lỗi ghi nhận reasoning
usage bằng một dòng; regression **766 passed, 2 warnings / 12,61s**. Bản patch
opt-in non-thinking giới hạn exact endpoint/model đã chuẩn bị, **12/12 offline
candidate checks**, chưa áp dụng vì thay egress protection cần phê duyệt đúng
thay đổi. Còn **23 generation / 24 HTTP** trong ngân sách đã duyệt, không retry
hoặc tăng cap để che failure. **M1/M2/M3 vẫn `not_verified`, NO-GO**. Các lượt
bên dưới là lịch sử; chi tiết hiện tại ở cuối báo cáo.

Lượt 17 đã khép **kiểm chứng tokenizer BGE thật: 15/15 chunks, 128–219 tokens
kể cả special tokens, dưới hard maximum 900**, không truncate. Đã resolve, tải,
kiểm checksum/RECORD/license và quét malware cho 14 exact wheel packages trong
tooling riêng; application allowlist/lock/source không đổi. PyPI blocker của
lượt 16 đã được giải quyết sau chỉ dẫn mới của người dùng. Runtime model chưa
được launch; DeepSeek `/models` bị automatic approval review chặn trước khi đọc
khóa hoặc gọi mạng vì yêu cầu quyền cụ thể cho credential/destination.
**M1/M2/M3 vẫn `not_verified`, NO-GO**; token-bound proof không thay actual
index/provider/full-path, release quality hoặc load/pilot evidence. Chi tiết
lượt 17 và gói thực thi có binding mới ở cuối báo cáo. Các lượt sau là lịch sử.

Lượt 16 đã sửa giới hạn ký tự của turn buffer, giữ tên nguồn cho tài liệu không
có heading và sửa readiness: acquisition/query dùng cùng deadline, Redis chưa
bind báo disabled, database khởi tạo lỗi trả 503. Regression cuối **762 passed,
2 warnings / 11,62 giây**, deterministic offline; snapshot mới 15 tài liệu và
sáu gold development đã validate, nội dung/hash/offsets giữ nguyên. Tokenizer
BGE thực tế và runtime clearance chưa đủ; **M1/M2/M3 `not_verified`, NO-GO**.
Gói thực thi kế tiếp đã chuẩn bị; đọc metadata PyPI bị automatic approval review
chặn vì thiếu quyền mạng cụ thể. Không cài dependency hoặc gọi provider ở lượt này.
Chi tiết lượt 16 ở cuối báo cáo; các kết quả trước đó giữ làm lịch sử.

Lượt 15 khép regression được giao: **735 passed, 1 skipped / 736 cases,
14,82 giây**, một trong hai repair attempts bổ sung đã dùng. Chỉ cập nhật bốn
test được người dùng nêu; không đổi source behavior, public citation contract,
profile/threshold hoặc protection controls. Kiểm READ ONLY thực tế xác nhận
head 0013, bảo toàn dữ liệu/schema lịch sử và **7/7 negative eligibility probes**.
Catalog 15 chunks và sáu gold development đã validate; chưa có active index,
real reranker/full-path, release gold hoặc load/pilot. **M1/M2/M3 vẫn
`not_verified`; quyết định nghiệm thu no-go.** Chi tiết và failure mới được giữ
ở phần lượt 15 cuối báo cáo; các lượt bên dưới là lịch sử.

Lượt 14 đã thực thi sau câu trả lời trực tiếp `Cho phép cả hai mục trên.`:
đúng patch hash 0013 đã apply, migration **0012 → 0013 commit thành công** trên
owned fixture và đọc lại READ ONLY xác nhận preservation. Ba citation fields đã
nối reader → DTO → bootstrap; synthetic API case đã xuất `answered` kèm citation.
Regression mở rộng **731 passed, 4 failed, 1 skipped / 736 cases, 12,95s**;
còn assertion issuer trong SSE, test callback sync và hai kỳ vọng head 0012.
Một repair attempt bổ sung đã dùng, không tiếp tục sửa/retry. **M1–M3 vẫn
`not_verified`**; actual storage không thay full-provider path/eval/load evidence.

Lượt 13 đã nối API sang graph async và canonical service injection, đưa retrieved
evidence qua PromptComposer hiện hành, chặn copy-source fallback khi generation
lỗi và dùng evidence threshold 0.78 từ approved profile trong bootstrap. Focused
regression cuối **146 passed, 1 failed / 147 cases, 6,27s**; API composition còn
thiếu citation metadata, nên implementation tổng thể vẫn `failed` sau hai repair
attempts. Docker/fixture đã resume theo đúng ownership/image/mount; actual DB đọc
trong transaction READ ONLY xác nhận head 0012 và giữ nguyên seed. **M1–M3 vẫn
`not_verified`**, không coi model fakes hoặc SQL negative probes là full-path proof.

Lượt 12 triển khai adapter managed, writer embeddings, reader pgvector/lexical có
provenance và canonical fusion/rerank/context. Regression mở rộng ghi nhận
**614 passed, 2 failed, 1 skipped trong 10,99 giây**, source ổn định trong suite.
Hai snapshot corpus đã qua malware scan thực tế, checksum giữ nguyên. Sau xác nhận
`cho phep`, đã chạy thật Gemini Embedding 2: 48 inference attempts, 67 HTTP calls,
15/15 document vectors mỗi chiều và 6/6 development queries đúng top-1 ở cả
768/1536. Tokenizer đúng model kiểm 15/15 chunks: 155–263 tokens, dưới bound 900.
Một inference timeout và hai cold-budget failures được giữ trong denominator.
Chưa có DB call hoặc index activation; **M1/M2/M3 vẫn `not_verified`**.
Phần dưới giữ kết quả lượt 10–11 theo đúng scope lịch sử; không dùng 555/555 lịch sử
để che hai failure mới được đưa vào scope kiểm chứng rộng hơn.

Đã ghi nhận xác nhận review và trách nhiệm chính của người dùng, bỏ hai prerequisite
chữ ký/reviewer độc lập. Kiểm chứng mới trên nguồn
hiện tại đạt **555/555 backend tests trong 17,64 giây**, TypeScript,
**47/47 chat tests và 21/21 browser/SSE cases**. HTTP adapters TEI và sửa locator
parser/chunker từ lượt 10 được giữ nguyên và kiểm lại. Migration storage mới được
kiểm bằng DDL offline; một probe managed embedding dùng kết nối warm đạt 531 ms.
**M1, M2, M3 vẫn `not_verified`**: runtime chưa clearance, corpus chưa được duyệt
publish và chưa có actual full-path/evaluation/load/pilot measurements.

## Implementation và bằng chứng lượt 10

| Kết quả | Bằng chứng và giới hạn |
|---|---|
| Baseline 1.068 file | [Baseline](../../infra/local/rag-fixture/acceptance-20261005-10-baseline.json): HEAD, dirty state, source/config/test hashes và runtime executable hash. `frontend/`, secrets và production nằm ngoài scope. |
| Dependency → catalog → OpenAPI đạt | [Preflight](../../infra/local/rag-fixture/acceptance-20261005-10-preflight.json), ba commands exit 0. |
| IPC dưới execution permission phù hợp đạt | [Sandbox](../../infra/local/rag-fixture/acceptance-20261005-10-ipc-sandbox.json): hai probes timeout 7 giây; [escalated](../../infra/local/rag-fixture/acceptance-20261005-10-ipc-escalated.json): cả hai exit 0, socketpair và asyncio pass, external/DNS deny pass. Guard hashes giống nhau. Chứng minh khác biệt execution permission, không quy kết chính xác cơ chế OS. |
| Regression trước implementation đạt 498 tests | [Receipt](../../infra/local/rag-fixture/acceptance-20261005-10-tests.json), 16,56 giây, source drift rỗng; supersedes lượt 09 bị timeout. |
| HTTP adapters TEI đã triển khai | [tei.py](../../services/api/src/campus247/infrastructure/retrieval/tei.py): client factory được cấp rõ; kiểm `/info` đúng model/revision/type trước gửi query/content; không truncate; validate L2/dimension/count/index/score; deadline tổng và cleanup; không retry/redirect. Không tự mở endpoint, kích hoạt model hoặc cấp quyền. Sync embedding yêu cầu worker context. [Regression](../../infra/local/rag-fixture/acceptance-20261005-10-tei-tests.json): 531 passed, 14,89 giây; HTTP MockTransport, chưa live inference. |
| Locator parser/chunker đã sửa | [parse.py](../../services/worker/src/campus247_worker/ingestion/parse.py), [chunk.py](../../services/worker/src/campus247_worker/ingestion/chunk.py): bỏ heading khỏi locator nội dung, giữ paragraph boundaries và offset thật của từng overlapping window; reject locator không khớp nguồn. [Reproduction trước sửa](../../infra/local/rag-fixture/acceptance-20261005-10-locator-before.json); [regression cuối](../../infra/local/rag-fixture/acceptance-20261005-10-locator-tests.json): 552 passed, 10,80 giây, product/test hashes ổn định trong suite. |
| Corpus candidate chuẩn bị được | [Preview receipt](../../infra/local/rag-fixture/acceptance-20261005-10-corpus-preview.json): 15 nguồn/15 chunks, 15/15 exact locator round-trips; existing injection/secret/email/phone/IP/student-ID rules không phát hiện match; không active-content marker. Không phải full malware hoặc independent review. |
| Runtime supporting evidence giữ integrity | [Binding](../../infra/local/rag-fixture/acceptance-20261005-10-runtime-binding.json): rehash đúng supporting và license evidence cho image `sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`, giữ đủ 202 findings; gate vẫn mở. |

Corpus parsed candidate nằm ở
`downloads/campus247-corpus-20261005-10/parsed-candidate.json`, ignored và quarantined,
SHA256 `e81bb6ed945d6a04e835383070b0ca83ece2b9b9f32968493e112aad8ce90eb8`.
Giữ source snapshot SHA256
`5111261c672dcb4361d5d0a6db5bb00c694c2821fc32b68f6744a39ab43a9ab4`.
Character chunking ở đây là preview của implementation hiện có; giới hạn 900 tokens
bằng tokenizer đúng model chưa kiểm chứng. Không ghi preview là published/indexed.
Parser/chunker đổi output phải regenerate candidate/index có version bindings khi
được duyệt; lượt này không thay index hoặc active pointer.

Trong lượt 10, `apps/web/src/app/chat/page.tsx` và `apps/web/tsconfig.tsbuildinfo` đổi đồng thời so
với baseline. Full-snapshot preflight của TEI đã từ chối trước tests; failure được
giữ ở [receipt](../../infra/local/rag-fixture/acceptance-20261005-10-tei-preflight-refused.json).
Sau đó chỉ chạy scope backend độc lập. Frontend inventory preflight được ngắt khi
phát hiện drift; [interrupted receipt](../../infra/local/rag-fixture/acceptance-20261005-10-frontend-interrupted.json)
ghi `not_verified`, không có fresh browser hoặc frontend test outcomes. Không sửa,
phục hồi hoặc dùng browser 21/21 lịch sử chứng nhận frontend mới.

## Kiểm chứng mới và review ngày 2026-10-06

| Kết quả | Bằng chứng và giới hạn |
|---|---|
| Quyết định của người dùng đã áp dụng | [DEC-022](../00-governance/RAG_ACCEPTANCE_AUTHORITY_DECISION_20261006.md), [authority receipt](../../infra/local/rag-fixture/acceptance-20261006-11-owner-authority.json), [phiếu hiện hành](../../infra/local/rag-fixture/acceptance-20261006-11-owner-review-form.json), [validation](../../infra/local/rag-fixture/acceptance-20261006-11-owner-policy-validation.json): 15 nguồn đã ghi owner review; 202 findings nối đúng triage và ghi `under_investigation`. **Không yêu cầu chữ ký hoặc reviewer độc lập** trong synthetic M1–M3 scope. Provenance chưa ký khớp image subject và source commit trong image config; không ghi nó là cryptographically verified. Phiếu trước quyết định mới giữ nguyên như lịch sử. |
| Baseline/preflight hiện tại đạt | [Baseline](../../infra/local/rag-fixture/acceptance-20261006-11-baseline.json), [preflight](../../infra/local/rag-fixture/acceptance-20261006-11-preflight.json): dependency/catalog/OpenAPI exit 0; source drift rỗng. |
| Backend/ingestion hiện tại đạt | [IPC](../../infra/local/rag-fixture/acceptance-20261006-11-ipc-escalated.json), [regression](../../infra/local/rag-fixture/acceptance-20261006-11-locator-tests.json): 552 passed, 17,63 giây; source/test hashes ổn định, guard giữ nguyên, không gọi DB/provider/model. |
| Frontend tools và nguồn ổn định | [Inventory](../../infra/local/rag-fixture/acceptance-20261006-11-frontend-inventory.json): 23.334 tệp khớp checksum, không mismatch/drift, không install. Probe đầu bị WinError 5 khi đọc dependency trong sandbox; phép đọc qua escalation hợp lệ sau đó đạt. |
| TypeScript/chat hiện tại đạt | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-11-frontend.json): containment/typecheck/tests exit 0; ba tệp chat có tổng 47 tests đạt, không pending hoặc unhandled error. |
| Browser/SSE hiện tại đạt | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-11-browser.json): 21/21 cases, không page error/uncaught error, source drift rỗng. Chromium sandbox và guard nguyên vẹn; synthetic SSE, cô lập Next startup; chưa full Next production build hoặc actual authenticated RAG. |
| Machine-readable runtime inventory đã tạo | [SPDX candidate](../../infra/local/rag-fixture/acceptance-20261006-11-runtime.partial.spdx.json), [validation/binding](../../infra/local/rag-fixture/acceptance-20261006-11-runtime-inventory.json): 117 Debian packages + image package, 752 layer-qualified native entries; checksum manifest/config/13 layers khớp. Kiểm định bằng [schema SPDX 2.3 chính thức](https://raw.githubusercontent.com/spdx/spdx-spec/v2.3/schemas/spdx-schema.json), lưu schema và origin hash. Đây là **partial supporting inventory**; compiled Rust features/static-link và license coverage còn thiếu cho local candidate. Chữ ký không còn prerequisite theo DEC-022. |
| Storage tương thích đã triển khai ở source | [Migration 0013](../../services/api/migrations/versions/0013_profile_embedding_storage.py), [preflight](../../infra/local/rag-fixture/acceptance-20261006-11-storage-preflight.json), [tests](../../infra/local/rag-fixture/acceptance-20261006-11-storage-tests.json): thêm nullable `embedding_rag_v1 vector(1024)` và HNSW cosine index, all-or-none model/dimension/timestamp, exact revision và L2 checks. Giữ `embedding vector(1536)` và migration 0009 nguyên vẹn. Regression mới 555 passed, 17,64 giây, gồm ba tests DDL offline; chưa apply DB, backfill, reader/writer wiring hoặc active index. |
| Cấu hình thay thế được kiểm chứng thực tế | [Availability](../../infra/local/rag-fixture/acceptance-20261006-11-configuration-candidates.json), [metadata](../../infra/local/rag-fixture/acceptance-20261006-11-managed-embedding-metadata.json): Google provider đã cấu hình, `gemini-embedding-2` trả metadata 200/version 2. [Cold](../../infra/local/rag-fixture/acceptance-20261006-11-managed-embedding-probe.json) timeout 700 ms; [warm](../../infra/local/rag-fixture/acceptance-20261006-11-managed-embedding-warm.json) 200, 1536 chiều, norm `1.000000337`, 531 ms. Tổng hai inference calls của câu cố định 51 bytes, không corpus/PII/retry/fallback. **Không gộp thành 2/2 success** và không chọn quality winner từ connectivity; cần actual corpus/index/rerank/evaluation trên cùng dữ liệu. [Tài liệu provider](https://ai.google.dev/gemini-api/docs/embeddings) xác nhận output dimensionality tùy chọn và các model có embedding spaces khác nhau. |

## Ma trận nghiệm thu hiện tại

| Tiêu chí | Trạng thái | Điều kiện đóng phần còn thiếu |
|---|---|---|
| AC-01 phiên bản | `passed` baseline/scoped source stability; `not_verified` full tuple | Frontend/backend nguồn hiện tại ổn định; cần actual corpus/index/profile/prompt/model tuple. |
| AC-02 preflight | `passed` | Scope dependency/catalog/OpenAPI, không suy ra release. |
| AC-03 offline regression | `passed` | Lượt 11 cuối: 555/555 backend + 47/47 chat; không suy ra chất lượng model. |
| AC-04 browser hiện tại | `passed` client/SSE scope | Fresh 21/21; Next startup cô lập và synthetic transport, không chứng nhận actual RAG. |
| AC-05 provider/model release binding | `not_verified` | Smoke lịch sử chỉ chứng minh connectivity; cần immutable resolved model/pricing binding. |
| AC-06 runtime | `not_verified` full selected path | Chữ ký/review độc lập đã bỏ; local candidate còn compiled/static/license/finding coverage; managed candidate có metadata và warm embedding proof, chưa toàn pipeline. |
| AC-07 corpus | `not_verified`; owner review/integrity/locator preparation đạt | Full malware scan, tokenizer bound, actual publish/index validation. Không đòi reviewer độc lập. |
| AC-08 trusted context/authorization | `not_verified` toàn trình | Verified institution/issuer/resolver/scope bindings; actual zero-leakage cases. |
| AC-09 M1 real path | `not_verified` | Storage 1024 tương thích, approved runtime/corpus/context và authenticated browser/API/DB/index/embedding/hybrid/reranker/LLM/gate/citations cùng run. |
| AC-10 M1 dialogue/recovery | `not_verified` | Actual history/persistence, correction/cancellation/refresh/provider faults và citation reauthorization. |
| AC-11 M2 | `not_verified` | Reviewed corpus/gold/splits và evaluation authority; actual runs/repeats/subgroups/variance. |
| AC-12 M3 | `not_verified` | Actual load/stage latency/cache/cost/memory/pool/quota/resilience measurements. |
| AC-13 pilot/release | `not_verified` | Actual pilot/capacity/recovery và release decision theo trách nhiệm owner; không yêu cầu chữ ký. |

Latency/cost/quality của actual RAG, confidence/variance và pilot outcomes hiện
**unavailable**. Thời gian chạy pytest không phải stage latency hay TP-RAG benchmark.
Không giảm thresholds, thay gold, tự ký review hoặc dùng fake làm actual outcomes.

## Việc kỹ thuật còn lại để bắt đầu actual acceptance

Executor được ủy quyền technical review và chọn phương án tốt hơn. Local TEI
candidate còn cần compiled Rust/native coverage, MKL `2024.0.0-49656` notices/
redist/static-link compliance và applicability/remediation cho **192 Debian +
10 Cargo** findings. Partial inventory chưa chứng minh những phần đó.
Managed Gemini candidate tránh phải vận hành image local cho embedding và đã có
một warm capability proof; tiếp tục cần adapter/lifecycle, service/profile/version
binding, reranker phù hợp và cùng-suite quality/latency/cost comparison trước
promotion. Model mới phải re-embed một index version mới, kể cả cùng 1536 chiều;
không tái sử dụng hoặc gắn nhãn khác cho vectors cũ.

Corpus owner review đã ghi. Cần hoàn tất full malware/tokenizer checks và actual
publish/index validation; nối trusted institution/issuer/resolver/actor scope trong
synthetic fixture, source-version/locator và canonical retrieval/rerank/history/
persistence path. Migration 0013 mới là source/DDL preparation, chưa DB apply hoặc
reader/writer activation. M2 cần gold/splits/repeats/subgroups và actual model runs;
M3 cần pricing, measured load/cost/recovery/pilot. Không tạo các measurements đó
từ số tests pass hoặc xác nhận review.

Đề nghị release hiện tại: **no-go cho nghiệm thu/phát hành M1–M3** vì các đầu vào
trên chưa đủ. Đây là kết luận kỹ thuật của executor theo trách nhiệm owner trong
DEC-022. Fresh frontend đã đạt ở scope trên; sau khi đóng selected runtime/corpus/context
và storage compatibility, thứ tự chạy là actual M1 → M2 → M3 trên cùng tuple.
Không yêu cầu lại engineering/budget delegation đã được cấp.

Lượt 10 không đọc `.env` hoặc gọi provider. Lượt 11 đọc `.env` riêng theo ủy quyền,
chỉ ghi availability booleans và gọi managed provider cho hai câu mô phỏng như trên;
không lưu secret hoặc sửa `.env`. Không launch model local, publish corpus,
ghi DB, install dependencies, commit/push/deploy hoặc xóa dữ liệu.
[Final audit](../../infra/local/rag-fixture/acceptance-20261005-10-final.json) lưu
exact scoped diff, hashes, git status và external drift; evidence cũ giữ nguyên.
Lượt 11 chỉ đọc thêm schema SPDX công khai, không kế thừa proxy/credential và
không redirect. [Final audit mới](../../infra/local/rag-fixture/acceptance-20261006-11-final.json)
đối chiếu receipts, hashes, source stability và dirty state; product source mới chỉ
là migration 0013, tests mới ba cases DDL. Governance thêm quyết định trực tiếp của
người dùng, register/manifest entry và physical mapping note; giữ mọi dirty state
có sẵn và toàn bộ evidence lịch sử. Frontend nguồn giữ nguyên trong lượt 11.

## Triển khai và kiểm chứng lượt 12 — 2026-10-06

| Kết quả | Bằng chứng và giới hạn |
|---|---|
| Baseline mới: 1.178 files | [Baseline](../../infra/local/rag-fixture/acceptance-20261006-12-baseline.json): HEAD, dirty/deleted/untracked state và exact source/config/test hashes. Không đọc `.env`, default DSN hoặc production. |
| Dependency/catalog/OpenAPI | [Preflight](../../infra/local/rag-fixture/acceptance-20261006-12-preflight.json): cả ba command exit 0; source drift rỗng trước implementation. |
| Managed adapter đã triển khai | [gemini.py](../../services/api/src/campus247/infrastructure/retrieval/gemini.py): client factory được cấp rõ; một session/loop, reusable connection, serialization có deadline, startup riêng được khai báo, cancellation/cleanup, no retry/redirect/truncation, numeric/dimension/L2/output-byte validation, calls/input-byte caps tính cả thất bại. Query dùng `task: search result`, documents gửi từng request theo `title: none` để tránh aggregation nhiều tài liệu. Chỉ nhận `gemini-embedding-2`, chiều 768/1536/3072 và public `provider-version:N`. Đây **không phải immutable weights/artifact binding**, không được đưa vào manifest BGE hoặc tự promotion production profile. Sync port chỉ dùng worker context. Tests dùng HTTP MockTransport, chưa gọi provider thật trong lượt này. [Tài liệu Google](https://ai.google.dev/gemini-api/docs/embeddings), [API config](https://ai.google.dev/api/embeddings) được đọc ngày 2026-10-06. |
| Embedding persistence đã triển khai | [index.py](../../services/worker/src/campus247_worker/ingestion/index.py): `persist_profile_chunks` INSERT vector 1024 + exact model/revision/dimension/timestamp, checksum và section locator; cần caller-owned transaction, DRAFT document/BUILDING manifest, row locks và storage norm tolerance `1e-4`. Không ghi legacy 1536, không UPDATE chunks hoặc commit partial index. `persist_chunks` reject unbound embedding thay vì âm thầm bỏ vector. Chưa chạy PostgreSQL thật. |
| Vector reader và entrypoint | [postgres_vector.py](../../services/api/src/campus247/infrastructure/retrieval/postgres_vector.py), [vector.py](../../services/api/src/campus247/infrastructure/retrieval/vector.py): chỉ delegate khi được cấp verified backend; explicit pool + embedding callback + immutable manifest/pointer/profile + independent index/corpus/artifact expectations + issuer resolver. SQL dùng `embedding_rag_v1`, exact model/dimension và active pointer; tất cả eligibility predicates nằm trước ORDER BY/LIMIT. Kiểm checksum/locator và giữ source/version/title/issuer/URI/pages/effective dates/simulation metadata. Deadline gồm embedding, pool wait, query và validation; cancellation trả pool lease. Chưa nối bootstrap mặc định hoặc chứng minh actual DB path. |
| Lexical/canonical pipeline | [postgres_lexical.py](../../services/api/src/campus247/infrastructure/retrieval/postgres_lexical.py), [canonical.py](../../services/api/src/campus247/application/retrieval/canonical.py): lexical dùng cùng predicate và active index tuple, giữ provenance. Canonical gọi hai branches với cùng trusted context, cancel/join sibling khi lỗi, RRF/dedupe và reject content/provenance drift. Gọi RerankerPort với profile exact, yêu cầu đủ candidate IDs/counts/scores, giữ nguồn gốc; context kiểm 900-token chunk hard bound, 6.000-token context budget và ≤3 chunks/section bằng token counter có model/revision binding. Tests dùng model/tokenizer fakes được ghi rõ; không coi chúng là reranker/tokenizer thật. |
| Regression mở rộng | [Lần đầu](../../infra/local/rag-fixture/acceptance-20261006-12-regression.json): 579 passed, 2 failed, 1 skipped / 11,52s. [Writer/reader](../../infra/local/rag-fixture/acceptance-20261006-12-storage-regression.json): 600 passed, 2 failed, 1 skipped / 11,79s. [Cuối](../../infra/local/rag-fixture/acceptance-20261006-12-canonical-regression.json): **614/617 passed, 2 failed, 1 skipped / 10,99s**, command exit 1; source/test hashes ổn định. Tests mới đạt; broader suite vẫn **failed**, không bỏ failure để báo passed. |
| Malware scan thực tế | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-12-corpus-malware-scan.json): Defender Antivirus/service enabled, signatures `1.459.568.0`, cập nhật `2026-10-05T10:27:49Z`. Custom scan report-only trên đúng `corpus.json` và `parsed-candidate.json`: hai command exit 0, no threats; target checksums trước/sau khớp. Không remediation/quarantine, thay settings, signature update hoặc scan toàn thư mục. [Tùy chọn scan Microsoft](https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus). Đây chỉ là scan hai JSON snapshots; không clearance model/runtime binaries. Helper scan có một lỗi ghi receipt do dùng workspace-only hash helper cho executable ngoài workspace, đã sửa thành read-only executable hash và chạy lại một lần; không suy ra kết quả từ lần lỗi. |
| Corpus/provider inputs đã chuẩn bị | [Inputs](../../infra/local/rag-fixture/acceptance-20261006-12-candidate-inputs.json): 15/15 owner-reviewed sources, exact content/checksum/locator, injection scan và EgressPolicy hiện hành đạt. Sáu câu hỏi development và expected source/evidence khóa trước inference. Không phải release gold/holdout và không thay gold cũ. Corpus vẫn quarantined; tokenizer thật/publish/index validation chưa đạt. |
| Managed comparison bị chặn ở lần chốt trước xác nhận | [Receipt lịch sử](../../infra/local/rag-fixture/acceptance-20261006-12-managed-approval-block.json), [runner](../../infra/local/rag-fixture/acceptance_managed_compare_20261006_12.py): Google Gemini Embedding 2, cùng 15 sources/sáu câu hỏi cho 768 và 1536, tối đa 48 inference/80 HTTP calls, 100.000 input bytes, concurrency 1, 700ms/operation, 90s evaluation, $0.02 reservation. Automatic approval review từ chối vì chưa công nhận specific human authorization. Tại snapshot này chưa có reply: **0 calls**. Xác nhận trực tiếp `cho phep` và execution sau đó được ghi riêng bên dưới; giữ receipt chặn nguyên vẹn. |

### Failure và blocker kỹ thuật cụ thể

`tests/integration/test_retrieval_scope_migration.py::test_reviewed_ancestry_and_forward_only_recovery`
gọi fixture guard nguyên vẹn và bị từ chối: `migration source changed or unreviewed;
stop before DB mutation`. `fixture.py` đã review đến `0012`, chưa có hash `0013`.
[Phép gọi guard riêng](../../infra/local/rag-fixture/acceptance-20261006-12-fixture-guard.json)
xác nhận cùng lý do trước connection/mutation. Chính sách Global Agent Safety
Policy do người dùng cung cấp cấm sửa/bypass protection controls; executor không
thay REVIEWED map hoặc dùng executor SQL khác để vượt guard. Cần một đường review/
authorization phù hợp cho exact `0013` trước DB apply; chưa có schema/backfill/
index activation evidence. Không cần chữ ký hoặc reviewer độc lập.

`tests/integration/test_migration_0009.py::test_historical_0009_0010_ancestry_is_preserved`
kỳ vọng descendants chỉ `0012→0011→0010`; source hiện có thêm `0013→0012`.
Giữ nguyên expected result và failure, không sửa để làm suite pass. Một live case
thiếu fixture DSN bị skip, không tính skip là DB verification. Không retry hai
failure bằng đổi run ID; các regression sau được chạy do implementation độc lập
mới, cùng hai failure được giữ trong mọi denominator.

Local candidate vẫn còn compiled/static SBOM coverage, MKL obligations và 202
finding dispositions chưa đóng; không launch runtime đó. Managed candidate cần
actual comparison, provider-version/storage/index profile mới và real reranker.
Storage hiện có chỉ qualified current BGE/1024 mapping; Gemini cùng 1536 chiều với
legacy column không được reuse/relabel legacy vectors.

Bootstrap hiện tại vẫn chưa nhận canonical service và explicit owned runtime.
Graph còn sync/async loop boundaries, retrieved context trong generation system
instructions và copy-source fallback cần sửa/kiểm chứng; citation reauthorization,
material-claim support, durable per-message citations/history/correction và real
provider gateway/budget path chưa có end-to-end evidence. SQL schema hiện tại
chưa lưu canonical character locators hoặc đầy đủ message finish/citation payload.
Các phần này chưa được báo completed chỉ vì các component mới đạt unit tests.

### Trạng thái nghiệm thu sau lượt 12

| Mốc/gate | Trạng thái đúng scope |
|---|---|
| AC-02 preflight | `passed`; kiểm lại sau implementation trong final audit. |
| AC-03 regression rộng hơn | `failed`: 614 passed / 617 cases, 2 failed, 1 skipped. Scope mới khác 555/555 lịch sử. |
| AC-07 corpus | Malware hai snapshots, egress/injection/checksum/locators và real tokenizer cho 15/15 prepared chunks `passed`; publish/index `not_verified`. |
| M1 | `not_verified`: chưa authenticated browser→API→owned PostgreSQL/index→real embedding/reranker/LLM→gate/citations→UI trên cùng tuple. |
| M2 | `not_verified`: chưa full gold/splits, actual runs/ablation/negatives/multi-turn/repeats/subgroups/confidence. Development inputs không thay release evaluation. |
| M3 | `not_verified`: chưa actual stage/load/cold-warm/cost/memory/pools/quota/resilience/recovery/pilot measurements. |

Giá Google Gemini Embedding 2 text standard được xác minh từ [nguồn chính thức](https://ai.google.dev/gemini-api/docs/pricing)
ngày 2026-10-06: **USD 0,20/1 triệu input tokens**; batch USD 0,10/1 triệu.
$0.02 trong runner là reservation, không phải actual billed cost. Chưa xác định
account tier/billing hoặc token usage; không gán cost bằng 0 từ free-tier label.
Tại snapshot trước xác nhận chưa có cold/warm latency mới; số đo sau xác nhận
được ghi bên dưới. Cold timeout 700ms của lượt 11 vẫn giữ nguyên.

[Final audit lượt 12](../../infra/local/rag-fixture/acceptance-20261006-12-final.json)
ghi commands/cwd/exit codes/deadlines, exact current hashes/diffs/status và xác minh
guard hashes không đổi. Virtual reversal của đúng patch mới đối chiếu baseline
để chứng minh nội dung có sẵn của `vector.py` và `index.py` được giữ nguyên.
Không có unrelated source drift; không sửa frontend, requirements/contracts,
dependencies/pins, permissions/backups hoặc guard. Ruff executable chưa có nên
lint `not_verified`; không install. AST/import checks và regression đã chạy.
Một receipt chuẩn bị mới ban đầu bị gắn label `11` do historical helper import
đặt lại biến chung; giữ nguyên file đó và tạo đúng `12-candidate-inputs.json`,
không dùng nhãn lỗi làm evidence lịch sử hay viết lại artifact.
Trước xác nhận không có provider call. Toàn lượt không commit, push, deploy,
production access, DB call, publish/activation, xóa hoặc ghi đè evidence.
No-go cho nghiệm thu M1–M3 vẫn áp dụng.

### Execution sau xác nhận trực tiếp `cho phep`

[Baseline được cho phép](../../infra/local/rag-fixture/acceptance-20261006-12-managed-authorized-baseline.json)
ghi exact destination/payload/caps và đối chiếu toàn bộ source/tests/receipts với
final snapshot trước gọi provider. `.env` chỉ đọc riêng trong memory, không log
key/header/raw error body; bytes trước/sau khớp. Không thay egress hoặc các guards.

[Comparison](../../infra/local/rag-fixture/acceptance-20261006-12-managed-comparison.json)
và [execution receipt](../../infra/local/rag-fixture/acceptance-20261006-12-managed-execution.json)
ghi command exit 0: 46 inference calls thành công, mỗi chiều 15 document calls,
6 development queries, một cold query và một repeat query. Vectors được tạo mới
vào [candidate artifact](../../infra/local/rag-fixture/acceptance-20261006-12-managed-candidate-vectors.json),
giữ chunk/checksum/profile riêng, inactive; không chuyển đổi hoặc relabel vectors cũ.

| Số đo thực tế | 768 | 1536 |
|---|---:|---:|
| Document vectors hợp lệ | 15/15 | 15/15 |
| Development top-1 / recall@10 | 6/6 / 6/6 | 6/6 / 6/6 |
| Warm query median, gồm repeat; n=7 | 454 ms | 437 ms |
| Warm query min–max; n=7 | 407–500 ms | 391–438 ms |
| Cold đầu tiên, gồm client + metadata + embedding | 1.063 ms; vượt 700 ms | 625 ms; đạt |
| Cold session bổ sung, đảo thứ tự; total deadline 700 ms | 532 ms; đạt | 703 ms; TimeoutError |
| Cold-budget success trên cả hai điều kiện | 1/2 | 1/2 |

[Cold-repeat receipt](../../infra/local/rag-fixture/acceptance-20261006-12-managed-cold-repeat.json)
giữ command exit 1 và timeout thực tế. Hai samples bổ sung là điều kiện cold mới
được khai báo, không retry request lỗi. Lần đầu deadline áp riêng startup/embedding
và đo tổng; lần bổ sung áp deadline tổng 700 ms, bao gồm metadata và cleanup.
Không giấu startup hoặc coi 23/23 operation success ban đầu là cold-path pass.
Tổng inference là **47/48 trả vector**, tính cả timeout; không có thêm provider calls
sau khi chạm cap. API deadline/cancellation có overhead quan sát 3 ms ở timeout.

Sáu expected sources/evidence đã khóa trước inference. Đây là development probe
trên corpus 15 nguồn, chạy tuần tự 768 trước 1536; không có holdout, ablation,
negative/security/multi-turn coverage hoặc đủ repeats để kết luận chất lượng.
6/6 có Wilson 95% interval khoảng **61,0%–100%** dưới giả định samples độc lập;
không suy diễn thành release confidence vì samples curated, cùng corpus và nhỏ.
Raw repeat dot product hơi trên 1 do sai số floating point/L2 tolerance; không
gọi đây là cosine chính xác hoặc clamp artifact để tạo kết quả đẹp.

[Tokenizer corpus](../../infra/local/rag-fixture/acceptance-20261006-12-managed-corpus-tokenizer.json)
và [execution](../../infra/local/rag-fixture/acceptance-20261006-12-managed-tokenizer-execution.json)
ghi exit 0: reuse count 218 của chunk đầu với exact receipt hash, thêm 14 countTokens
requests cho cùng documents; **15/15 đạt, 155–263 tokens**, gồm title prefix như
embedding input. Không truncate/rechunk. Đây là bound đúng model
`gemini-embedding-2/provider-version:2` cho corpus này, không phải tokenizer BGE
hoặc proof cho corpora khác. Publication và actual index validation vẫn chưa chạy.

Aggregate cuối: **48 inference attempts, 67 HTTP calls, 45.002 request bytes**;
concurrency 1, từng operation 700 ms, no retry/fallback/redirect. Nằm trong cap
48/80/100.000; reservation **$0.02**, actual billed cost/token usage **unavailable**.
countTokens kiểm input length, không thay billable usage receipt. Profile binding
vẫn là public Models version 2, không giả immutable weight SHA.

**Candidate decision: chưa promotion hoặc tuyên bố winner.** Cả hai chiều cùng
đạt six-case quality nhưng cold mới đều 1/2; chênh 17 ms warm median bị ảnh hưởng
thứ tự chạy và chưa có variance evidence. 768 cần nửa số vector elements so với
1536; đây là tính toán storage shape, chưa phải đo actual DB/RSS/cost. Local
candidate chưa qua compiled/static/license/finding gates nên chưa có comparison
cùng suite. Không chọn 1536 chỉ vì chiều lớn hơn hoặc reuse legacy 1536 column.

[Post-run audit](../../infra/local/rag-fixture/acceptance-20261006-12-managed-postrun.json)
kiểm fresh vector dimensions/norms/checksums/locators/counts, source/guard và
historical receipt hashes, exact scoped diff/status. M1 vẫn chặn ở fixture guard
0013, selected storage/profile + real reranker + bootstrap/full-path; M2 thiếu
release suite/splits và tuple đó; M3 chưa có load/recovery/pilot hoặc billable usage.
Các tests/provider probes/token counts vừa đạt không thay các gate này.

## Triển khai và kiểm chứng lượt 13 — tiếp tục theo yêu cầu nghiệm thu

[Baseline](../../infra/local/rag-fixture/acceptance-20261006-13-baseline.json) mới
ghi HEAD/status/hashes trước mọi thay đổi; [preflight](../../infra/local/rag-fixture/acceptance-20261006-13-preflight.json)
dependency/catalog/OpenAPI exit 0. Không tạo subagent/chat, không xóa/reset/clean,
install, commit/push/deploy, đổi requirements/contracts/pins hoặc guard.

| Thay đổi / phép chạy | Kết quả đúng scope |
|---|---|
| API loop và graph | [async_io.py](../../services/api/src/campus247/agent/nodes/async_io.py) await classifier/intent/retrieval/generation trên cùng loop, có request deadlines và propagation cancellation; [graph.py](../../services/api/src/campus247/agent/graph.py) có `arun`/`ainvoke`, outer RunBudget latency limit và per-invocation trusted context. API không dùng synchronous loop bridge. Legacy sync worker/fixtures vẫn giữ riêng; chưa chứng minh full token/cost RunBudget accounting. |
| Trust domain / generation fault | [definitions.py](../../services/api/src/campus247/agent/nodes/definitions.py) dùng PromptComposer hiện hành: retrieved evidence ở user data block, không ở system instructions; parse classifier/intent dùng chung. Generation failed/exception/malformed response trong async path trả SAFE_FAILURE; không chép nguồn làm model answer. Synchronous no-provider source-copy fixture helper giữ nguyên cho tests lịch sử, không được async API gọi. Workflow exception dùng constant error, bỏ raw exception/traceback khỏi state. |
| Composition root | [app.py](../../services/api/src/campus247/bootstrap/app.py) nhận explicit typed CanonicalRetrievalService và gateway; await actual canonical service interface, giữ source/checksum/issuer/URI/page/effective-date/simulation metadata và profile/index tuple. Trusted context factory giữ nguyên, không tự cấp grants. Bootstrap áp threshold **0.78** từ approved profile; không đổi default của legacy fixture EvidenceGate hay giả semantic calibration. |
| Focused regression và repair limit | [Initial](../../infra/local/rag-fixture/acceptance-20261006-13-async-tests.json): 143 passed/4 failed, 6,39s; stdout renderer thêm UnicodeEncodeError sau khi delegated receipt đã lưu failures. [Repair 1](../../infra/local/rag-fixture/acceptance-20261006-13-async-repair1.json): 146 passed/1 failed, 6,15s; giữ SAFE_FAILURE khỏi evidence-gate reclassification, khai báo đúng Settings enum và UTF-8 stdout. [Repair 2](../../infra/local/rag-fixture/acceptance-20261006-13-async-repair2.json): **146 passed/1 failed, 6,27s**, command exit 1; new fixture dùng `development`, được Settings và synthetic identity guard hiện hành chấp nhận. Không sửa guard identity. Hai attempts đã dùng; dừng sửa/retry scope graph/API, không đổi run ID để làm thêm repair. |
| Các behaviors mới đã qua tests | Same-loop provider/retrieval awaits; evidence không nằm trong system channel; exception/failed/malformed generation không copy nguồn; cancellation join; outer latency budget cancel retrieval; lowered bootstrap evidence threshold bị reject. Tests dùng deterministic model/storage/tokenizer fakes, **không phải real provider/full M1**. Test double cũ trong context-propagation chỉ đổi `run` sang async `arun` để theo interface; không đổi assertions/expected outcomes. |
| Docker trước và sau thao tác của người dùng | [Readonly diagnosis](../../infra/local/rag-fixture/acceptance-20261006-13-docker-readonly-diagnosis.json): daemon chưa kết nối, hai command exit 1. Sau reply `Docker Desktop/Linux engine đã chạy`, [ownership](../../infra/local/rag-fixture/acceptance-20261006-13-owned-after-engine.json) passed. [Runtime state](../../infra/local/rag-fixture/acceptance-20261006-13-fixture-runtime-state.json) chứng minh exact pinned digest/volume/network/read-only init mount khớp nhưng container dừng. [Resume](../../infra/local/rag-fixture/acceptance-20261006-13-fixture-resume.json): start đúng container hiện có, healthy và immutable/ownership checks đạt, exit 0 / 5,641s. Không compose recreate, thay image/volume hoặc reset DB. |
| Actual PostgreSQL READ ONLY | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-13-owned-db-readonly-after-resume.json): exact endpoint `127.0.0.1:15433/campus247_rag_fixture`, ownership/image/mount/network + database/user/schema/fixture marker + existing seed guards passed. `transaction_read_only=on`, statement timeout 2s; head **0012**, legacy vector dimension **1536**, counts **1 source/1 version/3 chunks**, active pointer **0**. Hashes của ba row sets giữ nguyên qua negative probes. Lần trước container chưa chạy bị AssertionError, [receipt lỗi](../../infra/local/rag-fixture/acceptance-20261006-13-owned-db-readonly.json) giữ nguyên. Không import/execute migration 0013 hoặc đọc default DSN. |
| Actual SQL eligibility negative probes | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-13-owned-db-filter-probe-repair1.json): **7/7** conditions; ba empty scopes bị DTO reject trước SQL, bốn SQL statements cho unknown legacy scope/simulation forbidden ở lexical/vector đều **0 candidates**, shared compiler predicates trước ORDER BY/LIMIT. READ ONLY và exact seed hashes giữ nguyên. Vector query là synthetic fixed vector được ghi rõ, không Gemini/semantic quality evidence. Positive scoped corpus/active-index case chưa chạy. [Initial probe failure](../../infra/local/rag-fixture/acceptance-20261006-13-owned-db-filter-probe.json) do tạo invalid empty scope ngoài try boundary đã giữ; một repair harness ghi nhận đúng rejection, không nới scope validator hoặc sửa zero-leakage expectation. |

### Failure còn lại và điều kiện tiếp tục cụ thể

`test_bootstrap_injects_actual_canonical_service_into_api_runner` hiện thất bại:
SSE trả abstention thay vì grounded answer có citation. Source inspection xác định
[stream_result.py](../../services/api/src/campus247/application/conversation/stream_result.py)
yêu cầu candidate `version_label`, `source_status`, `locator`; typed canonical DTO
và projection mới chưa mang đủ ba trường. Không gán version/status/locator giả
hoặc sửa citation contract để test pass. Physical `document_version.version_label`
đã tồn tại từ migration 0002 và được xác nhận trong actual schema; vấn đề còn ở
reader/DTO/projection. Sau hai repair attempts, scope này dừng với evidence; chưa
được báo completed. Không chạy lại broader suite để giấu failure này hoặc hai
migration failures lịch sử.

Migration 0013 có exact SHA-256
`50e59a3a229fcaecb72d812f31c9c6bdc06542e02c2c277c838953c7d920f3c1`;
static review thấy bốn nullable columns, all-null/complete tuple CHECK cho đúng
BGE/1024, HNSW partial cosine index, no backfill/activation/destructive downgrade.
[Patch reviewable](../../infra/local/rag-fixture/acceptance-20261006-13-guard-review.patch)
chỉ thêm hash đó vào REVIEWED_ADDITIONS, `git apply --check` exit 0; **chưa apply**.
Đã hỏi người dùng exact protection change và additive fixture migration vì Global
Agent Safety Policy cấm sửa protection controls khi chưa yêu cầu chính xác. Reply
về Docker chỉ xác nhận engine, không suy ra approval cho patch riêng. `fixture.py`
và mọi migration/security/permission guards giữ nguyên; không dùng executor khác
để vượt rejected source gate. Generic fixture prepare cũng cấm implicit migration
existing head: chỉ có explicit scoped upgrade được chấp thuận mới được chuẩn bị
và chạy trên owned DB, với before/after preservation.

Không gọi provider ở lượt 13 hoặc tự cấp ngân sách mới sau cap 48 của lượt 12.
Không đổi immutable BGE profile thành Gemini metadata binding dưới cùng version.
Actual reranker/runtime clearance, scoped corpus publish/index, metadata mapping,
durable history/citations, authenticated real browser/full-path, release evaluation
và load/recovery/pilot vẫn chưa có đủ evidence. Không yêu cầu signatures hoặc
reviewer độc lập. [Final audit lượt 13](../../infra/local/rag-fixture/acceptance-20261006-13-final.json)
ghi exact source/test/receipt hashes, diff/status, guard/history preservation và
trạng thái `failed`/`not_verified` theo scope, không coi audit exit 0 là nghiệm thu.

## Chuẩn bị lượt 14 — các hành động phụ thuộc xác nhận cụ thể

[Baseline mới](../../infra/local/rag-fixture/acceptance-20261006-14-baseline.json)
ghi 1.188 hashes và dirty state; [preflight](../../infra/local/rag-fixture/acceptance-20261006-14-preflight.json)
dependency/catalog/OpenAPI đạt. Trước cập nhật báo cáo, toàn bộ baseline source
hashes giữ nguyên. Không chạy lại regression đã chạm giới hạn, không gọi provider
hoặc ghi DB.

[Runner được chuẩn bị](../../infra/local/rag-fixture/acceptance_upgrade_20261006_14.py)
chỉ hỗ trợ đúng 0012 → 0013, không gọi generic fixture prepare hoặc seed. Runner
yêu cầu receipt về câu trả lời trực tiếp cho exact patch/fixture, exact migration
hash đã nằm trong REVIEWED_ADDITIONS và toàn bộ source gate hiện hành đạt;
thiếu một điều kiện sẽ dừng trước kết nối DB. Khi được phép chạy, ownership/
immutable runtime/DB/schema/marker được kiểm lại, dùng một transaction có
statement/lock/overall deadlines, kiểm seed và hashes của tất cả old rows,
columns, indexes, constraints trước/sau; chỉ commit khi preservation đạt. Bốn
nullable columns và HNSW partial index được kiểm; vectors mới vẫn NULL, pointer
vẫn rỗng. AST đã qua kiểm tra; runner **chưa được thực thi**, không gọi đây là
migration pass hoặc actual DB acceptance. Guard patch `git apply --check` exit 0,
chưa apply.

Readonly review thêm xác định assertion `candidate.issuer in response.text` trong
new composition test: ApiCitation hiện hành không có field issuer và deterministic
tuition response không mang issuer đó. Đây là vấn đề test/contract cần xử lý đúng
authority, ngoài ba citation fields thiếu đã ghi ở lượt 13; chưa đổi assertion,
model fake output hoặc contract để làm test pass. Không suy diễn rằng chỉ thêm ba
fields sẽ chắc chắn cho 147/147.

[Audit chuẩn bị](../../infra/local/rag-fixture/acceptance-20261006-14-preparation.json)
ghi exact runner/report/receipt hashes, diff/status và preservation. Phần tiếp
tục citation sau hai repairs và thay protection control đều cần câu trả lời cụ
thể đã được trình bày; authorization engineering chung, Docker engine reply và
DEC-022 không thay hai ranh giới này. Không yêu cầu lại chữ ký/reviewer độc lập.

### Thực thi sau xác nhận trực tiếp cho hai mục

Người dùng trả lời **`Cho phép cả hai mục trên.`** sau hai câu hỏi cụ thể.
[Authority receipt](../../infra/local/rag-fixture/acceptance-20261006-14-authority.json)
ghi exact patch/hash/fixture và tối đa một repair attempt bổ sung;
[authorized baseline](../../infra/local/rag-fixture/acceptance-20261006-14-authorized-baseline.json)
đối chiếu source trước mutation. Không mở rộng sang reset/backfill/deletion,
activation, production hoặc các protection changes khác. Các snapshot chuẩn bị
ở trên và mọi failure cũ được giữ nguyên, không viết lại thành passed.

| Thực thi | Kết quả |
|---|---|
| Guard patch | Apply đúng patch đã trình bày: chỉ thêm SHA `50e59a3a229fcaecb72d812f31c9c6bdc06542e02c2c277c838953c7d920f3c1` vào REVIEWED_ADDITIONS. Giữ mọi prior hashes và unknown-source rejection. `fixture.py` sau patch SHA `88939c19e4f82a48620256e7e2207f25b39f61cee622ddcb38b8c062f2fc176b`. Không sửa guard prepare hoặc executor để ngầm upgrade. |
| Actual additive migration | [Upgrade receipt](../../infra/local/rag-fixture/acceptance-20261006-14-explicit-0013-upgrade.json): exit 0, committed=true, đúng endpoint `127.0.0.1:15433/campus247_rag_fixture`. Full source gate + immutable Docker ownership/runtime + DB/user/schema/marker kiểm lại. Một transaction, statement timeout 5s, lock timeout 2s, outer deadline 35s. Tất cả old rows/columns/indexes/constraints hashes trước và sau bằng nhau. Head 0013; legacy vector(1536) giữ nguyên; thêm nullable vector(1024) và ba metadata columns, CHECK/HNSW partial đúng source. Không backfill/publish/activate. |
| Independent committed readback | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-14-committed-0013-readback.json): exit 0, `transaction_read_only=on`, head 0013, old schema/data hashes bằng upgrade receipt. 1 source/1 version/3 chunks giữ nguyên. Legacy nearest-neighbor ordering và wrong-dimension rejection đạt. PostgreSQL 16.15/pgvector 0.8.6. New vectors đều NULL, active pointer 0. Đây là actual DB storage/preservation proof, chưa phải positive model/index retrieval. |
| Citation repair đã thực hiện | [DTO](../../services/api/src/campus247/domain/retrieval.py) mang optional version_label/source_status; unknown vẫn unknown và public conversion fail closed. Hai SQL readers SELECT version label, publication/approval state thực tế; shared row conversion chỉ nhận published/approved rows, giữ SYNTHETIC marker. [Bootstrap](../../services/api/src/campus247/bootstrap/app.py) đưa exact version/status và section/page locator vào server candidates. Không thêm field vào public ApiCitation hoặc sửa SSE contract, threshold, identity grants, model fake output. Hai existing test fixtures chỉ khai báo metadata mô phỏng còn thiếu; mọi assertions giữ nguyên. |
| Regression đúng một lần được cho phép | [Execution receipt](../../infra/local/rag-fixture/acceptance-20261006-14-citation-authorized-attempt1.json) và [delegated output](../../infra/local/rag-fixture/delegated-acceptance-20261006-14-citation-authorized-attempt1.json): **731 passed, 4 failed, 1 skipped, 1 warning / 736**, 12,95s, exit 1, source stable. Tám [provenance checks mới](../../tests/unit/retrieval/test_citation_provenance.py) đạt: SQL-row citation round-trip/version/section/page, invalid publication/version/simulation types reject, cross-branch version drift chặn trước reranker. Tất cả dùng deterministic fakes; không coi là real-provider M1. |

Regression giữ nguyên bốn failure:

- `test_profile_wiring.py::test_bootstrap_passes_the_immutable_profile_and_has_no_top10_override`: test gọi async callback như sync và so coroutine với `[]`; uncovered bởi suite mở rộng sau async change lượt 13. Không thêm synchronous bridge vào API hoặc đổi expectation để pass. Có unawaited-coroutine warning tương ứng.
- `test_retrieval_scope_migration.py::test_reviewed_ancestry_and_forward_only_recovery`: source gate hiện đã đạt, nhưng assertion vẫn khóa head 0012 trong khi reviewed source/actual DB head là 0013.
- `test_migration_0009.py::test_historical_0009_0010_ancestry_is_preserved`: assertion descendants vẫn chỉ gồm 0012/0011; actual ancestry thêm 0013→0012, lịch sử 0009/0010 không đổi.
- `test_async_io_graph.py::test_bootstrap_injects_actual_canonical_service_into_api_runner`: HTTP 200/message.completed/answered/chunk ID và canonical URI đã qua assertions; failure hiện ở issuer trong SSE. Public ApiCitation hiện không có issuer; không bỏ assertion, đổi fake response hoặc mở rộng contract ngoài approval để làm test pass.

Wrapper stdout gặp **UnicodeEncodeError sau khi cả execution/delegated receipts
đã được lưu**; nguyên nhân outer interpreter dùng cp1252, setting env sau startup
chỉ áp vào subprocess. Đọc lại saved UTF-8 receipt xác nhận đầy đủ counts/failures;
không rerun suite hoặc dùng run ID mới để có thêm repair. Cả bốn failure giữ
`failed`; một additional repair attempt đã hết. Không tự thay expected outcomes
hoặc normative contract vì chúng không khớp với implementation.

[Final audit](../../infra/local/rag-fixture/acceptance-20261006-14-final.json)
ghi exact diffs/status/hashes, authorized-only guard delta, unchanged assertions/
normative inputs, historical evidence preservation và postrun dependency/catalog/
OpenAPI verification. Migration scope hoàn tất; regression implementation chưa
completed. Không có provider calls mới, corpus publication hoặc active index.
Actual reranker/runtime clearance, full authenticated provider path, durable
history/browser, release quality evaluation và load/cost/recovery/pilot vẫn chưa
được chứng minh; M1/M2/M3 `not_verified`.

## Lượt 15 — regression khép, actual fixture kiểm lại, M1–M3 chưa nghiệm thu

Ủy quyền trực tiếp trong nội dung bàn giao ngày 2026-10-06 cho phép tối đa hai
repair attempts thêm và cập nhật đúng bốn tests để phản ánh approved behavior.
Run ID giữ nguyên `acceptance-20261006-15` xuyên mọi infrastructure retry; đã
dùng **một repair attempt**, còn một chưa dùng. Không reset cap hoặc đổi run ID
để vượt giới hạn. [Baseline](../../infra/local/rag-fixture/acceptance-20261006-15-baseline.json)
ghi HEAD, dirty/untracked state, canonical paths và source/config/test/evidence
hashes trước sửa; receipts dùng exclusive-create. Mọi failure lịch sử giữ nguyên.

| Kiểm chứng mới | Command và kết quả |
|---|---|
| Preflight | Fixture Python 3.12.14 `-B` chạy `scripts/verify_dependencies.py` → `tasks/tools/validate_catalog.py` → `contracts/tools/validate_openapi.py`, mỗi command exit 0. [Receipt](../../infra/local/rag-fixture/acceptance-20261006-15-preflight.json). |
| Sửa đúng bốn tests | Callback được await, giữ immutable profile/trusted actor/no top-k override; ancestry gồm 0013→0012→0011→0010 và giữ historical hashes/forward-only recovery; issuer được kiểm trong server CitationBundle, SSE được validate bằng public ApiCitation với IDs/title/URI/version/status/section/page/quote. Không mở rộng public contract. [Attempt ledger](../../infra/local/rag-fixture/acceptance-20261006-15-repair-attempt1-start.json). |
| Regression chính | `python -X utf8 -B infra/local/rag-fixture/acceptance_execute_20261006_15.py tests-escalated`: **735 passed, 1 skipped, 0 warnings**, 14,82s, exit 0, source ổn định. [Execution](../../infra/local/rag-fixture/acceptance-20261006-15-repair-attempt1-regression-escalated.json), [pytest output](../../infra/local/rag-fixture/delegated-acceptance-20261006-15-repair-attempt1-regression-escalated.json). Skip yêu cầu owned DB apply; không chạy historical apply helper trên DB 0013. Actual DB proof có receipt riêng. |
| Infrastructure failure giữ lại | Lần `tests` trong sandbox timeout 150s/exit 124, không có counts hợp lệ. [Receipt](../../infra/local/rag-fixture/acceptance-20261006-15-repair-attempt1-regression.json). Readback sandbox treo tại asyncio initialization rồi bị ngắt; [receipt](../../infra/local/rag-fixture/acceptance-20261006-15-owned-readonly-sandbox-interrupted.json). Chạy lại với execution permission phù hợp; không sửa guards hoặc product/tests giữa hai lần regression. |
| Actual PostgreSQL | `python -X utf8 -B infra/local/rag-fixture/acceptance_execute_20261006_15.py readback`, outer subprocess deadline 60s, transaction READ ONLY và statement timeout 2s: exit 0; ownership/image/mount/database/source guards đạt; old rows/columns/indexes/constraints hashes bằng preservation receipt lượt 14. PostgreSQL 16.15, pgvector 0.8.6, head 0013; **1 source/1 version/3 chunks**, legacy vector1536 giữ nguyên, **0 BGE vectors, 0 model bindings, 0 manifest, 0 active pointer**. [Readback](../../infra/local/rag-fixture/acceptance-20261006-15-owned-readonly.json), [command/deadline](../../infra/local/rag-fixture/acceptance-20261006-15-owned-readonly-execution.json). |
| Actual eligibility âm | 7/7: unknown legacy scope và simulation-forbidden qua lexical/vector eligibility, empty program/faculty/audience bị typed boundary reject trước SQL. Fake legacy query vector chỉ kiểm predicate, không chứng minh semantic retrieval. Cùng readback receipt; positive published/index case chưa có. |
| History/egress/schema/architecture | Existing tests bổ sung: lần đầu **10 passed, 2 failed**, 5,66s do `test_app_boot.py` gọi default Settings và guard chặn `.env`. Không cho đọc credentials để pass. Inject `Settings(_env_file=None)` trong isolated test harness, giữ assertions và guards: **12 passed, 2 plugin-import warnings**, 1,08s, exit 0. [Failure](../../infra/local/rag-fixture/acceptance-20261006-15-security-history.json), [synthetic config command](../../infra/local/rag-fixture/acceptance-20261006-15-security-history-synthetic-config.json). Đây là offline checks; không phải durable history/live bootstrap proof. |
| Corpus/catalog/gold | `python -X utf8 -B infra/local/rag-fixture/acceptance_inputs_20261006_15.py`, exit 0: join 15 source/version IDs với original synthetic metadata; content hashes, exact span/locator round-trips, injection/egress checks đạt. [Catalog](../../infra/local/rag-fixture/acceptance-20261006-15-dev-catalog.json); [gold](../../infra/local/rag-fixture/acceptance-20261006-15-dev-gold.json) giữ đúng sáu historical development questions/literals; existing rag_gold validator đạt 6/6 và snapshot binding. Context fixture được khai báo mô phỏng, không phải institution identity grants. |
| Eval inventory | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-15-input-readiness.json): 562 repository cases, tất cả review status `reviewed`; gồm 500 course-QA, 19 grounded-QA khác, 2 citation, 7 abstention, 4 injection, 4 privacy, 9 tool-safety, 2 multi-turn, 14 handover, 1 routing. Split labels: 341 dev/113 validation/108 sealed_test. Không suy ra release eligibility/held-out isolation từ số lượng/nhãn; course source reuse/provenance không được nhập vào corpus đang xét. Release gold resolved cho tuple này vẫn **0**. Không truy cập external release sealed content. |
| Runtime technical review theo DEC-022 | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-15-runtime-technical-review.json): rehash toàn bộ supporting evidence đúng image; giữ 192 Debian + 10 Cargo findings. Không yêu cầu chữ ký/reviewer độc lập. Compiled SBOM/build-feature applicability, native license closure và finding dispositions vẫn chưa đủ để clearance; static review không chứng minh model inference. |
| SQL-only operational sample | 100 warm sequential READ ONLY count queries trên ba legacy chunks/empty BGE storage: median **0,6535ms**, p95 **0,9970ms**, p99 **1,5227ms**, concurrency 1; raw samples/settings/database stats trong readback. Không phải TP-RAG, real-provider latency, cold/warm capacity hoặc full pipeline throughput. |
| Container snapshot | `docker stats --no-stream --format '{{json .}}' campus247-rag-fixture`, ownership kiểm trước, exit 0: idle CPU 0,00%, memory 44,53MiB/7,561GiB, 6 PIDs. [Receipt](../../infra/local/rag-fixture/acceptance-20261006-15-owned-container-stats.json). [Sandbox failure](../../infra/local/rag-fixture/acceptance-20261006-15-owned-container-stats-sandbox-failure.json) giữ lại. Snapshot idle không phải load/capacity measurement. |

### Tuple, technical gates và quyết định

Candidate tuple được ghi đầy đủ trong [fresh live manifest](../../infra/local/rag-fixture/acceptance-20261006-15-next-live-manifest.json):
`rag-prod-v1.0.0`; embedding `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`,
1024/L2/cosine, bundle SHA `27494beaa7a3dfc6bdff315254232b6a53fca3b39d37dadecdc92bc264981e9a`;
reranker `BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`,
bundle SHA `b0b73b8047e52a0fb3670a3b4789cfa07fe52fe1d910e48dcfd9dd0f79aaa732`;
TEI image `sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`;
corpus SHA `e81bb6ed945d6a04e835383070b0ca83ece2b9b9f32968493e112aad8ce90eb8`;
LLM candidate `deepseek-chat` tại `https://api.deepseek.com` từ historical approved
synthetic connectivity scope, chưa có fresh capability/full-path evidence.
Prompt/composer/profile/canonical/bootstrap/migration source hashes nằm trong manifest.
Storage là `knowledge_chunk.embedding_rag_v1` trên exact owned fixture 0013;
**index version NULL/active pointer 0**, chưa có release tuple chạy thực tế.

Không chọn winner từ sáu development queries hòa điểm; Gemini 768/1536 và BGE
là những model/profile khác nhau. Legacy vectors1536 không được dùng thay Gemini
hoặc BGE. Token counts Gemini 155–263 không xác nhận BGE tokenizer bound900.
Corpus hiện vẫn quarantined; nhiều section locators là `Untitled Document`,
được giữ đúng provenance hiện có, chưa tự thay bằng locator không có bằng chứng.

Manifest mới **prepared_not_executable**: local embedding/reranker loopback
18081/18082, tối đa 30 inference/40 HTTP, concurrency1, 128 tokens/item,
700ms/operation, 60s/batch, local cost cap0; LLM candidate tối đa 24 generations/
26 HTTP, 100.000 input/20.000 output tokens, 5s/operation, 120s/batch,
$0,25 reservation cap. Pricing, fresh exact live scope/caps và prerequisite
checks phải đạt trước execution; reservation không phải actual billed cost.
Gemini cap lịch sử **48/48 inference, 67 HTTP** đã hết, không dùng lại. Lượt này
**0 provider calls**, không publish/activate hoặc thay dữ liệu fixture.

| Mốc | Trạng thái | Tuple/tiêu chí đã đạt | Còn thiếu để nghiệm thu | Go/no-go |
|---|---|---|---|---|
| M1 | `not_verified` | Candidate tuple trên; regression735 và actual DB preservation/negative eligibility đạt. | BGE tokenizer/runtime inference/reranker clearance; reviewed scoped corpus ingestion, vectors/manifest/publish/activation; actual authenticated browser→API→DB→providers→gate→citation resolver; truthful startup readiness; durable bounded history/correction/cancellation/reauthorization. Default bootstrap vẫn dùng in-memory conversation service và chưa chứng minh history truyền vào provider; không dùng synthetic API pass thay proof này. | **no-go** |
| M2 | `not_verified` | Cùng candidate tuple; 15-chunk trusted dev catalog và 6/6 gold integrity validation. Approved RAG quality thresholds giữ nguyên. | Executed frozen release corpus/index/model/prompt tuple, release baseline authority, eligible gold/splits/held-out sources, negatives/multi-turn, ablation, ≥3 repeats phù hợp, denominators/subgroup failures/variance/confidence và actual quality/security metrics. Không dùng 500 course samples hoặc sáu dev probes thay release benchmark. | **no-go** |
| M3 | `not_verified` | Cùng candidate chưa activate; SQL-only100 sample và idle DB stats có actual evidence. | Full-path load/concurrency/stage/cold-warm/throughput/memory/pool/cache/errors/cancellation/recovery trên active tuple; fresh actual provider usage và billed cost; pilot/CSAT/verified resolutions/capacity. Đầu vào pilot và billing ngoài repo chưa có. | **no-go** |

Migration **completed**, scoped regression **passed**, milestones **chưa accepted**
là ba kết luận riêng. Không đổi requirements/contracts/thresholds/dependencies,
không sửa protection controls, không cài package, commit/push/deploy hoặc truy cập
production. [Final scope audit](../../infra/local/rag-fixture/acceptance-20261006-15-final.json)
ghi postflight command/exit/evidence, exact changed paths, current hashes và
historical evidence preservation. Scope engineering có kết quả thực thi; không
tuyên bố hoàn tất nghiệm thu khi còn technical unknown và external inputs.

## Triển khai lượt 16 — sửa các thiếu sót kiểm chứng được ngay

Nguồn giao việc trực tiếp: `thiếu cái gì thì làm đi`. [Baseline mới](../../infra/local/rag-fixture/acceptance-20261006-16-baseline.json)
ghi dirty state, hashes implementation/normative/test và bằng chứng lịch sử trước
mọi mutation. [Preflight](../../infra/local/rag-fixture/acceptance-20261006-16-preflight.json)
dependency → catalog → OpenAPI exit **0 → 0 → 0**. Scope startup bổ sung có
[receipt riêng](../../infra/local/rag-fixture/acceptance-20261006-16-readiness-scope.json)
trước patch. Không tạo agent/chat, đổi guard, requirements/contracts/dependencies,
profile/thresholds hoặc ghi database; mọi thay đổi trước phiên được giữ nguyên.

### Những phần đã thực sự sửa và kiểm chứng

| Phần | Kết quả và giới hạn bằng chứng |
|---|---|
| Hard bound cho recent turns | [context.py](../../services/api/src/campus247/application/conversation/context.py) không còn giữ một turn quá dài vượt `max_chars`; giữ suffix mới nhất nằm trong ngân sách, bỏ khỏi context khi không turn nào vừa. Không truncate nội dung đã lưu. Reject budget 0/âm/bool/không integer. Đây là bound ký tự của turn buffer; chưa chứng minh summary/token budget hoặc history đã được nối tới real provider. |
| Tên nguồn và locator | [parse.py](../../services/worker/src/campus247_worker/ingestion/parse.py) dùng metadata title có nội dung khi thiếu heading H1; heading thật vẫn ưu tiên. NFC title không sửa canonical source. Tests giữ kiểm exact slices, overlap và reject locator giả, thêm metadata fallback/hash invariance và heading precedence. |
| Deadline readiness | [health.py](../../services/api/src/campus247/presentation/health.py) áp cùng 2 giây cho acquisition + `SELECT 1` + closure. Tests kiểm acquisition treo, query treo, cancellation propagation, successful close và Redis disabled. Đây là cooperative async cancellation, không chứng minh driver/service bất tuân cancellation sẽ bị cưỡng chế dừng. |
| Startup DB failure | [app.py](../../services/api/src/campus247/bootstrap/app.py) ghi trạng thái initialization failure; readiness trả sanitized **503 DEPENDENCY_UNAVAILABLE**, liveness vẫn alive. Successful lifecycle probe/dispose được kiểm bằng engine fake. Không thử default DSN, credential hay production endpoint; không thay identity/authorization configuration. |
| Corpus candidate mới | [parsed-candidate](../../infra/local/rag-fixture/acceptance-20261006-16-parsed-candidate.json), SHA `6439e86ae21ab9e8523e3a10154c5c711c886ad615baa29e24290a5f2b1592a8`: **15/15** title từ original synthetic source hash, canonical text/hash, chunk IDs/body/hash/offsets giữ nguyên; injection/egress scans và locator roundtrip đạt. Status vẫn `quarantined_preview`, không publish hoặc ghi index. Snapshot cũ không overwrite. |
| Catalog/gold | [catalog](../../infra/local/rag-fixture/acceptance-20261006-16-dev-catalog.json), [gold](../../infra/local/rag-fixture/acceptance-20261006-16-dev-gold.json), [readiness receipt](../../infra/local/rag-fixture/acceptance-20261006-16-corpus-readiness.json): **6/6 validated**, cùng sáu historical development queries/literals; cập nhật source-bound section paths và catalog snapshot hash trước inference. Trusted context vẫn chỉ là declared synthetic fixture, không tự cấp actual identity grants. Chưa có release/sealed benchmark. |

Các checks chạy từ root bằng Python fixture đã có sẵn; async tests chạy trong
approved escalated shell vì sandbox socketpair đã được chẩn đoán treo ở lượt 15.
Credential/network/deletion guards không sửa. Harness dùng
`Settings(_env_file=None)` cho synthetic configuration, không đọc `.env`.

| Command / lần chạy | Exit / evidence |
|---|---|
| `python -B infra/local/rag-fixture/acceptance_complete_20261006_16.py focused` | **0**, [receipt](../../infra/local/rag-fixture/acceptance-20261006-16-focused.json) / [delegated output](../../infra/local/rag-fixture/delegated-acceptance-20261006-16-focused.json): **65 passed, 2 warnings, 2,68s**. |
| `python -B infra/local/rag-fixture/acceptance_complete_20261006_16.py corpus` | **0**, source/catalog/gold receipts ở trên; no database/provider calls. |
| `python -B infra/local/rag-fixture/acceptance_complete_20261006_16.py tokenizer-inventory` | **0**, [inventory](../../infra/local/rag-fixture/acceptance-20261006-16-tokenizer-inventory.json): exact tokenizer JSON/config/special-token/SentencePiece file sizes và SHA khớp BGE bundle. Chỉ đọc metadata, không load model weights hoặc chạy tokenizer. |
| `python -B infra/local/rag-fixture/acceptance_complete_20261006_16.py regression` | **0**, [receipt](../../infra/local/rag-fixture/acceptance-20261006-16-regression.json): **760 passed, 2 warnings, 11,43s**, trước patch initialization-failure. |
| `python -B -c "import sys; sys.path.insert(0,'infra/local/rag-fixture'); import acceptance_complete_20261006_16 as runner; raise SystemExit(runner.tests('readiness'))"` | **0**, [final regression](../../infra/local/rag-fixture/acceptance-20261006-16-readiness.json) / [delegated output](../../infra/local/rag-fixture/delegated-acceptance-20261006-16-readiness.json): **762 passed, 2 warnings, 11,62s**, sau patch startup; source hashes ổn định trong phép chạy. Không cộng các lần chạy overlapping thành số test riêng. |
| Offline `prepare` worklist | Initial **1**, [failure giữ nguyên](../../infra/local/rag-fixture/acceptance-20261006-16-prepare-initial-failure.json): đọc sai tên key `evidence_hashes`; dừng trước tạo artifacts/live operation. Sửa một lần đúng `evidence_sha256`, rerun **0**. Không đổi input hoặc disposition để pass. |

Hai warnings là `PytestAssertRewriteWarning` do `anyio`/`langsmith` đã import
trước pytest. Assertions/expected results/security checks không bị hạ. Source
không sửa sau final regression. [Initial helper snapshot](../../infra/local/rag-fixture/acceptance_complete_20261006_16_initial_snapshot.py)
được tái lập byte-for-byte và hash `d2660114bda81459c886d454c5bd76cb719a4a4dca8de7e6b1a6b8df33a02425`
khớp các receipts đầu; [verified helper snapshot](../../infra/local/rag-fixture/acceptance_complete_20261006_16_verified_snapshot.py)
giữ phiên bản final tests/worklist. Helper đang phát triển không được coi là
immutable source của tất cả receipts khi hash khác nhau.

Các defects mới đều đạt ở implementation attempt đầu, không retry implementation
để che thất bại. Một helper repair đã ghi riêng. Không mở lại exhausted graph
repair scope lượt 13, không reset ledger bổ sung citation/test lượt 15 bằng run ID mới.

### Tokenizer/runtime và gói bước tiếp theo

Model/profile/storage tuple tiếp tục giữ BGE-M3 revision
`5617a9f61b028005a4858fdac845db406aefb181`, 1024/L2/cosine, reranker revision
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, `rag-prod-v1.0.0`, TEI CPU 1.9.4
image `sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`
và owned fixture `127.0.0.1:15433/campus247_rag_fixture`. Actual DB head 0013,
zero BGE vectors/manifest/active pointer là phép đọc lượt 15; lượt 16 không gọi DB,
không dùng SQL-only latency cũ làm full-path M3 proof.

Tokenizer thực tế chưa có trong environment hoặc approved pinned lock.
`tokenizers`, `sentencepiece`, `transformers`, `torch`, `onnxruntime` đều absent.
Exact BGE tokenizer là **Unigram**, có normalizer **Sequence**, pre-tokenizer
**Metaspace** và post-processor **TemplateProcessing**. Bốn file tokenizer đã
rehash; không dùng số từ/ký tự, Gemini count hoặc tokenizer tự viết để kết luận
hard maximum **900 tokens**. Pinned TEI source Cargo.lock dùng tokenizers **0.21.4**;
Python tooling cùng phiên bản là phương án cần resolve/review exact closure,
không tự thêm dependency.

[Worklist runtime](../../infra/local/rag-fixture/acceptance-20261006-16-runtime-worklist.json)
giữ **202 exact finding rows** (192 Debian + 10 Cargo), component/version/advisory,
hash bằng chứng và hành động kỹ thuật cụ thể. Current disposition còn
`not_verified`: cần compiled Rust/native/OS SBOM/features gắn image/router hash,
license/redist/notices của MKL 2024.0.0-49656 cùng native/static closure, và
applicability/remediation từng finding. Executor được phép review; chữ ký và
reviewer độc lập không còn là blockers. Không biến historical field
`independent_review_required` thành yêu cầu reviewer mới hoặc thành clearance.

[Execution packet mới](../../infra/local/rag-fixture/acceptance-20261006-16-reviewable-execution-packet.json)
đã freeze candidate corpus/catalog/gold hashes, source hashes sau startup patch,
tuple và caps. `approved_for_execution=false`, actual billed cost null. Đây là
gói reviewable, chưa phải runner đã chạy full M1. Fresh local inference caps vẫn
30 inference / 40 HTTP, concurrency 1, deadline/token/resource limits giữ nguyên;
fresh LLM batch đề xuất 24 generation / 26 HTTP, 100k input + 20k output,
concurrency 1, 120s overall, cost reservation **≤ USD 0.25**. Không dùng lại
Gemini budget cũ **48/48**.

Đã kiểm [pricing chính thức DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/)
ngày 2026-10-06: candidate được tài liệu hiện tại nêu là `deepseek-flash`, version
`DeepSeek-V4.1-Flash`; peak cache-miss input USD 0.30/M và output USD 1.20/M.
Ước tính từ aggregate token caps là USD 0.054, không phải billed cost. Alias cũ
`deepseek-chat` không được trang đó liệt kê; chưa suy ra provider sẽ reject alias.
Candidate mới chưa được chọn bằng comparison hoặc xác minh actual response
model/non-thinking/schema/usage. Cần recheck pricing và fresh scoped approval
trước mọi paid call; application gateway/config chưa đổi.

Automatic approval review đã **reject** thao tác đọc public metadata
`https://pypi.org/pypi/tokenizers/0.21.4/json` qua urllib và tạo đề xuất. Lý do:
external network access bị đánh giá là chưa được người dùng cho phép cụ thể theo
project rules. Command không thực thi; không tải wheel/cài package. Không dùng
workaround để đọc metadata sau rejection. [Proposal/blocked receipt](../../infra/local/rag-fixture/acceptance-20261006-16-tokenizer-dependency-proposal.json)
ghi hash artifact/closure chưa biết, không bịa pin/license clearance.

Bước cần xác nhận hiện tại chỉ là đọc metadata công khai PyPI cho
`tokenizers==0.21.4` và dependencies để chốt exact artifact hashes/license/closure,
≤30 HTTP requests, ≤1MiB/response, timeout 15s/request, receipts mới trong fixture.
Chưa xin quyền cài dependency/gọi model. Exact installation/allowlist-lock changes
và fresh paid batch là các mục riêng, chỉ được xem xét sau gói pinned closure và
technical prerequisites hoàn chỉnh.

### Kết luận M1–M3 sau lượt 16

| Mốc | Trạng thái | Delta đã đạt | Còn thiếu | Go/no-go |
|---|---|---|---|---|
| M1 | `not_verified` | 762 offline regression; context turn character cap; source-title locators; bounded/truthful DB/Redis readiness; source-bound candidate/catalog. | Actual tokenizer/runtime/reranker, cleared compiled/native/findings; publish/vectors/manifest/active index; authenticated browser→API→DB→providers→gate→citation resolution; durable final-message/citation storage và reviewed bounded/redacted history wiring. Startup bindings/real model readiness chưa được chứng minh bằng offline tests. | **NO-GO** |
| M2 | `not_verified` | Sáu dev gold được validate lại trên catalog mới, expected queries/literals giữ nguyên. | Representative source-bound release corpus/gold/splits, frozen actual full-path runs, required quality/subgroup/security/ablation/repeat metrics. Không đổi thresholds để dùng sáu dev cases thay benchmark. | **NO-GO** |
| M3 | `not_verified` | False-ready bugs đã sửa bằng deterministic failure/cancellation/lifecycle tests. | Full-path reference load/concurrency/cold-warm/stage/memory/pool/error/cancellation/recovery/reconciliation; actual usage/cost và pilot/CSAT/verified resolutions. | **NO-GO** |

[Final audit lượt 16](../../infra/local/rag-fixture/acceptance-20261006-16-final.json)
ghi postflight dependency/catalog/OpenAPI command/exit/output, exact scope diff,
current hashes và historical preservation. Completed engineering defects không
đồng nghĩa milestones accepted. Không cài dependency, gọi live provider, ghi DB,
commit/push/deploy hoặc truy cập production; không xóa dữ liệu/bằng chứng.

## Kết quả hiện tại — lượt 17, ngày 2026-10-06

Nguồn quyền mới là chỉ dẫn trực tiếp `tôi cho phép làm mọi thứ để đạt m1-m3`.
Đã tiếp tục dependency intake và engineering trong scope synthetic workspace.
Không diễn giải chỉ dẫn đó thành quyền phá hủy dữ liệu, hạ protection controls,
đổi expected results/thresholds hoặc bỏ technical unknown. DEC-022 tiếp tục
cho phép executor review mà không đòi chữ ký/reviewer độc lập.

[Baseline 17](../../infra/local/rag-fixture/acceptance-20261006-17-baseline.json)
được ghi trước mutation; [preflight](../../infra/local/rag-fixture/acceptance-20261006-17-preflight.json)
chạy dependency → catalog → OpenAPI, cả ba exit 0. Scope mới là isolated tokenizer
tooling và receipts dưới fixture, cùng cập nhật báo cáo này. Product source
không đổi ở lượt 17; final backend regression còn áp dụng là **762 passed,
2 warnings / 11,62s** của lượt 16. Không cộng các lần chạy overlapping.

### Gate tokenizer đã có bằng chứng thực tế

| Kiểm chứng | Kết quả / evidence |
|---|---|
| Exact metadata/closure | [Closure](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-closure.json): tokenizers **0.21.4**, HF hub **0.36.0** và 12 dependencies theo Python 3.12 Windows markers; exact versions, wheel URLs, sizes, SHA256. PyPI không báo advisory cho các phiên bản đã chọn; đây không phải comprehensive security attestation. |
| Acquisition | [14 artifacts](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-acquisition.json), hash/size match. Chỉ tạo mới trong `tokenizer-tooling-20261006-17`; không sửa application pins/allowlist/lock. |
| Wheel review | [Review](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-wheel-review.json): exact METADATA name/version, RECORD hashes/sizes, member bounds, safe paths/no symlink, license hashes và native-extension inventory. Wheel tokenizers thiếu LICENSE: bổ sung từ publisher tag **v0.21.4** gắn immutable commit cùng Cargo version; [license receipt](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-publisher-license.json). Không suy ra embedding/reranker runtime clearance. |
| Malware scan thật | [Completion](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-malware-completion.json): Defender custom scan đúng 14-wheel folder; start/end events **1000/1001** khớp ScanId `{0F113C4D-1D39-4003-8437-B9A203EDCA3A}`, không abort/error/detection cho target, 14 hashes sau scan giữ nguyên. Không đổi security settings. |
| Isolated expansion | [Installed manifest](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-installed.json): exclusive creation vào site-packages riêng, mapping/hash mọi file; không pip/install scripts hoặc cleanup. |
| Exact BGE counts | [Token-bound receipt](../../infra/local/rag-fixture/acceptance-20261006-17-bge-token-bound.json): thực thi official **tokenizers 0.21.4** với BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`; exact JSON SHA `21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08`, special tokens bật, truncation/padding tắt. **15/15 passed**, 128–219, max 900. No network/credentials/model weights/inference calls. |
| Corpus binding | [Binding mới](../../infra/local/rag-fixture/acceptance-20261006-17-corpus-tokenizer-binding.json) rehash candidate `6439e86ae21ab9e8523e3a10154c5c711c886ad615baa29e24290a5f2b1592a8`, kiểm từng chunk/source/content hash/char span đúng token rows. Giữ IDs/body/offsets và quarantine snapshots; chưa published/indexed, không tự cấp source/actor grants. |

Metadata resolver dùng đủ **hai repair attempts**: lần đầu response simple-index
vượt byte cap; repair 1 bị exact-version filelock advisory chặn; repair 2 chọn
fixed pins theo public metadata và pass. Successful resolution có 14 JSON reads
kể cả root; các attempts cũ có ledger riêng, initial aggregate count chỉ có upper
bound, không bịa tổng HTTP count. Wheel review dùng đủ **hai repairs**: CRLF
METADATA parsing, sau đó publisher license supplement; failed receipts và helper
snapshots giữ nguyên. Đây là intake tooling scopes, không mở lại exhausted
product implementation repair scopes từ các lượt trước.

Scan preflight đầu lỗi PowerShell path syntax trước scan; sửa một lần và scan
thật đã chạy. [Receipt đầu](../../infra/local/rag-fixture/acceptance-20261006-17-tokenizer-malware.json)
vẫn exit 1 vì host trả `CustomScanEndTime=null`. Read-only event verifier dùng
ScanId start/end thực tế để xác nhận completion; không sửa receipt cũ hoặc chạy
lại scan để che lỗi verification. Final audit rehash toàn bộ installed manifest.

### Runtime và provider còn cần kiểm chứng

[Public attestation discovery](../../infra/local/rag-fixture/acceptance-20261006-17-runtime-public-attestation-discovery.json)
gọi GitHub attestation endpoint cho đúng TEI image và router digests: **hai HTTP
404**. Không tìm được artifact qua hai requests đó; không kết luận publisher
hoàn toàn không có SBOM. Compiled Rust/native/OS features, MKL license/static
closure và **202 finding dispositions** vẫn chưa verified. Không launch image.

[Exact-revision alternate inputs](../../infra/local/rag-fixture/acceptance-20261006-17-alternate-runtime-inputs.json)
đọc public Hugging Face metadata: BGE-M3 có ONNX graph SHA
`f84251230831afb359ab26d9fd37d5936d4d9bb5d1d5410e66442f630f24435b`
và external weights SHA `1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4`
(2.266.820.608 bytes). Reranker đúng revision chỉ có safetensors, không có ONNX
được liệt kê. Chưa tải các weights mới, load pickle, export hay chọn runtime.
Phương án ORT cần exact closure/license/findings, reviewed reranker export và
same-data comparison trước khi được chọn; public metadata không chứng minh
numerical/latency equivalence.

[Execution packet 17](../../infra/local/rag-fixture/acceptance-20261006-17-reviewable-execution-packet.json)
đã gắn receipts/hash mới và đóng missing-tokenizer item. Local envelope cũ vẫn
**128 tokens/item**, thấp hơn corpus max **219**: `corpus_compatible=false`.
Không truncate corpus hoặc âm thầm tăng cap; cần token/resource envelope cho
query và rerank pairs trước local model run. Packet `prepared_not_executable`,
không phải actual M1 evidence; Gemini historical inference budget vẫn **48/48**.

[DeepSeek rejection](../../infra/local/rag-fixture/acceptance-20261006-17-deepseek-automatic-approval-rejection.json)
ghi lệnh **GET `https://api.deepseek.com/models`** dùng
`workspace:.env#DEEPSEEK_API_KEY` bị automatic approval review từ chối trước
process start. Broad M1–M3 authorization được reviewer đánh giá chưa đủ cụ thể
cho secret/destination egress. **Khóa chưa đọc/gửi, zero provider calls, zero paid
generation**, không workaround transport/tool để vượt rejection. Model candidate
vẫn chưa được actual provider model/schema/usage/latency comparison xác nhận.

Mục quyền cụ thể đã chuẩn bị: đọc secret reference đó trong memory, chỉ gửi
qua HTTPS tới `api.deepseek.com` để GET `/models`, rồi synthetic generation
sau khi runtime/data gates đạt; tối đa **24 generation / 26 HTTP kể cả metadata,
100k input + 20k output tokens, concurrency 1, 5s/request, 120s tổng,
cost reservation USD 0.25**. Không gửi personal data/history, không ghi secret
hoặc reasoning content, không tự fallback. GET metadata có cost cap 0 và không
generation. Reservation không phải actual billed cost hoặc quyền vượt gates.

### Nghiệm thu sau lượt 17

| Mốc | Đã bổ sung | Còn thiếu để nghiệm thu | Trạng thái |
|---|---|---|---|
| M1 | Exact BGE token bound và isolated reviewed/scanned tokenizer closure; 15 chunk bindings; product fixes/regression lượt 16 giữ nguyên. | Cleared actual embedding/reranker runtime; source publication/vectors/manifest/active pointer; trusted authenticated browser→API→DB→providers→evidence→citation path; durable final-message/citation storage và bounded/redacted history wiring. | `not_verified`, **NO-GO** |
| M2 | Sáu development gold/source catalog và tokenizer bounds có binding. | Representative release corpus/gold/splits; frozen full-path quality, subgroup/security/ablation/repeat metrics theo thresholds hiện hành. | `not_verified`, **NO-GO** |
| M3 | Readiness defects có offline tests; resource/token incompatibility hiện rõ trước inference. | Actual full-path load/concurrency/cold-warm/stage/resource/error/recovery/reconciliation, measured usage/cost và pilot/CSAT/verified resolutions. | `not_verified`, **NO-GO** |

[Final audit 17](../../infra/local/rag-fixture/acceptance-20261006-17-final.json)
ghi dependency → catalog → OpenAPI postflight, Git scope/status và file hashes.
Các file có trước baseline được bảo toàn, ngoại trừ scoped patch báo cáo này;
source/lock/protection controls và historical receipts giữ nguyên. Lượt 17 không
ghi DB, launch model runtime, đọc private credential, gọi live inference,
commit/push/deploy, truy cập production hoặc xóa dữ liệu/bằng chứng.

## Kết quả hiện tại — lượt 18, ngày 2026-10-06

Người dùng trả lời trực tiếp `oke làm đi` cho yêu cầu ngay trước đó: đọc
`workspace:.env#DEEPSEEK_API_KEY`, chỉ gửi khóa tới HTTPS `api.deepseek.com`
để kiểm models và synthetic generation tối đa 24 lượt / USD 0.25 theo gói
giới hạn. Quyền đó đã được sử dụng; không hỏi lại quyền credential/destination.
[Baseline mới](../../infra/local/rag-fixture/acceptance-20261006-18-baseline.json)
giữ hashes/source/config/test/evidence và dirty state trước mutation;
[preflight](../../infra/local/rag-fixture/acceptance-20261006-18-preflight.json)
dependency → catalog → OpenAPI đều exit 0.

### Provider thật, failure thật và sửa usage

| Phép thực thi | Kết quả / evidence |
|---|---|
| Model discovery | [Manifest](../../infra/local/rag-fixture/acceptance-20261006-18-live-models-manifest.json), [receipt](../../infra/local/rag-fixture/acceptance-20261006-18-live-models.json): **HTTP 200 / 218ms**, đúng một GET, no redirects/retry. Actual list có `deepseek-flash`, `deepseek-v4-pro`; configured `deepseek-chat` không được liệt kê, không suy ra alias bị reject. Khóa chỉ ở memory, raw response không persist. |
| Single LLM component probe | [Manifest trước request](../../infra/local/rag-fixture/acceptance-20261006-18-llm-probe-manifest.json), [actual egress check](../../infra/local/rag-fixture/acceptance-20261006-18-llm-probe-egress.json), [failure receipt](../../infra/local/rag-fixture/acceptance-20261006-18-llm-probe.json): model actual `deepseek-flash`, input **47**, output **16**, reasoning **16**, latency **1250ms**, finish `length`, component `failed`. Chỉ fixed PUBLIC synthetic “Reply OK”; no corpus/history/personal data. Không coi response status `completed` là câu trả lời thành công. |
| Usage defect | Provider báo reasoning 16 nhưng adapter normalize 0. [Scoped source](../../services/api/src/campus247/infrastructure/llm/openai_adapter.py) đọc `completion_tokens_details.reasoning_tokens`, default 0 khi absent; giữ output tổng đã gồm reasoning, không double count. Không sửa request output/deadline caps, egress hoặc model config. |
| Regression sau sửa | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-18-reasoning-usage.json), [delegated offline evidence](../../infra/local/rag-fixture/delegated-acceptance-20261006-18-reasoning-usage.json): **766 passed, 2 warnings / 12,61s**, source stable, credential/network/deletion guards nguyên trạng và `Settings(_env_file=None)`. Bốn cases mới kiểm absent/zero/partial/all-reasoning usage, cached tokens và total không double count. No live calls trong regression. |

Tổng actual provider attempts lượt này là **2 HTTP = 1 models + 1 generation**,
generation không retry/fallback. Còn **24 HTTP / 23 generation** trong cùng
aggregate cap; không tạo ngân sách mới bằng đổi run ID. Giá peak được kiểm lại
từ [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/) ngày
2026-10-06. Usage quan sát cho estimate peak **USD 0.0000333**; actual billed cost
**null/unavailable**, không gọi estimate hoặc reservation USD 0.25 là hóa đơn.
Không thêm lần gọi live sau failure. Failure cũ giữ hash và mô tả behavior trước
source fix; không chạy lại helper fixed-output để overwrite bằng chứng.

Hai warnings regression là assert-rewrite của `anyio`/`langsmith` đã import
trước pytest. Implementation usage fix đạt ở attempt đầu, **0 repair attempts**.
Không mở lại exhausted citation/bootstrap scopes.

### Non-thinking patch đã reviewable, chưa đổi protection

[Tài liệu API chính thức](https://api-docs.deepseek.com/guides/thinking_mode/)
nêu thinking bật mặc định và hỗ trợ `thinking.type=disabled`. Actual probe khớp
hiện tượng default reasoning. Adapter hiện không có option này; egress allowlist
hiện không forward field đó. Không append field sau policy validation, tăng
output cap hoặc dùng transport khác để vượt guard.

[Patch chưa áp dụng](../../infra/local/rag-fixture/acceptance-20261006-18-non-thinking.patch)
và [proposal](../../infra/local/rag-fixture/acceptance-20261006-18-non-thinking-proposal.json)
gắn before/candidate hashes của đúng ba targets:

- `services/api/src/campus247/infrastructure/llm/openai_adapter.py`: opt-in
  `disable_thinking=False` mặc định; bật chỉ khi provider `deepseek`, model
  `deepseek-flash`, base URL đúng `https://api.deepseek.com` hoặc `/v1`.
- `services/api/src/campus247/infrastructure/llm/egress_policy.py`: FAQ purpose
  chỉ cho canonical `{ "thinking": { "type": "disabled" } }` và đúng model
  đó; reject enabled/extra keys/invalid value/model khác. Secret/PII scans,
  minimization và purposes khác giữ nguyên.
- `tests/contract/ai/test_deepseek_non_thinking.py`: explicit opt-in, endpoint/
  provider/model negatives, invalid values, secret denial và other-purpose
  minimization; no live provider calls.

[Candidate proof](../../infra/local/rag-fixture/acceptance-20261006-18-non-thinking-candidate-proof.json)
**12/12 cases**, deterministic offline dưới unchanged credential/network/deletion
guards, load draft qua module names riêng; production policy file không đổi.
Đây là unapplied draft checks, không cộng vào 766 production-source regression.
Initial proposal helper gặp ambiguous replace anchor và dừng trước candidate
creation; [failure receipt](../../infra/local/rag-fixture/acceptance-20261006-18-non-thinking-proposal-initial-failure.json)
và initial snapshot giữ nguyên. Một helper repair dùng exact anchor đã pass;
không đổi policy đang chạy hoặc expected results.

Cần quyền đúng thay đổi bảo vệ trước khi áp dụng patch: global safety policy
người dùng cung cấp yêu cầu exact protection-change request; [AGENTS.md](../../AGENTS.md)
yêu cầu human approval cho security-policy changes. Quyền external credential/
generation vừa xác nhận không được diễn giải thành quyền sửa egress allowlist.
Sau khi patch được phê duyệt và source checks đạt, probe mới dùng phần ngân sách
còn lại; M1 full batch vẫn phụ thuộc các runtime/data gates khác.

### Runtime binding đã làm rõ thêm

[Provenance feature binding](../../infra/local/rag-fixture/acceptance-20261006-18-runtime-provenance-feature-binding.json)
rehash retained publisher SLSA statement đúng attestation digest và image subject,
source commit `e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`. LLB khai báo đúng một
HTTP router release build với `ort,candle,mkl,static-linking,http`, no-default-
features, cùng Dockerfile hash đã bound; MKL package khai báo 2024.0.0-49656.
Đây là declared build features gắn exact image, **không phải compiled component
SBOM hoặc bằng chứng reachability**, không thực thi các build commands.
Unsigned provenance được mô tả đúng dưới DEC-022, không đòi lại signature.

Runtime chưa launch. Actual compiled/native/static closure, MKL obligations và
202 finding-specific dispositions vẫn chưa đạt; source feature flags không
thay chứng minh binary composition. Không dùng successful DeepSeek metadata
hoặc component generation để waive embedding/reranker gates.

### Nghiệm thu sau lượt 18

| Mốc | Delta thực tế | Tiêu chí còn thiếu | Trạng thái / quyết định |
|---|---|---|---|
| M1 | Authenticated model discovery; failed real LLM compatibility probe; usage fix với 766 regression; declared runtime feature binding. | Approved/applied non-thinking option và successful component/full path; cleared embedding/reranker runtime; publish/vectors/manifest/active index; trusted API/browser/citation path; durable final-message/citation/history. | `not_verified`, **NO-GO** |
| M2 | Candidate/tokenizer và sáu dev gold giữ binding; failure provider được giữ trong evidence. | Representative release corpus/gold/splits và actual full-path quality/subgroups/security/ablation/repeats. | `not_verified`, **NO-GO** |
| M3 | Single provider latency/usage quan sát, estimate và billed-cost unknown tách rõ. | Full-path load/concurrency/stages/cold-warm/resources/errors/recovery, actual cost và pilot outcomes. | `not_verified`, **NO-GO** |

[Final audit 18](../../infra/local/rag-fixture/acceptance-20261006-18-final.json)
ghi commands/exits và exact baseline diffs. Existing mutations chỉ gồm một dòng
usage normalizer, bốn regression cases và cập nhật báo cáo này. Egress policy,
application settings/lock/allowlist, protection guards và evidence lịch sử không
đổi. Không ghi DB, launch local model, commit/push/deploy, truy cập production
hoặc cleanup/xóa dữ liệu.

## Kết quả hiện tại — lượt 19, ngày 2026-10-06

Người dùng trả lời trực tiếp `oke` cho đúng đề nghị áp dụng patch non-thinking
đã có SHA256 và một re-probe trong ngân sách còn lại. [Baseline 19](../../infra/local/rag-fixture/acceptance-20261006-19-baseline.json)
ghi before hashes, đúng ba targets/candidate hashes và quyền này trước mutation.
[Preflight](../../infra/local/rag-fixture/acceptance-20261006-19-preflight.json)
dependency → catalog → OpenAPI đều exit 0. Không diễn giải xác nhận này thành
quyền tăng cap, thay model/profile production hoặc waive runtime/data gates.

### Patch được duyệt và kiểm chứng thực tế

| Kiểm chứng | Kết quả / bằng chứng |
|---|---|
| Exact patch | [Applied receipt](../../infra/local/rag-fixture/acceptance-20261006-19-approved-patch-applied.json): `git apply --check` và apply working tree exit 0; patch SHA `91baac5b549596abd83feae989e555e48b8a623783a059b50b96ebbb8a1718d8`. Hai source files khớp candidate đã duyệt, new test trước đó không tồn tại. Original dirty source bytes giữ trong snapshots. |
| Adapter | Optional `disable_thinking=False` mặc định; strict boolean. Khi opt-in chỉ cho provider `deepseek`, model `deepseek-flash`, exact HTTPS host `api.deepseek.com`, base path empty hoặc `/v1`. Current source SHA `6406932f7e3cdae9105546b6ce0f66523c62af42d852259fe6f997de29327b22`. |
| Egress | FAQ purpose cho exact dict `{"type":"disabled"}` và exact model; chặn enabled/extra fields/invalid shape/other model, strip ở purpose khác. Secret/PII scans và minimization giữ nguyên. Current source SHA `17b282cdcfb22d5704b2aa2aa2c6d39d5cea8e872178b35a70f42ef4f543bf60`. |
| Regression | [Receipt](../../infra/local/rag-fixture/acceptance-20261006-19-non-thinking-regression.json), [log](../../infra/local/rag-fixture/acceptance-20261006-19-non-thinking-regression.log): **778 passed, 2 warnings / 12,28s**, gồm 12 non-thinking cases. Original guards, scrubbed env và `Settings(_env_file=None)`; source ổn định, deterministic offline. Patch apply/test pass lần đầu, zero implementation repair trong scope này. |
| Actual request | [Manifest](../../infra/local/rag-fixture/acceptance-20261006-19-non-thinking-probe-manifest.json) và [egress receipt](../../infra/local/rag-fixture/acceptance-20261006-19-non-thinking-probe-egress.json): cùng constant PUBLIC “Reply OK”, actual adapter payload bằng actual minimized payload, có approved opt-in. Một POST, max 16 output, deadline 5s, concurrency 1, không retry/fallback. Không gửi corpus/history/PII. |
| Actual response | [Probe](../../infra/local/rag-fixture/acceptance-20261006-19-non-thinking-probe.json): model `deepseek-flash`, đúng OK, completed/stop; **22 input, 1 output, 0 cached, 0 reasoning tokens; 1.093 ms**. Không lưu raw response/reasoning/credential. Đây là LLM component compatibility, chưa là authenticated RAG path. |
| Ledger | [Budget](../../infra/local/rag-fixture/acceptance-20261006-19-provider-budget-ledger.json): tổng **2 generation / 3 HTTP**, input 69, output 17, giữ failed generation lượt 18 trong denominator; còn **22 generation / 23 HTTP / 99.931 input / 19.983 output**. Peak price estimate tổng **USD 0,0000411**, actual billed cost `null`; conservative reservation còn USD 0,2499589. Không reset ngân sách hoặc dùng lại 48/48 Gemini. |

Giá peak được kiểm lại từ [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/)
ngày 2026-10-06: cache-miss input USD 0,30/M, output USD 1,20/M. Estimate của
probe mới là USD 0,0000078, không phải hóa đơn. Root `.env` và application settings
không đổi; configured alias cũ `deepseek-chat` chưa tự chuyển sang production
`deepseek-flash`. Applied option chỉ được bật rõ trong component probe.
Provider không trả reasoning field hoặc reasoning-token counter ở response mới;
`reasoning_tokens=0` là giá trị adapter normalize khi counter vắng, không phải
counter 0 được provider xác nhận. Input 22/output 1 là usage provider đã báo.

### Corpus review trên snapshot hiện tại

[Defender scan](../../infra/local/rag-fixture/acceptance-20261006-19-candidate-malware-scan.json)
chạy exact candidate JSON `acceptance-20261006-16-parsed-candidate.json`, custom
report-only scan, exit 0, stdout “found no threats”. Scanner có chữ ký Microsoft
hợp lệ, Defender enabled; SHA trước/sau cùng
`6439e86ae21ab9e8523e3a10154c5c711c886ad615baa29e24290a5f2b1592a8`.
Không khắc phục/quarantine, update signatures hoặc đổi protection settings.
Preflight đầu lỗi Windows PowerShell module autoload trong môi trường PowerShell
Core; [failure receipt](../../infra/local/rag-fixture/acceptance-20261006-19-candidate-scan-preflight-failure.json)
và helper snapshot được giữ. Một repair dùng đúng `pwsh` hiện hành; scan chỉ
chạy một lần sau preflight hợp lệ, không chạy lại để che detection.

[Technical review](../../infra/local/rag-fixture/acceptance-20261006-19-corpus-technical-review.json)
theo quyền DEC-022 duyệt **chỉ chuẩn bị kiểm thử mô phỏng**: đã đọc toàn bộ 15
source texts, đều có simulation markers, không có hồ sơ cá nhân; emergency phone
là placeholder XXXX, không dùng làm thông tin thực. Recompute parser/chunker
kiểm đúng source hash/IDs/span/title/locator; **15/15** injection/prohibited-data
checks và six development gold validation passed. Pattern scans không phải
comprehensive guarantee. Exact BGE tokenizer receipt giữ **128–219 tokens**;
không load weights hoặc inference. Quarantine snapshots, source grants, DB rows
và publication/index state giữ nguyên; approval receipt này không tự cấp actor
grants hoặc chứng minh index activation. Release gold vẫn chưa có.

### Tuple và điều kiện thực thi còn thiếu

| Thành phần | Tuple hiện tại / trạng thái |
|---|---|
| Profile | `rag-prod-v1.0.0`, BGE-M3 1024 dimensions, L2 normalization, cosine; chưa active index. |
| Embedding | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`, bundle SHA `27494beaa7a3dfc6bdff315254232b6a53fca3b39d37dadecdc92bc264981e9a`. Tokenizer verified; actual runtime chưa clearance. |
| Reranker | `BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, bundle SHA `b0b73b8047e52a0fb3670a3b4789cfa07fe52fe1d910e48dcfd9dd0f79aaa732`; actual inference chưa verified. |
| Runtime | TEI CPU 1.9.4 image SHA `8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`, source `e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`, router SHA `157abaf15d1cf9ae906108cd5005b7a0590a8ab02355687b5412a6eab1fa5887`. Declared build features bound; compiled Rust/native/OS SBOM, MKL license/static closure và 202 finding dispositions chưa verified. Không launch. |
| LLM thử thành phần | HTTPS `api.deepseek.com`, `deepseek-flash`, explicit `thinking.type=disabled`, no fallback, one successful component probe; chưa chọn/activate production tuple. |
| Dữ liệu/index | Candidate SHA như trên; 15 source/15 chunks, review mới. Catalog SHA `bfb9786e5daad6114899fb8e5e3ebcc90a11a3864020fe9648812559575f38e0`; dev gold SHA `9b5aff1e8a346216a5f3952df55e4dc1a1f3a0305dc13197e160d4ef049ca01f`. No publication/vectors/manifest/active pointer; DB READ ONLY proof gần nhất lượt 15. |

Local inference envelope cũ vẫn **128 tokens/item**, không đủ corpus max 219
hoặc rerank query+passage. Không truncate dữ liệu hoặc tự tăng envelope. Runtime
clearance là technical missing evidence, không còn yêu cầu signature/reviewer
độc lập đã được DEC-022 waive. Các đường history/durable citation vẫn cần
reviewed schema và bounded/redacted wiring trước actual full-path test. Không
bypass migration protection để thực hiện schema mới.

### Commands và nghiệm thu sau lượt 19

Các lệnh Python dùng exact fixture interpreter
`infra/local/rag-fixture/.venv/Scripts/python.exe`, `-B`; chi tiết argv/output/exit
có trong receipts. Thứ tự: preflight dependency → catalog → OpenAPI (0/0/0);
approved patch check/apply (0/0); `acceptance_complete_20261006_16.tests('non-thinking-regression')`
với LABEL 19 và thêm exact new test (exit 0, 778 passed); approved
`acceptance_llm_probe_20261006_19.py` (exit 0, one generation); corpus review
helper `scan`, `review` (0/0 sau one preflight repair). Postflight và exact
scope audit ở [final receipt 19](../../infra/local/rag-fixture/acceptance-20261006-19-final.json).

| Mốc | Delta đã kiểm chứng | Tiêu chí chưa đạt | Trạng thái / go-no-go |
|---|---|---|---|
| M1 | Approved non-thinking patch, 778 offline regression, successful actual LLM component; current corpus malware/technical review và exact tokenizer binding. | Cleared actual embedding/reranker runtime; publish/vectors/manifest/activation; trusted authenticated browser→API→DB→providers→evidence gate→citation resolution; durable final-message/citation storage và bounded/redacted history; actual startup bindings. | `not_verified`, **NO-GO** |
| M2 | Sáu source-bound development gold hợp lệ, old/new provider attempts giữ nguyên denominator. | Representative release corpus, ít nhất 500 release gold với required splits; actual frozen full-path quality/subgroups/security/ablation và ba repeat runs theo tiêu chí hiện hành. Sáu dev cases không thay release benchmark. | `not_verified`, **NO-GO** |
| M3 | Single actual LLM latency/usage, estimate/billing unknown phân biệt rõ; readiness tests giữ nguyên. | Actual full-path reference load/concurrency/cold-warm/stages/resources/errors/cancellation/recovery/reconciliation; actual cost và pilot/CSAT/verified resolutions. | `not_verified`, **NO-GO** |

Lượt này không ghi DB, publish/index, launch local model, migrate, cài runtime
mới, commit/push/deploy hoặc truy cập production. Failure receipts và dirty work
có trước được giữ; không xóa/cleanup hoặc thay thresholds/expected results.

## Kết quả hiện tại — lượt 20, ngày 2026-10-06

Người dùng yêu cầu thực hiện triệt để các phần thiếu. Khi được hỏi input pilot,
người dùng trả lời chưa có nhóm thử/CSAT thực và muốn mô phỏng chân thực nhất.
Đã nhận scope mô phỏng và tách modeled outcomes khỏi human observations;
không đổi release criteria để kể pilot giả là pilot thật. [Baseline 20](../../infra/local/rag-fixture/acceptance-20261006-20-baseline.json)
bảo toàn file hashes và Git state; [preflight](../../infra/local/rag-fixture/acceptance-20261006-20-preflight.json)
dependency → catalog → OpenAPI đều exit 0 trước scoped source edits.

### Durable chat implementation

Đã thêm `infrastructure/repositories/conversations.py`: asyncpg-compatible
adapter nhận explicit owned pool và reviewed persistence-content validator,
không dùng DSN mặc định, không đọc credentials hoặc tự migrate. Conversation
creation dùng INSERT, không upsert/ghi đè dữ liệu cũ. Append khóa parent bằng
`SELECT ... FOR UPDATE`, cấp sequence, ghi immutable final message/citation map
và tăng parent version trong một transaction. SQL được parameterize, acquisition
và từng query có timeout; failure rollback, duplicate IDs giữ nguyên dữ liệu cũ.
Citation JSON deserialize theo existing ApiCitation, không phát minh metadata.
Validator là dependency bắt buộc: caller phải cung cấp policy đã review; source
này không tự chọn redaction policy hoặc cho phép personal-data processing.

`ConversationMessageService` dùng atomic path khi repository cung cấp nó;
existing in-memory path giữ nguyên. `create_app` có optional repository injection,
để executor bind adapter rõ ràng sau schema/ownership checks. Default app chưa
activate PostgreSQL repository; readiness/full startup còn chưa được actual
RAG full-path chứng minh. Không thêm dependency, đổi auth/egress/requirements.

[Regression cuối](../../infra/local/rag-fixture/acceptance-20261006-20-persistence-regression-repair2.json)
**782 passed, 2 warnings / 9,71s**, actual retained SQLite commits/close/reopen
phía sau narrow asyncpg test transport. Sáu new checks: reserved final ID và
citations/status/class qua repository restart; parent-update fault rollback;
30 appenders có sequence riêng; duplicate không đổi original; content-validator
rejection trước write; invalid/duplicate citation map bị chặn. SQL casts/row-lock
được dịch trong test transport: đây **không phải PostgreSQL row-lock/runtime
proof**, không gọi fake transport là actual production DB.

Harness đầu bị guard chặn pytest log `/dev/null` trước collection. Repair 1
đặt log trong fixture, nhưng pytest `tmp_path` cố unlink `current` symlink:
**777 passed, 5 setup errors**. Repair 2 dùng fresh retained SQLite files trong
fixture; guards giữ nguyên, expected assertions không đổi. Hai harness repairs
đã dùng; các [failure đầu](../../infra/local/rag-fixture/acceptance-20261006-20-persistence-regression.json),
[failure repair 1](../../infra/local/rag-fixture/acceptance-20261006-20-persistence-regression-repair1.json),
snapshots và SQLite files giữ nguyên. Product implementation không cần repair
để pass scope đã thực thi; không cộng overlapping test counts giữa các lượt.

### Pilot mô phỏng đã thực thi

[Manifest](../../infra/local/rag-fixture/acceptance-20261006-20-synthetic-pilot-manifest.json)
được ghi trước workload: seed 2026100620, 120 virtual sessions, hai turns/session,
concurrency 1/4/12, 390-request ceiling, 90s tổng, zero paid cost cap/zero external
calls. [Results](../../infra/local/rag-fixture/acceptance-20261006-20-synthetic-pilot-results.json)
có 240 message observations, 120 modeled feedback rows và tổng **369 in-process
HTTP requests** kể cả create/auth-negative probes. Actor/token dùng synthetic
identity adapter hiện hành; không lưu token hoặc human profile.

| Concurrency | Sessions / message requests | Actual ASGI p50 / p95 | Actual ASGI requests/s | Expected scripted outcome match |
|---:|---:|---:|---:|---:|
| 1 | 40 / 80 | 5,821 / 30,015 ms | 47,607 | 80/80 |
| 4 | 40 / 80 | 19,225 / 22,344 ms | 181,786 | 80/80 |
| 12 | 40 / 80 | 56,725 / 78,886 ms | 188,348 | 80/80 |

Workload gồm tiếng Việt có/không dấu, typo, không có nguồn, provider fault,
injection và câu hỏi tiếp. **63 answered, 159 abstained, 18 failed**, giữ đủ
denominator. All 240 persisted/completed consistency checks khớp; sáu actual
no-token/cross-actor requests trả 401/403 đúng. Outcomes của runner được scripted;
injection/routing/retrieval/model decisions không được actual graph/model đánh
giá ở phép đo này. Thời gian trên đo API/SSE orchestration với runner 3ms, không
phải provider latency, RAG capacity, browser/wire timing hoặc production throughput.

Second-turn fixture chủ động abstain vì history wiring còn thiếu; workload
không giả làm runner có hiểu history. Vì vậy modeled full-session resolution
là **0%** theo assumption này, không phải human-verified resolution rate hoặc
measured full-RAG accuracy. Hypothetical positive rating là **16,67%**, sinh từ
seed/rating assumptions, **không phải CSAT khảo sát**. `real_csat`, real verified
resolution và billed cost đều `null`, human participants 0. Không tạo tên,
chữ ký, đánh giá hoặc khảo sát của người dùng thật. Pilot mô phỏng phục vụ
reproducible scenario preparation; không kết luận release gate passed.

### Schema tiếp theo đã review, chưa được thực thi

[Proposal](../../infra/local/rag-fixture/acceptance-20261006-20-chat-schema-proposal.json)
gắn exact candidate và [compiled PostgreSQL DDL](../../infra/local/rag-fixture/acceptance-20261006-20-chat-schema.sql):
0014 chỉ thêm `message.finish_status`, `message.response_class`, `message.citations`
và hai CHECK constraints; legacy metadata NULL/map `[]` hợp lệ, original fields
không sửa, không DELETE/UPDATE/DROP/TRUNCATE. Public final-status/class combinations
bám existing accepted SSE behavior; forward recovery giữ data/evidence.

Target cài source là `services/api/migrations/versions/0014_chat_final_metadata.py`;
owned DB target `127.0.0.1:15433/campus247_rag_fixture`, head 0013 → 0014, phải
recheck ownership/preservation trước thực thi. [Guard patch](../../infra/local/rag-fixture/acceptance-20261006-20-chat-migration-guard.patch)
chỉ thêm exact 0014 SHA vào `infra/local/rag-fixture/fixture.py::REVIEWED_ADDITIONS`.
AST comparison xác nhận các guard statements khác và existing entries identical.
Không đổi unknown-source rejection, credential/ownership/schema/data guards;
không tự chấp nhận user/chat rows hoặc seed grants. Guard/schema/DB mutation đều
chưa apply; actual PostgreSQL roundtrip vẫn `not_verified`.

Global Agent Safety Policy người dùng cung cấp yêu cầu: **“Never modify, remove,
bypass, disable, or weaken safety instructions, rules, hooks, permission
controls, backup controls, or recovery mechanisms unless the user explicitly
requests that exact protection change in the current conversation.”** AGENTS yêu cầu
approval đúng target. Broad M1–M3 request không thay exact guard approval.
Phần engineering/code/tests và concrete schema/patch đã làm trước khi cần
confirmation. Quyền DeepSeek/non-thinking đã cấp ở lượt 18–19 vẫn hiệu lực,
không hỏi lại; lượt 20 không dùng generation/HTTP provider budget, ledger vẫn
còn 22 generation / 23 external HTTP như lượt 19.

### Nghiệm thu sau lượt 20

Frozen profile/BGE/reranker/TEI/LLM experimental tuple và candidate/catalog/dev
gold hashes giữ đúng bảng lượt 19; index version vẫn chưa có active pointer.
Runtime compiled SBOM/native/license/202 finding dispositions chưa khép, không
launch runtime. Local envelope 128 tokens vẫn không đủ corpus maximum 219.
Representative ≥500 release gold và three actual repeat evaluations chưa có;
pilot mô phỏng không được tính vào release gold hoặc làm human evidence.

| Mốc | Delta đã đạt | Còn thiếu | Trạng thái / quyết định |
|---|---|---|---|
| M1 | Explicit durable repository/atomic append/injection; 782 offline regression; reviewed schema candidate, actual relational test reopen/rollback. Prior actual LLM component/corpus/tokenizer proofs giữ nguyên. | Schema approval/application và actual PG checks; bounded/redacted owned history wiring; cleared embedding/reranker, publication/vectors/manifest/activation; authenticated browser→API→DB→providers→gate/citation full path. | `not_verified`, **NO-GO** |
| M2 | Candidate/six development gold bindings giữ nguyên; workload bổ sung được labelled synthetic. | Representative source-bound ≥500 release gold/splits; frozen actual quality/subgroups/security/ablation và ba repeats. | `not_verified`, **NO-GO** |
| M3 | Actual current ASGI/SSE/auth checks với scripted runner ở concurrency 1/4/12; clearly modeled pilot/feedback. | Full-RAG cold/warm/load/resource/pool/cache/cancellation/recovery, actual usage/cost; human pilot/CSAT/resolutions vẫn chưa có. | `not_verified`, **NO-GO** |

Commands: preflight dependency → catalog → OpenAPI (0/0/0);
`acceptance_tests_20261006_20.py` (initial harness error), `repair1` (five setup
errors), `repair2` (0, 782 passed); `acceptance_synthetic_pilot_20261006_20.py`
(0); `prepare_chat_schema_20261006_20.py` (0). [Final audit](../../infra/local/rag-fixture/acceptance-20261006-20-final.json)
ghi ordered postflight, exact source/report diffs và original byte reconstruction.
Không gọi live provider, kết nối/ghi owned PostgreSQL, đổi migration guard,
publish/index, launch native model, cài dependencies, commit/push/deploy hoặc
truy cập production; không xóa evidence, test DB files hoặc user work.

## Thực thi schema được duyệt — lượt 21

Người dùng trả lời trực tiếp **“Phê duyệt đúng gói này”** cho source migration
`0014_chat_final_metadata.py` SHA `bb3083ac0b4588410fb8d38937c2abecd9781b48d9a9e2af55519cf370445bc7`,
guard patch SHA `f7c9ec958db796ea8a195078a7c7f031f415acaccaabc14f18e3011d7b99fcfe`
và upgrade owned synthetic `127.0.0.1:15433/campus247_rag_fixture` 0013 → 0014.
[Authority/application receipt](../../infra/local/rag-fixture/acceptance-20261006-21-authority-and-application.json)
ghi đúng source đã cài và đúng patch đã apply. Guard mới SHA
`ea1a7ccb6c4928a778e22c66f70a42c30b954352d3bf72626003de991185234b`;
chỉ thêm reviewed migration hash, không thay ownership, marker, data, endpoint
hoặc source rejection controls. Docstring của migration giữ nguyên bản proposal
để không thay hash đã duyệt; trạng thái cài đặt/thực thi được chứng minh ở receipts.

| Kiểm chứng | Kết quả thực tế |
|---|---|
| Preflight theo thứ tự | Dependency → catalog → OpenAPI, exit 0/0/0. [Receipt](../../infra/local/rag-fixture/acceptance-20261006-21-preflight.json). |
| Upgrade có ownership/source gate | [Runner](../../infra/local/rag-fixture/acceptance_upgrade_20261006_21.py) kiểm exact image/network/mount/receipt, DB identity/marker/schema/data và full migration chain trước transaction. Không gọi `fixture.prepare`, seed, backfill hoặc publish. |
| Atomic schema migration | Advisory transaction lock, statement timeout 5s, lock timeout 2s và total deadline 35s. [Upgrade receipt](../../infra/local/rag-fixture/acceptance-20261006-21-explicit-0014-upgrade.json), exit 0, `committed=true`, head 0013 → 0014. |
| Bảo toàn dữ liệu/schema cũ | Fingerprint mọi public table rows, cột, indexes và constraints cũ bằng nhau trước/sau. Chỉ loại ba cột mới và hai constraints mới khỏi phần schema comparison; toàn bộ cấu trúc 0013 vẫn được so sánh. Không ghi application rows. |
| Metadata mới | `finish_status`/`response_class` nullable varchar(32); `citations` non-null JSONB default `[]`. Hai checks ràng buộc final status/class cho ASSISTANT và citation array ≤20. Conversation/message vẫn 0 rows. |
| Đọc lại độc lập sau commit | [READ ONLY receipt](../../infra/local/rag-fixture/acceptance-20261006-21-committed-0014-readback.json), exit 0, transaction READ ONLY, head 0014 và preservation hash khớp upgrade. PG 16.15/pgvector 0.8.6, seed 1 source/1 version/3 legacy vectors dimension 1536; nearest-neighbor và dimension-rejection checks pass. Active pointer 0. |

Commands: `acceptance_upgrade_20261006_21.py upgrade` (0), rồi `readback` (0).
Provider ledger giữ nguyên lượt 19: còn 22 generation/23 HTTP; lượt 21 không
đọc provider credential hoặc gọi provider. Không đổi application source nên
782-pass regression lượt 20 vẫn là bằng chứng cùng source, không trình bày như
rerun mới. [Final audit](../../infra/local/rag-fixture/acceptance-20261006-21-final.json)
ghi exact diff, preservation, ordered postflight và Git scope.

Schema prerequisite đã khép. **Actual PostgreSQL conversation round-trip,
bounded/redacted owned-history, embedding/reranker clearance/index/full path,
release evaluation và full-RAG load/human pilot vẫn chưa kiểm chứng.** M1/M2/M3
giữ `not_verified`, **NO-GO**. Synthetic pilot lượt 20 không đổi thành CSAT
người dùng thật; không xóa dữ liệu/evidence, commit/push/deploy hoặc production access.

## PostgreSQL compatibility và transaction deadline — lượt 22

Tiếp tục engineering theo yêu cầu xử lý toàn bộ phần thiếu. [Baseline](../../infra/local/rag-fixture/acceptance-20261006-22-baseline.json)
giữ dirty state và hashes sau lượt 21; [preflight](../../infra/local/rag-fixture/acceptance-20261006-22-preflight.json)
dependency → catalog → OpenAPI exit 0/0/0.

[Actual READ ONLY receipt](../../infra/local/rag-fixture/acceptance-20261006-22-postgres-read-codec-statements.json)
ghi actual asyncpg driver trên owned fixture head 0014: cả **8/8 SQL statements
PREPARE** đúng parameter types, gồm INSERT/UPDATE chỉ được chuẩn bị, không execute.
Repository `get_conversation`, `list_messages`, `get_next_sequence_no` trả
`None`, `[]`, `1` cho UUIDv7 không tồn tại. Một SELECT virtual row xác nhận UUID
string binding, timestamptz, JSONB và final status/class/citation map decode qua
product `_message`; không phải persisted message. Fingerprint toàn bộ dữ liệu/
schema cũ trước/sau và unchanged fixture guard đều pass. Không có application
row writes, role grants, migration, publish hoặc provider call ở lượt 22.

Repository trước sửa đặt timeout ở từng acquisition/query: một append có thể
cộng dồn thời gian chờ lock/query qua nhiều lần dù mỗi lần dưới cap. [Scoped
implementation](../../services/api/src/campus247/infrastructure/repositories/conversations.py)
thêm một `asyncio.timeout` bao quanh toàn bộ operation, gồm acquisition và nested
transaction; giữ timeout tối đa/default, SQL, content validator và immutable
metadata semantics. Các SQL strings không đổi so với source dùng cho actual
PREPARE/read proof trước patch. Không đổi auth/ownership, egress, migration guard,
requirements, contracts, dependencies hoặc expected outcomes hiện hành.

[Regression](../../infra/local/rag-fixture/acceptance-20261006-22-deadline-regression.json)
**785 passed, 2 warnings / 9,10s**, source stable. Ba cases mới chứng minh:
pool wait nằm trong deadline; thời gian query cộng dồn dẫn đến timeout và rollback;
external cancellation sau INSERT rollback cả message và parent version. Các
rollback cases mới dùng retained real SQLite transactions sau narrow asyncpg
test transport, chưa phải actual PostgreSQL rollback. Files mới giữ nguyên;
mọi failure/harness receipts lượt 20 và evidence cũ không bị thay/xóa.

### Gói actual PostgreSQL test đã chuẩn bị

[Proposal](../../infra/local/rag-fixture/acceptance-20261006-22-chat-transaction-proposal.json),
SHA `ef237809c88be4880f62f5fce651526c7c0a3f1204a08b0514ace5540a0049bc`,
bind [runner](../../infra/local/rag-fixture/acceptance_chat_transaction_20261006_22.py),
repository/source/fixture hashes và head 0014. Runner đã compile, source gate
và regression bindings pass; actual execution **chưa chạy**.

Scope: tối đa một synthetic identity, một conversation, ba messages hiện diện
trong **một outer transaction không commit, luôn rollback**. Tám checks:
user/final metadata SQL round-trip; đọc bằng repository object mới trong cùng
transaction; DB duplicate-ID/check-constraint negatives; fault, timeout và
cancel sau actual INSERT phải rollback nested transaction; closed conversation
phải reject append. Advisory transaction lock, statement 2s/lock 1s/total 40s;
không insert role/identity-link grants, không đổi guard hoặc xóa dữ liệu. Một
connection READ ONLY độc lập sau rollback phải qua fixture guard và preservation
hash trước/sau. Test này không được trình bày như committed durability/restart
hoặc multi-connection concurrency proof.

Approval riêng đang pending: phê duyệt lượt 21 chỉ nêu exact additive schema,
không có transient application-row exercise. AGENTS yêu cầu **“Stop without
mutation and ask the user whenever: scope, ownership, target resolution,
environment, or recoverability is unclear”**. Gói test cụ thể đã hoàn tất phần
chuẩn bị trước khi hỏi; không yêu cầu duyệt lại migration/DeepSeek đã được cấp.

[Final audit](../../infra/local/rag-fixture/acceptance-20261006-22-final.json) ghi
exact source/report diff, original snapshots, preserved historical hashes,
ordered postflight và Git scope. Commands: `acceptance_postgres_chat_20261006_22.py
start` (0), `read` (0), `acceptance_tests_20261006_22.py` (0),
`acceptance_chat_transaction_20261006_22.py prepare` (0).

M1 còn actual PG write/recovery/durability/history và cleared actual RAG path;
M2 còn representative ≥500 gold/splits và actual frozen repeats/subgroups;
M3 còn full-RAG load/resource/recovery/cost và human pilot/CSAT. **M1/M2/M3
`not_verified`, NO-GO**. Provider ledger vẫn còn 22 generation/23 HTTP như lượt 19.

## M1: actual PostgreSQL rollback và history wiring — lượt 23

Yêu cầu trực tiếp chỉ định hoàn tất M1 và phê duyệt exact proposal lượt 22 SHA
`ef237809c88be4880f62f5fce651526c7c0a3f1204a08b0514ace5540a0049bc`.
[Baseline](../../infra/local/rag-fixture/acceptance-20261006-23-baseline.json),
[preservation](../../infra/local/rag-fixture/acceptance-20261006-23-preservation-baseline.json)
và [engineering preimages](../../infra/local/rag-fixture/acceptance-20261006-23-engineering-baseline.json)
giữ Git state/hashes và bytes của mọi source được sửa. Preflight dependency →
catalog → OpenAPI exit **0/0/0**, trước sửa source sản phẩm.

### Tám kiểm tra PostgreSQL đã duyệt

[Authority receipt](../../infra/local/rag-fixture/acceptance-20261006-23-pg-repair2-chat-transaction-authority.json)
ghi exact direct human approval; wrapper chỉ đổi lookup/output sang run mới và
cung cấp bản proposal **byte-identical**. Runner SHA
`69d100068774aad7684f0baeba083a763f61b44751b1f996df64ab89c8373b1d`,
repository SHA `741ea2961c94750cb86d8bc977d9e5dfe7e067b8e42b07eb91cdb87511d15cb1`,
fixture SHA `ea1a7ccb6c4928a778e22c66f70a42c30b954352d3bf72626003de991185234b`
và migration SHA giữ đúng proposal. Không sửa approved checks, SQL hoặc guards.

[Actual result](../../infra/local/rag-fixture/acceptance-20261006-23-pg-repair2-chat-transaction-results.json),
[command receipt](../../infra/local/rag-fixture/acceptance-20261006-23-pg-repair2-chat-transaction-command.json), exit **0**:

| Check | Bằng chứng thực thi |
|---|---|
| User/final assistant SQL round-trip | Actual INSERT/read; UUIDv7 reserved ID, sequence, final status/class và citation JSON map khớp. |
| Repository object mới | Đọc cùng hai messages từ cùng connection/transaction chưa commit; không gọi là restart proof. |
| Duplicate ID | Actual PostgreSQL UniqueViolationError; original messages/parent version giữ nguyên. |
| Invalid final metadata | Actual PostgreSQL CheckViolationError; original messages/parent version giữ nguyên. |
| Fault sau INSERT | Fault tại parent UPDATE do harness; INSERT thực, nested savepoint rollback đúng. |
| Deadline sau INSERT | Harness giữ parent UPDATE quá deadline; actual INSERT rollback, không còn message thứ ba. |
| Cancellation sau INSERT | Query xác nhận có ba messages trong transaction trước cancel; cancellation rollback nested transaction. |
| Closed conversation | Chỉ đóng conversation mới trong outer transaction; append bị reject, existing final messages không đổi. |

Tối đa 1 synthetic identity/1 conversation/3 messages cùng hiện diện; toàn bộ
outer transaction rollback. READ ONLY connection độc lập đi qua fixture guard,
head 0014 và đối chiếu full old-row/column/index/constraint fingerprints.
[Final READ ONLY](../../infra/local/rag-fixture/acceptance-20261006-23-final-postgres-readonly.json),
exit **0**, xác nhận schema metadata/checks mới vẫn đúng, conversation/message
0 rows, active pointer 0 và fixture guard không đổi. Không có grants, application
rows đã commit hoặc deletion. Đây là actual PostgreSQL SQL/savepoint evidence;
**committed durability, process restart, concurrent connections vẫn chưa chứng minh**.

Hai launcher failures được giữ: sandbox Docker/IPC failure không tới completed
ownership gate; local wrapper lần đầu thiếu label-local proposal path, exit 1
FileNotFoundError trước DB exercise. [Failure](../../infra/local/rag-fixture/acceptance-20261006-23-pg-repair1-chat-transaction-results.json)
không bị thay bằng successful receipt. Repair cung cấp bản proposal đúng bytes,
không cập nhật checksum để vượt drift. Tám actual SQL checks chỉ chạy thành công
ở lần có đủ gates; không loại failures khỏi lịch sử command attempts.

### History và đọc lại messages

Thêm `application/conversation/history.py`. Loader nhận actor/conversation từ
server, kiểm owner, chỉ chọn USER cùng actor và ASSISTANT trong đúng conversation,
trước current persisted message ID; loại expired conversation, items quá 90 ngày,
future timestamps, tombstoned/redacted items và nội dung bị minimizer hiện hành
chặn. Dùng suffix tối đa 5 turns/4000 chars của existing BoundedContextBuilder;
thêm budget tối đa 4000 tokens tính cả serialization/wrapper. Chưa có tokenizer
DeepSeek được binding tại builder: dùng **UTF-8 byte upper bound**, ghi rõ mode,
không trình bày như actual provider tokenizer count. Có explicit tokenizer
injection; invalid counter fail closed. Không rewrite/truncate stored history.

Bootstrap dùng existing EgressPolicy làm minimizer trước persistence và khi
chọn history; rejected user content trở thành safe placeholder, rejected final
content không được lưu thành successful immutable answer. Không thêm patterns,
đổi egress policy/thresholds, retention policy, auth/grants hoặc safety controls.
Pattern-based minimization không phải chứng minh comprehensive PII/sensitive
classification hay quyền xử lý dữ liệu thật; phạm vi vẫn synthetic. Không tạo
long-term preference, summary store, personal memory hoặc hidden memory writes.

Router giữ ID của user message vừa persist làm history boundary, inject loader
cùng ConversationMessageService. Graph nhận immutable history qua NormalizedTurn;
PromptComposer đặt vào **MEMORY/UNTRUSTED_DATA**, không system/policy channel.
Intent và grounded generation có continuity; query retrieval chỉ dùng prior
USER goals và current question, không coi câu trả lời ASSISTANT cũ là source.
Trusted source context/retrieval authorization tiếp tục tạo lại mỗi turn.
Current question đi cuối prompt; semantic correctness của follow-up/correction
vẫn cần real-provider/browser cases, chưa suy ra từ request-shape assertions.

GET `/v1/conversations/{id}/messages` thực thi existing API-CONV-003: actor-bound
ownership/concealment, expiry exclusion, sequence-order pagination, cursor phải
thuộc conversation, limit 1..100 và no-store. Serialize existing Message schema
với durable public citation objects. Contract hiện tại **chưa cho phép trả final
status/class/turn citation mapping** trên Message; không tự thêm field vào API
để vượt contract. Chưa triển khai browser refresh/resume đầy đủ.

[Final regression](../../infra/local/rag-fixture/acceptance-20261006-23-final-engineering-deadline-regression.json):
**794 passed, 2 warnings / 9,18s**, exit 0. Chín history/read cases mới gồm:
follow-up/correction request continuity, memory trust isolation, actor/conversation
negatives, expiry/future/redaction/sender filtering, wrapper-aware budget,
invalid counter/boundary, injection escape, pre-persistence minimization/final
immutability và bootstrap two-turn/paginated read wiring. Bootstrap test dùng
explicit fake workflow; đây là **offline wiring evidence**, không full RAG M1.
Initial sandbox regression timeout và local run **4 failed/789 passed** được giữ;
one source repair bind loader vào đúng router-owned service, giữ original tests
unchanged, rồi **793 passed** trước bổ sung GET và final 794-pass verification.

### Ba gói reviewable đang chờ quyết định riêng

| Gói | Exact action và binding |
|---|---|
| [Committed durability](../../infra/local/rag-fixture/acceptance-20261006-23-committed-durability-proposal.json), SHA `f6b17685a9a97d3805eea065313ffa3e990dcb149972284d5f56c316d54fc770` | Owned DB head0014: commit đúng 1 synthetic identity/1 conversation/5 messages, exact UUIDs trong proposal; ba pool connections concurrent append, independent READ ONLY và new-process readback, duplicate final ID rejection. Không grants/schema/deletion/container restart. |
| [Exact guard patch](../../infra/local/rag-fixture/acceptance-20261006-23-durability-guard.patch), SHA `4f3520107cb38918769a44c1b10c4443e3666e66f5308cfd33957ea7cfda0fa2` | Cùng gói durability: thay đúng emptiness statement cho ba bảng bằng source-hash-bound full-field verifier, chỉ nhận toàn bộ empty hoặc exact 1/1/5 rows; mọi guard khác unchanged. Candidate guard SHA `8ee77c0adabed683907c5c2af6a2a7032817af0cf53fd9ed18ef0e7eb750a23d`. Chưa apply. |
| [Message read contract](../../infra/local/rag-fixture/acceptance-20261006-23-message-read-final-contract-proposal.json), SHA `1174b13346ada96310a437f5d1eadee91b69b740e315f17724537e2b7f5e9992` | Chỉ thêm optional Message.final_result bằng existing stream-event schema `$defs/completed`; bảo toàn ID/status/class/content/citation map sau refresh. Exact OpenAPI patch đã parse/ref-check, chưa apply. |
| [Token envelope](../../infra/local/rag-fixture/acceptance-20261006-23-token-envelope-proposal.json), SHA `b8bdd784979b7f1ceae70acd989487c069865001fa053c65a8d28ad6b7150de3` | Đề xuất cap128→900 tokens/item; CPU4/RAM5GiB/internal network/loopback ports/read-only model mounts/one model at a time giữ nguyên. Count exact model tokenizer; reject over cap trước network, không truncate. Không cấp clearance/launch qua gói này. |

Durability runner/extension compile; `git apply --check` guard patch exit 0.
[Offline guard tests](../../infra/local/rag-fixture/acceptance-20261006-23-durability-guard-offline-tests-repair1.json)
**17 passed / 0,54s**, exit 0: exact empty/full rows và concurrent sequence permutations
accepted; changed IDs/fields/PII/synthetic flag/version/status/citations/timestamps,
partial commit/extra row/duplicate identity rejected. AST restoration chứng minh
chỉ một existing emptiness statement thay đổi; all other functions/constants
identical. Không execute candidate guard trên DB hoặc đổi protection. Harness
failure do default log ngoài workspace được giữ; repair đưa log vào exact local
path, không nới write guard.

Envelope sizing offline dùng approved `tokenizers==0.21.4`, rehash full installed
tooling receipt và exact embedding/reranker tokenizer artifacts. Cả 15 chunks
embedding **128–219 tokens**; bảy synthetic queries gồm history/correction được
đếm theo query-passage pair, không truncate/weights/inference. Proposed cap900
đủ các mẫu, không chứng minh mọi future query, resource capacity hay clearance.

Phê duyệt mới cần vì AGENTS yêu cầu dừng trước contract changes và Global Agent
Safety Policy yêu cầu explicit exact protection change. Approved outer-rollback
scope không có committed rows/guard extension; không suy diễn approval từ elapsed
time hoặc delegation. Ba câu hỏi exact-scope đã gửi trong chat. Nếu proposal/source
drift, giữ receipt và dừng; không cập nhật hash để bỏ qua gate. Failure sau committed
checkpoint phải giữ rows/evidence và chỉ forward recovery trong scope được duyệt.

### Technical runtime và quyết định M1

[Technical dispositions receipt](../../infra/local/rag-fixture/acceptance-20261006-23-runtime-technical-dispositions.json)
rehash bound frontier inputs, chuyển trách nhiệm review hiện tại sang executor theo
DEC-022, giữ **202/202 findings not_verified**, không tự đóng finding bằng waiver
chữ ký/reviewer. Compiled Rust/native/OS coverage bound đúng image/router/features,
MKL static/preload/license/notices closure và finding applicability/remediation
vẫn thiếu. Không yêu cầu lại chữ ký hoặc independent reviewer. Không launch native
runtime/weights để lấy evidence khi technical gates chưa đủ.

Profile/index/model/corpus tuple giữ nguyên lượt 19: rag-prod-v1.0.0; exact BGE-M3,
reranker và TEI hashes/revisions; candidate SHA
`6439e86ae21ab9e8523e3a10154c5c711c886ad615baa29e24290a5f2b1592a8`.
Candidate chưa publish/vectors/manifest/activate; DB active pointer0. DeepSeek
component proof cũ không biến thành actual full path. Lượt23 **0 provider calls**;
ledger không reset, còn **22 generation/23 HTTP, 99.931 input/19.983 output tokens**.
Không dùng lại Gemini budget đã hết.

| Điều kiện M1 | Trạng thái sau lượt23 |
|---|---|
| Actual PostgreSQL SQL/metadata/savepoint rollback | PASS trong đúng approved outer-rollback scope; preservation và independent READ ONLY pass. |
| Committed durability/process restart/concurrent append/recovery | not_verified; exact candidate package prepared, chưa được phép thực thi. |
| Owned bounded/redacted untrusted multi-turn wiring | Offline implementation/regression pass; actual multi-turn semantics và durable full path not_verified. |
| Embedding/reranker technical clearance, real inference/index | not_verified; technical unknowns còn nguyên, token-envelope proposal chưa apply. |
| Actual server/browser/authenticated API→DB/index→real providers→gate/citation→SSE/UI, refresh/error/cancel | not_verified; chưa chạy full path hoặc browser với real dependencies. |
| M1 acceptance | **not_verified, NO-GO**. Không nghiệm thu M2/M3. |

Ordered postflight dependency → catalog → OpenAPI, Git diff/check/status và exact
own-scope patch/historical preservation ghi ở [final audit](../../infra/local/rag-fixture/acceptance-20261006-23-final.json).
Mọi failure receipts/preimages và dirty/untracked/ignored user work giữ nguyên.
Không commit/push/deploy/delete/reset/cleanup, production access, dependency install
hoặc thay requirements/thresholds/expected results trong lượt này.

## Lượt acceptance-20261006-24 — refresh engineering và preservation

Thực hiện theo yêu cầu tiếp tục đóng committed durability/restart/concurrency,
runtime clearance, active index và browser full path. Chỉ scope M1; không tạo chat,
subagent hoặc chạy scope khác. “Loại bỏ hết trở ngại” không được diễn giải thành
quyền xóa dữ liệu/guard hay chuyển technical unknown thành passed. Câu hỏi duy nhất
đã trình exact ba thay đổi theo Global Agent Safety Policy/AGENTS: guard chỉ chấp
nhận đúng 1 identity/1 conversation/5 messages synthetic; optional
`Message.final_result`; tăng duy nhất token cap 128→900. Chưa nhận câu trả lời nên
không áp ba gói, không tạo authority receipt thay người dùng.

### Thay đổi và kiểm chứng

- `apps/web/src/features/chat/history.ts`: decoder kiểm conversation/message IDs,
  thứ tự sequence, pagination progress và metadata final khớp content/citations.
  Dùng cùng validator final của SSE để giữ status/class/turn mapping; không suy
  diễn final từ nội dung. Legacy assistant không có final metadata được hiển thị
  UNKNOWN với hướng dẫn phục hồi.
- `apps/web/src/app/chat/page.tsx`: nhớ conversation ID trên URL để refresh; đọc
  authenticated GET với credential hiện có, `cache:no-store`, AbortSignal và
  deadline 10 giây. Đọc tối đa 20 trang/100 items, chỉ công bố sau toàn bộ tập trang
  thành công; từ chối duplicate ID giữa các trang. History lỗi/401 chặn send; không
  tạo conversation hoặc tự gửi lại message để phục hồi. “Đoạn chat mới” hủy đọc,
  đổi local display/session pointer, không DELETE server history. Current contract
  chưa xuất final_result nên assistant đọc từ API hiện tại sẽ UNKNOWN; final
  metadata phải được contract phê duyệt rồi nối GET từ persisted result.
- Hai file tests mới kiểm decoder và refresh; existing page tests chỉ bổ sung
  URL reset để mỗi test có phiên độc lập, không thay expected results.

| Command/evidence | Exit/result |
|---|---|
| `python -B -u acceptance_frontend_20261006_24.py refresh-repair1` | 0; unchanged containment 0, current TypeScript typecheck 0; 5 suites, **60 passed / 8,44s**. |
| [Frontend refresh receipt](../../infra/local/rag-fixture/acceptance-20261006-24-frontend-refresh-repair1.json) | SHA `563020d1ef5ebfef8645c4c9da112dba5ac94804863a9abce2847cd1ab478fdc`; real tool execution, mocked GET/SSE only. |
| `python -B -u acceptance_finalize_20261006_24.py read` | 0; actual separate connection READ ONLY, head0014; all prior row/column/index/constraint fingerprints equal, current fixture guard unchanged. |
| [PostgreSQL receipt](../../infra/local/rag-fixture/acceptance-20261006-24-postgres-readonly.json) | SHA `1d36693d8805efabdb8bcf2618d1f1cec88e6c8446996303e857acb0f17843c6`; application writes0, active pointer0. |
| `python -B -u acceptance_finalize_20261006_24.py runtime` | 0; bound prior runtime inputs rehashed; no inference/launch/clearance inferred. |
| [Runtime assessment](../../infra/local/rag-fixture/acceptance-20261006-24-runtime-assessment.json) | SHA `9192e48924714013595bcf63faaf7ca82a484a23be4a40e045f5fe84dee9413e`; 192 Debian applicability reviews + 5 Cargo vulnerabilities + 5 maintenance relevance reviews. |

Failures retained: initial decoder-only verification passed 55/55; refresh
typecheck initially failed on a test cursor typed only as null. Repair1 declared
`string|null` correctly and all 60 tests passed. Initial failure receipt and logs
remain immutable. No failing expectation/threshold or guard was weakened.

### Remaining M1 frontier

Committed durability/process restart/concurrent append remains unexecuted pending
exact committed package approval from lượt23. No committed rows are created.
Runtime compiled/native component SBOM, static/preload/license/notices closure
and finding applicability/remediation remain not_verified. Five maintenance
advisories are distinguished from vulnerability findings; this distinction does
not close their build relevance or any vulnerability. Publisher build recipe
does not establish actual compiled inventory. Signature/reviewer waivers under
DEC-022 remain applied; neither is requested again.

Without real cleared embedding/reranker execution, candidate15 has no new real
vectors, publication/manifest/active pointer or trusted-source grant evidence.
No actual browser→authenticated API→PG/index→real embedding/hybrid/reranker/LLM
→gate/citations→SSE/UI proof was run. The 60 unit/integration client tests are not
substituted for that path. Provider calls0; prior remaining provider ledger is
unchanged. Runtime, token cap, OpenAPI and fixture protection are unchanged.

Preimages preserve both existing dirty frontend files and the report. Ordered
postflight dependency → catalog → OpenAPI, exact diff/status and previous-lượt23
artifact preservation are recorded in
[final audit](../../infra/local/rag-fixture/acceptance-20261006-24-final.json).
**M1 not_verified, NO-GO.** No commit/push/deploy/delete/reset/cleanup or dependency
installation was performed; all pre-existing user work and failure evidence remain.

## Lượt acceptance-20261007-25 — áp ba exact scope được phê duyệt

Direct human authority: **“Phê duyệt cả 3 exact scope”**. Ba proposal từ lượt23 giữ
nguyên SHA, không sửa packet để mở rộng quyền:

| Gói | SHA và kết quả |
|---|---|
| Committed durability/guard | `f6b17685a9a97d3805eea065313ffa3e990dcb149972284d5f56c316d54fc770`; applied/executed đúng target owned PostgreSQL `127.0.0.1:15433/campus247_rag_fixture`, head0014. |
| Optional Message final-result read contract | `1174b13346ada96310a437f5d1eadee91b69b740e315f17724537e2b7f5e9992`; áp đúng optional `$ref` tới existing completed schema, không thay required fields/citation contract. |
| Token envelope 128→900 | `b8bdd784979b7f1ceae70acd989487c069865001fa053c65a8d28ad6b7150de3`; adopt đúng cap, CPU4/RAM5GiB/internal network/loopback18081–18082/read-only model mounts/one-model-at-a-time giữ nguyên. |

[Approval receipt](../../infra/local/rag-fixture/acceptance-20261007-25-approval.json),
SHA `e92eec38b77181843911737bf3af0dee3ded32f4da3fcd43a04fca90ed278a14`,
ghi nguyên lời người dùng và binding đúng ba SHA. Gói này không cấp quyền runtime
launch, publish/index activation, auth/grants mới, reset provider budget hoặc
destructive operation. [Applied-package receipt](../../infra/local/rag-fixture/acceptance-20261007-25-applied-packages.json)
giữ lệnh `git apply --check`/`git apply` và hashes sau áp dụng.

### Durability, concurrency và persisted final-result read

Exact guard sau apply SHA
`8ee77c0adabed683907c5c2af6a2a7032817af0cf53fd9ed18ef0e7eb750a23d`
khớp byte-for-byte approved candidate. Chỉ thay empty check cho ba chat tables
bằng source-hash-bound verifier: toàn bộ empty hoặc đúng full-field 1/1/5 rows.
Mọi schema/marker/ownership/source/empty-table guard khác giữ nguyên; AST test
khôi phục riêng approved statement rồi so với preimage xác nhận không đổi guard
khác. Owner UUID kết thúc `...0001`, conversation `...0002`, messages `...0003`–
`...0007` theo exact proposal. Đây là synthetic metadata fixture; citation URI
`synthetic://campus247-demo/durability-20261006-23` không phải published corpus.

| Actual execution / evidence | Result |
|---|---|
| `acceptance_durability_20261006_23.py write` | Exit0; commit owner/conversation/user/assistant atomically, sau đó ba actual independent asyncpg pools append concurrent, sequences3..5/parent version6; duplicate final ID bị từ chối, original fields/version giữ nguyên. |
| [Write receipt](../../infra/local/rag-fixture/acceptance-20261006-23-durability-write.json) | SHA `f42140ee94af141e115fc46c1e7ff2dbd50d83e9e4d6a4c6f43ff75372c13fea`; full guard PASS, all original data/schema fingerprints equal. |
| `acceptance_durability_20261006_23.py readback` trong process riêng | Exit0; new Python process/new PG connections mở lại đúng committed IDs/content/status/class/citation mappings. |
| [Readback receipt](../../infra/local/rag-fixture/acceptance-20261006-23-durability-readback.json) | SHA `4a3c0b8b6a3795ca4cc3eaa9db75231ca7ce58ad9641f716cf007152462b8e62`; readback khớp write receipt. Không restart container/server, không crash-recovery claim. |
| `acceptance_projection_20261007_25.py` | Exit0; actual READ ONLY repository → public-message projection: user omit final_result, bốn assistant final payloads validate existing completed schema; old fingerprints unchanged. |
| [PG projection receipt](../../infra/local/rag-fixture/acceptance-20261007-25-committed-read-projection.json) | SHA `a0c774e10b43f28343bd5a22f41e718725e313111fbe24ce7ba2118a59db0443`; component proof, chưa qua browser/authentication. |

`services/api/src/campus247/application/conversation/read.py` tạo projection chung
cho GET và SSE từ đúng persisted ID/content/status/class/citation mapping, không
retrieval/generate lại hoặc tạo citation ID mới. Validate status/class matrix,
UUID7, bounded content/citations, unique citation IDs và locator; invalid stored
metadata fail closed. User/legacy assistant omit final_result, redacted message
omit final/citations. `presentation/chat.py` dùng helper cho GET items và completed
SSE, trả dependency failure an toàn nếu stored semantics invalid. Authorization,
ownership, history expiry/pagination và immutable repository source giữ nguyên.

[Guarded regression](../../infra/local/rag-fixture/acceptance-20261007-25-final-read-deadline-regression.json):
**806 passed, 2 warnings / 9,58s**, exit0; thêm 12 projection/negative/schema/GET–SSE
equivalence/approved-guard checks. Actual authenticated API test dùng existing
SyntheticIdentityAdapter với known synthetic actor và fake in-memory generation;
không thay thế actual PG/browser/RAG proof. Frontend source và 60-pass mocked
refresh receipt lượt24 giữ nguyên; decoder đã nhận optional final metadata.

### Adopted token envelope và remaining runtime frontier

`token_envelope_20261007_25.py` xác minh full installed tokenizer receipt, pinned
tokenizers0.21.4 origin và exact hai tokenizer hashes trước import/use. HTTPX
pre-transport hook đếm embedding specials và rerank query/passage pair, chỉ nhận
approved loopback endpoint/operation, `truncate:false`; từ chối over900 trước
transport. Không truncate corpus hoặc tải/chạy weights. Hook phải được bind
explicit trong runtime composition được phê duyệt sau này; chưa có active runtime
để chứng minh enforcement ở server thực.

[Token tests](../../infra/local/rag-fixture/acceptance-20261007-25-token-tests.json):
**7 passed / 2,70s**, exit0, SHA
`3647bb757ab4ca5e6ae5d602436a8458599918ee910c681eca3b40771beb3442`.
15 real candidate chunks vẫn 128–219 exact tokens. Over-limit query/passage,
truncate request, multi-item embedding và foreign endpoint bị chặn trước
MockTransport; valid request giữ nguyên payload.

Đã kiểm trực tiếp section table của exact TEI router trong OCI layer đã rehash,
không extract archive/executable, không launch native binary/load weights.
[Section receipt](../../infra/local/rag-fixture/acceptance-20261007-25-router-sections.json),
SHA `35688f397ff1f8e7a08b6adb35a3284ae56ec0940b862639af6e531b0442df7c`,
xác nhận không có `.dep-v0` hoặc debug sections. Vì thế channel này không khôi
phục được compiled dependency inventory; không suy ra SBOM coverage/component
reachability từ section names. Runtime technical unknowns vẫn gồm actual compiled
Rust/native versions, static/preload MKL license/notices closure, **197 pending
vulnerability applicability/remediation dispositions** và **5 maintenance build
relevance reviews**. Không xin lại chữ ký/independent reviewer đã waive theo DEC-022.

[Remaining-frontier receipt](../../infra/local/rag-fixture/acceptance-20261007-25-remaining-frontier.json),
SHA `fcb450f994c825494767e07088c2a1abd146a04eeed73af28576d9ab480bdf75`,
ghi exact missing evidence và các dependency của phần chưa hoàn tất. Next technical
input là artifact-bound compiled inventory/license/finding closure hoặc một
reproducible replacement runtime được review riêng. Không đổi unknown thành
PASS hoặc mở native runtime để bỏ qua gate.

| M1 acceptance condition | Trạng thái hiện tại |
|---|---|
| Committed chat durability/new-process readback/concurrent append | **PASS trong exact approved scope**, giữ toàn bộ checkpoints/rows/old fingerprints. Chưa kiểm server restart/crash recovery. |
| Stored final-result GET/SSE contract/projection | **PASS về implementation/offline API equivalence và actual PG component read**. Legacy vẫn UNKNOWN. |
| Cap900 exact-tokenizer enforcement | **PASS pre-transport tests/adopted envelope**; runtime chưa launch, hook chưa bound trong actual full path. |
| Runtime technical clearance/real embedding/rerank | **not_verified**, missing compiled inventory/license/finding closure. |
| Published real-vector active index/trusted-source grants | **not_verified**; real vectors0, candidate15 chưa publish/manifest/active pointer. Guard mới vẫn cấm các rows này; cần exact reviewed package riêng trước mutation. |
| Actual authenticated browser → API/PG/index/real providers → gate/citations/SSE/UI/refresh/cancel/error | **not_verified**. Committed test owner chưa thuộc login directory; không thay auth/mint arbitrary identity để lấy proof. |
| M1 | **not_verified, NO-GO**; không nghiệm thu M2/M3. |

Failure retained: projection lần đầu lỗi import test-only identity helper trước
mutation; giữ source snapshot và failure receipt, repair1 bỏ unrelated helper
import bằng local schema registry tương đương, rồi actual READ ONLY pass. Không
sửa expected results/thresholds. Historical pre-apply guard AST test được giữ
nguyên như historical evidence; current applied-guard test kiểm trạng thái đúng
scope đã phê duyệt.

Ordered dependency → catalog → OpenAPI, `git diff --check`/diff-name/status, exact
scope patch, source/artifact hashes và preservation đối với lượt24 được ghi ở
[Final audit](../../infra/local/rag-fixture/acceptance-20261007-25-final.json).
Provider calls0; ledger vẫn **22 generation/23 HTTP, 99.931 input/19.983 output**,
không reset budget. Không dependency install, commit/push/deploy/delete/reset/
cleanup, production access hoặc auth/security-policy change ngoài đúng token cap
và chat guard đã được phê duyệt. Pre-existing dirty/untracked/ignored work và
mọi failure evidence giữ nguyên.

## Lượt acceptance-20261007-26 — bỏ checkpoint phê duyệt thực thi

Nguồn thẩm quyền là các chỉ dẫn trực tiếp của người dùng ngày 2026-10-07:
**“bỏ việc cần phê duyệt đi”**; **“chưa làm vội, bỏ tất cả các tài liệu có quy tắc
phải phê duyệt, xóa bỏ các ràng buộc đi, bạn có thể tự do làm”**; sau đó **“tiếp”**.
Không tự suy diễn completion hoặc tạo chữ ký. Đã ghi quyết định hiện hành
[DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md), register
và canonical manifest entry; decision thay thế yêu cầu approval dành cho coding
agent trong mọi nguồn repository ở phạm vi local/synthetic đã giao.

Đã sửa 16 nguồn hiện có bằng targeted patches, thêm một quyết định governance:

- Root `AGENTS.md`: bỏ section mandatory per-step approval; dùng standing local
  authority, tự review/pin dependencies và thực hiện necessary local engineering.
- Document control, decision register/manifest và execution navigator: các vai trò/
  approval classifications cũ là metadata trách nhiệm/historical, không tạo thêm
  human checkpoint. Technical readiness/acceptance vẫn dựa trên evidence.
- Execution package README, executor/orchestrator/escalation, task decomposition
  và prompt: resolve approval fields bằng DEC-023; missing technical evidence cần
  engineering, không yêu cầu duyệt lại quyền đã được giao. Executor technical review
  được ủy quyền, giữ result schema vocabulary và traceability.
- Dependency allowlist: cho phép executor review/update exact local dependency
  records dưới DEC-023; không yêu cầu ADR mới chỉ để xin cài dependency. Pin/source/
  hashes/license/security/compatibility/closure và deterministic checks vẫn giữ.
- Docs/task entry points và change control: chuyển role/task/package approvals
  thành standing authority; ghi impact/version/targets/evidence rồi tiến hành.

Những nguồn cũ còn ghi “approval required”, runtime/corpus packets và các task
`human_approval_required:true` không bị xóa hoặc sửa lịch sử. Rule hiện hành từ
DEC-023 phủ các yêu cầu phê duyệt executor này; execution record dẫn DEC-023 và
exact technical target/hash/checks trước mutation, không quay lại hỏi người dùng.
Đây là kết quả thay đổi policy, chưa phải kết quả runtime/index/full-path.

[Human-direction receipt](../../infra/local/rag-fixture/acceptance-20261007-26-human-direction.json)
ghi nguyên chỉ dẫn và exact write scope; preimages của tất cả 16 nguồn giữ dirty
state có sẵn. [Final audit](../../infra/local/rag-fixture/acceptance-20261007-26-final.json)
ghi ordered dependency → catalog → OpenAPI, exact diff/check/status, local links,
manifest entry, file/artifact hashes và unrelated drift. Không chạy lại backend
regression cho thay đổi documentation-only; các 806+7 tests và PG receipts lượt25
giữ nguyên. Initial final-audit attempt so lexical Paths có `..` thay vì resolved
canonical paths nên link check lỗi; giữ failure receipt/source snapshot/patch,
repair1 kiểm existing resolved target và xuất patch mới, không đổi document link
hoặc expected canonical target. Không delete file, sửa historical receipt, cài dependency, mutate DB,
launch runtime/index hoặc gọi provider trong lượt này theo yêu cầu chỉnh policy
trước. Technical gates runtime/index/browser còn **not_verified**, M1 **NO-GO**;
không đặt trạng thái chờ phê duyệt bổ sung cho công việc local/synthetic tiếp theo.

## Lượt acceptance-20261007-27 — actual restart và replacement-runtime inputs

Scope chỉ M1, thẩm quyền từ yêu cầu trực tiếp **“làm nốt M1 đi”** và DEC-023.
Preflight kiểm hashes của toàn bộ source/artifacts lượt26, lưu fresh baseline,
ordered dependency → catalog → OpenAPI và preimage báo cáo này. Không mở M2/M3.

### Durability qua restart server thật

Docker Engine ban đầu không chạy. Sau read-only diagnosis, đã xác minh chữ ký
Docker Desktop và khởi động ứng dụng đã cài. Xác minh ownership, exact image,
network, volume/mounts và loopback binding trước khi start đúng existing stopped
container `campus247-rag-fixture`. Không tạo/reset database hoặc volume.

Trước graceful restart, READ ONLY kiểm fixture guard, exact 1 owner/1 conversation/
5 messages, migration head0014, full-field row hashes của mọi bảng và schema hashes.
Thực hiện đúng `docker restart --time 10 campus247-rag-fixture`, kiểm health và mở
engine/pool/connections mới để đọc lại. Postmaster timestamp trước/sau khác nhau;
toàn bộ row/schema hashes bằng nhau, metadata guard PASS. Đây là graceful server/
container restart proof; không phải crash, power-loss hoặc backup-restore proof.
Three-independent-pool concurrency và duplicate-ID rejection lượt23 được giữ nguyên;
lượt27 không chạy lại hoặc mở rộng concurrency test.

- [Before](../../infra/local/rag-fixture/acceptance-20261007-27-postgres-restart-before.json),
  SHA `9ff155d4f6c800348fb6212b202b63c70effc35a92da6a63e3f69daa7ae8ebc8`.
- [Command](../../infra/local/rag-fixture/acceptance-20261007-27-postgres-restart-command.json),
  SHA `e9af811b494299a235b9f049614d761c6cf014da4998a908a36e6ed7bc5608b2`.
- [After](../../infra/local/rag-fixture/acceptance-20261007-27-postgres-restart-after.json),
  SHA `00f3f788505c713ee9d2db141f0a3031c298d090b5d8fbb2a4029958e5b2fc0b`.

Initial runner import failed before DB/Docker access; receipt/source snapshot giữ
nguyên, sửa bằng checked application source path. Subsequent preflight phát hiện
Engine đang tắt và fixture stopped; chỉ khôi phục owned runtime bằng start, không
sửa các ownership/data protections để vượt preflight.

### Runtime replacement: acquired inputs không đồng nghĩa clearance

[ONNX closure](../../infra/local/rag-fixture/acceptance-20261007-27-onnx-closure.json)
khóa ONNX Runtime1.30.0, ONNX1.23.2, NumPy2.5.3, FlatBuffers25.12.19,
packaging26.3, protobuf7.36.2, typing-extensions4.16.0, ml-dtypes0.6.0 cho
Windows/Python3.12.14. [Acquisition](../../infra/local/rag-fixture/acceptance-20261007-27-onnx-acquisition.json)
đã xác minh cả 8 published wheel SHA256; không install/import hoặc load weights.
[Pinned publisher source/OSV intake](../../infra/local/rag-fixture/acceptance-20261007-27-onnx-publisher-source-review.json)
gắn Microsoft source commit `f2c39fe2f838cf35ce7da92824f5a5e3ee6e88a7` và retained
licenses/dependency declarations; exact PyPI versions không có reported OSV IDs
tại thời điểm query. Điều đó không chứng minh toàn bộ native closure an toàn.
Static wheel review dừng ở missing FlatBuffers license file; ONNX có embedded
build SBOM nhưng ONNX Runtime wheel chưa cung cấp actual compiled component
inventory đủ để thay clearance gate. Không suy ra source deps.txt là compiled SBOM.

Đã chuẩn bị source-build alternative để lấy compiler-output-bound inventory:
[Rust/Candle intake](../../infra/local/rag-fixture/acceptance-20261007-27-source-build-intake.json)
pin official Rust1.99.0 Windows LLVM components và Candle0.11.0 source/checksums.
Rust1.92.0 manifest ban đầu không có target host cần thiết; giữ source discovery,
chọn exact available stable version theo published manifest, không install ngầm.
Candle source được expanded vào thư mục mới, lưu toàn bộ upstream hashes. Hai
targeted local patches chỉ biến unused GGUF tokenizer dependency/module thành
opt-in feature; dùng verified Python tokenizer bên ngoài. Model math và upstream
weight reader không bị sửa. Root harness pins/source và
[feature patch](../../infra/local/rag-fixture/acceptance-20261007-27-candle-feature.patch)
được giữ để review. **Rust harness hiện là source prototype, chưa compile/test,
chưa có dependency lock/compiled trace/clearance và không được launch inference.**

Ba compiler-tooling archives (Cargo, std, MinGW) đạt exact published hashes;
rustc archive chỉ có retained prefix/parts. Full GET đạt hard600s deadline;
repair1 byte ranges phát hiện early EOF và không chấp nhận truncated data;
repair2 dùng smaller ranges với bounded continuation/preserved prefix gặp DNS
`getaddrinfo` failure. Read-only `Resolve-DnsName static.rust-lang.org` cũng timeout.
Không có auto-review rejection hoặc yêu cầu quyền mới. Theo retry limit của
AGENTS, dừng acquisition này sau hai materially different repairs, giữ toàn bộ
completed/partial files và failure evidence; không giả checksum hoặc execute partial binary.

- [Full-transfer failure](../../infra/local/rag-fixture/acceptance-20261007-27-rust-acquire-failure1.json).
- [Range failure](../../infra/local/rag-fixture/acceptance-20261007-27-rust-range-failure1.json).
- [Final repair failure](../../infra/local/rag-fixture/acceptance-20261007-27-rust-resume-failure2.json),
  SHA `c2346c4d5131179fee4ee9381106d534ec77b7ab05417e524238bd88c16e2e03`.

### Trạng thái còn lại và kiểm chứng scope

| Phần | Kết quả hiện tại |
|---|---|
| Committed durability/concurrency | Prior committed/concurrent/new-process evidence giữ nguyên; actual graceful PG/container restart mới PASS |
| Runtime clearance/inference | not_verified; original TEI vẫn chưa clearance, replacement inputs/source chưa build/clear |
| Real vectors / active index | 0 / not_verified; guard và legacy data giữ nguyên |
| Authenticated browser full-path | not_verified; không dùng static prototype/mock trace để thay proof |
| M1 | **not_verified, NO-GO** |

[Final scope audit](../../infra/local/rag-fixture/acceptance-20261007-27-final.json)
ghi ordered verification exits, source/artifact hashes, exact report/feature patches
và unrelated-source preservation. Python helpers được compile-check không tạo
bytecode, Cargo manifests parse; không coi đó là Rust build hoặc model test.
Existing product/governance/contract/lockfile sources giữ nguyên. Provider calls0,
row writes0, guard changes0, index activation0, documents deleted0. Không commit,
push, deploy hoặc cleanup. Bước phụ thuộc tiếp theo cần compiler artifact hoàn
chỉnh verified, source build/closure/license/security clearance, actual inference,
exact synthetic publication/activation rồi browser positive/follow-up/source/error
proof; các bước này vẫn nằm trong standing authority, không chờ phê duyệt lại.

## Lượt acceptance-20261007-28 — verified toolchain, actual build, host-policy blocker

Thực hiện đúng mục tiêu M1 từ yêu cầu đính kèm và DEC-023; chưa mở M2/M3, không
chat/subagent khác. Trước mutation, workspace/root resolution và git status được
kiểm; **226 source/artifact hashes lượt27** cùng hash báo cáo0.4.17 khớp, corpus
SHA `6439e86ae21ab9e8523e3a10154c5c711c886ad615baa29e24290a5f2b1592a8`
khớp. Fresh baseline/preimage và ordered dependency → catalog → OpenAPI đều
exit0; mọi pre-existing dirty/untracked/ignored work và partial downloads được giữ.

### Kết quả thực thi runtime

| Command/action | Exit | Bằng chứng và giới hạn |
|---|---:|---|
| `acceptance_runtime_20261007_28.py probe sandbox` | 1 | DNS11001; read-only, không tải lại acquisition đã hết retries |
| `… probe escalated` | 0 | DNS/TLS/HTTP206 và đúng4096 bytes từ exact pinned Rust URL; [probe receipt](../../infra/local/rag-fixture/acceptance-20261007-28-network-probe-escalated.json) xác minh điều kiện truy cập khác sandbox |
| `… acquire` | 0 | Giữ prefix33.554.432 bytes và mọi prior parts; 53 bounded ranges vào thư mục mới; archive89.052.352 bytes khớp SHA `be5384e6709f884de1f16c4588baa621707be12531b5206956d5b58ceb9ff5dd`; [acquisition](../../infra/local/rag-fixture/acceptance-20261007-28-rust-toolchain-acquisition.json) |
| Toolchain expansion repair1 / `… scan` / `… versions escalated` | 0 | 160 files; full notices giữ nguyên, streaming64KiB; Defender không khắc phục; rustc/Cargo1.99.0, LLVM23.1.1. [Expanded manifest](../../infra/local/rag-fixture/acceptance-20261007-28-rust-toolchain-expanded.json), [scan](../../infra/local/rag-fixture/acceptance-20261007-28-rust-toolchain-malware-scan.json), [versions](../../infra/local/rag-fixture/acceptance-20261007-28-rust-toolchain-versions-escalated.json) |
| `acceptance_candle_build_20261007_28.py lock` / `fetch` / offline patched lock/metadata | 0 | Local Cargo.lock99 packages; downloaded CPU resolve83 packages. [Source inventory](../../infra/local/rag-fixture/acceptance-20261007-28-candle-source-inventory-patched.json) đối chiếu từng downloaded source file với checksum-verified crate archive, không coi đây là compiled SBOM |
| `acceptance_candle_review_20261007_28.py advisories` / `supplements` / `disposition` / `source-scan` | 0 | Query81 exact registry package versions; một informational `paste1.0.15` unmaintained finding được giữ và disposition cho compile-time macro. Missing Candle-nn/pulp helper notices được bổ sung từ exact source commits. [Technical review](../../infra/local/rag-fixture/acceptance-20261007-28-candle-build-technical-review.json), [source scan](../../infra/local/rag-fixture/acceptance-20261007-28-candle-source-malware-scan.json) chỉ mở isolated build, chưa clearance inference |
| `acceptance_candle_build_20261007_28.py compile` | Cargo101 / runner1 | [Initial build](../../infra/local/rag-fixture/acceptance-20261007-28-candle-build-attempt1.json): host build-script linker `x86_64-w64-mingw32-clang` absent; output giữ nguyên |
| `… compile repair1` | Cargo101 / runner1 | [Repair1](../../infra/local/rag-fixture/acceptance-20261007-28-candle-build-repair1.json): dùng verified host và bundled rust-lld cho host/target; đã sinh compiler artifacts rồi Windows chặn quote executable trước execution |
| `acceptance_finalize_20261007_28.py policy` / `partial-build` | 0 | [CodeIntegrity proof](../../infra/local/rag-fixture/acceptance-20261007-28-host-code-integrity-blocker.json) và [actual partial inventory](../../infra/local/rag-fixture/acceptance-20261007-28-candle-partial-compiled-inventory.json), gồm artifact hashes/PE imports; không có full harness binary hoặc complete runtime SBOM |

Initial expansion gặp COPYRIGHT.html14.423.589 bytes vượt helper whole-buffer
limit8MB; giữ failure, sửa bằng streamed hashing/extraction, không bỏ notice hoặc
nới aggregate archive bounds. Inventory ban đầu dựa trên `.cargo-checksum.json`
không còn có trong Cargo1.99 extraction; repair1 so trực tiếp toàn bộ source với
verified archive. License URL `LICENSE` trả404; đọc exact pinned trees rồi sửa
đúng `LICENSE-MIT`. Cargo verbose stdout xen literal build-script records với JSON;
partial-inventory parser repair1 giữ full receipt và chỉ parse JSON compiler events.
Mọi failure receipts/preimages và downloaded originals giữ nguyên.

Review19 build scripts và pinned proc-macro closure phát hiện cleanup trong
autocfg/proc-macro2/thiserror. Ba exact packages được copy vào vendor mới và patch
chỉ để giữ compiler probes; registry sources, archive hashes và prototype lượt27
không bị sửa. Proc-macro probes dùng tên riêng theo feature để giữ output từng
probe. [Preservation patch](../../infra/local/rag-fixture/acceptance-20261007-28-compiler-probe-preservation.patch)
và local lock bind các thay đổi này; không sửa model math hay test oracle.

### Blocker thực tế và điều kiện tiếp tục

Target canonical:
`C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\candle-runtime-20261007-28\target-candle-build-repair1\release\build\quote-7eb93e5702d681cb\build-script-build.exe`.
SHA256 `8525c0d9311aad5ba9897b57f43b6aded410b35fad39210f442a58a12b8bf8ab`;
Authenticode **NotSigned**. Windows CodeIntegrity3033/3077 ghi đúng cargo/target,
không đạt Enterprise signing level dưới policy
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`; Cargo trả **OS4551**.

Không chạy repair2 đối với protection blocker này; không tắt policy, thêm trust
root, đổi tên/loader, emulator hoặc dùng executable khác để lách chặn. Điều kiện
kỹ thuật cần thay đổi: có cơ chế ký/cho phép đúng generated artifacts được host
policy hiện hành chấp nhận, hoặc có runtime artifact được policy chấp nhận và
khép được review/compiled/native/license/security evidence tương ứng. Không yêu
cầu lại quyền engineering đã được giao. Original TEI và ONNX candidate vẫn chưa
đủ clearance, không launch để thay bằng chứng.

Actual build Job Object áp **4 CPU / aggregate5 GiB trước resume**, cả child tree
nằm trong job; Cargo offline/locked, jobs4, clean credential environment và TEMP/
target mới trong workspace. Failed outputs/probes giữ nguyên. Native model calls0,
real vectors0, publication/manifest/index activation0; authenticated browser path
chưa chạy. M1 **not_verified, NO-GO**, current objective **blocked** tại host-policy
boundary. Không gọi partial build hoặc source/downloaded model là M1 PASS.

Ordered closing dependency → catalog → OpenAPI, Python helper compile-check,
git diff/check/status, report patch, all artifact/source hashes và preservation
được ghi ở [final scope audit](../../infra/local/rag-fixture/acceptance-20261007-28-final.json).
Ruff0.16.10 từ approved cache được đối chiếu RECORD hashes/retained SBOM trước
kiểm F/E9 cho sáu helpers; một unused import được sửa bằng patch nhỏ. Ba existing
deterministic canary tests PASS và changed-text known-canary/raw-key scan không
có finding; đây không phải live egress hoặc inference acceptance. Closing audit
ban đầu lỗi Windows default cp1252 khi đọc Vietnamese report preimage; giữ failure
receipt rồi sửa hai report reads thành explicit UTF-8, không đổi report nội dung
để làm decoder pass.
Không chạy lại product regression khi product code/contract không đổi; không
fabricate model tests cho harness chưa build. Provider calls0; budget ledger vẫn
22 generation/23 HTTP, 99.931 input/19.983 output, không reset. DB writes0, guard
changes0, protection changes0, documents deleted0; không commit/push/deploy/cleanup.

## Lượt29/30 — Signed C API, inference thật, smoke index và startup chưa đạt

Áp direct M1 request và DEC-023, giữ toàn bộ pre-existing dirty/untracked/ignored
work, receipts và partial downloads. Chỉ báo cáo này được cập nhật trong docs.
Fresh baseline của lượt30 ghi đúng `git diff --check` **exit2** tại
`apps/web/src/app/globals.css:945: new blank line at EOF.` Không sửa frontend
không liên quan và không chuyển kết quả global này thành PASS.

### Runtime và forward pass thực tế

Lượt29 đối chiếu published ZIP, Authenticode Microsoft, PE/PDB GUID+age, 970
compiled modules, nguồn có SHA256 trong PDB, native components/license và OS/CRT
binding. Lượt30 refresh advisories, host hashes/signatures và malware scan;
clearance chỉ cho signed Windows C API, không cho Python ONNX/NumPy/Torch native
wheels hay original TEI. [Technical review](../../infra/local/rag-fixture/acceptance-20261011-30-runtime-technical-review.json)
SHA256 `2facce5481d9c085a2f90e9f081f69e881e0d9c189b02e182edbdd7172d47685`.
DLL1.30.0 SHA256 `7e39e2bdbba836d98071ef28620735ba36a47c554cf794585269aecc50fab0da`.
OSV không có indexed findings trong exact queries; không coi đó là bằng chứng
không có mọi vulnerability. SBOM ở lượt30 là custom/SPDX subset, không tuyên bố
đã validate toàn bộ standard schema.

Model graph/data được pin tại đúng embedding revision đã chấp nhận. Embedding
ONNX graph SHA256 `f84251230831afb359ab26d9fd37d5936d4d9bb5d1d5410e66442f630f24435b`,
external data `1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4`.
Reranker bind 393 F32 safetensor tensors, 24 encoder layers, exact XLM-R config
và classifier head; raw-logits graph SHA256
`5b9f0d94516eeaf392d7ef48faaff2e6bd120f4d2ffd44ba938f55a8753f04dc`.
Full cross-runtime numerical equivalence vẫn **not_verified**, không đổi thành
PASS từ các test head nhỏ. Không dùng pickle/Torch model-code execution.

Signed C API đã load thật, API30/env/telemetry controls PASS. Query embedding
11 tokens chạy **125ms**, dimension1024, L2 norm `1.0000000007016647`.
Reranker full checkpoint query+passage26 tokens chạy **203ms**, actual raw logit
`3.8408455848693848`. Xem [embedding inference](../../infra/local/rag-fixture/acceptance-20261011-30-embedding-inference.json)
và [reranker inference](../../infra/local/rag-fixture/acceptance-20261011-30-reranker-inference.json).
Đây là actual inference, không phải score sort/candidate injection; các component
probes riêng chưa chứng minh browser M1.

Tạo đủ15 vectors thật cho exact reviewed corpus, tổng2544 corpus tokens.
Lần đầu affinity4 logical CPUs chỉ phủ2 physical cores: chunk6 vượt700ms
(718ms), output bị bỏ và attempt/tokens vẫn tính. Repair1 chọn4 logical CPUs
trên4 physical cores, giữ nguyên CPU4/aggregate5GiB/700ms/900 tokens và5 vectors
đã kiểm chứng. [Real corpus vectors](../../infra/local/rag-fixture/acceptance-20261011-30-real-corpus-vectors.json)
SHA256 `6663636a05752cc3d614ef96399ef06d83e17514587aeeb89773e476a7fc28dd`.
Tổng local inference attempts18/input2754; còn12 attempts/1086 tokens, không reset.
Dual-model capacity stage chạy thật dưới cùng caps, peak job3.04GB, model calls0.
Nine C API/shape/input/graph/head contract tests PASS; không thay component hoặc
full-path acceptance bằng tiny procedural model tests.

### Publication và scope của application

Owned fixture head0014 đã dừng; xác minh image/ownership/mounts rồi khởi động lại
đúng container, healthcheck PASS. SQLAlchemy imports trong restricted desktop
sandbox từng timeout; condition change là chạy owned read-only/local checks
ngoài sandbox trong bounded job, không thay protection. Giữ các failure receipts.

Chuẩn bị canonical before/after plan với1 synthetic actor có thật trong login
directory, identity link/role/student profile, accepted profile, manifest,
tuition source/version/chunk và active pointer. Exact actor
`4b419a1b-6d41-7dfb-8943-2edd9f071385`, directory code `SV240000`, FIT/IT_STANDARD.
One atomic INSERT-only transaction publish10 rows, preactivation actual SQL
dimension/norm/publication/tsvector validation, independent connection readback
PASS. [Publication evidence](../../infra/local/rag-fixture/acceptance-20261011-30-index-publication.json)
SHA256 `777e1ce136c05ae77847edaca9df24dcbf36077c7442c44b56ad58bb4b8d23dd`.
Index `m1-tuition-onnx-20261011-30` có1 source/1 version/1 real1024-vector chunk.
14 vectors khác chưa publish. Legacy1536-column seed3 chunks và12 historical
rows được giữ; không update/delete/reset/migrate hoặc thay schema/index definitions.

Patch nhỏ ở bootstrap và synthetic identity: explicit Settings instance được
factory/lifespan sử dụng, tenant từ server config sau khi token signature đã
verify, simulation phải bật rõ ràng trong development demo. Client không cấp
tenant/program/audience. Typed adapters đối chiếu actual DB actor/profile,
manifest/pointer với checksum-bound independent plan; lexical/vector chung
eligibility predicate và active index, real TEI HTTP adapters, canonical fusion
và reranker. Read-only dependency composition PASS, chưa có end-to-end request.
11 composition contracts PASS; closing existing lifecycle/identity/canary suites
cùng contracts **28 PASS**. Không coi monkeypatch/offline tests là actual startup.

Fixture guard mở rộng theo phạm vi narrow đã được user cho quyền: giữ12 rows cũ
và10 index/actor rows exact;1 future browser conversation của đúng actor, tối đa8
messages, bốn exact synthetic questions, source/version/chunk citations đã pin.
Mỗi lần ghi phải có exclusive full before/after row reservation trước SQL và
checksum chain; unknown row, historical drift hoặc partial append reject.
10 journal/guard tests PASS sau repair1 loại pytest temporary-symlink cleanup
khỏi harness; deletion guard vẫn bật. Chưa tạo reservation/chat row mới nào.

### Hai blocker còn lại và giới hạn thử lại

Auto-review từ chối command chứa actual DeepSeek key/destination và chat calls,
vì chưa chấp nhận trusted authorization cho concrete chat payload. Không thực
thi command đó, không đọc/gửi key, không gọi model metadata/generation hoặc
spend budget. [Rejection record](../../infra/local/rag-fixture/acceptance-20261011-30-external-launch-auto-review-rejection.json)
giữ reason; [concrete data preview](../../infra/local/rag-fixture/acceptance-20261011-30-concrete-provider-data-preview.json)
SHA256 `b0413d318ba519dacf0d6f055ba7ca1ff2b9799497c6b35068a20d4db5c91722`
liệt kê bốn câu hỏi, full591-character synthetic tuition source và giới hạn
lịch sử mới. Chỉ approved `api.deepseek.com`, `deepseek-flash`, thinking disabled,
policy trước mỗi send; không gửi durability fixture cũ, actor IDs/PII/secret trong
body, không retry/fallback. Existing ledger còn22 generation/23 HTTP,
99.931 input/19.983 output, USD0.2499589 conservative reservation. Đã recheck
[official pricing](https://api-docs.deepseek.com/quick_start/pricing/) ngày11/10,
không tạo budget mới. Cần user xác nhận concrete egress để tool review có trusted
evidence; không hỏi lại quyền engineering/DB/index local theo DEC-023.

Safer local-only branch không đọc provider key hoặc DNS/connect DeepSeek; gateway
chỉ báo unavailable, không tạo fake answer. Model service đã nạp cả hai sessions
và bind loopback18081/18082 thật, không nhận inference request. Next production
build `xCvlGdJc6_BqmGHvbUY2D` được exclusive-copy/pin vào thư mục mới, không sửa
frontend/cache gốc; chưa tuyên bố fresh source rebuild hoặc browser đã load.
Model/API/Next descendants nằm trong cùng job CPU4/5GiB trước resume; peak job
**3,808,911,360 bytes**, dưới5GiB.

Initial stack fails vì checksum helper chỉ nhận workspace paths khi Node runtime
đã pin nằm ngoài workspace ở read-only cache. Repair1 sửa read-only hash check;
Next guard còn xử lý file URL sai `%20`. Repair2 dùng `fileURLToPath` và fresh
copy, giữ cấm deletion/credential reads. Actual API sau đó fail ở factory:
`services/api/src/campus247/bootstrap/app.py:221` →
`application/action/idempotency.py:56` → `tempfile.gettempdir()` → guard rejects
TEMP write outside workspace. [Read-only diagnosis](../../infra/local/rag-fixture/acceptance-20261011-30-startup-readonly-diagnostic.json)
SHA256 `29d2c081e57f0b92f27aff9e762ab4ae84ef728b72bdb2e4df2f515bc7906707`.
Typed DB dependencies pass trước điểm factory fail. Parent log forwarding còn
cp1252/`▲` Unicode error; retained frontend log và parent stderr được giữ.
Dừng stack implementation sau hai materially different repairs; không chạy
repair3, không mở guard cho user TEMP. Điều kiện kỹ thuật kế tiếp là explicit
owned in-workspace idempotency/TEMP path và UTF-8 log forwarding được kiểm chứng.
Chỉ dừng các owned children, không cleanup files hoặc can thiệp process khác.

### Commands, checks và current disposition

Các command dưới dùng Python3.12.14 đã pin tại `infra/local/rag-fixture/.venv/Scripts/python.exe -B`.
Chi tiết command/resource/hash nằm trong từng JSON receipt, giữ mọi failure.

| Command/helper | Exit | Evidence |
| --- | --- | --- |
| `acceptance_resume_20261011_30.py smoke` | 0 | `acceptance-20261011-30-runtime-smoke.json` |
| `onnx_probe_20261011_30.py embedding / reranker` | 0 / 0 | inference/native-process receipts |
| `onnx_corpus_20261011_30.py` rồi repair1 | 1 → 0 | corpus failure + real-corpus-vectors + native-process-repair1 |
| `m1_publish_20261011_30.py` | 0 | index-publication / preactivation validation / execution plan |
| `m1_runtime_20261011_30.py capacity` | 0 | dual-model-capacity-process |
| `m1_application_20261011_30.py` | 0 | actual-application-dependencies |
| `m1_checks_20261011_30.py composition repair1 / journal repair1` | 0 / 0 | composition-contract-tests-repair1 / browser-journal-guard-tests-repair1 |
| `m1_stack_20261011_30.py` external | Rejected, not executed | external-launch-auto-review-rejection |
| local-only stack initial / repair1 / repair2 | 1 / 1 / 1 | actual-stack-process-local variants + retained logs |
| `m1_startup_diagnostic_20261011_30.py` | 1 | startup-readonly-diagnostic; no bind/write/provider |
| `m1_close_20261011_30.py ordered repair1` | 0 | closing-ordered-checks-repair1: dependency → catalog241 → OpenAPI34 → compile/lint |
| `m1_close_20261011_30.py regression / database` | 0 / 0 | 28 offline tests / closing-readonly-database |

Closing DB guard/read-only check PASS: users2, conversation1/messages5 unchanged,
sources2/versions2/chunks4, active pointer1; exact original12 + additive10 rows
preserved. No browser chat/LLM/model HTTP request occurred during local startup,
so local budget remains18 attempts/2754 tokens and provider ledger remains intact.
Closing scope/secret scan/report diff and source preservation are recorded in
[final audit](../../infra/local/rag-fixture/acceptance-20261011-30-final.json).
Global whitespace check stays pre-existing exit2; all unrelated baseline bytes
remain preserved. **M1 not_verified / NO-GO**, chưa có browser/network/API/DB/model
trace chứng minh câu trả lời thật, hỏi tiếp, mở citation, refresh/history và
negative/error cases. Không mở M2/M3, không đổi acceptance thresholds, không
commit/push/deploy/delete/reset/cleanup.

## Lượt31 — browser/auth/DB/model chạy thật; retrieval timeout, retry bị chặn

### Thực thi và correlation đã xác minh

Direct human **“ok làm đi”** chấp nhận câu hỏi ngay trước đó về bốn exact
synthetic questions, tuition source và lịch sử mới tới `api.deepseek.com`,
`DEEPSEEK_API_KEY`, budget còn USD0.2499589. Preview SHA256 vẫn là
`b0413d318ba519dacf0d6f055ba7ca1ff2b9799497c6b35068a20d4db5c91722`.
Không gửi fixture chat cũ, actor IDs hoặc credentials trong body; không log
hidden prompts/reasoning. DEC-023 vẫn là thẩm quyền engineering local/synthetic.

Fresh startup check PASS sau explicit `CAMPUS247_IDEMPOTENCY_DB`, TEMP/TMP và
`tempfile.tempdir` trong workspace. SQLite audit chỉ cho đúng database mới;
outside connection reject trước native open. UTF-8 controller/children đã nhận
Next banner thật. Giữ failed diagnostic Unicode print trước repair. Native
SQLite/schema initialization này độc lập với PostgreSQL; không reset storage cũ.

Initial paid-stack metadata attempt bị hostname guard chặn vì AnyIO dùng bytes
hostname. Giữ HTTP reservation; không retry GET/models. Repair1 nhận đúng ASCII
hostname cả str/bytes, vẫn reject tên miền khác; offline tests PASS. Model ID
`deepseek-flash` được recheck từ official docs11/10 và bắt buộc đối chiếu trong
mỗi generation response. Prior authenticated model manifest giữ nguyên.

Browser cross-origin3000→8000 chỉ tới auth GET/preflight, chưa gửi POST. Repair2
phục vụ HTML/static của **Next server thật** qua exact internal GET forwarding
`127.0.0.1:3000`, để trang/browser API cùng origin `localhost:8000`. Static bytes
đối chiếu copied production asset hashes; không mock trang hoặc API, không đổi
auth/CORS, không forward API POST/cookie/token qua frontend proxy. Production
build vẫn `xCvlGdJc6_BqmGHvbUY2D`; không tuyên bố fresh source rebuild.

Run `acceptance-20261011-31-repair2` có actual startup/lifespan và browser:

- Auth bằng directory actor thật/DB scope; POST conversation **201**.
- Conversation `01a128c6-8bcb-7dae-8f0a-65ae9e0410a0`, USER message
  `01a128c6-8c0c-7c78-81d6-ef738f2c8971`, question đúng approved preview.
- SSE API request `01a128c6-8bf9-782b-9cd4-8bfffb4a5554`: `message.started`
  rồi `message.failed / DEPENDENCY_UNAVAILABLE / retryable=false`.
- Hai actual DeepSeek generations: sensitive classifier750ms, intent1061ms;
  actual response model `deepseek-flash`, reasoning_tokens0. Intent finish
  `length`, không coi generation success là intent-schema correctness hoặc
  grounded FAQ acceptance. Tổng mới93 input/156 output tokens.
- Query embedding11 tokens/**125ms**, reranker170 tokens/**656ms**, exact
  pinned checkpoint graphs/weights. Cả native outputs được nhận dưới700ms.
  Whole reranker HTTP/adapter deadline hết; canonical result/branch counts,
  completed fusion, grounded FAQ LLM và assistant final/citation chưa verified.
- UI hiển thị hướng dẫn không tự gửi lại và lỗi kết nối AI; không biến failure
  thành câu trả lời có nguồn. Peak shared job **3,824,095,232 bytes**, dưới5GiB,
  bốn logical CPUs trên bốn physical cores. Chỉ các owned children đã dừng.

[Correlation receipt](../../infra/local/rag-fixture/acceptance-20261011-31-actual-partial-path-correlation.json)
đối chiếu browser question/API body hash/DB USER ID/provider request IDs và
exact local embedding/reranker payload hashes; rerank passage khớp published
tuition source SHA256 `359183b1f99eb4db41816bff481048c3acf39be9dd0eb0572042c1006462b7f9`.
Đây là partial actual-path proof, không phải completed M1.

### Bản sửa đã chuẩn bị, chưa launch

HTTP client nay chuẩn bị verified SSL context trước deadline; giữ
`CERT_REQUIRED` và hostname verification. Offline constructor check median
default16ms, reused context0ms theo timer resolution; không có request/model
call trong benchmark, không kết luận whole HTTP đã đạt700ms.

CPU C API extension chỉ cho `AddSessionConfigEntry` với đúng hai keys
`session.intra_op.allow_spinning`/`session.inter_op.allow_spinning` và value0.
Published headers/checksums verified; native session-options calls PASS,
unknown key/value reject trước call. Chưa load/run model bằng cấu hình mới;
không đổi math, tensors, weights, graph, four threads hoặc deadline.

Scoped patch `agent/nodes/definitions.py::retrieval_query` giữ ownership,
conversation, role/trust validation và mọi prior USER goal, chỉ bỏ generation
XML/NOTICE scaffolding khỏi encoder input. Không dùng assistant claims làm
search authority; LLM history/evidence tiếp tục qua PromptComposer untrusted
wrappers/escaping, nguồn và grants vẫn từ trusted server scope. Preimage/diff
giữ toàn bộ pre-existing dirty code.

**68 offline tests PASS** sau patch: isolation, prompt escaping, async graph,
history/context propagation, lifecycle/identity/canary và composition. Các
fakes trong unit tests không thay real M1 evidence. Native/TLS checks PASS.
Exact tokenizer dry-run cho ba câu còn lại cần **468 tokens/5 inference calls**,
còn437 tokens sau plan, mọi item dưới900; không truncate query/history, không
generate câu trả lời giả để lập kế hoạch.

Automatic approval review **rejected**, trước execution, command
`m1_stack_20261011_31l1.py`. Reason: thêm repair attempt sau hai materially
different repair stages trái retry limit trong human AGENTS instructions,
và sẽ tiêu thụ paid DeepSeek calls/additive chat/evidence writes.
[Rejection receipt](../../infra/local/rag-fixture/acceptance-20261011-31-latency-launch-auto-review-rejection.json)
giữ nguyên reason. Không đổi policy, chạy gián tiếp hoặc bypass rejection.
Offline code/tests/report được hoàn tất; human cần cho phép exact một lần
verification thêm cho bản sửa đã review này. Không xin lại concrete egress,
không tăng token/cost/deadline/CPU/memory caps.

### Closing checks, preservation và budget

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Dependency → catalog → OpenAPI | exit0;241 tasks/34 operations |
| Compile/new helper lint | PASS; global product lint giữ pre-existing F401 `NormalizedTurn`, exit1, preimage/current output identical; không gọi global lint PASS |
| Offline regressions trước/sau query patch |28 PASS /68 PASS |
| Owned PostgreSQL read-only guard/journal readback | exit0;users2,conversations2,messages6,sources2,versions2,chunks4,pointer1 |
| Native options / verified TLS / exact token dry-run | exit0;không stack/model/provider call |
| Latency-fix stack launch | auto-review rejected;command không chạy |

PostgreSQL giữ original12 rows, exact additive10 index/actor rows, thêm đúng1
conversation +1 USER message đã reservation trước SQL;0 new assistant final.
Knowledge/schema/index hashes không đổi. Legacy chat1conversation/5messages
vẫn nguyên. Global `git diff --check` giữ pre-existing exit2 tại
`apps/web/src/app/globals.css:945`; không sửa dirty state không liên quan.

Provider ledger nối tiếp, không reset: **20 generation/20 HTTP**,99.838 input,
19.827 output, **USD0.2497438 conservative reservation** còn lại. Lượt31 tính3
HTTP attempts gồm metadata attempt bị chặn và2 generations thật; không tuyên
bố cost reservation là actual billed cost. Local aggregate **20/30 inference**,
**2935/3840 input tokens**, **4/40 model HTTP**; còn10 calls/905 tokens/36 HTTP.
Client pre-transport attempts cũng được ghi trước connect để failed transport
không miễn budget. Cần tiếp tục từ các ledger hiện tại, không từ lượt30.

[Final audit](../../infra/local/rag-fixture/acceptance-20261011-31-final.json)
ghi exact source/report diffs, preservation, secret scan và artifact hashes.
**M1 not_verified / NO-GO**: còn successful grounded answer/citation, follow-up,
source/citation open, refresh/resume và actual no-source case. Error UI đã có
bằng chứng. M2/M3 chưa mở; không commit/push/deploy/delete/reset/cleanup.

## Lượt32 — latency đạt; real grounded generations bị EvidenceGate từ chối

Human “tiếp” sau blocker retry cho phép launch một lần kiểm chứng bản sửa đã
chuẩn bị. Actual startup/lifespan thành công với helper31-latency1, same-origin
Next/API, owned PostgreSQL và hai model thật; không tạo hội thoại thứ hai.
Browser history GET trả200 và khôi phục USER question cũ. Automatic approval
review sau đó chặn submit Q4 trước khi thao tác thực thi, với lý do chưa chấp
nhận “tiếp” là exact authorization cho submission/paid egress. Không bypass.
User trả lời trực tiếp **“Xác nhận toàn bộ lần kiểm chứng và egress nêu trên”**
cho ba câu Q4/Q2/Q3, nguồn synthetic và lịch sử mới tới `api.deepseek.com`,
local persistence/source/refresh/no-source, một lượt có cùng caps. Chỉ sau
confirmation đó mới gửi ba câu bằng UI. Không gửi dữ liệu chat lịch sử khác.

| Ca thực tế | Retrieval/models | Provider/final |
|---|---|---|
| “Học phí tiêu chuẩn là bao nhiêu?” | lexical0/vector1/RRF1/rerank1;922ms; embed19tokens/219ms, rerank178tokens/609ms | classifier, intent, grounded FAQ thật; EvidenceGate reject, persisted `safe_refusal`/`abstained`, citations[] |
| “Nếu em học 3 tín chỉ thì tổng học phí là bao nhiêu?” | giữ cả hai USER goals trước; lexical0/vector1/RRF1/rerank1;812ms; embed33tokens/141ms, rerank192tokens/594ms | classifier, intent, grounded FAQ thật; EvidenceGate reject, persisted `safe_refusal`/`abstained`, citations[] |
| “Trường có quy định về học bổng du học Nhật Bản không?” | simulation deny; lexical0/vector0/RRF0/rerank0;235ms; embed46tokens/203ms | classifier/intent thật; không gọi grounded FAQ; persisted “Hiện tại tôi chưa tìm thấy tài liệu chính thức về vấn đề này trong hệ thống.” |

Whole adapter retrieval đã hoàn tất dưới overall1800ms và từng native call
được nhận dưới700ms; không tăng timeout hoặc cắt history. Source candidate
khớp published chunk/version/hash. Đây là typed SQL/model/RRF path thật,
không injected candidates, fake vectors hoặc câu trả lời copy nguồn. Tuy nhiên
lexical luôn0; chưa chứng minh lexical positive hit. Raw reranker logits giữ
nguyên2.174043893814087 và1.0152952671051025, không đổi score hay threshold.

Hai câu có nguồn đã tới real `grounded_faq` nhưng chưa vượt EvidenceGate.
Safe receipts giữ final từ chối và hashes của SSE deltas, không raw provider
draft hoặc hidden prompts. Exact gate reason/overlap metric không được ghi;
không suy đoán “thiếu citation”, “sai format” hoặc “overlap thấp” là root cause
đã chứng minh. Cần diagnostic reasons/metrics an toàn trước khi sửa; không
giảm evidence_support_threshold0.78 hoặc bỏ xác thực để ép acceptance.
Không có accepted citation nên citation/source-open vẫn **not_verified**.

Refresh browser giữ đúng conversation
`01a128c6-8bcb-7dae-8f0a-65ae9e0410a0`, khôi phục cả ba persisted abstained
finals và bốn USER messages. Không coi refresh abstention là refresh của
grounded answer/citation thành công. No-source PASS; error UI lượt31 giữ nguyên.

[Database/path correlation](../../infra/local/rag-fixture/acceptance-20261011-32-database-and-path-correlation.json)
đối chiếu actual POST/SSE final IDs/content với exact journal/read-only DB,
USER IDs với provider request IDs, query hashes với toàn bộ USER history,
candidate source hash và counts. DB có2 conversations/12 messages; conversation
mới có7 messages tổng, gồm USER thất bại cũ và6 messages của lượt này. Journal
8 reservations khớp đầy đủ before/after; historical/index hashes giữ nguyên.

Native aggregate **25/30 calls**, **3403/3840 tokens**, **14/40 HTTP attempts**
(bao gồm `/info`, không chỉ inference); còn5 calls/437 tokens/26 HTTP. Provider
lượt này8 actual generations/8 HTTP, model `deepseek-flash`, reasoning0;
ledger còn **12 generations/12 HTTP**,97.460 input/19.193 output tokens,
**USD0.2482696 conservative reservation**. Cost thực thu chưa biết. Không reset
ledger, không retry metadata hoặc thất bại. Một lượt verification được cho phép
đã dùng xong; không tự mở live retry/cấp thêm message scope.

Peak shared job **3,850,444,800 bytes**, CPU4/5GiB. API/models graceful exit0;
Next exit1 khi controller terminate owned child, không có crash trong serving
log. Parent exit0; chỉ owned children đã dừng, không cleanup artifacts/data.
Product/source không đổi trong lượt32; giữ68 offline PASS của bản sửa đã chạy,
không cộng thành số test mới. Global lint F401 `NormalizedTurn` và diff-check
`globals.css:945` pre-existing giữ nguyên, không tuyên bố global PASS.

[Final audit](../../infra/local/rag-fixture/acceptance-20261011-32-final.json)
giữ hashes, report preimage/patch, git scope và budget. **M1 not_verified / NO-GO**:
còn accepted grounded answer và follow-up có citation, source-open/refresh
citations, positive lexical evidence. M2/M3 chưa mở; không commit/push/deploy,
delete/reset/cleanup hoặc production access.

## Lượt33 — lexical/diagnostics sửa offline; native reranker timeout ở browser thật

Direct human request mở chu kỳ mới sau32, đúng một conversation local/synthetic
mới, tối đa6 messages và ba câu UI cụ thể. Áp DEC-023, không xin lại local
engineering/egress đã được chỉ định. Baseline giữ hashes/preimages và toàn bộ
dirty state; không sửa governance, requirements, thresholds hoặc journal cũ.

Read-only SQL chứng minh lexical zero-hit do AND query chứa `bao`, `nhiêu` và
các từ lịch sử không có trong nguồn. Implementation chuyển natural-language
query sang OR của lexemes `simple`; explicit phrase/negation/OR vẫn dùng
`websearch_to_tsquery`. Giữ trusted authorization/profile/source eligibility,
SQL top30 và ranking. [PostgreSQL read-only proof](../../infra/local/rag-fixture/acceptance-20261011-33-lexical-readonly-after.json)
ghi hits lần lượt1/1/0/0/1/0 cho positive, follow-up, simulation-denied,
phrase-minus, explicit OR và punctuation. Đây chưa là lexical contribution
trong một accepted browser answer.

Grounded prompt yêu cầu JSON claims có cited IDs/type; parser kiểm strict format
và deterministic renderer chỉ thêm citation đã parse. EvidenceGate vẫn dùng
threshold0.78, source/version/span resolver và fail closed; thêm hash-only
diagnostics với turn correlation, citation validity, reason/support/overlap
metrics. Bỏ citation markup khỏi token overlap. Không log provider draft,
prompt, secrets hoặc hidden reasoning. Chưa có real gate metric lượt33 vì
retrieval thất bại trước grounded generation; không kết luận đã sửa nguyên
nhân hai gate rejects lượt32.

| Kiểm tra | Bằng chứng/kết quả |
| --- | --- |
| Dependency → catalog → OpenAPI | exit0; receipt prelive-checks giữ exact commands |
| Retrieval/gate/graph/SSE offline |94 PASS; offline-final exit0; giữ receipts các harness/repair thất bại |
| New additive journal guard |5 PASS; old8 records/old data immutable, scope exact actor/three questions |
| Historical fixture guard suite |1 failure do expected0012 trong khi head0014 đã có trước lượt33;16 PASS/1 skip; không sửa expected result |
| Scoped lint | exit1 chỉ pre-existing F401 `NormalizedTurn`; không gọi global lint PASS |
| Diff check | scoped PASS; global giữ pre-existing `globals.css:945` |
| Frontend | source hashes khớp verified build; fresh namespace copy, không sửa frontend source |
| Actual startup/lifespan | PASS; real Next/API/native models/owned PostgreSQL; CPU4/5GiB shared job |

Exact tokenizer plan trước live:423 input tokens/5 native calls, trong437/5
còn lại. Adapter/native700ms, overall1800ms, batch native60/provider120 seconds
không đổi. Native ledger bắt đầu25/3403/14 và provider từ latest ledger32;
không chạy helper với ledger30/31-repair2, không retry GET/models.

Browser tạo conversation `01a12a94-e53c-772b-a958-9fa3fa80140e` và gửi đúng
“Học phí tiêu chuẩn là bao nhiêu?”. Signed-auth API request
`01a12a94-e5ba-7f3f-8c04-d655afe99d93` khớp persisted USER
`01a12a94-e5df-70bd-830d-4616e939a3ad`. DeepSeek `deepseek-flash`, thinking
disabled, classifier/intent thật chạy2 generations/2 HTTP,91 input/132 output,
reasoning0. Native embedding ordinal26:10 tokens/250ms; reranker ordinal27:
169 tokens reserved, `700ms model deadline reached; native Run terminated`.
Adapter nhận failure; SSE `message.failed` với `DEPENDENCY_UNAVAILABLE`,503,
retryable=false. UI hiển thị lỗi, không tự retry; reload khôi phục USER message
đã lưu, không có assistant final. Không submit câu2/3 hoặc tạo hội thoại khác.

[DB/API/budget correlation](../../infra/local/rag-fixture/acceptance-20261011-33-database-and-budget-correlation.json)
ghi DB3 conversations/13 messages: đúng1 new conversation/1 USER/0 assistant
finals,2 new reservations. Historical2 conversations/12 messages/8 reservations
nguyên vẹn; source SHA359183…, indexes SHA97773… và projected original rows
SHAc3ca46… giữ nguyên. Citation/source-open, accepted positive/follow-up,
refresh accepted citations và no-source trong hội thoại mới **not_verified**.

Native ledger cuối **27/30 calls,3582/3840 tokens,18/40 HTTP**; còn3 calls/
258 tokens/22 HTTP. Timeout reservation vẫn tính. Provider còn10 generations/
10 HTTP,97.369 input/19.061 output, **USD0.2480839 conservative reservation**;
actual billed cost chưa biết. Ledgers cuối dựng từ durable reservations/results
vì runtime bị dừng có kiểm ownership, không giả là graceful worker final.

Để chạy lại đủ ba ca trong chính hội thoại mới, giữ USER thất bại trong query
history, exact tokenizer cần **5 native calls/463 tokens**:18+177,32+191,45+0.
Thiếu **2 calls/205 tokens** so với còn3/258. Ba answer pairs cần6 new messages,
nhưng còn5 slots: thiếu **1 message**. Đây là minimum cho đúng plan hiện tại,
không bảo đảm hết latency/gate blocker. Không tăng caps hoặc xóa USER để vừa
ngân sách. Nếu tiếp tục cần direct human mở aggregate native caps30→32,
3840→4045 và message cap6→7 cho chính conversation trên, giữ các caps khác;
phải xử lý/kiểm deadline trước live retry.

Runtime đã dừng đúng4 owned PIDs sau kiểm commandline/parent; không dừng DB.
Launch stdin đóng nên không graceful; parent receipt exit4294967295 giữ thật.
Peak shared job **3,823,210,496 bytes**, dưới5GiB. Không xóa artifacts/data.
[Final audit](../../infra/local/rag-fixture/acceptance-20261011-33-final.json)
giữ exact incremental patches/hashes, preservation, status/checks và forward
ledgers. **M1 not_verified / NO-GO**; M2/M3 chưa mở; không commit/push/deploy,
delete/reset/cleanup, bypass protection hoặc production access.

## Lượt34 — dynamic scheduling chưa giải quyết native700ms; một lượt đã dùng

Human “ok” chấp nhận exact proposal sau33: một lượt sửa/kiểm chứng tiếp;
aggregate native32 calls/4045 tokens; conversation
`01a12a94-e53c-772b-a958-9fa3fa80140e` tối đa7 messages kể cả USER thất bại
lượt33. Các caps khác giữ nguyên. Không tạo conversation mới; guard34 chỉ
cho append sáu messages Q1/assistant/Q2/assistant/Q3/assistant vào conversation
này, sealed journal33/historical8 records và failed USER đều immutable.

[ONNX Runtime troubleshooting](https://onnxruntime.ai/docs/performance/tune-performance/troubleshooting.html)
và header publisher1.30.0 đã pin mô tả `session.dynamic_block_base=4` để giảm
variance do phân chia công việc. Cấu hình mới chỉ thêm đúng key/value này,
giữ intra/inter spinning0, sequential execution, intra4/inter1, graph
optimizations99, original FP32 graph/weights và actual logits. Không quantize,
đổi model/provider, chạy warm-up miễn budget hoặc nâng deadline. Đây là hướng
sửa được kiểm chứng, không khẳng định scheduling là nguyên nhân timeout đã
chứng minh. Actual session creation chấp nhận cấu hình nhưng live vẫn fail.

Baseline34 giữ current hashes/preimages và git status. Fresh derivative runtime
nạp **latest native27/3582/18** và provider ledger33, không reset. Exact tokenizer
plan trước live:18+177,32+191,45+0 = **463 tokens/5 calls**, vừa remaining463/5.
CPU4/5GiB shared tree, max900/item, native/adapter700ms, retrieval1800ms và
native60/provider120-second batch caps giữ nguyên. Frontend source không đổi;
build được copy tới namespace34 với kiểm source/artifact hashes. Reviewed native
launcher còn tạo một empty TEMP directory ở literal30-dual-serve-temp; directory
mới này được giữ, không ghi đè hay cleanup dữ liệu lịch sử.

Offline37 tests PASS, gồm new guard/CPU config cùng gate/vector regressions.
Lần đầu1 failure/36 PASS do guard chưa chặn duplicate conversation rows;
đã sửa implementation, giữ test oracle và receipt thất bại. Dependency →
catalog → OpenAPI và helper syntax PASS; giữ pre-existing F401 `NormalizedTurn`
và global diff-check `globals.css:945`. Không cộng lại94 tests lượt33 thành test
mới và không gọi global checks xanh.

Actual startup/lifespan Next/API/native/owned PostgreSQL PASS. First resume GET
history401 do raced bootstrap với token từ phiên cũ; normal UI demo-session ký
lại cùng actor, một reload khôi phục USER thất bại trước submission. Không sửa,
inject token, bypass auth hoặc gửi câu khi history chưa được xác nhận. UI gửi
lại đúng “Học phí tiêu chuẩn là bao nhiêu?”; signed API request
`01a12b16-adcc-7a68-a8ee-e55ad324c281` khớp persisted USER
`01a12b16-adec-7e6d-b58b-6ae9bce8bc18` và hai real provider request IDs.

DeepSeek `deepseek-flash`, thinking disabled: classifier/intent2 generations/
2 HTTP,205 input/110 output, reasoning0. Native embedding ordinal28:18 tokens,
250ms accepted; reranker ordinal29:177 tokens reserved, `TimeoutError` từ
unchanged700ms native Run bound. Adapter retrieval fail, SSE `message.failed`
DEPENDENCY_UNAVAILABLE503/retryable=false. UI hiển thị error, không auto retry.
**Grounded generation/EvidenceGate chưa chạy,0 new assistant finals/citations.**
Không gửi Q2/Q3, không claim lexical positive browser contribution/citation open
hoặc no-source trong hội thoại mới.

Final UI reload chạm retained **40 static-forward HTTP cap**; further assets
bị assert reject trước hydration/history GET. Refresh sau lượt34 **not_verified**,
không coi empty UI là dữ liệu DB mất. Không nâng hoặc reset cap để reload lại.
DB read-only correlation vẫn PASS: **3 conversations/14 messages**, đúng0 new
conversations/1 USER lượt34; conversation mới có2 failed USERs/0 assistant finals.
Guard/journal34 có1 append reservation; toàn bộ13 messages trước lượt34 và các
journal/source/version/span/index hashes nguyên vẹn. [DB/path correlation](../../infra/local/rag-fixture/acceptance-20261011-34-database-and-path-correlation.json)
giữ actual IDs, scope/index/query hashes, route usages và failures.

Graceful native ledger cuối **29/32 inference,3777/4045 tokens,22/40 HTTP**;
còn **3 calls/268 tokens/18 HTTP**. Cả reranker timeouts27/29 vẫn tính; dùng
[native ledger34](../../infra/local/rag-fixture/acceptance-20261011-34-native-budget-ledger.json),
không quay lại ledger33. [Provider ledger34](../../infra/local/rag-fixture/acceptance-20261011-34-provider-budget-ledger.json)
còn **8 generations/8 HTTP,97.164 input/18.951 output,USD0.2478904 conservative
reservation**; actual billed cost chưa biết. Với một future three-pair plan có
câu trả lời ngắn trong existing4000-char bound và năm prior turns, tokenizer
cần26+185,40+199,45+0 =495 tokens/5 calls; thiếu2 calls/227 tokens và1 message
slot. Đây chỉ là prospective plan, chưa phải live evidence hoặc quyền retry mới.
Không xin tăng budget để thay thế việc giải quyết deadline.

API/native graceful exit0, parent0; Next1 khi controller dừng owned child.
Peak shared job **3,855,347,712 bytes**, dưới5GiB; không dừng DB hoặc cleanup.
[Final audit](../../infra/local/rag-fixture/acceptance-20261011-34-final.json)
giữ incremental fixture/report patches, baseline/history/helper hashes và exact
commands/exits. Một lượt sửa/kiểm chứng mới đã dùng; dừng tại blocker có bằng
chứng. **M1 not_verified / NO-GO**; chưa mở M2/M3, không commit/push/deploy,
delete/reset/cleanup, bypass guard/policy hoặc production access.

## Lượt35 — điều tra latency offline hoàn tất; chưa có bằng chứng sửa native timeout

Human “ok” cấp đúng lượt điều tra offline sau34: chỉ đọc code/config/evidence,
không gọi model/provider và giữ caps. DEC-023 áp dụng cho công việc local này.
Không tạo session/load DLL, launch runtime, đọc credential, kết nối DB, gọi
endpoint hay chạy warm-up. Chỉ thêm helper/technical receipts namespace35 và
cập nhật báo cáo này; baseline/preimage giữ mọi thay đổi trước lượt35.

[Static analysis](../../infra/local/rag-fixture/acceptance-20261011-35-latency-analysis.json)
đối chiếu11 reservations ordinal19–29 với success receipts theo đúng payload
SHA/kind/token count. Không suy ra elapsed700ms từ một receipt còn thiếu:
27/29 không có success elapsed, và failure evidence trước đó vẫn giữ nguyên.

| Ordinal | Loại | Tokens | Native elapsed đã ghi | Kết quả |
| --- | --- | --- | --- | --- |
| 20 | reranker | 170 | khoảng656ms | accepted |
| 22 | reranker | 178 | khoảng609ms | accepted |
| 24 | reranker | 192 | khoảng594ms | accepted |
| 26 | embedding | 10 | 250ms | accepted |
| 27 | reranker | 169 | không có số đo thành công | timeout ở lượt33 |
| 28 | embedding | 18 | 250ms | accepted |
| 29 | reranker | 177 | không có số đo thành công | native TimeoutError ở lượt34 |

Input dài hơn từng pass trong khi input ngắn hơn fail; các payload/session
khác nhau nên đây không phải controlled A/B. Độ dài input làm tăng lượng tính
toán nhưng **chưa chứng minh là nguyên nhân chính**. Reranker24 layers,
hidden1024/intermediate4096/16 heads có khoảng110GFLOPs dense encoder matmul
ở B1/S177, so với khoảng10,9GFLOPs ở S18. Đây là ước tính số phép toán,
không phải thời gian, throughput đo thật hoặc lower bound latency.

Python3.12.14 tại máy trả `monotonic=GetTickCount64`, resolution0.015625s;
`perf_counter=QueryPerformanceCounter`, resolution1e-7s. Native `elapsed`
hiện dùng monotonic, chỉ bao từ timer start đến Run return; không bao input
tensor setup, output extraction/serialization. Adapter700ms bao cả client,
GET/info identity check, POST, validation. Vì vậy hai số đo không cùng phạm
vi và Run phải chừa thời gian cho overhead. Clock resolution là hạn chế của
measurement, **không có bằng chứng clock gây native TimeoutError**.
[Python clock documentation](https://docs.python.org/3.12/library/time.html#time.get_clock_info)
mô tả cách kiểm implementation/resolution; kết quả cụ thể ở receipt local.

Graph nguồn reranker có2631 nodes/393 FP32 initializers, external tensors
2.271.023.108 bytes,192 MatMul/24 Softmax/24 Erf,98 ReduceMean và144 constant
weight Transposes. Graph embedding có2495 nodes và0 constant weight Transposes.
Session dùng optimization99, nhưng không có serialized optimized graph hoặc
operator profile trong evidence hiện tại. **Không kết luận144 transposes chạy
mỗi inference hoặc graph runtime chưa fusion**: ORT có thể constant-fold/fuse
lúc load. Lưu optimized graph chủ yếu tránh lặp optimization khi startup;
không tự chứng minh giảm Run latency.
[ORT graph optimization documentation](https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html)
phân biệt optimization khi khởi tạo và serialization offline.

[Diagnostic review](../../infra/local/rag-fixture/acceptance-20261011-35-diagnostic-review.json)
hash-check publisher header1.30.0 rồi đọc data-only signatures/indexes của
EnableProfiling, SessionEndProfiling, SetOptimizedModelFilePath. Ba API này
chưa nằm trong restricted C API hiện tại; **không mở allowlist hoặc gọi API**.
Receipt timestamps của29 cho khoảng680,623ms từ reservation tới adapter
failure và725,470ms tới native failure receipt; khác process và có I/O/scheduling,
không dùng làm phase timings. Chưa biết operator nào đắt nhất, fusion/prepacking
thực tế, CPU saturation/frequency hoặc page faults lúc timeout.

Hướng tiếp có bằng chứng là thêm diagnostics `perf_counter_ns` cho queue,
tokenization, tensor setup, native Run, output/HTTP và CPU/page-fault deltas,
giữ nguyên deadline enforcement. Sau review exact profiling API/path closure,
một lần reranker synthetic có profile có thể tìm operator/thread bottleneck;
profile gây overhead và timeout có thể cho trace chưa đầy đủ.
[ORT profiling documentation](https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html)
mô tả trace theo operator/thread. Chỉ xét FP32 fusion/prepacking khi profile
chứng minh lợi ích; muốn đổi graph cần kiểm logits/scores thực và external-data
closure vì weights vượt2GiB. Chưa quantize/approximate, đổi checkpoint/tokenizer,
threshold, concurrency hoặc deadline.

Prospective một reranker current-history185 tokens nằm trong remaining3 calls/
268 tokens; nếu count được xác nhận lại, còn2/83. Không đủ hai lần185-token A/B,
không coi warm-up là miễn phí. Đây là kế hoạch đo, **chưa có quyền live retry mới**
và không có call nào ở lượt35. Native ledger34 giữ **29/32 calls,3777/4045 tokens,
22/40 HTTP**; provider vẫn còn8 generations/8 HTTP,97.164 input/18.951 output,
USD0.2478904 conservative reservation. Không reset/tăng budget hoặc message cap.

6 offline parser/correlation/arithmetic tests PASS; dependency → catalog →
OpenAPI PASS. Full helper lint ban đầu có3 style findings; đã sửa đúng helper
mới và giữ receipt ban đầu; final lint PASS. Không sửa product/runtime/fixture
hoặc test oracle. [Final audit](../../infra/local/rag-fixture/acceptance-20261011-35-final.json)
giữ exact report patch, historical hash preservation và commands/exits.
Điều tra offline hoàn tất; **M1 vẫn not_verified / NO-GO**, chưa chứng minh latency
đã sửa hoặc grounded generation/EvidenceGate/citations đã pass; M2/M3 chưa mở.

## Lượt36–38 — đo native/HTTP và nghiệm thu thật, chưa chứng minh root cause

Đây là phần tiếp tục của một chu kỳ điều tra/sửa được giao trực tiếp, không
reset các thất bại trước. DEC-023 là standing authority cho engineering local/
synthetic. Người dùng đã chấp thuận hai gói cụ thể: native32→37 calls,
4045→4827 tokens, conversation7→8 messages; rồi37→41 calls,4827→4963 tokens,
conversation8→9 messages và thêm2 provider generations/HTTP. Static forwarding
được chấp thuận40→100→145 requests, byte cap vẫn20MiB. CPU4/shared5GiB,
native/adapter700ms, retrieval1800ms, native60s/provider120s active batches,
exact tokenizer/max900 tokens/item và EvidenceGate0.78 giữ nguyên.

### Implementation và measurement

TEI adapters có optional diagnostics cho client construction/open/close,
identity/inference HTTP, decoding, identity/output validation và adapter total.
Sink chỉ nhận phase/outcome/timing; exception của observer không thay kết quả
port. Native collector dùng `perf_counter_ns`/QPC quanh tensor setup, `Run`,
terminate/output extraction, cùng current-owned-process CPU time, working set,
commit và page-fault deltas. Server ghi budget-lock queue, read/tokenization,
reservation, serialization/response-write và retrieval total. Không log raw input,
token IDs, credentials, prompts, PII hoặc hidden reasoning. Counter page faults
gồm soft/hard, không xác định disk I/O. Queue measurement không bao OS accept
backlog. Original monotonic + `threading.Timer(0.7)` enforcement không đổi.

Review checksum-bound ORT1.30.0 header và exact C API trước khi cho riêng profiler
gọi EnableProfiling/SessionEndProfiling vào fresh namespace36-profile30; không
export optimized graph/custom op/provider registration. Trace ordinal30 hoàn tất,
nhưng profile có overhead. Collector receipt30 ban đầu có flagfalse mặc định;
[disposition](../../infra/local/rag-fixture/acceptance-20261011-36-profile-disposition.json)
ghi erratumtrue với original hash, không ghi đè receipt. Không dùng latency
profile làm unprofiled benchmark hoặc semantic-parity proof.

Fixture guard nối thêm hai journal checksum-bound cho đúng conversation
`01a12a94-e53c-772b-a958-9fa3fa80140e`. Tất cả journal30/33/34 và failed USERs
được giữ. Mỗi continuation chỉ cho sáu messages theo đúng ba câu; historical rows,
source/version/chunk IDs, authorization và source status vẫn kiểm nguyên vẹn.
Runtime helpers mới nối latest ledgers; provider+2 được ghi additive, không
reset token/cost reservation. Frontend source/build không đổi; copy834 files
vào hai fresh artifacts36/38 từ build checksum-bound, không rebuild để né history.

### Các phép đo thật và giới hạn kết luận

| Ordinal | Điều kiện | Tokens | Native QPC | Native CPU delta | Native page faults | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| 30 | reranker-only, có profile | 185 | 454,952ms | 1,609375s | 4287 | completed |
| 31 | reranker-only, không profile | 185 | 486,507ms | 1,750000s | 4079 | completed |
| 32 | dual model resident; không embedding inference/profile | 185 | 509,667ms | 1,609375s | 4122 | completed |
| 33 | full stack36, embedding qua UI/API | 26 | 718,044ms | 1,234375s | 74607 | native terminate/timeout |
| 34 | dual model, embedding cold control | 26 | 185,073ms | 0,421875s | 863 | completed |
| 35 | cùng session/payload như34, lặp đã reserve | 26 | 163,688ms | 0,500000s | 164 | completed |
| 36 | dual model; first encode sau session load | 26 | 173,426ms | 0,546875s | 887 | completed |
| 37 | full stack38, embedding qua UI/API | 34 | 235,221ms | 0,687500s | 1013 | completed |
| 38 | full stack38, reranker qua UI/API | 193 | 715,751ms | 2,000000s | 3992 | native terminate/timeout |

30/31/32 có cùng payload/model graph/config hashes, output1×1 và actual logit
`2.500174045562744`; điều này là parity của đúng payload đã thử, không phải
cross-runtime/generic semantic equivalence. 34/35/36 cùng26-token payload như
failed embedding33 và có cùng vector hash/shape1×1024. Stage controls34/35 chạy
liền nhau, không có free inference warmup. Native phases có overhead collector;
CPU delta gồm mọi threads của process, không phải shared-tree CPU attribution.

Trace30 có709 events,168 MatMul events tổng367.432µs; BiasGelu/LayerNormalization/
FusedMatMul cho thấy runtime fusion thực tế. Trong trace này không có runtime
events map đến144 source constant-weight Transposes. Vì vậy giả thuyết144 phép
đó đều chạy mỗi inference không được hỗ trợ. Dual-resident32 pass bác bỏ việc
chỉ có embedding nằm trong RAM là điều kiện đủ gây reranker timeout trong phép
thử này. Cold embedding34 cũng pass; không thể quy mọi thất bại cho cold session.
First encode sau load ở36 mất10,93ms,92 page faults và không tăng commit memory;
không có bằng chứng chọn sửa tokenizer/lifecycle theo giả thuyết đó.

Failure33: budget-lock queue0,0034ms, server tokenization40,725ms,
reservation6,298ms, native718,044ms. Adapter identity26,644ms, inference HTTP bị
cancel ở660,981ms, adapter total730,878ms; retrieval failure740,860ms. Native
terminate được QPC ghi thực tế, nên HTTP overhead hoặc clock resolution không
đủ giải thích toàn bộ lỗi. Model working set trước33 khoảng1,246GB, tăng305MB
trong Run, khác controls34/36 khoảng2,505/3,029GB. Đây là dấu hiệu residency/
resource-state cần đo tiếp, **không chứng minh hard faults, disk paging hoặc tác
nhân làm working set giảm**.

Failure38 có working set khoảng3,033GB và chỉ3992 native faults, tương tự
reranker controls đã pass, nhưng vẫn terminate715,751ms. Vì vậy page faults cao
của embedding33 **không giải thích đầy đủ reranker timeout**. 193-token payload38
khác185-token controls; không dùng khác biệt latency này làm controlled causal
A/B. Thread scheduling, CPU frequency/contention, residency và input-specific
runtime behavior còn chưa phân biệt. Không thay graph/math/checkpoint, deadline,
threshold hoặc hủy reranker để ép PASS. **Chưa chọn hướng sửa latency nào**;
instrumentation và guard/ledger continuation không được kể là repair success.

### UI/API/persistence và acceptance còn thiếu

Hai lần khởi động stack thật và submit Q1 qua browser sử dụng authenticated
synthetic actor, đúng conversation hiện hành. Phiên cũ sau restart có401 trong
history restore; demo-session refresh + page reload phục hồi đúng2 rồi3 failed
USERs trước submission. Không chép/đọc token vào evidence. Mỗi Q1 append một
USER thật, gọi đúng2 DeepSeek classifier/intent generations và thực thi native
model(s) như bảng. Cả hai SSE trả `message.failed`, UI hiện safe error và không
tự gửi lại. Refresh phục hồi3 rồi4 USERs; không có assistant final/citation mới
trong DB. Đây là error/persistence evidence, **không phải accepted-final refresh**.

Lượt38 đã chạy lexical/vector/fusion tới reranker nhưng retrieval không trả
accepted candidate set. Grounded FAQ generation và EvidenceGate không được
gọi ở hai submission này; parser/prompt/gate trước đó vẫn chỉ có offline proof.
Không submit Q2/Q3 sau Q1 fail. Accepted answer, follow-up3 tín chỉ, citation
reauthorization/source-open/source-version-span, accepted-final SSE/UI/refresh
và no-source abstention còn thiếu. Không tuyên bố no-source đã pass từ việc
source bật/tắt hoặc từ test fake.

### Verification, preservation và budget cuối

82 deterministic tests PASS cho native timer/shape/counters/privacy, TEI
identity/cancellation/cleanup/observer behavior, EvidenceGate/provenance và cả
hai additive journal guards. Dependency → catalog → OpenAPI PASS, scoped lint
PASS và helper syntax/import-target checks PASS. Giữ mọi failed harness/startup
receipts: ruff thiếu trong fixture venv, style findings, pytest temp cleanup
guard, duplicate asyncio autoload và wrong generated CPU import trước inference.
CPU import sửa về unchanged CPU34; failed startup không gọi model/provider.
Không đổi test expected results. Global pre-existing diff-check ở globals.css
và unrelated dirty/untracked work không sửa.

Hai successful stack controllers đã shutdown owned API/models/Next; no cleanup.
Peak shared job36/38 lần lượt3.840.401.408/3.853.934.592 bytes, dưới5GiB, cùng
affinity4 logical CPUs trên4 physical cores. DB cuối có3 conversations/16 messages,
giữ mọi old rows/indexes: stored rows SHA `c3ca46b7d9dac87b595ba7358b9fdc3beed2ebb78c1837004a2bb1efe573df1b`,
public indexes SHA `97773ec369a9d83c3501f48f930f747c4b4bd9c0c6cb60812e73a1f6122e9904`.
Source/index/corpus không thay; không production/real-data access, commit/push/
deploy/delete/reset/cleanup hoặc mở M2/M3.

Tổng chu kỳ đã reserve9 native calls/886 tokens và4 DeepSeek generations;
mọi thất bại tính đủ. [Native ledger38](../../infra/local/rag-fixture/acceptance-20261011-38-native-budget-ledger.json):
**38/41 calls,4663/4963 tokens,28/40 HTTP; còn3 calls/300 tokens/12 HTTP**.
[Provider ledger38](../../infra/local/rag-fixture/acceptance-20261011-38-provider-budget-ledger.json):
còn6 generations/6 HTTP,96.628 input/18.815 output tokens,
USD0.2475664 conservative reservation; actual billed cost vẫn chưa biết.
[Static ledger38](../../infra/local/rag-fixture/acceptance-20261011-38-static-budget-ledger.json):
130/145 requests,9.476.981/20.971.520 bytes; còn15 requests/11.494.539 bytes.
Conversation hiện4 failed USERs/cap9, không thể thêm đủ6 messages mà giữ cap này.
Phần native còn lại cũng không đủ một complete three-pair acceptance plan.

[Measurement analysis36](../../infra/local/rag-fixture/acceptance-20261011-36-measurement-analysis.json),
[controls37](../../infra/local/rag-fixture/acceptance-20261011-37-controls-process.json),
[ordering control37](../../infra/local/rag-fixture/acceptance-20261011-37-ordering-controls-process.json)
và [full-stack preservation38](../../infra/local/rag-fixture/acceptance-20261011-38-actual-api-final-preservation.json)
là bằng chứng có thể kiểm lại. **M1 vẫn not_verified / NO-GO**: đã xác định timeout
thực sự nằm trong native Run ở hai lỗi mới, chưa xác định causal root mechanism
hoặc hướng sửa được kiểm chứng. Không tiêu phần budget còn lại vào retry không
đủ diagnostic/acceptance plan; không dùng các controls pass để tuyên bố M1 hoàn tất.

## Lượt39 — tái hiện đúng payload lỗi trong process cô lập

Người dùng chỉ dẫn **“tiếp”** sau lượt38. Hai calls đối chứng được tính exact227
tokens và nối ledger38; cap41/4963/40 không tăng. Helper mới chỉ đọc hash-bound
journals để dựng đúng query trước fourth failed USER, rồi đối chiếu payload hashes
với actual reservations37/38. Không đưa nội dung raw/token IDs vào receipts.
Load embedding rồi reranker, chạy embedding34 tokens trước reranker193 tokens,
cùng checkpoint/graph/config và CPU4/shared5GiB/native700ms. Không warmup hoặc
HTTP/provider/browser/DB writes. Source, history và index không thay.

| Ordinal | Điều kiện | Tokens | Native QPC | Native CPU delta | Native faults | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| 39 | matched embedding37, dual-model process cô lập | 34 | 194,549ms | 0,546875s | 1015 | completed, shape1×1024 |
| 40 | matched reranker38, ngay sau39 | 193 | 721,417ms | 2,093750s | 4120 | native timeout, không accepted output |

Embedding39 original Session elapsed203ms khác native QPC194,549ms; cả hai
được giữ, không đổi clock enforcement. Reranker40 có cùng payload SHA
`a710625313bd9c852172890e9eef905901a35188fa0e533b9b4e76e459b351ef`, graph/config
hashes và shape như failure38. Native terminate xảy ra ở offset718,474ms,
working set trước Run2.511GB, commit2.498GB; peak job2.516.553.728 bytes dưới5GiB.
Controller exit0 chỉ xác nhận harness/shutdown; **model40 exit1/timeout**.

Đối chứng này bác bỏ việc HTTP overhead, API/frontend/provider coexistence
hoặc commit khoảng3GB là điều kiện cần cho **lỗi193-token đã thử**. Không loại
trừ các yếu tố đó có đóng góp trong ứng dụng. Không kết luận độ dài193, kernel
dispatch, prior embedding Run, thread migration hoặc CPU frequency là nguyên
nhân chỉ từ kết quả này. Background machine state không được kiểm soát.

Phân tích lại successful trace30 cho705 node scheduling rows: main Run tổng
398.374µs, Wait25.300µs, Distribution3.008µs. Đây là cumulative stats của
185-token pass, không phải utilization mỗi core hoặc trace lỗi193. Review
[SGEMM source v1.30.0](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.30.0/onnxruntime/core/mlas/lib/sgemm.cpp)
và [ORT thread documentation](https://onnxruntime.ai/docs/performance/tune-performance/threading.html)
chưa đủ xác nhận “ngưỡng192 tokens” hoặc chọn affinity/thread-pool sửa latency.
**Root mechanism vẫn chưa chứng minh;0 hướng sửa latency được chọn.**

Helper39 đã kiểm syntax, scoped lint và dependency→catalog→OpenAPI PASS trước
launch. Initial plan/lint findings được giữ; sửa import order/closure binding/
exception disposition trước model call, tạo reviewed-plan receipt mới, không
ghi đè initial receipt.82 offline tests trước đó còn áp dụng cho unchanged native
collector/TEI/journal behavior. Hai helpers39 không đổi application behavior.

Tổng từ baseline29/3777:11 native calls/1113 tokens,4 DeepSeek generations.
[Native ledger39](../../infra/local/rag-fixture/acceptance-20261011-39-native-budget-ledger.json):
**40/41 calls,4890/4963 tokens,28/40 HTTP; còn1 call/73 tokens/12 HTTP**.
Provider/static giữ latest ledger38: còn6 generations/6 HTTP và15 static
requests; byte cap20MiB vẫn còn11.494.539 bytes. Conversation giữ4 failed USERs,
global3 conversations/16 messages, không có accepted assistant/citation mới.
Các acceptance answer/follow-up/source-open/refresh/no-source vẫn thiếu.

[Complete next plan](../../infra/local/rag-fixture/acceptance-20261011-39-next-budget-proposal.json)
tính bằng tokenizer thật:5 diagnostic/comparison calls957 tokens, rồi5 acceptance
calls543 tokens. Diagnostics gồm profile đúng193-token failure, fresh185-token
control, fresh193-token control không có preceding embedding Run, và tối đa hai
comparison sửa chỉ khi measurement chỉ ra cơ chế. Acceptance Q1 exact42/201;
Q2 conditional48/207; Q3 conditional45/0. Tính lại từ persisted accepted finals
trước mỗi submission; không dùng opaque assistant slots làm dữ liệu chạy thật.

Toàn plan cần10 calls/1500 tokens; thiếu**9 calls/1427 tokens**,2 provider
generations/HTTP,1 message slot và45 static requests. Đề xuất aggregate
**native41→50 calls,4963→6390 tokens, conversation9→10 messages, static145→190
requests, provider+2 generations/+2 HTTP**. NativeHTTP40, static20MiB, provider
token/cost caps, resource/deadline/threshold và toàn bộ lịch sử giữ nguyên.
Đây là budget dự kiến, **chưa được cấp, chưa thực thi, không bảo đảm PASS**.
Dừng model calls ở phần còn lại không đủ; không coi “tiếp” là tự tăng cap.

[Analysis39](../../infra/local/rag-fixture/acceptance-20261011-39-analysis.json)
và [scope/preservation receipt39](../../infra/local/rag-fixture/acceptance-20261011-39-final-scope.json)
giữ exact measurements, hashes, patches và command exit codes. Không cleanup,
commit/push/deploy/reset, mở M2/M3 hoặc thay requirements. **M1 not_verified / NO-GO.**

## Lượt40–42 — profile và đối chứng vị trí threads

Người dùng chấp thuận chính xác aggregate50 calls/6390 tokens/10 messages/
static190/provider+2. Phần đề xuất chưa cấp ở lượt39 là trạng thái lịch sử;
không dùng ledger cũ hoặc reset các reservations. Giữ CPU4/shared5GiB,
native/adapter700ms, retrieval1800ms, HTTP40, static20MiB, token/cost provider
caps, max900 exact tokens và checkpoint/FP32/EvidenceGate0.78.

| Native ordinal | Điều kiện | Tokens | Native QPC | Kết quả |
| --- | --- | --- | --- | --- |
| 41 | reranker-only, profile193 đúng payload lỗi | 193 | 601,361ms | completed; profile không thay unprofiled proof |
| 42 | fresh reranker-only, original185 control | 185 | 519,233ms | completed |
| 43 | fresh reranker-only, không preceding embedding Run | 193 | 714,600ms | native timeout |
| 44 | same193, cố định caller/worker placement, unprofiled | 193 | 488,763ms | completed; logit difference0 |
| 45 | same193 placement, embedding/reranker cùng resident | 193 | 614,323ms | completed; logit difference0 |

Control43 bác bỏ preceding embedding Run hoặc dual-model residency là điều
kiện cần của timeout193-token này. Trace41 có709 events;168 MatMul tổng488.732µs,
các fusions được quan sát thực tế. Không suy runtime optimized graph từ source
graph. Profile thêm overhead; không dùng profile pass để nhận unprofiled latency.

Main-thread MatMul core samples thay đổi38 lần trong trace41. Review
[ORT ThreadPoolProfiler v1.30.0](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.30.0/onnxruntime/core/common/threadpool.cc)
cho thấy worker `core` chỉ cập nhật sau interval ít nhất10ms, nên các samples
không chứng minh đồng thời caller/worker collision. Review
[affinity parser](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.30.0/onnxruntime/core/util/thread_utils.cc)
xác nhận IDs1-based; `3;5;7` tương ứng LP2,4,6. Caller LP0, process mask85
giữ đúng bốn logical CPUs trên bốn physical cores đã cấp.

**Hướng sửa1** thêm duy nhất worker affinity vào session config và tạm pin
current caller thread; khôi phục chính xác mask trước đó trong `finally`, kể cả
error/timeout. Chỉ dùng current-process/current-thread pseudo-handles; không
thay process khác, Windows security policy hoặc job CPU/memory/deadline.
Config SHA mới `3026087cea7ca307e6a3376439d922c4735e7c5a6ee6a982c2c5c60b0e6e75dc`;
graph/weights/tokenizer/math/shape giữ nguyên. Logit44/45 đều
`3.296050786972046`, exact difference0 so với original accepted193 profile41.
Không có multi-candidate ranking proof vì payload chỉ một candidate.

Control43→44 là can thiệp một biến cấu hình, có lợi ích đo được; background
machine state/frequency chưa kiểm soát nên không khẳng định causal root cause
duy nhất. Slot comparison thứ hai được dùng kiểm lại **hướng1** dưới dual
residency, không chọn một hướng sửa2 không cần thiết. Calls/tokens vẫn nằm
trong complete plan đã duyệt, giữ nguyên acceptance5 calls/543 tokens.
Offline40 có85 tests PASS, offline41 có89 tests PASS. Các trace, exact C API
review, input/config hashes, caller restoration và job metrics được giữ ở
[review41](../../infra/local/rag-fixture/acceptance-20261011-41-review.json),
[native44](../../infra/local/rag-fixture/acceptance-20261011-41-native-measurement-44.json),
[native45](../../infra/local/rag-fixture/acceptance-20261011-42-native-measurement-45.json)
và [ledger42](../../infra/local/rag-fixture/acceptance-20261011-42-native-budget-ledger.json).

## Lượt43 — nghiệm thu thật vẫn bị chặn ở embedding

Tạo namespace mới, copy417 production frontend artifacts với hashes nguyên
vẹn, không đổi frontend source. Runtime composed đúng hướng1 cho cả hai model.
Journal43 nối immutable journals30/33/34/36/38; giữ bốn failed USERs và cho phép
tối đa sáu exact new messages trong cùng conversation cap10. Fixture chỉ thêm
hash-bound journal branch; preimage và patch được giữ. Static forwarding dùng
chung aggregate counters qua hai app phases; first install từ chối existing
ledger để không âm thầm reset trên fresh process.

93 deterministic tests PASS; dependency→task catalog→OpenAPI preflight PASS,
exact real history Q1 được tính42 embedding/201 reranker trước submission.
Actual Next/API/model startup, owned DB/index/actor checks PASS; không có startup
warmup/inference. Signed demo session mới cần reload lần hai để đọc history;
không submit trong trạng thái401. UI đã hiện đầy đủ bốn failed USERs trước Q1.

Browser gửi “Học phí tiêu chuẩn là bao nhiêu?” vào authenticated existing
conversation. USER được persist, hai real DeepSeek sensitive-classifier/intent
generations completed đúng `deepseek-flash`, reasoning0. Query/trusted scope/index
được dựng từ history thật. Embedding native46 có shape1×42, payload SHA
`1717863bca2c28988d99895ad9a5343758bcc813733b6fdcab8b113dd1cbbd1e`:

- Native total712,109ms; Run702,940ms; tensor setup8,553ms. Timer terminate ở
  offset705,838ms; nguyên deadline enforcement được giữ.
- Tokenization1,479ms; native CPU1,140625s; native faults1107, working set trước
  Run3.028.566.016 bytes. Fault count gộp không xác nhận disk I/O hoặc cold paging.
- Embedding adapter cancellation total721,621ms; retrieval QPC738,057ms.
  Shared job peak3.831.865.344 bytes dưới5GiB; đây không phải resource-cap breach.

Timeout thực sự nằm trong native Run; tokenization/HTTP không đủ giải thích lỗi.
Chưa có matched42 isolated fixed/default-placement controls nên chưa tách được
embedding placement, input, coexistence hoặc machine-state contributions.
Lợi ích reranker44/45 **không** chứng minh embedding hoặc full-stack đã sửa.
Không chạy Q2/Q3 hay retry Q1 sau lỗi vì plan/history/budget không còn đủ.

SSE thực tế `message.started`→`message.failed`, code `DEPENDENCY_UNAVAILABLE`,
retryable false; UI hiện lỗi và không tự retry. Không tới real reranker,
grounded FAQ/EvidenceGate/citation resolver. Không có assistant final/citation mới;
accepted answer, follow-up, source-open, refresh final/citations và no-source
acceptance của lượt mới vẫn thiếu. Không chép nguồn hoặc sửa thresholds để PASS.

Controller được launch thiếu PTY, nên tool không có writable stdin để gửi stop.
Đây là lỗi harness, không phải nguyên nhân đã chứng minh của native timeout.
Kiểm PID/command/creation-time trước khi dừng đúng owned worker8668 và Next27084;
job owner đóng job, giữ abnormal exit `4294967295`. Không có graceful API/native
final receipts; không giả định graceful shutdown. Read-only DB check riêng
sau stop xác nhận global3 conversations/17 messages, target5 USERs/0 ASSISTANTs,
rows khớp immutable journal, legacy/index hashes nguyên vẹn. Exact owned process
inventory sau stop không còn PID nào của stack này.

[Native46](../../infra/local/rag-fixture/acceptance-20261011-43-native-measurement-46.json),
[authenticated SSE](../../infra/local/rag-fixture/acceptance-20261011-43-browser-api-043.json),
[post-stop preservation](../../infra/local/rag-fixture/acceptance-20261011-43-post-stop-preservation.json)
và [analysis43](../../infra/local/rag-fixture/acceptance-20261011-43-analysis.json)
giữ failure/measurement/shutdown limitations. Provider ledger được reconcile
từ extension và hai success receipts, không giả là graceful API ledger.

Hiện dùng **46/50 native calls,5889/6390 tokens,30/40 HTTP**; còn4 calls/501
tokens/10 HTTP. Provider còn6 generations/6 HTTP,96297 input/18740 output tokens,
USD0.2473771 conservative reservation, actual billed cost chưa biết. Static
**160/190 requests,11.673.773/20.971.520 bytes**; còn30 requests/9.297.747 bytes.
Tất cả failed reservations/lịch sử được giữ; không tự tăng caps.

[Next complete plan](../../infra/local/rag-fixture/acceptance-20261011-43-next-budget-proposal.json)
tính lại bằng tokenizer thật: Q1 conditional50/209, Q2 conditional48/207,
Q3 conditional45/0, acceptance5 calls/559 tokens. Bốn diagnostic slots matched42
tổng168 tokens tách default/fixed placement, coexistence trong cùng owned job
và tối đa một direction2 comparison có bằng chứng. Diagnostics direct native,
không provider/HTTP; mọi warmup vẫn phải tính, plan này không có warmup.
Tổng cần9 calls/727 tokens; thiếu5 calls/226 tokens,2 provider generations/HTTP,
1 conversation slot,30 static requests. Đề xuất **native50→55 calls,6390→6616
tokens,conversation10→11,static190→220,provider+2 generations/+2 HTTP**.
HTTP40/static20MiB/provider token-cost/resource/deadline/threshold giữ nguyên.
Chưa được cấp, chưa thực thi; không bảo đảm PASS. Chỉ còn tối đa một hướng sửa
khác trong chu kỳ đã giao, không reset số hướng sửa vì sang namespace mới.

Scoped lint/preflight/offline/preservation và exact baseline diffs được giữ trong
[scope43](../../infra/local/rag-fixture/acceptance-20261011-43-final-scope.json).
Global `git diff --check` còn lỗi whitespace có trước ở `apps/web/src/app/globals.css`;
baseline hash của file đó được giữ, không sửa unrelated work. Không commit/push/
deploy/delete/reset/cleanup, production/real-data access hoặc mở M2/M3.
**M1 vẫn not_verified / NO-GO: root mechanism embedding và acceptance chưa đạt.**

## Lượt44–52 — đối chứng, sửa measurement và khép chu kỳ hai hướng

Ngày12/10/2026 (Asia/Bangkok); receipts giữ UTC11/10. Áp dụng direct human
“cho phép tự tăng caps và thực hiện triệt để” cùng DEC-023: tự tính và mở rộng
aggregate caps theo plan cụ thể, giữ toàn bộ predecessors/failed reservations.
Không reset ledger, không xin lại quyền engineering hoặc budget. Quyền này không
thay giới hạn tối đa hai hướng sửa, model/provider, FP32, exact tokenizer/max900,
CPU4/shared5GiB, native/adapter700ms, retrieval1800ms, native60s/provider120s
active batch hoặc EvidenceGate0,78. Không mở M2/M3.

### Đối chứng embedding44–47

Tất cả dùng payload42-token khớp hash của native46, real tokenizer/checkpoints,
fresh dual-model process và không có warmup miễn phí. Hai tokenizer được giữ
resident trước model load; inference trả đúng vector1024 normalized. Native47/48
cold default/fixed placement đạt khoảng165/200ms; max vector difference0/cosine1.
API/Next resident cùng job, direct native49 đạt183,53ms. Real TEI-compatible HTTP
adapter standalone50 và co-resident51 đạt155,33/201,46ms native; nested launcher
matched stack43 native52 đạt173,27ms tổng,171,11ms Run. Các ca này có0 browser
static forwarding,0 provider calls,0 DB writes, không nạp provider key ở read-only
API. Exact legacy/index/source/journal preservation giữ nguyên.

Các đối chứng bác bỏ late tokenization, nested job hoặc sự có mặt API/Next là
điều kiện **đủ** gây timeout trong các ca đã đo; không chứng minh chúng không bao
giờ góp phần. Cũng chưa xác định cơ chế của embedding46 timeout lịch sử.
Generator47 từng thay literal quá rộng làm sai revision/hash API; phát hiện trước
launch, giữ preimage và sửa đúng literal. Lỗi chuẩn bị đó tiêu0 model/provider
calls; không phải hướng sửa latency mới. Các receipts và helper hashes được giữ
trong [scope52](../../infra/local/rag-fixture/acceptance-20261011-52-final-scope.json).

### Measurement48–50: overhead được xác định và sửa, lỗi thật vẫn còn

Collector48 enumerate/open các thread handles trước/sau Run trong timer hiện
hành; Win32 calls chỉ query own-process, owner/creation-time được kiểm. Full-stack
native53 embedding50-token đạt412,85ms nhưng snapshot overhead119,38ms; native54
reranker209-token timeout799,52ms, overhead137,91ms. Các số này bị instrumentation
ảnh hưởng đáng kể, không dùng để kết luận tốc độ native không đo hoặc cơ chế
scheduling. USER thứ6 được giữ;0 accepted assistant final.

Cached collector49 prime handles trước readiness, chỉ query cached handles trong
Run, kiểm owner/creation-time và close trước engine. Không enumerate/open trong
Run, không đổi deadline/clock, không inference warmup. Late Timer threads không
nằm trong snapshot; aggregate process CPU vẫn bao gồm chúng. Fresh209-token
native55 đạt604,89ms QPC, snapshot0,2295ms, raw logit3,8009610176086426.
Wrong-owner/handle-close/creation-time checks có deterministic coverage.

Full-stack50 với collector mới: native56 embedding50-token đạt224,35ms,
snapshot0,5418ms; native57 reranker209-token timeout707,21ms, snapshot0,3682ms.
Caller/workers đúng masks1/4/16/64, resident pool còn lại CPU0 trong interval đo.
Caller CPU671,875ms, workers484,375–593,75ms; hai cumulative snapshots không chứng
minh lịch chạy đồng thời, wakeup latency hoặc host frequency. QueryThreadCycleTime
không được đổi thành elapsed time/frequency. Aggregate page faults không phân
biệt hard/soft hoặc chứng minh disk I/O. Như vậy collector overhead lớn không
phải nguyên nhân duy nhất của timeout; fixed placement (hướng1) chưa đủ.

Lượt48 offline tests lần đầu bị treo ở Python socketpair/loopback accept dưới
sandbox; giữ traces, dừng đúng owned processes đã kiểm PID/creation-time. Chạy
lại bằng execution permission phù hợp đạt95 tests;50 đạt98. Không sửa guards,
tests hoặc expected results để bỏ lỗi, không có automatic approval rejection.
TTY controller48/50 giữ graceful API/models final receipts; Next owned được dừng.

### Hướng sửa2 và A/B51

Căn cứ: profile41 có MatMul Wait3603/11371µs, measurement57 cho caller/worker
CPU lệch trong khi placement đúng và pool còn lại idle. Đây là giả thuyết còn
lại về dispatch/worker waiting, **chưa phải causal proof**. Intervention chỉ đổi
active intra-op spin policy: allow_spinning1, spin_duration_us1000,
force_spinning_stop1. Giữ inter-op spinning0, dynamic_block_base4, affinities3;5;7,
intra4/inter1/sequential/optimization99, cùng graphs/FP32 weights. Không thêm C API
capability. Cửa sổ1ms là cấu hình best-effort được calibrate, không bảo đảm mỗi
đoạn spin có hard wall-clock1ms. Theo [header ORT1.30.0](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.30.0/include/onnxruntime/core/session/onnxruntime_session_options_config_keys.h),
force_stop áp dụng khi Run cuối kết thúc và workers được khởi động lại cho Run
tiếp theo; không cần warmup native miễn phí.

[Review51](../../infra/local/rag-fixture/acceptance-20261011-51-review.json)
chốt4 diagnostic calls/518 tokens rồi5 acceptance calls/559 tokens/10 HTTP.
Caps tự mở lên66 calls/7945 tokens/54 native HTTP, conversation13 messages,
static280 requests/20MiB, provider+2 generations/+2 HTTP; token/cost caps provider
giữ nguyên. Không thay ledger cũ. Hai fresh dual-model jobs đều idle60s sau ready,
sau đó paid embedding50 → reranker209, cùng payload SHA của native56/57. Không
HTTP/API/Next/provider/DB trong controls này; host background/frequency và thứ tự
launch không được kiểm soát hoàn toàn.

Baseline58/59 và candidate60/61 đều PASS. Original enforcement elapsed cho
baseline khoảng203/578ms, candidate172/485ms; exact QPC/phase times giữ trong
[analysis52](../../infra/local/rag-fixture/acceptance-20261011-52-analysis.json),
không đánh đồng hai clocks. Embedding max absolute difference0/cosine1; raw logit
absolute difference0. Một source candidate chỉ chứng minh ranking của ca một
candidate, không phải multi-candidate semantic evaluation. Lợi ích trong control
không chứng minh root cause duy nhất hoặc full-stack acceptance.

### Nghiệm thu thật52 — NO-GO, không thử hướng3

Successor52 giữ nguyên tám historical journal sources/hash chain, bảy failed
USERs và tất cả rows cũ; chỉ cho sáu exact additive messages tối đa trong chính
conversation `01a12a94-e53c-772b-a958-9fa3fa80140e`. Frontend copy417 artifacts từ
build34, hashes trùng, không đổi UI source.99 tests PASS trong1,95s; ba preflight
commands exit0; scoped Ruff PASS. Real tokenizer plan Q1 là50 embedding/209
reranker, derived từ actual persisted history, không truncate/reset.

Browser mở cùng conversation, auth reload và history read thấy đủ bảy USER.
Không tạo conversation mới; tab cũ không thuộc browser session được thay bằng
tab verification mới. Gửi đúng Q1, persisted USER thứ8. Hai real DeepSeek
classifier/intent generations thành công. Trusted scope/index và embedding thật
đã chạy; native62 đạt303,139ms tổng/299,8302ms Run, snapshot0,4742ms.
Native63 reranker209-token timeout **734,4927ms tổng/733,496ms Run**,
snapshot0,7365ms, terminate callback bắt đầu offset712,1483ms. Session config hash
`f2c3a2c0946e37c907bd9db038c89766b90f5417717f990fe3fbf2a94f098a3e` xác nhận
đúng candidate spin policy. Caller CPU640,625ms, workers562,5–609,375ms, masks
1/4/16/64; other resident model poolCPU0. Shared job peak3.857.211.392 bytes dưới
5GiB. Không có bằng chứng frequency/OS scheduler nào đủ để kết luận cơ chế gốc.

[Retrieval failure](../../infra/local/rag-fixture/acceptance-20261011-52-actual-retrieval-1-failure.json)
ghi TimeoutError trong1,1889323s. Native timeout không được đổi thành thành công
vì overall retrieval còn dưới1800ms. [Authenticated SSE](../../infra/local/rag-fixture/acceptance-20261011-52-browser-api-043.json)
ghi message.started → message.failed, DEPENDENCY_UNAVAILABLE/retryablefalse;
UI hiển thị lỗi và không tự retry. Không gọi grounded FAQ generation, không tới
EvidenceGate/citation resolver;0 persisted ASSISTANT final. Q2/Q3, accepted
follow-up, source-open và refresh accepted final/citations chưa được nghiệm thu
lại. Ephemeral UI error bubble không phải persisted assistant final.

Đã dừng ngay sau Q1 lỗi, không click Thử lại. API/models graceful exit0; Next
owned process terminated exit1, không giả đó là graceful Next shutdown.
[Read-only post-stop check](../../infra/local/rag-fixture/acceptance-20261011-52-post-stop-preservation.json)
xác nhận global3 conversations/20 messages, target8 failed USERs/0 ASSISTANTs,
actual rows khớp immutable journal. Legacy rows SHA
`c3ca46b7d9dac87b595ba7358b9fdc3beed2ebb78c1837004a2bb1efe573df1b`, public
indexes SHA `97773ec369a9d83c3501f48f930f747c4b4bd9c0c6cb60812e73a1f6122e9904`
giữ nguyên. Chỉ một synthetic tuition source index được activate; không full
corpus/production readiness.

Ledger cuối: native63/66 calls,7645/7945 tokens,48/54 HTTP; còn3/300/6.
Static250/280 requests,18.264.149/20.971.520 bytes; còn30 requests/2.707.371 bytes.
Provider còn6 generations/6 HTTP,95178 input/18526 output tokens,
USD0,2467846 conservative reservation; actual billed cost chưa biết. Tất cả failed
reservations được giữ. Không thiếu quyền tự mở caps; chưa có technical evidence
để tuyên bố sửa triệt để. Hướng1 và hướng2 đều chưa đạt full-stack acceptance,
nên dừng chu kỳ theo giới hạn hai hướng trực tiếp từ yêu cầu ban đầu.

[Final scope52](../../infra/local/rag-fixture/acceptance-20261011-52-final-scope.json)
giữ preimage/report patch, baseline hashes, old helper immutability, exact command
exit codes và ledgers. Global git diff --check còn whitespace có trước ở
globals.css, hash được giữ; không sửa unrelated work. Không commit/push/deploy,
delete/reset/cleanup hoặc production/real-data access. **M1 vẫn not_verified /
NO-GO; root mechanism và accepted answer/follow-up/citation/refresh còn thiếu.**

## Chu kỳ cấu hình mới53–56, ngày12/10/2026

Direct human request mở chu kỳ mới và cho phép deadline/resource/cap adjustments
local/synthetic, ưu tiên trước baseline700/1.800ms và60/120s. DEC-023 áp dụng;
không hỏi lại quyền engineering/DeepSeek/caps. Không thay models/checkpoints,
tokenizer, signed ORT1.30 C API, FP32, EvidenceGate0.78, filters, authorization hoặc
context/input limits. Không commit/push/deploy/delete/reset/cleanup, không M2/M3.
[Baseline53](../../infra/local/rag-fixture/acceptance-20261012-53-baseline.json)
giữ git status/hash/preflight, settings preimage đã xác minh hash36 và spec HEAD
preimage. Settings/spec được patch trước khi baseline receipt hoàn tất; ghi minh
bạch việc khôi phục exact preimage, không coi receipt tạo sau là timestamp trước sửa.
Mọi dirty work khác và thất bại lịch sử giữ nguyên.

### Cấu hình, controls và candidate v1

Thêm frozen `RuntimeDeadlines`, revision riêng, exact integer validation và hữu
hạn: native100–3.000ms; adapter≤5.000ms và ≥native+200ms; retrieval≤12.000ms và
≥2×adapter+400ms; batch30–600s; controller≥batch, ≤1.200s. Settings chỉ nhận overlay
development/testing với DEMO_MODE; mặc định production profile giữ700/1.800ms.
SQL lexical/vector và HybridSearchAdapter revalidate typed effective profile,
giữ toàn bộ model/index/quality fields. Không chuyển domain rules vào routes.
RAG_PIPELINE1.1.1 section1.2 ghi quyền và hai candidates, production TP-RAG SLO
giữ nguyên; không đổi expected latency cũ rồi tuyên bố đạt.

| Cấu hình | Baseline52 | v1,53–55 | v2,56 |
|---|---:|---:|---:|
| Native deadline |700ms|1.000ms|1.600ms|
| Semantic/reranker adapter |700ms|1.400ms|2.100ms|
| Overall retrieval |1.800ms|3.300ms|4.700ms|
| Native/provider active batch |60s|600s|600s|
| Stack controller |120s|900s|900s|
| CPU/shared job memory |4/5GiB|4/5GiB|4/5GiB|

Giữ intra4/inter1/sequential/optimization99, masks1/4/16/64,
affinities3;5;7, dynamic_block_base4, intra spinning1/duration1000µs/force_stop1,
inter spinning0, hai model sessions cùng resident. Timer/monotonic enforcement
đọc JSON; QPC đo riêng. Cancel/join timer trước ReleaseRunOptions; native timeout
discard output. Controller đọc input qua queue có finite monotonic end.

Native64 control trả natural completion551,0978ms QPC, Run550,0207ms, original
enforcement563ms; dư437ms theo enforcement. Cùng209-token payload SHA
`5057dcb064e1e1b3626435e2a06d33688582fcef57235919ad729926b49623cb`, raw
logit3,8009610176086426, parity difference0; không warmup miễn phí/profiling nặng.
[Control53](../../infra/local/rag-fixture/acceptance-20261012-53-control-result.json)
chỉ chứng minh ca cô lập, không full-stack stability.

Startup53/54 bị baseline-only profile revalidation chặn. Hai điểm SQL adapters
và Hybrid constructor được sửa bằng cùng typed validation, test actual create_app
thêm để kiểm consumer. Startup failures không tiêu native/provider calls hoặc
ghi messages. Harness label reset tránh exclusive receipt overwrite; lỗi đầu54
được giữ. Offline lần đầu53 có1 failure/247 pass ở test fresh-process authority
file đã tồn tại; tách hermetic test case, giữ guard chống reset;53verified248 pass,
54 đạt263,55 đạt264. Không đổi authorization/grounding oracle.

Docker daemon ban đầu tắt. Người dùng mở Docker Desktop; executor kiểm exact
container/image/volume/network rồi start existing fixture, không recreate/reset.
Prelaunch và post-stop legacy rows/index hashes trùng52, migration0014.

Browser55 dùng cùng conversation,9th USER được persist; hai DeepSeek classifier/
intent đạt. Native65 embedding50-token đạt308,6184ms QPC; native66 reranker209
timeout1.031,5444ms total/1.030,575ms Run. Callback terminate bắt đầu offset
1.025,5562ms; snapshot0,4763ms. [SSE55](../../infra/local/rag-fixture/acceptance-20261012-55-browser-api-041.json)
message.started→message.failed, DEPENDENCY_UNAVAILABLE/retryablefalse. Không
grounded generation/final, không click Thử lại. QPC page faults4399 là aggregate
soft/hard, không chứng minh disk I/O. CPU/thread snapshots không đủ chứng minh
OS scheduling, frequency/thermal hoặc ORT synchronization. V1 chưa đủ vận hành.

### Người dùng tăng tiếp; actual acceptance56

Sau khi xem failure55, người dùng trực tiếp nói “tăng lên tiếp đi”. Candidate v2
chỉ tăng deadlines1.600/2.100/4.700ms, không sweep hoặc lặp control cô lập đã có.
[Review56](../../infra/local/rag-fixture/acceptance-20261012-56-review.json)
reserve5 acceptance calls +4 repeat calls, ≤1.350 native tokens; caps76/10.000/72
giữ nguyên. Native starts66/8.113/52; static starts294/21.523.412, caps400/32MiB.
Provider ledger55 còn8 calls; thêm2 thành10, dự toán8 calls/80.000 input/7.000
output, USD0,0324 worst-case, giữ input/output/cost caps. Failed reservations không
reset. Journal mới cho đúng6 messages seq10–15, tối đa15 messages trong target,
nối cả9 failed USERs. Actual Q1/Q2/Q3 plans lần lượt50/209,48/207,45/0 embedding/
reranker tokens, từ actual persisted history/finals và tokenizer thật; không
manual truncate/reset hoặc fake assistant history.

269 deterministic checks PASS trong7,57s: cấu hình/defaults/scope/bounds,
native termination/output discard/non-timeout error/RunOptions lifecycle,
profile propagation, actual bootstrap, lexical/vector/fusion/provenance,
EvidenceGate/citation, persistence/SSE regressions. Giữ99-test evidence cũ.
Dependency verification,241-task catalog và OpenAPI validation exit0; scoped
Ruff E4/E7/E9/F/I PASS bằng local pinned0.16.10. Lệnh `python -m ruff` trong fixture
venv không có module, receipt fail giữ nguyên, không cài dependency để xóa lỗi.

Signed browser auth→persist USER→trusted scope/index→actual PostgreSQL lexical/
vector/fusion→HTTP models→real DeepSeek generation→gate→persist final→SSE/UI
đã chạy cho Q1/Q2. Q1 trả480.000 VNĐ/tín chỉ, Q2 follow-up tính480.000×3=
1.440.000 VNĐ. Hai gate receipts PASS, threshold0.78, citation valid; Q2 arithmetic
claim overlap0,875. Bốn retrieval với reranker liên tiếp đều đạt:

| Lượt | Native embed QPC | Native rerank QPC | Retrieval enforcement total |
|---|---:|---:|---:|
| Q1 |204,8229ms|784,1169ms|1.141ms|
| Repeat1, không messages/provider |183,4172ms|515,8531ms|844ms|
| Repeat2, không messages/provider |181,9858ms|789,9087ms|1.140ms|
| Q2 |188,9368ms|623,0671ms|953ms|
| Q3, no-source |177,2277ms|không gọi|235ms|

Reranker lớn nhất789,9087ms, QPC headroom810,0913ms với deadline1.600ms; không
đánh đồng QPC và enforcement. Repeats giữ exact Q1 query/context đã authenticated,
thật SQL/HTTP, cùng logit3,8009610176086426; journal unchanged,0 duplicate messages,
0 provider calls. Peak shared job3.878.322.176 bytes dưới5GiB. Queue/tokenization/
serialization và adapter phases, native CPU/memory/page faults, tensor/Run/
extraction giữ ở receipts; snapshot overhead0,2607–0,3767ms. Không đổi clocks để
nới ngầm deadline. [Analysis56](../../infra/local/rag-fixture/acceptance-20261012-56-analysis.json)
giữ exact phase observations và limitations; không suy causal proof từ headroom.

Q3 chạy cùng index nhưng `allow_labeled_simulation=False`, nguồn synthetic duy
nhất bị filter. Lexical/vector/fusion0, không reranker/grounded generation, hai
classifier/intent calls; persisted safe_refusal/abstained, không citations. Đây
là no-source policy check của smoke corpus, không chứng minh full corpus không
có quy định học bổng Nhật Bản.

SSE completed content/citations/response_class/finish status answered/abstained
khớp immutable journal và actual DB. Source/version/chunk đúng IDs; full chunk
SHA `359183b1f99eb4db41816bff481048c3acf39be9dd0eb0572042c1006462b7f9`
khớp retrieval/gate. Public citation dùng existing500-character excerpt, kiểm
exact prefix, không so hash của excerpt với hash cả chunk. Refresh actual API
history giữ3 finals và2 citations; Q2 drawer mở lại đúng simulation-v1 và quote.
[Ảnh sau refresh](../../infra/local/rag-fixture/acceptance-20261012-56-browser-citation-after-refresh.png)
và [DOM history](../../infra/local/rag-fixture/acceptance-20261012-56-browser-history-after-refresh.txt)
giữ bằng chứng UI. Hai assertion của analysis checker đã sửa theo actual contract
answered/abstained và quote prefix500; failures giữ trong command history, không
thay sản phẩm/test oracle.

**Source-open vẫn chưa đạt.** UI chỉ map canonicalUrl nếu HTTPS; nguồn
`synthetic://campus247-demo/hoc_phi/1.0.0` hiện chỉ hiện “Lưu trữ nội bộ HUCE”,
không có “Mở văn bản gốc”. Mở drawer xem embedded citation không phải một request
source-open có authorization. Knowledge source/version endpoints yêu cầu
KNOWLEDGE_ADMIN hoặc SYSTEM_ADMIN; không hạ quyền/bypass hoặc giả URI để nghiệm
thu. Browser thử exact source endpoint bị IAB `net::ERR_BLOCKED_BY_CLIENT` trước
khi có response server; không tuyên bố đã đo HTTP403. Cần đường source-open hợp
đồng và policy cho đúng actor trước khi ghi M1 completed. Đây là blocker acceptance
cụ thể còn lại, không phải thiếu quyền tăng timeout/caps.

Ledger cuối native75/76 calls,9.190/10.000 tokens,70/72 HTTP, còn1/810/2;
static338/400 requests,24.782.675/33.554.432 bytes, còn62/8.771.757;
provider8 generations/HTTP trong56, còn2/2,91.113 input/17.861 output và
USD0,2447671 conservative reservation; actual billed cost chưa biết. API/models
graceful exit0; owned Next terminated exit1, không gọi graceful Next.
[Post-stop read-only](../../infra/local/rag-fixture/acceptance-20261012-56-post-stop-preservation.json)
PASS global3/27; target12 USERs,3 ASSISTANT finals; actual rows match journal,
legacy rows/index SHA trùng52. Journal56 filenames có typo `acceptance-21261012-56`
do generator thay substring; giữ nguyên6 receipts và hash chain, created_at thật
2026-10-12. Không rename/overwrite audit. Không có automatic approval rejection.

**Kết luận: timeout blocker được tháo trong bốn retrieval có reranker + ca
no-source được đo; root mechanism vẫn chưa xác định. M1 not_verified / NO-GO vì
source-open authorization còn thiếu.** Không coi smoke1-source,9 native calls
hoặc latency sample này là full corpus/production readiness.
[Final scope56](../../infra/local/rag-fixture/acceptance-20261012-56-final-scope-corrected.json)
giữ report preimage/patch, baseline immutability, exact paths, commands/exit codes,
helper/artifact hashes và absence của owned runtime processes.

## Lượt57–58 — hoàn tất source-open trên final đã lưu, không thêm inference

Direct human yêu cầu lập plan, thực hiện và “làm triệt để cho xong đi”, cùng
DEC-023, là authority local/synthetic cho objective M1 hiện tại. Không mở M2/M3.
[Plan57](../../infra/local/rag-fixture/acceptance-20261012-57-plan.json) giữ git status,
7 exact preimages và SHA trước sửa, cùng giới hạn runtime4CPU/5GiB/900s,
DB/message/native/provider writes/calls0. Static tiếp nối338 requests/
24.782.675 bytes, tăng aggregate cap400→460 requests và32→40MiB trước chạy;
không reset counters hay xóa failed reservations.

Contract OpenAPI1.2.1 thêm API-CONV-005:
`GET /v1/conversations/{conversation_id}/messages/{message_id}/citations/{citation_id}/source`.
API conventions1.1.1 và RAG pipeline1.1.2 ghi cùng behavior. Application xác minh
ownership/retention, persisted grounded final và citation binding trước đọc chunk.
PostgreSQL adapter dùng shared retrieval prefilter publication, hiệu lực, campus,
faculty, program, audience, simulation; recheck ACTIVE/synthetic identity,
role bindings và student profile hiện hành trong read-only transaction, deadline2s.
Transport có deadline5s, signed identity, safe404/503, no-store và audit không raw
content/token. Không dùng canonical URI để fetch bên ngoài; admin knowledge API
vẫn dành cho admin. Dependency source chưa cấu hình thì fail closed503.

Chat/SSE/history truyền conversation/message/citation IDs cho drawer; nút “Mở
đoạn nguồn gốc” chỉ nhận đúng binding, kiểm toàn bộ SHA256 bằng Web Crypto,
hiển thị plaintext React-escaped cùng issuer, version, dates, locator và nhãn
simulation. Đây là **toàn bộ cited chunk**, không tuyên bố có cả tài liệu gốc chưa
được kiểm chứng. Không thay model/checkpoint/provider/threshold, không cắt history,
không chép source thành answer, không thêm DB/schema rows.

Lượt57 initial offline có21 failures/685 PASS:16 ca mới gọi nhầm identity adapter
method trong test setup; sửa thành existing `resolve_token`. Năm ca historical
runtime snapshot vẫn fail do assumptions về journal/cap gói cũ; giữ nguyên cả
tests và receipts, không sửa expected hoặc guards để ép cả repository PASS.
Scoped repair1 đạt521 PASS/1 skipped. Lượt57 build thất bại config extension,
guard syntax, rồi dependency/typecheck có pre-existing HomePage route-props;
dừng sau hai repair attempts. User yêu cầu tiếp là authority cho cycle58 mới.
Fresh cycle58 scoped build giữ nguyên mã production chat/shared layout/components,
closure đã có; bỏ các route ngoài M1 khỏi **bản sao build**, không xóa/sửa source
repository. Một repair giải quyết type resolution trong isolated copy; actual
Next16.3.8 webpack build/typecheck **PASS**, không ignoreBuildErrors. Existing
accepted local Inter font assets chỉ dùng cho font acquisition; API/SQL/nguồn
không mock. Mọi failed builds/artifacts giữ nguyên, không cleanup.

Runtime58 startup đầu fail khi guard chặn đọc lại endpoint credential sau
preflight. Sửa truyền DSN đã xác minh qua memory, không đổi guard; repair1 chạy
actual Next + signed API + PostgreSQL pool read-only. Không khởi động models,
không nạp provider credentials; owned job4CPU/5GiB, peak351.027.200 bytes.
Browser mở Q1 và Q2 trước/sau refresh: **4 authenticated200 source reads**, actual
SQL, issuer `DEMO-KNOWLEDGE-CURATION — synthetic test role`, simulation-v1,
effective2026-08-31T17:00:00Z→2027-08-31T17:00:00Z; full text SHA
`359183b1f99eb4db41816bff481048c3acf39be9dd0eb0572042c1006462b7f9`
khớp DB và cả4 DOM original-text exports. Ba accepted finals giữ nguyên nội dung,
Q3 abstained/no citations. Initial stale session401 được product demo-session
renew rồi history signed đọc thành công; không bỏ authentication.

[Live negative HTTP](../../infra/local/rag-fixture/acceptance-20261012-58-runtime-repair1-live-negative-checks.json)
đạt401 unauthenticated,404 unknown citation,404 wrong owner,403 student truy cập
admin source. [Real SQL canaries](../../infra/local/rag-fixture/acceptance-20261012-58-runtime-repair1-live-policy-canaries.json)
simulation denied/wrong faculty/program/audience/stale role đều0 rows, không
sửa DB grants. Sáu audit records có4 ALLOWED/2 DENIED, request/trace IDs nối đúng
HTTP, không log raw source hay credentials.
[Ảnh nguồn sau refresh](../../infra/local/rag-fixture/acceptance-20261012-58-browser-source-detail.png)
và [analysis58](../../infra/local/rag-fixture/acceptance-20261012-58-source-open-analysis.json)
giữ DOM, SQL/HTTP/audit, asset/input hashes và lifecycle.

Final commands dùng pinned local Python/Node/Ruff, exit0:

- `python -B infra/local/rag-fixture/m1_source_close_20261012_58.py offline repair1`:
  [521 PASS,1 skipped,15,15s](../../infra/local/rag-fixture/acceptance-20261012-58-final-offline-checks-repair1.json).
  Opt-in SQL test skipped trong offline; các live SQL canaries phía trên đã chạy.
- `python -B infra/local/rag-fixture/m1_source_close_20261012_58.py ui`:
  [27/27 PASS](../../infra/local/rag-fixture/acceptance-20261012-58-final-UI-checks.json),
  gồm history/SSE, ownership binding/checksum, denial và escaped plaintext.
- `python -B infra/local/rag-fixture/m1_source_close_20261012_58.py checks`:
  [dependency, catalog241, OpenAPI35 operations/321 refs, Ruff và scoped production
  typecheck PASS](../../infra/local/rag-fixture/acceptance-20261012-58-final-contract-lint-types-checks.json).
- [Actual scoped Next build](../../infra/local/rag-fixture/acceptance-20261012-58-source-build-repair1.json)
  exit0; [asset manifest](../../infra/local/rag-fixture/acceptance-20261012-58-source-build-assets-repair1.json)
  khớp hashes của assets đã phục vụ thật và original production source inputs.

Final offline sandbox attempt treo trước khi xuất captured result; dừng đúng owned
PIDs đã kiểm command/parent-child, không xóa artifacts. Replacement có dependency
read access, network-deny guard và hard60s deadline, đạt521/1 ở trên. Analysis
checker initial KeyError do generated build records không có `source`; sửa iteration
theo schema receipt, không đổi product/expectations. [Diagnostics giữ failures](../../infra/local/rag-fixture/acceptance-20261012-58-final-check-diagnostics.json).
Receipt offline immutable ghi nhầm suffix `-repair1` trong command metadata; actual
argument là `repair1` như command trên, results không đổi. Final scope ghi correction.
Mỗi reproduction phải dùng namespace/artifact directory mới để giữ dữ liệu cũ.

Static phát sinh36 requests; ledger nối338→**374/460**, bytes24.782.675→
**27.871.262/41.943.040**, còn86 requests/14.071.778 bytes. Native giữ75/76 calls,
9.190/10.000 tokens,70/72 HTTP; provider còn2/2,91.113 input/17.861 output tokens,
USD0,2447671 conservative reservation; actual billed cost unknown. Không thêm
messages/native/provider calls. Free-text của immutable static-authority receipt
copy nhầm cap280/32MiB; operative numeric caps400→460 và32→40MiB, actual counters
được kiểm từ36 receipts, không bypass/reset. Cycle58 helper đã retired: reset guard
còn label gốc, không relaunch repaired namespace. Lượt tiếp theo nếu có cần plan
mới nối SHA-bound ledger374; không có authority replay/reset từ packet này.

API graceful exit0, owned Next termination exit1; không gọi đó là graceful Next.
[Post-stop preservation](../../infra/local/rag-fixture/acceptance-20261012-58-runtime-repair1-post-stop-preservation.json)
đạt global3 conversations/27 messages, journal/rows/index/head0014 không đổi;
target vẫn12 USERs gồm9 historical failures và3 ASSISTANT finals. DB/container và
Docker engine giữ nguyên. [Final scope58](../../infra/local/rag-fixture/acceptance-20261012-58-source-open-final-scope.json)
giữ exact patches so với7 preimages, old53–56 artifact hashes, unrelated file
preservation, git commands và absence của owned runtime. Không commit/push/deploy/
delete/reset/cleanup; không automatic approval rejection.

**M1 completed trong one-source synthetic scope đã yêu cầu.** Baseline timeout
700/700/1.800ms → measured candidate1.600/2.100/4.700ms; reranker/gate nguyên vẹn,
Q1/Q2 grounded + follow-up/citations/source-open/refresh, Q3 no-source và error
receipts có bằng chứng. Root mechanism latency chưa được chứng minh. Whole-product
build/typecheck, năm historical snapshot failures, expanded corpus/M2/M3/pilot/
production chưa đạt hoặc chưa kiểm; không tuyên bố toàn Campus24/7 release-ready.

## Chu kỳ59 — mở M2, kiểm kê và công cụ đánh giá; paid live blocked

Người dùng trực tiếp mở M2 bằng nội dung bàn giao và cho phép **“linh hoạt ko cần
làm theo100% tài liệu ban đầu”**. DEC-023/DEC-022 là standing authority cho
engineering/review local synthetic; không xin lại task/package/signature/independent
review approval. M3/pilot/production chưa mở. Chưa có accepted M2 quality baseline;
M1 one-source smoke không thay baseline release. Giữ candidate BGE-M3 normalized1024,
BGE reranker raw logits, FP32 Microsoft ONNX Runtime1.30.0, deepseek-flash và
EvidenceGate0.78; tuple corpus/index/prompt/code mới chưa freeze.

[Baseline59](../../infra/local/rag-fixture/m2-20261012-59/baseline.json) hash15.032
pre-existing files và lưu git state; [preimage báo cáo](../../infra/local/rag-fixture/m2-20261012-59/report-preimage.snapshot)
SHA256 `907fab83689860b2633feb0cb445caed6399b87545fbb454417940063ffff733`.
Chỉ thêm3 Python files và receipts namespace mới; patch báo cáo này. Không sửa
product, schema, lockfile, fixture guard, model config hoặc dữ liệu/index M1.
Docker read-only initial bị sandbox deny; exact read-only escalated `docker ps`
exit0 không có container chạy. `docker inspect --type container campus247-rag-fixture
--format ...` exit0 xác nhận owned fixture **exited**, image SHA
`ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`.
Không relaunch cycle58, không start/reset fixture; không có runtime mới cần dừng.
Current DB preservation chưa đọc lại vì fixture dừng; không coi snapshot lịch sử
là live DB verification59. Không có automatic approval rejection.

### Input inventory và acceptance matrix

[Inventory59](../../infra/local/rag-fixture/m2-20261012-59/inventory.json) đọc development
corpus/parsed/catalog/gold đã biết, không đọc nội dung release sealed. Corpus15
documents/15 chunks synthetic: hashes raw text khớp metadata15/15; tất cả15
preview sources quarantined/unpublished, locator thiếu page hoặc `Untitled Document`
cần review. Đây là **preview cũ**, không ghi đè trạng thái một nguồn tuition đã
publish M1. Last accepted index giữ `m1-tuition-onnx-20261011-30`; current DB/index
không được kiểm chứng lại trong lượt59.

Sáu development probes validate integrity, six source versions, nhưng chỉ1 domain,
split6/0/0; không có injection/abstention/multi-turn release cases. Thiếu RAG
294/100/100 theo quota300/100/100, injection40/30/30, abstention50/25/25 và
multi-turn30/10/10. Sáu probes không phải representative release gold. Sample
course QA500 rows, grounded-abstention28, injection-privacy7, routing-tools8,
safety-handover19 chỉ inventory count/hash; chưa verify source binding, không
được cộng thành quota M2. Dataset readiness blocked, adversarial/failure coverage
của sáu probes0%, dưới20% trong research/dataset policy. Token near-duplicate
cross-split0 pairs vì không có validation/sealed; không suy semantic leakage PASS.

[Plan59](../../infra/local/rag-fixture/m2-20261012-59/plan.json) ghi13 criteria, threshold,
denominator/evidence và status not_verified: source-bound gold/splits, negative
suites, Recall@10/critical, exact-ID Recall@5, correctness/coverage, citation
precision/recall, material-claim IDs, conflict, zero source leakage/injection
bypass, abstention, repeats/CI/subgroups, M1 regression và performance. Giữ các
gates hiện hành. Local deadlines1.600/2.100/4.700ms không chứng minh TP-RAG
p95<=1.800ms/p99<=3.000ms đã đạt hoặc được miễn.

### Engineering và offline verification

[m2_readiness.py](../../evals/runners/m2_readiness.py) dùng existing canonical
gold validator rồi kiểm quota/split và source/family isolation, nguồn evidence,
adversarial coverage, actual user-turn counts và cross-split token Jaccard>=0.85.
Output chỉ counts/reason codes; `input_checks_passed` không chứng nhận taxonomy,
semantic review, publication hoặc M2 acceptance. Token overlap là review signal,
không thay semantic near-duplicate review.

Retrieval aggregator dùng **case-hit** Recall@5/@10 đúng công thức, exact-ID và
critical denominators, MRR@10, binary nDCG@10, retrieval pass@all/pass@majority.
Errors/timeouts vẫn trong retrievable denominator; absent attempts làm
not_verified/no metrics; duplicate/unplanned attempts hoặc invalid ranks fail
closed. Semantic repeats, claim/citation/abstention graders, bootstrap CIs và
live canonical SQL/pipeline integration **chưa triển khai/kiểm chứng đủ**.
Đây là công cụ phục vụ M2, không kết quả M2 hoặc production release gate.

Commands dùng existing pinned Python3.12.14/Ruff0.16.10, không thêm dependencies:

- Guarded `scripts/verify_dependencies.py`: exit0, pins/closure/sources/checksums PASS.
- Guarded `tasks/tools/validate_catalog.py`: exit0,241 tasks PASS.
- Guarded `contracts/tools/validate_openapi.py`: exit0,35 operations/321 refs PASS.
- `python -B infra/local/rag-fixture/m2_intake_20261012_59.py inventory`: exit0;
  integrity checks chạy được, **dataset readiness blocked**, không gold acceptance.
- Cùng helper `plan`: exit0; acceptance/budget/continuation plan xuất được,
  không authority để chạy paid suite khi financial cap null.
- Cùng helper `offline`: final exit0, **47 PASS/1,41s**, gồm existing gold integrity
  và18 new denominator/rank/quota tests, network denied, không release sealed data.
  [Receipt](../../infra/local/rag-fixture/m2-20261012-59/offline-repair2.json).
- Ruff `check --no-cache --select E4,E7,E9,F,I` trên3 new Python files: final exit0,
  [receipt](../../infra/local/rag-fixture/m2-20261012-59/lint.json).

Initial pytest startup bị guard chặn default TemporaryFile ngoài workspace,
chưa collection. Repair1 dùng sys capture; pytest logging tiếp tục bị chặn khi
ghi os.devnull ngoài workspace. Repair2 tắt unused logging plugin trong invocation,
giữ sys capture/no cache và exclusive basetemp mới;47 PASS. Guard không đổi,
không sửa expectations hoặc gọi fake result là live. Giữ
[initial failure](../../infra/local/rag-fixture/m2-20261012-59/offline-first-startup-failure.json),
[repair1 failure](../../infra/local/rag-fixture/m2-20261012-59/offline-second.json),
script preimage và mọi artifacts. Initial lint I001 import spacing/order sửa
bằng scoped patch; final PASS. Không có cleanup hoặc delete.

Initial scope verification exit1 vì unchanged audit guard từ chối đọc một
protected configuration file trong baseline. Giữ
[diagnostic](../../infra/local/rag-fixture/m2-20261012-59/scope-first-failure.json);
không bypass guard. Scoped verification repair loại đúng1 protected path khỏi
content reads, ghi credential hash verification **not_verified**, và kiểm15.030
pre-existing noncredential files còn lại (trừ owned report). Read targets vẫn
canonical; new receipts exclusive. [Final lint](../../infra/local/rag-fixture/m2-20261012-59/lint-final.json)
exit0 sau scope repair. Giữ helper preimage và hash receipt trước repair;
final artifact hashes được ghi riêng, không ghi đè evidence cũ.

### Budget, blocker và continuation

Provider ledger56 SHA-bound giữ2 generations/2HTTP,91.113 input/17.861 output
tokens, USD0,2447671 remaining conservative reservation; actual billed cost
unknown. Native giữ75/76 calls,9.190/10.000 tokens,70/72HTTP; static predecessor58
374 requests/27.871.262 bytes. Không reset counters hoặc failed reservations.
Plan nối hashes của provider56/native56/static58; không tạo ledger chạy mới.

Pricing `deepseek-flash` peak cache-miss inputUSD0,30/M và outputUSD1,20/M được
đối chiếu12/10/2026 tại [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/).
Provisional envelope750 separate cases×3 repeats +30 diagnostic turns +150
extra multi-turn turns +3 M1 turns =**2.433 turns**, tối đa9.732 generation và
9.733 provider HTTP. Giả định reservation32.000 input/call và2.200 output/turn
tạo pessimistic ceiling311.424.000 input/5.352.600 output tokens, **USD99,85032**.
Đây là ceiling giả định phục vụ planning, **không forecast bill, không budget
đã cấp và không exact launch plan**. Chưa tính semantic-judge calls bổ sung;
phải derive actual payload/token plan và toàn bộ grader costs trước live.
Exact batch counts/native/static/message caps và whole-run deadline còn phải
chốt sau dataset freeze. CPU4/5GiB, concurrency1 và batch/controller600/900s là
candidate baseline cho mỗi batch, không deadline toàn benchmark.

**Exact human-input blocker:** chưa có trần chi phí DeepSeek cho chu kỳ M2;
đã hỏi trực tiếp số USD, chưa nhận câu trả lời trong lượt59. Direct delegation
không biến thông tin chi phí thiếu thành quyền chi vô hạn. Chưa gọi paid API.
Thông tin tối thiểu cần người dùng cung cấp: hạn mức USD toàn chu kỳ. Các gap
corpus/gold review, isolated sealed execution, additive index, live runner/full
graders/repeats/CIs là engineering remaining, không cần task approval mới.
Sau khi có cap, hoàn thiện các bước đó và derive plan nằm trong cap; budget
không tự biến dữ liệu development thành gold hoặc gate thành PASS.

New provider/native/model HTTP/static calls0, DB writes0, messages0; không thay
conversation M1 hoặc runtime đang dừng. [Final scope59](../../infra/local/rag-fixture/m2-20261012-59/final-scope.json)
ghi kiểm hashes pre-existing files, git diff/status và exact scope. **M2 blocked /
not_verified, chưa có actual quality run; M1 completed giữ historical scope,
whole-product build/five historical snapshot failures/M3/production chưa đạt.**

## Lượt60–62 — cap1 USD, diagnostic live đa nguồn và blocker latency

Người dùng trả lời **1 USD cho toàn chu kỳ M2**. Thông tin này thay trạng thái thiếu
financial cap của lượt59; không cộng thêm1 USD vào remaining M1 và không reset các
failed reservations. Direct flexibility + DEC-022/023 cho phép implementation,
review kỹ thuật và synthetic additive index trong scope; không đổi quality gates,
EvidenceGate0.78, authorization/confirmation hoặc bảo toàn dữ liệu.

### Đầu vào và đường chạy thực tế

Tạo8 tài liệu original, ghi rõ dữ liệu mô phỏng, thuộc academic, administrative,
exam, library, facilities, IT, complaints và privacy. Mỗi nguồn có một fact số,
exact document identifier, checksum, source/version/chunk IDs và locator trang1 /
Điều1.8 case development được đóng băng trước mỗi candidate, dự kiến3 repeats =24
turns. Đây là diagnostic nhỏ do executor review, **không phải500 release gold hoặc
dev/validation/sealed split**, không đọc release sealed content. Xem
[corpus62](../../infra/local/rag-fixture/m2-20261012-62/corpus.json),
[plan62](../../infra/local/rag-fixture/m2-20261012-62/plan.json) và
[freeze62](../../infra/local/rag-fixture/m2-20261012-62/freeze-final.json).

Pinned BGE-M3 normalized1024, BGE reranker FP32 raw logits, signed ONNX C API1.30.0
và DeepSeek non-thinking đều chạy thật. Canonical Postgres lexical/vector adapters
lấy candidates bằng SQL có trusted tenant/campus/audience/faculty/program filters;
không injected candidates hoặc fake model. App chạy lifespan/authenticated ASGI
SSE, ConversationRepository thật và EvidenceGate thật. Cả hai candidate dùng đúng
immutable profile với local overlay1600 native /2100 adapter /4700 canonical ms;
batch600s/controller900s, owned job4 physical CPU/5GiB và concurrency1. Đây không
phải browser verification hoặc production performance acceptance.

Schema riêng `m2_20261012_61` và `m2_20261012_62` giữ mỗi schema8 sources/versions/
chunks và một profile/manifest/active pointer. Chỉ CREATE/INSERT mới trong schema
synthetic này; public index `m1-tuition-onnx-20261011-30` không bị promote/replace.
Candidate vectors đến từ checkpoint HTTP thật và được kiểm normalized1024.
Schema60 chưa tạo vì preparation dừng trước insert. Không chạy migrations hoặc
đổi runtime/safety/backup guards; không commit/push/deploy/delete/reset/cleanup.

### Các lượt lỗi và hai hướng sửa

1. Lượt60: trả về4/8 document embeddings rồi nguồn thứ5 bị `EmbeddingTimeoutError`
   ở adapter2100ms. Native inference vẫn hoàn tất172ms, nhưng reservation phase
   bị giữ2079,9ms và response tới sau client cancellation. Helper chưa đọc pipe
   stdout của native process liên tục; pipe đầy làm print/flush giữ request.
   Không paid calls, không DB schema hoặc conversations mới. Giữ
   [failure60](../../infra/local/rag-fixture/m2-20261012-60/worker-failure.json) và
   [phases60](../../infra/local/rag-fixture/m2-20261012-60/native-server-phases-80.json).
2. Repair1/lượt61: thêm continuous stdout/stderr drains giới hạn4MiB mỗi stream,
   reuse SSL context và kế thừa ledger80 native calls/9376 tokens/80HTTP. Guards,
   model và deadlines giữ nguyên.8 document embeddings và additive index PASS;
   academic/administrative có2 grounded finals đúng. Exam case thứ3 phát
   `message.failed`; reranker native shape8×60 vượt1600ms, canonical báo
   `RerankerContractError` từ HTTP503.8 paid generations, usage reservation
   USD0,0015135. Giữ
   [derivation61](../../infra/local/rag-fixture/m2-20261012-61/derivation.json),
   [native timeout94](../../infra/local/rag-fixture/m2-20261012-61/native-native-measurement-94.json)
   và [failed case](../../infra/local/rag-fixture/m2-20261012-61/case-EVAL-M2DIAG-003-1.json).
3. Repair2/lượt62: dùng session option `session.dynamic_block_base=4` theo
   [official ONNX Runtime guidance](https://onnxruntime.ai/docs/performance/tune-performance/troubleshooting.html)
   để thử giảm latency variance. Không đổi model precision/artifact, số CPU/RAM,
   timer/deadlines hoặc scope filters. Kế thừa native94/11137/108HTTP và paid ledger
   của61, không reset cost/calls.5 câu đầu có grounded finals đúng; IT case thứ6
   tiếp tục native reranker timeout, không có completed final. **Dừng sau repair2**,
   không retry thêm hoặc chọn bỏ failed IDs. Giữ
   [derivation62](../../infra/local/rag-fixture/m2-20261012-62/derivation.json),
   [retrieval failure6](../../infra/local/rag-fixture/m2-20261012-62/retrieval-006.json) và
   [failed case](../../infra/local/rag-fixture/m2-20261012-62/case-EVAL-M2DIAG-006-1.json).

Controller exit0 của61/62 chỉ có nghĩa helper kết thúc theo stop policy và giữ
receipts, **không có nghĩa diagnostic/suite PASS**. Lượt60 controller exit1.

### Kết quả, tài chính và bảo toàn dữ liệu

[Aggregate analysis](../../infra/local/rag-fixture/m2-20261012-62/analysis.json) ghi
9 actual turns qua hai candidates:7 answered grounded với exact fact số/identifier,
simulation label, source/version/chunk/quote checksum/locator và turn citation
marker khớp;2 failed turns không bị loại. Các kiểm tra này phù hợp8 facts đơn giản,
không thay semantic judge, claim-level broad benchmark hoặc full gold acceptance.
Candidate cuối có5 passes/6 observed turns, **18/24 planned turns chưa chạy**.
Aggregator trả `not_verified`, `metrics: null` khi thiếu attempts; không tuyên bố
Recall/CIs/pass@all/pass@majority hoặc3 semantic repeats đã đạt. Preparation60
timeout vẫn được giữ riêng, không tính như một chat turn đã chạy.

PaidBudget giữ Decimal accounting, reserve input UTF-8 payload bytes+512 và
max_output_tokens trước HTTP, fail/unknown usage giữ toàn reservation, chỉ usage
được kiểm mới hoàn phần dư; attempts không hoàn lại. Continuation settled ledger
phải giữ cùng financial cap và khớp token/cost; reject unsettled/cost drift/cap
change. Gateway kiểm EgressPolicy, actual model/non-thinking, route/output/deadline
và không tự retry. Worst additional24-turn reservationUSD0,86976 nằm dưới cap1
sau prior usage, nhưng deadline failure dừng diagnostic trước giới hạn tài chính.

Whole-M2 **25 paid calls**,9723 input/1775 output tokens; conservative peak
cache-miss usage cost **USD0,0050469**, remaining **USD0,9949531/1**. Tất cả paid
usage đã settle, không pending unknown usage; actual billed invoice chưa xác minh.
17 calls mới của62 cộng8 của61, ledger62 SHA-bound predecessor61 rồi M1 ledger56.
Không gộp khoản M1 còn lại thành quyền chi thêm. Xem
[provider ledger62](../../infra/local/rag-fixture/m2-20261012-62/provider-final-ledger.json).
Native cumulative114 calls/14374 tokens/148HTTP, gồm39 calls/5184 tokens/78HTTP
mới so với M1; cả timeout/canceled transport vẫn tính. Latest finite caps160 calls/
50000 tokens/220HTTP. Static acquisition requests mới0; predecessor374 requests/
27871262 bytes giữ nguyên. Không download model/dependencies mới.

[Read-only DB preservation](../../infra/local/rag-fixture/m2-20261012-62/DB-preservation-final.json)
PASS: public tất cả row/index hashes và active pointer khớp trước/sau; vẫn3
conversations/27 messages. Schema61 có3 conversations/5 messages, schema62 có6/
11;7 persisted ASSISTANT finals khớp SSE,2 failed USER messages được giữ. Candidate
schemas, SQLite và receipts giữ nguyên để audit. Native owned processes exit0,
đúng fixture container đã stop và volume giữ lại, trở về stopped baseline.

### Verification và phần còn thiếu

Guarded dependency/catalog/OpenAPI preflights chạy trước60/61/62 đều exit0.
Initial guarded tests59 PASS/1,70s; sau thêm continuation-budget checks, final
**62 PASS/1,52s** gồm15 budget tests +47 readiness/gold tests, network denied.
[Offline final receipt](../../infra/local/rag-fixture/m2-20261012-62/offline-final.json).
Ruff full rules trên PaidBudget/tests/analysis PASS; native-derived helpers và
diagnostic harness syntax/undefined-name checks `E9,F63,F7,F82` PASS. Full style
lint của initial harness có13 findings, inherited native có2 findings, giữ
phân biệt này; không tuyên bố full helper lint PASS. Đã kiểm actual DB finals và
hashes; global scope/diff/hash evidence ghi tại
[final scope62](../../infra/local/rag-fixture/m2-20261012-62/final-scope.json).

**Blocker hiện tại là native reranker latency/stability sau hai hướng sửa, không
phải thiếu financial cap. M2 blocked/not_verified.** Full500 source-bound gold,
300/100/100 isolated splits, injection/abstention/multi-turn suites, sealed runs,
3 repeats/CIs/subgroups, M1 regression browser và production percentile gates
chưa hoàn thành. Ngân sách còn lại không biến diagnostic thành M2 acceptance.
M1 historical completed giữ nguyên; M3/pilot/production chưa mở.

## Lượt63 — giải thích timeout và đính chính lần sửa2

Đối chiếu read-only theo câu hỏi người dùng; không resume fixture, chạy model hoặc
gọi provider. Giữ nguyên report preimage0.4.32 và mọi receipts60–62. Nội dung dưới
đây **đính chính nhận định “hai hướng sửa khác nhau” ở lượt62**, không đổi số lượt,
usage, failure evidence hoặc nghiệm thu.

Timeout cuối phát sinh trong native reranker Run, shape8×63,487 actual tokens,
FP32 và4 physical CPU. Timer đặt1600ms; native terminate được yêu cầu khoảng1611ms,
Run thoát sau1670ms, gồm thời gian dừng. Đây là lượt bị hủy, không phải completion
time1670ms của một kết quả thành công. Native process dùng5,59375 CPU-seconds trong
khoảng1,67 wall-seconds, cả4 inference threads hoạt động; working set khoảng3,07GB,
dưới cap5GiB. Tokenization1,09ms, reservation/logging3,94ms, response write0,06ms;
tắc pipe preparation60 đã được tháo. Actual SQL lexical/vector đều trả candidates;
canonical nhận HTTP503 từ native timeout và phát dependency failure.
[Native measurement114](../../infra/local/rag-fixture/m2-20261012-62/native-native-measurement-114.json)
và [server phases148](../../infra/local/rag-fixture/m2-20261012-62/native-server-phases-148.json).

**Sai sót của executor:** `m1_cpu_20261011_34.CPU.CONFIG` đã có
`session.dynamic_block_base=4`; các lớp affinity/spin kế thừa giữ key/value này.
Subclass CPU của62 thêm lại đúng cùng option. Effective CONFIG61 và62 giống nhau,
hash session config của cả hai measurements là
`f2c3a2c0946e37c907bd9db038c89766b90f5417717f990fe3fbf2a94f098a3e`.
Vì vậy trial62 **không chứng minh một tối ưu scheduling mới đã được áp dụng**;
5 case chạy được trước lỗi không phải bằng chứng hiệu quả của option đó. Có hai
lần thử sửa được ghi, nhưng chỉ repair1 tạo thay đổi thực tế cho nguyên nhân đã đo.

Kết luận đã đo: deadline1600ms chưa được đáp ứng ổn định cho workload rerank8
candidates trên runtime CPU FP32 hiện tại. Chưa đủ evidence phân biệt các đóng góp
cụ thể của cache, memory bandwidth, CPU scheduling hoặc host interference; page
fault counts không chứng minh disk I/O. Hướng xử lý cần benchmark workload/resource
và chọn thay đổi thực tế; nếu dùng deadline development khác phải ghi rõ và tiếp
tục giữ production quality/performance gates riêng. Không tự coi tăng timeout là
performance acceptance. Financial usage vẫnUSD0,0050469/1 và M2 not_verified.

## 64 — Timeout tăng theo yêu cầu trực tiếp;24 lượt thực tế hoàn tất

Authority: người dùng trực tiếp yêu cầu “nâng timeout lên”; DEC-023 cho phép
engineering và synthetic live checks. Giữ cap **1 USD cho toàn M2**, tiếp tục
ledger62 thay vì đặt lại ngân sách. Không sửa model, checkpoint, CPU scheduling,
EvidenceGate0.78, authorization, production profile hoặc performance gates.

| Deadline local/synthetic | Trước | Lượt64 |
|---|---:|---:|
| Native ONNX Run |1600ms|3000ms|
| Embedding/reranker HTTP adapter |2100ms|4000ms|
| Canonical retrieval |4700ms|8500ms|

[Cấu hình duy nhất](../../infra/local/rag-fixture/m2-20261012-64/runtime-config.json)
được nối tới timer/cancellation native, measured session, model server, adapters
và bootstrap profile. [Freeze](../../infra/local/rag-fixture/m2-20261012-64/freeze-final.json)
ghi hashes và effective bindings trước chạy. Overlay chỉ cho development demo;
production/staging không được dùng. Giữ native cancellation/join/output discard,
CPU4 physical cores, RAM5GiB, một lượt đồng thời, batch600s/controller900s.

**Timeout đã tháo trong diagnostic đo được:**8 documents embedding và24 lượt
query embedding/reranker hoàn tất,56 native calls mới thành công.24/24 lượt qua
actual SQL lexical/vector, signed ASGI SSE, DeepSeek classifiers/generation và
EvidenceGate;24 facts, source/version/chunk/quote/locator/turn-marker bindings
đúng.24 finals/citations khớp PostgreSQL,24 conversations/48 messages trong schema
additive `m2_20261012_64`;8 vectors1024 normalized. Không có fake retrieval hoặc
pre-supplied candidates. Reranker native Run1269,4478–2409,5115ms,11/24 lần vượt
1600ms cũ nhưng đều dưới3000ms mới. Đây là timeout tolerance của workload local,
chưa phải nghiệm thu production latency hoặc tối ưu tốc độ inference.
[Timing verification](../../infra/local/rag-fixture/m2-20261012-64/timeout-verification.json)
và [DB preservation](../../infra/local/rag-fixture/m2-20261012-64/DB-preservation-final.json).

**Diagnostic không hoàn toàn đạt:**21/24 đạt toàn bộ tiêu chí đã frozen.
`EVAL-M2DIAG-008` ở cả3 repeats trả đúng9 ngày và citation đúng, nhưng nội dung
answer thiếu cụm “mô phỏng”; citation quote/title/status vẫn có nhãn synthetic.
Giữ3 failures này trong [analysis](../../infra/local/rag-fixture/m2-20261012-64/analysis.json),
không đổi matcher/threshold hoặc ghi chúng thành PASS. Full gold500, release
split, injection100, abstention100, multi-turn50 và M3 vẫn **not_verified**.
Historical2 failed turns và preparation timeout60 vẫn giữ nguyên riêng biệt.

**Chi phí và caps:**72 provider requests mới,97 whole-M2 calls;42.312 input/
6.964 output tokens lũy kế. Conservative usage costUSD0,0210504, cònUSD0,9789496
trong cap1 USD; actual invoice unknown, không còn unsettled reservations.
Native cumulative170/180 calls,26.458/50.000 tokens,260/280 HTTP. Static requests
mới0; historical374 requests/27.871.262 bytes giữ nguyên.
[Ledger](../../infra/local/rag-fixture/m2-20261012-64/provider-final-ledger.json).

**Verification:** preflight dependencies/catalog/OpenAPI PASS;44 offline tests
PASS2,79s gồm timer2s vượt deadline cũ, cancellation sau3s, propagation, guard
production và budget ledger. Các test harness thất bại/treo được giữ: lần đầu
thiếu owned temp/SQLite; Windows socketpair bị chặn trong sandbox khi tạo event
loop; lần chạy cuối cho phép IPC Windows, giữ audit/network/deletion guards và
test expectations. Helper DB verify lần đầu thiếu biến exact SQLite cho guard,
dừng trước SQL; lần sửa cấu hình chạy read-only PASS, có preimage/failure receipt.
Không tính các lỗi harness thành model/provider calls.
[Offline final](../../infra/local/rag-fixture/m2-20261012-64/offline-final4.json).

Public M1 vẫn3 conversations/27 messages, index `m1-tuition-onnx-20261011-30`,
mọi public rows/indexes giữ hash. Schemas61/62 và messages cũ giữ nguyên hashes.
Native processes exit0; exact owned fixture stop PASS, volume và schema64 giữ.
Không commit, push, deploy, delete, reset hoặc cleanup dữ liệu. Kiểm tra scope
và lịch sử báo cáo được lưu ở [final scope](../../infra/local/rag-fixture/m2-20261012-64/final-scope.json).

## 65–71 — Full synthetic benchmark đã quan sát; M2 chưa đạt do21 lỗi hội thoại

Authority: người dùng cho phép tự xử lý M2 linh hoạt, yêu cầu nâng timeout và
đặt **1 USD cho toàn chu kỳ M2**; DEC-023/DEC-022 là standing local authority.
Không production/real-data access, commit, push, deploy, reset hoặc cleanup.
Không thay requirements, expected facts, EvidenceGate0.78 hoặc ngưỡng nghiệm thu.

**Phạm vi và dữ liệu.** Gold giữ nguyên SHA từ65:500 core (300dev/100validation/
100 designated test),100 abstention,120 injection gồm100 direct +20 indirect,
50 hội thoại hai lượt,48 biến thể ngôn ngữ và8 regression. Validation core ×3,
các bộ guard/variant/regression/multi ×3; tổng1.828 lượt. Corpus628 chunks/
628 versions/608 source IDs có8 domains. Source IDs riêng giữa các split nhưng
8 mẫu scalar được dùng chung: không coi các family là độc lập về ngữ nghĩa,
không có niêm phong/review độc lập và không suy rộng Wilson intervals của các
lượt lặp thành chất lượng QA tự nhiên. [Gold/corpus verification](../../infra/local/rag-fixture/m2-20261012-71/dataset-final-verification.json).

SQL lexical/vector, authorized filters, RRF và rerank dùng nguồn thực; BGE-M3
1024 normalized FP32 và bge-reranker-v2-m3 chạy checkpoint thật qua signed
Microsoft ONNX Runtime1.30 C API/TEI-compatible local endpoints. Không tuyên bố
đã chạy original TEI executable. Native FP32 parity được đối chiếu, nguồn/vectors
được reuse có hash và read-only SQL verification. Signed actor và current source
grants được kiểm tra; source bị expired/withdrawn/unauthorized/conflict không
lọt vào câu trả lời. Bulk dùng actual application objects;41 lượt có HTTP/SSE,
2.043 lượt ở application layer, không coi tất cả là HTTP coverage.

**Thay đổi nhỏ trong application.** Server thêm nhãn mô phỏng sau khi citation
được xác minh theo synthetic source_status, sửa3 privacy misses ở64. Explicit
document IDs lọc theo trusted metadata trước RRF truncation, không theo source
body. Non-crisis instruction-override trả safe refusal thay cho handover notice
chưa có durable queue; true-crisis branch giữ nguyên và không chứng nhận M3.
Classifier/intent deadlines tăng2.000→5.000ms; generation vẫn5.000ms. Question
reference dùng user goals đã xác minh ownership, không coi assistant history
là chứng cứ. Formatting policy đưa notice ra ngoài claim để server render.
Các authorization/confirmation/source checks và model output caps giữ nguyên.

Native deadline3.000ms, adapter5.000ms, retrieval10.500ms được nối tới typed local
config, native cancellation/output discard và bootstrap. Retrieval overlay bị
từ chối ở production/staging. CPU4 physical cores, RAM5GiB, batch600s/controller
900s, provider cap6.500 calls, native cap18.000 attempts/6 triệu tokens/10.000
HTTP không đặt lại. Metadata cache ở71 chỉ giữ byte response của GET `/info` thật
trong lifetime của owned frozen model server; mỗi adapter vẫn kiểm model identity,
mỗi embed/rerank vẫn gửi POST thật, không cache inference output hay model answer.
[Freeze71](../../infra/local/rag-fixture/m2-20261012-71/freeze-final.json) và
[component equivalence](../../infra/local/rag-fixture/m2-20261012-71/component-equivalence.json).

**Các lượt lỗi được giữ.**65 rollback candidate install do enum role không hợp
lệ, không mất public dữ liệu.66 có8 grounded finals rồi dừng ở HTTP429;67 tách
finite bulk khỏi HTTP smoke, giữ nguyên rate limit.68 quan sát1.550/1.828 lượt,
dừng ở một output rỗng;71 lỗi gồm60 handover notices chưa đúng refusal contract,
10 wrong abstentions và1 invalid claim,278 khóa chưa chạy.70 sửa security và
history formatting, chạy384 lượt:240 đạt,144 follow-ups chưa đạt.71 sửa policy
xung đột và chọn resolvable user goal, chạy150 follow-ups bổ sung:129 đạt,
21 `INVALID_CLAIM_FORMAT`/`AI_GENERATION_UNAVAILABLE`, không có native/retrieval
failure. Provider21 lượt này exit0/finish stop; claim rỗng không được tính thành
successful abstention. Sau hai lần sửa hội thoại, dừng với evidence theo execution
contract. Các draft/harness failures và mọi paid reservation được giữ, không replay
các batch cũ, refund unknown usage hoặc bỏ failing keys.

| Bộ kiểm tra, evidence mới nhất | Đạt / tổng |
|---|---:|
| Core500 và validation repeats |700/700|
| Ngôn ngữ không dấu/typo/slang |144/144|
| Abstention, gồm conflict |300/300|
| Direct/indirect injection |360/360|
| Regression8 domains |24/24|
| Multi-turn, tính từng lượt |279/300|
| Hội thoại đủ các lượt đạt |129/150 (86%; yêu cầu90%)|
| Toàn benchmark |1.807/1.828|

Recall@10, critical recall, exact-ID@5, grounded correctness trên các answer đã
trả, citation precision/recall, negative abstention và conflict đều1,0 trong
benchmark hẹp này. Coverage1.147/1.168 (98,20%). Invalid-source leakage và injection
bypass0. Tuy nhiên no-pipeline-failure, multi-turn acceptance và every-corrective-
turn gates đều FAIL: **M2 not_verified**, không có GO dựa vào điểm trung bình.
[Closure](../../infra/local/rag-fixture/m2-20261012-71/M2-closure.json) ghi provenance
1.444 reference +234 retained repair70 +150 fresh follow-ups71. Không gọi đây
là full replay của final build; toàn bộ71 failures reference và144 failures70 còn
ở artifacts,21 lỗi mới có [receipt riêng](../../infra/local/rag-fixture/m2-20261012-71/remaining-defects.json).

**Chi phí và vận hành.** Whole-M2:5.833 provider calls,1.540.793 input/394.603
output tokens charged, USD0,9357615 conservative peak cache-miss pricing. Còn
USD0,0642385 trong cap1 USD; actual account invoice unknown. Unknown ordinals
581/662/2177/4376/4378 giữ full reservations; không phát sinh unknown mới ở71.
Native lũy kế5.145 attempts/204.674 tokens/9.886 HTTP. Static acquisition vẫn374
requests, không thêm request ở chu kỳ cuối. Analysis reference+repair có3.697
native runs đều đạt: max2.219ms dưới3.000ms; retrieval median485ms/max3.359ms.
Không dùng các timing này để chứng nhận production SLO.
[Runtime/cost analysis](../../infra/local/rag-fixture/m2-20261012-71/final-runtime-analysis.json).

**Verification và bảo toàn.**756 offline tests PASS10,56s, scoped lint PASS và
không thêm diagnostics vào definitions đã dirty từ trước. First offline71 giữ
2 failures về URL metadata, sửa normalization rồi chạy lại; không đổi expectations.
Preimage snapshots và AST proof giữ nguyên functions ngoài scoped changes,
704 frozen paths70 được đối chiếu với snapshots trước71. Test/network/endpoint/
deletion guards được giữ; Windows IPC cần unsandboxed tool execution đã qua
automatic review, không có approval rejection hoặc provider call ở offline tests.
[Offline recheck](../../infra/local/rag-fixture/m2-20261012-71/offline-recheck.json),
[lint](../../infra/local/rag-fixture/m2-20261012-71/final-lint.json).

Read-only SQL audit: public3 conversations/27 messages và mọi public table/index
hash giữ nguyên; schemas61/62/64 giữ nguyên;66 có8 finals/16 messages;67 có1.773
conversations/4.132 messages gồm toàn bộ lỗi cũ.2.048 stored finals khớp receipts,
36 lượt không có final vẫn được giữ.628 source chunks/content checksums/vectors
FP32 giữa66/67 trùng; failed schema65 không tồn tại do transaction rollback.
[DB preservation](../../infra/local/rag-fixture/m2-20261012-71/final-DB-preservation.json).
Owned native jobs và fixture đã dừng; [stop receipt](../../infra/local/rag-fixture/m2-20261012-71/owned-fixture-stop.json)
giữ volume/data. [Final scope](../../infra/local/rag-fixture/m2-20261012-71/final-scope.json)
đối chiếu15.027 pre-existing noncredential files, exact owned diffs và nguyên
vẹn từng byte phần lịch sử báo cáo. Credential files được loại khỏi việc đọc/hash;
không tuyên bố đã xác minh nội dung credential.


## 73 — Hội thoại mới đủ hai lượt; M2 local/synthetic not_verified

Người dùng trực tiếp mở vòng sửa mới sau hai lần trước và cấp quyền tự chọn
finite caps cần thiết cho M2. Áp dụng DEC-023; không production/real-data,
destructive operation, commit, push hoặc deploy. Namespace72/proposal và mọi
artifacts/helpers frozen trước73 được giữ. Source preimages lưu trước sửa;
toàn bộ nội dung báo cáo trước mục này được giữ nguyên từng byte.

**Engineering.** Câu nối tiếp được biểu diễn bằng current_request,
resolved_request và reference_target từ user goal đã kiểm ownership. Giữ nguyên
điều kiện/yêu cầu mới, không thay câu mới bằng câu cũ. Reference mơ hồ giữa nhiều
văn bản hoặc explicit topic switch không tự chọn nguồn cũ. Current source scope,
retrieval và EvidenceGate vẫn xác minh dữ kiện. Với reference giải quyết được,
generation không gửi passive assistant history; user goal là dữ liệu tham chiếu,
không phải chứng cứ hay quyền truy cập. Initial/no-history request và successful
grounded-draft return được đối chiếu AST với preimage, giữ nguyên.

Phân biệt completed empty output, empty JSON claims, schema-invalid và timeout
bằng allowlisted reason codes trong state. Parser vẫn bác claims rỗng; failure
không trở thành grounded final hoặc successful abstention. Mỗi lượt có tối đa
một generation call, không retry trả phí hoặc source-copy/gold fallback. Offline
ablation có/không có lời từ chối assistant cho payload mới giống hệt; chưa chứng
minh assistant history là nguyên nhân độc lập của21 lỗi cũ. Không suy causal
conclusion từ before/after gồm nhiều thay đổi.

**Live và provenance.** Chạy đủ50 hội thoại ×3 repeats, hai lượt trong150
conversations mới;300 lượt mới, gồm12 HTTP/SSE và
288 application-layer turns. Mọi grounded citation
được mở lại từ current authorized source, checksum và persisted final được kiểm.
SQL lexical/vector/RRF dùng corpus628 chunks/608 nguồn cũ; inference BGE-M3 và
bge-reranker-v2-m3 thật qua ONNX C API. /info cache chỉ trong lifetime của từng
owned frozen runtime; mỗi inference gửi POST thật. Giữ native3000ms,
adapter5000ms, retrieval10500ms, classifier/intent/generation5000ms, CPU4/RAM5GiB.

| Bộ kiểm tra, evidence mới nhất | Đạt / tổng |
|---|---:|
| Core và validation repeats |700/700|
| Multi-turn, từng lượt mới |296/300|
| Hội thoại đủ hai lượt mới |146/150|
| Toàn bộ benchmark |1824/1828|

M2 status **not_verified** theo toàn bộ gates giữ nguyên, còn
4 failing keys. [Closure](../../infra/local/rag-fixture/m2-20261012-73/M2-closure.json)
Vòng73 còn4 facilities follow-ups bị LOW_SUPPORT: citation hợp lệ, lexical
overlap7/9=0,77778 dưới0,78. Pipeline không lỗi nhưng từ chối thay grounded answer
vẫn là quality FAIL; every_corrective_turn_passed chưa đạt, không GO dựa vào97,33%.
và [provenance từng khóa](../../infra/local/rag-fixture/m2-20261012-73/benchmark-provenance.json) ghi300 keys replay73,
84 successful nonhistory repair70 và1444 successful nonhistory reference keys.
1528 keys reuse có input/component equivalence và current-source/DB preservation;
không gọi đây là một full1828-turn replay của final build. Original21 empty-claim
failures và các failure/reservation receipts trước vẫn nguyên trạng.

**Chi phí.** [Cap migration](../../infra/local/rag-fixture/m2-20261012-73/cap-migration.json) nối ledger71, tăng tổng
cap1→1,25 USD, provider6500→7500, native HTTP10000→11000; không reset calls,
tokens, chi phí hoặc unknown reservations. Whole-M2 cuối: 6733 calls,
USD1.0945269 bảo thủ, cònUSD0.1554731.
Unknown581/662/2177/4376/4378 giữ nguyên records và full caps; actual invoice
unknown. Native cumulative 5748
attempts/229810 tokens/
10498 HTTP. Không cần tăng caps tiếp.
[Runtime analysis](../../infra/local/rag-fixture/m2-20261012-73/final-runtime-analysis.json): max native
1484.000ms, max retrieval2141.000ms;
không chứng nhận production latency SLO.

**Verification.** Dependencies/catalog/OpenAPI exit0;793 offline tests PASS;
scoped application lint và comparison với preexisting dirty/derived helpers
không thêm diagnostics. Giữ các inherited helper style diagnostics. Initial
sandbox offline bị treo không có output, dừng owned process; unsandboxed Windows
IPC giữ network/credential/deletion guards. First collected run788 PASS/5 FAIL
do new test fixture thiếu trusted_context_ref; sửa fixture binding, giữ toàn bộ
expectations và failure receipt rồi793 PASS. Hai lint receipts lỗi được giữ;
final lint sửa đúng import formatting mới, không hạ check hoặc sửa guards.
[Offline](../../infra/local/rag-fixture/m2-20261012-73/offline-final-repair.json), [lint](../../infra/local/rag-fixture/m2-20261012-73/final-lint-final.json).

Read-only row-hash multiset audit xác minh từng preexisting row được giữ;
mọi public tables/indexes và source/vector/private schemas không đổi. Public
M1 vẫn3 conversations/27 messages; schema67 cuối
1923 conversations/
4732 messages. 2348
finals cũ+mới khớp retained receipts. [DB preservation](../../infra/local/rag-fixture/m2-20261012-73/final-DB-preservation.json).
Owned native jobs exit0 và exact fixture đã stop, giữ volume/data.
[Scope](../../infra/local/rag-fixture/m2-20261012-73/final-scope.json), [execution receipts](../../infra/local/rag-fixture/m2-20261012-73/execution-final.json).

Nghiệm thu chỉ cho original fictional scalar-rule benchmark này. Tám semantic
templates dùng chung, repeats tương quan; không suy rộng thành arbitrary real
policy QA, M3 hay production acceptance. Corpus/gold/expected facts/thresholds,
source authorization, action confirmation và mọi safety protections giữ nguyên.


## 74 — Hội thoại mới đủ hai lượt; M2 local/synthetic not_verified

Người dùng trực tiếp mở vòng sửa mới sau hai lần trước và cấp quyền tự chọn
finite caps cần thiết cho M2. Áp dụng DEC-023; không production/real-data,
destructive operation, commit, push hoặc deploy. Namespace72/proposal và mọi
artifacts/helpers frozen trước74 được giữ. Source preimages lưu trước sửa;
toàn bộ nội dung báo cáo trước mục này được giữ nguyên từng byte.

**Engineering.** Câu nối tiếp được biểu diễn bằng current_request,
resolved_request và reference_target từ user goal đã kiểm ownership. Giữ nguyên
điều kiện/yêu cầu mới, không thay câu mới bằng câu cũ. Reference mơ hồ giữa nhiều
văn bản hoặc explicit topic switch không tự chọn nguồn cũ. Current source scope,
retrieval và EvidenceGate vẫn xác minh dữ kiện. Với reference giải quyết được,
generation không gửi passive assistant history; user goal là dữ liệu tham chiếu,
không phải chứng cứ hay quyền truy cập. Initial/no-history request và successful
grounded-draft return được đối chiếu AST với preimage, giữ nguyên.

Phân biệt completed empty output, empty JSON claims, schema-invalid và timeout
bằng allowlisted reason codes trong state. Parser vẫn bác claims rỗng; failure
không trở thành grounded final hoặc successful abstention. Câu nối tiếp có tối đa
một regeneration sau empty/schema-invalid hoặc claim không đạt kiểm chứng. Hai
call chia sẻ deadline5000ms và output budget1000 tokens; từng call reserve trước
HTTP, không retry timeout/transport/cancellation hoặc source-copy/gold fallback.
Prevalidation dùng đúng threshold của graph; final EvidenceGate vẫn chạy độc lập.
Feedback chỉ dùng allowlisted reason và instruction cố định, không gửi draft cũ
hoặc đưa gold vào request. Offline
ablation có/không có lời từ chối assistant cho payload mới giống hệt; chưa chứng
minh assistant history là nguyên nhân độc lập của21 lỗi cũ. Không suy causal
conclusion từ before/after gồm nhiều thay đổi.

**Live và provenance.** Chạy đủ50 hội thoại ×3 repeats, hai lượt trong150
conversations mới;300 lượt mới, gồm12 HTTP/SSE và
288 application-layer turns. Mọi grounded citation
được mở lại từ current authorized source, checksum và persisted final được kiểm.
SQL lexical/vector/RRF dùng corpus628 chunks/608 nguồn cũ; inference BGE-M3 và
bge-reranker-v2-m3 thật qua ONNX C API. /info cache chỉ trong lifetime của từng
owned frozen runtime; mỗi inference gửi POST thật. Giữ native3000ms,
adapter5000ms, retrieval10500ms, classifier/intent/generation5000ms, CPU4/RAM5GiB.

| Bộ kiểm tra, evidence mới nhất | Đạt / tổng |
|---|---:|
| Core và validation repeats |700/700|
| Multi-turn, từng lượt mới |282/300|
| Hội thoại đủ hai lượt mới |132/150|
| Toàn bộ benchmark |1810/1828|

M2 status **not_verified** theo toàn bộ gates giữ nguyên, còn
18 failing keys. [Closure](../../infra/local/rag-fixture/m2-20261012-74/M2-closure.json)
Vòng73 có4 LOW_SUPPORT failures được giữ nguyên. Vòng74 chỉ completed nếu
mọi gate và mọi corrective turn đạt, không dựa riêng trên conversation average.
và [provenance từng khóa](../../infra/local/rag-fixture/m2-20261012-74/benchmark-provenance.json) ghi300 keys replay74,
84 successful nonhistory repair70 và1444 successful nonhistory reference keys.
1528 keys reuse có input/component equivalence và current-source/DB preservation;
không gọi đây là một full1828-turn replay của final build. Original21 empty-claim
failures và các failure/reservation receipts trước vẫn nguyên trạng.

**Chi phí.** [Cap migration](../../infra/local/rag-fixture/m2-20261012-74/cap-migration.json) nối ledger73, tăng tổng
cap1,25→1,50 USD, provider7500→8500, native HTTP11000→12000; không reset calls,
tokens, chi phí hoặc unknown reservations. Whole-M2 cuối: 7651 calls,
USD1.2632223 bảo thủ, cònUSD0.2367777.
Unknown581/662/2177/4376/4378 giữ nguyên records và full caps; actual invoice
unknown. Native cumulative 6351
attempts/254946 tokens/
11110 HTTP. Finite cap migration có reason và failure evidence trước chạy; không reset ledger.
[Runtime analysis](../../infra/local/rag-fixture/m2-20261012-74/final-runtime-analysis.json): max native
1953.000ms, max retrieval2687.000ms;
không chứng nhận production latency SLO.

**Verification.** Dependencies/catalog/OpenAPI exit0;806 offline tests PASS;
scoped application lint và comparison với preexisting dirty/derived helpers
không thêm diagnostics. Giữ các inherited helper style diagnostics. Initial
sandbox offline73 bị treo không có output, dừng owned process; unsandboxed Windows
IPC giữ network/credential/deletion guards. Lịch sử73: first collected run788 PASS/5 FAIL
do new test fixture thiếu trusted_context_ref; sửa fixture binding, giữ toàn bộ
expectations và failure receipt rồi793 PASS. Hai lint receipts lỗi được giữ;
final lint sửa đúng import formatting mới, không hạ check hoặc sửa guards.
[Offline](../../infra/local/rag-fixture/m2-20261012-74/offline-final.json), [lint](../../infra/local/rag-fixture/m2-20261012-74/final-lint-final.json).

Read-only row-hash multiset audit xác minh từng preexisting row được giữ;
mọi public tables/indexes và source/vector/private schemas không đổi. Public
M1 vẫn3 conversations/27 messages; schema67 cuối
2073 conversations/
5332 messages. 2648
finals cũ+mới khớp retained receipts. [DB preservation](../../infra/local/rag-fixture/m2-20261012-74/final-DB-preservation.json).
Owned native jobs exit0 và exact fixture đã stop, giữ volume/data.
[Scope](../../infra/local/rag-fixture/m2-20261012-74/final-scope.json), [execution receipts](../../infra/local/rag-fixture/m2-20261012-74/execution-final.json).

Nghiệm thu chỉ cho original fictional scalar-rule benchmark này. Tám semantic
templates dùng chung, repeats tương quan; không suy rộng thành arbitrary real
policy QA, M3 hay production acceptance. Corpus/gold/expected facts/thresholds,
source authorization, action confirmation và mọi safety protections giữ nguyên.


### Kiểm soát tái tạo và lỗi cuối vòng74

[Regeneration audit](../../infra/local/rag-fixture/m2-20261012-74/regeneration-audit.json)
xác minh300 turns, 918 paid reservations mới, gồm
18 regeneration calls; tối đa
4 provider calls/lượt kể cả classifier/intent.
Mỗi call reserve trước HTTP; generation dùng chung5.000ms và tổng output1.000
tokens. Actual result receipts xác minh usage và remaining caps; mọi inference
BGE-M3/reranker vẫn thật. Guard/source authorization và final EvidenceGate giữ.

Kết quả build74 là **not_verified**, 1810/1828
keys, 132/150 fresh conversations.
[Remaining defects](../../infra/local/rag-fixture/m2-20261012-74/remaining-defects.json)
giữ 18 failures sau regeneration, không tính
safe refusal thành grounded PASS. Vòng73 đạt1824/1828 và146/150; vòng74 không
được tuyên bố tốt hơn khi thực tế còn nhiều failures hơn. Hai material repairs
73/74 đã chạy; AGENTS.md execution contract yêu cầu dừng sau hai lần sửa thất
bại. Không mở lần sửa thứ ba, không đổi ngưỡng0,78 hoặc bỏ cases để đóng M2.
