# RAG v2 — báo cáo cuối (2026-10-29)

**Kết luận: chưa chuyển cờ sang v2.** v2 chạy được sau cờ `CAMPUS247_RAG_ENGINE=v2`, tốt hơn v1 rõ rệt về độ phủ và độ đủ ý trên bộ phát triển, nhưng chưa đạt A1–A9, và lần đo bộ giữ kín ×3 bị chặn giữa chừng vì nhà cung cấp mô hình trả **HTTP 402** (hết số dư DeepSeek). Mặc định vẫn là v1 và runtime hiện chạy v1.

Bằng chứng là gì: 760 ca do mô hình `gpt-6.1-sol` viết từ 2019 đoạn kho đang phục vụ, đáp án chuẩn là đoạn trích nguyên văn kiểm bằng mã, chạy trên runtime thật (DeepSeek sinh, bge-m3 nhúng). Chưa đo bằng câu hỏi của người dùng thật.

## 1. Đã giao
| Hạng mục | Vị trí |
|---|---|
| Quy tắc dọn (nhãn "do mô hình tạo", `not_verified` vì thiếu người kiểm); giữ nguyên bảo vệ dữ liệu/bảo mật | `AGENTS.md`, `.claude/skills/campus247/**` |
| Đặc tả, tiêu chí A1–A9, phân loại lỗi, thiết kế | `SPEC-v2.md`, `DESIGN-v2.md` |
| Kho xuất (2019 đoạn thực tế; brief cũ ghi 2515/151/123 không khớp release generation 27) | `evals/corpus/` |
| Bộ ca 760 (533 phát triển / 227 giữ kín, chia theo nhóm; 120 ca không đáp án; 4 biến thể) + bộ kiểm + bộ chạy + bộ chấm | `evals/datasets/rag-v2/`, `evals/runners/rag_v2_{cases,eval,suite,retrieval_probe}.py` |
| Bộ safety/injection/nhiều lượt/routing/tool: 610 ca + bộ chạy | `evals/datasets/rag-v2/suite.jsonl`, `rag_v2_suite.py` (đã có test 76 ca; **chưa chạy trên runtime** vì 402) |
| Lõi v2 (nạp có cấu trúc 9071 unit, 137 dữ kiện có kiểu, hiểu câu hỏi xác định, truy xuất RRF + dự phòng, sinh ràng buộc theo ID, kiểm chứng xác định + ngữ nghĩa, kết quả có kiểu, trace hữu hạn) | `services/api/src/campus247/rag_v2/`, `agent/nodes/rag_v2.py`, `bootstrap/rag_v2.py`, `scripts/rag_v2_build_index.py` |
| Test | `tests/rag_v2` (296), `tests/evals` (+3 tệp mới) |

Phân công: Codex (`gpt-6.1-sol`, mức high) viết T1–T8; tôi viết đặc tả, kiểm, và sửa các lỗi thiết kế tìm được khi đo thật (mục 3). Codex hết hạn mức ChatGPT từ ~23:30 đến 02:08 nên T9 do tôi làm trực tiếp.

## 2. Số đo (cùng bộ chấm, cùng quy tắc khớp dữ kiện cho cả hai engine)
Bộ chấm: dữ kiện bắt buộc khớp theo cụm, hoặc mọi số của dữ kiện có mặt + ≥75% từ nội dung. "Đủ ý" = đủ mọi dữ kiện. A1 ở đây là proxy (đã trả lời nhưng thiếu dữ kiện/bị sai), chưa phải chấm ngữ nghĩa.

**Bộ phát triển, 49 nhóm / 116 ca có đáp án (mẫu phân tầng theo nhóm), 1 lượt**
| | v1 | v2 (bản cuối) |
|---|---|---|
| Trả lời đủ ý | 43 (37%) | 64 (55%) |
| Trả lời nhưng thiếu ý | 15 | 17–18 |
| Từ chối / hỏi lại | 56 | 26 |
| Lỗi hạ tầng | 2 | 8–9 |
| Ca không đáp án bị trả lời nhầm | 0/20 | 0/20 |
Hai lần chạy lặp v2 cho cùng 64 ca đủ ý.

**Bộ phát triển đầy đủ 533 ca (bản v2 trước 3 sửa cuối, 1 lượt)**
| Tiêu chí | Ngưỡng | v1 | v2 |
|---|---|---|---|
| A4 chuẩn+không dấu | ≥92% | 63% | 78% |
| A4 từ khóa | ≥85% | 40% | 62% |
| A4 lóng | ≥75% | 48% | 81% (đạt) |
| A3 từ chối đúng | ≥98% | 93,8% | 91,4% |
| A5 dẫn đúng mục | ≥95% | 58% | 90,6% |
| A1 (proxy) | ≤2% | 9,1% | 21,9% |
| A7 lỗi | <1% | 2,6% | 4,3% |
| A8 trung vị / p95 | ≤6 / ≤12 s | 13,3 / 22,7 s | 8,2 / 17,7 s |

**Bộ giữ kín** (chạy ×3, 227 ca): **không hoàn tất**. 183 lượt đầu (lượt 1, các nhóm A0–A3, N, Q1) hợp lệ trước khi DeepSeek trả 402; các lượt sau là lỗi hạ tầng, không dùng. Trên 183 lượt đó: ca có đáp án (144) đủ ý 85 (59%), thiếu ý 29, từ chối 21, lỗi 9; ca không đáp án (39) bị trả lời nhầm 6, từ chối/hỏi lại 32, lỗi 1. Không đủ để nêu A1–A9 của bộ giữ kín; v1 chưa chạy trên bộ giữ kín.

Độ trễ: dịch vụ v2 trung vị 3,3 s (p95 5,5 s) nhưng đầu–cuối 8 s vì hai lời gọi mô hình tuần tự của nút an toàn/định tuyến v1 (~4 s) chạy trước. Rerank CPU (~2,9 cặp/s ở 300 ký tự) không dùng được trong đường yêu cầu.

## 3. Nguyên nhân gốc tìm được và đã sửa (phân loại lỗi theo SPEC)
| Lỗi | Nhãn | Sửa |
|---|---|---|
| Ủy quyền toàn bộ 2019 chunk mỗi lượt (N+1 truy vấn) ⇒ mọi lượt hết 12 s | INFRA | Cache theo release/generation/policy/phạm vi, stale-while-revalidate, chunk được dẫn vẫn đọc lại trực tiếp |
| Rerank làm tụt chunk gold (92% → 83% → 60% ở ngưỡng −1) | RERANK | Bỏ rerank khỏi đường yêu cầu, giữ RRF |
| Dữ kiện cần có trong top-12 unit chỉ 62% dù chunk đúng 92% (đáp án nằm ở hàng/khoản anh em) | RETRIEVAL | Sinh trên nguyên chunk cha (≤19 KB, trần 28 KB của cổng nhà cung cấp), lấy từ hàng DB đã ủy quyền |
| "nếu" gấp thành "neu" ⇒ nhận nhầm trường NEU, ngoài phạm vi; học kỳ số La Mã; hỏi lại học phí quá hăng | OVER_REFUSE | Sửa `understanding/analyze.py` + test |
| Kiểm phủ định so bằng nhau trên cả chunk ⇒ loại hầu hết phát biểu đúng; regex mã dính số vào chữ ⇒ `NUMBER_NOT_IN_SOURCE` giả | VERIFICATION | Kiểm cục bộ (thêm/bỏ phủ định theo cụm), số cho phép dính chữ |
| Phát biểu có "kỷ luật" bị nút output_guard v1 chặn ⇒ lỗi hệ thống | INFRA | Chuyển thành từ chối có thông báo; không nới guard |
| Bộ chấm khớp cụm quá chặt với dữ kiện dạng "998824 – 2" | đo lường | Khớp theo số + từ nội dung, áp cho cả v1 và v2 |

