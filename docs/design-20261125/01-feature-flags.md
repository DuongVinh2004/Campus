# F0 — Cờ tính năng cho mọi tính năng trong dự án

> Yêu cầu của chủ dự án (25/11/2026): "mỗi tính năng trong dự án phải bật tắt được bằng cờ".
> Phạm vi: **mọi** tính năng đang có và mọi tính năng mới của đợt này (F1–F8).

## 1. Mục tiêu và tiêu chí xong

Mục tiêu: quản trị viên bật hoặc tắt từng tính năng mà không phải sửa mã. Phần lớn cờ đổi được ngay khi hệ thống đang chạy. Tắt một tính năng thì mọi lối vào tính năng đó (API, trang, menu, job nền, tool agent) đóng lại cùng lúc, còn dữ liệu được giữ nguyên.

Tiêu chí xong, kiểm được:

1. Mọi route `/v1/*` mà runtime 8015 phục vụ và mọi trang trong `apps/web/src/app/**/page.tsx` thuộc **đúng một** cờ, hoặc thuộc nhóm lõi bị khóa. Có test quét route và trang; test đỏ khi có route hay trang mới chưa gắn cờ.
2. Với cấu hình mặc định, hành vi 8015 không đổi: `web_acceptance.mjs` và `run_full_regression.py --ci` vẫn đạt.
3. Với mỗi cờ có thể tắt, test tự động chứng minh bốn điều khi tắt nó:
   - route của nó trả `404` với `code=FEATURE_DISABLED`;
   - route của cờ khác không bị ảnh hưởng;
   - job của nó không chạy thêm tick nào;
   - tool agent của nó không còn trong danh sách gửi cho model.
4. Đổi cờ lúc đang chạy thì mọi API worker thấy giá trị mới trong **≤ 3 giây**. Đo bằng test hai tiến trình dùng chung tệp trạng thái.
5. Mọi lần đổi cờ đi qua preview → xác nhận → idempotency → audit (ai, lúc nào, trước/sau, lý do). Chỉ **quản trị viên** được đổi: `SYSTEM_ADMIN` hoặc `KNOWLEDGE_ADMIN`, đúng tập `ADMIN_ROLES` mà `require_admin` đang dùng (`application/campus_ops/service.py:24,64`). Tài khoản chủ dự án ở máy local mang vai trò `KNOWLEDGE_ADMIN` (`infrastructure/identity/local_owner.py:77`), nên nếu chỉ cho `SYSTEM_ADMIN` thì chủ dự án không đổi được cờ.
6. Các biến môi trường bật tắt cũ vẫn chạy như trước: chúng thành nguồn giá trị của cờ, không bị bỏ.

Ngoài phạm vi: A/B test có thống kê, phân phối cờ cho dịch vụ khác ngoài API và web, và giao diện cho người không phải quản trị.

---

## 2. Hiện trạng

- Bật tắt hiện nằm rải rác ở 4 kiểu, không có chỗ xem chung:
  1. Biến môi trường đọc lúc khởi động: `CAMPUS_LEARNING_ENABLED`, `CAMPUS_LEARNING_AI_ENABLED` (`scripts/knowledge_platform.py:365,475`), `CAMPUS247_OIDC_CONFIG` (`:554`).
  2. Biến môi trường đọc khi chạy: `CAMPUS247_RAG_ANSWER_CACHE` (`rag_v2/answer_cache.py:26`), `CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC` (`rag_v2/verification/verbatim.py:36`, ba giá trị `off|shadow|on`).
  3. Thuộc tính `Settings`: `parallel_classify`, `rag_engine` (`bootstrap/settings.py`).
  4. Biến build web `NEXT_PUBLIC_UNIFIED_AI`, `NEXT_PUBLIC_KNOWLEDGE_PLATFORM`, `NEXT_PUBLIC_CAMPUS_OPERATIONS`, `NEXT_PUBLIC_MULTI_AGENT`… (`apps/web/src/components/AppShell.tsx`): đóng cứng lúc build, không đổi được khi đang chạy.
- Lối vào API do `scripts/runtime_routes.py` quyết định bằng danh sách cứng (`ALLOWED_API_PREFIXES`, `BLOCKED_LEGACY_API_PREFIXES`), kèm test `tests/test_runtime_routes.py`. Theo danh sách này, `/v1/auth/oidc` và `/v1/auth/providers` đang **bị chặn**. Nghĩa là dù có cấu hình OIDC, runtime 8015 vẫn trả 404 cho các đường dẫn đó. Cần kiểm lại điểm này ở F0.2.
- `CapabilityManager` (`presentation/capabilities.py`) suy capability từ trạng thái hệ thống (NORMAL, READ_ONLY…). Đây là chiều khác với cờ: trạng thái vận hành tạm thời so với lựa chọn sản phẩm. F0 kết hợp hai chiều (§4.4), không thay thế nó.

---

## 3. Khái niệm

| Thuật ngữ | Nghĩa |
|---|---|
| **Cờ (feature)** | Một tính năng có tên khóa ổn định, ví dụ `rooms.booking` |
| **Định nghĩa cờ** | Khai báo trong mã (`campus247/features/registry.py`): khóa, mô tả, loại, mặc định, phụ thuộc, lối vào (route, trang, job, tool) |
| **Giá trị cấu hình** | Giá trị lấy từ hồ sơ chạy, biến môi trường hoặc ghi đè của quản trị |
| **Giá trị hiệu lực** | Kết quả cuối sau khi xét thứ tự ưu tiên, phụ thuộc, trạng thái hệ thống và đối tượng (§4) |
| **Cờ khóa (locked)** | Lõi không được tắt: đăng nhập, sức khỏe, quyền riêng tư, chính trang quản trị cờ |
| **Cờ nối lúc khởi động (`startup_wired`)** | Tính năng chỉ được dựng khi khởi động, ví dụ học liệu cần pool Postgres và cấu hình. Tắt lúc chạy được (gate chặn ngay); muốn **bật** khi lúc khởi động nó chưa được dựng thì phải khởi động lại, và giao diện quản trị nói rõ điều đó |

