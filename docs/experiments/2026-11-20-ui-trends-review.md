# Đánh giá xu hướng UI và phương án cải tiến CitedTrip

Ngày nghiên cứu: 2026-11-20. Cập nhật 2026-11-20: P0 và điều hướng ngày P1
đã triển khai; P2 và các đề xuất chưa đánh giá sâu vẫn chưa triển khai.
Đối tượng: source tại `bdf3e353cf09490bc97fdbbea31098b578ef4636`, nhánh `improve-ui`.

## Goal Card

- Mục tiêu: nghiên cứu thiết kế hiện hành, đối chiếu giao diện dự án và đề xuất cải tiến phù hợp tác vụ lập lịch tham quan có nguồn.
- Nghiệm thu: có nguồn tham khảo, bằng chứng giao diện hiện tại, phân biệt quan sát với giả thuyết, thứ tự triển khai và tiêu chí kiểm tra.
- Phạm vi: landing, tạo chuyến đi, lịch trình, chat, tour lưu; tài khoản và admin chỉ cần tính nhất quán.
- Ngoài phạm vi: sửa ứng dụng trong lượt nghiên cứu, thay API/runtime, booking, bản đồ, triển khai production.
- Commit/push/PR: không thuộc yêu cầu nghiên cứu này. Ý định giao code của lượt trước đã được hoàn tất riêng.

## Kết luận thiết kế

Giữ hệ màu xanh/slate, Lexend, Source Sans 3 và Lucide. Phát triển phong cách du lịch nhẹ nhàng, lấy lịch trình và nguồn thông tin làm trọng tâm: chữ phân cấp rõ, ảnh địa điểm đúng nguồn, ít lớp card, hành động chính gần nội dung. Nền hiện tại đã hỗ trợ hướng này; không cần thay toàn bộ hệ thiết kế.

Các xu hướng dưới đây là tín hiệu từ nhà cung cấp thiết kế và sản phẩm tiêu biểu, không phải thống kê thị phần toàn ngành. Lợi ích đối với CitedTrip là giả thuyết cần kiểm tra, không được suy ra trực tiếp từ kết quả nghiên cứu của sản phẩm khác.

## Nghiên cứu bên ngoài

