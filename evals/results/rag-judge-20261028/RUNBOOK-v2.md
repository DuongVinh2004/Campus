# Runbook RAG v2

## Bật / tắt
- Cờ: biến môi trường `CAMPUS247_RAG_ENGINE` = `v1` (mặc định) | `v2`; chỉ nhánh `grounded_faq` đổi. `CAMPUS247_RAG_V2_INDEX` = thư mục chỉ mục (mặc định `data/rag_v2_index`; bản đã nhúng đủ: `data/rag_v2_index/embedded`).
- Khởi chạy v2 (PowerShell, tại gốc repo): đặt `PYTHONPATH=data\rag_v2_vendor` (numpy 3.12), `CAMPUS247_RAG_ENGINE=v2`, `CAMPUS247_RAG_V2_INDEX=data/rag_v2_index/embedded`, dừng đúng tiến trình có dòng lệnh chứa `knowledge_platform.py serve --generation --port 8015`, rồi `infra/local/rag-fixture/.venv/Scripts/python.exe -B scripts/knowledge_platform_runtime.py start --defer-worker`. Sau đó gửi một câu hỏi khởi động nóng và đợi ~40 s (cache ủy quyền).
- Lui về v1: bỏ `CAMPUS247_RAG_ENGINE` (hoặc đặt `v1`) và khởi động lại như trên. Thiếu thư mục chỉ mục khi `v2`: ứng dụng không khởi động (`RAG_V2_INDEX_MISSING`), không tự lùi lặng lẽ.

## Cờ vận hành v2
- `CAMPUS247_PARALLEL_CLASSIFY=true` (mặc định tắt): chạy đồng thời lời gọi phân loại an toàn và định tuyến (`agent/nodes/async_io.py:classify_and_route`); quyết định như tuần tự, kết quả định tuyến bị bỏ khi an toàn chuyển người. Chỉ có tác dụng khi `CAMPUS247_RAG_ENGINE=v2`.
- Quyết định "trả lời / hỏi lại / không có nguồn / ngoài phạm vi" do lời gọi sinh trả về (`decision` trong lược đồ); mã chỉ kiểm tra và ánh xạ sang kết quả có kiểu. Không còn luật tay theo dạng câu (thực thể lạ, thống kê, đại từ) — đo ngày 2026-10-30 trên bộ chưa từng dùng cho thấy chúng không tốt hơn.
- Khởi động sau khi máy khởi động lại: (1) dịch vụ mô hình `.venv/Scripts/python.exe -B -u scripts/serve_rag_models.py --state infra/local/rag-advanced-models-<ngày>-accounting-NN --predecessor <namespace cuối đã dùng> --accounting-only` (namespace mới, nối predecessor; không dùng lại state; chờ dòng `"ready": true`); (2) `evals/results/rag-judge-20261028/resume/restart_rt.ps1 -Engine v2` (tự khởi động PostgreSQL, API, frontend; `-DebugCapture` chỉ để gỡ lỗi ca tổng hợp); (3) một lượt khởi động nóng và đợi ~45 s.

## Dựng lại chỉ mục (khi release kho đổi)
1. `evals/runners/corpus_export.py` xuất kho phục vụ (giao dịch chỉ đọc) → `evals/corpus/`.
2. `scripts/rag_v2_build_index.py --embed --output <thư mục mới>` (cần máy chủ nhúng 18081; có tệp tiếp tục `embed-cache.jsonl`; không ghi đè thư mục có sẵn).
3. Chỉ mục gắn với `corpus_sha256`/release; chunk không còn trong release bị loại ở bước ủy quyền mỗi lượt.

## Đo
- `evals/runners/rag_v2_eval.py run|score|compare` (bộ ca `evals/datasets/rag-v2/cases.jsonl`); `rag_v2_suite.py run|score` (A9); `rag_v2_retrieval_probe.py` (đo truy xuất ngoại tuyến, không gọi mô hình sinh).
- Bộ giữ kín chỉ chạy ở mốc; không sửa mã theo từng ca.