## 4. Giới hạn còn lại và việc chưa xong
1. **Bị chặn (đã kiểm chứng):** nhà cung cấp sinh trả HTTP 402 (hết số dư). Chưa chạy được: bộ giữ kín ×3 cho v2 và v1, bộ safety 610 ca trên runtime, đo độ nhất quán A6, đo lại tải/ổn định (M5). Đầu vào tối thiểu cần: nạp lại số dư DeepSeek (hoặc cấp ngân sách/nhà cung cấp khác); tôi không có quyền chi trả.
2. Chưa đạt A1 (đủ ý/đúng), A3, A4 (từ khóa, chuẩn form), A5, A7, A8 trên bộ phát triển. Nút nghẽn còn thấy: câu nhiều ý chỉ trả lời một phần; ~15% ca bảng chương trình có đáp án rải ở nhiều hàng; hai lời gọi phân loại v1 làm chậm ~4 s; nhãn bộ ca có thể sai (đã xem 9 ca ngẫu nhiên, hợp lý; vài `required_facts` quá ngắn như "3", "8").
3. Câu trả lời có "kỷ luật" bị guard v1 từ chối ngay cả khi nguồn đúng (giữ nguyên bảo vệ).
4. Khởi động lạnh: lượt đầu sau khi bật v2 mất ~25–35 s (cache ủy quyền); cần gọi một lượt khởi động nóng.
5. Runtime v2 cần numpy: venv fixture (Python 3.12) không có; đã sao chép numpy 3.12 từ runtime Codex vào `data/rag_v2_vendor/` (git-ignored) và đặt `PYTHONPATH` khi chạy v2. Nên cài chính thức vào venv fixture.
6. Có ghi nhật ký gỡ lỗi hữu hạn (`rag_v2_*`, `stream_*`) và một cơ chế chụp đầu ra sinh `CAMPUS247_RAG_V2_DEBUG_DIR` (mặc định tắt, chỉ dùng cho ca tổng hợp) — tắt trong vận hành.
7. Tests: `tests/rag_v2` + eval + nhóm v1 liên quan: 945 đạt, 8 đỏ — đúng 8 ca đỏ có sẵn (intent "Lịch học ngày mai", context_propagation ×2, huce_discovery, huce_service_release, public_rag_wiring, multi_agent_api, architecture/applicability). Không đỏ mới.

## 5. Bước tiếp theo
Nạp số dư → `rag_v2_eval.py run --split holdout --repeat 3` cho v2 và v1 → `rag_v2_suite.py run` → so bằng `compare` → chuyển cờ chỉ khi A1–A9 đều đạt (hiện chưa). Hướng cải thiện có đòn bẩy lớn nhất: (a) trả lời đủ ý cho câu nhiều phần (tách câu hỏi thành các ý, truy xuất/sinh theo ý); (b) chạy song song nút phân loại an toàn/định tuyến để về ≤6 s; (c) chấm ngữ nghĩa độc lập cho A1 thay proxy.

## 6. Phụ lục: trần của ngữ cảnh sinh (đo ngoại tuyến, không gọi mô hình; 2026-10-29)
`evals/runners/rag_v2_context_probe.py` đóng gói ngữ cảnh đúng như dịch vụ (đoạn cha của các unit đầu, ≤6 hàng, ≤19.000 byte JSON) rồi kiểm mọi dữ kiện bắt buộc có trong ngữ cảnh hay không, trên 452 ca có đáp án của bộ phát triển:
| Cấu hình | Đủ mọi dữ kiện trong ngữ cảnh |
|---|---|
| Hiện hành (6 hàng, 19 KB) | 376 (83,2%) |
| Tách câu hỏi thành ý con | 378 |
| lexical/vector k=80 | 373 |
| 8 hàng, 19 KB | 385 (85,2%) |
| 8 hàng, 22 KB | 386 (85,4%) |
Kết luận: ngữ cảnh chứa đủ dữ kiện cho ~83–85% ca nhưng v2 chỉ trả lời đủ ý khoảng 55–60%, nên nút nghẽn còn lại nằm ở sinh/kiểm chứng (câu nhiều ý trả lời thiếu, phát biểu bị loại), không ở truy xuất. Các thay đổi sinh/kiểm chứng chỉ đo được bằng mô hình thật nên đang bị chặn bởi HTTP 402. Nâng lên 8 hàng/22 KB không dùng được: trần 28.000 byte của cổng nhà cung cấp (đã kiểm: 6 hàng/19 KB là mức an toàn kèm chỉ dẫn và lược đồ).

## 7. Cập nhật 2026-10-29 (sau khi nạp lại số dư): bộ giữ kín và bộ safety
Chạy tiết kiệm theo yêu cầu: v2 bộ giữ kín ×3; v1 chỉ 1 lượt; bộ safety chỉ cho v2 và chỉ mẫu 221/610 ca. Hai lỗi mã tìm ra khi đo (và đã sửa trước các lượt dưới): `UnboundLocalError` ở nhánh thử lại kiểm chứng ngữ nghĩa (làm ~11% lượt lỗi trong một lần chạy hỏng, đã loại khỏi số liệu), và `--resume` của bộ chạy safety không tạo tệp mới.

**Bộ giữ kín 227 ca, lượt 1, cùng bộ chấm (188 ca có đáp án, 39 ca không đáp án)**
| | v1 | v2 |
|---|---|---|
| Có trả lời (đầy đủ hoặc một phần) | 85 (45%) | 151 (80%) |
| Trả lời đủ ý | 73 (39%) | 106 (56%) |
| Trả lời nhưng thiếu ý | 12 | 45 |
| Từ chối/hỏi lại ca có đáp án | 101 | 32 |
| Ca không đáp án từ chối/hỏi lại đúng | 37/39 (95%) | 32/39 (82%) |
| Lỗi | 2 | 5 |
| Trung vị / p95 đầu–cuối | 9,8 / 21,2 s | 9,9 / 14,3 s |

**v2 bộ giữ kín ×3 (681 lượt, bản mã cuối)**: A4 chuẩn+không dấu 82% (≥92%: chưa), từ khóa 73% (≥85%: chưa), **lóng 85% (≥75%: đạt)**; A3 82% (≥98%: chưa); A5 88% (≥95%: chưa); A6 nhất quán 93,4% (≥95%: chưa, gần); A7 lỗi 2,1% (<1%: chưa); A8 trung vị 9,2 s / p95 14,1 s (≤6 / ≤12: chưa); A1 proxy 24% (≤2%: chưa). A2 (phát biểu không có trích dẫn): 0.

**Đánh đổi quan sát được:** v2 trả lời nhiều hơn rõ rệt (80% so với 45%) và đủ ý hơn (56% so với 39%), nhưng trả lời thiếu ý nhiều hơn (45 so với 12) và trả lời nhầm câu không đáp án nhiều hơn (7 so với 2 trên 39). Ca nhầm của v2 chủ yếu là câu "gần miền" (ví dụ hỏi công nhận chứng chỉ Cisco/Udemy, mà kho chỉ có quy định chung về quy đổi tín chỉ) và một câu mơ hồ có đại từ "đó". Ý tưởng sửa chưa làm: từ chối khi từ đặc thù trong câu hỏi (tên riêng, mã khóa) không xuất hiện ở bất kỳ đâu trong kho; hỏi lại khi câu ngắn có đại từ chỉ định không có ngữ cảnh. Bộ giữ kín đã bị "nhìn" ở mức tổng hợp, nên các sửa đó cần đo lại trên ca mới.

**Bộ safety (mẫu 221 ca của v2: safety 50, injection 34, nhiều lượt 17, routing 100, tool 20)** — kết quả KHÔNG dùng làm điểm đạt/trượt vì nhà cung cấp sinh chậm/lỗi trong lúc chạy (107 lần quá hạn ở bước sinh; 92/221 lượt là lỗi hệ thống). Các số đáng tin vì lỗi không làm rò dữ liệu: **rò canary 0**, tool_guard 20/20, injection 32/34 (2 ca trượt đều là lượt lỗi), false-positive ca lành mạnh 1/13 (7,7%, ngưỡng ≤8%). Nhóm safety/nhiều lượt/routing chưa đo được sạch; v1 chưa chạy bộ safety.

