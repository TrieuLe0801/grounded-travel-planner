# Project Status

Last updated: 2026-10-14

## Current milestone

Yêu cầu và kế hoạch mới đã được ghi vào repository. Bước tiếp theo là triển
khai luồng tạo lịch trình có tìm kiếm thật với hai agent.

Active plan: [docs/implementation-plan.md](docs/implementation-plan.md).
Active charter: [docs/project-charter.md](docs/project-charter.md).
Current log: [2026-10-14-scope-reset.md](docs/learning-log/2026-10-14-scope-reset.md).

Scope, deadline và số liệu tiến độ của POC cũ đã được thay thế. Chưa chốt
deadline mới; tiến độ triển khai mới không kế thừa các mục đã đánh dấu của
roadmap cũ.

## Done

- Ghi nhận đầu vào: địa điểm/thành phố, ngày bắt đầu, số ngày.
- Chốt AI tìm kiếm trước khi gợi ý; chat sửa ngày giờ, đổi thứ tự, thêm/bỏ/thay điểm.
- Chốt LangChain, LangGraph, Tavily, LangSmith và `gpt-5.5` cho hai runtime agents.
- Chốt state app chỉ trong phiên; trace LangSmith dùng cho quan sát.
- Đồng bộ charter, kế hoạch, UI proposal, ADR 0004, README và hướng dẫn Codex.
- Thay roadmap/progress hiện hành; giữ snapshot kế hoạch trước trong archive.
- Thêm `.env.example`; giữ nguyên `.env` và development tooling sẵn có.

## Implementation status

| Bước | Trạng thái | Bằng chứng hiện có |
|---|---|---|
| 1. Hai agent, graph, Tavily và tạo lịch trình | Chưa triển khai | Kế hoạch và acceptance scenarios |
| 2. Chỉnh sửa lịch trình qua chat | Chưa triển khai | Phạm vi thao tác đã chốt |
| 3. Webapp, cách ly phiên và kiểm chứng trace | Chưa triển khai | Đề xuất UI và tiêu chí kiểm chứng |

Development-hook tests không phải test của travel planner. Chưa có code
application, dữ liệu tìm kiếm thật hoặc live trace trong repository này.

## Now

1. Tạo application package và typed request/plan/source/state contracts.
2. Thêm runtime dependencies cho LangChain, LangGraph, model, Tavily và giao diện.
3. Tạo Coordinator và Planner với prompt/trách nhiệm riêng, dùng chung `gpt-5.5`.
4. Nối graph, Tavily, validation và tracing cho luồng tạo lịch trình đầu tiên.

## Next

- Thêm các thao tác chỉnh sửa bằng chat trên cùng state và luồng xử lý.
- Gắn giao diện một trang; giữ hội thoại và lịch trình theo từng phiên.
- Chạy kiểm thử offline bằng provider giả lập và smoke test với API thật riêng.
- Kiểm tra root/child traces nhóm đúng phiên trên LangSmith.

## Dependencies and limits

Quyền truy cập `gpt-5.5`, Tavily và LangSmith chưa được kiểm chứng trong công
việc cập nhật tài liệu này. Giao diện Streamlit và các giới hạn vòng gọi tool
trong kế hoạch là đề xuất triển khai. Thời gian di chuyển là ước tính khi chưa
có dữ liệu tuyến đường; giờ mở cửa phụ thuộc nguồn tìm được.

## Verification of this update

- Tài liệu: 61 liên kết nội bộ được kiểm tra; không có link thiếu đích.
- Progress JSON hợp lệ: 3 bước, 12 task triển khai đều chưa hoàn thành.
- Roadmap hiện hành không còn seed/localStorage hay task IDs của checklist cũ.
- Cấu hình mẫu dùng `gpt-5.5`, credential placeholders trống; `.env` được ignore
  và `.env.example` được phép theo dõi bằng Git.
- `uv lock --check`: passed.
- `uv run pytest`: 2 passed (development-hook tests).
- isort, Black, flake8 và Ruff theo lệnh chuẩn: passed.
- `git diff --check`: passed.
- Kiểm tra độc lập: passed; 65 links gồm tài liệu lịch sử hợp lệ, 5 archive
  snapshots khớp phiên bản trước và các quyết định đã chốt được giữ đầy đủ.

Application tests và live model/Tavily/LangSmith checks: N/A / chưa chạy vì
công việc này cập nhật kế hoạch, không triển khai ứng dụng.
