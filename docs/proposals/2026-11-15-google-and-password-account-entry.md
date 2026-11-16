# Đề xuất đăng nhập Google và email/mật khẩu

Trạng thái: Người dùng chấp thuận triển khai ngày 2026-11-15. Google/password
đã có kiểm chứng offline trước đó; phần mở rộng Email OTP và công cụ reconcile
được viết ngày 2026-11-16, chưa chạy kiểm chứng tự động. Schema PostgreSQL đã
được migrate sau backup; user chọn UUID admin làm chuẩn và cho phép self-audit.
Đã gộp một identity, giữ sáu tour, thu hồi hai phiên phụ và ghi alias/audit.
Auth0 tenant, trình duyệt, deployment và kiểm chứng tự động chưa hoàn tất.

## Goal Card

- **Mục tiêu:** Một người dùng vào cùng tài khoản ứng dụng bằng Google, Auth0 email/mật khẩu hoặc email OTP. Người dùng đăng ký bằng Google có thể mở Thông tin cá nhân để tạo mật khẩu; mọi phương thức liên kết đều trỏ về một UUID ứng dụng.
- **Chấp nhận:** Cả ba cách đăng nhập trả về cùng UUID, quyền truy cập và tour đã lưu sau khi liên kết; liên kết lỗi không đổi UUID hay phiên đang dùng; không ghép tài khoản chỉ vì email giống nhau; email chưa xác minh hoặc tài khoản bị chặn không được vào ứng dụng; không có mật khẩu hoặc token Auth0 trong JavaScript, database ứng dụng, log hay trace.
- **Phạm vi:** React, FastAPI BFF, kho danh tính SQLite/PostgreSQL, Auth0 email OTP/password/Google và quy trình operator xử lý UUID trùng đã có.
- **Ngoài phạm vi:** Mật khẩu Gmail/Google, lưu mật khẩu trong ứng dụng, tự gộp tài khoản khi email trùng, xóa hoặc hủy liên kết danh tính. UUID trùng có thể được operator xử lý riêng bằng quy trình có backup, xác nhận quyền sở hữu cả hai identity, dry-run, bảo toàn tour/audit và alias usage; không xử lý tự động trong luồng đăng nhập.
- **Kiểm chứng:** Test offline có nhà cung cấp giả; frontend check/build; bộ kiểm tra Python theo `AGENTS.md`; thử trực tiếp trên Auth0 tenant và trình duyệt, gồm xác minh email, đặt lại mật khẩu, cả hai chiều liên kết và tour đã lưu.
- **Commit/push:** Chưa được yêu cầu.

Ở đây “đăng nhập bằng Gmail” nghĩa là **Tiếp tục với Google** qua Auth0. “Email và mật khẩu” dùng địa chỉ Gmail làm tên đăng nhập nhưng dùng **mật khẩu riêng của Auth0**, không phải mật khẩu Gmail.

## Hiện trạng trước triển khai — 2026-11-15

1. Landing có Đăng nhập và Đăng ký. Cả hai chuyển đến `/api/auth/login`; đăng ký chỉ thêm `screen_hint=signup`. Không có nút Google riêng. `frontend/src/main.tsx`, `src/grounded_travel_planner/web/api.py`.
2. Auth0 sở hữu Google, database password và email OTP. BFF dùng Authorization Code/PKCE, xác minh ID token và `email_verified`, rồi ánh xạ `(issuer, subject)` vào UUID ứng dụng. `src/grounded_travel_planner/auth.py`.
3. Sau khi đăng nhập tài khoản cũ, menu Tài khoản có Liên kết Google. Luồng này đòi CSRF, phiên mới trong 5 phút, Google xác thực lại, email đã xác minh và cùng email. Nó giữ UUID/tour cũ. Chỉ có kiểm chứng offline; Auth0/browser thật còn chờ.
4. `/api/auth/me` chỉ trả email, CSRF và quyền truy cập. Không trả cách đăng nhập đã liên kết. Chưa có trang Thông tin cá nhân hay thao tác tạo/đổi mật khẩu.
5. `find_or_create_user` chỉ chặn email trùng khi danh tính **Google** mới đến. Nếu Google đến trước rồi danh tính database password đến sau, mã hiện có thể tạo UUID ứng dụng thứ hai. Cả SQLite và PostgreSQL có cùng điều kiện một chiều.
6. Cấu hình Auth0 cho form xác nhận mật khẩu, chính sách mật khẩu và email xác minh đã được chuẩn bị trong `auth0/`, nhưng chưa áp dụng hoặc thử trực tiếp trên tenant.

## Trải nghiệm đề xuất