**Chưa làm do tiết kiệm chi phí và nhà cung cấp lại chậm/lỗi (mỗi lượt ~18 s rồi lỗi vào cuối phiên):** v1 bộ giữ kín lượt 2–3; v1 bộ safety; bộ safety đủ 610 ca; rà soát mã đối kháng của Codex (đã bắt đầu, bị dừng).

**Quyết định cờ: giữ v1 mặc định.** v2 chưa đạt A1, A3, A4 (hai dạng đầu), A5, A6, A7, A8, và A9 chưa đo sạch. Kết quả này đủ để kết luận v2 hơn v1 về độ phủ nhưng chưa an toàn hơn về trả lời thiếu/nhầm; không nên chuyển cờ.

## 8. Hai sửa không tốn chi phí mô hình (2026-10-29, chưa đo đầu–cuối)
Làm sau §7 để xử lý nhóm "trả lời nhầm ca không đáp án" mà không gọi mô hình:
1. **Cổng thực thể lạ** (`understanding/entities.py`, bật trong `bootstrap/rag_v2.py`): từ riêng (viết hoa, không đầu câu) hoặc mã khóa mà toàn kho không nhắc tới thì từ chối `no_source`. Chữ viết tắt toàn hoa (CNPM, TNLĐ), thẻ học kỳ (HK1) và từ lóng không bị coi là thực thể. Đo ngoại tuyến: 0 trong 452 (dev) và 0 trong 188 (giữ kín) ca có đáp án bị gắn nhầm; bắt được 10/81 (dev) và 11/39 (giữ kín) ca không đáp án.
2. **Đại từ chỉ định không ngữ cảnh** ("Cách tính điểm đó?") hỏi lại thay vì tra cứu. Tính chung với các luật hiểu câu hỏi: ca có đáp án bị thoát sớm sai 3/452 (dev), 3/188 (giữ kín); ca không đáp án thoát sớm đúng 18/81 (dev), 14/39 (giữ kín).
Test: 301 ca `tests/rag_v2` đạt. Chưa chạy lại đầu–cuối vì nhà cung cấp sinh lại chậm/lỗi và để tiết kiệm chi phí; bộ giữ kín đã bị nhìn ở mức tổng hợp nên cần ca mới để xác nhận tác dụng. Mã v2 hiện hành vì vậy khác bản đã đo trong §7 ở hai điểm này.

## 9. Rà soát đối kháng bởi Codex (chỉ đọc) và các sửa (2026-10-29)
Phiên `gpt-6.1-sol` chỉ đọc, báo 2 lỗi cao và 4 lỗi trung, mỗi lỗi kèm ca tái hiện chạy qua đồ thị. Tất cả đã sửa, có test; chi tiết thô ở `briefs/T10-review-out.txt`.
| # | Mức | Phát hiện | Sửa |
|---|---|---|---|
| 1 | Cao | Nhánh dữ kiện trả một dòng "580.500 đồng/tín chỉ" mà bỏ điều kiện "chỉ áp dụng cho học phần học lại" ở dòng kế, không qua kiểm ngữ nghĩa | Chỉ dùng nhánh dữ kiện khi phần còn lại của unit không có điều kiện/ngoại lệ/phủ định; còn lại đi qua sinh + kiểm ngữ nghĩa |
| 2 | Cao | Tệp chỉ mục tự khai tiêu đề/phạm vi (K64) khác hàng nguồn chuẩn (K65); hệ thống trả lời với trích dẫn K65 | Unit chỉ được nhận khi `doc_title` bằng tiêu đề của hàng DB đã ủy quyền và mọi khóa/ngành/năm nó khai đều xuất hiện trong hàng đó |
| 3 | Trung | Tiêu đề nguồn chứa chỉ dẫn tấn công lọt vào lời gọi sinh và kiểm chứng | Quét cả tiêu đề, đường dẫn và nội dung trước khi ghép vào đoạn cha |
| 4 | Trung | Cơ chế chụp gỡ lỗi ghi nguyên câu hỏi (có thể có PII) | Chỉ ghi băm của câu hỏi |
| 5 | Trung | Nhật ký lỗi ghi 60 ký tự đầu của thông điệp `ValueError` (có thể chứa nội dung nhạy cảm) | Chỉ ghi loại lỗi và mã trạng thái HTTP |
| 6 | Trung | Kiểm phủ định bị qua mặt khi đổi chỗ phủ định ("không được nghỉ… và được dự thi" → "được nghỉ… và không được dự thi") với nguồn ngắn | Nguồn ngắn cũng kiểm theo cụm sau từ phủ định, bên cạnh đếm. Hai kiểu còn lại (đảo đối tượng ngoại lệ, diễn đạt lại tránh cụm) vẫn chỉ được chặn bởi bước kiểm ngữ nghĩa |
Test: `tests/rag_v2` + hợp đồng trích dẫn: 314 đạt. Các sửa này làm v2 thận trọng hơn ở nhánh dữ kiện; tác động lên A1–A9 chưa đo (chờ lần chạy đầy đủ).

Ghi chú sau khi sửa §9: lần đầu áp kiểm phạm vi lên mọi unit làm vòng ủy quyền mỗi lượt tăng từ ~0,9 s lên ~25 s (gấp hàng nghìn lần gập chuỗi cho từng unit) và gập dấu gạch "2026–2027"/"2026-2027" làm loại nhầm 493 unit. Đã sửa bằng bộ nhớ đệm theo hàng nguồn và thống nhất dấu gạch; trên runtime thật vòng này lại ~0,9 s, 8756 unit hợp lệ. Lời gọi sinh sau đó vẫn quá hạn (nhà cung cấp chậm), nên chưa có số đo đầu–cuối sau §8–§9.

## 10. Phiên hoàn tất (2026-10-29 chiều): cổng B0 đỏ, chỉ làm phần không tốn DeepSeek
**B0 (kiểm tra nhà cung cấp) đỏ, có bằng chứng:** chạy v2 với `--limit 2` hai lần (cách nhau ~35 phút) đều cho `error` sau ~17 s, log `rag_v2_failure kind=TimeoutError where=generate_statements`. Kiểm bằng `curl` không khóa: kết nối TCP tới `api.deepseek.com` (IPv4) và `www.deepseek.com` hết thời gian chờ (≥15 s, `time_connect=0`) trong khi `example.com` trả 200 sau 0,9 s; DNS phân giải bình thường. Tức là nhà cung cấp không truy cập được từ máy này ở tầng mạng (không phải HTTP 402). Theo quy tắc chạy tiết kiệm, không chạy B2–B6.

Việc đã làm không tốn DeepSeek:
1. **Bộ giữ kín mới `evals/datasets/rag-v2/holdout2/cases.jsonl`** (160 ca = 30 nhóm có đáp án ×4 + 10 nhóm không đáp án ×4; split `holdout`; validate sạch). Do `gpt-6.1-sol` viết từ kho, chỉ dùng 36 đoạn chưa nằm trong bộ cũ, không bị nhìn khi sửa mã (bằng chứng: trích dẫn/dữ kiện kiểm bằng mã; chưa người dùng thật). Brief: `briefs/T11-holdout2.md`; báo cáo: `briefs/T11-report.md` (lưu ý: báo cáo ghi "chưa đạt" vì validator đòi mỗi ca không đáp án một `group_id` riêng; đã đổi `group_id` các ca này thành `<nhóm>-<biến thể>` sau đó).
2. **Neo mã định danh trong truy xuất từ vựng** (`retrieval/bm25.py:anchored`, nhánh RRF thứ ba): từ khóa dạng mã ghép (K71QD, 71CS, mã học phần 6 chữ số) giới hạn BM25 trong các unit chứa mã đó. Đo ngoại tuyến bằng `rag_v2_context_probe.py` trên 452 ca có đáp án của bộ phát triển: "ngữ cảnh chứa đủ dữ kiện" **375 → 398 (83% → 88%)**; từ khóa 83 → 92/113, lóng 93 → 104, không dấu 95 → 98. Thử thêm viết tắt ĐATN/TTTN/KLTN/CĐR: không tăng (396), đã bỏ. Chỉ là trần ngữ cảnh, chưa đo đầu–cuối.
3. **Rà soát Codex lượt 2** (`briefs/T12-review-out.txt`, chỉ đọc): 2 cao + 8 trung. Đã sửa: (1,2) nhánh dữ kiện nay kiểm điều kiện trong cả 600 ký tự kế tiếp của hàng nguồn cha và dùng bộ nhận diện điều kiện rộng hơn ("áp dụng", "dành cho", "đối tượng", "từ học kỳ", "học lại", "lưu ý"…); (3) header `.npy` được kiểm với kích thước tệp trước khi cấp phát (`adapters/npy.py`); (4) cache nguồn hàng loạt lọc `effective_until` theo từng lượt; (7) "K 64" và "K64" cùng khóa trong từ vựng thực thể; (10) câu có dấu phẩy đi qua luồng sinh. **Chưa sửa (ghi nhận):** (5) subject của fact trong tệp chỉ mục có thể bị giả — tệp có checksum trong manifest nhưng chưa ký; (6) phủ định ở câu khác làm từ chối nhầm phát biểu đúng ở nguồn ngắn (thận trọng, không nguy hiểm); (8) cổng thực thể lạ nhạy kiểu chữ ("cisco" thường không bị bắt); (9) "Quy định đó…" khi nhận ra chủ đề vẫn tra cứu (đại từ "đó" folded thành "do", trùng từ "do"=vì, nên nới điều kiện sẽ gây hỏi lại nhầm).
4. **Thiết kế (chưa bật)** song song hóa hai nút phân loại: `DESIGN-parallel-classify.md`.
Test: `tests/rag_v2` 306 + 5 test mới đạt (không đỏ mới).

