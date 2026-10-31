# RAG v2 hardening — báo cáo tiến độ (2026-10-31, tối)

Nhánh: `rag-v2-hardening` (3 commit: `01c9a7013` nền, `915d6368d` P1/P2/P5, `bbdde9f3b` sửa nhỏ). Kế hoạch gốc: `PLAN-rag-v2-hardening.md`. Chưa chạm runtime 8015 và chưa gọi DeepSeek lần nào; runtime vẫn chạy v1, cờ vẫn là v1.

Bằng chứng là gì: test xác định với gateway/embedding giả và dữ liệu tổng hợp, đáp án kiểm bằng mã; chưa có phép đo đầu–cuối bằng mô hình thật sau các sửa này; chưa đo người dùng thật.

## Trạng thái hiện tại
- `tests/rag_v2` + `tests/evals/test_rag_v2_*` + `tests/contract/test_rag_v2_citations.py` + `test_corpus_export.py`: **đạt hết** (835 test ở lần chạy cuối, cộng 73 test truy xuất sau khi thêm tệp mới).
- `tests/architecture/test_import_boundaries.py` vẫn đỏ vì lỗi có sẵn `application/knowledge/applicability.py` → `infrastructure` (đã ghi từ REPORT-v2 §4). Luật mới cho `rag_v2/*` thêm vào `layers.yaml` và kiểm riêng: 24 tệp, 0 vi phạm.
- **Codex hết hạn mức ChatGPT** giữa lúc chạy I1/I2/I5 (thông báo: dùng lại được từ 02:14 ngày 1/11). Cả ba phiên đều đã ghi mã và test nhưng không kịp viết báo cáo cuối; tôi đã đọc diff, chạy lại toàn bộ test và sửa 4 test cũ xung đột với hành vi mới có chủ ý (liệt kê ở dưới).

## Đã xong (có test)
| Mục | Kết quả |
|---|---|
| F-A1/F-A2 nhánh dữ kiện | Chỉ trả fact trực tiếp khi toàn bộ cấu trúc (tiêu đề, đường dẫn, ngữ cảnh, đoạn cha, tiêu đề cột) không chứa dấu hiệu điều kiện/phạm vi; đoạn cha bị chặn thì fact bị loại khỏi nhánh nhanh. Test `test_fact_condition_closure_checks_the_whole_structure`, `test_rejected_parent_cannot_license_a_child_fact_or_send_source`. |
| F-A3 câu hỏi làm rõ | Văn bản tự do của mô hình không còn hiển thị; máy chủ dựng câu từ `missing_slots` cố định. |
| F-A5/F-D9 viết lại câu hỏi | Mã, số, năm, tên riêng, phủ định của câu mới phải còn nguyên; không được thêm mã/số không có ở câu mới hoặc lịch sử; `ResolvedQuestion` dùng chung cho ủy quyền, truy xuất, sinh và tái kiểm nguồn. |
| F-A4 ngoại lệ "kỷ luật" | Thêm kiểm thực thể có tên/chủ ngữ cá thể. |
| F-A6 thu hồi giữa lượt | Kiểm lại quyền nguồn trước mỗi lần gửi mô hình (viết lại, sinh, sửa, kiểm ngữ nghĩa) và trước khi trả/phát kết quả cuối; có test SSE thu hồi trong lúc chờ ngắt kết nối. |
| F-A7 debug capture | Mặc định chỉ ghi mã, độ dài, hash; không bao giờ ghi lịch sử. |
| F-D6 | Timeout ở lần sửa không còn thành `unverified`, không dùng lại verdict của lần lỗi. |
| F-B1/F-B2 snapshot–release | Manifest ghi release/generation/policy_generation, inventory chunk, danh tính embedding; bootstrap từ chối snapshot pending, sai model/revision/chiều/pooling; trạng thái `stale` có số chunk thiếu/thừa; `/health` có trường `rag_v2`. |
| F-B3/F-B4 embed-cache | Khóa cache gắn danh tính embedding; cache cũ không metadata bị bỏ qua; 503 chỉ thử lại đủ văn bản, không cắt âm thầm. |
| F-B5 bảng | `ingest/tables.py` mới: header nhiều tầng, đường dẫn cột, lược đồ không rõ thì không phát hành fact học phí (basis lấy từ header). |
| F-B6 coverage | Kiểm bảo toàn từng lần xuất hiện của token có nghĩa thay cho ngưỡng 98%. |
| F-B7/F-B8 | `corpus_export.py --output-dir` bất biến, số baseline cũ chỉ là tham chiếu; dựng tăng dần `--base` chỉ nhúng chunk mới/đổi. |
| F-C5 nhánh neo mã | `AuthorizedIndex.anchored` chuyển tiếp cùng quyền; ngưỡng phân biệt tính trong tập được phép. |
| F-C9 | BM25 cộng điểm theo thứ tự cố định, test với 6 `PYTHONHASHSEED`. |
| F-E1, E2, E3, E4, E6, E7, E8, E9 (bộ đo) | `rag_v2_scoring.py` dùng chung; ≥ 40 cặp mutation; A2 kiểm phát biểu thừa số/ngày/mã/tiền; manifest campaign, `--strict`, lệnh `gate` có exit code; route vắng là "chưa đo"; newdoc coi lỗi là lỗi; CI Wilson + bootstrap theo nhóm; probe `--authorized` với cache embedding. |
| F-F3 | Luật kiến trúc cho `rag_v2/*` (xem trên). |

