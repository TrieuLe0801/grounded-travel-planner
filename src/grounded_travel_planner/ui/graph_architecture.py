"""Read-only architecture inspection page for the compiled LangGraph workflow."""

from __future__ import annotations

import streamlit as st

from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.graph_diagram import (
    compiled_graph_svg,
    topology_from_compiled_graph,
)

_TEXT = {
    "vi": {
        "page": "Kiến trúc LangGraph",
        "language": "Ngôn ngữ",
        "description": "Sơ đồ SVG chỉ đọc được tạo cục bộ từ workflow đã biên dịch. Trang này không gọi model, Tavily, LangSmith hoặc dịch vụ render bên ngoài và không thay đổi lịch trình trong phiên.",
        "alt": "Sơ đồ graph gồm Bắt đầu, Coordinator, các bước kiểm tra, Planner, vòng sửa, Chat và Kết thúc.",
        "download_svg": "Tải sơ đồ SVG",
        "agents": "Runtime agents",
        "nodes": "Nút workflow",
        "branches": "Nhánh điều kiện",
        "read": "Cách đọc sơ đồ",
        "topology": "Dữ liệu topology đã đọc từ LangGraph",
        "guide": "- **Coordinator** phân loại và chuyển lượt tới Planner hoặc Chat.\n- **Planner** đề xuất thay đổi lịch; Planner và Chat yêu cầu tìm kiếm qua nút Tavily chung.\n- **Chat** tạo phản hồi sau khi kết quả đã được kiểm tra; Chat không thay đổi lịch.\n- Ứng viên lỗi có tối đa một vòng **Chuẩn bị sửa → Planner**; mọi nhánh khác đều đi đến **Chat** để trả kết quả và giữ an toàn cho lịch hiện tại.",
    },
    "en": {
        "page": "LangGraph architecture",
        "language": "Language",
        "description": "This read-only SVG is rendered locally from the compiled workflow. The page does not call models, Tavily, LangSmith or an external rendering service, and does not change the session itinerary.",
        "alt": "Graph diagram with Start, Coordinator, validation steps, Planner, repair loop, Chat, and End.",
        "download_svg": "Download SVG diagram",
        "agents": "Runtime agents",
        "nodes": "Workflow nodes",
        "branches": "Conditional branches",
        "read": "How to read the diagram",
        "topology": "Topology data read from LangGraph",
        "guide": "- **Coordinator** classifies and routes a turn to Planner or Chat.\n- **Planner** proposes itinerary changes; Planner and Chat request search through the shared Tavily node.\n- **Chat** writes the response after results are checked; Chat cannot change the itinerary.\n- A failed candidate has at most one **Prepare repair → Planner** loop; all other branches go to **Chat** to respond while retaining the current itinerary.",
    },
}


def _labels() -> dict[str, str]:
    return _TEXT[st.session_state.get("language", "vi")]


@st.cache_resource
def get_service() -> TravelPlannerService:
    """Build clients and compile the graph without invoking model or search tools."""

    return TravelPlannerService.from_environment()


def main(service: TravelPlannerService | None = None) -> None:
    """Show the current executable topology without changing session plan state."""

    labels = _labels()
    st.set_page_config(page_title=labels["page"], layout="wide")
    st.selectbox(
        labels["language"],
        options=("vi", "en"),
        format_func=lambda value: "Tiếng Việt" if value == "vi" else "English",
        index=0 if st.session_state.get("language", "vi") == "vi" else 1,
        key="language",
    )
    labels = _labels()
    st.title(labels["page"])
    st.caption(labels["description"])
    runtime_service = service or get_service()
    nodes, edges = topology_from_compiled_graph(runtime_service.graph)

    svg = compiled_graph_svg(runtime_service.graph)
    st.image(
        svg,
        output_format="SVG",
        width="stretch",
        alt=labels["alt"],
    )
    st.download_button(
        labels["download_svg"],
        data=svg,
        file_name="grounded-travel-planner-langgraph.svg",
        mime="image/svg+xml",
    )

    agent_count = sum(node.kind == "agent" for node in nodes)
    conditional_count = sum(edge.conditional for edge in edges)
    metrics = st.columns(3)
    metrics[0].metric(labels["agents"], agent_count)
    metrics[1].metric(labels["nodes"], len(nodes))
    metrics[2].metric(labels["branches"], conditional_count)

    st.subheader(labels["read"])
    st.markdown(labels["guide"])

    with st.expander(labels["topology"]):
        st.json(
            {
                "nodes": [node.identifier for node in nodes],
                "edges": [
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "conditional": edge.conditional,
                    }
                    for edge in edges
                ],
            }
        )


if __name__ == "__main__":
    main()