## 11. Đo đầu–cuối sau §10 (2026-10-29 chiều) — nhà cung cấp lại truy cập được
Mạng tới DeepSeek thông lại sau khoảng 1 giờ (B0 xanh: 5/6 lượt trả lời). Bằng chứng: ca do mô hình viết, đáp án chuẩn là đoạn trích kiểm bằng mã; chưa đo người dùng thật.

**B2 (79 ca, 1 lượt):** A3 37/39 = 94,9% (ca trượt: một lỗi nhà cung cấp, một trả lời nhầm; bỏ ca lỗi thì 37/38); không ca có đáp án nào bị từ chối thêm do các cổng mới. **B3 (mẫu dev 116 ca có đáp án, 1 lượt):** đủ ý 72 (mốc trước 64), thiếu ý 12 (trước 17), 5 lỗi `TimeoutError` ở bước sinh (nhà cung cấp chậm, trung vị 10,9 s).

**Bộ giữ kín mới `holdout2` (160 ca: 120 có đáp án + 40 không), bộ chấm không đổi:**
| | v1 ×1 | v2 ×1 | v2 ×3 |
|---|---|---|---|
| Có đáp án: đủ ý / thiếu ý / từ chối-hỏi lại / lỗi | 57 / 8 / 55 / 0 | 73 / 14 / 27 / 6 | — |
| Không đáp án: từ chối-hỏi lại đúng | 34/40 | 32/40 | A3 98/120 = 81,7% |
| A1 (proxy) | 6,7% | — | 13,3% |
| A4 chuẩn+không dấu / từ khóa / lóng | 60 / 33 / 63% | — | 73 / 71 / 74% |
| A6 nhất quán | — | — | 90,6% |
| A7 lỗi | 0% | — | 4,2% |
| A8 trung vị / p95 | 9,4 / 16,8 s | — | 10,2 / 16,3 s |
v2 hơn v1 rõ về độ phủ (đủ ý 73 so với 57; từ khóa 71% so với 33%) nhưng kém ở A1, A3 (ca không đáp án) và A7. **A5** sau khi bộ chấm coi trích dẫn đúng khi chunk được dẫn chứa nguyên văn đoạn gold (đổi `cites_gold` trong `rag_v2_eval.py`, áp dụng cho cả hai engine): v1 87,3%, v2 88,7% (trước đổi: 45% và 41% — cùng nội dung nằm ở nhiều chunk). Nhiều `required_facts` của holdout2 là cụm dài nên A1 bị tính khắt khe; holdout3 dùng dữ kiện ≤60 ký tự.
Hai điểm yếu lặp lại của v2: câu mơ hồ ("đăng ký bổ sung kịp không", "hai mức điểm khác nhau") bị trả lời; tên viết tắt toàn hoa ngoài kho (NPTEL/SWAYAM) lọt cổng thực thể.

**Bộ safety đủ 610 ca cho v2 (sạch: chỉ 3 lượt lỗi hệ thống):** rò canary **0**; injection 100/100; tool_guard 60/60; safety 44/100; nhiều lượt 31/50; routing 208/300; false-positive ca lành mạnh 8/25 = 32% (mốc ≤8%) ⇒ **A9 chưa đạt**. Nguyên nhân thấy được trong các ca trượt: (a) hỏi lại học phí quá hăng — "Học phí cử nhân K65 đến K68 năm 2026-2027…" và "Quyết định 924 … hiệu lực từ ngày nào" bị hỏi ngành/năm dù đã đủ phạm vi (cử nhân/kỹ sư là cấp bằng chọn đúng hàng phí; quyết định có số tự xác định phạm vi); (b) từ chối `unverified` ("đã tìm thấy nguồn nhưng chưa xác minh được phát biểu") ở câu học phí/hạn khiếu nại. (a) đã sửa (xem §12); (b) chưa.

**Quyết định cờ (B7): giữ v1.** v2 chưa đạt A1, A3, A4, A6, A7, A8, A9 trên bộ mới.

## 12. Việc đã sửa chưa đo đầu–cuối và cách tiếp tục (dừng 2026-10-29: mạng công ty chặn DeepSeek)
Đã sửa, có test, CHƯA đo bằng mô hình: neo mã định danh (`retrieval/bm25.py:anchored`); cổng thực thể mở rộng (viết tắt toàn hoa phát âm được, năm và mã 6 số ngoài kho, `asks_statistic`); câu mơ hồ ("ấy/kia/đó", "không biết … nào"); học phí: cấp bằng (cử nhân/kỹ sư/KS/KTS) và quyết định có số đủ phạm vi; "trường khác" không còn tự thành ngoài phạm vi; phủ định theo câu cho nguồn ngắn; nhánh dữ kiện kiểm điều kiện ở hàng bên cạnh; thử lại một lần khi bước sinh quá hạn (ngân sách sinh 6→8 s); `cites_gold` trong bộ chấm; song song hóa phân loại (`CAMPUS247_PARALLEL_CLASSIFY=true`, mặc định tắt). Cổng ngoại tuyến trên dev: ca có đáp án bị chặn nhầm 3/640; ca mơ hồ bắt 25/30; gần miền vắng 45/60.
Cách tiếp tục khi có mạng (tuần tự): (1) `resume/restart_rt.ps1 -Engine v2` (đặt `CAMPUS247_PARALLEL_CLASSIFY=true` trước nếu muốn đo song song), 1 lượt khởi động nóng + 45 s, `rag_v2_eval.py run --split dev --limit 2` (B0); (2) B2 trên `runs/cases-ho-cheap.jsonl` rồi B3 `runs/cases-dev-sample.jsonl`; (3) bộ safety đủ 610 ca (`rag_v2_suite.py run`, lần đầu không `--resume`) và so từng nhãn với `runs/v2-suite-b6.jsonl` để xác nhận song song hóa không đổi nhãn an toàn; (4) bước chưa sửa: từ chối `unverified` ở câu học phí/khiếu nại — cần bật `-DebugCapture` ở `restart_rt.ps1` một lần để xem đầu ra sinh; (5) đo cuối holdout3 (`evals/datasets/rag-v2/holdout3/cases.jsonl`, chưa ai mở) ×3 cho v2 bằng `--cases ... --split holdout --repeat 3 --concurrency 2`. Cờ mặc định vẫn là v1; runtime đã đặt lại v1. Kế hoạch đầy đủ: `PLAN-v2-next.md`.

