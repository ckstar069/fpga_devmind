"""Contextual node understanding agent for the Desktop Shell (T027).

Deterministic, rule-based answers about the currently-selected graph node.
No LLM, no API, no API key.  Pure Python; testable without PySide6.
"""

from __future__ import annotations

from typing import Any

from fpga_devmind.desktop.agent_panel_models import AgentPanelResponse
from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_project_graph,
    get_project_index,
)


def query_selected_node(
    bundle: ArtifactBundle,
    selected_node_id: str,
    selected_node_kind: str,
    selected_node_label: str,
    question: str,
) -> AgentPanelResponse:
    """Answer a question about the currently-selected graph node.

    Falls back to generic project-level query when no node is selected.
    """
    if not bundle.is_complete:
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="Bundle incomplete.",
        )

    if bundle.bundle_type != "project":
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="Contextual node query available for project bundles only.",
        )

    if not selected_node_id:
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="未选中任何节点。请在 Concept Graph 中点击一个节点。",
        )

    graph = get_project_graph(bundle)
    if graph is None:
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="Project understanding graph not found.",
        )

    index = get_project_index(bundle) or {}
    evidence_index = index.get("evidence_index", {}) if isinstance(index, dict) else {}

    # Dispatch by node kind.
    if selected_node_kind == "project":
        return _answer_project_node(graph, selected_node_label, question)

    if selected_node_kind == "concept":
        return _answer_concept_node(graph, selected_node_label, question, evidence_index)

    if selected_node_kind in ("mapping_claim", "claim"):
        return _answer_claim_node(graph, selected_node_id, selected_node_label, question, evidence_index)

    if selected_node_kind in ("rtl_module", "rtl_aggregate") or selected_node_kind.startswith("rtl_"):
        return _answer_rtl_node(graph, selected_node_id, selected_node_label, question, evidence_index)

    # Fallback: generic node info.
    lines = [
        "当前节点：{}（{}）".format(selected_node_label, selected_node_kind),
        "",
        "该节点类型的 contextual answer 尚未实现。",
        "可尝试在 Agent 问答页输入全局问题。",
    ]
    return AgentPanelResponse(
        question=question,
        response_kind="contextual",
        answer_text="\n".join(lines),
        referenced_node_ids=[selected_node_id],
        is_loaded=True,
    )


