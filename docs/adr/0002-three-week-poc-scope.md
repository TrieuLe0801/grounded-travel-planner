# ADR 0002: Rebaseline thành POC 3 tuần

Date: 2026-09-22
Status: Superseded by ADR 0004 on 2026-10-14

This is a historical decision. Use [ADR 0004](0004-city-sightseeing-webapp.md)
and the [current implementation plan](../implementation-plan.md) for new work.

## Context

Roadmap ban đầu có Week 0 và tám tuần triển khai. Thời gian hiện có được rút còn
ba tuần. Repository đã có charter và policy artifacts nhưng chưa có executable
code, tests, fixtures hoặc metrics. Nếu tiếp tục toàn bộ roadmap cũ, dự án khó có
vertical slice đủ ổn định để demo trong deadline.

## Decision

- Tập trung vào một deterministic single-graph vertical slice.
- Dùng một primary offline fixture journey TP.HCM → Đà Nẵng, 3 ngày.
- Dùng structured JSON/Python input và CLI fallback.
- Giữ input, budget, evidence, citation và bounded-loop invariants.
- Chỉ yêu cầu một recommended plan thay vì nhiều alternatives.
- Dùng offline tests/evaluation làm acceptance path; model call thật là optional.
- Đưa multi-agent, long-term memory, live providers, Chainlit/FastAPI/full UI,
  persistent storage, accessibility/dietary support, Docker/CI và expanded
  evaluation sang post-POC.

ADR 0003 later adds one minimal Streamlit page to P0 without changing the
single-graph or fixture-first boundaries.

Kế hoạch chi tiết và stop rules nằm tại `docs/poc-3-week-plan.md`.

## Alternatives considered

### Giữ roadmap tám tuần và cố hoàn thành nhanh hơn

Rejected vì tạo quá nhiều workstream song song và không phản ánh trạng thái
greenfield hiện tại.

### Chỉ làm một notebook minh họa LangGraph

Rejected vì không đủ bằng chứng về testability, constraints, evidence và khả
năng lặp lại của POC.

### Dùng live providers ngay từ đầu

Rejected vì authentication, rate limits, terms of use, freshness và lỗi mạng sẽ
chiếm phần lớn thời gian ba tuần mà không trực tiếp kiểm chứng orchestration.

## Consequences

### Positive

- Có khả năng đạt một demo end-to-end trong ba tuần.
- Tests và evaluation deterministic, không phụ thuộc API key hoặc network.
- Các failure paths chính của LangGraph vẫn quan sát và kiểm thử được.

### Negative

- POC không chứng minh độ chính xác của dữ liệu du lịch thật.
- Không kết luận được lợi ích multi-agent hoặc long-term memory.
- Minimal Streamlit/CLI và fixture data không đại diện cho production UX hoặc
  architecture.

## Review triggers

Review ADR sau POC hoặc sớm hơn nếu một trong các điều kiện sau xảy ra:

- deadline hoặc số giờ khả dụng thay đổi đáng kể;
- P0 hoàn thành sớm ít nhất bốn ngày;
- stakeholder yêu cầu live provider, full UI hoặc deployment làm acceptance
  gate.
