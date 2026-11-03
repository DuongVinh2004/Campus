# W12 — tách danh sách đánh số phẳng thành row unit

Ngày thực hiện: 2026-11-03. Workspace `C:\Users\Duong Vinh\Vinh`, branch `rag-v2-hardening`.

## Thay đổi

- `services/api/src/campus247/rag_v2/ingest/tables.py`: thêm `flat_list_rows`, trả về offset đầu/cuối dòng và ngữ cảnh đứng trước.
- `services/api/src/campus247/rag_v2/ingest/units.py`: tạo `table_row` cho dòng được nhận diện, đóng segment ngay khi hết chuỗi, nâng `SPLITTER_VERSION` từ `structural-spans-v2` lên `structural-spans-v3`.
- `tests/rag_v2/test_flat_list_rows.py`: 15 kiểm thử mới; đọc ba chunk trang 25 trực tiếp từ corpus, kiểm tra chuỗi ngắn/sai thứ tự, ngắt dòng/trang, pipe table, LF/CRLF, source spans, tái ghép nguồn và coverage.
- `evals/results/audit-opus-20261101/w12_sweep.py`: sao chép `l14_sweep.py`, thêm `--index`, `--output`, giữ mặc định index là `embedded2`; ghi checkpoint từng ca, hash context và chunk được chọn. Không sửa script gốc.
- Tạo mới `data/rag_v2_index/embedded3` cùng các tệp bằng chứng W12 trong thư mục audit. CLI chỉ append cache embedding theo quyền trong brief.

Không thay kỳ vọng của kiểm thử cũ, corpus, retrieval/fusion/packing hoặc runtime đang chạy; không commit/push.

## Quy tắc nhận diện và bảo toàn nguồn

Chỉ nhận một khối liên tục ít nhất 8 dòng, mỗi dòng khớp `^(\d{1,3})\s+\S`, không chứa `|`, và toàn bộ số thứ tự phải tăng đúng 1. Khối có số lặp, giảm hoặc nhảy số được giữ nguyên. Không nối qua dòng trắng, dòng tiêu đề trang hay dòng tiếp nối bị xuống hàng. Không chấp nhận thụt đầu dòng, số 4 chữ số hoặc số dạng `1.`. Đây là lựa chọn bảo thủ, không dự đoán cột hay giá trị bị thiếu.

Mỗi dòng nhận diện thành `table_row` với body là substring nguồn nguyên vẹn, bao gồm newline gốc. Lấy tối đa hai dòng liền trước làm context, cùng tiêu đề tài liệu qua cơ chế sẵn có. Context nằm trước `⟦RAG_V2_SOURCE⟧`, có marker span và không được dùng làm nội dung trích dẫn. Đoạn tiếp theo sau chuỗi được tách khỏi dòng cuối, không bị gán vào row cuối.

Trên trang 25, chuỗi 26–45 có 20 dòng; dòng 45 bị xuống hàng nên detector dừng trước phần tiếp nối. Dòng Logistics đô thị được giữ nguyên: `29 Logistics đô thị Cầu Đường Cử nhân\n`. Không nối hoặc suy diễn các dòng 46–51.

Đã rà nơi dùng/pin phiên bản trong ingest, `index_store`, builder và tests: các kiểm tra dùng chung `SPLITTER_VERSION`, không có literal v2 cần sửa thêm. `read_index` và kiểm tra base của builder tiếp tục từ chối snapshot sai phiên bản. Không dùng `--base embedded2`; cache chỉ tái dùng vector khi identity mô hình và hash toàn bộ text khớp. `MemoryIndex` dùng bởi phép đo offline đọc được cả hai snapshot qua cơ chế sẵn có, không nới kiểm tra runtime.

## Số lượng và coverage

| Chỉ số | embedded2 | embedded3 |
| --- | ---: | ---: |
| Chunk | 2.019 | 2.019 |
| Tổng unit | 9.173 | 9.251 |
| `table_row` | 626 | 705 |
| Fact | 136 | 136 |

Tăng ròng **78 unit**, gồm **79 ID table_row mới**. Detector nhận diện 376 lần xuất hiện dòng trên 24 chunk; sau hợp nhất provenance có 127 row unit, trong đó 48 ID đã tồn tại. So sánh toàn bộ unit: 87 ID mới, 9 ID cũ không còn trong snapshot mới, 48 ID chung có metadata/text thay đổi. Đây là khác biệt giữa hai snapshot; không xóa dữ liệu index cũ.

Toàn bộ **9.070 unit của các chunk không có chuỗi phù hợp giống hệt baseline**, kể cả metadata và text. `check_units` trả 0 issue; cả 6 doc family có coverage và min_chunk_coverage bằng 1. Tệp facts của hai index có SHA-256 giống nhau. Bằng chứng máy kiểm tra: `../w12-unit-analysis.json`.

Các chunk có dòng được nhận diện (số dòng tính riêng trên từng chunk, trước hợp nhất provenance):