| Hướng thiết kế | Bằng chứng | Áp dụng phù hợp |
|---|---|---|
| Phân cấp biểu cảm bằng chữ, kích thước, màu và nhóm nội dung | [Google Material 3 Expressive](https://design.google/library/expressive-material-design-google-research) mô tả dùng các yếu tố này để làm rõ hành động và nhóm liên quan. [Figma: xu hướng web 2026](https://www.figma.com/resource-library/web-design-trends/) nêu typography nổi bật và motion. | Tên điểm đến nổi bật, giờ và ngày dễ quét, mỗi trạng thái một hành động chính. Giữ font hiện có; không cần màu neon hoặc chữ chuyển động. |
| Card có thứ bậc và nội dung giàu hình ảnh | [Squarespace: xu hướng 2026](https://pros.squarespace.com/blog/design-trends) đưa Card Play vào các hướng thiết kế hiện hành. | Phân biệt card ngày, điểm tham quan và metadata. Giảm card lồng card; không thêm flip hoặc nội dung chỉ xuất hiện khi hover. |
| Trải nghiệm du lịch xoay quanh chuyến đi | [Airbnb Summer Release 2025](https://news.airbnb.com/product-releases/airbnb-2025-summer-release) trình bày Trips bằng lịch và các chi tiết chuyến đi. Đây là tham chiếu sản phẩm, không chứng minh mọi UI du lịch đều dùng cùng bố cục. | Header chuyến đi gọn, điều hướng ngày, các điểm theo thời gian. Không nhập chức năng đặt chỗ hay thanh toán vào phạm vi dự án. |
| AI có nguồn dễ kiểm tra | [NN/g, Explainable AI in Chat Interfaces, 2025-12-12](https://www.nngroup.com/articles/explainable-ai/) khuyến nghị nguồn có nhãn rõ, gần nội dung được hỗ trợ và truyền đạt giới hạn trung thực. | Giữ nguồn cạnh điểm tham quan và câu trả lời. Phân biệt “ước tính”, “chưa xác minh giờ mở cửa” với trạng thái lịch đã qua kiểm tra. Không biến citation thành huy hiệu bảo đảm đúng. |
| Chiều sâu nhẹ và chuyển động có mục đích | [Apple WWDC25: Get to know the new design system](https://developer.apple.com/videos/play/wwdc2025/356/) nhấn mạnh nhóm nội dung, phân cấp và độ rõ giữa điều khiển với nội dung. | Dùng phản hồi nhấn, mở panel, trạng thái tải. Bề mặt đọc lịch và nguồn vẫn rõ, không trong suốt trên ảnh. Không sao chép Liquid Glass như một skin toàn trang. |

Nguồn Squarespace ghi bài gốc ngày 2025-12-10 và đã cập nhật; không suy diễn năm của nhãn “Jul 16”. Các trang xu hướng có thể được cập nhật sau ngày nghiên cứu.

## Bằng chứng nội bộ

Đã đọc status, charter, implementation plan, learning log, các ADR liên quan và design system. Researcher chạy mới:

`cd frontend && npm run test:browser -- --project=chromium`

Kết quả: **10 passed, 18.8s**, Chromium qua HTTP tại `127.0.0.1:4173`, API giả lập. Chụp 390/768/1024/1440 px; xem trực tiếp landing và itinerary tại 390/1440 px. Không phải nghiệm thu production, Auth0, provider hoặc độ đúng của nguồn.

Ảnh tại thư mục test-results bị Git bỏ qua và có thể bị ghi đè khi chạy lại:

- `frontend/test-results/landing-public-landing-lay-fa6aa-e-tablet-and-desktop-widths-chromium/landing-{390,768,1024,1440}.png`
- `frontend/test-results/workspace-workspace-layout-1d590--widths-with-reduced-motion-chromium/workspace-{390,768,1024,1440}.png`

| Khu vực | Quan sát hiện tại | Phương án |
|---|---|---|
| Landing | Ảnh 390px: CTA Google bắt đầu khoảng y=863; trang dài khoảng 3.470px. Năm guide card gần cùng trọng lượng. Desktop có bố cục 3+2. Hero chưa cho thấy sản phẩm thực tế. | Rút gọn phần mở đầu, đưa nhóm đăng nhập lên trước lợi ích phụ. Giữ đủ năm bước, giảm chiều cao minh họa mobile và khoảng cách lặp. Cân nhắc một ảnh chụp sản phẩm có nhãn minh họa rõ. |
| Tạo chuyến đi | Source có đủ điểm đến, ngày bắt đầu, số ngày và calendar nội bộ. Phần giải thích trước form có thể rút gọn. | Tiêu đề ngắn, form xuất hiện sớm; chỉ giữ trợ giúp liên quan từng trường. Không thêm wizard cho ba trường hiện có. |
| Lịch trình | Ảnh mobile: banner lưu đứng trước tên điểm đến, khoảng 170px. Ảnh desktop cạnh thông tin, nguồn và credit hiện rõ. Source render mọi ngày liên tiếp, chưa có điều hướng ngày. | Đưa tên điểm đến/ngày lên đầu. Tích hợp lưu vào header với giải thích snapshot ngắn. Thêm liên kết nhảy tới ngày cho lịch nhiều ngày. |
| Ảnh và trạng thái | Source giữ fallback 16:9 khi thiếu ảnh; nhãn ước tính và chưa xác minh có sắc thái gần nhau. Ảnh xanh trong screenshot là SVG fixture. | Thiếu ảnh dùng hàng thông báo nhỏ và cho văn bản chiếm chỗ. Tách kiểu nhãn bằng chữ/icon và màu có tương phản; không coi fixture xanh là lỗi ảnh production. |
| Chat | Source dùng panel fixed tối đa 448px và input một dòng; chưa xem sâu screenshot chat mở. | Thử panel dock trên desktop rộng và textarea tự giãn. Giữ overlay trên màn hình nhỏ; kiểm tra focus, bàn phím và khả năng đọc lịch khi mở chat trước khi chốt. |
| Tour lưu | Source có phân trang, chi tiết read-only, dùng lại PlanView. Chỉ có kiểm tra điều hướng, chưa review hình ảnh sâu. | Ưu tiên tên/ngày/số ngày; thao tác mở rõ hơn xóa. Không thêm cover đòi tải từng tour vì list API chưa cung cấp ảnh. |
| Tài khoản/admin | Có card, trạng thái và điều khiển nhất quán; chưa review hình ảnh sâu. | Giữ bố cục phục vụ thao tác. Chỉ tinh chỉnh khoảng cách và phân cấp sau khi chụp trạng thái thực tế. |

Nợ UI phát hiện từ source: một số điều khiển calendar và đổi ngôn ngữ dùng chiều cao 40px, dưới quy tắc 44px của dự án. Cần đo vùng tương tác trong browser. Fixture tiếng Anh hiển thị “1 days”; cần kiểm tra và sửa singular/plural theo locale.

## Phương án ưu tiên

### P0 — Hành động sớm và thông tin dễ đọc

1. Landing: thứ tự mobile là brand/ngôn ngữ, tiêu đề và mô tả ngắn, nhóm đăng nhập, lợi ích, guide. Mục tiêu ở 390×844: CTA chính nhìn thấy trong viewport đầu khi không có thông báo lỗi; email, đăng ký và OTP vẫn dễ tìm.
2. Workspace: header gồm điểm đến, ngày bắt đầu và số ngày; lưu tour ngay trong khu vực này. Giữ phản hồi thành công/thất bại của lần lưu hiện tại dễ đọc; không gắn nhãn “đã lưu” cho một lịch đã thay đổi sau đó hoặc ngụ ý lịch luôn đồng bộ với snapshot. Không tự lưu khi tạo hoặc sửa lịch.
3. Chuẩn hóa target tối thiểu 44px, focus rõ; sửa số ít/số nhiều tiếng Anh. Dùng nội dung VI/EN dài khi kiểm tra.
4. Giảm diện tích fallback ảnh; giữ ảnh thật, tác giả, giấy phép và trang nguồn khi có. Không thay bằng ảnh ngẫu nhiên.

### P1 — Lịch dài và đọc nguồn

1. Liên kết “Ngày 1…Ngày 7” nhảy tới section ngày; có offset cho sticky header, dùng được bằng bàn phím. Một ngày thì không cần thanh điều hướng. Không ẩn các ngày còn lại hoặc thay plan state.
2. Mỗi ngày có heading rõ; mỗi điểm có giờ, tên, mô tả, thời lượng, nguồn và ảnh. Giảm border/shadow lồng nhau. Nội dung vẫn dễ đọc khi không có ảnh.
3. Giữ nhãn nguồn có ý nghĩa; nếu API chỉ gắn nguồn theo điểm, trình bày ở cấp điểm. Không tự suy ra nguồn hỗ trợ từng câu khi dữ liệu chưa có quan hệ đó.
4. Giữ đủ năm bước hướng dẫn, ưu tiên bố cục theo trình tự và minh họa gọn. Nếu dùng ảnh chụp sản phẩm trên landing, chụp từ UI thật với dữ liệu kiểm thử ghi rõ “Minh họa giao diện”; không gọi đó là gợi ý chuyến đi đã được xác minh. Ảnh không chứa dữ liệu tài khoản riêng.

### P2 — Chat theo ngữ cảnh và tinh chỉnh chuyển động

1. Prototype dock chat ở desktop rộng, chỉ chốt sau khi xác nhận lịch còn đủ chiều rộng. Tablet/phone giữ panel hiện có và quản lý focus. Textarea tự giãn có giới hạn chiều cao, quy tắc gửi rõ và tương thích bộ gõ tiếng Việt.
2. Dùng chuyển tiếp khoảng 150–220ms cho panel/nút nếu phù hợp; đây là thông số đề xuất. Nội dung không chờ animation mới thao tác được. Bỏ hoặc giới hạn vòng float SVG 2,8 giây vì không báo trạng thái.
3. Tour lưu/tài khoản/admin chỉ tinh chỉnh sau vòng screenshot riêng; không mở rộng API hoặc thêm ảnh chỉ để đồng nhất hình thức.

## Bố cục mục tiêu

Desktop: header chung; header chuyến đi và lưu; liên kết ngày; lịch trình rộng với nội dung và ảnh cạnh nhau. Khi thử dock chat, chat nằm cạnh lịch và có nút đóng rõ.

Mobile: header gọn; tên chuyến đi/ngày và lưu; điều hướng ngày; các điểm theo thời gian. Chat mở theo nhu cầu. Landing đưa hành động đăng nhập lên sớm và giữ hướng dẫn bên dưới.

Không ưu tiên dark mode, WebGL/3D, parallax, maximalism hoặc kính phủ toàn trang trong đợt này: chưa có nhu cầu sử dụng hay bằng chứng lợi ích đủ mạnh cho tác vụ hiện tại. Bản đồ và animation xe tiếp tục nằm ngoài phạm vi theo quyết định sản phẩm đã có.

## Phân công và kiểm chứng khi triển khai

| Thứ tự | Chủ sở hữu và file | Bằng chứng nghiệm thu |
|---|---|---|
| 1 | Planner chốt P0, copy VI/EN, trạng thái và tiêu chí | Không thay hợp đồng session, auth, save hoặc nguồn; prototype/ảnh trước–sau cho landing và plan |
| 2 | Coordinator: `frontend/src/main.tsx`, `frontend/src/i18n.ts`, `frontend/src/index.css` | Triển khai P0 trước; tái sử dụng component/token; không thêm dependency. Tách P1/P2 thành phần việc tiếp theo |
| 3 | Tester: `frontend/tests/browser/landing.spec.ts`, `workspace.spec.ts` | Check/build và browser tests; screenshot 390/768/1024/1440, VI/EN, lịch 1/7 ngày, có/thiếu ảnh, pending/rejected, chat mở, reduced motion, keyboard, 44px |
| 4 | Primary: design system, status, implementation plan, log/progress khi thực sự đổi trạng thái | Chỉ ghi tính năng hoàn tất sau khi có bằng chứng. Không chuyển đề xuất này thành quyết định kiến trúc đã chấp nhận |

Kiểm tra hồi quy bắt buộc: đổi VI/EN khi đang có pending turn không reset lịch, transcript hoặc lượt xử lý; kết quả được tích hợp đúng một lần. Home/New Trip vẫn xác nhận trước khi bỏ lịch; xem tour lưu không sửa live plan.

Đo trước–sau: vị trí CTA trong viewport, chiều cao phần trước lịch trình, khả năng đi tới ngày cuối, số vùng điều khiển dưới 44px, tràn ngang và nội dung bị che khi chat mở. Mục tiêu định tính: người đọc xác định được điểm đến, giờ, nguồn và thông tin chưa xác minh mà không phải mở tooltip.

Nếu cần kết luận về mức dễ dùng, thực hiện thử tác vụ với người dùng: bắt đầu chuyến đi, tìm điểm ngày cuối, kiểm tra nguồn, yêu cầu đổi giờ, lưu snapshot. Ghi thời gian và lỗi trước–sau; hiện chưa có dữ liệu chứng minh tăng chuyển đổi hoặc giảm thời gian tác vụ.

## Kết quả triển khai P0 và điều hướng ngày P1 — 2026-11-20

- Landing mobile đưa nhóm đăng nhập lên trước phần giới thiệu; CTA Google nằm
  trong viewport đầu 390×844. Năm bước hướng dẫn và VI/EN vẫn có.
- Header lịch trình nhóm điểm đến, ngày, số ngày và nút lưu snapshot. Lưu vẫn
  là thao tác rõ ràng, kèm mô tả snapshot chỉ đọc và phản hồi lần lưu.
- Lịch 2–7 ngày có liên kết bàn phím tới từng ngày; lịch một ngày không có
  điều hướng phụ. Vùng đích có scroll margin dưới header sticky.
- Fallback ảnh thiếu được thu gọn. Ảnh thật cùng tác giả, giấy phép, trang ảnh,
  nguồn điểm đến, thời lượng ước tính và giờ chưa xác minh được giữ nguyên.
- English singular/plural và các vùng bấm đổi ngôn ngữ/calendar đạt 44px.
- Kiểm tra pending-turn xác nhận đổi ngôn ngữ giữ lịch và lượt đang chạy.

`npm run check`, `npm run build`, `git diff --check` và 17 mocked Chromium
checks passed. Screenshot tại 390/768/1024/1440px được tạo; landing và
itinerary đã được xem trực tiếp ở 390/1440px. API giả lập; không kiểm chứng
Auth0, provider, owner-isolation hoặc production. Chat dock, tinh chỉnh tour
lưu/tài khoản/admin và thay đổi motion P2 chưa triển khai.

## Trạng thái kiểm tra của lượt nghiên cứu

- Đạt: đọc source/contract; tìm kiếm và đọc các nguồn bên ngoài; 10 mocked Chromium checks; xem ảnh landing/itinerary mobile và desktop.
- Chưa chạy: review hình ảnh sâu chat, tour lưu, tài khoản/admin; live Auth0/provider/production. Đây là giới hạn bằng chứng, không phải kết quả đạt.
- Không áp dụng: full Python suite và frontend build vì không thay source ứng dụng; commit/push/deploy không thuộc lượt nghiên cứu.
