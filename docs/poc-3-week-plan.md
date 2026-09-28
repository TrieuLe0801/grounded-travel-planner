# Kế hoạch POC 3 tuần

Last updated: 2026-09-28
Delivery window: 2026-09-22 đến 2026-10-12
Status: Active

## 1. Mục tiêu

Trong ba tuần, xây một vertical slice có thể chạy, kiểm thử và demo để chứng
minh LangGraph phù hợp với workflow lập kế hoạch du lịch có state, routing,
clarification, evidence và deterministic validation.

POC không nhằm chứng minh chất lượng của dữ liệu du lịch thật hoặc mức độ sẵn
sàng production. Kết quả cần trả lời được câu hỏi chính:

> Một LangGraph workflow có explicit state và conditional routing có giữ input
> constraints, xử lý thiếu dữ liệu và tạo grounded travel plan dễ kiểm thử hơn
> một luồng tuyến tính đơn giản không?

Giả định thời gian thực hiện là 8–10 giờ mỗi tuần. Nếu thời gian thực tế thấp
hơn, ưu tiên P0 và áp dụng các stop rules ở mục 8.

## 2. Tiến độ tại thời điểm rebaseline

- Focused POC charter đã được chấp nhận; input, output, budget, evidence và
  synthetic-pricing rules đã được chốt.
- Toolchain đã có `pyproject.toml`, `.python-version`, `uv.lock`, pytest, isort,
  Black, flake8, Ruff và hai development-hook tests chạy thành công.
- Chưa có application package, fixture data, application test, executable graph
  hoặc measured metric.
- Roadmap hiện ở 10/53 mục (19%): 6 mục rebaseline và 4 mục tooling/scaffold.
  Tiến độ travel-planner chạy được vẫn là 0% vì các artifact hiện tại chỉ hỗ trợ
  development, chưa triển khai vertical slice.

Các mục Week 0 còn thiếu không còn là điều kiện chặn toàn bộ implementation.
Chỉ những artifact tối thiểu cần cho vertical slice mới được hoàn tất trong ba
tuần; phần còn lại được chuyển sang post-POC backlog.

## 3. Scope POC đã thu gọn

### P0 — bắt buộc

- Một graph duy nhất bằng LangGraph Graph API; không dùng multi-agent.
- Một primary fixture journey: **TP.HCM → Đà Nẵng, 3 ngày**.
- Input có cấu trúc bằng JSON hoặc Python object gồm origin, destination,
  `start_date`, `end_date`, số người và budget tùy chọn.
- Typed state và typed domain models cho request, evidence, plan, validation và
  workflow outcome.
- Fixture tools deterministic cho flight/lodging estimate, places và local
  transport; không gọi live travel API.
- Luồng tối thiểu:

  ```text
  START
    -> normalize_and_validate
    -> clarify hoặc research_fixtures
    -> build_draft
    -> validate_plan
    -> repair tối đa 1 lần nếu có thể sửa
    -> finalize
    -> END
  ```

- Bốn outcome được kiểm thử trong POC: `PLAN_READY`, `NEEDS_CLARIFICATION`,
  `RESEARCH_INCOMPLETE` và `PLAN_UNAVAILABLE`.
- Một recommended plan gồm itinerary theo ngày, một accommodation, danh sách
  food/place recommendations, cost breakdown, fixture/source IDs, assumptions
  và data gaps.
- Budget là hard limit; giá synthetic luôn có nhãn `synthetic_estimate` và
  fixture ID.
- Mọi loop có giới hạn; unit/integration tests không cần network hoặc API key.
- Golden set nhỏ gồm 8 cases tập trung vào route, budget, evidence và
  clarification.
- Một Streamlit page tối thiểu với structured form và result renderer.
- CLI fallback và Streamlit UI cùng gọi một graph/service boundary.
- Demo chạy ít nhất ba đường đi: ready, clarify và unavailable/incomplete.

### P1 — làm sau khi P0 ổn định