---

## 4. Thiết kế lõi

### 4.1 Định nghĩa cờ (trong mã)

Tệp mới `campus247/features/registry.py`. Đây là domain thuần: không I/O, không đọc môi trường.

```python
@dataclass(frozen=True)
class FeatureDefinition:
    key: str                       # "area.name", ^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$
    title: str                     # tiếng Việt, hiện trong trang quản trị
    description: str
    area: Literal["core","chat","assistant","services","campus","learning","knowledge","admin","web","ai"]
    kind: Literal["module","job","ai","ops","ui"]
    default: bool                  # mặc định khi không có cấu hình nào; tính năng mới = False
    locked: bool = False           # True: luôn bật, không ghi đè được
    startup_wired: bool = False
    depends_on: tuple[str, ...] = ()
    api_prefixes: tuple[str, ...] = ()     # khớp tiền tố
    api_patterns: tuple[str, ...] = ()     # regex khớp toàn bộ, cho route lồng (feedback trong conversations)
    pages: tuple[str, ...] = ()            # đường dẫn trang web không có "/" đầu, khớp tiền tố theo đoạn
    nav_keys: tuple[str, ...] = ()         # khóa mục điều hướng trong AppShell
    jobs: tuple[str, ...] = ()             # tên job nền
    tools: tuple[str, ...] = ()            # tool_id trong agent/tools/registry.py
    client_visible: bool = True            # có trả về cho trình duyệt qua /v1/features không
    capability: str | None = None          # tên capability của CapabilityManager cần bật kèm (nếu có)
    env_alias: str | None = None           # biến môi trường cũ, xem §4.3
    variants: tuple[str, ...] = ()         # cờ nhiều giá trị, ví dụ ("off","shadow","on"); rỗng = bật/tắt
    cost: Literal["none","model_calls","ram","external"] = "none"
```

Ràng buộc kiểm khi nạp (test và lúc khởi động):

- Khóa là duy nhất. `depends_on` trỏ tới khóa có thật và không tạo vòng (sắp topo).
- Một tiền tố API hoặc một trang không thuộc hai cờ. Riêng các cặp lồng nhau được phép, ví dụ `chat.feedback` lồng trong `chat.assistant`, với điều kiện cờ con phụ thuộc cờ cha. Khi đó đường dẫn khớp **dài nhất** quyết định.
- Cờ `locked` thì `default=True`, không có `depends_on` tới cờ có thể tắt, và không có `variants`.

### 4.2 Lưu trữ giá trị

| Nguồn | Nơi | Đổi khi chạy | Ai đổi |
|---|---|---|---|
| Mặc định | `registry.py` | Không | Lập trình viên (qua review) |
| Hồ sơ chạy | `infra/profiles/features.<profile>.toml`, ví dụ `features.local.toml`, `features.cloud.toml` | Không (đọc lúc khởi động) | Người vận hành |
| Biến môi trường cũ | `env_alias` | Không | Người vận hành |
| Ghi đè quản trị | SQLite `<STATE>/feature-flags.sqlite3` (WAL), xem quyết định D1 | **Có** | Quản trị viên (`ADMIN_ROLES`) qua trang quản trị |
| Tắt khẩn cấp | `CAMPUS247_FEATURES_OFF=key1,key2` hoặc `*` | Không (khởi động lại) | Người vận hành |

Tệp cờ để riêng, **không** nhét vào `local.toml`/`cloud.toml`. Lý do: `runtime_profile.py` kiểm schema chặt, đúng tập khóa; thêm bảng mới sẽ làm hỏng hồ sơ cũ. Tệp cờ có schema riêng:

```toml
# infra/profiles/features.cloud.toml
schema = "campus247-features-v1"
profile = "cloud"
[features]
"learning.core" = false          # cloud chưa có ClamAV Linux (memory rollout-phase1-state)
"learning.ai_explanations" = false
"chat.answer_cache" = false
"chat.verbatim_skip" = "off"     # cờ nhiều giá trị
```

Khóa không có trong registry thì lỗi khởi động, để gõ sai không lặng lẽ thành "tắt".

Schema SQLite:

```sql
CREATE TABLE IF NOT EXISTS ff_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);       -- 'version' tăng mỗi lần ghi
CREATE TABLE IF NOT EXISTS ff_overrides(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,                 -- 'true' | 'false' | tên variant
  audience TEXT NOT NULL DEFAULT '{}', -- JSON, xem §4.5
  expires_at TEXT,                     -- NULL = không hết hạn; hết hạn thì bỏ qua (quay về nguồn thấp hơn)
  reason TEXT NOT NULL,
  actor_subject_id TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ff_previews(
  id TEXT PRIMARY KEY, actor_subject_id TEXT NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
  expected_version INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS ff_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor_subject_id TEXT NOT NULL, key TEXT NOT NULL,
  before TEXT NOT NULL, after TEXT NOT NULL, reason TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  UNIQUE(actor_subject_id, idempotency_key));
```

Dòng `ff_audit` không bao giờ bị xóa. Gỡ ghi đè ("trả về mặc định") là ghi một dòng audit với `after = {"removed": true}`.

### 4.3 Thứ tự ưu tiên và giá trị hiệu lực

Giá trị cấu hình lấy từ nguồn cao nhất có giá trị:

```
1. CAMPUS247_FEATURES_OFF chứa key (hoặc "*")      -> false   (bỏ qua với cờ locked)
2. ff_overrides còn hạn và khớp đối tượng          -> value
3. env_alias có đặt                                -> parse(value)
4. features.<profile>.toml                         -> value
5. FeatureDefinition.default
```

Giá trị hiệu lực cho một người dùng:

```
effective(key, actor) =
    locked(key)
 OR ( configured(key, actor)
      AND all(effective(d, actor) for d in depends_on(key))
      AND (startup_wired(key) => wired_at_startup(key))
      AND (capability(key) is None OR capability_map[capability(key)]) )
```

`explain(key, actor)` trả lý do khi hiệu lực là tắt. Có 6 mã: `CONFIGURED_OFF`, `EMERGENCY_OFF`, `DEPENDENCY_OFF:<key>`, `NOT_WIRED_RESTART_REQUIRED`, `SYSTEM_STATE:<state>`, `AUDIENCE_EXCLUDED`. Trang quản trị và log dùng các mã này.

Biến môi trường cũ được ánh xạ như sau:

| Biến cũ | Cờ | Ánh xạ |
|---|---|---|
| `CAMPUS_LEARNING_ENABLED` | `learning.core` | `true`/`false`, giữ kiểm hợp lệ hiện có |
| `CAMPUS_LEARNING_AI_ENABLED` | `learning.ai_explanations` | như trên; vẫn bắt buộc runtime có generation |
| `CAMPUS247_RAG_ANSWER_CACHE` | `chat.answer_cache` | `1/on/true/yes` → true |
| `CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC` | `chat.verbatim_skip` | variant `off|shadow|on` |
| `CAMPUS247_PARALLEL_CLASSIFY` | `chat.parallel_classify` | bool |
| `CAMPUS247_OIDC_CONFIG` | `identity.oidc` | có đặt → được nối lúc khởi động; cờ quyết định có phục vụ hay không |

Mã đọc trực tiếp các biến này được chuyển sang gọi `features.value(key)` trong F0.5. Hành vi giữ nguyên vì biến môi trường vẫn là nguồn số 3.

### 4.4 Kết hợp với trạng thái hệ thống

Cờ khai báo `capability="ticket_create"` (hay capability khác) tự tắt khi `CapabilityManager` báo capability đó tắt, ví dụ ở READ_ONLY hay MAINTENANCE. Lý do hiện ra là `SYSTEM_STATE:READ_ONLY`.

Bảng ánh xạ ban đầu:
- `tickets.student` → `ticket_create`
- `rooms.booking` → `room_booking`
- `chat.assistant` → `chat_generation`
- `services.preparations` → `ticket_create`

Phần này chỉ áp cho route ghi. Route đọc vẫn mở, khớp `ticket_read=True` ở READ_ONLY. Định nghĩa cờ có thêm `capability_scope: Literal["write","all"]="write"`. "Ghi" nghĩa là phương thức POST/PUT/PATCH/DELETE.

### 4.5 Đối tượng (bật thử cho một nhóm)

`audience` trong ghi đè, mọi điều kiện là AND:

```json
{"roles": ["STUDENT","LECTURER"], "subjects": ["<uuid7>", "..."], "percent": 20}
```

- `roles`: người dùng có ít nhất một vai trò trong danh sách.
- `subjects`: tối đa 200 subject id, dùng cho thí điểm. Không ghi tên người.
- `percent`: `int(sha256(key + ":" + subject_id)[:8], 16) % 100 < percent`. Ổn định theo người, độc lập giữa các cờ.
- Không có người dùng (khách, job nền): chỉ xét `roles=["GUEST"]` hoặc đối tượng rỗng.

Đối tượng chỉ áp cho cờ `module`/`ui`/`ai`. Cờ `job` và `ops` bỏ qua đối tượng vì job không chạy thay mặt một người.

### 4.6 Dịch vụ cờ (application)

`campus247/application/features/service.py`:

```python
class FeatureService:
    def __init__(self, registry, profile_values, env, store, capabilities, wired: frozenset[str], clock): ...
    def enabled(self, key: str, actor: IdentityContext | None = None) -> bool
    def value(self, key: str, actor=None) -> str | bool      # cho cờ nhiều giá trị
    def explain(self, key: str, actor=None) -> FeatureExplanation
    def snapshot(self, actor=None) -> FeatureSnapshot        # {version, values}; dùng 1 lần cho cả lượt chat
    def feature_for_path(self, path: str, method: str) -> str | None
    def preview_change(self, admin, key, *, value, audience, expires_at, reason, expected_version) -> ChangePreview
    def confirm_change(self, admin, preview_id, token, idempotency_key) -> ChangeReceipt
    def remove_override(...)  # cũng qua preview/confirm
```

Bộ nhớ đệm giữa các worker: mỗi lời gọi đọc `ff_meta.version`, nhưng không quá một lần mỗi 2 giây cho mỗi tiến trình. Khi version đổi thì nạp lại toàn bộ `ff_overrides`. SQLite WAL chịu được nhiều tiến trình đọc. Ghi là giao dịch `IMMEDIATE` ngắn, giống `CampusOpsStore`. Độ trễ lan truyền ≤ 2 s cộng thời gian xử lý, thỏa tiêu chí ≤ 3 s.

Lỗi tệp cờ (hỏng, khóa quá lâu): dịch vụ giữ snapshot hợp lệ cuối cùng và ghi log `feature_store_unavailable`; chỉ số `ops` đếm lỗi. Lúc khởi động mà tệp hỏng thì **không** tự tạo tệp rỗng thay thế, cùng nguyên tắc với `actor-storage-initialized.json`. Khi đó dùng nguồn 3–5 và báo trên trang quản trị.

