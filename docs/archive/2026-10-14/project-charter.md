# Grounded Travel Planner — Three-Week POC Charter

Last updated: 2026-09-28
Status: Accepted for the three-week POC
Delivery window: 2026-09-22 to 2026-10-12

## 1. Purpose

Xây một POC nhỏ, chạy được và kiểm thử được để chứng minh LangGraph phù hợp với
workflow lập kế hoạch du lịch có:

- typed state;
- conditional routing;
- clarification khi thiếu input;
- fixture-based research;
- deterministic validation;
- bounded repair;
- explicit business outcomes.

POC đánh giá orchestration và testability, không đánh giá độ chính xác của dữ
liệu du lịch thật hoặc mức độ sẵn sàng production.

Kế hoạch thực hiện và stop rules nằm tại `docs/poc-3-week-plan.md`.

## 2. Demo user và journey

POC phục vụ một người dùng đang cần kế hoạch du lịch ngắn ngày và đã biết điểm
đi, điểm đến và ngày đi.

Primary fixture journey duy nhất:

- origin: TP.HCM;
- destination: Đà Nẵng;
- duration: 3 ngày;
- currency: VND;
- data source: deterministic offline fixtures.

Route, duration hoặc destination khác được coi là unsupported trong POC, không
được tự tạo dữ liệu thay thế.

## 3. Research question

> Một LangGraph workflow có explicit state, routing và bounded repair có giúp
> giữ input constraints, xử lý thiếu dữ liệu và tạo grounded plan dễ kiểm thử
> hơn một luồng tuyến tính đơn giản không?

POC không nghiên cứu multi-agent, long-term memory hoặc live-provider quality.

## 4. Feature scope

### 4.1 Structured trip input

- Nhận JSON hoặc Python object; không cần natural-language parsing.
- Validate required fields và date range.
- Áp dụng traveler defaults có công bố trong assumptions.
- Route input thiếu hoặc không hợp lệ đến `NEEDS_CLARIFICATION`.

### 4.2 Fixture research tools

- Offline fixtures cho flight estimate, lodging, places và local transport.
- Tool results có typed schema, fixture/source ID và status.
- Có fixture mô phỏng missing data, timeout và conflicting evidence.
- Unit và integration tests không cần network hoặc API key.

### 4.3 Recommended plan

- Tạo đúng một recommended plan cho journey được hỗ trợ.
- Có itinerary theo ngày.
- Có một accommodation recommendation.
- Có food/place recommendations.
- Có total-trip cost breakdown.
- Có assumptions, source IDs và data gaps.

POC không tạo ba lựa chọn cộng alternatives cho từng nhóm recommendation.

### 4.4 Budget validation

- Budget, nếu được cung cấp, là hard limit cho toàn bộ chuyến đi.
- Total cost gồm flight, lodging, food, local transport và activities.
- Plan vượt budget không được trả `PLAN_READY`.
- Nếu không có budget, output trả một synthetic estimate range kèm assumptions.

### 4.5 Evidence and citation validation

- Mọi giá synthetic có `synthetic_estimate` label và fixture ID.
- Itinerary item hoặc cost claim cần reference đến fixture/source ID phù hợp.
- Missing, stale hoặc conflicting evidence không được trình bày như fact chắc
  chắn.
- Không tạo source URL, availability hoặc price ngoài fixture.

### 4.6 LangGraph orchestration

Graph tối thiểu:

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

Mọi loop phải có giới hạn. Graph cần expose state transitions đủ để test node,
router và outcome.

### 4.7 CLI demo

CLI hoặc demo script phải chạy được ít nhất ba flow:

1. valid input → `PLAN_READY`;
2. missing input → `NEEDS_CLARIFICATION`;
3. impossible budget hoặc research failure →
   `PLAN_UNAVAILABLE`/`RESEARCH_INCOMPLETE`.

### 4.8 Minimal Streamlit UI

- Một trang duy nhất với structured trip form.
- Submit form tạo typed request và gọi cùng LangGraph workflow dùng bởi CLI.
- Render outcome, itinerary, cost, fixture/source IDs và data gaps.
- Dùng Session State chỉ cho request/result hiện tại; không coi là persistence.
- Có ít nhất hai headless UI checks bằng Streamlit `AppTest`.

UI không chứa bản sao của date, budget, evidence hoặc routing rules.

### 4.9 Offline evaluation

- Một versioned JSONL golden set gồm 8 cases.
- Một deterministic eval runner.
- Report per-case outcome và invariant pass/fail.
- Ghi latency và node/tool-call count làm baseline nếu implementation cho phép.

## 5. Optional features after P0 is stable

P1, không phải Definition of Done:

- `InMemorySaver` và một `interrupt()`/resume clarification flow;
- một LangChain tool wrapper hoặc model adapter;
- một optional LLM-backed draft node với structured output.

P2 stretch:

- một synthetic-data LangSmith trace spike.

Deterministic offline flow luôn là acceptance path mặc định.

## 6. Input contract

### Required

| Field | Rule |
|---|---|
| `origin` | Bắt buộc; POC chỉ hỗ trợ TP.HCM |
| `destination` | Bắt buộc; POC chỉ hỗ trợ Đà Nẵng |
| `start_date` | ISO `YYYY-MM-DD` |
| `end_date` | ISO `YYYY-MM-DD`; không sớm hơn `start_date` |

### Optional/defaulted