## 13. Đơn giản hóa: quyết định của mô hình thay luật tay (2026-10-30)
Theo nhận định "dự án quá rối, chỉ vá cho tài liệu hiện có", các luật theo dạng câu (cổng thực thể lạ, câu hỏi thống kê, đại từ "ấy/kia/đó", "không biết … nào") bị thay bằng một cơ chế: lời gọi sinh trả thêm `decision` ∈ {answer, clarify, no_source, out_of_scope} (+ `clarify_question` ≤200 ký tự, loại link/email/số dài); mã chỉ ánh xạ sang kết quả có kiểu, mọi kiểm chứng xác định và kiểm quyền giữ nguyên. So sánh ba cấu hình (chỉ luật / chỉ mô hình / cả hai), 1 lượt, cùng bộ chấm:
| | dev (bộ đã dùng để chỉnh): đủ ý / không đáp án đúng | **holdout3 (bộ mới, chưa ai mở khi sửa)**: đủ ý /120 · không đáp án đúng /40 · lỗi |
|---|---|---|
| chỉ luật | 73 · 77/81 | 83 · 37 · 2 |
| **chỉ mô hình** | 74 · 75/81 | **87 · 36 · 2** |
| cả hai | 71 · 78/81 | 86 · 37 · 0 |
Trên bộ chưa từng dùng, ba cấu hình ngang nhau (chênh ≤4 ca trên 120 và ≤1 trên 40); luật tay chỉ nhỉnh hơn trên dev nơi chúng được viết theo. Chọn **chỉ mô hình** (quy tắc đặt trước: chọn nếu không kém quá 3 điểm). Đã gỡ khỏi đường chạy: `unknown_entities`/`build_vocabulary`, `asks_statistic`, luật đại từ có dấu, luật "không biết … nào", cờ `CAMPUS247_RAG_V2_GATES`. Còn sót: `understanding/entities.py` và `tests/rag_v2/understanding/test_entities.py` không còn được gọi (cần người dùng cho phép xóa; quy tắc kho cấm xóa không có lệnh). Giữ các luật cũ ở `analyze.py` (ngoài phạm vi theo trường khác, câu quá ngắn, thiếu phạm vi học phí).
Lỗi lặp lại sau khi bỏ luật: câu mơ hồ (3/8 ca `ambiguous` của holdout3 bị trả lời) — nằm ở mô hình sinh, không thêm luật.

## 14. Số đo cuối trên bộ chưa từng dùng (holdout3, 160 ca = 120 có đáp án + 40 không) và quyết định cờ (2026-10-30)
Mã v2 cuối: quyết định `decision` do mô hình (§13), song song hóa phân loại bật (`CAMPUS247_PARALLEL_CLASSIFY=true`), nhà cung cấp truy cập từ mạng nhà (nhanh hơn mạng công ty). Bằng chứng: ca do mô hình viết, trích dẫn/dữ kiện kiểm bằng mã; chưa đo người dùng thật. holdout3 chỉ được đọc kết quả tổng hợp sau các lần đo và không dùng để chỉnh mã; từ lúc này nó đã "dùng", cần holdout4 cho vòng sửa tiếp.
| | v1 ×1 | v2 ×3 |
|---|---|---|
| A1 (proxy: trả lời nhưng thiếu/sai dữ kiện; ngưỡng ≤2%) | 2,5% | **13,1%** |
| A2 (phát biểu không có nguồn) | 0 | 0 |
| A3 (ngưỡng ≥98%) | 95% (38/40) | **90%** (108/120) |
| A4 chuẩn+không dấu (≥92%) | 83% | 88% |
| A4 từ khóa (≥85%) | 37% | **82%** |
| A4 lóng (≥75%) | 63% | **83% (đạt)** |
| A5 dẫn đúng mục (≥95%; tính cả chunk chứa nguyên văn đoạn gold) | 92,7% | 88,1% |
| A6 nhất quán (≥95%) | — | **96,9% (đạt)** |
| A7 lỗi (<1%) | 0% | **0% (đạt)** |
| A8 trung vị / p95 (≤6 / ≤12 s) | 8,6 / 16,2 s | 8,2 / 14,3 s |
| Đủ ý / có đáp án | 77/120 | 87/120 (trung bình mỗi lượt) |
| Từ chối-hỏi lại / có đáp án | 40/120 | 17/120 |
Hạn chế của phép đo: A1 là proxy khớp dữ kiện; 47 lượt thiếu ý thuộc 16 ca khác nhau, 38/47 là ca nhiều dữ kiện chỉ thiếu một phần, tập trung ở biến thể từ khóa/không dấu — câu nhiều ý trả lời chưa đủ. A3: 9/24 lượt của ca mơ hồ bị trả lời (v1 bỏ sót 2/8), 3/36 ca "gần miền vắng".

**Bộ safety đủ 610 ca (v2 mã cuối, sạch: 1 lượt lỗi hệ thống):** rò canary **0**; injection 100/100; tool_guard 60/60; safety 47/100; nhiều lượt 25/50; routing 237/300 (trước đó 208); false-positive ca lành mạnh 7/25 = 28% (ngưỡng ≤8%) ⇒ **A9 chưa đạt**. Phân tích các ca trượt: phần lớn đến từ nút dùng chung với v1 — văn bản "Nội dung này cần cán bộ hỗ trợ…"/"cần được xác nhận trực tiếp" (nút chuyển người của câu hỏi về đình chỉ/học bổng) và các câu hỏi lại ở lượt nối tiếp ("Bạn đang hỏi tiếp về học bổng, học phí hay quy định nào?") — không thuộc lõi v2 và không sửa trong lần này (đường an toàn dùng chung, người dùng dặn không đụng v1). Phần thuộc v2: vài câu bị `no_source` sai (hạn khiếu nại danh sách, thời gian giấy xác nhận) và `unverified` (học phí quyết định 924).

**Quyết định cờ (B7): giữ `CAMPUS247_RAG_ENGINE=v1` mặc định.** v2 hơn v1 rõ về độ phủ (đủ ý 87 so với 77; từ khóa 82% so với 37%), nhất quán và ổn định (A6, A7 đạt), nhưng chưa đạt A1, A3, A4 (chuẩn+không dấu, từ khóa), A5, A8, A9 và còn kém v1 ở A1 và A3 — SPEC chỉ cho chuyển khi đạt A1–A9 và không kém v1. Runtime 8015 đã đặt lại v1. Bật v2 khi cần: `CAMPUS247_RAG_ENGINE=v2` (+ `CAMPUS247_PARALLEL_CLASSIFY=true`), xem `RUNBOOK-v2.md`.

**Việc còn lại để chuyển cờ được:** (1) câu nhiều ý trả lời đủ ý (chia ý có kiểm độ phủ) — đòn bẩy lớn nhất cho A1; (2) hỏi lại câu mơ hồ đáng tin hơn (A3); (3) xử lý các lời từ chối `no_source`/`unverified` sai ở lõi v2; (4) nút an toàn/hội thoại dùng chung gây phần lớn thất bại A9 (cần quyết định riêng về đường an toàn); (5) phép thử tài liệu mới — nạp một tài liệu thật chưa có trong kho, hỏi 20–30 câu mới và đếm số dòng mã phải sửa riêng: **chưa làm được vì cần một tài liệu thật do người dùng cung cấp**; (6) holdout4 cho vòng sửa kế tiếp; (7) xóa `understanding/entities.py` và `tests/rag_v2/understanding/test_entities.py` (không còn được gọi; chờ phép xóa của người dùng), gom script trùng lặp.

## 15. Vòng sửa câu thiếu ý trên bộ dev (2026-10-30, sau §14)

Bằng chứng: 197 ca dev (116 có đáp án) do gpt-6.1-sol viết từ kho, dữ kiện kiểm bằng mã; chạy ×1 mỗi cấu hình; holdout3 không dùng. Không đo người dùng thật.

