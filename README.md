# Grounded Travel Planner

Một webapp gợi ý điểm tham quan và lịch trình theo địa điểm/thành phố, ngày bắt
đầu và số ngày. AI tìm thông tin qua Tavily; người dùng chat để sửa ngày giờ,
đổi thứ tự, thêm, bỏ hoặc thay điểm tham quan.

Yêu cầu mới ngày **2026-10-14** thay thế toàn bộ scope POC trước đây. Tài liệu
hiện hành là [product charter](docs/project-charter.md) và
[kế hoạch triển khai](docs/implementation-plan.md). Chưa có deadline mới.

## Phạm vi và stack AI đã chốt

| Thành phần | Vai trò |
|---|---|
| LangChain | Tích hợp model, agents, tools và output có cấu trúc |
| LangGraph | State, định tuyến, bàn giao và giới hạn vòng sửa |
| Tavily | Tìm thông tin và nguồn cho các điểm tham quan |
| LangSmith | Trace toàn bộ lượt chat, agent và tool calls, nhóm theo phiên |
| `gpt-5.5` | Model dùng chung cho Coordinator và Planner |

Bản đầu có hai agent: **Coordinator** chat với người dùng, hỏi lại, giao tác vụ
và giải thích kết quả; **Planner** tìm thông tin, đề xuất và cập nhật lịch trình.
Kiểm tra ngày giờ và nguồn dùng code trước khi áp dụng bản lịch mới.

Lịch trình và hội thoại chỉ tồn tại trong phiên app hiện tại. Trace được gửi
đến LangSmith và có thể còn sau khi phiên kết thúc; app không dùng trace để
khôi phục chuyến đi. Streamlit là đề xuất giao diện một trang có form, lịch
trình và chat.

## Trạng thái thực tế

Đã ghi nhận yêu cầu, kiến trúc, các bước triển khai và cấu hình mẫu. Repository
có Python development tooling cùng hook tests; chưa có application package,
hai runtime agents, Tavily integration, webapp hoặc LangSmith trace chạy thật.
Xem [PROJECT_STATUS.md](PROJECT_STATUS.md) để tiếp tục từ đúng trạng thái.

## Tài liệu hiện hành

- [Product charter và acceptance scenarios](docs/project-charter.md)
- [Kế hoạch triển khai ba bước và kiến trúc hai agent](docs/implementation-plan.md)
- [Đề xuất giao diện](docs/ui-plan.md)
- [ADR 0004: Scope mới và stack AI](docs/adr/0004-city-sightseeing-webapp.md)
- [Learning log hiện tại](docs/learning-log/2026-10-14-scope-reset.md)
- [Roadmap](docs/roadmap.html) và [progress JSON](docs/progress/roadmap-progress.json)
- [Hướng dẫn cho Codex](AGENTS.md)
- [Tài liệu lịch sử đã thay thế](docs/archive/2026-10-14/README.md)

## Cấu hình và phát triển

[.env.example](.env.example) liệt kê cấu hình model, Tavily và LangSmith.
Điền cấu hình thực tế vào file `.env` được Git ignore. Cấu hình mẫu không xác
nhận tài khoản đã có quyền truy cập model hoặc các provider.

Development tooling hiện có dùng Python `>=3.10`, `uv`, `pytest`, isort,
Black, flake8 và Ruff. Các lệnh kiểm tra:

```bash
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
```

Lệnh chạy webapp sẽ được bổ sung khi entrypoint và runtime dependencies đã
được triển khai. Các Codex development agents trong `.codex/` hỗ trợ phát triển;
chúng tách biệt với Coordinator/Planner của webapp. Tooling được ghi ở
[ADR 0001](docs/adr/0001-python-development-tooling.md).

Một prompt tiếp tục phù hợp:

```text
Đọc AGENTS.md, PROJECT_STATUS.md, docs/project-charter.md,
docs/implementation-plan.md và docs/learning-log/2026-10-14-scope-reset.md.
Triển khai bước chưa hoàn thành đầu tiên của kế hoạch mới.
```
