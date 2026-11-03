# W14 — flat-list rows và nhánh lexical tập trung

Ngày thực hiện: 2026-11-03–04 (Asia/Bangkok). Workspace `C:\Users\Duong Vinh\Vinh`, branch `rag-v2-hardening`. Đã triển khai, build và đo đủ A/B; **không đạt điều kiện adoption và chưa đạt yêu cầu pytest all-pass**.

## Phạm vi thay đổi

- `services/api/src/campus247/rag_v2/ingest/tables.py`: thêm detector `flat_list_rows`.
- `services/api/src/campus247/rag_v2/ingest/units.py`: tạo `table_row` có span nguyên vẹn, kết thúc row đúng ranh giới dòng; nâng `SPLITTER_VERSION` lên `structural-spans-v3`.
- `services/api/src/campus247/rag_v2/retrieval/hybrid.py`: thêm `FOCUSED_LEXICAL = True`, bộ lọc filler và danh sách RRF thứ tư.
- `tests/rag_v2/test_flat_list_rows.py`: khôi phục nguyên 15 test W12 từ bản `.txt`.
- `tests/rag_v2/retrieval/test_focused_lexical.py`: 8 test cho nhánh mới, cờ tắt, query không đổi/quá ngắn, giữ số/mã, scope và rank metadata.
- `../w14_sweep.py`: bản sao W12, đọc `W14_FOCUSED_LEXICAL`, ghi cờ và `line29_in_context`; không sửa script W12.
- `../w14_validate.py`, `../w14_a23.py`, `../w14_compare.py`: kiểm tra snapshot, ngữ cảnh AU-A23 và đối chiếu hai sweep với baseline.
- Tạo mới `data/rag_v2_index/embedded3` và các tệp bằng chứng W14. Builder được phép append embedding cache; không ghi vào `embedded2`.

## Detector và nhánh truy hồi

Detector chỉ nhận toàn bộ khối liên tục ít nhất 8 dòng khớp `^(\d{1,3})\s+\S`, không có `|`, số thứ tự tăng đúng 1. Nếu có số lặp/nhảy/giảm thì loại cả khối, không nhận tiền tố hợp lệ. Không nối qua dòng trắng, tiêu đề trang hoặc phần xuống dòng. Mỗi body là substring nguồn nguyên vẹn, gồm newline gốc; tối đa hai dòng ngay trước khối làm context không được trích dẫn, ngoài `⟦RAG_V2_SOURCE⟧`. Không sửa thuật toán pipe-table.

Nhánh mới dùng riêng `u.search_query`, bỏ token có dạng folded thuộc tập `do nao gi la thi vay nhe sao the em minh toi hoi xin bao nhieu`. Dấu câu ở đầu/cuối token chỉ được bỏ khi nhận diện filler; token được giữ lại vẫn nguyên dạng, gồm số và mã như `580.500`, `924/QĐ-ĐHXDHN`, `K64`. Khi không có filler, helper trả đúng chuỗi gốc, kể cả khoảng trắng. Chỉ gọi BM25 bổ sung khi cờ bật, query thực sự thay đổi và còn ít nhất hai token.

RRF gộp bốn danh sách với cùng `RRF_K=60`. `Candidate.lexical_rank` và `vector_rank` tiếp tục chỉ thứ hạng của hai nhánh gốc; giữ nguyên `LEXICAL_PIN=4`, `PACK_WINDOW=6`, nhánh anchored và query cho vector. Không thêm lời gọi embedding, reranker hay model từ nhánh mới. Khi cờ tắt, test mới kiểm tra đúng điểm/thứ tự RRF ba nhánh và metadata cũ.

## Unit và snapshot

| Chỉ số | embedded2 | embedded3 |
| --- | ---: | ---: |
| Chunk | 2.019 | 2.019 |
| Unit | 9.173 | 9.251 |
| `table_row` | 626 | 705 |
| Fact | 136 | 136 |

Tăng ròng 78 unit, 79 ID `table_row` mới. Có 376 lần xuất hiện dòng trên 24 chunk trước hợp nhất provenance. Toàn snapshot có 87 ID mới, 9 ID baseline không có trong snapshot mới và 48 ID chung thay đổi; không xóa hoặc sửa snapshot cũ.

`w14_validate.py` tái tạo đúng toàn bộ units của `embedded2` khi tắt detector; 9.070 unit ngoài các chunk có run giống hệt sau thay đổi. `check_units` không có issue; cả sáu doc family có coverage và min_chunk_coverage bằng 1. Facts hai snapshot có SHA-256 giống nhau; `chunk_gaps` hai manifest giống hệt. Bằng chứng: [w14-unit-analysis.json](../w14-unit-analysis.json), gồm danh sách 24 chunk và hash các tệp được bảo vệ.

Lệnh build, exit 0:

```powershell
$env:PYTHONPATH='scripts;services/api/src;packages/synthetic/src;.'
.venv/Scripts/python.exe -B scripts/rag_v2_build_index.py --embed --batch-size 1 --output data/rag_v2_index/embedded3
```

Đã kiểm tra output chưa tồn tại, đường dẫn canonical trong workspace và không qua symlink/junction; đã đọc `--help`. Không dùng `--base embedded2` vì splitter version khác. Builder đã kiểm tra lại snapshot bằng `read_index`.

| Manifest embedded3 | Giá trị |
| --- | --- |
| `unit_count` / `fact_count` | 9251 / 136 |
| `splitter_version` | `structural-spans-v3` |
| `embedding_status` | `complete` |
| `embedding_dimension` | 1024 |
| `embedding_model` | `BAAI/bge-m3` |
| `embedding_revision` | `5617a9f61b028005a4858fdac845db406aefb181` |
| `embedding_batch_size` | 1 |
| `binding_sha256` | `164e1127358b15cb5ae27ee85d6ae9592e99e8fda91bdcdc2916ab0a71450521` |

## Sweep A/B

Đã chạy đủ 477 ca ở cả A và B, cùng baseline W12 (452 dev + 25 audit), qua `RagV2Service -> generate_draft` với recording gateway dừng trước provider. Mọi unit được cấp quyền mô phỏng như script gốc; chỉ gọi embedding local 18081, không gọi model trả phí. Không đo phân quyền production hay chất lượng câu trả lời sinh ra. Hai process sweep đều exit 0.

```powershell
$env:W14_FOCUSED_LEXICAL='0'
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/w14_sweep.py --index data/rag_v2_index/embedded3 --output evals/results/audit-opus-20261101/w14-embedded3-A-sweep.json
$env:W14_FOCUSED_LEXICAL='1'
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/w14_sweep.py --index data/rag_v2_index/embedded3 --output evals/results/audit-opus-20261101/w14-embedded3-B-sweep.json
```

| Facts-in-context | Baseline: embedded2 | A: embedded3, cờ tắt | B: embedded3, cờ bật |
| --- | ---: | ---: | ---: |
| Tổng | 281/477 (58,91%) | 281/477 (58,91%) | 281/477 (58,91%) |
| Dev | 262/452 | 262/452 | 262/452 |
| Audit | 19/25 | 19/25 | 19/25 |
| Gained so với baseline | — | 0 | 4 |
| Lost so với baseline | — | 0 | 4 |
| AU-A23 đủ facts | Có | Có | Có |
| AU-A23 dòng 29 trong context | Không | Không | Không |

- **A gained:** `[]`; **A lost:** `[]`.
- **B gained:** `R2-A0-0142`, `R2-A3-0116`, `R2-Q2-0003`, `R2-Q2-0026`.
- **B lost:** `R2-A0-0019`, `R2-A0-0062`, `R2-A3-0028`, `R2-A3-0040`.

B có chênh lệch ròng 0; tổng bằng baseline nhưng có bốn ca đổi sang đạt và bốn ca đổi sang không đạt. Tệp đối chiếu [w14-comparison.json](../w14-comparison.json) được tạo bằng `w14_compare.py`, exit 0: kiểm tra đủ 477 case không trùng, cùng ID với baseline, tổng facts, gained/lost, cờ A/B và `provider_calls=0`. Kết quả gốc: [A sweep](../w14-embedded3-A-sweep.json), [B sweep](../w14-embedded3-B-sweep.json).

### AU-A23

Phép đo riêng [w14-AU-A23.json](../w14-AU-A23.json) ghi cả candidates và payload context thực:

| Chỉ số | A: cờ tắt | B: cờ bật |
| --- | --- | --- |
| Đủ facts `Cầu Đường`, `Cử nhân` | Có | Có |
| Dòng 29 trong context | Không | Không |
| Row unit đích trong candidates | Không | Không |
| Chunk cha của dòng 29 được pack | Không | Không |

Row unit đích: `430c8d0bf39201a6`, body đúng `29 Logistics đô thị Cầu Đường Cử nhân\n`, provenance gồm ba chunk sổ tay trang 25 trong brief. Context A/B giống hệt baseline (cùng SHA-256), chỉ chọn chunk chương trình Logistics `01a16d41-d718-76e3-95f7-90b0009ba0f0`.

Query gốc: `ngành logistics đô thị do khoa nào quản lý, bằng gì?`; query tập trung thực: `ngành logistics khoa quản lý, bằng`. Tập filler folded được giao cũng loại `đô`/`thị` vì trùng `do`/`thi`. Thứ hạng BM25 của row đích trên index và query thực là 331 ở nhánh gốc, 1737 ở nhánh tập trung; cả hai ngoài top 40. Không đạt con số mô phỏng 56–59/1–6 trong brief; báo cáo dùng phép đo trên snapshot thật, không thay query hay kỳ vọng để đạt mô phỏng.