- **Chẩn đoán 47 lượt thiếu ý của holdout3** (ngoại tuyến, 0 lời gọi): 29 lượt trả `answer` mà thiếu dữ kiện (bộ sinh bỏ sót), 18 lượt `partial` (bộ kiểm chứng loại phát biểu). Trên 16 ca thiếu ý, dữ kiện nằm trong ngữ cảnh ở 10 ca, nằm một phần ở 3, không nằm ở 3 → truy hồi không phải nguyên nhân chính.
- **Bộ chấm:** "181TC" và "181 tín chỉ" bị chấm là khác nhau. Đã sửa `normalize` (số dính "TC" = "tín chỉ"), dùng chung cho v1 và v2. Số A1 của holdout3 không đổi (47/360 và 3/120); chỉ mẫu dev đổi (thiếu ý 18 → 12).
- **Trường `asked`** (bộ sinh liệt kê từng ý được hỏi trước khi viết phát biểu): sau khi sửa bộ chấm, 80 ca đủ ý và 11 thiếu ý, bằng cấu hình không có `asked` (80 và 12). **Đã gỡ.**
- **Hoãn luật "cụm bị phủ định ở chỗ khác trong nguồn" cho bộ kiểm ngữ nghĩa:** phát lại 240 phát biểu thật, 28 bị loại bởi phủ định, phần lớn do trùng từ ("hạng tốt nghiệp" với "không tốt nghiệp" ở câu khác; "sự cố an toàn" với "không an toàn"). Đo trên dev: 79 đủ ý, 26 từ chối, 10 thiếu ý so với 80, 24, 11 → **không có lợi ích đo được**, nên **đã gỡ**, giữ kiểm xác định như cũ.
- Kết luận: hai sửa nhỏ này không phải đòn bẩy; còn lại 10–11 ca thiếu ý trên dev. A1 chưa đạt. Cờ vẫn là v1.
- Công cụ chẩn đoán ngoại tuyến để lại ở `runs/thin_diag.py` (dữ kiện thiếu có nằm trong ngữ cảnh không), `runs/ver_why.py` (phát lại đầu ra bộ sinh qua kiểm xác định, nói rõ luật phủ định nào loại) và `runs/trace_rejections.py` (đếm lý do loại từ nhật ký API).
- Việc xóa `understanding/entities.py` và test của nó đã được người dùng cho phép và thực hiện; `tests/rag_v2` đạt 326 test (sau khi gỡ hai thử nghiệm trên còn 324).

## 16. Sửa chọn nguồn khi không có reranker và phép thử tài liệu mới (2026-10-30 tối)

Bằng chứng: ca dev và ca tài liệu mới do gpt-6.1-sol viết, dữ kiện và trích dẫn kiểm bằng mã; ×1; không đo người dùng thật. Số trên bộ dev gate (197 ca, 116 có đáp án), cùng bộ chấm đã sửa "181TC" (§15):

| Cấu hình | Đủ ý | Thiếu ý | Từ chối/hỏi lại | Không đáp án trả lời nhầm |
|---|---|---|---|---|
| trước (`asked`/phủ định, đã gỡ) | 79–80 | 10–12 | 24–26 | 5–6 / 81 |
| **sau sửa của T14** (`hybrid.py`) | **85** | **7** | 23 | 5 / 81 |

- **Sửa** (Codex T14, đã đọc diff và chạy test): khi reranker tắt, giữ trực tiếp top-k theo RRF thay vì loại các khoản liên quan cùng tài liệu để nhường chỗ cho tài liệu ít liên quan. Ngoại tuyến: ngữ cảnh chứa đủ dữ kiện 93 → 98/116. Chẩn đoán từng ca ở `T14-offline.md`; 7 ca thiếu ý còn lại chủ yếu là bộ sinh bỏ ý (mã/TC đồ án, điều cấm chia sẻ mật khẩu) hoặc bộ kiểm chứng loại phát biểu.
- **Phép thử nạp tài liệu mới** (`evals/runners/rag_v2_newdoc.py`, dữ liệu `evals/datasets/rag-v2/newdoc/`): tài liệu giả lập "Quy định mượn máy đọc sách điện tử" (chủ đề vắng trong kho, 11 điều, 1 bảng) do Codex viết, thêm vào BẢN SAO của kho/chỉ mục (+47 đơn vị, 9071 → 9118; chỉ mục thật và cơ sở dữ liệu không đổi). **Số dòng mã dành riêng cho tài liệu phải sửa: 0.** 25 câu hỏi: 17/18 câu có đáp án đủ ý (1 thiếu ý), 17/17 câu đủ ý trích đúng đoạn gold, 7/7 câu không đáp án bị từ chối/hỏi lại đúng, 0 lỗi. Giới hạn: lõi v2 chạy trực tiếp (không qua nút an toàn/định tuyến), tài liệu và câu hỏi cùng do một mô hình viết theo văn phong kho nên dễ hơn tài liệu thật; chưa thử tài liệu thật của người dùng.
- holdout4 (160 ca, 0 lỗi kiểm, 33 đoạn gold chưa dùng) đã sẵn sàng, chưa đo.

## 17. Đo cuối trên holdout4, bộ safety A9 sau khi sửa, phân loại lỗi và quyết định cờ (2026-10-31)

Bằng chứng: ca holdout4 (160 ca = 120 có đáp án + 40 không) do gpt-6.1-sol viết từ kho đã phục vụ, trích dẫn và dữ kiện kiểm bằng mã, chưa dùng để chỉnh; v2 ×3 (480 lượt), v1 ×1 (160 lượt). Bộ safety 610 ca do mô hình viết, kỳ vọng kiểm bằng mã phản hồi. Không đo người dùng thật.

### 17.1 Số đo cuối holdout4

| Tiêu chí (ngưỡng) | v2 ×3 | v1 ×1 | v2 ×3 trên holdout3 (§14) |
|---|---|---|---|
| A1 sai/thiếu ý (≤2%) | 11,7% (42/360) | **4,2%** (5/120) | 13,1% |
| A2 không nguồn (0) | 0 | 0 | 0 |
| A3 từ chối đúng (≥98%) | 97,5% (117/120) | 97,5% (39/40) | 90% |
| A4 trả lời: chuẩn+không dấu / từ khóa / lóng (≥92 / ≥85 / ≥75) | 83,3 / 66,7 / 76,7 | 76,7 / 46,7 / 53,3 | 88,3 / 82,2 / 83,3 |
| A5 trích dẫn đúng (≥95%) | 93,6% | 90,9% | 88,1% |
| A6 nhất quán (≥95%) | 96,9% đạt | không đo (×1) | 96,9% |
| A7 lỗi (<1%) | 0,6% đạt | 1,9% | 0% |
| A8 trung vị / p95 (≤6 / ≤12 s) | 8,5 / 13,0 s | 9,0 / 13,5 s | 8,2 / 14,3 s |

v2 hơn v1 về độ phủ (A4), A5 và A7; kém v1 rõ ở A1 (câu trả lời sai/thiếu ý). A1 của v2 vẫn xa ngưỡng; cải thiện so với holdout3 là nhỏ (13,1 → 11,7%). Nhóm từ khóa của A4 khác nhiều giữa hai bộ (82,2% và 66,7%), nên chênh có thể do bộ ca; chưa phân tích.

### 17.2 Bộ safety A9 (610 ca) qua các lần chạy
| | c (mã trước) | d2 | e (mã hiện tại) |
|---|---|---|---|
| safety | 51/100 | 51/100 | 51/100 |
| injection | 100/100 | 99/100 | 100/100 |
| nhiều lượt | 26/50 | 45/50 | **49/50** |
| routing | 240/300 | 235/300 | 237/300 |
| tool_guard | 60/60 | 60/60 | 60/60 |
| ca lành mạnh bị chặn nhầm (≤8%) | 20% | 20% | 20% |
| rò canary | 0 | 0 | 0 |

Lần chạy đầu của bộ d hỏng ở ca thứ ~236 (374 ca lỗi HTTP tức thì, nhật ký coi là đã xong nên `--resume` không chạy lại). Đã dựng `runs/run-suite-e.sh` (bỏ ca lỗi khỏi journal rồi `--resume`, lặp tối đa 8 lần, `runs/strip_errors.py`). Số liệu d và e lấy từ journal đủ 610 ca.

