"""Render the compiled LangGraph topology as a self-contained SVG."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html import escape
from typing import Any

START_NODE = "__start__"
END_NODE = "__end__"


@dataclass(frozen=True)
class DiagramNode:
    """A visible node copied from LangGraph's compiled graph representation."""

    identifier: str
    label: str
    description: str
    kind: str


@dataclass(frozen=True)
class DiagramEdge:
    """A visible edge copied from LangGraph's compiled graph representation."""

    source: str
    target: str
    conditional: bool


_NODE_TEXT = {
    START_NODE: ("BẮT ĐẦU", "Nhận một lượt yêu cầu", "boundary"),
    "coordinator_route": (
        "Coordinator",
        "Phân loại yêu cầu và quyết định có cần Planner",
        "agent",
    ),
    "planner_prepare": (
        "Planner yêu cầu tool",
        "Tạo yêu cầu Tavily có giới hạn cho Planner khi cần",
        "agent",
    ),
    "tavily_tool": (
        "Tavily tool",
        "Một node chung tìm kiếm cho Planner và Chat",
        "validation",
    ),
    "planner_delegate": (
        "Planner",
        "Nhận nguồn từ tool và đề xuất lịch trình ứng viên",
        "agent",
    ),
    "validate_candidate": (
        "Kiểm tra ứng viên",
        "Kiểm tra lịch, nguồn và thay đổi được yêu cầu",
        "validation",
    ),
    "chat_respond": (
        "Chat",
        "Phản hồi tiếng Việt và chỉ commit khi kiểm tra đạt",
        "finalize",
    ),
    END_NODE: ("KẾT THÚC", "Kết thúc lượt xử lý", "boundary"),
}

_POSITIONS = {
    START_NODE: (90, 300),
    "coordinator_route": (275, 300),
    "planner_prepare": (510, 145),
    "tavily_tool": (750, 145),
    "planner_delegate": (990, 145),
    "validate_candidate": (1230, 145),
    "chat_respond": (1230, 370),
    END_NODE: (1415, 370),
}

_COLORS = {
    "agent": ("#E5EEFF", "#245DAA"),
    "validation": ("#E4F6EE", "#19734C"),
    "repair": ("#FFF0DB", "#B45309"),
    "finalize": ("#F0E8FF", "#6941C6"),
    "boundary": ("#F2F4F7", "#667085"),
}


def _node_text(identifier: str) -> tuple[str, str, str]:
    """Return a Vietnamese label while retaining unknown graph nodes visibly."""

    return _NODE_TEXT.get(
        identifier,
        (identifier.replace("_", " "), "Nút do graph biên dịch cung cấp", "boundary"),
    )


def topology_from_compiled_graph(
    compiled_graph: Any,
) -> tuple[list[DiagramNode], list[DiagramEdge]]:
    """Copy nodes and edges from LangGraph without invoking the workflow."""

    graph = compiled_graph.get_graph()
    nodes = [
        DiagramNode(identifier, *_node_text(identifier)) for identifier in graph.nodes
    ]
    edges = [
        DiagramEdge(edge.source, edge.target, bool(edge.conditional))
        for edge in graph.edges
    ]
    return nodes, edges