## Adoption

**B không đủ điều kiện adoption. Khuyến nghị revert các thay đổi W14 và giữ `embedded2` cho runtime.** Điều kiện thứ nhất đạt (`lost=4 <= gained=4`), nhưng điều kiện thứ hai không đạt: dòng 29 không vào packed context. Sweep đủ 477 ca xác nhận cùng kết quả AU-A23 như phép đo riêng; không coi facts có sẵn từ chương trình Logistics là thành công truy hồi dòng sổ tay.

Chưa thực hiện revert hoặc xóa snapshot: brief yêu cầu khuyến nghị khi không adoptable và cấm reset/xóa; mã cùng `embedded3` được giữ để review. Không tự thay tập filler, trọng số RRF, pin hay packing để thay đổi kết quả thử nghiệm.

Không chuyển runtime. Do nâng splitter version, `read_index` runtime tiếp tục từ chối snapshot v2 (`INDEX_SPLITTER_VERSION_MISMATCH`); không nới kiểm tra này. Owner cần phối hợp phiên bản code và index nếu adoption; tác vụ này không đổi cấu hình service.

## Kiểm thử

- 23 test mới/khôi phục: **23 passed**, exit 0, gồm 15 flat-list + 8 focused-lexical.
- Lượt tập trung có test cũ: phát hiện hai assertion cũ không tương thích nhánh RRF bổ sung: `test_balanced_rrf_uses_ranks_not_score_scale` cố định điểm hai nhánh và `test_strong_lexical_hit_is_kept_inside_the_packing_window` giả định không có thêm phiếu lexical. Không sửa test cũ khi brief chưa cho phép; đã gửi câu hỏi xin đặt cờ tắt riêng hai test, giữ nguyên assertion.
- Không tìm thấy test pin literal `structural-spans-v2`; không sửa test kỳ vọng phiên bản. Builder/index store dùng chung `SPLITTER_VERSION`.

Lệnh đầy đủ đã kết thúc:

```powershell
$env:PYTHONPATH='scripts;services/api/src;packages/synthetic/src;.'
.venv/Scripts/python.exe -B -m pytest tests/rag_v2 tests/architecture tests/unit/retrieval tests/knowledge_platform -q -p no:cacheprovider --basetemp=.pytest-tmp-w14
```

**Exit 1: 2 failed, 1944 passed, 41 skipped, 2 warnings trong 596,42 giây.** Hai failure chính xác là hai test cũ nêu trên; hai warning là `LEGACY_EMBED_CACHE_IGNORED`. Giữ nguyên file `test_hybrid.py` và toàn bộ assertion hiện có theo giới hạn trong brief. Đầu ra: [w14-pytest-output.txt](../w14-pytest-output.txt). Yêu cầu “all must pass” chưa đạt; không báo nghiệm thu thành công.

Chẩn đoán riêng, không sửa test cũ: đặt `hybrid.FOCUSED_LEXICAL=False` trong process Python rồi gọi `pytest.main` đúng hai node ID thất bại, với `--basetemp=.pytest-tmp-w14-legacy-off`. **Exit 0: 2 passed trong 0,11 giây.** Kết quả này xác nhận tính tương thích của cờ tắt; không thay thế lần chạy bắt buộc với cờ mặc định bật ở trên.

## Bảo toàn và giới hạn

Không restart/stop/cấu hình lại API 8015, frontend 3015, Postgres, embedding 18081 hoặc reranker 18082. Không sửa corpus, existing data ngoài quyền append cache, script W12, generation/verification/prompt, hoặc thay đổi có sẵn. Không commit/push/reset/clean/xóa; giữ lại toàn bộ temp và bằng chứng. Hash corpus, hai tập case, baseline sweep, script W12 và bốn tệp `embedded2` đã được đối chiếu cuối tác vụ và đều nguyên vẹn; xem `w14-comparison.json`.

`git diff --check` đạt trên phần mã thay đổi. Các file tracked có diff do tác vụ chỉ gồm `tables.py`, `units.py`, `hybrid.py`; các test bổ sung và script/bằng chứng W14 là file mới. File `tests/rag_v2/retrieval/test_hybrid.py` giữ nguyên. Phần chặn nghiệm thu còn lại là giới hạn brief cấm sửa test cũ trong khi hai test cố định hành vi trước nhánh bổ sung; chưa có chỉ dẫn mới cho phép đặt cờ tắt riêng trong chúng.

Bằng chứng là test cấu trúc/nguồn do mã kiểm tra trên corpus thật và ca tổng hợp, manifest snapshot, cùng payload context ghi lại qua pipeline thật; trải nghiệm người dùng thực chưa được đo.