### 4.7 Điểm chặn (enforcement)

| Lối vào | Cơ chế | Vị trí |
|---|---|---|
| API | Middleware `feature_gate`: `feature_for_path(path, method)` → nếu tắt trả `404` problem `{"code":"FEATURE_DISABLED","feature":key}`, `Cache-Control: no-store`. Chạy **trước** `operational_boundary` | `scripts/knowledge_platform.py` (runtime 8015) và `bootstrap/app.py` (app thường, test) |
| Luồng chat SSE đang chạy | Snapshot cờ chụp một lần đầu lượt (`messages:stream`). Tắt giữa lượt không cắt lượt đó | `agent/graph.py` (truyền snapshot vào state) |
| Trang web | API proxy trang: `is_served_path` + cờ của trang. Tắt → trang 404 chuẩn `NOT_FOUND_HTML` | `scripts/runtime_routes.py`, `knowledge_platform.py:795` |
| Điều hướng web | `nav_keys` → AppShell lọc mục | `apps/web/src/components/AppShell.tsx` |
| Thành phần web trong trang | `useFeature(key)` / `<FeatureGate>` | `apps/web/src/lib/features.tsx` (mới) |
| Job nền | Bọc vòng lặp: `if not features.enabled(job_key): sleep; continue` trước mỗi tick | `scripts/knowledge_platform.py:604-660`, các `run_*` nhận thêm `enabled: Callable[[], bool]` |
| Tool agent | `ToolRegistry.available(snapshot)` lọc tool có cờ tắt trước khi dựng prompt. Model không thấy tool đã tắt. Executor kiểm lại lúc thực thi (phòng tool cũ trong preview) | `agent/tools/registry.py`, `executor.py` |
| Tùy chọn trong pipeline RAG | `features.value("chat.verbatim_skip")`… đọc từ snapshot của lượt | `rag_v2/answer_cache.py`, `rag_v2/verification/verbatim.py` |
| Thông báo đã sinh | Không thu hồi. Thông báo đã nằm trong hộp thư vẫn đọc được, vì `notifications.inbox` là cờ riêng | — |

Chọn 404 thay vì 403 hay 503 vì ba lý do: khớp với hành vi hiện có của `operational_boundary` (đường dẫn chưa mở là 404); không tiết lộ tính năng tồn tại với người không có quyền; và web đã có đường xử lý 404 (`use-policy-graph-available.ts`).

### 4.8 API

Mọi phản hồi đều có `Cache-Control: no-store`.

**`GET /v1/features`**: mọi người, kể cả khách.

```json
{"version": 42, "features": {"chat.assistant": true, "rooms.booking": false, "chat.verbatim_skip": "off"}}
```

Chỉ gồm cờ `client_visible=True`, đã tính theo người đang gọi. Không có lý do, đối tượng hay người đổi. Header `ETag: "42"`; gửi `If-None-Match` trùng thì nhận `304`.

**`GET /v1/admin/features`**: quản trị viên (`ADMIN_ROLES`).

```json
{"version": 42, "profile": "local", "items": [{
  "key": "rooms.booking", "title": "Đặt phòng", "area": "campus", "kind": "module",
  "locked": false, "startup_wired": false, "depends_on": [], "dependents": ["proactive.nudges"],
  "configured": {"value": false, "source": "override", "expires_at": null,
                 "reason": "Bảo trì phòng tầng 3", "by": "<subject>", "at": "2026-11-25T03:00:00Z"},
  "sources": {"default": true, "profile": true, "env": null, "override": false, "emergency_off": false},
  "effective_for_all": false, "off_reasons": ["CONFIGURED_OFF"],
  "entry_points": {"api": ["/v1/rooms"], "pages": ["rooms"], "jobs": [], "tools": []},
  "cost": "none"}]}
```

**`POST /v1/admin/features/{key}:preview`**: quản trị viên.

```json
// yêu cầu
{"value": false, "audience": {}, "expires_at": null, "reason": "Bảo trì phòng tầng 3 (≥ 10 ký tự)",
 "expected_version": 42}
// phản hồi 200
{"preview_id": "<uuid7>", "confirmation_token": "<HMAC>", "expires_at": "...+10 phút",
 "change": {"key": "rooms.booking", "from": true, "to": false},
 "impact": {"also_off": ["proactive.nudges"], "api_prefixes": ["/v1/rooms"], "pages": ["rooms"],
            "jobs": [], "restart_required": false, "data_kept": true}}
```

Token dùng `ConfirmationTokenService` sẵn có (`domain/action/confirmation.py`), ký bằng `CONFIRMATION_SIGNING_KEY`, gắn `preview_id` và subject.

**`POST /v1/admin/features:confirm`**: quản trị viên, header `Idempotency-Key` bắt buộc.

```json
{"preview_id": "...", "confirmation_token": "..."}
// 200
{"receipt_id": "<audit id>", "key": "rooms.booking", "value": false, "version": 43, "applied_at": "..."}
```

**`DELETE /v1/admin/features/{key}/override`**: trả về giá trị của nguồn thấp hơn. Đi theo đúng cặp preview/confirm, với body `{"remove": true, ...}`.

**`GET /v1/admin/features/audit?key=&cursor=&limit=50`**: lịch sử đổi cờ, phân trang ổn định.

Lỗi:

| HTTP | `code` | Khi nào |
|---|---|---|
| 403 | `FORBIDDEN` | Không thuộc `ADMIN_ROLES` (kể cả `KNOWLEDGE_CONTRIBUTOR`) |
| 404 | `FEATURE_UNKNOWN` | Khóa không có trong registry |
| 409 | `FEATURE_VERSION_CONFLICT` | `expected_version` cũ; trả version hiện tại |
| 409 | `FEATURE_DEPENDENCY_OFF` | Bật cờ con khi cờ cha đang tắt; liệt kê cờ cha cần bật trước |
| 410 | `PREVIEW_EXPIRED` | Preview quá 10 phút hoặc đã dùng |
| 422 | `FEATURE_LOCKED` | Ghi đè cờ khóa |
| 422 | `FEATURE_VALUE_INVALID` | Giá trị ngoài `variants`, lý do ngắn, `expires_at` đã qua, `audience` sai dạng |
| 428 | `CONFIRMATION_REQUIRED` | Confirm thiếu token hoặc token sai |

Thêm `/v1/features` và `/v1/admin/features` vào `ALLOWED_API_PREFIXES` của `runtime_routes.py`.

### 4.9 Web

- `apps/web/src/lib/features.tsx`: `FeatureProvider` gọi `GET /v1/features` khi tải, khi tab được focus lại, và mỗi 60 s. Cung cấp `useFeature(key): boolean | undefined` (`undefined` khi đang tải), `useFeatureValue(key)` và `<FeatureGate feature fallback>`.
- Trong lúc đang tải, ẩn mục điều hướng thuộc cờ mặc định tắt, hiện mục thuộc cờ mặc định bật. Bảng mặc định sinh từ registry (§4.10) để tránh nhấp nháy. Tải lỗi thì giữ giá trị đã biết cuối cùng; chưa có thì dùng mặc định.
- Biến `NEXT_PUBLIC_*` giữ vai trò "mã có được build vào hay không". Giá trị hiệu lực ở web là `build_flag && runtime_flag`.
- AppShell: mỗi mục điều hướng thêm trường `feature`, và `navItems.filter(i => !i.feature || enabled(i.feature))`.
- Trang `/admin/features` (mới, `features/admin/FeatureFlagsPanel.tsx`):
  - Bảng nhóm theo `area`: tên, trạng thái hiệu lực (huy hiệu Bật/Tắt/Một phần), nguồn giá trị, người đổi gần nhất, cột "lối vào".
  - Bộ lọc: đang tắt, có ghi đè, cần khởi động lại.
  - Nút đổi mở hộp thoại: ô lý do (bắt buộc), chọn hết hạn (1 giờ, 1 ngày, 7 ngày, không hết hạn), đối tượng (tùy chọn, dạng nâng cao), và khối preview liệt kê cờ phụ thuộc bị tắt theo. Chỉ có nút "Xác nhận" sau khi preview thành công.
  - Tab "Lịch sử" đọc audit.
  - Trạng thái rỗng, đang tải và lỗi theo nếp `campus-*` sẵn có. Có tiếng Việt và tiếng Anh (`lib/i18n`).
- Service worker (PWA): `/v1/features` luôn đi mạng (network-only), không cache.

### 4.10 Sinh mã và chống trôi

- `scripts/export_feature_registry.py` xuất `apps/web/src/lib/feature-registry.generated.ts`: khóa, mặc định, `nav_keys`, `pages`. Khóa là kiểu union TypeScript, gõ sai khóa là lỗi biên dịch.
- Test `tests/test_feature_registry.py` có bốn kiểm:
  1. Mọi route của app 8015, lấy từ `make_app` với fixture giống `test_runtime_routes.py`, thuộc đúng một cờ hoặc thuộc `CORE_PATHS`.
  2. Mọi `page.tsx` thuộc một cờ.
  3. Tệp `.generated.ts` khớp registry; lệch thì test đỏ, kèm lệnh sinh lại.
  4. Mỗi `features.*.toml` chỉ có khóa hợp lệ.
- `runtime_routes.ALLOWED_API_PREFIXES` vẫn giữ làm lớp ngoài: route không được phép thì vẫn 404 dù cờ bật. Cờ chỉ **thu hẹp** thêm, không bao giờ mở rộng ra ngoài danh sách cho phép.

---

## 5. Sổ cờ ban đầu (toàn bộ tính năng hiện có và mới)

Ký hiệu cột mặc định: L = hồ sơ `local`, C = hồ sơ `cloud`, ✓ bật, ✗ tắt. Mặc định của registry bằng cột L, trừ khi có ghi chú khác.

### 5.1 Lõi (khóa, luôn bật)

| Khóa | Lối vào | Lý do khóa |
|---|---|---|
| `core.auth` | `/v1/users/me`, `/v1/auth/logout`, `/v1/knowledge/platform/session`, trang `login` | Không có thì không đăng nhập hay đăng xuất được |
| `core.health` | `/health/*` | Giám sát và watchdog |
| `core.privacy` | `/v1/privacy/*`, trang `privacy` | Quyền xem thông báo dữ liệu và gửi yêu cầu về dữ liệu không được tắt |
| `core.features` | `/v1/features`, `/v1/admin/features*`, trang `admin/features` | Không tự khóa mình ra ngoài |
| `core.home` | trang `""` (trang chủ), `offline` | Điểm vào; trang offline của PWA |

### 5.2 Chat và trợ lý

