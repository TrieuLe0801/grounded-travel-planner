# Travel Planner — Yêu cầu mới

Ngày cập nhật: 2026-10-14

Tài liệu này ghi nhận yêu cầu mới từ cuộc trao đổi hiện tại. Kế hoạch POC cũ
không được kế thừa làm ràng buộc cho sản phẩm này. Stack AI đã chốt gồm
LangChain, LangGraph, LangSmith, Tavily và model `gpt-5.5`. Chưa bắt đầu viết
code ứng dụng.

## Mục tiêu

Một webapp đơn giản giúp người dùng khám phá các điểm tham quan và nhận lịch
trình tại một địa điểm hoặc thành phố. AI tìm kiếm thông tin trước khi gợi ý;
người dùng tham khảo kết quả và chat để chỉnh sửa lịch trình.

## Các quyết định đã chốt

### Đầu vào ban đầu

- Địa điểm hoặc thành phố muốn tham quan.
- Ngày bắt đầu cụ thể.
- Số ngày tham quan do người dùng nhập.

### Luồng sử dụng

1. Người dùng nhập ba thông tin trên và yêu cầu tạo lịch trình.
2. AI tìm kiếm thông tin về các điểm tham quan phù hợp.
3. App trình bày các điểm gợi ý và một lịch trình theo từng ngày, có giờ dự kiến.
4. Người dùng chat để thay đổi ngày giờ, sắp xếp lại, thêm, bỏ hoặc thay điểm
   tham quan.
5. App cập nhật lịch trình đang xem và kiểm tra lại phần bị ảnh hưởng.

### Phạm vi chỉnh sửa qua chat

- Đổi ngày hoặc giờ tham quan một điểm.
- Chuyển thứ tự hoặc chuyển một điểm sang ngày khác.
- Thêm điểm tham quan vào lịch trình.
- Bỏ điểm không muốn ghé.
- Thay một điểm bằng điểm khác theo yêu cầu.
- AI tìm kiếm thông tin và nguồn cho điểm mới được thêm hoặc thay thế.
- Lịch trình sau chỉnh sửa vẫn phải phù hợp với ngày bắt đầu và số ngày hiện
  tại; yêu cầu thay đổi phạm vi ngày mơ hồ cần được hỏi lại.

### Kết quả

- Các điểm gợi ý và lý do nên ghé.
- Lịch trình theo ngày thực tế, với giờ bắt đầu và thời lượng dự kiến.
- Khoảng nghỉ và thời gian di chuyển dự kiến.
- Đường dẫn nguồn từ kết quả tìm kiếm.
- Thông tin còn thiếu, chưa xác minh hoặc xung đột ảnh hưởng đến lịch trình.

### Phiên sử dụng

- Lịch trình và lịch sử chat chỉ được giữ trong phiên hiện tại.
- Kết thúc hoặc mất phiên có thể làm mất lịch trình và hội thoại.
- Bản đầu không có chức năng lưu chuyến đi để mở lại hoặc tiếp tục chat ở phiên
  sau. Giao diện cần thông báo rõ hành vi này.
- LangSmith nhận trace các lượt hội thoại để phục vụ quan sát và gỡ lỗi. Trace
  có thể tồn tại sau khi phiên app kết thúc theo cấu hình lưu giữ của LangSmith;
  app không dùng trace để khôi phục chuyến đi hoặc hội thoại ở phiên mới.

### Stack AI và các agent

- LangChain tích hợp model, tool và dữ liệu trả về có cấu trúc.
- LangGraph quản lý state và điều phối các bước xử lý.
- Tavily là công cụ tìm kiếm thông tin tham quan.
- LangSmith trace toàn bộ lượt chat, các agent và tool calls, nhóm theo phiên.
- Hai agent dùng chung model `gpt-5.5`.
- Webapp có ít nhất hai agent khi vận hành. Bản đầu đề xuất đúng hai agent với
  trách nhiệm như sau:

| Agent | Trách nhiệm |
|---|---|
| Coordinator | Chat thông thường, hiểu yêu cầu, hỏi lại khi cần, giao việc cho Planner và giải thích kết quả |
| Planner | Tìm thông tin qua Tavily, đề xuất lịch trình và tạo bản lịch trình cập nhật khi người dùng yêu cầu |

Coordinator là đầu mối giao tiếp với người dùng. Planner nhận yêu cầu cùng dữ
liệu chuyến đi hiện tại và trả kết quả có cấu trúc về Coordinator. Mọi thay đổi
lịch trình đi qua Planner và bước kiểm tra bằng code trước khi được áp dụng.

## Nguyên tắc chất lượng tối thiểu

