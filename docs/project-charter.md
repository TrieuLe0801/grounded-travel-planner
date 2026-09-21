# Grounded Travel Planner — Project Charter

Last updated: 2026-09-21  
Status: Accepted for MVP  
Approved date: 2026-09-21

## 1. Product vision

Grounded Travel Planner là một trợ lý lập kế hoạch du lịch dành cho người Việt
Nam và khách nước ngoài. Hệ thống giúp người dùng khám phá những điểm tham quan,
trải nghiệm, khu vực lưu trú và địa điểm ăn uống tại điểm đến mà họ đã lựa chọn.

Hệ thống không chỉ sinh một danh sách gợi ý. Mỗi kế hoạch cần phù hợp với thời
gian và ngân sách của người dùng, có chi phí ước tính, nêu rõ những thông tin còn
thiếu và dẫn nguồn cho các thông tin quan trọng.

## 2. Problem statement

Người dùng đã có ý định đi du lịch nhưng gặp khó khăn vì:

- không biết tại điểm đến có những địa điểm hoặc trải nghiệm nào phù hợp;
- không biết nên lưu trú ở khu vực nào;
- không biết nên ăn uống ở đâu;
- phải tự tổng hợp thông tin từ nhiều nguồn có độ mới và độ tin cậy khác nhau;
- khó ghép các gợi ý riêng lẻ thành một lịch trình theo ngày;
- khó ước tính tổng chi phí của chuyến đi;
- có thể không nhận ra thông tin nào còn thiếu hoặc chưa được kiểm chứng.

## 3. Target users

### Primary users

- Người Việt Nam đang lên kế hoạch cho chuyến đi trong nước hoặc quốc tế.
- Khách nước ngoài đang lên kế hoạch tham quan một điểm đến.
- Người dùng đã xác định được điểm xuất phát và điểm đến nhưng chưa biết nên
  tham quan, trải nghiệm, lưu trú và ăn uống như thế nào.

### Supported languages

- Tiếng Việt.
- Tiếng Anh.

Ngôn ngữ trả lời mặc định theo ngôn ngữ người dùng sử dụng. Việc nguồn tham khảo
có thể dùng ngôn ngữ khác với ngôn ngữ trả lời cần được xử lý ở tầng tổng hợp,
không được làm mất thông tin về nguồn gốc của evidence.

## 4. Interaction model

MVP sử dụng mô hình **clarify-then-generate**:

1. Người dùng cung cấp thông tin chuyến đi.
2. Hệ thống hỏi bổ sung nếu thiếu thông tin bắt buộc hoặc có constraint mơ hồ.
3. Sau khi đủ dữ liệu, hệ thống tạo một kế hoạch hoàn chỉnh.
4. Người dùng sử dụng kế hoạch làm cơ sở thực hiện chuyến đi.
5. Nếu có thể, người dùng cung cấp phản hồi sau khi nhận hoặc trải nghiệm lịch
   trình.

MVP không tập trung vào việc chỉnh sửa kế hoạch qua nhiều vòng sau khi kế hoạch
hoàn chỉnh đã được tạo. Clarification trước khi tạo kế hoạch vẫn nằm trong phạm
vi bắt buộc.

## 5. Primary use case

Người dùng nhập điểm xuất phát, điểm đến, ngày đi và ngân sách nếu có. Hệ thống:

1. kiểm tra thông tin bắt buộc và các hard constraints;
2. hỏi lại nếu dữ liệu chưa đủ;
3. nghiên cứu điểm tham quan, trải nghiệm, lưu trú và ăn uống;
4. kiểm tra nguồn, độ mới, xung đột và mức độ đầy đủ của evidence;
5. tạo kế hoạch theo ngày;
6. tính chi phí ước tính;
7. cung cấp nguồn kiểm chứng và danh sách thông tin còn thiếu.

## 6. Input contract

### Required inputs đã được xác nhận

#### Điểm xuất phát

- Thành phố hoặc sân bay xuất phát.
- Được sử dụng để tìm phương án di chuyển và ước tính chi phí vé máy bay.

#### Điểm đến

- Thành phố, khu vực hoặc điểm du lịch người dùng muốn đến.
- Agent không tự chọn điểm đến trong MVP.
- Agent được phép đề xuất điểm tham quan, trải nghiệm, nơi lưu trú và chỗ ăn tại
  điểm đến đã được người dùng cung cấp.