## Sự cố thường gặp
| Dấu hiệu | Nguyên nhân | Xử lý |
|---|---|---|
| Mọi lượt "lỗi kết nối" sau ~1 s, log `rag_v2_failure ... detail=402` | Nhà cung cấp sinh hết số dư | Nạp số dư; không đổi mã |
| Lượt đầu hết 12 s sau khởi động | Cache ủy quyền lạnh | Gửi lượt khởi động nóng |
| `provider operation bound` | Yêu cầu >28.000 byte JSON | Giảm `CONTEXT_BYTES` trong `rag_v2/service.py` |
| `ModuleNotFoundError: numpy` | Venv fixture thiếu numpy | Đặt `PYTHONPATH=data\rag_v2_vendor` |
| Mọi lượt `error` sau ~12–17 s, log `TimeoutError where=generate_statements`, `curl https://api.deepseek.com` hết thời gian chờ | Mạng chặn nhà cung cấp (mạng công ty) | Đổi mạng; không đổi mã |
| `Runtime check failed: ConnectError` khi khởi động | Dịch vụ mô hình 18081/18082 chưa chạy (sau khi máy khởi động lại) | Chạy bước (1) ở trên |
| `stream_prepare_failure site=1` | `output_guard` v1 chặn (ví dụ "kỷ luật") | v2 đã chuyển thành từ chối; xem log nếu còn |
| Bộ safety: hàng trăm ca `HTTPStatusError` ở 0,003 s | Phiên đăng nhập hết hạn giữa lượt chạy; nhật ký ghi ca lỗi như đã xong nên `--resume` không chạy lại | `bash evals/results/rag-judge-20261028/runs/run-suite-e.sh` (đổi tên tệp journal cho mỗi lần): bỏ ca lỗi bằng `runs/strip_errors.py` rồi `--resume`, lặp tối đa 8 lần, rồi chấm |
| `rag_v2_eval.py run --cases ...` báo `ValueError` ngay | Ca có `split` rỗng (shard chưa gộp) nên `--split holdout` lọc hết | Tạo `cases.jsonl` từ shard với `split="holdout"` (như `holdout4/cases.jsonl`) |
| Ca kỷ luật vẫn bị chặn dù ngoại lệ v2 đúng | Nguồn ở `drive.google.com`/`heyzine.com` không có ràng buộc xuất bản đã xác thực | Log `rag_v2_discipline_rule_rejected reason=...` cho biết điều kiện nào chặn; cấp `VerifiedPublication` lúc nạp, không nới quy tắc nguồn |
| Câu học phí nhiều lượt trả sai dòng bảng | Bước viết lại câu viết rõ từ viết tắt ("KS/KTS" thành "Kỹ sư/Kiến trúc sư") | Prompt `generation/rewrite.py` giữ nguyên chữ của câu mới; xem câu viết lại bằng `restart_rt.ps1 -Engine v2 -DebugCapture` (ghi `data/rag_v2_debug/rewrite.jsonl`) |

### Quy trình đo cuối (mốc)
1. `CAMPUS247_PARALLEL_CLASSIFY=1` rồi `restart_rt.ps1 -Engine v2`, chờ `/health/ready` 200, một lượt khởi động nóng + 50 s.
2. Bộ safety đủ 610 ca: `runs/run-suite-e.sh` (đổi tên journal).
3. Holdout: `rag_v2_eval.py run --cases <holdout>/cases.jsonl --split holdout --repeat 3 --concurrency 2 --api-log <api.log> --out runs/<tên>.json` cho v2; `restart_rt.ps1 -Engine v1` rồi `--repeat 1` cho v1; chấm bằng `score`.
4. Chỉ một runner trên một runtime; không đọc tệp kết quả khi runner đang ghi; kết thúc đặt runtime về `-Engine v1`.