Test cũ đã sửa vì xung đột với hành vi mới có chủ ý: `test_rewrite` (lịch sử phải chứa K64 thì viết lại mới được thêm K64), `test_service` clarify (không hiển thị câu của mô hình), `test_graph_integration` snapshot load (manifest phải đủ danh tính embedding), `test_corpus_export` (lệch baseline không còn là lỗi).

## Chưa làm
| Mục | Lý do / ghi chú |
|---|---|
| F-A8 (mất `applicability_note`, `_verified_publication`, `_verified_curriculum` ở `rag_v2_sources`) | Cần sửa `infrastructure/knowledge/runtime.py` (ngoài phạm vi các phiên Codex). Chưa khảo sát. |
| P3: F-C1 (bỏ cổng từ khóa chặn trước truy xuất), F-C2 (viết tắt/ngữ cảnh), F-C3/F-C4 (phạm vi đa trị, kiểu `Scope` chung), F-C6 (đa dạng tài liệu), F-C7 (chọn phiên bản theo câu hỏi), F-C8 (reranker 3 trạng thái), F-C10 (quét đồng bộ 2,4 s chặn event loop, cache không trần) | Cần Codex (hoặc làm trực tiếp, tốn quota Claude). |
| P4: F-D1 (độ phủ từng ý — nút thắt A1), F-D2/F-D3 (kiểm xác định theo quan hệ, ngày/đơn vị), F-D4 (đóng gói ngữ cảnh), F-D5 (prompt trung tính), F-D7 (lỗi hạ tầng không thành `no_source`), F-D8 (`outcome_kind` tới SSE), F-D10 (ngân sách lượt) | Như trên. |
| P6 bộ tài liệu mới + bộ nghiệm thu | Chưa viết. |
| Dựng lại chỉ mục thật | Bootstrap mới **từ chối** manifest cũ (thiếu danh tính embedding), nên trước khi bật v2 phải chạy `scripts/rag_v2_build_index.py --embed` (cần máy chủ nhúng 18081; nhúng local, không tốn DeepSeek). Runtime đang chạy v1 nên chưa bị ảnh hưởng. |
| Đo đầu–cuối bằng mô hình thật, P7 ổn định, P8 | Chờ P3/P4. |
| Bốn mục commit/numpy | numpy chính thức vào venv fixture (P0.2) chưa làm; commit mới chỉ gồm tệp v2, các tệp đang sửa dở khác của bạn (`graph.py`, `bootstrap/app.py`, `settings.py`, `health.py`…) và các tệp chưa theo dõi ngoài v2 (`corpus_export.py`, `test_corpus_export.py`…) **chưa** được commit. |

## Rủi ro/ghi chú
- HEAD của repo cách xa cây làm việc (hàng trăm tệp chưa theo dõi ngoài v2), nên nhánh `rag-v2-hardening` chưa phải một snapshot tự đủ để dựng từ checkout sạch; nó là mốc hoàn tác cho phần v2.
- Phần đã làm đều đóng-an-toàn hơn (thêm từ chối), nên cần đo lại độ phủ (A4) sau khi có P3/P4; có thể có ca trước đây trả lời giờ bị đẩy sang đường sinh/từ chối.

## Cần bạn trả lời
1. Codex dùng lại được từ 02:14 ngày 1/11. Đợi rồi giao P3/P4/P6 cho Codex (tiết kiệm quota Claude, trễ khoảng 4 giờ), hay tôi làm trực tiếp phần P3/P4 ngay bây giờ trên Sonnet (nhanh hơn, tốn quota Claude hơn)?
2. Ngân sách tiết kiệm: tôi đề xuất giới hạn phạm vi còn lại ở "đủ để chạy ổn định": P4.1 (độ phủ ý), P4.2 (kiểm số/ngày/đơn vị theo quan hệ), P4.3 (đóng gói ngữ cảnh), P4.5/P4.6 (lỗi hạ tầng, `outcome_kind`), P3.1 (bỏ cổng từ khóa chặn), P3.3/P3.4 (phạm vi), P3.7 (event loop, cache có trần), F-A8, và bộ tài liệu mới nhỏ (≥ 7 tài liệu tổng hợp, 1 phiên Codex); bỏ P7 ngâm dài và P8 mức đầy đủ. Đo cuối ở mức rút gọn (khoảng 2.000–3.000 lời gọi DeepSeek). Bạn đồng ý không?