#### Khoảng ngày đi

- Người dùng cung cấp một khoảng ngày cố định, ví dụ: `2026-09-04` đến
  `2026-09-06`.
- Hệ thống không tự động thay đổi khoảng ngày để tối ưu giá trong MVP.
- Input cần được chuẩn hóa thành `start_date` và `end_date` theo chuẩn ISO
  `YYYY-MM-DD` trước khi research hoặc planning.
- Chuẩn ISO được sử dụng thống nhất cho cả tiếng Việt và tiếng Anh.
- Nếu người dùng không cung cấp năm, hệ thống tự động điền năm hiện tại lấy từ
  runtime clock, sau đó chuẩn hóa thành ISO date.
- Việc tự động điền năm phải xuất hiện trong assumptions của output.
- Input không theo ISO nhưng có thể hiểu theo nhiều cách phải được clarification;
  hệ thống không được đoán theo ngôn ngữ hoặc locale.
- Hệ thống không tự động chuyển một khoảng ngày đã qua sang năm tiếp theo.
- Nếu `end_date` sớm hơn `start_date`, input không hợp lệ và phải được hỏi lại.

#### Số người

- Hệ thống phân biệt `adult_count` và `child_count`.
- Nếu người dùng không đề cập số người, hệ thống mặc định:
  `adult_count = 1` và `child_count = 0`.
- Default này phải xuất hiện trong phần assumptions của output.
- MVP chỉ thu thập số lượng người lớn và số lượng trẻ em; không hỏi tuổi hoặc age
  band của trẻ.
- Synthetic pricing fixtures của MVP chỉ được phép sử dụng hai count này, không
  được tự suy luận tuổi của trẻ.
- Tổng ngân sách và mọi cost estimate phải áp dụng cho toàn bộ nhóm.

### Optional input đã được xác nhận

#### Tổng ngân sách

- Budget là hard limit cho toàn bộ chuyến đi.
- Hard limit bao gồm vé máy bay, lưu trú, ăn uống, di chuyển tại điểm đến, vé
  tham quan và các hoạt động được đưa vào itinerary.
- Nếu người dùng cung cấp budget, recommended plan không được vượt hard limit.
- Nếu người dùng không cung cấp budget, agent phải đề xuất một khoảng ngân sách
  `min_estimate`–`max_estimate` và giải thích cơ sở của khoảng này.
- Khoảng ngân sách phải nêu assumptions và cost breakdown thay vì chỉ đưa ra hai
  con số tổng.
- Giá chỉ là ước tính tại thời điểm thu thập, không phải cam kết đặt chỗ hoặc
  availability.

#### MVP pricing source

- MVP sử dụng deterministic synthetic fixtures để tạo flight và lodging
  estimates.
- Synthetic estimates chỉ dùng cho development, evaluation và demonstration.
- Output phải gắn nhãn `synthetic_estimate` và không được trình bày như live
  market price.
- Live flight, lodging và availability providers được hoãn sang giai đoạn sau
  MVP.

### Conditional inputs

Các thông tin dưới đây cần được hỏi khi có liên quan:

- accessibility requirements;
- dietary preferences và non-severe restrictions;
- fixed bookings hoặc fixed commitments;
- must-have và must-avoid;
- giới hạn đi bộ hoặc thời gian hoạt động mỗi ngày;
- yêu cầu bắt buộc về nơi lưu trú;
- yêu cầu về phương tiện di chuyển.

Accessibility và dietary questions chỉ được mở rộng khi người dùng cho biết có
nhu cầu liên quan; hệ thống không bắt mọi người dùng hoàn thành một form chi tiết.

### Hard-constraint policy

- Hard constraint không được âm thầm chuyển thành soft preference.
- Hard constraints phải được áp dụng từ research-result selection, planning đến
  final validation.
- Trạng thái `UNKNOWN` không được xem là đã đáp ứng accessibility hoặc dietary
  constraint.
- Severe allergy handling không nằm trong khả năng lập recommendation của MVP.
  Khi người dùng khai báo severe allergy, hệ thống phải nêu rõ giới hạn, không
  đưa ra tuyên bố an toàn và yêu cầu người dùng xác nhận trực tiếp với venue.