- `InMemorySaver` và `interrupt()`/resume cho một clarification flow với
  `thread_id` ổn định.
- Một LangChain tool wrapper hoặc model adapter để thể hiện integration boundary.
- Một optional LLM-backed draft node với structured output; fake/deterministic
  implementation vẫn là acceptance path mặc định.
- Thu latency, node/tool-call count và route accuracy làm baseline, không đặt
  release threshold.

### P2 — stretch, không phải điều kiện hoàn thành

- LangSmith trace/experiment trên dữ liệu synthetic.
- Mermaid/image architecture diagram đẹp hơn cho buổi chia sẻ.
- Một case tiếng Anh ngoài bộ acceptance tiếng Việt chính.

## 4. Ngoài scope và chuyển sang hậu POC

- Multi-agent, specialist subgraphs và so sánh single-agent/multi-agent.
- Long-term memory, LangGraph Store, consent/update/forget workflow.
- Live flight, hotel, weather, maps, routes hoặc availability providers.
- Booking, payment, authentication, tenant isolation và production security.
- Chainlit, FastAPI, multipage UI, custom components/CSS và authentication.
- Postgres checkpointer, restart persistence, TTL và cleanup.
- Docker/Compose và CI/CD; local `uv` workflow là đủ cho POC.
- Full bilingual behavior và natural-language date parsing.
- Accessibility/dietary recommendation và severe-allergy handling.
- Multi-city, iterative replanning sau final plan và durable feedback.
- Dataset 40–60 cases, LLM-as-judge và quality/cost optimization.
- Ba lựa chọn chính cộng alternatives cho mọi nhóm recommendation. POC chỉ cần
  một recommended plan có cấu trúc và evidence rõ ràng.

## 5. Kế hoạch theo tuần

### Tuần 1 — 2026-09-22 đến 2026-09-28: executable vertical slice

**Mục tiêu:** từ repository greenfield đến graph deterministic đầu tiên chạy và
có test.

1. Ghi baseline máy thực tế nếu có thể, nhưng không để thiếu Docker chặn code.
2. Hoàn tất package/data layout và import smoke test trên nền `pyproject.toml`,
   `uv.lock`, pytest, isort, Black, flake8 và Ruff đã có.
3. Tạo typed request/state/outcome models và fixture schema tối thiểu.
4. Tạo fixture journey TP.HCM → Đà Nẵng và 3–5 eval cases đầu tiên.
5. Implement `normalize_and_validate`, router và một graph spike không gọi LLM.
6. Test `PLAN_READY`, `NEEDS_CLARIFICATION`, invalid date và loop limit.

**Exit criteria:** `uv run pytest`, isort/Black/flake8 và Ruff checks chạy thành
công; một input hợp lệ đi từ `START` đến một output có outcome rõ ràng.

### Tuần 2 — 2026-09-29 đến 2026-10-05: grounded planner

**Mục tiêu:** tạo được itinerary fixture-based, có evidence và không vi phạm
budget.

1. Implement provider-independent fixture tools và LangChain tool boundary.
2. Tổng hợp evidence có provenance, freshness/status và structured errors.
3. Implement draft builder; chỉ thêm real model path sau khi deterministic path
   đã xanh.
4. Implement budget, schedule, required-section và citation validators.
5. Cho phép một bounded repair attempt; không tự đoán khi data gap không sửa
   được.
6. Hoàn thiện golden set lên 8 cases và chạy regression.

**Exit criteria:** plan hợp lệ có itinerary/cost/evidence; impossible budget,
unsupported route, tool failure và unsupported claim không tạo `PLAN_READY`
sai.

### Tuần 3 — 2026-10-06 đến 2026-10-12: HITL, evaluation và demo

**Mục tiêu:** đóng gói POC có thể trình bày và nêu rõ giới hạn.

1. Tạo Streamlit page một trang với trip form và bốn outcome renderers.
2. Thêm ít nhất hai Streamlit `AppTest` cases và giữ CLI làm fallback.
3. Thêm `InMemorySaver`/interrupt-resume chỉ khi graph, eval và UI P0 đã xanh.
4. Chạy evaluation, ghi route accuracy, pass/fail, latency và node/tool-call
   count.
