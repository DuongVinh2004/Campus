# Stitch — Mở rộng giao diện Campus 24/7 từ bản đã chọn

Ngày: 15/10/2026. Mục tiêu: thiết kế các màn hình còn lại theo đúng bố cục, phong cách và hệ component của hai màn hình tổng quan đã chọn. Tập trung vào UX/UI, không dành vòng chỉnh để sửa câu chữ.

## Cách dùng

Trong cùng dự án Stitch, chọn/đính kèm màn hình tổng quan desktop và mobile hiện tại làm reference. Dán khối 00 một lần, sau đó chạy lần lượt từng prompt 01–08. Mỗi lần chỉ chạy một nhóm; xem và chỉnh nhóm đó trước khi chuyển tiếp. Nếu đổi chat/dự án, gửi lại reference và khối 00.

Hai gói đã đọc:
- Desktop: `stitch_campus_24_7_huce_portal.zip` — screen.png 1600×1280.
- Mobile: `stitch_campus_24_7_huce_portal (1).zip` — screen.png 442×1600.
- Cả hai có code.html và DESIGN.md.

Ưu tiên màn hình đã chọn và style thực tế trong HTML. DESIGN.md xuất kèm có một số token/mô tả không khớp HTML: primary trong frontmatter khác màu hiển thị, mô tả sidebar 260px trong khi HTML desktop dùng 244px, radius cũng khác. Không để các giá trị đó tự tạo một hướng thiết kế mới.

Các prompt chỉ yêu cầu thiết kế; không upload code riêng, thực hiện nghiệp vụ, hay sửa source FE. Nội dung mẫu chỉ giúp thể hiện hierarchy và trạng thái, không phải yêu cầu bổ sung chức năng backend.

## 00 — Quy tắc chung: dán một lần

```text
We are extending the selected Campus 24/7 HUCE student overview designs into a complete application.

Use BOTH selected overview screens as the visual reference. Preserve their identity; do not redesign the overview or introduce alternative styles.

Keep the same desktop sidebar, compact toolbar, mobile header, primary bottom navigation, brand mark, icon style, typography, card language, borders and button treatments. Change only the active destination for each new screen. Staff/admin may use role-appropriate navigation within the same shell design.

Visual anchors: canvas #F6F7F9, white surfaces, primary teal #155E63, ink #182C3A, supporting text #526371, restrained pale-teal emphasis, Inter with Vietnamese support. Match the actual reference for proportions and corner radii. If attached DESIGN.md conflicts with the selected screens, follow the selected screens.

Focus on layout, hierarchy, task flow, interaction affordances and responsive composition. Use natural Vietnamese sample content without spending iterations rewriting copy. Do not invent integrations or additional product modules.

Use one clear primary action per task context. Avoid card-within-card nesting, excessive dividers, large empty panels and unnecessary badges. Keep controls and information close to the action they support.

Desktop and mobile must be intentionally recomposed. Design at 1440px and 390px; respect safe areas. Keep primary touch targets at least 44px, visible keyboard focus, readable text and long-label wrapping. Only data tables/code may scroll horizontally within their own container.

Maintain one global navigation. Additional chat history, filters or supporting details should use contextual panels/drawers where appropriate, rather than stacking permanent sidebars.

Use enough fictional sample data to demonstrate the layout, marked as prototype data. Design the relevant empty/loading/error/selected/disabled states as compact component variants or annotations; do not multiply every state into a full page.

Generate only the requested group. Reuse established components. Output named screens, shared-component references and brief interaction annotations. Do not generate production code at this stage.
```

## 01 — Trợ lý học vụ

```text
Continue with the established Campus 24/7 reference and shared design rules.
Design the academic assistant workspace. Keep “Trợ lý” active.

Create FOUR screens: desktop welcome, mobile welcome, desktop active conversation, mobile active conversation.

Welcome: a calm introduction, four compact suggested-task cards and a prominent question composer. Keep the usable workspace spacious without a marketing hero.

Conversation: distinguish user and assistant messages through alignment and surface treatment, with comfortable reading width. Show a realistic long response, a short structured list and source-reference chips. Group secondary response actions discreetly below the response.

Keep the composer anchored to the conversation area. It grows for longer questions, provides a clear send/stop action and remains reachable with the mobile keyboard open. Reserve space so navigation and the composer never cover each other.

Conversation history opens from one contextual control. Avoid a second permanently expanded sidebar beside global navigation. Source details open in a desktop side panel and a mobile sheet; annotate these overlays on the active-conversation screens without generating extra full pages.

Include compact composer focus/filled/sending/error variants and source-chip selected treatment. Prioritize conversation readability and clear interactions; preserve the reference visual identity.
```