- Accessibility và dietary restrictions mặc định chỉ nằm trong trip state hiện
  tại. Ghi vào long-term memory cần explicit consent.
- Yêu cầu hiện tại luôn được ưu tiên hơn profile đã lưu.
- Evidence cho accessibility và dietary constraints được ưu tiên theo thứ tự:
  website chính thức của venue, structured provider có provenance, cơ quan du
  lịch/chính quyền, rồi mới đến nguồn thứ ba đáng tin cậy.
- Blog hoặc review không được dùng độc lập để xác nhận một hard constraint.

## 7. Output contract

Mỗi kết quả cần có các phần sau.

### Trip summary

- Điểm xuất phát.
- Điểm đến.
- Khoảng thời gian chuyến đi.
- Các assumptions chính.
- Ngôn ngữ kế hoạch.

### Day-by-day plan

Mỗi ngày cần có:

- các điểm tham quan hoặc trải nghiệm được đề xuất;
- thứ tự và thời gian dự kiến;
- khu vực hoặc địa chỉ;
- thời gian di chuyển ước tính khi có dữ liệu;
- chi phí ước tính;
- nguồn thông tin liên quan;
- cảnh báo nếu thông tin chưa được xác nhận.

Attractions được chọn dựa trên schedule feasibility, travel time, budget và hard
constraints. Những địa điểm phù hợp nhưng không thể xếp vào lịch được đưa vào
phần alternatives.

### Accommodation recommendation

- Khu vực nên lưu trú.
- Ba lựa chọn chính và tối đa hai lựa chọn thay thế khi có đủ evidence.
- Mỗi nơi cần có tên, địa chỉ hoặc khu vực, loại hình lưu trú và lý do phù hợp
  với itinerary.
- Hệ thống chọn đúng một lựa chọn lưu trú chính cho recommended plan.
- Giá ước tính và thời điểm lấy dữ liệu.
- Lý do phương án phù hợp với lịch trình.
- Trong MVP, không khẳng định còn phòng vì live availability provider chưa nằm
  trong phạm vi.

### Food recommendation

- Ba lựa chọn chính và tối đa hai lựa chọn thay thế.
- Mỗi nơi cần có tên, khu vực hoặc địa chỉ và lý do được đề xuất.
- Loại món ăn hoặc trải nghiệm ẩm thực.
- Giá ước tính khi có dữ liệu.
- Hệ thống gợi ý địa điểm ăn uống; MVP không bắt buộc gán từng địa điểm thành
  bữa sáng, bữa trưa hoặc bữa tối cụ thể trong itinerary.
- Dietary verification status khi có non-severe constraint liên quan.
- Severe allergy không nằm trong MVP; hệ thống không được khẳng định một địa điểm
  an toàn và phải khuyến nghị người dùng xác nhận trực tiếp với venue.

### Estimated cost

Nếu người dùng cung cấp budget:

- budget được xem là hard limit cho toàn bộ chuyến đi;
- recommended plan phải có tổng estimate không vượt hard limit;
- nếu không thể đáp ứng, hệ thống phải đề nghị nới constraint hoặc thay đổi plan.

Nếu người dùng không cung cấp budget, output cần có một khoảng budget đề xuất:

```text
min_estimate ≤ recommended total cost ≤ max_estimate
```

Khoảng estimate phải được tạo từ deterministic synthetic fixtures và được gắn
nhãn rõ ràng. Agent phải giải thích cơ sở của khoảng estimate. Cost breakdown
cần tách tối thiểu:

- vé máy bay;
- nơi lưu trú;
- ăn uống;
- di chuyển tại điểm đến;
- vé tham quan và hoạt động;
- contingency nếu áp dụng;
- tổng chi phí;
- assumptions và thời điểm lấy dữ liệu.

### Sources

- Material claims phải có source ID hoặc URL.
- Dynamic facts cần có `retrieved_at`.
- Synthetic flight/lodging prices phải có fixture ID và nhãn
  `synthetic_estimate`; chúng không được gắn URL giả.
- Các nguồn mâu thuẫn phải được nêu rõ, không được tự chọn một nguồn mà không có
  lý do.
- Không tạo nguồn hoặc URL không tồn tại.

### Missing information

Kết quả phải có một danh sách riêng cho:

- input người dùng chưa cung cấp;
- evidence không tìm thấy;
- thông tin không thể xác nhận;
- dữ liệu có thể đã stale;
- assumption mà agent buộc phải sử dụng.

