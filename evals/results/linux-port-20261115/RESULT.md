# Bước 1.11: port sang Linux (2026-11-15)

Kiểm trên WSL2 Ubuntu (Python 3.12.16 từ `uv.lock`) và trên Ubuntu 24.04 sạch trong Docker (bước 1.13). Mỗi thay đổi giữ nguyên hành vi trên Windows.

| Chỗ gắn với Windows | Cách xử lý |
|---|---|
| Khóa ledger trả phí dùng `msvcrt.locking` (`scripts/public_rag_ledger.py`) | nhánh `fcntl.flock`; lỗi giữ nguyên kiểu `PermissionError`. Test 4 ca đạt trên Windows và Linux (tiến trình thứ hai bị từ chối, nhả khi người giữ thoát) |
| Binding ONNX nạp `onnxruntime.dll` bằng `WinDLL` | `onnx_capi_20261011_30.py` chọn theo hệ điều hành; Linux dùng `libonnxruntime.so.1.30.0` từ bản phát hành của Microsoft, **khớp digest của nhà phát hành** (`a5ed5a3c…`), ghim bằng hash thư viện và header trong `onnx-linux-20261115/linux-release.json`; `CreateSession` dùng `char*` thay vì `wchar_t*` |
| Tokenizer cài ở site-packages Windows | tokenizers 0.21.4 cài vào thư mục riêng `tokenizers-linux-20261115`, mọi tệp của gói ghim hash |
| Máy chủ mô hình bao bằng job object Windows (5 GiB, 4 bộ xử lý) | `bounded_posix_process_20261115.py`: tiến trình con bị SIGKILL khi cha chết; giới hạn bộ nhớ và CPU do systemd (`MemoryMax`) hoặc container áp dụng |
| Lớp engine ghim 4 bộ xử lý logic cụ thể ("3;5;7") | `m1_platform_20261115.CPU`: Windows giữ chính sách đã đo, Linux dùng tùy chọn lập lịch đã duyệt không ghim (máy 4 vCPU không có CPU 5 và 7) |
| `creationflags=0x08000000`, đường dẫn `node.exe` cố định (frontend) | hằng `NO_WINDOW` theo hệ điều hành; `CAMPUS247_NODE` hoặc `node` trên PATH |
| Manifest bằng chứng ghi đường dẫn có dấu `\` | `public_knowledge` và các hàm `sha` của chuỗi `m2_*` đổi dấu phân cách khi đọc; `multi_agent_live_resources` so sánh đường dẫn ủy quyền theo phần dưới gốc workspace (tệp ủy quyền ghi đường dẫn tuyệt đối của máy Windows) |
| Launcher dùng PowerShell, `pg_ctl.exe`, `vector.dll` | **không port**: trên Linux systemd khởi động từng dịch vụ (đơn vị sinh từ hồ sơ), Postgres 17 hệ thống kèm pgvector |

## Khớp số học (tiêu chí của bước)

200 câu hỏi mẫu, cùng mô hình bge-m3 FP32, Windows và Linux: **cosine nhỏ nhất 0,9999999999999998, chênh lệch tuyệt đối lớn nhất 0,0** (vector giống hệt từng bit, dù Windows ghim 4 bộ xử lý còn Linux không ghim). Ngưỡng của kế hoạch là 0,9999. (`parity.json`; tệp vector lớn không đưa vào kho.)
Vì vector giống hệt và chỉ mục giữ nguyên nên `rag_recall_probe` trên Linux không thể thấp hơn Windows; mình không chạy riêng.

## Bộ test trên Linux

Các nhóm `rag_v2, api, architecture, operations, knowledge_platform, evals, contract(s), unit/retrieval, unit/agent, integration`:
lần đầu 135 lỗi + 78 lỗi dựng fixture; sau các sửa trên và `tests/conftest.py` chỉ còn các lỗi **có sẵn trên Windows** (mốc 1.0) cùng các test **chỉ chạy được trên Windows** được bỏ qua kèm lý do:
- 11 tệp đọc manifest bằng chứng ghi trên Windows (đường dẫn `\` hoặc `C:\`): corpus HUCE, không chạy trên máy chủ;
- công cụ phát triển chỉ Windows: parser interpreter lookup, script khôi phục PowerShell, 3 test launcher.
Không có test nào bị bỏ qua trên Windows. Danh sách cụ thể nằm trong `tests/conftest.py`; log đầy đủ `pytest-linux.log` và `pytest-linux-rerun.log`.

## Chưa đạt hoặc chưa làm

- Module học liệu quét tệp tải lên bằng ClamAV bản Windows (`.tooling/learning-clamav-…`); trên cloud chạy với `CAMPUS_LEARNING_ENABLED=false` cho đến khi dựng ClamAV Linux.
- Chưa chạy lại toàn bộ test trên Linux sau mọi sửa cuối cùng (chạy lại chỉ các tệp từng lỗi).
- Frontend (Next.js) chưa được dựng hay chạy thử trên Linux.