- AI phải thực sự tìm kiếm trước khi trình bày kết quả như thông tin có nguồn.
- Đường dẫn nguồn phải xuất phát từ kết quả tìm kiếm, không được tự bịa.
- Thời lượng tham quan và thời gian di chuyển ước tính phải được ghi rõ.
- Thiếu dữ liệu giờ mở cửa phải được thể hiện là chưa xác minh.
- Khi phát hiện lịch bị trùng giờ hoặc trái với giờ mở cửa đã tìm được, app báo
  xung đột và đưa phương án điều chỉnh; không âm thầm coi yêu cầu sửa là khả thi.
- Chat phải cập nhật lịch trình hiện tại. Lịch cũ chưa đáp ứng yêu cầu mới không
  được hiển thị như kết quả đã sửa thành công.
- Khi thêm, bỏ hoặc thay điểm, phần lịch liên quan được sắp xếp lại và nguồn
  được gắn đúng với các điểm còn trong lịch trình.
- Kết quả giúp người dùng tham khảo và không bảo đảm tình trạng hoạt động hoặc
  khả năng di chuyển tại thời điểm chuyến đi.

## Các tình huống cần kiểm chứng

1. Nhập địa điểm, ngày bắt đầu và số ngày hợp lệ: nhận lịch trình tương ứng kèm
   các nguồn đã tìm được.
2. Chat chuyển một điểm sang ngày hoặc giờ khác: lịch trình hiển thị cập nhật
   và phần thời gian liên quan được kiểm tra lại.
3. Chat thêm một điểm: app tìm thông tin và nguồn rồi đưa điểm vào lịch trình.
4. Chat bỏ một điểm: điểm đó được bỏ khỏi lịch trình hiển thị và phần lịch liên
   quan được điều chỉnh.
5. Chat thay một điểm: điểm cũ được thay bằng điểm mới có nguồn tương ứng.
6. Yêu cầu sửa gây xung đột với dữ liệu đã biết: app giải thích và đề xuất cách
   điều chỉnh.
7. Không tìm đủ thông tin hoặc tìm kiếm lỗi: app nêu rõ giới hạn dữ liệu,
   không tự tạo nguồn hoặc thông tin xác nhận.
8. Input hoặc yêu cầu chat mơ hồ: app hỏi lại thông tin cần thiết để tiếp tục.
9. Phiên mới bắt đầu với lịch trình và chat trống; các phiên không dùng chung
   dữ liệu chuyến đi.
10. Chat thông thường được Coordinator trả lời và không làm thay đổi lịch
    trình hoặc gọi Planner/Tavily khi không cần.
11. Tạo hoặc sửa lịch trình được giao cho Planner; lỗi hoặc kết quả không hợp
    lệ không được báo như đã cập nhật thành công.
12. Các lượt chat trong cùng phiên, bao gồm child runs của hai agent và Tavily,
    xuất hiện dưới cùng mã phiên trong LangSmith khi chạy thử tích hợp thật.

## Đề xuất thiết kế, chưa phải quyết định đã chốt

- Một trang gồm form nhập yêu cầu, lịch trình hiện tại và vùng chat.
- Mỗi lịch trình tập trung vào một thành phố hoặc khu vực cụ thể.

## Cấu trúc triển khai tối thiểu đề xuất

1. Giao diện: form, lịch trình theo ngày và vùng chat.
2. Coordinator và Planner dùng LangChain, được điều phối bằng LangGraph.
3. Tavily cung cấp kết quả và URL nguồn cho Planner.
4. Kiểm tra bằng code: input hợp lệ, lịch không trùng giờ, các điểm nằm trong
   phạm vi ngày và các nguồn tham chiếu thực sự tồn tại trong kết quả tìm kiếm.
5. LangSmith trace từng lượt xử lý với cùng mã phiên được truyền xuyên suốt.

Một bản lịch trình có cấu trúc trong state là dữ liệu chính dùng để hiển thị
và cập nhật. Mỗi agent có prompt và trách nhiệm riêng; hai agent có thể dùng
chung model mà vẫn giữ vai trò tách biệt. Kiểm tra ngày giờ và nguồn là code.

## Trạng thái yêu cầu

Các lựa chọn sản phẩm chính đã chốt: đầu vào có ngày bắt đầu và số ngày, AI tìm
kiếm trước khi gợi ý, chat có thể thêm/bỏ/thay điểm và sửa ngày giờ, dữ liệu chỉ
tồn tại trong phiên hiện tại. Stack AI và model đã chốt như trên. Kế hoạch
kiến trúc hai agent nằm tại `docs/implementation-plan.md`; Streamlit vẫn là đề xuất
cho giao diện một trang.

## Trạng thái triển khai

Hiện có tài liệu yêu cầu. Chưa có code ứng dụng, dữ liệu tìm kiếm thực tế hoặc
kết quả kiểm thử ứng dụng trong repository này.