Danh sách này vẫn phải xuất hiện khi hệ thống tạo được itinerary.

## 8. Workflow outcomes

LangGraph workflow cần trả về trạng thái nghiệp vụ rõ ràng:

- `PLAN_READY`: đã có đủ input và dữ liệu để trả kế hoạch hoàn chỉnh.
- `NEEDS_CLARIFICATION`: thiếu input bắt buộc hoặc constraint mơ hồ.
- `RESEARCH_INCOMPLETE`: một phần dữ liệu bên ngoài thiếu, lỗi hoặc chưa xác minh;
  hệ thống có thể trả partial result kèm data gaps.
- `NEEDS_USER_DECISION`: có các phương án hoặc nguồn mâu thuẫn mà người dùng cần
  lựa chọn.
- `PLAN_UNAVAILABLE`: không thể tạo kế hoạch hữu ích trong constraint hiện tại.

Đây là workflow outcomes riêng của Travel Planner.

## 9. MVP scope

- Một điểm đến do người dùng cung cấp.
- Một điểm xuất phát do người dùng cung cấp.
- Khoảng ngày đi cố định với ngày bắt đầu và ngày kết thúc.
- Phân biệt người lớn và trẻ em.
- Mặc định một người lớn, không có trẻ em nếu traveler information không được
  cung cấp.
- Kế hoạch theo ngày.
- Ba lựa chọn chính và tối đa hai alternatives cho mỗi nhóm recommendation khi
  đủ evidence.
- Attractions được xếp lịch theo schedule feasibility; những điểm còn lại nằm
  trong alternatives.
- Một lựa chọn lưu trú chính được sử dụng trong recommended plan.
- Các nơi ăn được gợi ý như địa điểm; không bắt buộc gán vào từng bữa ăn.
- Hard budget limit cho toàn bộ chuyến đi nếu người dùng cung cấp budget.
- Một khoảng budget đề xuất nếu người dùng không cung cấp budget.
- Tiếng Việt và tiếng Anh.
- Clarification trước khi tạo kế hoạch.
- Citation và danh sách missing information.
- Offline fixtures để kiểm thử deterministic.
- Deterministic synthetic flight/lodging pricing fixtures cho MVP.
- Optional feedback sau khi kế hoạch được tạo hoặc chuyến đi kết thúc.

## 10. Non-goals

- Không tự chọn điểm đến thay người dùng trong MVP.
- Không chỉnh sửa kế hoạch qua nhiều vòng sau khi final plan được tạo.
- Không đặt vé máy bay, phòng ở hoặc nhà hàng.
- Không thực hiện thanh toán.
- Không tích hợp live provider cho flight price, lodging price hoặc availability
  trong MVP đầu tiên.
- Synthetic estimates không đại diện cho giá thị trường thật.
- Không đảm bảo giá hoặc availability.
- Không xử lý severe allergy như một khả năng recommendation hoặc safety
  guarantee trong MVP.
- Không đưa ra tư vấn pháp lý, visa hoặc y tế có tính thẩm quyền.
- Không dùng request-supplied identity như production authorization boundary.
- Không production authentication hoặc tenant isolation trong MVP.
- Không multi-city planning trong MVP đầu tiên.

## 11. Research questions and hypotheses

### RQ-1: Orchestration — explicit workflow có đáng giá không?

> Với cùng model, tools, fixtures và evaluation inputs, một LangGraph workflow có
> explicit state, conditional routing, interrupts và bounded loops có xử lý yêu
> cầu lập kế hoạch du lịch ổn định hơn một LangChain agent loop đơn giản không?

**Hypothesis:** LangGraph không trực tiếp làm model thông minh hơn, nhưng explicit
state và routing giúp giảm mất input constraints, sai workflow outcome, tool-call
loop không kết thúc và lỗi khi clarification/resume.

**Evaluation signals:** input-normalization accuracy, workflow-outcome accuracy,
hard-constraint violations, loop-limit violations, clarification/resume success
và khả năng unit test từng node/edge.

### RQ-2: Multi-agent — khi nào tốt hơn single-agent?

> Với cùng model, tools, synthetic fixtures, constraints và evaluation dataset,
> việc tách destination, accommodation và food research thành specialist agents
> có cải thiện itinerary quality đủ để bù thêm model calls, token cost và
> orchestration complexity so với một single planning agent không?