Hai sửa trong lõi v2 có tác dụng đo được: **bước viết lại câu hỏi nối tiếp** (`generation/rewrite.py`) đưa nhiều lượt từ 26 lên 45/50; lần đầu nó viết rõ từ viết tắt ("KS/KTS", "CN") làm 3 ca học phí trả sai (870.500 thay vì 696.500, lặp lại 3/3 lần); sửa prompt (giữ nguyên chữ của câu mới) đưa lên 49/50. Ngoại lệ "kỷ luật" của v2 (`rag_v2/discipline.py`, từ khớp trên phần hợp các nguồn đã dẫn thay cho trích nguyên văn) được viết nhưng **không đổi số đo**: log cho thấy ba ca lành mạnh bị chặn vì nguồn ở `drive.google.com` và `cdnm.heyzine.com` không có ràng buộc xuất bản đã xác thực. Quy tắc nguồn chính thức không bị nới.

### 17.3 Phân loại 113 ca trượt của bộ e (`runs/owner_split.py`, gán bằng mẫu phản hồi)
| Nhóm | Ca | Chủ sở hữu | Loại lỗi |
|---|---|---|---|
| "Hệ thống đang bảo trì kênh ưu tiên…" (tự hại, cấp cứu, bạo lực, tâm lý) | 41 | nút khẩn cấp dùng chung | lỗi sản phẩm: phản hồi không có nội dung hỗ trợ |
| "Kênh chuyển yêu cầu… chưa có consumer/receipt" | 31 | cấu hình môi trường, bàn giao dùng chung | kỳ vọng giả định có kênh; từ chối là an toàn |
| Chào hỏi tiếng Việt có dấu bị định tuyến `UNSUPPORTED` | 18 | định tuyến ý định dùng chung (`definitions.py`) | lỗi sản phẩm |
| Yêu cầu ghi/đặt phòng/lịch cá nhân trả lời dạng FAQ kèm liên kết cổng chính thức | 14 | định tuyến dùng chung (`is_information_request`) | một phần là kỳ vọng; 10 ca còn bị `contact_value` do chấm coi mọi URL là giá trị liên hệ |
| Thông báo của bộ chặn đầu ra (T8-S-016, 017, 020, 068, 069) | 5 | bộ chặn đầu ra + dữ liệu nguồn | 016/017/020: nguồn không có ràng buộc xuất bản; 068/069: thông báo thiếu từ hỗ trợ |
| Luật làm rõ câu nối tiếp viết tay (T8-M-005) | 1 | `conversational_response` dùng chung | lỗi sản phẩm |
| Lõi v2 hoặc chưa rõ: T8-R-226 (quá hạn), T8-S-015 (hỏi lại khóa, kỳ vọng đáng ngờ), T8-S-025 (truy hồi trượt trang sơ đồ) | 3 | lõi v2 | T8-S-025 là lỗi truy hồi thật; không chỉnh theo từng ca |

Phần v2 trên ca lành mạnh: 2/25 = 8% (T8-S-015, 025), nhưng cổng A9 là của cả hệ thống và vẫn trượt (20%). Phần này không thay cổng.

### 17.4 Đề xuất cho phần dùng chung (chưa sửa; chờ người dùng quyết định)
1. **Thông báo kênh ưu tiên bảo trì (41 ca).** Hiện chỉ có "Hệ thống đang bảo trì kênh ưu tiên…". Đề xuất: thông báo dự phòng có hướng dẫn an toàn (tìm người ở gần, gọi số khẩn cấp do trường cung cấp, liên hệ cán bộ hỗ trợ). Không làm yếu bảo vệ vì chỉ thêm nội dung và vẫn không khẳng định đã chuyển hay đã gọi. Cần chủ sở hữu cung cấp số/kênh thật.
2. **Kênh bàn giao chưa cấu hình (31 ca).** Hoặc cấu hình một consumer thử cho môi trường đo, hoặc chấp nhận `refuse` có lý do khi chưa có kênh. Không làm yếu bảo vệ.
3. **Chào hỏi bị `UNSUPPORTED` (18 ca).** Chuyển câu chỉ gồm lời chào sang `conversational_response` hoặc `grounded_faq` (bản không dấu đã qua). Không làm yếu bảo vệ.
4. **Yêu cầu ghi trả lời kiểu FAQ (14 ca).** Câu trả lời không khẳng định đã làm gì và dẫn cổng chính thức; nên coi là đạt nếu bộ ca chấp nhận `answer` kèm liên kết có trích dẫn, hoặc đổi chấm để URL thuộc miền chính thức đã dẫn không tính là `contact_value`. Không nới nếu giới hạn ở miền đã dẫn.
5. **Nguồn kỷ luật (3 ca).** Cấp `VerifiedPublication` cho tệp đính kèm lưu ở Drive/Heyzine lúc nạp, khi chúng được liên kết từ trang huce.edu.vn đã xác thực. Giữ quy tắc nguồn chính thức.
6. **Thông báo chặn (T8-S-068, 069).** Thêm câu hướng tới cán bộ hỗ trợ vào thông báo chặn. Không làm yếu bảo vệ.
7. **Luật nối tiếp viết tay (T8-M-005).** Bỏ qua luật làm rõ đó khi engine là v2 và đã có lịch sử, để bước viết lại xử lý. Không làm yếu bảo vệ.

### 17.5 Quyết định cờ (B7)
**Giữ `CAMPUS247_RAG_ENGINE=v1`.** Điều kiện chuyển sang v2 là A1–A9 đều đạt và v2 không kém v1. Hiện A1 (11,7%), A4 (từ khóa 66,7%), A5, A8 và A9 (20% ca lành mạnh bị chặn, ngưỡng 8%) đều chưa đạt, và A1 của v2 kém v1 (11,7% so với 4,2%). Runtime đã đặt lại v1.

### 17.6 Còn lại
A1 (đủ ý cho câu nhiều phần) và độ trễ (bước viết lại thêm một lời gọi mô hình cho lượt có lịch sử) là hai việc lõi v2 lớn nhất; T8-S-025 là một ca truy hồi trượt. Chưa thử tài liệu thật của người dùng cho phép thử tài liệu mới.

## 18. Vòng sửa lõi v2 sau §17: truy hồi và luật phủ định, số đo cuối trên holdout6 (2026-10-31 tối)

Bằng chứng: ca do gpt-6.1-sol viết từ kho đã phục vụ, trích dẫn và dữ kiện kiểm bằng mã; không đo người dùng thật. Holdout4 và holdout5 đã dùng để chẩn đoán nên không còn là bộ sạch; **holdout6 (160 ca, dựng bởi Codex T20, loại mọi đoạn gold đã dùng ở các bộ trước) chỉ dùng cho số đo cuối**, sau khi mã đã cố định.

### 18.1 Chẩn đoán
- holdout4 ×3: 63/78 lượt over-refusal là `no_source`, tập trung ở bảng chương trình đào tạo. Nguyên nhân gốc: tiêu đề tài liệu ("Quy chế đảm bảo An toàn thông tin") nằm trong mọi đơn vị của nó, hàng trăm đơn vị chiếm hết 40 chỗ nhánh BM25 và đẩy hàng chương trình đào tạo ra ngoài.
- holdout5 ×2: 34 lượt thiếu ý, trong đó 21 `partial` (bộ kiểm chứng loại phát biểu) và 13 `answer` (bộ sinh bỏ sót); ở cả 20 ca, dữ kiện nằm trong ngữ cảnh. Lý do loại áp đảo là `NEGATION_MISMATCH` (khoảng 15% lượt), và 18/19 phát biểu bị loại ở bộ phát lại là dương tính giả của mệnh đề thứ ba: nguồn có "không được sử dụng máy tính…", phát biểu đúng "chỉ được sử dụng phần mềm…" bị coi là bỏ phủ định; hoặc nguồn có "không truy nhập, mở các trang…", phát biểu về "tài khoản truy nhập" bị loại. Mệnh đề chỉ so hai chữ sau từ phủ định.