---

# Cập nhật 2026-10-31 (đêm): P3/P4 phần thu hẹp, làm trực tiếp trên Sonnet

Quyết định của bạn: làm ngay, thu hẹp để tối ưu chi phí. Commit `8de934d70` (P4) và `730b36b19` (P3/F-A8). Test: **875 đạt** (v2, eval, hợp đồng trích dẫn, xuất kho). Bằng chứng là test xác định với gateway giả và dữ liệu tổng hợp; **chưa có phép đo đầu–cuối bằng mô hình thật** sau các sửa này (xem "Bị chặn").

## Đã làm trong lượt này
| Mục | Kết quả |
|---|---|
| F-D4 đóng gói ngữ cảnh | `generation/packing.py`: gói theo byte thật của JSON, tối đa 8 nguồn; đoạn cha quá lớn thì dùng đơn vị con vừa ngân sách thay vì bỏ im lặng hoặc vượt trần 28 KB; phần bị bỏ thì kết quả là `partial` có ghi chú. |
| F-D7 lỗi hạ tầng | Vector lỗi mà lexical rỗng, hoặc đầu ra sinh không phân tích được, nay là `transient_error` (có gợi ý thử lại) thay vì `no_source`/`unverified`. |
| F-D2/F-D3 kiểm xác định | Gắn số với đơn vị (đồng/USD/EUR, kg/tấn, ngày/tháng, tín chỉ, giờ, %), mã `UNIT_MISMATCH`; ngày ISO, dấu chấm, "ngày … tháng … năm" tương đương nhau; "50 phần trăm" = "50%"; học kỳ La Mã = số; thập phân "0.125" khác "125"; câu gộp nhiều nguồn K64+K65 không còn bị `SCOPE_MISMATCH` sai. Không bắt được: tráo hàng bảng (P11), tráo phần trăm giữa hai mức (P14), bỏ điều kiện (P17), số viết bằng chữ — vẫn do kiểm ngữ nghĩa. Quy đổi tương đương (1 kg = 1000 g) vẫn bị từ chối (thận trọng) cho tới khi bạn chốt chính sách. |
| F-D1 độ phủ từng ý | Lời gọi sinh liệt kê các ý (`facets`, cụm nguyên văn từ câu hỏi, kiểm bằng mã) và gán từng phát biểu; nếu có ý chưa được phát biểu nào qua kiểm thì gọi thêm đúng một lần cho các ý còn thiếu rồi gộp; ý vẫn thiếu thì kết quả `partial` ghi "Chưa tìm thấy căn cứ cho: <lời của người hỏi>". Không thêm lời gọi cho câu một ý. Khác lần thử `asked` ở REPORT-v2 §15: độ phủ do **mã tính và quyết định kết quả**, và có lượt bổ sung. Chưa biết mức cải thiện A1 vì chưa đo. |
| F-C3 phạm vi nhiều khóa/ngành | Câu nêu hai khóa/năm/ngành không còn bị lọc theo giá trị đầu tiên và không bị hỏi lại. Phần còn lại của F-C3/F-C4 (kiểu `Scope` chung, "từ K70", năm tuyển sinh) **chưa làm**. |
| F-C10 hiệu năng/cache | Mỗi lượt không còn băm lại và so khớp 9.071 đơn vị: bằng chứng ràng buộc được nhớ và chỉ tin lại khi định danh, tiêu đề, đường dẫn, hash và nội dung hàng nguồn không đổi; cache có trần. Mức giảm độ trễ chưa đo trên runtime. |
| F-A8 | Đọc trực tiếp các chunk được dẫn nay mang `applicability_note`, xác thực tệp đính kèm (`_verified_publication`) và hình học chương trình (`_verified_curriculum`) sang bước xuất/kiểm kỷ luật. **Lưu ý:** sửa nằm ở `infrastructure/knowledge/runtime.py`, tệp này đang chưa được git theo dõi cùng nhiều tệp khác của bạn nên tôi **không commit** nó; thay đổi vẫn nằm trong cây làm việc. Chưa có test tích hợp vì cần cơ sở dữ liệu thật. |

