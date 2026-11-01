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

---

# Cập nhật 2026-11-01: chạy lại dịch vụ, dựng chỉ mục mới, đo thật — kết quả **chưa đạt**

Bằng chứng: ca do mô hình viết, đoạn nguồn kiểm bằng mã, mỗi ca chạy 1 lần (nên có dao động); không đo người dùng thật. Runtime 8015 đã **trả về v1** (cờ mặc định không đổi). Test sau các thay đổi: **1.016 đạt** (`tests/rag_v2`, `tests/evals`).

## Đính chính "Bị chặn" ở trên
Dịch vụ mô hình **không hỏng**: nó chỉ nhận **đúng 1 văn bản mỗi lượt `/embed`** (`len(inputs) != 1` → 503), còn `rag_v2_build_index.py` mặc định gửi lô 20. Phép thử của tôi lúc đó dùng sai định dạng nên kết luận "hỏng" là sai. Sau khi bạn cho phép, tôi dừng 5 tiến trình cũ và chạy lại với namespace `…20261031-accounting-01` (không xóa state nào). Chỉ mục mới dựng với `--batch-size 1`: `data/rag_v2_index/embedded2` (9.173 đơn vị, 1024 chiều, `embedding_status=complete`, ~38 phút, 0 lời gọi DeepSeek). Script dựng vẫn mặc định lô 20, không chạy được với dịch vụ hiện tại nếu quên `--batch-size 1`.

## Lỗi thật tìm ra khi đo (đã sửa)
| Lỗi | Hậu quả | Sửa |
|---|---|---|
| `app.py` không truyền `inventory_reader` | `/health/ready` của v2 **luôn** `unverified` (503), không bao giờ đối chiếu chỉ mục với DB | `KnowledgeReleaseRuntime.rag_v2_inventory()` (đọc chỉ-đọc, dùng chung bộ truy vấn với xuất kho, chia sẻ giữa các probe, nhớ 60 s). Kết quả thật: `ready`, `inventory_checked=true`, 0 chunk thiếu/thừa/đổi |
| Bộ nhớ đệm ràng buộc nguồn có trần 40.000 < 48.364 cặp (đơn vị, chunk) | Cache bị xóa mỗi lượt, không có tác dụng; mỗi lượt vẫn băm sha256 48 nghìn lần (~0,86 s) | Trần 250.000 + test chống tái phát. Đo ngoại tuyến: lượt thứ hai 0,86 s → 0,024 s (chưa đo lại trên runtime) |
| Bộ chấm `rag_v2_scoring` (Codex) coi mọi mệnh đề phủ định chứa fact là mâu thuẫn, và tách mệnh đề tại dấu chấm trong `office.com` | Câu trả lời đúng như "181TC … không tính học phần giáo dục thể chất" bị gán *thiếu ý* | Phân cực chấp nhận được lấy thêm từ câu gold chứa fact; chấm không tách tại dấu chấm trong token. Test mới (phủ định đúng, mâu thuẫn vẫn bị bắt, URL) |

## Kết quả đo (bộ chấm đã sửa, cùng bộ chấm cho bản cũ và mới)
| Bộ | Chỉ số | Bản cũ (trước hardening) | Bản mới |
|---|---|---|---|
| B2 (79 ca) | có đáp án (40): đủ / thiếu / từ chối / lỗi | 16 / 10 / 11 / 3 | 14 / 18 / 5 / 3 |
| B2 | không đáp án (39): đúng / trả lời nhầm / lỗi | 37 / 1 / 1 | 32 / 5 / 2 |
| Mẫu dev (136 ca) | có đáp án (116): đủ / thiếu / từ chối / lỗi | 63 / 21 / 27 / 5 | 62 / 28 / 23 / 3 |
| Mẫu dev | không đáp án (20) | 20 đúng | 20 đúng |
| Tài liệu mới (25 ca, 8 chunk mới trong bản sao kho) | có đáp án (18): đủ / thiếu / từ chối | — | 15 / 3 / 0, trích đúng đoạn gốc 18/18 |
| Tài liệu mới | không đáp án (7) | — | 7 đúng, 0 lỗi |
| **holdout3 (160 ca, chưa ai mở)** | có đáp án (120): đủ / thiếu / từ chối / lỗi | — | 51 / 39 / 23 / 7 |
| holdout3 | không đáp án (40): đúng / nhầm / lỗi | — | 31 / 6 / 3 |