| Khóa | Lối vào | Phụ thuộc | L | C | Ghi chú |
|---|---|---|---|---|---|
| `chat.assistant` | `/v1/conversations` (POST, GET), `…/messages`, `…/messages:stream`, `…/receipts/*`; trang `chat`; nav `chat` | — | ✓ | ✓ | capability `chat_generation` |
| `chat.history` | `/v1/assistant/conversations*`; thành phần `ConversationHistory` | chat.assistant | ✓ | ✓ | |
| `chat.feedback` | regex `^/v1/conversations/[^/]+/messages/[^/]+/feedback(/.*)?$`; `AnswerFeedback` | chat.assistant | ✓ | ✓ | |
| `chat.gap_report` | `/v1/answer-gap-reports*`; `GapReport` | chat.assistant | ✓ | ✓ | |
| `chat.parallel_classify` | (pipeline) | chat.assistant | ✓ | ✓ | `env_alias=CAMPUS247_PARALLEL_CLASSIFY`, `client_visible=False` |
| `chat.answer_cache` | (pipeline) | chat.assistant | ✗ | ✗ | Đòn bẩy L2, chủ dự án quyết; `client_visible=False` |
| `chat.verbatim_skip` | (pipeline) | chat.assistant | `off` | `off` | variants `off,shadow,on`; L1 |
| `assistant.personalization` | `/v1/assistant/preferences*`, `/v1/assistant/chats/*`, `/v1/assistant/consent*`, `/v1/assistant/consents*`, `/v1/assistant/context*`, `/v1/assistant/consumer-capabilities` | chat.assistant | ✓ | ✓ | Tắt thì trợ lý chạy như chưa đồng ý cá nhân hóa |
| `assistant.memory` | `/v1/assistant/memory*`; trang `memory` | assistant.personalization | ✓ | ✓ | |
| `assistant.tracking` | `/v1/assistant/tracking*` | assistant.personalization | ✓ | ✓ | |
| `assistant.grants` | `/v1/assistant/grants*`, `/v1/assistant/resources:read`, `/v1/assistant/resource-runs*` | assistant.personalization | ✓ | ✓ | |
| `assistant.legacy_import` | `/v1/assistant/legacy-imports*` | assistant.personalization | ✓ | ✓ | |
| `assistant.baseline` | `/v1/assistant/baseline*`, `/v1/assistant/contracts` | — | ✓ | ✓ | |

### 5.3 Dịch vụ sinh viên và ticket

| Khóa | Lối vào | Phụ thuộc | L | C |
|---|---|---|---|---|
| `services.preparations` | `/v1/student-preparations*`, `/v1/assistant/student-actions`, `/v1/assistant/student:*`, `/v1/assistant/proposals:prepare`, `/v1/assistant/surface:resolve`, `/v1/assistant/receipts*`; trang `services`; nav `services` | — | ✓ | ✓ |
| `services.case_workflow` | `/v1/assistant/cases*`, `/v1/assistant/workflows`, `/v1/assistant/staff-workspace*`, `/v1/assistant/staff-drafts*` | — | ✓ | ✓ |
| `tickets.student` | `/v1/tickets*`; trang `tickets`; nav `tickets` | — | ✓ | ✓ |
| `tickets.staff_queue` | `/v1/staff/tickets*`; trang `staff`; nav `staff` | — | ✓ | ✓ |

### 5.4 Vận hành khuôn viên

| Khóa | Lối vào | Phụ thuộc | L | C |
|---|---|---|---|---|
| `rooms.booking` | `/v1/rooms*`; trang `rooms`; nav `rooms` | — | ✓ | ✓ |
| `schedule.personal` | `/v1/students/me/schedule`, `/v1/students/me/schedule/events*`; trang `schedule`; nav `schedule` | — | ✓ | ✓ |
| `schedule.ics` | `/v1/students/me/schedule.ics` | schedule.personal | ✓ | ✓ |
| `notifications.inbox` | `/v1/notifications*`; trang `notifications`; nav `notifications` | — | ✓ | ✓ |
| `reminders.exam` | job `exam_reminders` (`run_reminders`) | notifications.inbox, schedule.personal | ✓ | ✓ |

### 5.5 Học liệu

Toàn bộ học liệu nằm dưới `/v1/learning/*`. Tiền tố con lấy từ `presentation/learning*.py`. Đường dẫn chính xác chốt ở F0.2 bằng test quét route.

| Khóa | Lối vào | Phụ thuộc | L | C | Ghi chú |
|---|---|---|---|---|---|
| `learning.core` | `/v1/learning/*` (phần còn lại); trang `learning`; nav `learning` | — | ✓ | ✗ | `startup_wired`, `env_alias=CAMPUS_LEARNING_ENABLED`; cloud tắt vì chưa có ClamAV Linux |
| `learning.upload_ocr` | `…/materials/{id}/upload-intents`, `…/ocr-jobs/*`, `…/ocr-releases/*`; job `learning_worker` | learning.core | ✓ | ✗ | |
| `learning.accessible_text` | `…/reading-instructions/*`; job `accessible_text` | learning.core | ✓ | ✗ | |
| `learning.exit_tickets` | `…/exit-tickets/*`, `…/sessions/{id}/exit-tickets` | learning.core | ✓ | ✗ | |
| `learning.exit_reminders` | job `exit_ticket_reminders` | learning.exit_tickets, notifications.inbox | ✓ | ✗ | |
| `learning.idea_cards` | `…/me/idea-cards*`, `…/me/idea-topics*`, `…/me/idea-shares*` | learning.core | ✓ | ✗ | |
| `learning.practice` | `…/practice-sets/*`, `…/practice-items/*` | learning.core | ✓ | ✗ | |
| `learning.discussion` | `…/questions/*`, `…/replies/*` | learning.core | ✓ | ✗ | |
| `learning.page_feedback` | `…/me/page-feedback*` | learning.core | ✓ | ✗ | |
| `learning.presentations` | `…/presentations/*`, `…/offerings/{id}/presentations` | learning.core | ✓ | ✗ | |
| `learning.ai_explanations` | `…/page-explanations/*`, `…/sessions/{id}/page-explanations` | learning.core | ✗ | ✗ | `startup_wired`, `env_alias=CAMPUS_LEARNING_AI_ENABLED`, `cost=model_calls` |