| Tài liệu / trang | Chunk ID | Dòng |
| --- | --- | ---: |
| HUCE + JAXTINA / 5 | `01a16d17-1b9d-73c4-ad76-7667add6a06d` | 15 |
| HUCE + JAXTINA / 5 | `01a16d17-1ba2-7e5e-81cc-960089adc52a` | 15 |
| HUCE + JAXTINA / 5 | `01a16d17-1ba8-77b6-ab2e-cf4bc27dd106` | 15 |
| HUCE + JAXTINA / 6 | `01a16d17-1bc9-70d6-92a6-2e3ef4039fe5` | 11 |
| HUCE + JAXTINA / 6 | `01a16d17-1bcd-7229-8529-02e4b6274f4c` | 11 |
| HUCE + JAXTINA / 6 | `01a16d17-1bd2-732b-96fd-4cf126e73c99` | 11 |
| Sổ tay / 24 | `01a16d1e-5df2-7a57-ba93-b461684fb7b6` | 24 |
| Sổ tay / 24 | `01a16d1e-5df5-7a67-8653-16e3a6ad3632` | 24 |
| Sổ tay / 24 | `01a16d1e-5df9-7e46-96f2-4e8ba14be0a5` | 24 |
| Sổ tay / 25 | `01a16d1e-5dfd-71bf-9f08-60dd0a0d5a3f` | 20 |
| Sổ tay / 25 | `01a16d1e-5e00-7e06-b5a8-f4e3b6817b57` | 20 |
| Sổ tay / 25 | `01a16d1e-5e03-7aa1-92fd-b1de97dd4cc6` | 20 |
| Kỹ thuật Vật liệu K70 trở về trước / 2 | `01a16d41-bdaf-7eaa-a0fc-a6bfd1cefb95` | 8 |
| Kỹ thuật Vật liệu K70 trở về trước / 2 | `01a16d41-bdb5-7738-8c5c-c68b8f39eb60` | 8 |
| Kỹ thuật Vật liệu K70 trở về trước / 2 | `01a16d41-bdbc-7fb8-9832-64e07b6612f5` | 8 |
| Kỹ thuật Vật liệu K71MSE / 2 | `01a16d41-c498-7322-8ee6-b7efc4b39cac` | 14 |
| Kỹ thuật Vật liệu K71MSE / 2 | `01a16d41-c49e-7c27-88d5-242048c6c00b` | 14 |
| Kiến trúc 2025 / 1 | `01a16eec-221e-7a24-a7ad-7768321fdced` | 26 |
| Kiến trúc 2025 / 1 | `01a16eec-2226-728d-bae5-65274db6ad3f` | 26 |
| Kiến trúc 2025 / 1 | `01a16eec-222a-7f8c-a220-4afbd49d9e0d` | 26 |
| Kiến trúc 2025 / 2 | `01a16eec-222f-787a-b8ea-959a6236cd35` | 9 |
| Kiến trúc 2025 / 2 | `01a16eec-2235-70ee-9ab0-d7b50b31aa82` | 9 |
| Kiến trúc 2025 / 2 | `01a16eec-223a-7915-86be-44147c52c834` | 9 |
| Kiến trúc 2025 / 2 | `01a16eec-2240-794b-87b3-9c1dd18a1ee0` | 9 |

## Build index mới

Đã kiểm tra `--help`, xác minh `embedded3` chưa tồn tại và đường dẫn không qua symlink/junction. Lệnh PowerShell:

```powershell
$env:PYTHONPATH='scripts;services/api/src;packages/synthetic/src;.'
.venv/Scripts/python.exe -B scripts/rag_v2_build_index.py --embed --batch-size 1 --output data/rag_v2_index/embedded3
```

Exit 0; `read_index('data/rag_v2_index/embedded3')` đạt kiểm tra manifest binding, checksum, nguồn và matrix.

| Manifest | Giá trị |
| --- | --- |
| `unit_count` | 9251 |
| `splitter_version` | `structural-spans-v3` |
| `embedding_status` | `complete` |
| `embedding_dimension` | 1024 |
| `embedding_model` | `BAAI/bge-m3` |
| `embedding_revision` | `5617a9f61b028005a4858fdac845db406aefb181` |
| `embedding_batch_size` | 1 |
| `binding_sha256` | `dd2643651794bfaccfb7ad81b57351326f4468872d53e31ce551f85765e34530` |

## Đo truy hồi offline

Hai sweep đã hoàn tất, cùng exit 0. Kết quả trên cùng 477 ca (452 dev + 25 audit):

| Chỉ số facts-in-context | embedded2 | embedded3 |
| --- | ---: | ---: |
| Tổng | **281/477 (58,91%)** | **281/477 (58,91%)** |
| Dev | 262/452 | 262/452 |
| Audit | 19/25 | 19/25 |
| AU-A23 | true | true |