**Kết luận trung thực: thay đổi P4 thu hẹp không làm tăng số câu trả lời đủ ý** (mẫu dev 63 → 62); nó chuyển một phần từ chối thành trả lời một phần (có ghi "chưa đủ căn cứ"), nên "thiếu ý" tăng. Phía không đáp án ở B2 kém hơn: lặp lại 7 ca sai ×3 cho thấy 3 ca là nhiễu/hết hạn, **4 ca ổn định** (CCNA, LinkedIn Learning, thi tiếng Anh trên máy, "CNTT K74 tổng tín chỉ") — đó là trả lời một phần có trích dẫn đúng quy định chung (Điều 12 công nhận tín chỉ), không bịa, nhưng bộ ca kỳ vọng từ chối. Đây là câu hỏi chính sách (xem cuối).

**holdout3, chấm chính thức** (`e2e/holdout3-v2.score.json`): A1 = 32,5% (mục tiêu ≤ 2%), A2 = 10 lỗi (mục tiêu 0), A3 = 77,5% (≥ 98%), A5 = 86,5% (≥ 95%), A7 = 6,25% (≤ 1%), A4/A8 không đạt, A6/A9 không có số liệu. **Không chỉ số nào đạt.** Trong 39 ca "thiếu ý", 25 ca vẫn chứa fact theo phép so khớp chuỗi lỏng (bộ chấm chặt coi là thiếu vì diễn đạt/ngắt mệnh đề) và 14 ca thiếu thật; cận dưới của A1 vẫn ~11,7%, xa mục tiêu. Điểm yếu thật rõ nhất: họ `ctdt` (chương trình đào tạo/bảng) có 13/23 lần từ chối.

## Độ trễ và lỗi
- Phần v2 (đo trong nhật ký): tổng p50 4,8 s, p90 7,3 s; sinh p50 2,2 s; kiểm ngữ nghĩa p50 1,8 s.
- Phía khách: byte đầu p50 0,1 s, nội dung đầu p50 8,5 s, hoàn tất p50 14,0 s (p90 23,9 s) với 2 luồng đồng thời. Khoảng 3,7 s trước dịch vụ v2 và ~5,5 s sau nội dung đầu nằm ngoài dịch vụ v2 (ước từ hiệu số các trung vị, chưa phân tích từng nút dùng chung).
- 14 lần `TimeoutError` ở ngưỡng cứng 12 s của nút (`agent/nodes/rag_v2.py`, `asyncio.timeout(12)`), dồn thành đợt (độ trễ nhà cung cấp tăng). Chúng trở thành thông báo "lỗi kết nối" (đúng thiết kế `transient_error`) nhưng chiếm 6,25% số lượt ở holdout3. Tôi **không đổi ngưỡng 12 s** vì đó là đánh đổi độ trễ/lỗi cần bạn quyết.

## Việc chưa làm và vì sao
Các mục đã thu hẹp ở trên vẫn chưa làm (F-D8, F-D10, F-C2/C4/C6/C7/C8, F-D5, P3.1, P7 soak, P8). Không chạy bộ safety 610 ca (tốn ~1.800 lời gọi, và A9 phụ thuộc các nút dùng chung). Chưa commit: `infrastructure/knowledge/runtime.py`, `evals/runners/corpus_export.py` (chưa được git theo dõi) và `bootstrap/app.py` (lẫn sửa đổi của bạn).

## Việc cần bạn quyết định tiếp
1. **Ngưỡng 12 s của nút v2**: giữ (lỗi ~6% khi nhà cung cấp chậm) hay nâng (vd 20 s) và cho phép trả lời chậm hơn?
2. **Trả lời một phần so với từ chối** khi chỉ có quy định chung (Udemy/CCNA/LinkedIn Learning): chấp nhận trả lời một phần có ghi chú, hay ép từ chối (mất giá trị cho câu hỏi thật)?
3. **Có làm tiếp v2 để đạt A1–A7** hay giữ v1 làm mặc định. Khoảng cách ở holdout3 là lớn (A1 32,5% so với 2%); Codex dự kiến đã được đặt lại quota từ 02:14 ngày 01/11 (chưa kiểm) nên có thể làm các hạng mục nặng (ctdt/bảng, độ phủ, chấm lại), nhưng sẽ tốn thêm công và lời gọi và **bộ holdout3 đã mở, không còn là bộ sạch**.
4. Các câu chính sách 1–6 ở phần trên vẫn còn mở.

