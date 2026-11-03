# W11 — Ghi nhận phê duyệt dependency ngày 2026-11-03

Đã ghi nhận phê duyệt `DIRECT-HUMAN-2026-11-03-STACK-002` theo brief W11. Gate đạt và toàn bộ kiểm thử dependency resolution đạt; không cần thay đổi khai báo dependency.

## Phạm vi thay đổi

- `scripts/verify_dependencies.py`: cập nhật ba hằng `APPROVAL_REFERENCE`, `APPROVED_CANDIDATE_SHA256`, `APPROVED_ADDITIONAL_PACKAGE_COUNT` và chú thích xác nhận chủ sở hữu duyệt đúng bytes ứng viên ngày 2026-11-03; tên/phiên bản mới vẫn cần phê duyệt mới.
- `pyproject.toml`: chỉ cập nhật `reference` và `candidate-lock-sha256` trong `[tool.campus247.dependency-approval]`.
- `evals/results/audit-opus-20261101/impl/W11-report.md`: thêm báo cáo này.

Repository đã có nhiều thay đổi trước W11, gồm cả `scripts/verify_dependencies.py`, `pyproject.toml`, `uv.lock` và bộ kiểm thử chưa được Git theo dõi. Diff của lượt này được đối chiếu với nội dung tại đầu lượt, không quy các thay đổi có sẵn thành kết quả W11.

## Checksum và số gói

- SHA-256 tính từ bytes `uv.lock` trước và sau thay đổi: `251e0a8fbd1f5910abd30105a3a0e6b63f6ab9a51244d209cfc29848b2dbce46`, khớp chính xác brief.
- Số gói bổ sung: **133**, tính bằng chính biểu thức của gate: tập `(name, version)` trong `lock["package"]`, loại root `project["project"]["name"]` và các tên thuộc `approved_names(...)`. Đã đặt `APPROVED_ADDITIONAL_PACKAGE_COUNT = 133`.
- 21 gói khai báo trực tiếp chưa có trong allowlist được nêu ở brief là tập con của 133 gói resolve, không phải 21 gói cộng thêm vào 133.
- Giữ nguyên `uv.lock`, allowlist, regex, mọi quy tắc gate, `APPROVED_OTEL_PRERELEASES` và kỳ vọng kiểm thử. Không chạy lệnh resolve, sync hay cài đặt dependency.

## Nguyên nhân ba lỗi dự kiến

Sau khi cập nhật phê duyệt, chạy `.venv/Scripts/python.exe -B scripts/verify_dependencies.py` trả mã **0**, thông báo `Dependency verification passed: approved exact pins, resolved closure, sources and artifact hashes.` Danh sách lỗi còn lại: **rỗng**.

Đối chiếu bằng parser của gate xác nhận cả **31** khai báo production và **9** khai báo dev khớp chính xác metadata root trong `uv.lock`: tên, pin `==`, extras, markers và tập dependency references. Extras hiện có là `sqlalchemy[asyncio]` và `uvicorn[standard]`; không có marker trong các khai báo trực tiếp này. Không có drift độc lập cần sửa trong `[project].dependencies` hay nhóm dev.

Để xác định nguyên nhân, gọi `validate_documents` trên cùng dữ liệu nhưng không truyền tập phiên bản được phê duyệt đã tái hiện đủ ba lỗi dự kiến; truyền tập phê duyệt đúng checksum cho kết quả `[]`.

| Lỗi | Nguyên nhân chính xác | Cách khắc phục đã thực hiện |
|---|---|---|
| `dependency must use an exact stable == pin; URL/VCS/range/wildcard denied` | Bốn khai báo `opentelemetry-instrumentation-fastapi==0.66b0`, `opentelemetry-instrumentation-httpx==0.66b0`, `opentelemetry-instrumentation-sqlalchemy==0.66b0`, `opentelemetry-instrumentation-redis==0.66b0` là prerelease. Khi tham chiếu/checksum phê duyệt cũ không khớp lock hiện tại, `approved_versions` rỗng; `_requirements` từ chối cả bốn và kết quả cuối gộp thành một chuỗi lỗi duy nhất. | Ghi đúng tham chiếu, checksum và số lượng đã được chủ sở hữu duyệt; ngoại lệ hiện hữu chỉ chấp nhận đúng các cặp OpenTelemetry được duyệt. |
| `lock drift: production requirement metadata differs` | Sau khi bốn khai báo trên bị parser loại, bản đồ production chỉ còn 27 mục, còn root `metadata.requires-dist` vẫn chứa đủ 31 mục, gồm đúng bốn pin `==0.66b0`. | Phê duyệt hợp lệ giúp parser giữ đủ 31 mục; metadata khớp mà không đổi dependency. |
| `lock drift: root dependency references differ` | Cùng việc loại bốn khai báo làm tập production thiếu bốn tên so với root `dependencies`, vốn chứa đủ 31 tên. Nhóm dev gồm 9 mục vẫn khớp. | Phê duyệt hợp lệ khôi phục tập production đầy đủ; references và extras khớp nguyên trạng lock. |

## Kiểm chứng

Lệnh theo brief:

```text
.venv/Scripts/python.exe -B -m pytest tests/unit/dependency_resolution -q -p no:cacheprovider --basetemp=.pytest-tmp-w11
```

Mã thoát **0**; kết quả: **34 passed, 14 subtests passed in 0.38s**. Bao gồm các ca phủ định `test_candidate_count_mismatch_does_not_enable_prerelease_exception`, `test_candidate_bytes_drift_cannot_reuse_approval`, `test_project_cannot_self_approve_a_different_candidate` và các ca từ chối prerelease ngoài phạm vi.

Bằng chứng là bộ kiểm thử offline hiện có cùng đối chiếu metadata/references bằng code, kiểm tra SHA-256 và so sánh AST của gate trước/sau khi loại đúng ba hằng được phép sửa. AST còn lại giống nhau; dữ liệu TOML ngoài hai trường phê duyệt giống nhau. Checksum của lock, allowlist và tệp kiểm thử giữ nguyên; fingerprint diff của các tệp tracked ngoài hai tệp sửa và staged diff giữ nguyên so với đầu lượt.

`.pytest-tmp-w11` không tồn tại trước hoặc sau pytest: bộ kiểm thử không tạo thư mục này, nên không có thư mục cần xóa. Không thực hiện thao tác xóa, commit, push, reset hay clean.