5. Fix lỗi P0; không mở rộng chức năng sau ngày 2026-10-09.
6. Rehearse demo từ môi trường local sạch; cập nhật README, result report và
   post-POC backlog.

**Exit criteria:** Streamlit và CLI demo chạy lặp lại được, UI tests/eval có kết
quả lưu trong repo, không có fabricated source/price, và production gaps được
công bố rõ.

## 6. Definition of Done

POC hoàn thành khi tất cả điều kiện P0 sau đạt được:

- Graph compile và chạy end-to-end từ structured input.
- Ít nhất ba đường đi quan sát được: ready, clarify và
  incomplete/unavailable.
- 100% case thiếu required input đi đến clarification thay vì sinh plan.
- Không `PLAN_READY` nào vượt hard budget trong golden set.
- Không claim về giá hoặc nguồn thiếu fixture/source ID.
- Unsupported route hoặc duration không được chuyển thành guessed fixture.
- Research/repair loop kết thúc trong giới hạn cấu hình.
- 8 eval cases chạy offline và có report được commit.
- Các lệnh pytest, isort, Black, flake8 và Ruff chuẩn chạy thành công.
- Streamlit page chạy offline, render đủ outcome và có ít nhất hai `AppTest`
  cases.
- CLI fallback, README, architecture summary, limitations và backlog hậu POC có
  trong repository.

Optional LLM, LangSmith, interrupt/resume, Docker và deployment không nằm trong
Definition of Done.

## 7. Bộ eval tối thiểu

Golden set tập trung vào các failure mode có giá trị trình bày cao:

1. Supported journey có budget đủ → `PLAN_READY`.
2. Supported journey không budget → estimate range có assumptions.
3. Thiếu origin hoặc destination → `NEEDS_CLARIFICATION`.
4. Date range không hợp lệ → `NEEDS_CLARIFICATION`.
5. Route hoặc duration ngoài fixture → `PLAN_UNAVAILABLE`.
6. Impossible budget → `PLAN_UNAVAILABLE`.
7. Fixture/tool timeout hoặc missing data → `RESEARCH_INCOMPLETE`.
8. Evidence stale hoặc conflict → `RESEARCH_INCOMPLETE` hoặc explicit data gap.

Không thêm biến thể nội dung nếu chúng không bao phủ failure mode mới.

## 8. Stop rules và bảo vệ deadline

- Hết ngày 2026-09-25 mà graph chưa chạy: bỏ mọi natural-language parsing và chỉ
  nhận typed JSON.
- Hết ngày 2026-10-02 mà draft path chưa ổn định: dùng deterministic builder làm
  path chính; real model trở thành stretch.
- Hết ngày 2026-10-05 mà 8 cases chưa xanh: UI chỉ gồm form, outcome banner và
  structured-result renderer; không làm chat, visual polish, LangSmith hoặc
  Docker.
- Từ ngày 2026-10-09: feature freeze; chỉ sửa lỗi, chạy eval, viết tài liệu và
  rehearsal.
- Một task P1/P2 không được bắt đầu nếu test P0 đang đỏ.
- Mỗi phiên 90–120 phút phải kết thúc bằng code/test/doc artifact; không tiếp
  tục nghiên cứu mở nếu không gắn với một quyết định hoặc experiment cụ thể.

## 9. Thứ tự post-POC đề xuất

1. Thay fixture bằng một live provider có điều khoản sử dụng phù hợp.
2. Thêm persistent checkpointer và restart/resume.
3. Mở rộng dataset, LangSmith evaluation và observability/privacy controls.
4. Mở rộng multipage UI/API và thêm container/CI.
5. Đánh giá Chainlit nếu conversational clarification trở thành UX chính.
6. Thử long-term memory với consent.
7. Chỉ sau đó mới chạy experiment single-agent so với multi-agent.