## Không làm (đã thu hẹp theo bạn đồng ý), cần bạn biết
- F-D8 (`outcome_kind` tới SSE/lịch sử), F-D10 (ngân sách lượt cho v2): chưa làm. Cả hai chạm vào hợp đồng API/ngân sách dùng chung với v1.
- P3.1: giữ nguyên luật từ khóa ngoài phạm vi ("thời tiết", "tỷ giá", "FPT"…) và luật "câu quá ngắn = không rõ", vì bỏ chúng chuyển quyết định sang mô hình mà chưa thể đo tác động lên A3 (câu mơ hồ). Test hiện có cũng coi "Học bổng FPT…" là ngoài phạm vi. Cần chốt chính sách (xem dưới).
- F-C2, F-C4, F-C6, F-C7, F-C8, F-D5: chưa làm.
- Bộ tài liệu mới (P6) và phép đo cuối: chưa làm.

## Bị chặn (đã kiểm chứng) — cần bạn quyết định
**Dịch vụ mô hình local (cổng 18081) đang hỏng.** `/info` trả 200 nhưng mọi `/embed` trả 503 `MODEL_RUNTIME_UNAVAILABLE` (thử 1, 5, 20 văn bản và 20 đơn vị dài nhất); tệp lỗi trong state ghi `ValueError`, lần dùng thành công cuối khoảng 22:12 ngày 30/10. Hệ quả:
- Không dựng lại được chỉ mục (lần chạy `rag_v2_build_index.py --embed` thất bại: `INDEX_BUILD_FAILED: HTTP_STATUS_503`, nhật ký ở `e2e/build-embedded2.log`; không ghi gì vào chỉ mục cũ).
- Runtime 8015 hiện không nhúng được câu hỏi, nên cả v1 lẫn v2 đang không dùng được nhánh vector.
- Mọi phép đo đầu–cuối (cổng B2, mẫu dev, phép thử tài liệu mới) đều chờ việc này.
Cách xử lý theo RUNBOOK-v2 (bước 1 sau khi máy khởi động lại): dừng các tiến trình `serve_rag_models.py --state …20261030-accounting-02` (PID 19496, 5108, 5152, 10560, 20980) rồi chạy `.venv/Scripts/python.exe -B -u scripts/serve_rag_models.py --state infra/local/rag-advanced-models-20261031-accounting-01 --predecessor infra/local/rag-advanced-models-20261030-accounting-02 --accounting-only` và chờ `"ready": true`. Không xóa state nào. Tôi đã thử làm bước này nhưng hệ thống từ chối việc dừng tiến trình đang chạy, nên **dừng ở đây để bạn quyết**: bạn tự chạy hai lệnh trên, hoặc cho phép tôi làm.

Sau khi dịch vụ mô hình chạy lại, thứ tự tiếp theo (không cần quyết định thêm): dựng chỉ mục mới (`--output data/rag_v2_index/embedded2`, nhúng local ~ vài chục phút, 0 DeepSeek) → `restart_rt.ps1 -Engine v2 -Index data/rag_v2_index/embedded2` (runtime v2) → khởi động nóng → B2 (79 ca) + mẫu dev (116 ca) so với mốc §19 (dev gate: đủ ý 89, thiếu ý 7, ca không đáp án đúng 75) → phép thử tài liệu mới `rag_v2_newdoc.py` → trả runtime về v1. Ước ~250–350 lời gọi DeepSeek.

## Câu hỏi chính sách còn mở (từ kế hoạch §7)
1. Phạm vi `UNKNOWN` (nguồn không ghi khóa/ngành): nêu rõ "nguồn không ghi phạm vi" rồi vẫn trả lời (đề xuất), hay hỏi lại?
2. Chấp nhận quy đổi tương đương (1 kg = 1000 g, ISO/dấu chấm — phần ngày đã chấp nhận) trong câu trả lời không?
3. Phạm vi sản phẩm cho nghiên cứu khoa học, phòng thí nghiệm, dịch vụ mới; có nên bỏ các luật từ khóa ngoài phạm vi để mô hình quyết định (đánh đổi A3)?
4. Nguồn tài liệu mới để nghiệm thu (tài liệu HUCE công khai thật, hay tổng hợp) và cách nạp thử vào DB.
5. Có sửa các nút dùng chung với v1 đang làm trượt A9 (khẩn cấp, bàn giao, lời chào, yêu cầu ghi, che liên hệ) hay không.
6. Cho phép commit `infrastructure/knowledge/runtime.py` (đang chưa theo dõi) cùng các tệp ngoài v2 hay để bạn tự quản.
