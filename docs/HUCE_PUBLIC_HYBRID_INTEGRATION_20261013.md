# Tích hợp advanced retrieval vào HUCE public — 13/10/2026

**Cập nhật:** runtime đã được nạp và kiểm thật trong lượt tiếp theo; xem
[báo cáo activation cuối](HUCE_PUBLIC_HYBRID_ACTIVATION_20261013.md).
Các nhận định “chưa restart/chưa live” bên dưới là trạng thái của lượt trước.

Đã sửa mã nguồn cục bộ để factory `scripts/run_public_rag.py` dùng BM25 +
BGE-M3 → RRF → BGE-reranker-v2-m3 → mở rộng parent nguồn → kiểm chứng claim.
Đường dẫn API/UI vẫn là public `8000/3000`; state, lịch sử SQLite và gateway
ngân sách vẫn thuộc namespace public hiện có. Các tiến trình đang chạy chưa
được khởi động lại để nạp bản sửa.

## Wiring và thay đổi

- Trước sửa, bootstrap ưu tiên `public_knowledge_store.search()`; public factory
  truyền `PublicKnowledgeStore` chỉ dùng lexical/FAQ. Canonical hybrid không
  được gọi trên đường này. Runtime advanced riêng đã có BGE và semantic verifier.
- `scripts/public_rag_retrieval.py` tập trung model, revision, endpoint loopback,
  giới hạn và đọc index. Public và advanced dùng chung cấu hình này.
- Public tải và xác minh index hiện có trước khi mở state/gateway. Thiếu index,
  sai corpus/model/chunking/vector hoặc thiếu xác nhận giữ nguyên nguồn đều bị
  từ chối; không tự build index hoặc thay bằng lexical/fake model.
- Semantic verifier dùng cùng gateway public, phần deadline/output còn lại của
  generation; kết quả không thay nguồn, không cấp quyền và không thực thi action.
- Launcher public kiểm index/model listeners trước khi spawn; dừng nếu thấy
  public hoặc advanced API đang chiếm cổng. Đây là kiểm tra phụ thuộc, không là
  bằng chứng đầy đủ về quyền sở hữu ledger giữa mọi tiến trình.

Giữ nguyên corpus, source/locator/hash, filter tenant/campus/hiệu lực, citation
readback và ownership, EvidenceGate/OutputGuard, auth, xác nhận action, rate
limit, provider gateway và ledger. Không sửa các thay đổi có sẵn trong workspace.
Ba script đã tồn tại dạng untracked được lưu bản trước sửa trong thư mục bằng chứng.

## Giới hạn đã kiểm tra

Model card BAAI tại revision được pin mô tả embedding 1024 chiều và đầu vào
tới 8192 token: [BGE-M3](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/README.md).
Runtime local áp dụng giới hạn thấp hơn; không mở rộng theo khả năng lý thuyết
của model. Hai config model lưu local có `max_position_embeddings=8194`.

| Thành phần | Cấu hình thực tế được giữ |
|---|---|
| Embedding | BAAI/bge-m3, revision `5617a9f61b028005a4858fdac845db406aefb181`; L2, 1024 chiều, một text/request, adapter 5 giây |
| Reranker | BAAI/bge-reranker-v2-m3, revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; raw logit, adapter 10 giây |
| Native service | 900 token/text hoặc cặp query–passage có special tokens; không truncate; 3 giây/native call; CPU 4 core, memory 5 GiB |
| Retrieval | Lexical/vector tối đa 24 mỗi nhánh; sáu ứng viên rerank tổng cộng, chia tối đa ba subquery; bốn parent; 15.000 byte context; 12 giây gồm chờ lock |
| Native ledger | HTTP 6.000, inference 2.000, token 750.000; giữ reservations khi lỗi, không reset |
| Provider | deepseek-flash non-thinking, TLS; 5 giây/call, 1.000 output token, input cap 28.000; reservation trước HTTP; generation/regeneration/verifier chia ngân sách còn lại |
| Agent | Deadline lượt 30 giây; các kiểm soát route, safety và action hiện có giữ nguyên |

Index hiện có xác minh thành công: 131 parent, 261 child; fingerprint
`903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`.
Không ghi lại hoặc xây lại index/corpus.

## Kiểm chứng trong lượt này

