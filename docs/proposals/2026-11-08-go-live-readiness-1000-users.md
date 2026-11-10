# Phương Án Go-Live Cho 1.000 Người Dùng

Ngày: 2026-11-08
Trạng thái: Đề xuất; chưa triển khai và chưa đổi kiến trúc.

## Mục tiêu và phạm vi

Đánh giá khả năng đưa Grounded Travel Planner lên môi trường công khai cho khoảng 1.000 người dùng, với trọng tâm là bảo mật, sức chịu tải và chi phí OpenAI API. Đợt rà soát chỉ đọc tài liệu và mã nguồn hiện có. Không đọc `.env`, không gọi dịch vụ thật, không kiểm tra container đang chạy và không chạy test.

“1.000 người dùng” cần tách thành hai mục tiêu:

- 1.000 tài khoản đã đăng ký, nhưng chỉ một phần nhỏ hoạt động cùng lúc.
- 1.000 người truy cập đồng thời, có thể cùng gửi lượt lập kế hoạch.

Mã nguồn hiện tại chưa chứng minh đạt mục tiêu thứ hai. Số tài khoản không đủ để dự báo tải; cần đo số phiên đồng thời, số lượt lập kế hoạch mỗi phút, số token mỗi lượt và độ dài giờ cao điểm.

## Kết luận

**Chưa sẵn sàng go-live công khai cho 1.000 người hoạt động đồng thời.** Có đường chạy sản phẩm, kiểm tra offline và PostgreSQL cho tour đã lưu. Nhưng bản đang chạy chưa có đăng nhập bắt buộc mới, phiên làm việc chưa dùng chung giữa các process/replica, khả năng xử lý model bị giới hạn ở 8 lượt mỗi process, và chưa có tải thực tế để xác nhận năng lực.

Có thể chuẩn bị pilot giới hạn sau khi triển khai và kiểm tra Auth0 trên môi trường đích. Không nên quảng bá rằng hệ thống chịu được 1.000 người đồng thời trước khi hoàn thành các cổng tải, khôi phục dữ liệu và giới hạn chi phí bên dưới.

## Bằng chứng hiện có

- Charter và ADR 0021 yêu cầu đăng nhập Auth0 trước khi dùng planner. Status và implementation plan ghi nhận thay đổi này mới được kiểm tra offline; chưa kiểm tra OTP/callback thật, browser QA, Compose rebuild hay restart. Bản đang chạy vẫn là image trước thay đổi.
- Compose chạy một app container trên máy chủ Mac, bind cổng app vào loopback, và dùng PostgreSQL trên thư mục host. Uvicorn chạy một process theo lệnh hiện tại. App và database không có chính sách tự khởi động lại trong Compose.
- `SessionStore` giữ tối đa 1.024 phiên trong RAM; phiên hết hạn sau một giờ không hoạt động. Restart hoặc thay process làm mất itinerary, transcript và lượt đang chờ. Nhiều replica không thể đọc cùng phiên.
- `TurnRunner` có 4 worker và tối đa 8 lượt đang chạy hoặc xếp hàng mỗi process. Khi đầy, API trả 429. Hai bộ giới hạn lượt và hai PostgreSQL pool cũng nằm trong từng process. Pool auth và pool tour có sức chứa tối đa 4 kết nối mỗi pool.
- Khi lượt đang chờ, React đọc `/api/session` mỗi 1,2 giây. Mỗi lần đọc xác thực cookie qua PostgreSQL; xác thực hiện cập nhật thời gian hết hạn idle. Nếu 1.000 người cùng chờ, tần suất thăm dò lý thuyết khoảng 833 request/giây, đồng thời tạo xấp xỉ số lần cập nhật auth-session. Đây là phép tính từ chu kỳ UI, không phải kết quả đo tải.
- Ngrok policy hiện giới hạn 20 lượt/giờ/IP và 20 lần tạo/reset phiên/giờ/IP. Giới hạn theo IP có thể chặn người dùng hợp lệ cùng dùng mạng trường học, công ty, khách sạn hoặc NAT di động. Đây là profile tùy chọn, không phải edge production được quản lý.
- Giới hạn 20 lượt/người/giờ và giới hạn tổng theo process đếm số lượt, không đếm USD. Global cap là tùy chọn trong code và trạng thái hiện có không công bố giá trị cấu hình. Bộ đếm mất khi process restart và không dùng chung giữa replica.
- `PROJECT_STATUS.md` ghi nhận 176 test offline qua, 1 test PostgreSQL tùy chọn bỏ qua; nhưng các kết quả đó không kiểm tra Auth0 thật, lượt model thật, tải đồng thời hoặc bản image mới.
- GitHub Actions kiểm tra source. Mac deploy poller đang bị khóa bằng `GTP_DEPLOY_ENABLED=false`; đây chưa phải pipeline production có HA hoặc rollback dữ liệu.