### 5.6 Kho tri thức

| Khóa | Lối vào | Phụ thuộc | L | C |
|---|---|---|---|---|
| `knowledge.sources` | `/v1/knowledge/sources*`, `/v1/knowledge/source-review-status`, `/v1/knowledge/document-versions/*`, `/v1/knowledge/platform/availability`, `…/state`; trang `knowledge/sources`, `knowledge`; nav `knowledge` | — | ✓ | ✓ |
| `knowledge.documents` | `/v1/knowledge/platform/{documents,uploads,intakes,url-intakes,previews,search-preview,resolve-preview,confirmations,jobs}*`, `…/versions/{id}/{original,rendition,reviews,releases}`; trang `knowledge/documents`; nav `documents` | knowledge.sources | ✓ | ✓ |
| `knowledge.corrections` | `…/platform/corrections*`, `…/versions/{id}/correction*` | knowledge.documents | ✓ | ✓ |
| `knowledge.editions` | `…/platform/edition-relations*`, `…/platform/editions/*`, `…/versions/{id}/{edition-workspace,applicability-versions}` | knowledge.documents | ✓ | ✓ |
| `knowledge.crawl` | `…/platform/crawl-sources*`; trang `knowledge/crawl`; nav `crawl`; tick `crawl` trong worker | knowledge.documents | ✓ | ✓ |
| `knowledge.auto_publication` | tick `auto` trong worker ingest | knowledge.documents | ✓ | ✓ |
| `knowledge.schedules` | `…/platform/schedules*`; job `knowledge_schedules` | knowledge.documents | ✓ | ✓ |
| `knowledge.freshness` | `/v1/knowledge/freshness*`; trang `knowledge/freshness`; job `freshness_reminders` | knowledge.sources | ✓ | ✓ |
| `knowledge.answer_quality` | `/v1/knowledge/answer-quality*`, `/v1/knowledge/gap-reports`; trang `knowledge/quality` | knowledge.sources | ✓ | ✓ |
| `knowledge.release_check` | job `release_check` | knowledge.sources | ✓ | ✓ |
| `knowledge.policy_graph` | `/v1/policy-graph/*`; trang `knowledge/policy-graph` | knowledge.sources | ✗ | ✗ |

`knowledge.policy_graph` mặc định tắt vì đồ thị hiện chưa chạy trên v2 (E3). Gói G-PG ở [03](03-policy-rules-engine.md) bật lại nó.

### 5.7 Quản trị, danh tính, web

| Khóa | Lối vào | Phụ thuộc | L | C | Ghi chú |
|---|---|---|---|---|---|
| `admin.overview` | `/v1/admin/overview`; trang `admin`; nav `admin` | — | ✓ | ✓ | |
| `admin.operations` | `/v1/admin/operations/*` | admin.overview | ✓ | ✓ | |
| `ops.alerts` | job `alerts` | — | ✓ | ✓ | `kind=ops` |
| `identity.oidc` | `/v1/auth/oidc*`, `/v1/auth/providers`; nút đăng nhập trường | — | ✗ | ✗ | `startup_wired` (cần `CAMPUS247_OIDC_CONFIG`) |
| `web.pwa` | `sw.js`, `manifest.webmanifest`; đăng ký service worker | — | ✓ | ✓ | Tắt thì web gỡ đăng ký service worker và xóa cache |
| `web.i18n_en` | nút chuyển ngôn ngữ, từ điển `en.ts` | — | ✓ | ✓ | |

### 5.8 Tính năng mới của đợt (mặc định tắt ở mọi hồ sơ)

| Khóa | Tài liệu | Phụ thuộc |
|---|---|---|
| `announcements.publish` | F1 | notifications.inbox |
| `announcements.inbox` | F1 | notifications.inbox |
| `announcements.knowledge_sync` | F1 | announcements.publish, knowledge.documents |
| `announcements.second_approval` | F1 | announcements.publish (cờ chính sách: bật thì gửi toàn trường cần người thứ hai duyệt) |
| `announcements.chat_tool` | F1.8 (cần duyệt) | announcements.inbox, chat.assistant |
| `policy.graph_v2` | G-PG trong F2 | knowledge.policy_graph |
| `policy.rules` | F2 | policy.graph_v2 |
| `policy.simulator` | F2 | policy.rules, chat.assistant |
| `policy.impact` | F3 | policy.graph_v2 |
| `policy.conflicts` | F3 | policy.graph_v2 |
| `policy.impact_announcements` | F3 | policy.impact, announcements.publish |
| `policy.impact_user_notices` | F3.6 (cần duyệt) | policy.impact, notifications.inbox, chat.history |
| `chat.evidence_receipts` | F4 | chat.assistant |
| `chat.evidence_ui` | F4 | chat.evidence_receipts |
| `agent.procedures` | F5 | policy.rules, services.preparations, tickets.student |
| `proactive.nudges` | F6 | notifications.inbox |
| `proactive.digest` | F6 | proactive.nudges |
| `learning.tutor` | F7 | learning.practice |
| `learning.mastery_map` | F7 | learning.practice |
| `input.image` | F8 | chat.assistant |
| `input.voice` | F8 | chat.assistant |
| `output.read_aloud` | F8 | chat.assistant |

---

## 6. Bảo mật