## 02 — Danh mục dịch vụ và điền yêu cầu

```text
Continue the same Campus 24/7 design system. Keep “Dịch vụ” active.

Create FOUR screens: desktop service directory, mobile service directory, desktop request form, mobile request form.

Directory: a clear page header, compact search/category controls, and service cards using the same visual grammar as the overview. Use the existing service families: certificate requests, grade appeals and general support. Each card is one accessible target with a clear action and short supporting information. Avoid a dense wall of equal-weight text or decorative icons.

Form: design a certificate-request example. Group fields into meaningful sections: request details, delivery choice and attachments. Keep labels visible, helper/error text directly related to fields and primary actions easy to find. Use two columns only for short related fields; long inputs remain full width. Keep main form reading width comfortable.

A concise supporting summary may sit beside the form on desktop and collapse into a disclosure on mobile. Use two task stages only: fill in information and review. Place “Lưu bản nháp” as secondary and “Xem trước” as primary. Do not imply the form is submitted at this point.

Annotate selected options, a field error, attachment progress and disabled/submitting controls. Preserve draft visibility. Focus on composition, clear form rhythm and mobile ergonomics.
```

## 03 — Hồ sơ, chi tiết và xem trước

```text
Continue the selected Campus 24/7 visual language. Keep “Hồ sơ” active.

Create FOUR screens: desktop request list, mobile request list, desktop request detail, mobile request detail.

List: page header with one primary create-request action, search and compact status filters. On desktop use a readable table/list with aligned request identity, service, status, last update and open action. Clearly show one selected row. On mobile recompose each record into a concise card with consistent label/value hierarchy; do not shrink the desktop table.

Detail: a clear back path, request identity, prominent status, task-specific next action, grouped submitted information, attachments and progress/activity timeline. Desktop may use main content plus a quieter summary rail. Mobile prioritizes status and next action, with supporting detail progressively disclosed.

Demonstrate a “needs additional information” state to show a useful action hierarchy. Keep the timeline lightweight, rather than turning every event into a separate large card.

Also annotate the review-and-confirm composition reached from the request form: readable grouped summary, edit links, secondary back action and explicit final confirmation. Use a comfortable desktop modal/page region and full-height mobile sheet as space requires. Do not create an additional visual language for this step.

Provide compact empty/no-results and confirmation-loading variants. Keep actions close to the relevant information.
```

## 04 — Bàn làm việc cán bộ

```text
Extend Campus 24/7 into a staff workspace using the SAME brand, surfaces, typography and controls. Change navigation destinations to the staff role while retaining the shell geometry.

Create THREE screens: desktop staff queue, desktop case review, mobile case review.

Queue: prioritize quick scanning with search, restrained status/assignment filters and a table with well-aligned identity, request type, priority, owner and status. Use modest density, tabular figures and subtle row selection. Avoid decorative KPI dashboards and excessive colored badges.

Case review: establish a strong working hierarchy. Main region contains the dossier and attachments; a secondary region contains review steps and the current decision controls. Use collapsible supporting sections instead of overwhelming the page with every panel at once. Distinguish internal notes from student-facing communication visually.

Keep the primary next action easy to reach. Place consequential decision controls in a deliberate action area with a clear preview/confirmation treatment; prevent accidental proximity to navigation controls.

Mobile: prioritize case identity, status and current action. Convert secondary panels into accessible disclosures/sheets. Avoid forcing multiple narrow columns or copying the desktop density.

Annotate claimed/selected row, busy action and validation states. Preserve the calm teal identity; make this a focused working environment rather than another overview dashboard.
```

## 05 — Lịch học và phòng học

```text
Continue the established Campus 24/7 system.

Create FOUR screens: desktop schedule, mobile schedule, desktop room search, mobile room search. Set the correct active navigation destination for each.

Schedule: a compact date/week toolbar, a clear today action and restrained view switching. Desktop uses a legible weekly timetable with a stable time axis and restrained event colors. Mobile uses a selected-day agenda with a compact date strip; do not compress seven calendar columns into the phone width. An event exposes details in a contextual popover/sheet.

Room search: place date/time and essential filters in a clear search region. Results show room identity, capacity, relevant facilities and availability as readable structured rows/cards. Maintain alignment and one clear contextual action. On mobile collapse secondary filters into a sheet and keep selected filters visible.

Do not introduce a campus map or navigation module. Use marked prototype records solely to demonstrate the UI. If an action is unavailable, show a designed disabled/unavailable variant rather than an apparently functional control.

Annotate selected date/event, active filters, no-results and loading variants. Keep the shared shell and component styling unchanged. Prioritize readable calendar geometry, filter usability and clear visual states.
```