## Thiết kế go-live đề xuất

### Giai đoạn 0 — Hoàn tất bảo mật và rollout Auth0

1. Dùng Auth0 production tenant, email OTP delivery, domain và callback/logout URL cố định. Kiểm tra login, logout, hết hạn, OTP sai, callback lỗi, nhiều tab, đổi tài khoản, session cũ và cookie `Secure` qua HTTPS.
2. Chạy migration account ownership theo ADR 0016/0015 trong maintenance window: dừng ghi, tạo backup, kiểm tra restore, migrate, đối chiếu số dòng/checksum, rồi mới chuyển app. Giữ bản backup và đường rollback trong thời hạn đã định.
3. Deploy image chứa ADR 0021. Xác minh API từ browser và request trực tiếp: anonymous bị từ chối; phiên tài khoản A không đọc/sửa được dữ liệu tài khoản B; logout vô hiệu hóa cookie và phiên.
4. Đưa app sau managed TLS, WAF/DDoS protection và rate limiter. Chỉ edge được gọi origin. Không tin `X-Forwarded-For` nếu edge chưa ghi đè header đó. Giới hạn IP chặt cho đăng nhập và session allocation; giới hạn lượt chính theo internal account UUID. Đặt mức IP đủ dùng cho nhiều tài khoản chung NAT.
5. Rà soát endpoint graph công khai. Giữ public landing, static assets và health check cần thiết; đóng hoặc giới hạn `/api/graph` và `/api/graph/image` nếu chỉ dành cho nhà phát triển.
6. Chốt thời hạn lưu dữ liệu và quy trình xóa/xuất dữ liệu tài khoản. Xác định LangSmith có lưu prompt, lịch trình, câu người dùng và output model hay không; giới hạn project access, retention và nội dung trace theo chính sách riêng tư. Sự kiện `model.usage` tự tạo đã được redaction, nhưng không xem đó là bằng chứng rằng mọi trace LangChain khác đã được làm sạch.
7. Pin production container images theo phiên bản/digest đã duyệt, quét lỗ hổng trước release và giữ artifact build cùng commit SHA. Không dùng tag `latest` làm production pin.

### Giai đoạn 1 — Pilot có giới hạn

- Chọn nhà cung cấp cloud và region theo yêu cầu độ trễ, dữ liệu và ngân sách; không dùng Mac cá nhân, tunnel ngrok hoặc Ollama trên máy phát triển làm production dependency.
- Bắt đầu bằng pilot mời riêng, giới hạn đồng thời bằng quota và hàng đợi hiện có. Không vượt 8 lượt đang chạy/đợi trên một process cho đến khi đã thay `TurnRunner` bằng hàng đợi có chia sẻ trạng thái. Thông báo 429 và retry rõ ràng cho người dùng.
- Bật metric về request rate, active sessions, worker utilization, queue depth, 429/5xx, thời gian chờ, thời gian model, DB pool wait, DB latency, lỗi Auth0, token usage theo role/model, Tavily calls và USD theo ngày/tháng.
- Đo pilot trên workload đại diện. Ghi p50/p95/p99 cho API và model turns, tỉ lệ lỗi, số lượt bị từ chối, token trung bình và chi phí mỗi itinerary. Chỉ tăng cohort sau khi có số liệu và ngân sách thực tế.

### Giai đoạn 2 — Mở rộng đến 1.000 tài khoản

