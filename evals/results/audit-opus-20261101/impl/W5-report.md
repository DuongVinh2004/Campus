1. **Đã hoàn tất W5 trong phạm vi mã và kiểm thử ngoại tuyến.**
   Nguyên nhân gốc: binding và quét injection đồng bộ chặn event loop; cache nguồn lạnh khiến lượt đầu chờ lâu.
   Đã chuyển dựng units và AuthorizedIndex sang luồng; quét injection nền ngay sau nạp chỉ mục.
   Lifespan làm nóng nguồn và binding qua factory/context sinh viên tổng hợp cùng đường rag_v2_sources hiện có; warm hiển thị pending/ready/failed.

2. **Tệp đổi và test thêm.**

   - `services/api/src/campus247/agent/nodes/rag_v2.py`
   - `services/api/src/campus247/bootstrap/rag_v2.py`
   - `services/api/src/campus247/bootstrap/app.py`: chỉ móc lifespan và truyền factory cho warmup, giữ phần sửa dở khác.
   - `tests/rag_v2/test_l22_event_loop.py`: 9 ca, gồm:
     `test_large_unit_build_keeps_event_loop_responsive`;
     `test_unit_and_drop_results_preserve_original_order`;
     `test_concurrent_turns_have_identical_authorized_units`;
     `test_index_load_prescans_in_background_with_on_demand_fallback`;
     `test_lifespan_warmup_status_and_no_provider_calls` (3 ca);
     `test_lifespan_cancels_pending_warmup_before_closing_runtime`;
     `test_v1_lifespan_never_starts_v2_warmup`.
   - Báo cáo này: `evals/results/audit-opus-20261101/impl/W5-report.md`.

3. **Lệnh và kết quả trước/sau.**

   - Baseline: `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp-W5 tests/rag_v2`
     → **559 đạt, 0 đỏ**, 131,49 s, exit 0.
   - Test tái hiện trên mã cũ: `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/rag_v2/test_l22_event_loop.py`
     → **2 đạt, 5 đỏ**, exit 1; CPU ≥300 ms gây chặn event loop **432 ms**.
   - Lượt giữa dùng `--basetemp .pytest-tmp-W5-after-20261101`: **576 đạt, 10 đỏ**, exit 1.
     Cả 10 đỏ thuộc tệp W9 mới xuất hiện `test_audit_clarify_20261101.py`; sau cập nhật song song, chạy riêng đạt 18/18.
   - Lượt cuối: `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp-W5-final-20261101 tests/rag_v2`
     → **586 đạt, 0 đỏ**, 128,33 s, exit 0; 2 cảnh báo LEGACY_EMBED_CACHE_IGNORED như baseline.
     Dùng basetemp mới để giữ nguyên bằng chứng cũ; tổng ca tăng gồm 9 ca W5 và 18 ca W9.
   - Nhóm W5 + binding cache + graph: **39/39 đạt**; test CPU xác nhận heartbeat không bị chặn quá 100 ms.
   - `git diff --check` trên ba tệp mã: sạch. Ruff tệp test mới: đạt.
     Ruff ba tệp node/bootstrap/test còn 2 lỗi có sẵn từ HEAD: I001 ở node, C408 ở bootstrap; không phát sinh lỗi mới.

   Bằng chứng là chỉ mục/hàng nguồn tổng hợp với tập units, drops, hash, trạng thái health và lời gọi provider được kiểm bằng mã.

4. **Quyết định thiết kế và giới hạn.**
   Khóa ngắn bảo vệ cache dùng chung; tính trùng được phép, không giữ khóa khi quét CPU.
   Giữ thứ tự loại row/ids/body/title/scope/hash, nhật ký drops/stage và kiểm quyền trước dispatch/sau chờ.
   Warmup chỉ đọc, không gọi gateway/embedding, không tạo tài khoản hay cấp quyền; lỗi log loại ngoại lệ rồi bỏ qua.
   Context không hợp lệ thì warm failed, không chế tạo scope thay thế; shutdown hủy tác vụ trước khi đóng runtime.
   Cache nguồn vẫn 300 giây; không sửa runtime.py hoặc scripts của W6.

5. **Cần phối hợp / rủi ro.**
   Không còn blocker mã W5; W9 đã xanh ở lượt cuối.
   Chưa đo khởi động lạnh/độ trễ với dữ liệu thật hoặc người dùng thật; không khởi động/build 8015, không gọi mạng/DeepSeek.
   Lượt hỏi đến khi warm còn pending vẫn có thể chờ nguồn lạnh và chạm deadline 12 giây.