- Landing: một nút **Tiếp tục với Google** và một nút **Đăng nhập bằng email**. Đăng ký email/mật khẩu vẫn là hành động riêng. Chọn Google lần đầu đồng thời tạo tài khoản ứng dụng sau khi Auth0 xác minh email. Không đặt các chi tiết xác thực vào phần mô tả sản phẩm.
- Trang **Thông tin cá nhân** từ menu Tài khoản: email đã xác minh; trạng thái **Google** và **Mật khẩu**; hành động **Liên kết Google**, **Tạo mật khẩu**, **Đã có mật khẩu? Liên kết** hoặc **Đổi mật khẩu** theo trạng thái. Phản hồi rõ khi cần xác minh email, đăng nhập lại hoặc xử lý tài khoản trùng.
- Google trước, mật khẩu sau: người dùng đã đăng nhập Google chọn Tạo mật khẩu. Ứng dụng mở form đăng ký của Auth0 cho đúng database connection; Auth0 nhận mật khẩu, xác nhận mật khẩu và xác minh email. Người dùng trở lại tài khoản Google, xác thực mới bằng email/mật khẩu để liên kết danh tính database vào UUID hiện có. Nếu danh tính database đã tồn tại, người dùng chọn Đã có mật khẩu? Liên kết và xác thực danh tính đó, không đăng ký thêm. Trong thời gian chưa hoàn tất, đăng nhập độc lập bằng danh tính database cùng email phải yêu cầu liên kết, không tạo UUID mới.
- Mật khẩu hoặc OTP trước, Google sau: dùng luồng Liên kết Google đang có, chuyển điểm vào từ Thông tin cá nhân. Đăng nhập Google lần sau giữ UUID và tour.
- Google, mật khẩu hoặc OTP có thể được liên kết từ Thông tin cá nhân theo cùng quy tắc chứng minh tài khoản gốc và identity mới. Nếu identity đã thuộc UUID khác, từ chối self-service và chuyển sang quy trình operator có kiểm soát.
- Khi đã có mật khẩu: Đổi mật khẩu khởi động luồng đặt lại mật khẩu do Auth0 quản lý và gửi thư đến email đã xác minh. Google không có mật khẩu Auth0 để “đổi”; hành động đầu tiên là **Tạo mật khẩu**. Không nhận mật khẩu mới trong form React/FastAPI.

## Kế hoạch triển khai theo thứ tự

1. **Kiểm tra tenant Auth0 trước:** xác nhận Google, một database password connection và email OTP đều bật; New Universal Login; chính sách mật khẩu, form xác nhận và thư xác minh hoạt động. Thử `screen_hint=signup` cùng `prompt=login` và database connection để bảo đảm phiên Google không bỏ qua form. Kiểm tra luồng đặt lại mật khẩu của database connection và cấu hình bot protection. Nếu tenant không hỗ trợ luồng hosted này, quyết định cơ chế Auth0 thay thế trước khi viết tích hợp.
2. **Chặn UUID trùng ở kho danh tính:** khi `(issuer, subject)` mới nhưng email đã xác minh trùng tài khoản có sẵn, yêu cầu người dùng xác thực tài khoản gốc và liên kết, áp dụng cho Google, database password và OTP. Không chọn một UUID bằng email. Nếu đã có nhiều UUID hoặc danh tính đã thuộc UUID khác, báo xung đột để xử lý có kiểm soát; giữ mọi tour. Thực hiện tương đương và an toàn đồng thời trong SQLite/PostgreSQL.
3. **Mở rộng liên kết trong BFF:** dùng lại state ký, PKCE, CSRF, phiên gốc mới, `prompt=login`, kiểm tra issuer/subject và email đã xác minh. Thêm liên kết danh tính database vào UUID gốc và audit. Đường callback chưa xác minh chỉ hướng dẫn xác minh email, giữ phiên gốc. Không nhận tên connection tùy ý từ client.
4. **Thêm API trạng thái phương thức đăng nhập:** trả Google, database password và OTP từ các danh tính đã liên kết để React hiển thị hành động đúng; không tiết lộ dữ liệu xác thực. Thêm hành động bắt đầu đặt lại mật khẩu chỉ khi UUID đang có danh tính database. Giới hạn tần suất gửi thư và hiển thị lỗi trung tính.
5. **Cập nhật UI:** thêm lựa chọn Google rõ ràng, trang Thông tin cá nhân, hướng dẫn tạo/đổi mật khẩu và lỗi liên kết bằng tiếng Việt/Anh. Giữ truy cập bàn phím, focus, mục tiêu chạm tối thiểu 44 px và trạng thái chờ.
6. **Kiểm chứng và triển khai có cổng:** test hai thứ tự đăng ký, đăng nhập lại qua từng phương thức, email chưa xác minh, phiên cũ, CSRF sai, email khác, tài khoản bị chặn, danh tính đã thuộc UUID khác, tính nguyên vẹn tour. Sau đó thử trình duyệt/Auth0 thật, sao lưu và kiểm tra migration nếu schema đổi; chỉ ghi “đã triển khai” khi image chạy và luồng thật qua kiểm chứng.

## Lý do và rủi ro

Auth0 tạo danh tính khác nhau giữa Google và database connection, kể cả khi email giống nhau; việc ghép chỉ bằng email tạo nguy cơ chiếm tài khoản. Cách trên dùng phép xác thực mới với **cả hai** danh tính trước khi cùng trỏ vào UUID ứng dụng, như cơ chế ánh xạ danh tính ứng dụng đang có. Nó tận dụng cơ chế liên kết Google hiện có và giữ mật khẩu trong Auth0; không yêu cầu Auth0 Management API cho việc liên kết. Hạn chế chính là luồng Google sang mật khẩu cần bước xác minh email và xác thực lại, chưa có bằng chứng từ tenant hiện tại.

Tham khảo Auth0: [account linking](https://auth0.com/docs/manage-users/user-accounts/user-account-linking/link-user-accounts), [email trùng giữa connections](https://support.auth0.com/center/s/article/Does-Auth0-Require-a-Unique-Email-Address-Per-User), [signup và prompt](https://support.auth0.com/center/s/article/How-to-Redirect-Users-directly-to-the-Hosted-Signup-Page), [đổi mật khẩu chỉ cho database connection](https://support.auth0.com/center/s/article/Change-Password-API-Connections-Support), [gửi thư đổi mật khẩu](https://support.auth0.com/center/s/article/Passing-Extra-Parameters-to-the-Password-Reset-URL).
