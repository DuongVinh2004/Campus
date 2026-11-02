# W5 — L-22: bước `auth` của RAG v2 chặn event loop; lượt đầu sau khởi động luôn hết hạn

Đọc `W0-common.md` (quy tắc chung; phần lệnh test web không áp dụng, đây là việc Python). Mã phiên W5.

Sở hữu: `services/api/src/campus247/agent/nodes/rag_v2.py`, `services/api/src/campus247/bootstrap/rag_v2.py`, `services/api/src/campus247/bootstrap/app.py` (chỉ thêm móc làm nóng trong lifespan; tệp có sửa dở của người dùng, giữ nguyên phần khác), tệp test mới `tests/rag_v2/test_l22_event_loop.py`. Đọc không sửa: `infrastructure/knowledge/runtime.py` (`rag_v2_sources`, cache stale-while-revalidate 300 s; không đổi thời hạn 300 s — người dùng đã quyết giữ), `scripts/knowledge_platform.py` (phiên W6 đang sửa).

## Quan sát trên runtime 8015 (3 phiên đồng thời, DeepSeek thật)
- `rag_v2_node_stage auth_ms=6062 units_ms=6108` ở đợt đầu (khi ấm: 100–400 ms). Health-poll `/health/live` ghi một lần event loop bị chặn 6,0 s đúng lúc đó; một lượt hết hạn 12 s.
- Nguyên nhân: trong `RagV2Node` (khoảng dòng 150–185), vòng lặp đồng bộ qua 9.173 đơn vị gọi `_binding_failure` (băm/so khớp với hàng nguồn; cache `_BOUND` lạnh lúc đầu) và quét `PromptInjectionDetector` cho từng đơn vị, chạy thẳng trên event loop. Ba lượt đồng thời cùng làm việc này.
- Lượt đầu tiên sau khởi động chờ lần đọc toàn bộ 2.019 hàng nguồn (19–70 s) nên luôn chạm `asyncio.timeout(12)` và người dùng thấy "lỗi kết nối".

## Yêu cầu
1. Không còn công việc CPU dài trên event loop trong nút v2: chuyển việc dựng `units` (vòng binding + quét injection) sang luồng (`asyncio.to_thread` hoặc tương đương). Giữ nguyên ngữ nghĩa ủy quyền: cùng các kiểm, cùng thứ tự loại, cùng nhật ký `rag_v2_unit_drops`/`rag_v2_node_stage`. Dữ liệu dùng chung (`_BOUND`, `self._injection`) phải an toàn khi nhiều lượt chạy song song: không làm hỏng; tính trùng thì chấp nhận được.
2. Quét injection theo đơn vị không phụ thuộc người dùng: tính sẵn trong nền ngay sau khi nạp chỉ mục (luồng nền, không chặn khởi động). Lượt hỏi trong lúc đang tính vẫn đúng: tự tính đơn vị chưa có.
3. Làm nóng sau khởi động: trong lifespan của app (khi `rag_engine == "v2"` và có `knowledge_runtime`), chạy một tác vụ nền chỉ-đọc để nạp sẵn cache hàng nguồn và cache ràng buộc cho phạm vi sinh viên công khai, dùng đúng đường ủy quyền hiện có (`rag_v2_sources` với một `RetrievalContext` tạo bởi `retrieval_context_factory` cho một danh tính sinh viên tổng hợp chỉ dùng nội bộ để làm nóng). Yêu cầu với tác vụ này:
   - không gọi mô hình, không ghi gì, không cấp quyền;
   - lỗi thì ghi log và bỏ qua;
   - trạng thái hiển thị qua trường `warm` sẵn có trong `/health/ready` → `rag_v2` (`"pending" | "ready" | "failed"`).

   Nếu không thể tạo context hợp lệ mà không nới quyền thì không làm bước 3: ghi rõ lý do và chỉ làm bước 1–2.
4. Test (không mạng, gateway/embedding giả, chỉ mục tổng hợp):
   - (a) trong lúc dựng `units` của một chỉ mục lớn (đủ để mất ≥ 300 ms), một coroutine khác vẫn chạy được, không bị chặn quá ~100 ms. Ca này phải đỏ trên mã cũ.
   - (b) kết quả ủy quyền (tập `units`, `drops`) giống hệt trước và sau.
   - (c) làm nóng cập nhật `warm` và không gọi gateway.
   - (d) hai lượt đồng thời cho cùng kết quả.
5. Chạy `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp-W5 tests/rag_v2` (khoảng 2,5 phút), báo trước/sau. Không khởi động runtime, không gọi DeepSeek.