def _answer_project_node(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    label: str,
    question: str,
) -> AgentPanelResponse:
    """Answer about a project node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    concept_count = sum(1 for n in raw_nodes if n.get("kind") == "concept")
    claim_count = sum(1 for n in raw_nodes if n.get("kind") == "mapping_claim")
    rtl_count = sum(1 for n in raw_nodes if str(n.get("kind", "")).startswith("rtl"))
    shared = sum(
        1 for e in raw_edges if e.get("edge_type") in ("shares_file", "shares_rtl_object")
    )
    unknowns = sum(
        1
        for n in raw_nodes
        if n.get("kind") == "concept" and n.get("confidence") == "unknown"
    )
    concepts = [n.get("label", "") for n in raw_nodes if n.get("kind") == "concept"]

    lines = [
        "当前节点：{}（project）".format(label),
        "",
        "这是项目级理解图的根节点。整体统计：",
        "  • 概念：{} 个".format(concept_count),
        "  • Mapping claims：{} 个".format(claim_count),
        "  • RTL 对象：{} 个".format(rtl_count),
        "  • 概念间共享关系：{} 条".format(shared),
        "  • 不确定概念：{} 个".format(unknowns),
    ]
    if concepts:
        lines.append("  • 概念列表：{}".format(", ".join(concepts)))
    lines.append("")
    lines.append(
        "💡 提示：shares_file / shares_rtl_object 边是 structural inferred，"
        "表示多个概念引用了同一 RTL 文件或对象，不等同于语义确认。"
    )

    return AgentPanelResponse(
        question=question,
        response_kind="contextual",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_concept_node(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    label: str,
    question: str,
    evidence_index: dict[str, Any] | None = None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer about a concept node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    node_by_id = {n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")}

    # Find the concept node.
    concept_node = next(
        (n for n in raw_nodes if n.get("kind") == "concept" and n.get("label") == label),
        None,
    )
    confidence = concept_node.get("confidence", "unknown") if concept_node else "unknown"

    # Find related claims.
    related_claims = [
        n for n in raw_nodes
        if n.get("kind") == "mapping_claim" and n.get("concept") == label
    ]
    claim_labels = [c.get("label", "") for c in related_claims]

    # Find related RTL targets via realizes edges from claims.
    related_rtls: set[str] = set()
    for e in raw_edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            from_node = node_by_id.get(from_id, {})
            if from_node.get("kind") == "mapping_claim" and from_node.get("concept") == label:
                to_node = node_by_id.get(to_id, {})
                to_label = to_node.get("label", "")
                if to_label:
                    related_rtls.add(to_label)

    # Find shared edges involving this concept.
    shared_with: list[str] = []
    for e in raw_edges:
        if e.get("edge_type") in ("shares_file", "shares_rtl_object"):
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            from_label = node_by_id.get(from_id, {}).get("label", "")
            to_label = node_by_id.get(to_id, {}).get("label", "")
            if from_label == label and to_label:
                shared_with.append(to_label)
            elif to_label == label and from_label:
                shared_with.append(from_label)

    lines = [
        "当前节点：{}（concept）".format(label),
        "",
        "{} 是当前项目识别出的一个概念节点。".format(label),
        "当前可信度：{}".format(confidence),
    ]

    if claim_labels:
        lines.append("相关 mapping claims：{}".format(", ".join(claim_labels)))
    if related_rtls:
        lines.append("映射到的 RTL 对象：{}".format(", ".join(sorted(related_rtls)[:10])))
        if len(related_rtls) > 10:
            lines.append("  ... 以及另外 {} 个".format(len(related_rtls) - 10))
    if shared_with:
        lines.append("与以下概念共享文件/RTL：{}".format(", ".join(sorted(set(shared_with))[:10])))
        if len(shared_with) > 10:
            lines.append("  ... 以及另外 {} 个".format(len(shared_with) - 10))

    lines.append("")
    if confidence == "supported":
        lines.append("该概念的 L5/L6 侧和 RTL 侧均有证据支撑，可信度较高。")
    elif confidence == "inferred":
        lines.append("该概念仅有命名匹配或单侧证据支撑，建议补充更多证据或人工 review。")
    elif confidence == "unknown":
        lines.append("该概念当前缺少足够证据，处于 unknown 状态。")

    # Top evidence summary (T029).
    ev_lines = _format_top_evidence_for_concept(related_claims, evidence_index)
    if ev_lines:
        lines.append("")
        lines.extend(ev_lines)

    lines.append("")
    lines.append(
        "💡 提示：在 Evidence 页面可按 claim 查看该概念的所有证据分组。"
        "点击节点详情中的「📄 证据」按钮可直接跳转到过滤后的 Evidence 页面。"
    )

    return AgentPanelResponse(
        question=question,
        response_kind="contextual",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_claim_node(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    node_id: str,
    label: str,
    question: str,
    evidence_index: dict[str, Any] | None = None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer about a mapping_claim node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    node_by_id = {n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")}

    claim_node = node_by_id.get(node_id, {})
    if not claim_node:
        # Fallback: search by label.
        claim_node = next(
            (n for n in raw_nodes if n.get("kind") == "mapping_claim" and n.get("label") == label),
            {},
        )

    concept = claim_node.get("concept", "")
    confidence = claim_node.get("confidence", "unknown")
    bridge = claim_node.get("bridge_kind", "unknown")

    # Find realizes edges from this claim.
    realizes_rtls: list[str] = []
    for e in raw_edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            if from_id == node_id or (from_id == claim_node.get("node_id", "") and claim_node):
                to_node = node_by_id.get(to_id, {})
                to_label = to_node.get("label", "")
                if to_label:
                    realizes_rtls.append(to_label)

    # Evidence count: use evidence_ids if present, else count realizes targets as proxy.
    evidence_count = 0
    ev_ids = claim_node.get("evidence_ids", [])
    if isinstance(ev_ids, list):
        evidence_count = len(ev_ids)
    if evidence_count == 0:
        evidence_count = len(realizes_rtls)

    # Missing evidence.
    missing = claim_node.get("required_missing_evidence", [])
    missing_list = missing if isinstance(missing, list) else []

    lines = [
        "当前节点：{}（mapping_claim）".format(label),
        "",
        "{} 是概念 '{}' 的映射声明。".format(label, concept),
        "可信度：{}".format(confidence),
        "桥接类型：{}".format(bridge),
    ]

    if realizes_rtls:
        lines.append("映射到的 RTL 对象：{}".format(", ".join(realizes_rtls[:10])))
        if len(realizes_rtls) > 10:
            lines.append("  ... 以及另外 {} 个".format(len(realizes_rtls) - 10))

    lines.append("证据数量：{}".format(evidence_count))

    if missing_list:
        lines.append("缺失证据：{}".format("; ".join(missing_list)))

    lines.append("")
    if confidence == "supported":
        lines.append(
            "该 claim 的可信度为 supported，说明 L5/L6 侧和 RTL 侧均有对应证据。"
        )
    elif confidence == "inferred":
        lines.append(
            "该 claim 的可信度为 inferred，通常基于命名匹配或单侧证据。"
            "建议补充更多实现证据或人工 review。"
        )
    elif confidence == "unknown":
        lines.append(
            "该 claim 的可信度为 unknown，缺少必要证据。"
        )
        if missing_list:
            lines.append("需要补充：{}".format("; ".join(missing_list)))

    # Top evidence summary (T029).
    ev_lines = _format_top_evidence_for_claim(claim_node, evidence_index)
    if ev_lines:
        lines.append("")
        lines.extend(ev_lines)

    lines.append("")
    lines.append(
        "💡 提示：在 Evidence 页面可按 claim 查看该声明的证据分组。"
        "点击节点详情中的「📄 证据」按钮可直接跳转到过滤后的 Evidence 页面。"
    )

    return AgentPanelResponse(
        question=question,
        response_kind="contextual",
        answer_text="\n".join(lines),
        referenced_claim_ids=[label],
        is_loaded=True,
    )


def _answer_rtl_node(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    node_id: str,
    label: str,
    question: str,
    evidence_index: dict[str, Any] | None = None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer about an rtl_module or rtl_aggregate node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    node_by_id = {n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")}

    rtl_node = node_by_id.get(node_id, {})
    if not rtl_node:
        rtl_node = next(
            (n for n in raw_nodes if str(n.get("kind", "")).startswith("rtl") and n.get("label") == label),
            {},
        )

    file_path = rtl_node.get("file_path", "")

    # Find which concepts/claims use this RTL (via realizes edges).
    related_concepts: set[str] = set()
    related_claims: set[str] = set()
    for e in raw_edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            if to_id == node_id:
                from_node = node_by_id.get(from_id, {})
                if from_node.get("kind") == "mapping_claim":
                    related_claims.add(from_node.get("label", ""))
                    related_concepts.add(from_node.get("concept", ""))

    # Count child evidence nodes if this is an aggregate.
    child_counts: dict[str, int] = {}
    for n in raw_nodes:
        if n.get("file_path") == file_path and n.get("node_id") != node_id:
            kind = n.get("kind", "")
            if kind in ("rtl_signal", "rtl_always_block", "rtl_assign", "rtl_comment"):
                child_counts[kind] = child_counts.get(kind, 0) + 1

    lines = [
        "当前节点：{}（RTL）".format(label),
        "",
        "{} 是 RTL 侧的模块/文件节点。".format(label),
    ]
    if file_path:
        lines.append("文件路径：{}".format(file_path))

    if related_concepts:
        lines.append("被概念使用：{}".format(", ".join(sorted(related_concepts))))
    if related_claims:
        lines.append("被 claims 引用：{}".format(", ".join(sorted(related_claims))))

    if child_counts:
        lines.append("包含的细粒度 RTL 对象：")
        for kind, count in sorted(child_counts.items()):
            lines.append("  • {}: {} 个".format(kind, count))

    lines.append("")
    if related_claims:
        lines.append(
            "该 RTL 对象被 mapping claim 引用，是 concept-to-RTL 映射的实现证据。"
        )
    else:
        lines.append(
            "该 RTL 对象当前未被任何 mapping claim 直接引用。"
            "可能通过 contains 关系被聚合到父模块中。"
        )

    # Top evidence summary (T029).
    raw_nodes_rtl = graph.get("nodes", [])
    raw_edges_rtl = graph.get("edges", [])
    node_by_id_rtl = {n.get("node_id", ""): n for n in raw_nodes_rtl if n.get("node_id")}
    related_claim_nodes = []
    for e in raw_edges_rtl:
        if e.get("edge_type") == "realizes" and e.get("to_node_id") == node_id:
            from_node = node_by_id_rtl.get(e.get("from_node_id", ""), {})
            if from_node.get("kind") == "mapping_claim":
                related_claim_nodes.append(from_node)
    ev_lines = _format_top_evidence_for_concept(related_claim_nodes, evidence_index)
    if ev_lines:
        lines.append("")
        lines.extend(ev_lines)

    lines.append("")
    lines.append(
        "💡 提示：在 Evidence Detail Graph 中可查看该模块下的所有 signal/always/assign 节点。"
        "点击节点详情中的「📄 证据」按钮可直接跳转到过滤后的 Evidence 页面。"
    )

    return AgentPanelResponse(
        question=question,
        response_kind="contextual",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Evidence summary helpers (T029)
# ---------------------------------------------------------------------------


def _format_top_evidence_for_concept(
    related_claims: list[Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> list[str]:
    """Return formatted lines listing top evidence for a concept."""
    if not evidence_index:
        return []
    # First try evidence_ids on claims.
    ev_ids: list[str] = []
    for c in related_claims:
        ids = c.get("evidence_ids", [])
        if isinstance(ids, list):
            ev_ids.extend(ids)
    # Fallback: search evidence_index by concept names.
    if not ev_ids:
        concepts: set[str] = set()
        for c in related_claims:
            concept = c.get("concept", "")
            if concept:
                concepts.add(concept)
        for eid, info in evidence_index.items():
            if isinstance(info, dict) and info.get("concept", "") in concepts:
                ev_ids.append(eid)
    if not ev_ids:
        return []
    return _format_evidence_list(ev_ids, evidence_index)


def _format_top_evidence_for_claim(
    claim_node: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> list[str]:
    """Return formatted lines listing top evidence for a claim."""
    if not evidence_index:
        return []
    ev_ids = claim_node.get("evidence_ids", [])
    if isinstance(ev_ids, list) and ev_ids:
        return _format_evidence_list(ev_ids, evidence_index)
    # Fallback: search evidence_index by claim concept.
    concept = claim_node.get("concept", "")
    if concept:
        ev_ids = [
            eid for eid, info in evidence_index.items()
            if isinstance(info, dict) and info.get("concept", "") == concept
        ]
    if not ev_ids:
        return []
    return _format_evidence_list(ev_ids, evidence_index)


def _format_evidence_list(
    ev_ids: list[str],
    evidence_index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> list[str]:
    """Format up to 5 evidence items with file/line/symbol/strength."""
    import re
    lines = ["Top evidence:"]
    shown = 0
    for eid in ev_ids[:5]:
        info = evidence_index.get(eid)
        if not isinstance(info, dict):
            continue
        file_path = info.get("file_path", "")
        basename = file_path.split("/")[-1] if file_path else "unknown"
        symbol = info.get("symbol", "")
        strength = info.get("strength", "unknown")
        # Parse line range from evidence_id if present.
        start_line = ""
        m = re.search(r":(\d+)(?:-(\d+))?:", eid)
        if m:
            start_line = m.group(1)
            if m.group(2):
                start_line += "-" + m.group(2)
        line_info = "{}".format(start_line) if start_line else ""
        parts = ["  • {}".format(eid)]
        if basename or line_info:
            parts.append("    {} {}".format(basename, line_info).strip())
        if symbol:
            parts.append("    symbol: {}".format(symbol))
        parts.append("    strength: {}".format(strength))
        lines.extend(parts)
        shown += 1
    if not shown:
        return []
    lines.append("可在 Evidence 页点击证据查看源码上下文。")
    return lines