**Hypothesis:** single-agent đủ dùng cho các yêu cầu đơn giản; multi-agent chỉ tạo
giá trị rõ ràng ở các trường hợp research-heavy, có nhiều nhóm dữ liệu hoặc cần
chạy những nhiệm vụ độc lập song song.

**Evaluation signals:** hard-constraint satisfaction, recommendation relevance,
source coverage, duplicated/incorrect tool calls, model/tool call count, token
usage và estimated cost. Latency được ghi nhận nhưng chưa là release threshold.

### RQ-3: Memory — cần nhớ gì và trong bao lâu?

> Đối với workflow clarify-then-generate, thông tin nào phải nằm trong
> thread-scoped state và thông tin nào, nếu có, đáng được lưu vào long-term Store
> để cá nhân hóa chuyến đi sau mà không gây stale preference, conflict, privacy
> hoặc consent errors?

**Hypothesis:** short-term state là bắt buộc để thu thập và giữ constraints trong
một planning thread. Long-term memory chưa cần cho MVP và chỉ nên được thêm nếu
thử nghiệm chứng minh lợi ích cá nhân hóa lớn hơn rủi ro lưu nhầm hoặc dùng sai
preference.

**Evaluation signals:** memory recall precision, current-request override
accuracy, stale/irrelevant preference usage, cross-user isolation, unauthorized
memory writes và sensitive-data leakage. Unauthorized writes và cross-user
leakage phải bằng 0.

### Supporting product hypothesis

Một kế hoạch one-shot có cấu trúc, nguồn và missing-information list đủ hữu ích
để người dùng thực hiện chuyến đi mà không cần chỉnh sửa nhiều vòng. Feedback có
thể hỗ trợ evaluation trong tương lai, nhưng persistence và reuse nằm ngoài MVP.

## 12. Success criteria

### Input quality

- Không tạo final plan khi thiếu điểm xuất phát, điểm đến hoặc thông tin thời
  gian tối thiểu.
- Khoảng ngày phải được chuẩn hóa thành ngày bắt đầu và ngày kết thúc.
- Nếu traveler information không có, hệ thống phải dùng default một người lớn,
  không có trẻ em và công bố assumption này.
- Khi người dùng cung cấp người lớn/trẻ em, hệ thống chỉ yêu cầu count và không
  hỏi tuổi trong MVP.
- Nếu budget không có, output phải đưa ra một khoảng budget và assumptions.
- Nếu budget có, tổng estimate của recommended plan không được vượt hard limit.
- Constraint mơ hồ phải được clarification trước khi planning.

### Plan completeness

- Mỗi accepted plan có itinerary theo ngày.
- Có ba lựa chọn chính và tối đa hai alternatives cho mỗi nhóm: tham quan/trải
  nghiệm, nơi lưu trú và nơi ăn, khi đủ evidence phù hợp.
- Recommended plan dùng một lựa chọn lưu trú chính.
- Food recommendations không bắt buộc được gán vào từng bữa ăn.
- Có cost breakdown cho toàn bộ chuyến đi.
- Có sources.
- Có missing-information list.

### Evidence quality

- Material dynamic claims có source và thời điểm lấy dữ liệu.
- Không có fabricated source.
- Unsupported material claims bị reject hoặc đánh dấu chưa xác nhận.
- Nguồn stale hoặc conflict không được trình bày như fact chắc chắn.

### Constraint compliance

- Không itinerary item nào vi phạm hard constraint đã xác nhận.
- Accessibility/dietary requirement chưa được xác minh không được báo là phù
  hợp.
- Severe allergy input phải kích hoạt limitation notice; hệ thống không được tạo
  safety claim về venue.
- Current request override preference đã lưu.

### Operations

- Mọi loop có giới hạn.
- Tool failure được surfaced hoặc xử lý rõ ràng.
- Acceptance tests có thể chạy bằng offline fixtures.
- Có thể đo latency, model/tool calls và estimated cost.
- MVP chưa đặt latency threshold; latency chỉ được ghi nhận làm baseline.

### MVP acceptance thresholds

- 100% required inputs được normalize hoặc clarification.
- Không accepted plan nào vi phạm hard constraint đã xác nhận.
- Không có fabricated source, price hoặc availability claim.
- 100% accepted plans có itinerary, accommodation, food recommendations, cost
  breakdown, sources và missing-information list.