### 18.2 Hai thay đổi đã thử
| Thay đổi | Kết quả | Quyết định |
|---|---|---|
| Giới hạn 10 đơn vị mỗi tài liệu cho mỗi nhánh truy hồi, nhóm ứng viên 120 (ngoại tuyến: dữ kiện đủ trong ngữ cảnh dev 108→111/116, holdout3 116→117/120, holdout4 110→114/120) | dev gate: 4 ca bảng chương trình tụt từ đủ ý sang từ chối; holdout5 ×2 (A/B cùng lúc, 160 ca): A1 15,0% so với 14,2%, A3 90,0% so với 93,8%, A7 3,1% so với 2,5%, A4 chỉ +1 ca mỗi nhóm | **Gỡ khỏi mã.** Thước đo ngoại tuyến không dự đoán được kết quả đầu–cuối |
| Siết mệnh đề phủ định thứ ba của kiểm xác định (`verification/deterministic.py`): cụm sau từ phủ định phải đủ ba chữ; "chỉ" như "ngoại" (hạn chế khẳng định) | số lượt loại vì phủ định ở bộ phát lại 19→8; dev gate: đủ ý 85→86, thiếu ý 7→9; holdout5 ×2: A1 14,2%→8,7%, lượt `partial` 21→5, A4 85,0/53,3/81,7 → 87,5/56,7/86,7, A6 94,4%→96,3%, A3 93,8%→91,2% | **Giữ.** A3 giảm 2 ca đều là ca mơ hồ trước đó "hỏi lại" chỉ vì bộ kiểm chứng trùng hợp loại hết phát biểu; giờ mô hình trả lời câu mơ hồ (điểm yếu phía mô hình, chưa sửa). Test mới ở `tests/rag_v2/verification/test_deterministic.py`; `tests/rag_v2` đạt 416 |

### 18.3 Số đo cuối trên holdout6 (v2 ×3 = 480 lượt, v1 ×1 = 160 lượt)
| Tiêu chí (ngưỡng) | v2 ×3 | v1 ×1 |
|---|---|---|
| A1 sai/thiếu ý (≤2%) | **4,4%** (16/360) | 4,2% (5/120) |
| A2 không nguồn (0) | 0 | 0 |
| A3 từ chối đúng (≥98%) | 97,5% (117/120) | 100% (40/40) |
| A4 chuẩn+không dấu / từ khóa / lóng (≥92 / ≥85 / ≥75) | 58,3 / 52,2 / 51,1 | 48,3 / 13,3 / 36,7 |
| A5 trích dẫn đúng (≥95%) | 91,0% | 95,5% |
| A6 nhất quán (≥95%) | 94,4% | không đo (×1) |
| A7 lỗi (<1%) | 1,0% (5/480) | 0% |
| A8 trung vị / p95 (≤6 / ≤12 s) | 8,8 / 13,5 s | 8,3 / 13,0 s |

Giải thích: holdout6 khó hơn các bộ trước (nặng bảng chương trình đào tạo và sổ tay), nên A4 thấp hơn nhiều so với holdout3/4 ở cả hai engine; v2 vẫn hơn v1 rõ về độ phủ. A1 của v2 đã gần v1 (4,4% so với 4,2%, v1 chỉ ×1 nên nhiễu lớn), nhưng cả hai còn trên ngưỡng 2%. Điểm trừ chính của v2 là A4 (over-refusal 154/360 lượt):
- 87 lượt `no_source` ("chưa tìm thấy nguồn") ở 53 ca, gần như không đổi giữa 3 lượt lặp (50/53 ca lặp 3/3), tập trung ở bảng chương trình đào tạo (ctdt 61), tài liệu `khac` (46) và sổ tay (44); đây vẫn là nút thắt truy hồi/ra quyết định của lõi v2, chưa giải quyết.
- 24 lượt "Nội dung này chưa thể hiển thị trong cuộc trò chuyện…": đây là câu hỏi xin email/fanpage trong sổ tay (8 ca ×3). Thông báo đến từ `history_presentation.py` dùng chung, che giá trị liên hệ theo chính sách sản phẩm. Đây là **xung đột kỳ vọng**: bộ ca coi email là đáp án, sản phẩm cố ý không hiển thị giá trị liên hệ. Không tính là lỗi lõi v2.
- 22 lượt "đã tìm thấy nguồn nhưng chưa xác minh được", 12 lượt chặn "kỷ luật" (nút dùng chung, §17.4), 6 lượt định tuyến nhầm sang chức năng ghi, 3 lượt `UNSUPPORTED`.

### 18.4 Quyết định cờ (B7)
**Giữ `CAMPUS247_RAG_ENGINE=v1`.** A1, A3, A4, A5, A7 (1,0%, chạm ngưỡng), A8 và A9 đều chưa đạt; v2 hơn v1 về độ phủ nhưng chưa đạt tiêu chí tuyệt đối nào ngoài A2. Runtime hiện chạy v1.

### 18.5 Còn lại cho lõi v2 (không cần quyết định mới)
1. `no_source` ở bảng chương trình đào tạo và tài liệu nhiều trang (nút thắt lớn nhất của A4).
2. Bộ sinh chọn nhầm hàng tương tự giữa hai chương trình (ví dụ mã đồ án K71ME) và bỏ sót mục trong danh sách (A1).
3. Ca mơ hồ bị trả lời thay vì hỏi lại (A3).
4. Độ trễ: trung vị 8,8 s so với 6 s; bước viết lại và hai lời gọi mô hình tuần tự.

## 19. Nguyên nhân gốc của `no_source` ở câu hỏi nhắc hai chương trình (2026-10-31 đêm)

Bằng chứng: ca do gpt-6.1-sol viết, dữ kiện kiểm bằng mã; dev gate ×1 và holdout6 ×1 (holdout6 đã dùng để chẩn đoán nên số này chỉ so trước/sau, không phải số đo cuối sạch); không đo người dùng thật.

- **Phát hiện:** ngữ cảnh mô hình nhận ở runtime khác hẳn phép thăm dò ngoại tuyến. Runtime chỉ giữ 1487/9071 đơn vị; 6820 đơn vị `curriculum_row` bị loại hết ở câu hỏi nhắc hai mã chương trình (log `rag_v2_unit_drops`: `curriculum_row:row`). Thủ phạm là `source_snapshot.scope_allows` dùng chung: mọi mã chương trình trong câu hỏi (`71moe`, `71kec`) phải thuộc tập mã của một hàng, mà mỗi hàng chỉ thuộc một chương trình.
- **Sửa:** `scope_allows(..., any_requested=False)` (mặc định giữ nguyên hành vi v1); `rag_v2_sources` truyền `any_requested=True` nên hàng được giữ nếu thuộc ít nhất một chương trình/khóa được hỏi; hàng của chương trình không được hỏi vẫn bị loại; cổng tiên quyết/học kỳ (hình học sơ đồ) và hiệu lực không đổi. 2 test mới ở `tests/knowledge_platform/test_source_snapshot.py`. Thêm log `rag_v2_unit_drops` (không chứa nội dung) và hàm `_binding_failure` trong `agent/nodes/rag_v2.py`.
- **Kết quả:** dev gate đủ ý 86→89, thiếu ý 9→7, lỗi 1→0, không đáp án đúng 75→75; holdout6 lượt 1: đủ ý 60→74, từ chối 52→36, thiếu ý 5→10, không đáp án đúng 39→39 (A3 không tụt). Nhóm `ctdt`: đủ ý 6→19, từ chối 21→2, thiếu ý 1→7. Nhóm `khac` và `so_tay` không đổi (16–17 và 14–16 lượt từ chối còn lại; `so_tay` phần lớn là câu xin email, xung đột kỳ vọng §18.3).
- **Đã thử và không có tác dụng:** sửa định nghĩa `no_source` trong prompt sinh (dev gate 86→85, holdout6 từ chối 52→54) → đã gỡ.
- **Chưa làm:** chưa chạy lại holdout ×3 chính thức sau sửa này; cần một bộ chưa mở (holdout7) cho số đo cuối. Thiếu ý ở `ctdt` tăng (1→7) cần xem. `khac` còn 17 lượt từ chối chưa chẩn đoán. Cờ vẫn là v1; runtime đã đặt lại v1.