- Chỉ quản trị viên (`ADMIN_ROLES` = `SYSTEM_ADMIN`, `KNOWLEDGE_ADMIN`) đổi cờ, kiểm ở application service, không chỉ ở route. `KNOWLEDGE_CONTRIBUTOR`, `SUPPORT_OFFICER`, `LECTURER` và `STUDENT` không đổi được. Khi có tài khoản `SYSTEM_ADMIN` thật (sau OIDC), có thể thu hẹp xuống còn `SYSTEM_ADMIN`; đó là quyết định riêng của chủ dự án.
- `GET /v1/features` không trả lý do, đối tượng hay danh sách subject. Người dùng chỉ biết giá trị của chính mình.
- Không cờ nào được nới kiểm tra bảo mật, xác thực, xác nhận hay kiểm nguồn. Registry **cấm** khai báo cờ kiểu "tắt xác nhận" hay "bỏ kiểm nguồn": test kiểm danh sách đen tên khóa (`*confirm*`, `*auth*`, `*verify*` khi không có `locked`) và review bắt buộc.
- Tắt khẩn cấp bằng biến môi trường chỉ tắt được, không bật được.
- Audit lưu subject id, không lưu tên hiển thị hay địa chỉ IP.

## 7. Quan sát

- Gauge `feature_enabled{key}` (0/1, theo cấu hình toàn cục) trong `ops-metrics`.
- Bộ đếm `feature_blocked_requests_total{key}`.
- Bộ đếm `feature_store_errors_total`.
- Trang `/admin` (ops status) thêm ô "Cờ đang tắt: n · có ghi đè: m · cần khởi động lại: k".
- Cảnh báo mới (`observability/alerts.py`): ghi đè hết hạn trong 24 giờ tới (mức thông tin); tệp cờ lỗi hơn 5 phút (mức cảnh báo).

## 8. Kiểm thử

| Mức | Nội dung | Tệp |
|---|---|---|
| Đơn vị | Thứ tự ưu tiên 5 nguồn; phụ thuộc bắc cầu; vòng phụ thuộc bị từ chối; cờ khóa; hết hạn; `percent` ổn định (vector cố định); variants; `explain` đúng mã | `tests/features/test_feature_resolution.py` |
| Đơn vị | Registry hợp lệ: khóa duy nhất, không chồng tiền tố trái phép, tên cấm | `tests/features/test_feature_registry.py` |
| Tích hợp | Quét route và trang (tiêu chí 1); tệp `.generated.ts` khớp | `tests/test_feature_registry.py` |
| Tích hợp | Ma trận tắt: tham số hóa theo mọi khóa không khóa → route 404 `FEATURE_DISABLED`; một route của cờ khác vẫn 200 hoặc 401 như trước | `tests/features/test_feature_gate_matrix.py` |
| Tích hợp | Job: `enabled=False` thì hàm tick không được gọi trong 3 chu kỳ; bật lại thì chạy | `tests/features/test_feature_jobs.py` |
| Tích hợp | Tool: registry lọc tool; executor từ chối tool đã tắt dù có preview cũ | `tests/features/test_feature_tools.py` |
| Tích hợp | Hai `FeatureService` dùng chung tệp: ghi ở A, B thấy trong ≤ 3 s | `tests/features/test_feature_propagation.py` |
| API | preview/confirm/idempotency/409/410/422/428; không phải admin → 403 | `tests/features/test_feature_admin_api.py` |
| Web | `useFeature`, `FeatureGate`, lọc nav, giữ giá trị cuối khi lỗi, trang admin (vitest) | `apps/web/src/lib/features.test.tsx`, `features/admin/FeatureFlagsPanel.test.tsx` |
| Chấp nhận | `web_acceptance.mjs` với cấu hình mặc định (không đổi hành vi); thêm kịch bản tắt `rooms.booking` → nav mất, `/rooms` 404, bật lại → có | `scripts/qa/web_acceptance.mjs` |
| Hồi quy | `run_full_regression.py --ci` | — |

## 9. Rủi ro và cách giảm

| Rủi ro | Giảm |
|---|---|
| Gắn sai tiền tố làm tắt nhầm route lõi | Test ma trận và quét route; route lõi nằm ở `CORE_PATHS` riêng |
| Cờ bị lệch giữa worker | Version trong `ff_meta`; kiểm 2 s; test lan truyền |
| Web nhấp nháy menu lúc tải | Mặc định sinh từ registry |
| Tắt tính năng đang có dữ liệu dở (đơn nháp, đặt phòng) | Dữ liệu giữ nguyên; bật lại thấy lại; preview cảnh báo "dữ liệu được giữ" |
| Quá nhiều cờ, khó quản | Nhóm theo `area`; bộ lọc; `depends_on` để tắt cả nhánh bằng một cờ cha |
| Cờ cũ không ai dọn | Registry có trường `introduced` (ngày) và `review_by`; cảnh báo khi qua `review_by` |

## 10. Kế hoạch gói con

| Gói | Nội dung | Cỡ |
|---|---|---|
| F0.1 | `features/registry.py` + domain giải giá trị + test đơn vị | S |
| F0.2 | Sổ cờ đầy đủ §5 + test quét route và trang; chốt ánh xạ chính xác; kiểm lại OIDC bị chặn | M |
| F0.3 | Store SQLite + `FeatureService` + nạp `features.<profile>.toml` + biến môi trường cũ | S |
| F0.4 | Middleware gate (app thường và runtime 8015) + trang proxy + ma trận test | S |
| F0.5 | Job, tool, pipeline RAG đọc cờ; bỏ đọc biến môi trường trực tiếp | S |
| F0.6 | API admin preview/confirm/audit + test | S |
| F0.7 | Web: `FeatureProvider`, nav, `FeatureGate`, trang `/admin/features`, sinh `.generated.ts` | M |
| F0.8 | Quan sát + cảnh báo + `web_acceptance` | S |

Thứ tự: F0.1 → F0.3 → F0.2 → F0.4 → F0.5 → F0.6 → F0.7 → F0.8.