- Recommendation groups có ba lựa chọn chính và tối đa hai alternatives khi đủ
  evidence; nếu thiếu evidence phải nêu data gap.
- Missing live data không được chuyển thành guessed fact.

## 13. Feedback policy

Người dùng có thể cung cấp phản hồi về kế hoạch, ví dụ:

- kế hoạch hữu ích hay không;
- địa điểm nào phù hợp hoặc không phù hợp;
- estimated cost có sát thực tế không;
- thông tin nào sai hoặc đã stale;
- accessibility hoặc dietary recommendation có chính xác không.

Trong MVP:

- feedback là optional;
- người dùng có thể feedback sau khi chọn plan;
- người dùng cũng có thể feedback sau khi đã trải nghiệm một phần hoặc toàn bộ
  chuyến đi;
- feedback không tự động sửa plan đã tạo;
- feedback không tự động trở thành long-term memory;
- durable feedback storage nằm ngoài MVP;
- retention, update và delete workflow cho feedback chưa được triển khai;
- feedback không được tự động đưa vào evaluation dataset hoặc memory.

Nên phân biệt hai loại feedback:

- `plan_selection_feedback`: lý do người dùng chọn hoặc không chọn plan;
- `post_trip_feedback`: đánh giá sau khi đã trải nghiệm thực tế.

## 14. Data and privacy constraints

- Không lưu passport number, payment data hoặc credentials.
- Không yêu cầu medical diagnosis để xử lý accessibility.
- Severe allergy data là sensitive. Nếu người dùng cung cấp, dữ liệu chỉ được
  dùng để hiển thị limitation và không được lưu dài hạn nếu chưa có consent.
- Traces không chứa raw sensitive preferences nếu không cần thiết.
- Corpus, fixtures và evaluation examples phải dùng dữ liệu synthetic hoặc đã
  sanitize.
- Secrets chỉ nằm trong ignored environment files.

## 15. Confirmed decisions and deferred topics

### Confirmed MVP decisions

- Người dùng cung cấp khoảng ngày bắt đầu và kết thúc.
- Canonical date format là ISO `YYYY-MM-DD` cho cả tiếng Việt và tiếng Anh.
- Nếu thiếu năm, hệ thống dùng năm hiện tại từ runtime clock và ghi assumption.
- Hệ thống phân biệt `adult_count` và `child_count`; không thu thập tuổi trẻ em
  trong MVP.
- Nếu thiếu traveler information, mặc định một người lớn và không có trẻ em.
- Budget là hard limit cho toàn bộ chuyến đi.
- Vé máy bay và lưu trú nằm trong hard budget, cùng với các chi phí itinerary
  khác.
- Nếu thiếu budget, agent đưa ra một khoảng budget estimate.
- MVP dùng deterministic synthetic fixtures cho flight/lodging prices.
- Synthetic prices phải được gắn nhãn và không đại diện cho live market prices.
- Mỗi nhóm recommendation có ba lựa chọn chính và tối đa hai alternatives khi
  đủ evidence.
- Recommended plan dùng một lựa chọn lưu trú chính.
- Food recommendations là danh sách địa điểm, không phải lịch bữa ăn bắt buộc.
- Attractions được xếp lịch theo schedule feasibility; phần còn lại nằm trong
  alternatives.
- Accessibility và dietary questions chỉ được hỏi chi tiết khi có liên quan.
- Accessibility/dietary hard constraints ưu tiên official hoặc authoritative
  evidence; blog/review không đủ để xác nhận độc lập.
- Live flight/lodging/availability providers nằm ngoài MVP hiện tại.
- Feedback được thu thập sau khi người dùng chọn plan hoặc sau khi họ đã trải
  nghiệm.
- Feedback retention, update và delete nằm ngoài MVP hiện tại.
- Severe allergy không nằm trong MVP.
- Latency được đo làm baseline nhưng chưa có acceptance threshold.

### Deferred post-MVP topics

#### Live provider exploration

Các nguồn ứng viên để nghiên cứu sau MVP gồm:

- Vietjet Air;
- Vietnam Airlines;
- Bamboo Airways;
- “Phú Quốc Air” — tên hãng/đơn vị cần được xác minh trước khi xem là nguồn;
- các lodging hoặc travel APIs chưa được lựa chọn.