def _position(identifier: str, index: int, total: int) -> tuple[int, int]:
    if identifier in _POSITIONS:
        return _POSITIONS[identifier]
    return (240 + (index % 5) * 240, 110 + (index // 5) * 180)


def _edge_path(
    source: tuple[int, int], target: tuple[int, int], *, conditional: bool
) -> str:
    """Use curves for branch and repair paths so concurrent routes remain visible."""

    source_x, source_y = source
    target_x, target_y = target
    direction = 1 if target_x >= source_x else -1
    start_x = source_x + direction * 86
    end_x = target_x - direction * 86
    if source_y == target_y:
        return f"M {start_x} {source_y} L {end_x} {target_y}"
    bend = 120 if conditional else 70
    return (
        f"M {start_x} {source_y} C {start_x + direction * bend} {source_y}, "
        f"{end_x - direction * bend} {target_y}, {end_x} {target_y}"
    )


def _edge_label(edge: DiagramEdge) -> str:
    if edge.conditional:
        return "nhánh điều kiện"
    if edge.target == "tavily_tool":
        return "gọi tool"
    if edge.source == "tavily_tool":
        return "trả nguồn"
    return "luồng xử lý"


def _wrapped_lines(value: str, width: int = 27) -> list[str]:
    """Wrap node descriptions for the fixed-width SVG cards."""

    lines: list[str] = []
    current: list[str] = []
    for word in value.split():
        candidate = " ".join([*current, word])
        if current and len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _render_edges(
    edges: Iterable[DiagramEdge], positions: dict[str, tuple[int, int]]
) -> str:
    rendered: list[str] = []
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        dash = ' stroke-dasharray="8 7"' if edge.conditional else ""
        path = _edge_path(
            positions[edge.source], positions[edge.target], conditional=edge.conditional
        )
        label = escape(_edge_label(edge))
        source_x, source_y = positions[edge.source]
        target_x, target_y = positions[edge.target]
        label_x = (source_x + target_x) / 2
        label_y = (source_y + target_y) / 2 - 12
        rendered.append(
            f'<path d="{path}" class="edge"{dash} marker-end="url(#arrow)" />'
            f'<text class="edge-label" x="{label_x}" y="{label_y}">{label}</text>'
        )
    return "".join(rendered)


def render_topology_svg(
    nodes: Iterable[DiagramNode], edges: Iterable[DiagramEdge]
) -> str:
    """Render a stable, accessible SVG of a LangGraph topology."""

    node_list = list(nodes)
    edge_list = list(edges)
    positions = {
        node.identifier: _position(node.identifier, index, len(node_list))
        for index, node in enumerate(node_list)
    }
    rendered_nodes: list[str] = []
    for node in node_list:
        x, y = positions[node.identifier]
        fill, stroke = _COLORS.get(node.kind, _COLORS["boundary"])
        title = escape(f"{node.label}: {node.description}")
        description_lines = "".join(
            f'<tspan x="{x}" dy="{0 if index == 0 else 14}">{escape(line)}</tspan>'
            for index, line in enumerate(_wrapped_lines(node.description))
        )
        rendered_nodes.append(
            f'<g class="node"><title>{title}</title>'
            f'<rect x="{x - 86}" y="{y - 43}" width="172" height="86" '
            f'rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2" />'
            f'<text class="node-title" x="{x}" y="{y - 18}">{escape(node.label)}</text>'
            f'<text class="node-description" x="{x}" y="{y + 2}">'
            f"{description_lines}</text></g>"
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="600" viewBox="0 0 1500 600" role="img" aria-labelledby="diagram-title diagram-description">
  <title id="diagram-title">Kiến trúc LangGraph của Trợ lý lập lịch tham quan</title>
  <desc id="diagram-description">Sơ đồ lấy từ graph LangGraph đã biên dịch. Đường nét đứt là nhánh điều kiện; đường liền là luồng cố định.</desc>
  <style>
    .edge {{ fill: none; stroke: #667085; stroke-width: 2.5; }}
    .edge-label {{ fill: #475467; font: 500 13px sans-serif; text-anchor: middle; }}
    .node-title {{ fill: #101828; font: 700 16px sans-serif; text-anchor: middle; }}
    .node-description {{ fill: #344054; font: 12px sans-serif; text-anchor: middle; }}
  </style>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#667085" /></marker></defs>
  <rect width="1500" height="600" fill="#FFFFFF" />
  {_render_edges(edge_list, positions)}
  {''.join(rendered_nodes)}
</svg>"""


def compiled_graph_svg(compiled_graph: Any) -> str:
    """Build an SVG directly from an already compiled LangGraph workflow."""

    nodes, edges = topology_from_compiled_graph(compiled_graph)
    return render_topology_svg(nodes, edges)