---

# Cập nhật 2026-11-01 (A/B): v2 trước hardening so với hiện tại, cùng holdout3

Cách làm: đưa 17 tệp mã v2 và dòng nối `inventory_reader` trong `app.py` về commit baseline `01c9a7013` (chỉ thư mục làm việc, có sao lưu), chạy runtime v2 với chỉ mục cũ `embedded`, holdout3 ×1, cùng bộ chấm đã sửa; sau đó khôi phục mã (khớp byte với HEAD) và trả runtime về v1. Mỗi bên chỉ 1 lần chạy, chỉ mục khác nhau (cũ/mới) và thời điểm khác nhau nên có nhiễu. Tệp: `e2e/holdout3-base.json`, `holdout3-base.score.json`, `ab-flips.json`.

| holdout3 | Baseline (trước hardening) | Hiện tại |
|---|---|---|
| Có đáp án (120): đủ / thiếu / từ chối / lỗi | **63** / 42 / 15 / 0 | 51 / 39 / 23 / 7 |
| Không đáp án (40): đúng / nhầm / lỗi | **36** / 4 / 0 | 31 / 6 / 3 |
| A1 · A2 · A3 · A5 · A7 | 35% · 6 · 90% · 89% · 0% | 32,5% · 10 · 77,5% · 86,5% · 6,25% |
| Độ trễ khách p50 | **8,1 s** | 14,0 s |
| Phần v2 p50 / p90 (nhật ký) | 3,6 / 5,2 s | 4,8 / 7,3 s |
| Hết hạn 12 s | 1 | 14 |

**Kết luận: baseline tốt hơn ở hầu hết chỉ số; các thay đổi hardening làm v2 kém đi.** Cả hai đều xa mục tiêu A1 (≤2%), nên baseline cũng chưa đạt.

Khác biệt tập trung: họ `ctdt` (bảng chương trình đào tạo) chiếm 15/22 ca xấu đi (8 đủ→từ chối, 6 →lỗi hết hạn, 1 →thiếu), và nhóm "gần miền vàng" (3 đúng→lỗi, 2 đúng→trả lời nhầm). Ca tốt lên chỉ 3.

**Nguyên nhân rất có khả năng (đọc từ kết quả, chưa chạy lại để xác nhận):**
1. **Hầu như mọi lượt bị đánh dấu "bị cắt ngữ cảnh" → `partial`.** Phân bố kết quả: baseline `answer` 105 / `partial` 4; hiện tại `answer` 9 / `partial` 87 (không có câu nào mang "Chưa tìm thấy căn cứ cho", tức không phải do độ phủ từng ý). `pack_context` đặt `truncated=True` ngay khi còn đơn vị ứng viên sau khi đủ 8 nguồn; retrieval luôn trả 12 ứng viên nên hầu như lượt nào cũng "bị cắt" → `coverage=0.9` → trả lời một phần kèm câu "chưa đủ căn cứ". Đây là lỗi thiết kế của tôi: phần đuôi xếp hạng bị bỏ là bình thường, không phải mất ngữ cảnh. Nó giải thích phần lớn "trả lời một phần/thiếu ý" và các ca trả lời nhầm.
2. **`UNIT_MISMATCH` (mới, 31 lần bác phát biểu)** và `NEGATION_MISMATCH` tăng (14→26) khiến câu hỏi mã/tín chỉ ở bảng bị "đã tìm thấy nguồn nhưng chưa xác minh được phát biểu" (7/9 ca ctdt đủ→từ chối).
3. **Thêm vòng gọi mô hình và ngữ cảnh lớn hơn** làm phần v2 chậm thêm ~1,2 s ở p50 và ~2 s ở p90, đẩy đuôi vượt 12 s (1→14 lần hết hạn).

**Đề xuất sửa nhỏ, chưa làm (chờ bạn quyết):** chỉ đặt `truncated` khi một đơn vị được xếp hạng cao bị loại vì ngân sách/giới hạn, không phải khi cắt đuôi; xem lại ngưỡng của `UNIT_MISMATCH` với ô bảng; đo lại từng nhóm trên mẫu dev trước khi gộp.