Các website hãng bay là nguồn thông tin ứng viên, không mặc nhiên là API provider
hoặc được phép tự động thu thập dữ liệu. Cần đánh giá API, điều khoản sử dụng,
rate limit, coverage, freshness và chi phí trước khi tích hợp.

#### Durable feedback

Retention, update, delete và việc sử dụng feedback để cập nhật long-term memory
chỉ được thiết kế khi durable feedback storage được đưa vào scope.

#### Severe allergy support

Chỉ được đưa vào scope sau khi có nguồn allergen/cross-contamination đáng tin cậy,
validation policy và UX cảnh báo phù hợp.

## 16. Initial acceptance scenarios

Tối thiểu cần có:

1. Đủ input và có budget → `PLAN_READY` với plan không vượt total-trip hard
   limit.
2. Không có traveler information → dùng default một người lớn, không có trẻ em
   và ghi assumption.
3. Có người lớn và trẻ em → giữ hai count riêng, không hỏi tuổi.
4. Date input ở tiếng Việt và tiếng Anh → cùng được normalize thành ISO
   `YYYY-MM-DD`.
5. Khoảng ngày thiếu năm → tự động dùng năm hiện tại, normalize thành ISO và ghi
   assumption.
6. Input ngày mơ hồ không thể normalize an toàn → `NEEDS_CLARIFICATION`.
7. `end_date < start_date` → `NEEDS_CLARIFICATION`.
8. Không có điểm xuất phát → `NEEDS_CLARIFICATION`.
9. Không có budget → dùng deterministic synthetic fixtures để trả một khoảng
   budget và cost breakdown có nhãn `synthetic_estimate`.
10. Có budget → recommended plan không vượt total-trip hard limit.
11. Synthetic price có fixture ID và không có fabricated source URL.
12. Output có ba nơi lưu trú chính và tối đa hai alternatives khi đủ evidence;
    đúng một nơi được chọn cho recommended plan.
13. Output có ba nơi ăn chính và tối đa hai alternatives; không bắt buộc gán vào
    từng bữa ăn.
14. Attractions được chọn theo schedule feasibility; các điểm phù hợp còn lại
    nằm trong alternatives.
15. Hai nguồn có giờ mở cửa mâu thuẫn → `RESEARCH_INCOMPLETE` hoặc
    `NEEDS_USER_DECISION`.
16. Wheelchair + step-free bắt buộc → chỉ dùng candidate có official hoặc
    authoritative evidence phù hợp.
17. Không có accessibility/dietary need → không mở rộng bộ câu hỏi chi tiết.
18. Severe allergy input → hiển thị limitation và không tạo safety claim.
19. Prompt injection trong travel source → instruction bị cô lập.
20. Stored preference mâu thuẫn current request → current request được ưu tiên.
21. Người dùng feedback sau khi chọn plan → ghi nhận loại
    `plan_selection_feedback`.
22. Người dùng feedback sau chuyến đi → ghi nhận loại `post_trip_feedback`, nhưng
    không persist trong MVP.

## 17. Week 0 Definition of Done

- Charter đã được review và có trạng thái `Accepted for MVP`.
- Các quyết định về ISO date, current-year default, adult/child counts,
  total-trip budget, synthetic pricing, recommendation structure, conditional
  accessibility/dietary intake, feedback scope và severe-allergy scope được ghi
  rõ.
- Flight/lodging estimates dùng deterministic synthetic fixtures; không có
  fallback tạo giá hoặc source giả.
- Có hard-constraint, accessibility và dietary policy.
- Có ít nhất 15 evaluation scenarios.
- Có baseline environment report cho MacBook M1.
- Có `AGENTS.md`, `PROJECT_STATUS.md` và Week 0 learning log.
- Chưa triển khai LangGraph trước khi các mục trên hoàn thành.

## 18. Charter change control

Charter cần được review lại khi một trong các thay đổi sau được đưa vào scope:

- chọn live flight, lodging hoặc availability provider;
- thêm multi-city planning;
- thêm durable feedback storage hoặc dùng feedback cho memory/evaluation;
- thêm severe-allergy support;
- thay đổi từ synthetic pricing sang live pricing;
- đặt latency hoặc cost threshold làm release gate.