1. Giữ API stateless sau ingress và lưu phiên tạm có TTL một giờ trong một kho dùng chung như Redis. Giữ nội dung phiên chỉ trong thời gian cần thiết; việc chuyển vị trí lưu không đổi chính sách session-only.
2. Thay `Future` trong process bằng job queue dùng chung. Worker đọc bản chụp phiên, chạy graph có giới hạn, rồi ghi kết quả về đúng session/job. Bảo đảm một lượt đang chạy cho mỗi session, kiểm tra revision khi commit và không để worker ghi đè phiên đã reset hoặc logout.
3. Đưa quota theo account, giới hạn tổng, khóa session và budget reservation vào kho dùng chung để không bị nhân lên theo số replica hoặc reset khi restart. Trả quota nếu job chưa bắt đầu; lưu dấu vết idempotency để tránh chạy trùng sau retry.
4. Dùng managed PostgreSQL có private networking, mã hóa, backup tự động, point-in-time recovery và cảnh báo dung lượng. Thực hiện restore drill. Đặt connection budget theo công thức: tối đa 8 kết nối app mỗi process hiện tại (4 auth + 4 archive), cộng migration, monitoring và headroom. Dùng pooler nếu tổng pool replica vượt giới hạn database.
5. Giảm tải polling. Thay chu kỳ cố định 1,2 giây bằng backoff có jitter hoặc cơ chế server notification. Tránh ghi auth-session expiry cho mỗi lần poll; chỉ gia hạn theo hoạt động có ý nghĩa hoặc theo ngưỡng thời gian, nhưng phải giữ đúng chính sách idle timeout và logout/revocation.
6. Cấu hình retry có backoff/jitter cho lỗi 429/503 theo `Retry-After`. Không retry lỗi billing, key hoặc model permission. Đặt concurrency theo project RPM/TPM thật của từng model, không suy ra từ tier tài khoản.

### Giai đoạn 3 — Xác nhận 1.000 người đồng thời

Thực hiện load test trước khi mở cohort rộng. Dùng các bước 10, 50, 100, 250, 500 và 1.000 session đồng thời; chạy cả tình huống chỉ duyệt, lưu/xem tour, đăng nhập, và nhiều lượt lập kế hoạch cùng lúc. Mỗi bước phải dùng cùng phân bố model, ngôn ngữ, độ dài request, plan hiện có, tỉ lệ Tavily và retry như dự kiến production.

Tiêu chí go/no-go cần chốt trước khi chạy: p95/p99 mục tiêu cho API và lượt planner; tỉ lệ lỗi tối đa; thời gian chờ queue; mức sử dụng CPU/RAM; giới hạn pool PostgreSQL; RPM/TPM OpenAI; chi phí tối đa theo ngày/tháng; và kết quả khi app, worker, Redis hoặc PostgreSQL restart/failover. Chạy ít nhất một bài soak test đủ dài để phát hiện tăng bộ nhớ, session không hết hạn và quota không được giải phóng. Không lấy benchmark archive 2 triệu dòng hiện có làm bằng chứng cho tải model: benchmark đó dùng snapshot nhỏ, một mình DB và không có traffic đồng thời.

## Kiểm soát chi phí OpenAI

Theo charter, model mặc định là Coordinator `gpt-5.5`, Planner `gpt-6.1-terra`, Chat `gpt-4.1`. Bảng giá tiêu chuẩn hiện tại của OpenAI là USD trên một triệu token: Coordinator $5 input / $30 output; Planner $1 input / $5 output; Chat $2 input / $8 output. Giá cached input thấp hơn nếu request được cache. Đối chiếu lại model ID, project, context tier và giá ngay trước launch; giá thay đổi theo model và endpoint.

Code mặc định chặn output mỗi lần gọi ở 2.048 token cho Coordinator, 8.192 cho Planner và 2.048 cho Chat. Một lượt đổi itinerary có thể gọi Planner thêm một lần để repair. Nếu mọi lần gọi dùng hết trần output, giới hạn lý thuyết là `(2.048 × $30 + 2 × 8.192 × $5 + 2.048 × $8) / 1.000.000`, khoảng **$0,160 cho một lượt**, chưa tính input token, search, LangSmith hay hạ tầng. Không xem đây là chi phí trung bình; đây là trần ước tính từ default hiện tại.

Ước tính ngân sách sau khi đo:

`chi phí lượt = tổng theo role ((input tokens × input USD/MTok) + (output tokens × output USD/MTok)) / 1.000.000`

Ví dụ quy mô: 1.000 tài khoản × 10 lượt/tháng = 10.000 lượt/tháng. Nếu đo được chi phí trung bình mỗi lượt là $0,02 / $0,05 / $0,10, chi phí model lần lượt là $200 / $500 / $1.000 mỗi tháng. Đây là kịch bản minh họa, không phải dự báo. Tavily, Auth0 email, LangSmith, database, compute, egress và thuế nằm ngoài số này.

Việc cần làm:

1. Tạo OpenAI project riêng cho production, key chỉ ở secret manager hoặc workload identity, quyền thấp nhất, chỉ bật model cần dùng, tách key staging/production và đặt quy trình rotate.
2. Đặt monthly project spend hard limit cùng cảnh báo sớm. Hard limit của OpenAI có thể trễ và vượt nhẹ; cảnh báo không chặn request. Dùng thêm ngân sách ứng dụng theo giờ/ngày/tháng trong kho quota dùng chung.
3. Trước mỗi lần gọi model, ước lượng input token, đặt giới hạn input và output, reserve phần ngân sách tối đa cho request, rồi đối chiếu với usage thực tế sau response. Nếu đạt ngưỡng, không đưa thêm job vào queue và trả thông báo có thể hiểu được.
4. Đo usage theo role/model, loại lượt, kết quả và revision. So sánh `model.usage` với OpenAI Usage/Billing Dashboard; LangSmith event là telemetry, không thay thế ledger chi phí đáng tin cậy.
5. Thử model rẻ hơn cho Coordinator và Chat vì hai role này được gọi thường xuyên; giữ Planner model cho lượt thay itinerary cho đến khi bộ eval xác nhận chất lượng. Hạ output caps theo p95 usage và regression QA, không chỉ cắt token theo suy đoán. Giữ giới hạn search hai lần/lượt và chỉ gọi Chat search khi cần dữ kiện mới.
6. Tính savings từ prompt caching sau khi đo cache hit. Giữ summary/history đã có giới hạn; không gửi nguyên transcript hoặc lặp lại source context.

OpenAI giới hạn RPM/TPM theo organization/project và theo model. Xem rate limit thực tế tại project trước load test; đặt allowlist model và tăng tải từ từ. Project spend limit và model rate limit là hai cơ chế khác nhau.
[OpenAI rate limits](https://developers.openai.com/api/docs/guides/rate-limits), [quản lý project và spend limits](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform), [GPT-5.5 pricing](https://developers.openai.com/api/docs/models/gpt-5.5), [GPT-6.1 Terra pricing](https://developers.openai.com/api/docs/models/gpt-6.1-terra), [GPT-4.1 pricing](https://developers.openai.com/api/docs/models/gpt-4.1).

## Cổng go-live

Chỉ mở public launch khi tất cả mục sau có bằng chứng:

- Image production chứa mandatory Auth0 sign-in đã deploy; OTP, callback, cookie, CSRF, account isolation và logout đã qua browser QA.
- Migration database đã có backup/restore kiểm tra; account-owner indexes và auth schema khớp code đang chạy.
- Edge TLS/WAF, origin lock-down, distributed account/IP quotas và cảnh báo abuse hoạt động. Không dựa riêng vào giới hạn process-local hoặc ngrok.
- Phiên/job/quota dùng chung trước khi chạy nhiều replica. Queue và model concurrency có giới hạn rõ. API polling không gây nghẽn auth database.
- Load test đạt mục tiêu đã thống nhất cho đúng số session và model turns; có log/metric về queue, token, USD, DB và lỗi.
- OpenAI project có rate limit phù hợp, hard spend limit và app-level budget. Giá/tải thực tế được đo trên workload đại diện.
- Backup off-host, point-in-time recovery hoặc cơ chế tương đương và restore drill hoạt động. Có người trực, runbook sự cố, rollback image và rollback migration.
- Đã quyết định retention, deletion/export, trace access và incident response cho dữ liệu người dùng.

## Các quyết định cần chốt trước khi triển khai

- Mục tiêu tải: 1.000 tài khoản hay 1.000 concurrent sessions; số planner turns đồng thời và số lượt mỗi tài khoản mỗi ngày.
- Cloud/region, budget tháng, SLA và thời gian mất dữ liệu/tối đa gián đoạn chấp nhận được.
- Mức lưu trace LangSmith và chính sách dữ liệu, xóa tài khoản và export.
- Pilot có mời riêng hay mở public ngay sau khi đạt load gate.

## Nguồn trong repository

- `docs/project-charter.md`, ADR 0011/0012/0015/0016/0021.
- `PROJECT_STATUS.md` và đầu `docs/implementation-plan.md` cho trạng thái deployed so với offline-verified.
- `compose.yaml`, `src/grounded_travel_planner/web/api.py`, `src/grounded_travel_planner/ui/turn_runner.py`, `src/grounded_travel_planner/auth.py`, `src/grounded_travel_planner/web/turn_rate_limit.py`, `src/grounded_travel_planner/adapters/model.py` và `frontend/src/main.tsx` cho giới hạn process, polling, auth và model usage.

Không chạy test, container, browser hoặc live provider trong đợt rà soát này.