- Gained: **0**, danh sách `[]`.
- Lost: **0**, danh sách `[]`.
- Chênh lệch ròng: **0**. Không có trường hợp số lost lớn hơn gained.

**Khuyến nghị giữ `embedded2` cho runtime:** tách row đã đạt yêu cầu cấu trúc và `embedded3` hợp lệ, nhưng phép đo này không cho thấy cải thiện truy hồi; gold sổ tay của AU-A23 vẫn ngoài top 80. Chưa chuyển runtime. Tệp đối chiếu tự kiểm tra đủ/không trùng case, tổng facts, gained/lost và hash tệp được bảo vệ: `../w12-comparison.json`.

Hai lệnh chạy nền, chờ kết thúc; cùng tập dev answerable + audit answerable, tổng 477 ca, `RRF_K=60`, `LEXICAL_PIN=4` giữ nguyên trong `hybrid.py`:

```powershell
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/w12_sweep.py --index data/rag_v2_index/embedded2 --output evals/results/audit-opus-20261101/w12-embedded2-sweep.json
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/w12_sweep.py --index data/rag_v2_index/embedded3 --output evals/results/audit-opus-20261101/w12-embedded3-sweep.json
```

Tiêu chí giữ nguyên từ L14: mọi `required_fact` khớp text context qua `fact_matches`; thu context thật của `RagV2Service -> generate_draft` bằng recording gateway, dừng trước gọi provider. Chỉ dùng embedding local 18081; không dùng paid model, không dùng reranker. Grant mọi unit được mô phỏng như phép đo gốc; không đo phân quyền production hoặc chất lượng câu trả lời sinh ra.

Kiểm tra riêng AU-A23: facts-in-context **true trên cả hai index**, context giống nhau, chọn chunk chương trình Logistics đô thị `01a16d41-d718-76e3-95f7-90b0009ba0f0`, có tiêu đề trình độ Cử nhân và chữ ký Trưởng khoa Cầu đường. Không chọn ba chunk sổ tay trang 25. Vì vậy không quy kết AU-A23 là cải thiện mới của W12; baseline hiện tại đã đạt tiêu chí facts-in-context, khác chẩn đoán ban đầu trong brief. Bằng chứng đầy đủ: `../w12-AU-A23.json`.

Chẩn đoán bổ sung với `analyze(question).search_query`, BM25 và vector top 80: gold unit chứa dòng `29 Logistics` vẫn nằm ngoài top 80 trên cả hai index. W12 tạo đúng row unit nhưng riêng việc tách dòng chưa đưa dòng sổ tay này lên top 80. Không sửa retrieval ngoài phạm vi brief. Bằng chứng: `../w12-AU-A23-ranks.json`.

## Kiểm thử

Lệnh yêu cầu:

```powershell
.venv/Scripts/python.exe -B -m pytest tests/rag_v2 tests/architecture -q -p no:cacheprovider --basetemp=.pytest-tmp-w12
```

**Exit 0: 620 passed, 2 warnings in 148.59s.** Hai warning là `LEGACY_EMBED_CACHE_IGNORED`. 15 test W12 riêng cũng đạt. Lượt chạy tập trung ban đầu phát hiện lỗi trong helper test mới khi kiểm tra riêng một chunk nhưng unit giữ provenance của ba chunk; đã sửa helper, không sửa kỳ vọng test cũ. Lượt đó cũng báo quyền truy cập thư mục temp mặc định bên ngoài workspace; lệnh đầy đủ dùng basetemp đúng brief và đạt.

Không xóa `.pytest-tmp-w12` hay thư mục kiểm thử khác. Mục dọn temp bị chặn bởi Global Agent Safety Policy trong `AGENTS.md`: cấm xóa vĩnh viễn dữ liệu untracked, yêu cầu quy trình xác nhận phá hủy; phần “Do not” của brief cũng cấm xóa bất cứ thứ gì. Giữ nguyên bằng chứng là phương án không phá hủy. Việc này không chặn build, kiểm thử hoặc sweep.

## Phạm vi và giới hạn

Không khởi động lại, dừng hay cấu hình lại API, frontend, Postgres, embedding hoặc reranker. Chưa chuyển runtime sang index mới. Hash corpus, bốn tệp `embedded2`, `hybrid.py`, script L14 và hai tập case đã được đối chiếu cuối tác vụ, tất cả giữ nguyên; xem `../w12-unit-analysis.json` và `../w12-comparison.json`. `chunk_gaps` của hai manifest giống hệt nhau: 9 chunk có khoảng trắng phi ngữ nghĩa được lưu bằng cơ chế sẵn có; W12 không tạo thêm gap trên corpus này. `git diff --check` đạt; các thay đổi có sẵn trước W12 được giữ nguyên. Trải nghiệm người dùng thực chưa được đo.

Bằng chứng nghiệm thu là test cấu trúc/nguồn do mã kiểm tra trên corpus thật và ca tổng hợp, manifest index, cùng context ghi lại qua pipeline thật; không có đánh giá bằng mô hình trả phí.