| Field | Rule |
|---|---|
| `adult_count` | Default `1` |
| `child_count` | Default `0` |
| `budget_vnd` | Optional hard limit; phải lớn hơn `0` nếu có |

POC không thu thập tuổi trẻ em, passport, payment data, medical information,
profile hoặc long-term preferences.

## 7. Output contract

Mọi execution trả structured result gồm:

- `outcome`;
- normalized trip summary;
- assumptions;
- itinerary theo ngày nếu có;
- accommodation và food/place recommendations nếu có;
- cost breakdown và total/range estimate;
- fixture/source IDs;
- validation errors hoặc data gaps.

`PLAN_READY` chỉ hợp lệ khi itinerary, recommendation, cost và evidence sections
đều có mặt và deterministic validators đã pass.

## 8. Workflow outcomes

POC chỉ triển khai bốn outcome:

- `PLAN_READY`: input, fixture evidence và plan đều hợp lệ.
- `NEEDS_CLARIFICATION`: thiếu required input hoặc date/budget không hợp lệ.
- `RESEARCH_INCOMPLETE`: fixture tool lỗi hoặc evidence thiếu/mâu thuẫn.
- `PLAN_UNAVAILABLE`: route/duration không được hỗ trợ hoặc hard budget không
  thể đáp ứng.

Không thêm outcome mới trong delivery window nếu chưa cập nhật charter, tests và
golden set.

## 9. Product invariants

- Không fabricate source, price, availability hoặc tool result.
- Synthetic price luôn có label và fixture ID.
- `PLAN_READY` không được vượt hard budget.
- Missing/conflicting evidence không được chuyển thành guessed fact.
- Unsupported route hoặc feature phải trả outcome rõ ràng.
- Research/repair attempts luôn bounded.
- Tests mặc định không gọi network hoặc model thật.

## 10. Acceptance scenarios

Golden set tối thiểu gồm đúng 8 nhóm case:

1. Supported journey có budget đủ → `PLAN_READY`.
2. Supported journey không có budget → `PLAN_READY` với estimate range và
   assumptions.
3. Thiếu origin hoặc destination → `NEEDS_CLARIFICATION`.
4. Date range không hợp lệ → `NEEDS_CLARIFICATION`.
5. Route hoặc duration ngoài fixture → `PLAN_UNAVAILABLE`.
6. Budget không thể đáp ứng → `PLAN_UNAVAILABLE`.
7. Fixture tool timeout/missing data → `RESEARCH_INCOMPLETE`.
8. Evidence stale/conflicting → `RESEARCH_INCOMPLETE` hoặc output nêu data gap,
   không khẳng định như fact.

Mỗi case có input, expected outcome và expected invariants. Không thêm biến thể
nội dung nếu không bao phủ failure mode mới.

## 11. Definition of Done

POC hoàn thành khi:

- LangGraph compile và chạy end-to-end từ structured input.
- Bốn workflow outcomes có test coverage phù hợp.
- Valid journey tạo được một recommended plan đúng output contract.
- Không `PLAN_READY` nào vượt hard budget.
- Không price/source claim nào thiếu fixture/source ID.
- Repair loop kết thúc sau tối đa một attempt.
- 8 golden cases chạy offline và có report trong repository.
- Các lệnh pytest, isort, Black, flake8 và Ruff chuẩn chạy thành công.
- CLI/demo script chạy được ba flow đã định nghĩa.
- Streamlit page chạy offline, render đủ bốn outcome và có ít nhất hai
  `AppTest` cases.
- README có lệnh chạy, limitations và post-POC backlog.

Optional LLM, LangSmith, interrupt/resume, Docker và deployment không phải điều
kiện hoàn thành.

## 12. Explicit non-goals and post-POC backlog

- Natural-language input parsing và full bilingual behavior.
- Route khác, multi-city hoặc trip duration khác fixture.
- Live flight, hotel, weather, maps, routes hoặc availability providers.
- Booking, payment, authentication, tenant isolation và production security.
- Accessibility/dietary recommendation và severe-allergy handling.
- Long-term memory, user profile, consent/update/forget và durable feedback.
- Multi-agent hoặc specialist subgraphs.
- Incremental replanning sau final output.
- Chainlit, FastAPI, multipage UI, custom components/CSS, authentication,
  Docker/Compose, CI/CD và deployment.
- Persistent checkpointer, process-restart resume, TTL và cleanup.
- Dataset lớn, LLM-as-judge và quality/cost optimization.

Các mục này không được thêm vào POC chỉ vì còn thời gian ở một phiên. Chỉ xem
xét sau khi toàn bộ P0 Definition of Done đã đạt và thay đổi đã được ghi bằng
ADR.

## 13. Data and safety boundaries

- Fixtures và eval data phải synthetic hoặc sanitized.
- Secrets chỉ nằm trong ignored environment files.
- Không commit credentials hoặc raw personal data.
- POC không tuyên bố giá/availability thật và không thay thế kiểm tra trực tiếp
  với nhà cung cấp.

## 14. Change control

Charter phải được review lại nếu thay đổi một trong các quyết định sau:

- thêm live provider hoặc route mới;
- tăng golden set ngoài 8 failure-mode groups;
- thêm persistent storage, API, multipage/custom UI hoặc deployment;
- thay Streamlit bằng Chainlit hoặc thêm chat-first interaction;
- đưa accessibility/dietary, memory hoặc multi-agent vào POC;
- biến optional model/LangSmith path thành release gate;
- thay đổi deadline hoặc Definition of Done.