## 06 — Đăng nhập và thông báo

```text
Use the established Campus 24/7 identity and shared components.

Create FOUR screens: desktop login, mobile login, desktop notification center, mobile notification center.

Login: an uncluttered entry experience. Desktop may pair a restrained branded panel with a focused form; mobile centers the task without large decorative artwork. Use the existing account/password form structure, visible labels, password visibility control, accessible errors and clear submit/loading states. Keep help and return navigation secondary. Use the same buttons, field styling and typography as the application; no new gradient-heavy theme.

Notifications: retain the regular application shell with “Thông báo” active. Use a readable list grouped by recency, compact read/unread filters, a clear unread indicator and a consistent relationship between icon, title, preview, time and destination. A notification should be one coherent open target; secondary actions stay visually secondary.

Mobile must support long titles without clipping and avoid tiny action targets. Empty and loading states should be compact and useful, rather than oversized illustrated cards.

Annotate login focus/error/busy states and notification unread/selected states. Concentrate on visual consistency, spacing and effortless interaction, not additional account or notification features.
```

## 07 — Quyền riêng tư và ghi nhớ cá nhân

```text
Continue the same Campus 24/7 design system.

Create FOUR screens: desktop privacy/settings, mobile privacy/settings, desktop personal-memory list, mobile personal-memory list.

Settings: a clear page header and well-spaced groups of label, brief explanation and control. Distinguish section navigation from actual settings. Avoid putting every setting into a separately elevated card. Use consistent alignment, visible toggle states and a clear relationship between a changed setting and its save/confirmation controls.

Memory: a manageable list of saved items with a compact search/filter region. Show item content, category and recency with clear hierarchy. Keep edit and forget controls discoverable but visually secondary. Longer content expands without breaking the list layout. Use contextual confirmation for consequential actions.

On mobile, convert side navigation into a compact section selector if needed; keep settings controls comfortably reachable. Do not use several permanent sidebars or squeeze desktop label/control columns into the phone width.

Annotate saving/saved/error, expanded memory item and edit/confirmation sheet variants. Preserve existing feature meanings. Treat the labels as sample copy; prioritize grouped layout, interaction clarity and visual consistency.
```

## 08 — Quản lý tri thức và quản trị

```text
Extend the same Campus 24/7 visual system into knowledge administration. Keep role-appropriate navigation within the established shell.

Create FOUR screens: desktop knowledge-source list, desktop source review, desktop administration/settings, mobile source review.

Source list: readable table/list with compact search and status/version filters. Align source identity, owner, version, state and update information. Use subtle selection and an obvious open action. Do not turn metadata into a wall of badges.

Source review: main document/evidence area plus a contextual metadata/review region. Use clear source title, version selector, locator/reference treatment and grouped review controls. Dense technical details belong in expandable sections. Where a relationship/graph view is available, keep it inside a bounded tab or workspace with zoom/fit controls, not overflowing the page.

Administration: use structured settings sections and a concise secondary section navigator. Avoid invented analytics, billing, personnel management or unrelated modules. Keep controls aligned and primary actions specific to the current section.

Mobile review: a focused reading layout with supporting metadata and review controls in disclosures/sheets. Maintain legible references and comfortable controls.

Annotate selected source/version, review pending and preview/confirmation states. Reuse existing component styles and preserve the same calm academic identity.
```

## Prompt sửa sau khi review — dùng lại cho từng nhóm

```text
Refine ONLY the selected screens in this group. Preserve the established Campus 24/7 design system and all already-approved layouts.

Address these visual/interaction findings:
1. [screen and region]: [observed layout issue] → [required composition or interaction].
2. [screen and region]: [observed hierarchy/spacing issue] → [required correction].
3. [mobile component]: [observed usability issue] → [required correction].

Do not rewrite copy, invent functionality, regenerate the overview or introduce alternative concepts. Return the corrected screens at readable scale and reuse the same shared components.
```

## Bàn giao sang Antigravity khi thiết kế đã ổn

Xuất ảnh và HTML từng màn hình cùng DESIGN.md, đặt tên theo nhóm và viewport. Giữ bản xuất gốc để đối chiếu. Antigravity cần nhận ảnh chuẩn + tokens đã thống nhất + tương tác/state annotations; không chỉ nhận HTML rồi thay toàn bộ ứng dụng bằng static markup.

Khi tích hợp, giữ business logic và các variant hiện có. Ưu tiên style thực tế của bộ Stitch đã chọn nếu khác với bản nháp apps/web/DESIGN.md trước đó; cập nhật có chọn lọc, không tạo hai design system song song.
