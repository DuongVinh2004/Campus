# W13 — Cache attestation cho attachment

Ngày thực hiện: 2026-11-03. Nhánh: `rag-v2-hardening`.

## Thay đổi

- `services/api/src/campus247/infrastructure/knowledge/publication.py`: thêm lớp memo quanh `verified_attachment`; chuyển nguyên thân hàm xác minh vào `_verify_attachment`. Thêm `clear_attachment_cache()` để xóa cả kết quả dương và âm. Không sửa các receipt, phép xác minh, retrieval, prompt hoặc deadline 12 giây.
- `tests/knowledge_platform/test_attachment_cache.py`: thêm 15 ca kiểm thử độc lập, dùng verifier giả và đồng hồ giả; không mạng, không gọi model.
- `evals/results/audit-opus-20261101/impl/W13-report.md`: báo cáo này.

## Khóa, thời hạn và giới hạn an toàn

Khóa cache gồm `id(platform)`, đường dẫn workspace đã resolve, tenant, `row.get("id")`, `content_checksum`, `document_version_id`, `release_id`, `canonical_uri`, `source_id` và `content_text`. Các trường bổ sung tránh tái sử dụng kết quả khi nguồn hoặc nội dung thực tế thay đổi dù checksum được giữ nguyên. Dùng `get("id")` để tương thích các row giả hiện có không có ID; các trường nội dung và phiên bản vẫn phân biệt kết quả. Mỗi entry giữ tham chiếu platform để Python không tái sử dụng identity của platform khi entry còn tồn tại. Hai platform, kể cả cùng workspace, không dùng chung entry.

TTL là hằng module `ATTACHMENT_CACHE_TTL_SECONDS = 30`, dùng `time.monotonic`, tính từ trước khi bắt đầu xác minh; cache hit không gia hạn TTL. Entry hết hạn tại mốc 30 giây sẽ được xác minh lại. Giới hạn `ATTACHMENT_CACHE_MAX_ENTRIES = 512`; khi đầy, bỏ entry được chèn sớm nhất. Cache lưu cả `VerifiedPublication` và `None`; exception được truyền ra và không được lưu. Các thao tác tra cứu/chèn/loại entry chạy đồng bộ giữa các điểm await trên event loop; kết quả luôn được ghi theo khóa cục bộ của chính lời gọi đó. Không thêm cơ chế gộp các lượt xác minh đồng thời đang chạy.

Cache miss vẫn chạy nguyên các kiểm tra hash receipt đã pin, publisher chính thức, ánh xạ link/viewer, hash bản gốc, checksum nội dung và rendition. So sánh AST với `HEAD` xác nhận thân hàm xác minh không thay đổi. Các gate release, independent review, scope và metadata tại caller được giữ nguyên.

Trong cửa sổ TTL, cache tái sử dụng kết quả xác minh của cùng binding. Nếu receipt, HTML, viewer, artifact gốc, rendition hoặc metadata backing bị đổi tại chỗ mà khóa không đổi, việc phát hiện thay đổi có thể trễ tối đa 30 giây; kết quả `None` cũng có thể chậm phản ánh dữ liệu vừa được sửa trong cùng thời hạn. Đây là giới hạn độ mới được brief cho phép, không phải một lần đọc lại đĩa tại mỗi cache hit. Không tạo attestation dương khi chưa có lần xác minh đầy đủ thành công; cache âm không cấp thêm quyền. Đổi checksum, version, release, URI, source, nội dung, tenant hoặc platform/workspace sẽ làm trượt cache ngay.

## Kiểm chứng

15 ca mới kiểm tra: tái sử dụng lời gọi giống nhau; phân biệt ID/checksum/version/URI/source/nội dung/release; hết TTL cho cả kết quả dương và `None`; exception không được cache; tách platform cùng và khác workspace; xóa cache; giới hạn 512 entry và loại entry cũ nhất, không gia hạn khi hit.

Lệnh kiểm tra tập trung (exit code 0):

```text
.venv/Scripts/python.exe -B -m pytest tests/knowledge_platform/test_attachment_cache.py tests/knowledge_platform/test_stem_publication_binding.py tests/knowledge_platform/test_regulation_publication_binding.py tests/knowledge_platform/test_handbook_publication_binding.py -q -p no:cacheprovider
43 passed in 0.67s
```

Lệnh đầy đủ đúng brief (exit code 0):

```text
.venv/Scripts/python.exe -B -m pytest tests/knowledge_platform tests/rag_v2 tests/unit/retrieval -q -p no:cacheprovider --basetemp=.pytest-tmp-w13
1920 passed, 41 skipped, 2 warnings in 516.37s (0:08:36)
```

Không có test fail. Có 41 ca bị skip; không sửa điều kiện skip hay kỳ vọng của test hiện có. Hai warning cùng là `LEGACY_EMBED_CACHE_IGNORED` tại `scripts/rag_v2_build_index.py:43`. Thư mục `.pytest-tmp-w13` chưa tồn tại trước lần chạy và được giữ lại sau chạy.

Ba file publication binding hiện có được giữ nguyên. Bằng chứng chức năng là các ca tổng hợp dùng đồng hồ/verifier giả để kiểm tra memo, kết hợp kiểm thử binding trên artifact đã giữ lại và so sánh AST xác nhận phép xác minh gốc không đổi.

Không gọi model trả phí, không đo lại INJ-06, không dừng hoặc khởi động lại dịch vụ, không commit/push/reset/clean/xóa dữ liệu. Hiệu quả latency thực tế của INJ-06 chưa được đo lại; chủ hệ thống tự khởi động lại API và đo theo brief.