| Phép kiểm | Kết quả | Giới hạn diễn giải |
|---|---|---|
| Regression cơ sở retrieval/TEI/public/budget | 60 passed, exit 0 | Model doubles; không chứng minh chất lượng câu trả lời thực tế |
| Test wiring mới | 18/18 passed trong suite mở rộng | Factory public, HTTP adapter, semantic verdict, SSE, source hash/ownership, reload SQLite, thiếu nguồn, thiếu index/model và launcher |
| Suite mở rộng | 751 passed, 1 failed; 22,64 giây; exit 1 | Suite chưa hoàn toàn xanh; lỗi ngoài phạm vi được ghi dưới đây |
| Retrieval BGE local đang chạy | 4/4 smoke passed, exit 0 | Ba câu có nguồn và một câu lịch thiếu nguồn; không phải benchmark độc lập |
| Source readback của smoke | 10/10 khớp nội dung/hash | Kiểm provenance; chưa kiểm mọi claim và hiệu lực chính sách ngoài snapshot |
| Lint | Ruff hai file mới pass, exit 0 | Không tuyên bố toàn repository sạch |

Smoke dùng câu hỏi học bổng, phòng học nhóm thư viện và hai chương trình từ bộ
regression hiện có. Nguồn kỳ vọng có trong tập kết quả, parent/hash giữ nguyên;
latency lần lượt 4.141, 2.359 và 1.594 ms. Câu lịch nghỉ Tết 2030 thiếu nguồn
trả tập rỗng, 47 ms, không embedding/rerank. Kết quả này không chứng minh answer
correctness, precision toàn bộ nguồn trả về, held-out recall hoặc SLO tải đồng thời.

Ledger paid trước/sau smoke bằng nhau: 8.362/8.500 call,
`1.6790964` USD đã tính bảo thủ / cap 3 USD, còn `1.3209036` USD và 138 call.
Không gọi paid generation, không thay cap, không hoàn lại uncertain reservations.
Native ledger tăng từ 1.422 lên 1.441 inference, token từ 325.683 lên 328.081;
HTTP từ 1.690 lên 1.702. Dùng dịch vụ hiện có, không start/stop model.

Lỗi còn lại: `tests/unit/retrieval/test_citations.py:39` kỳ vọng
`simulation_label=True` cho chunk không có metadata simulation. Mã citation đã
có thay đổi trước lượt này: lấy flag từ chunk hoặc trạng thái SYNTHETIC nên trả
False. Lỗi tái hiện khi chạy riêng test này, không nhập các script integration.
Giữ nguyên mã và expected result ngoài phạm vi; không hạ kiểm tra để suite xanh.

Python event loop Windows ban đầu kẹt ở socketpair trong sandbox. Các test hoàn
tất và smoke được chạy trong ngữ cảnh cho phép socket nội bộ/loopback. Pytest
dùng `-B`, `-p no:cacheprovider`, thư mục `--basetemp` mới trong workspace và
model giả lập; các thư mục/lỗi trước đó được giữ nguyên.

## Bằng chứng và tái lập

Thư mục: `infra/local/huce-public-hybrid-verification-20261013-01/`.

- `regression02.xml`: JUnit của 752 test, gồm failure hiện có và 18 test wiring mới.
- `retrieval-smoke.json`: kết quả từng ca, source/hash, native/paid ledger trước/sau.
- `retrieval_smoke.py`: runner không nhập/khởi tạo gateway paid.
- `*.before` và `*.patch`: bản trước sửa và diff của ba script integration.
- `verification-manifest-final.json`: hash source/artifact và kiểm tra cú pháp;
  bản manifest ban đầu chưa đủ artifact được giữ nguyên.

Python kiểm tra: `infra/local/rag-fixture/.venv/Scripts/python.exe`.
Test mới: `-B -m pytest -q -p pytest_asyncio.plugin -p no:cacheprovider
tests/unit/retrieval/test_public_rag_wiring.py` với `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`,
`PYTHONDONTWRITEBYTECODE=1` và một `--basetemp` chưa tồn tại trong workspace.
Thư mục cha của basetemp phải tồn tại; không tái sử dụng thư mục có dữ liệu vì
pytest có thể dọn basetemp. Smoke chỉ chạy với output mới, không ghi đè báo cáo.

Để nạp bản sửa cần một lần restart public API có kiểm soát, sau khi xác minh
đúng tiến trình và chỉ có một writer của ledger paid. Hiện `8000`, `8001`,
`3001`, `18081`, `18082` đang có listeners trong ngữ cảnh Windows thực tế;
quan sát cổng từ sandbox không phản ánh trạng thái này. Không khởi chạy API
thứ ba hoặc tự dừng các runtime đó.

Chưa kiểm generation paid với factory mới, browser sau restart, held-out
quality, tải đồng thời hoặc production. Source OCR và hiệu lực CURRENT vẫn
phụ thuộc chất lượng/phiên bản snapshot hiện có.
