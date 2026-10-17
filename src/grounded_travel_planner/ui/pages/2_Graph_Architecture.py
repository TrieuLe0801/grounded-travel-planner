"""Read-only architecture inspection page for the compiled LangGraph workflow."""

from __future__ import annotations

import streamlit as st

from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.graph_diagram import (
    compiled_graph_svg,
    topology_from_compiled_graph,
)


@st.cache_resource
def get_service() -> TravelPlannerService:
    """Build clients and compile the graph without invoking model or search tools."""

    return TravelPlannerService.from_environment()


@st.cache_data(show_spinner="Đang tạo ảnh kiến trúc graph...")
def get_graph_image() -> bytes:
    """Cache the static compiled-graph image across page reruns."""

    return get_service().get_graph_image()


def main(service: TravelPlannerService | None = None) -> None:
    """Show the current executable topology without changing session plan state."""

    st.set_page_config(page_title="Kiến trúc LangGraph", layout="wide")
    st.title("Kiến trúc LangGraph")
    st.caption(
        "Ảnh PNG chỉ đọc được LangGraph/Mermaid tạo từ workflow đã biên dịch. "
        "Trang này không gọi model, Tavily hoặc LangSmith và không thay đổi "
        "lịch trình trong phiên."
    )
    runtime_service = service or get_service()
    nodes, edges = topology_from_compiled_graph(runtime_service.graph)

    try:
        graph_image = (
            runtime_service.get_graph_image()
            if service is not None
            else get_graph_image()
        )
    except Exception:  # noqa: BLE001 - keep diagnostics available if render API fails
        svg = compiled_graph_svg(runtime_service.graph)
        st.warning(
            "Không thể tạo ảnh PNG qua Mermaid lúc này; đang hiển thị bản SVG dự phòng."
        )
        st.image(
            svg,
            output_format="SVG",
            width="stretch",
            alt="Sơ đồ graph gồm Bắt đầu, Coordinator, các bước kiểm tra, Planner, "
            "vòng sửa, Chat và Kết thúc.",
        )
        st.download_button(
            "Tải sơ đồ SVG",
            data=svg,
            file_name="grounded-travel-planner-langgraph.svg",
            mime="image/svg+xml",
        )
    else:
        st.image(
            graph_image,
            width="stretch",
            alt="Ảnh graph do LangGraph tạo từ workflow đã biên dịch.",
        )
        st.download_button(
            "Tải ảnh graph PNG",
            data=graph_image,
            file_name="grounded-travel-planner-langgraph.png",
            mime="image/png",
        )

    agent_count = sum(node.kind == "agent" for node in nodes)
    conditional_count = sum(edge.conditional for edge in edges)
    metrics = st.columns(3)
    metrics[0].metric("Runtime agents", agent_count)
    metrics[1].metric("Nút workflow", len(nodes))
    metrics[2].metric("Nhánh điều kiện", conditional_count)

    st.subheader("Cách đọc sơ đồ")
    st.markdown(
        "- **Coordinator** phân loại và chuyển lượt tới Planner hoặc Chat.\n"
        "- **Planner** là agent duy nhất tìm kiếm và đề xuất ứng viên.\n"
        "- **Chat** tạo phản hồi sau khi kết quả đã được kiểm tra; Chat không "
        "thay đổi lịch.\n"
        "- Ứng viên lỗi có tối đa một vòng **Chuẩn bị sửa → Planner**; mọi nhánh "
        "khác đều đi đến **Chat** để trả kết quả và giữ an toàn cho lịch hiện tại."
    )

    with st.expander("Dữ liệu topology đã đọc từ LangGraph"):
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
