"""Agent interaction panel models for the Desktop Agent Shell (T011).

Deterministic, rule-based artifact query.  No LLM, no external API,
no API key.  Pure Python; testable without PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpga_devmind.desktop.agent_query_utils import (
    deduplicate_diagnostics,
    extract_claim_id,
    extract_evidence_id,
    has_any,
)
from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_graph,
    get_grounding_report,
    get_index,
    get_project_graph,
    get_run_metadata,
)


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentPanelResponse:
    """Response from a deterministic local artifact query."""

    question: str = ""
    answer_text: str = ""
    response_kind: str = "unsupported"  # "summary" | "claims" | "evidence" |
    # "diagnostics" | "unknown" | "nodes" | "edges" | "claim_detail" |
    # "evidence_detail" | "unsupported"
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def query_artifact_bundle(
    bundle: ArtifactBundle,
    question: str,
) -> AgentPanelResponse:
    """Answer a question about *bundle* using deterministic rules.

    Never raises; all errors return ``is_loaded=False``.
    """
    if not bundle.is_complete:
        errors = [
            d.message for d in bundle.diagnostics if d.severity == "error"
        ]
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="; ".join(errors) if errors else "Incomplete bundle",
        )

    if bundle.bundle_type == "project":
        return _query_project_bundle(bundle, question)

    if bundle.bundle_type not in ("p1b", "p1a"):
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="Agent query available for P1a/P1b/project bundles only",
        )

    graph = get_graph(bundle)
    index = get_index(bundle) or {}
    grounding = get_grounding_report(bundle) or {}
    meta = get_run_metadata(bundle) or {}

    normalized = question.strip().lower()

    # Specific ID lookups first (use original question to preserve case).
    claim_match = extract_claim_id(question)
    if claim_match:
        return _answer_claim_detail(
            normalized, graph, claim_match, index, grounding
        )

    evidence_match = extract_evidence_id(question)
    if evidence_match:
        return _answer_evidence_detail(normalized, graph, evidence_match)

    # Keyword-based routing.
    # Summary — must come before other checks to catch broad questions.
    if has_any(
        normalized,
        ["summary", "概况", "整体情况", "做了什么", "overview", "about"],
    ):
        return _answer_summary(normalized, graph, meta, grounding)

    # Evidence — check before claims to avoid "有什么证据支持这些映射"
    # being mis-routed to claims because it contains "映射".
    if has_any(normalized, ["evidence", "证据", "proof"]):
        return _answer_evidence(normalized, graph)

    if has_any(
        normalized, ["claims", "mapping", "映射", "claim", "mapping claims"]
    ):
        return _answer_claims(normalized, graph)

    if has_any(
        normalized, ["diagnostics", "grounding", "诊断", "checker"]
    ):
        return _answer_diagnostics(normalized, graph, grounding)

    if has_any(
        normalized, ["unknown", "不确定", "uncertainty", "unsure"]
    ):
        return _answer_unknown(normalized, graph)

    # Edges — check before nodes to avoid "节点之间的关系是什么"
    # being mis-routed to nodes because it contains "节点".
    if has_any(normalized, ["edges", "edge", "边", "关系"]):
        return _answer_edges(normalized, graph)

    if has_any(normalized, ["nodes", "node", "节点"]):
        return _answer_nodes(normalized, graph)

    # Fallback.
    return AgentPanelResponse(
        question=question,
        response_kind="unsupported",
        answer_text=(
            "This question is not supported by the local deterministic query.\n"
            "Supported topics: summary, claims, evidence, diagnostics, "
            "unknown/uncertainty, nodes, edges, or a specific claim_id / "
            "evidence_id.\n"
            "External LLM is not enabled in T011."
        ),
        unsupported_reason="question_type_not_recognized",
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Project bundle query handler
# ---------------------------------------------------------------------------


def _query_project_bundle(
    bundle: ArtifactBundle,
    question: str,
) -> AgentPanelResponse:
    """Answer a question about a project-level understanding bundle."""
    graph = get_project_graph(bundle)
    meta = get_run_metadata(bundle) or {}
    normalized = question.strip().lower()

    if graph is None:
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="Project understanding graph not found.",
        )

    # Project-level keyword routing.
    # Order matters: more specific before broad.
    if has_any(
        normalized,
        [
            "summary",
            "概况",
            "整体情况",
            "做了什么",
            "overview",
            "about",
            "这个项目整体实现了什么",
            "项目整体实现了什么",
            "这个项目做了什么",
            "项目概况",
        ],
    ):
        return _answer_project_summary(normalized, graph, meta)

    if has_any(normalized, ["不确定", "unknown", "哪些概念还不确定"]):
        return _answer_project_unknown(normalized, graph)

    if has_any(normalized, ["rtl 映射", "映射", "mapped", "哪些概念有"]):
        return _answer_project_mapped(normalized, graph)

    if has_any(normalized, ["shared", "多个概念", "承载了多个概念", "共享"]):
        return _answer_project_shared(normalized, graph)

    if has_any(normalized, ["有哪些概念", "概念", "concepts"]):
        return _answer_project_concepts(normalized, graph)

    if has_any(normalized, ["graph", "图", "画出"]):
        return _answer_project_graph(normalized, graph)

    # Fallback to generic unsupported.
    return AgentPanelResponse(
        question=question,
        response_kind="unsupported",
        answer_text=(
            "Project-level questions supported:\n"
            "• 这个项目整体实现了什么？\n"
            "• 有哪些概念？\n"
            "• 哪些概念有 RTL 映射？\n"
            "• 哪些概念还不确定？\n"
            "• 哪些 RTL 文件承载了多个概念？\n"
            "• 画出项目理解图\n"
        ),
        unsupported_reason="project_question_not_recognized",
        is_loaded=True,
    )


def _answer_project_summary(
    question: str,
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    meta: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer '这个项目整体实现了什么？'"""
    project = meta.get("project_root", "")
    concepts = meta.get("concepts_processed", [])
    failed = meta.get("concepts_failed", [])
    total_claims = meta.get("mapping_claims", 0)
    total_evidence = meta.get("evidence_items", 0)

    lines = ["项目 '{}' 的整体理解如下：".format(project), ""]
    lines.append("识别出 {} 个概念：{}".format(len(concepts), ", ".join(concepts)))
    if failed:
        lines.append("其中 {} 个概念 trace 失败：{}".format(len(failed), ", ".join(failed)))
    lines.append("")
    lines.append("聚合统计：{} 个 mapping claims，{} 条证据。".format(total_claims, total_evidence))
    lines.append("")

    # Build concept -> RTL mapping from realizes edges.
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_by_id = {}
    for n in nodes:
        nid = n.get("node_id", "")
        if nid:
            node_by_id[nid] = n

    concept_to_rtl: dict[str, list[str]] = {}
    for e in edges:
        if e.get("edge_type") == "realizes":
            from_node = node_by_id.get(e.get("from_node_id", ""), {})
            to_node = node_by_id.get(e.get("to_node_id", ""), {})
            concept = from_node.get("concept", "") or from_node.get("label", "")
            rtl_label = to_node.get("label", "")
            rtl_kind = to_node.get("kind", "")
            if concept and rtl_label and rtl_kind.startswith("rtl_"):
                display = "{} ({})".format(rtl_label, rtl_kind)
                concept_to_rtl.setdefault(concept, []).append(display)

    if concept_to_rtl:
        lines.append("识别出的概念及主要 RTL 实现：")
        for concept in sorted(concept_to_rtl):
            rtls = sorted(set(concept_to_rtl[concept]))[:5]
            lines.append("• {} — 主要对应 {}".format(concept, ", ".join(rtls)))
        lines.append("")

    # Uncertainty count.
    unknown_concepts = [
        n for n in nodes
        if n.get("kind") == "concept" and n.get("confidence") == "unknown"
    ]
    if unknown_concepts:
        lines.append("不确定项：")
        lines.append("  • {} 个概念存在 unknown 状态".format(len(unknown_concepts)))
        lines.append("")

    lines.append("下一步建议：")
    lines.append("  • 点击 Overview 图中的概念节点查看详情")
    lines.append("  • 在 Evidence 页面查看各 claim 的证据分组")
    lines.append('  • 使用 "哪些概念还不确定？" 查看缺失证据')

    return AgentPanelResponse(
        question=question,
        response_kind="summary",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_project_concepts(
    question: str,
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer '有哪些概念？'"""
    nodes = graph.get("nodes", [])
    concept_nodes = [n for n in nodes if n.get("kind") == "concept"]

    lines = ["项目中共识别出 {} 个概念：".format(len(concept_nodes)), ""]
    for node in concept_nodes:
        lines.append("• {} — 可信度：{}".format(node.get("label", ""), node.get("confidence", "unknown")))

    return AgentPanelResponse(
        question=question,
        response_kind="concepts",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_project_mapped(
    question: str,
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer '哪些概念有 RTL 映射？'"""
    nodes = graph.get("nodes", [])
    concept_nodes = [n for n in nodes if n.get("kind") == "concept"]
    edges = graph.get("edges", [])

    # Find concepts that have has_claim edges.
    concepts_with_claims: set[str] = set()
    for edge in edges:
        if edge.get("edge_type") == "has_claim":
            from_id = edge.get("from_node_id", "")
            for node in concept_nodes:
                if node.get("node_id") == from_id:
                    concepts_with_claims.add(node.get("label", ""))

    lines = ["有 RTL 映射的概念（通过 mapping claims 连接）：", ""]
    for concept in sorted(concepts_with_claims):
        lines.append("• {}".format(concept))

    return AgentPanelResponse(
        question=question,
        response_kind="mapped",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_project_unknown(
    question: str,
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer '哪些概念还不确定？'"""
    nodes = graph.get("nodes", [])
    unknown_concepts = [
        n for n in nodes
        if n.get("kind") == "concept" and n.get("confidence") == "unknown"
    ]

    lines = []
    if unknown_concepts:
        lines.append("以下概念当前处于 unknown 状态：")
        for node in unknown_concepts:
            lines.append("• {}".format(node.get("label", "")))
    else:
        lines.append("所有概念至少有一条 inferred 或 supported 的映射声明。")

    return AgentPanelResponse(
        question=question,
        response_kind="unknown",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_project_shared(
    question: str,
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer '哪些 RTL 文件承载了多个概念？'"""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    node_map = {}
    for n in nodes:
        nid = n.get("node_id", "")
        if nid:
            node_map[nid] = n.get("label", nid)

    # Group by RTL module/file: find which concepts share each rtl_module node.
    rtl_to_concepts: dict[str, list[str]] = {}
    for e in edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            to_node = next((n for n in nodes if n.get("node_id") == to_id), None)
            if to_node is not None and to_node.get("kind", "").startswith("rtl_"):
                from_node = next((n for n in nodes if n.get("node_id") == from_id), None)
                if from_node is not None:
                    concept = from_node.get("concept", "") or from_node.get("label", "")
                    rtl_label = to_node.get("label", to_id)
                    if concept:
                        rtl_to_concepts.setdefault(rtl_label, []).append(concept)

    # Also report concept-concept shares_file edges.
    shared_edges = [e for e in edges if e.get("edge_type") in ("shares_file", "shares_rtl_object")]

    lines = ["概念之间的共享关系（结构推断）：", ""]

    if rtl_to_concepts:
        lines.append("按 RTL 模块/文件分组：")
        for rtl_label, concepts in sorted(rtl_to_concepts.items()):
            unique = sorted(set(concepts))
            if len(unique) > 1:
                lines.append(
                    "• {} — 被 {} 个概念共享：{}".format(
                        rtl_label, len(unique), ", ".join(unique)
                    )
                )
            else:
                lines.append(
                    "• {} — 仅关联概念：{}".format(rtl_label, ", ".join(unique))
                )
        lines.append("")

    if shared_edges:
        lines.append("概念之间的共享边：")
        for edge in shared_edges:
            from_label = edge.get("from_node_id", "").replace("PUG_CONCEPT_", "")
            to_label = edge.get("to_node_id", "").replace("PUG_CONCEPT_", "")
            etype = edge.get("edge_type", "")
            notes = edge.get("notes", "")
            lines.append("• {} 和 {} 共享 {} — {}".format(from_label, to_label, etype, notes))
    else:
        lines.append("未发现额外的概念之间共享文件或 RTL 对象边。")

    return AgentPanelResponse(
        question=question,
        response_kind="shared",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_project_graph(
    question: str,
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    """Answer '画出项目理解图'."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Count hidden kinds for overview stats.
    hidden_kinds = {"rtl_signal", "rtl_always_block", "rtl_assign", "rtl_comment", "comment"}
    hidden_count = sum(1 for n in nodes if n.get("kind", "") in hidden_kinds)

    lines = ["项目理解图概览：", ""]
    lines.append(
        "当前默认显示 Overview Graph（语义聚合视图）。"
        "signal / always_block / assign / comment 等底层节点已隐藏，"
        "可在 Evidence Detail Graph 中查看全部节点。"
    )
    lines.append("")
    lines.append("节点：{} 个（Overview 视图中隐藏 {} 个）".format(len(nodes), hidden_count))
    lines.append("边：{} 条".format(len(edges)))
    lines.append("")
    lines.append("节点类型分布：")
    kind_counts: dict[str, int] = {}
    for node in nodes:
        kind = node.get("kind", "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    for kind, count in sorted(kind_counts.items()):
        lines.append("  • {}: {}".format(kind, count))
    lines.append("")
    lines.append("边类型分布：")
    etype_counts: dict[str, int] = {}
    for edge in edges:
        etype = edge.get("edge_type", "unknown")
        etype_counts[etype] = etype_counts.get(etype, 0) + 1
    for etype, count in sorted(etype_counts.items()):
        lines.append("  • {}: {}".format(etype, count))
    lines.append("")
    lines.append(
        "💡 提示：shares_file / shares_rtl_object 边是 structural inferred，"
        "不是语义确认。它们表示多个概念引用了同一 RTL 文件或对象。"
    )

    return AgentPanelResponse(
        question=question,
        response_kind="graph",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Answer builders — P1b aware, fall back gracefully when graph is None
# ---------------------------------------------------------------------------


def _answer_summary(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    meta: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    concept = meta.get("concept", "")
    status = meta.get("status", "unknown")
    claims = meta.get("mapping_claims", 0)
    evidence = meta.get("evidence_items", 0)
    blocking = meta.get("blocking_diagnostics", 0)
    elapsed = meta.get("elapsed_seconds", 0.0)

    lines = ["概念 '{}' 的追踪概况如下：".format(concept), ""]
    lines.append(
        "当前状态为 {}，共有 {} 条映射声明，{} 条证据项。".format(
            status, claims, evidence
        )
    )
    if blocking:
        lines.append("注意：存在 {} 条阻断性诊断，需要优先处理。".format(blocking))
    else:
        lines.append("目前没有阻断性诊断。")

    if graph:
        nodes = len(graph.get("nodes", []))
        edges = len(graph.get("edges", []))
        lines.append(
            "概念图包含 {} 个节点、{} 条边。".format(nodes, edges)
        )

    lines.append("追踪耗时 {:.3f} 秒。".format(elapsed))

    summary_diag = grounding.get("summary", {})
    if isinstance(summary_diag, dict) and summary_diag:
        lines.append("")
        lines.append("补充诊断信息：")
        for key, value in summary_diag.items():
            lines.append("  • {}: {}".format(key, value))

    return AgentPanelResponse(
        question=question,
        response_kind="summary",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_claims(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="claims",
            answer_text="当前没有可用的概念 trace 图数据。",
            is_loaded=True,
        )

    claims = graph.get("mapping_claims", [])
    if not claims:
        return AgentPanelResponse(
            question=question,
            response_kind="claims",
            answer_text="未发现任何映射声明。",
            is_loaded=True,
        )

    lines = ["共有 {} 条映射声明：".format(len(claims)), ""]
    claim_ids: list[str] = []
    for claim in claims:
        cid = claim.get("claim_id", "")
        claim_ids.append(cid)
        conf = claim.get("confidence", "unknown")
        bridge = claim.get("bridge_kind", "unknown")
        l5 = len(claim.get("l5_l6_evidence_ids", []) or [])
        rtl = len(claim.get("rtl_evidence_ids", []) or [])
        lines.append(
            "• {} — 可信度：{} | 桥接类型：{} | L5/L6 证据 {} 条、RTL 证据 {} 条".format(
                cid, conf, bridge, l5, rtl
            )
        )

    return AgentPanelResponse(
        question=question,
        response_kind="claims",
        answer_text="\n".join(lines),
        referenced_claim_ids=claim_ids,
        is_loaded=True,
    )


def _answer_evidence(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence",
            answer_text="当前没有可用的概念 trace 图数据。",
            is_loaded=True,
        )

    items = graph.get("evidence_items", [])
    if not items:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence",
            answer_text="未发现任何证据项。",
            is_loaded=True,
        )

    # Group by source type for natural language summary
    l5_l6 = [i for i in items if i.get("source_type", "") in (
        "concept_occurrence", "p1b_concept", "l5_l6"
    )]
    rtl = [i for i in items if i.get("source_type", "") in (
        "rtl_source", "p1b_rtl", "rtl"
    )]
    other = [i for i in items if i not in l5_l6 and i not in rtl]

    # Strength breakdown
    strong_count = sum(1 for i in items if i.get("evidence_strength") == "strong")
    medium_count = sum(1 for i in items if i.get("evidence_strength") == "medium")
    weak_count = sum(1 for i in items if i.get("evidence_strength") == "weak")
    unknown_count = sum(1 for i in items if i.get("evidence_strength") == "unknown")

    lines = ["共有 {} 条证据支持当前概念追踪：".format(len(items)), ""]
    if l5_l6:
        lines.append("L5/L6 代码证据 {} 条".format(len(l5_l6)))
    if rtl:
        lines.append("RTL 证据 {} 条".format(len(rtl)))
    if other:
        lines.append("其他证据 {} 条".format(len(other)))
    lines.append("")
    lines.append("强度分布：")
    if strong_count:
        lines.append("  • strong {} 条 — 高置信度，可直接支撑 mapping claim".format(strong_count))
    if medium_count:
        lines.append("  • medium {} 条 — 中等置信度，需额外验证".format(medium_count))
    if weak_count:
        lines.append("  • weak {} 条 — 低置信度，仅供参考".format(weak_count))
    if unknown_count:
        lines.append("  • unknown {} 条 — 未评估".format(unknown_count))
    lines.append("")

    eids: list[str] = []
    for item in items[:20]:
        eid = item.get("evidence_id", "")
        eids.append(eid)
        src = item.get("source_type", "")
        sym = item.get("symbol") or ""
        strength = item.get("evidence_strength", "")
        file_path = item.get("file_path", "")
        lines.append(
            "• {} — 来源：{} | 符号：{} | 强度：{} | 文件：{}".format(
                eid, src, sym, strength, file_path
            )
        )
    if len(items) > 20:
        lines.append("\n... 以及另外 {} 条".format(len(items) - 20))

    lines.append("")
    lines.append("💡 提示：在 Evidence 页面选中证据行可查看详细解释。")

    return AgentPanelResponse(
        question=question,
        response_kind="evidence",
        answer_text="\n".join(lines),
        referenced_evidence_ids=eids,
        is_loaded=True,
    )


def _answer_diagnostics(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    diags = deduplicate_diagnostics(graph, grounding)

    if not diags:
        return AgentPanelResponse(
            question=question,
            response_kind="diagnostics",
            answer_text="未发现任何诊断信息。",
            is_loaded=True,
        )

    blocking = [d for d in diags if d.get("severity") == "error"]
    warnings = [d for d in diags if d.get("severity") == "warning"]

    lines = ["共 {} 条诊断信息：".format(len(diags)), ""]
    if blocking:
        lines.append("阻断性错误 {} 条（需要优先处理）".format(len(blocking)))
    if warnings:
        lines.append("警告 {} 条".format(len(warnings)))
    lines.append("")

    diag_ids: list[str] = []
    for diag in diags:
        did = diag.get("diagnostic_id", "")
        diag_ids.append(did)
        severity = diag.get("severity", "")
        issue = diag.get("issue_type", "")
        target = diag.get("target_claim_id") or ""
        msg = diag.get("message") or ""
        lines.append(
            "• {} — 严重级别：{} | 问题类型：{} | 目标声明：{} | {}".format(
                did, severity, issue, target, msg
            )
        )

    return AgentPanelResponse(
        question=question,
        response_kind="diagnostics",
        answer_text="\n".join(lines),
        referenced_diagnostic_ids=diag_ids,
        is_loaded=True,
    )


def _answer_unknown(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="unknown",
            answer_text="当前没有可用的概念 trace 图数据。",
            is_loaded=True,
        )

    notes = graph.get("uncertainty_notes", [])
    claims = graph.get("mapping_claims", [])
    unknown_claims = [c for c in claims if c.get("confidence") == "unknown"]

    lines = []
    if unknown_claims:
        lines.append("有 {} 条映射声明的可信度为 unknown：".format(len(unknown_claims)))
        for claim in unknown_claims:
            cid = claim.get("claim_id", "")
            missing = claim.get("required_missing_evidence", [])
            lines.append(
                "  • {} — 缺失证据：{}".format(
                    cid,
                    "; ".join(missing) if isinstance(missing, list) else "无",
                )
            )
        lines.append("")

    if notes:
        lines.append("不确定性备注：")
        for note in notes:
            topic = note.get("topic", "")
            reason = note.get("reason", "")
            lines.append("  • {} — {}".format(topic, reason))
    elif not unknown_claims:
        lines.append("当前没有明显的不确定性或缺失证据。")

    return AgentPanelResponse(
        question=question,
        response_kind="unknown",
        answer_text="\n".join(lines),
        referenced_claim_ids=[c.get("claim_id", "") for c in unknown_claims],
        uncertainty_notes=[n.get("reason", "") for n in notes],
        is_loaded=True,
    )


def _answer_nodes(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="nodes",
            answer_text="当前没有可用的概念 trace 图数据。",
            is_loaded=True,
        )

    nodes = graph.get("nodes", [])
    lines = ["概念图中共 {} 个节点：".format(len(nodes)), ""]
    nids: list[str] = []
    for node in nodes:
        nid = node.get("node_id", "")
        nids.append(nid)
        label = node.get("label", "")
        kind = node.get("kind", "")
        conf = node.get("confidence", "")
        ev_count = len(node.get("evidence_ids", []) or [])
        lines.append(
            "• {} — 标签：{} | 类型：{} | 可信度：{} | 证据：{} 条".format(
                nid, label, kind, conf, ev_count
            )
        )

    return AgentPanelResponse(
        question=question,
        response_kind="nodes",
        answer_text="\n".join(lines),
        referenced_node_ids=nids,
        is_loaded=True,
    )


def _answer_edges(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="edges",
            answer_text="当前没有可用的概念 trace 图数据。",
            is_loaded=True,
        )

    edges = graph.get("edges", [])
    nodes = graph.get("nodes", [])
    node_map = _build_node_map(graph)

    # Count nodes by kind and confidence.
    l5_l6_nodes = [n for n in nodes if n.get("kind") in ("stage_view", "concept")]
    rtl_nodes = [n for n in nodes if str(n.get("kind", "")).startswith("rtl")]
    claim_nodes = [n for n in nodes if n.get("kind") in ("claim", "bridge")]
    supported = sum(1 for e in edges if e.get("confidence") in ("supported", "confirmed"))
    inferred = sum(1 for e in edges if e.get("confidence") == "inferred")
    unknown_conf = sum(1 for e in edges if e.get("confidence") == "unknown")

    lines = ["概念图中共 {} 条关系边：".format(len(edges)), ""]
    lines.append("节点构成：")
    lines.append("  • L5/L6 概念节点 {} 个".format(len(l5_l6_nodes)))
    lines.append("  • Mapping claim 节点 {} 个".format(len(claim_nodes)))
    lines.append("  • RTL 对象节点 {} 个".format(len(rtl_nodes)))
    lines.append("")
    lines.append("边可信度分布：")
    if supported:
        lines.append("  • supported/confirmed {} 条".format(supported))
    if inferred:
        lines.append("  • inferred {} 条".format(inferred))
    if unknown_conf:
        lines.append("  • unknown {} 条".format(unknown_conf))
    lines.append("")

    for edge in edges:
        eid = edge.get("edge_id", "")
        fid = edge.get("from_node_id", "")
        tid = edge.get("to_node_id", "")
        fl = node_map.get(fid, fid)
        tl = node_map.get(tid, tid)
        et = edge.get("edge_type", "")
        conf = edge.get("confidence", "")
        lines.append(
            "• {} — {} → {} | 关系类型：{} | 可信度：{}".format(
                eid, fl, tl, et, conf
            )
        )

    lines.append("")
    lines.append("💡 提示：在 Concept Graph 页面可直观查看节点和边的关系。")

    return AgentPanelResponse(
        question=question,
        response_kind="edges",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_claim_detail(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    claim_id: str,
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="claim_detail",
            answer_text="当前没有可用的概念 trace 图数据。",
            referenced_claim_ids=[claim_id],
            is_loaded=True,
        )

    claims = graph.get("mapping_claims", [])
    claim = next((c for c in claims if c.get("claim_id") == claim_id), None)
    if claim is None:
        return AgentPanelResponse(
            question=question,
            response_kind="claim_detail",
            answer_text="未找到声明 {}。".format(claim_id),
            referenced_claim_ids=[claim_id],
            is_loaded=True,
        )

    lines = ["映射声明 {} 的详情：".format(claim_id), ""]
    lines.append(
        "概念引用：{}".format(claim.get("concept_ref", "(无)"))
    )
    lines.append("可信度：{}".format(claim.get("confidence", "unknown")))
    lines.append("桥接类型：{}".format(claim.get("bridge_kind", "unknown")))
    statement = claim.get("statement", "")
    if statement:
        lines.append("声明内容：{}".format(statement))

    l5 = claim.get("l5_l6_evidence_ids", [])
    rtl = claim.get("rtl_evidence_ids", [])
    bridge = claim.get("bridge_evidence_ids", [])
    lines.append("")
    lines.append("证据分布：")
    lines.append("  • L5/L6 证据：{} 条".format(len(l5) if isinstance(l5, list) else 0))
    lines.append("  • RTL 证据：{} 条".format(len(rtl) if isinstance(rtl, list) else 0))
    lines.append("  • 桥接证据：{} 条".format(len(bridge) if isinstance(bridge, list) else 0))

    missing = claim.get("required_missing_evidence", [])
    if missing and isinstance(missing, list):
        lines.append("")
        lines.append("缺失证据：{}".format("; ".join(missing)))

    # Count diagnostics targeting this claim (deduplicated).
    all_diags = deduplicate_diagnostics(graph, grounding)
    diag_count = sum(
        1 for d in all_diags if d.get("target_claim_id") == claim_id
    )
    if diag_count:
        lines.append("关联诊断：{} 条".format(diag_count))

    return AgentPanelResponse(
        question=question,
        response_kind="claim_detail",
        answer_text="\n".join(lines),
        referenced_claim_ids=[claim_id],
        referenced_evidence_ids=list(claim.get("evidence_ids", [])),
        is_loaded=True,
    )


def _answer_evidence_detail(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    evidence_id: str,
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence_detail",
            answer_text="当前没有可用的概念 trace 图数据。",
            referenced_evidence_ids=[evidence_id],
            is_loaded=True,
        )

    items = graph.get("evidence_items", [])
    item = next(
        (i for i in items if i.get("evidence_id") == evidence_id), None
    )
    if item is None:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence_detail",
            answer_text="未找到证据 {}。".format(evidence_id),
            referenced_evidence_ids=[evidence_id],
            is_loaded=True,
        )

    lines = ["证据 {} 的详情：".format(evidence_id), ""]
    lines.append("来源类型：{}".format(item.get("source_type", "")))
    lines.append("文件路径：{}".format(item.get("file_path", "")))
    start_line = item.get("start_line", "")
    end_line = item.get("end_line", "")
    if start_line or end_line:
        lines.append("代码行范围：{} - {}".format(start_line, end_line))
    lines.append("符号：{}".format(item.get("symbol") or "(无)"))
    lines.append("证据强度：{}".format(item.get("evidence_strength", "")))
    summary = item.get("excerpt_summary", "")
    if summary:
        lines.append("内容摘要：{}".format(summary))

    return AgentPanelResponse(
        question=question,
        response_kind="evidence_detail",
        answer_text="\n".join(lines),
        referenced_evidence_ids=[evidence_id],
        is_loaded=True,
    )


def _build_node_map(graph: dict[str, Any]) -> dict[str, str]:  # pyright: ignore[reportExplicitAny]
    """Map node_id -> label from graph.nodes."""
    mapping: dict[str, str] = {}
    for node in graph.get("nodes", []):
        nid = node.get("node_id", "")
        label = node.get("label", "")
        if nid:
            mapping[nid] = label
    return mapping
