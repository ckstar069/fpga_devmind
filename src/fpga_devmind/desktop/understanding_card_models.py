"""End-to-end understanding card for a selected graph node (T030).

Integrates T027 (contextual agent), T028 (focus/filter), and T029 (source
context) into a single card that gives the user a complete picture of a
node without navigating across pages.

Pure Python — no PySide6, no LLM, no API, no file mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_project_graph,
    get_project_index,
)
from fpga_devmind.desktop.source_context_models import (
    build_source_context_for_evidence,
)


# ---------------------------------------------------------------------------
# View models
# ---------------------------------------------------------------------------


@dataclass
class RelationshipItem:
    """A relationship from the selected node to another node."""

    relation_type: str = ""
    target_id: str = ""
    target_label: str = ""
    confidence: str = ""
    note: str = ""


@dataclass
class ClaimSummary:
    """Summary of a mapping claim related to the selected node."""

    claim_id: str = ""
    concept: str = ""
    confidence: str = ""
    bridge_kind: str = ""
    evidence_count: int = 0
    short_explanation: str = ""


@dataclass
class RtlTargetSummary:
    """Summary of an RTL target related to the selected node."""

    node_id: str = ""
    label: str = ""
    file_path: str = ""
    kind: str = ""
    related_concepts: list[str] = field(default_factory=list)
    related_claims: list[str] = field(default_factory=list)


@dataclass
class EvidenceSnippet:
    """A preview of evidence source context."""

    evidence_id: str = ""
    file_path: str = ""
    line_range: str = ""
    symbol: str = ""
    strength: str = ""
    why_this_matters: str = ""
    code_preview_lines: list[str] = field(default_factory=list)
    is_source_available: bool = False


@dataclass
class UnderstandingCardViewModel:
    """End-to-end understanding card for a selected graph node."""

    is_loaded: bool = False
    load_error: str | None = None
    node_id: str = ""
    title: str = ""
    node_kind: str = ""
    confidence: str = ""
    summary_text: str = ""
    relationships: list[RelationshipItem] = field(default_factory=list)
    claims: list[ClaimSummary] = field(default_factory=list)
    rtl_targets: list[RtlTargetSummary] = field(default_factory=list)
    evidence_snippets: list[EvidenceSnippet] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_understanding_card(
    bundle: ArtifactBundle,
    selected_node_id: str,
    max_evidence: int = 3,
) -> UnderstandingCardViewModel:
    """Build an end-to-end understanding card for *selected_node_id*.

    Only project bundles are supported.  Returns a card with ``is_loaded``
    set and clear ``limitations`` for unsupported node kinds.
    """
    if not bundle.is_complete:
        return _error_card("Bundle 未完成加载。")

    if bundle.bundle_type != "project":
        return _error_card("理解卡仅支持 project bundle。")

    if not selected_node_id:
        return _error_card("未选中任何节点。请在概念图中点击一个节点。")

    graph = get_project_graph(bundle)
    if graph is None:
        return _error_card("无法加载项目图数据。")

    index = get_project_index(bundle) or {}
    evidence_index: dict[str, Any] = index.get("evidence_index", {})  # pyright: ignore[reportExplicitAny]

    raw_nodes: list[Any] = graph.get("nodes", [])  # pyright: ignore[reportExplicitAny]
    node_by_id: dict[str, dict[str, Any]] = {  # pyright: ignore[reportExplicitAny]
        n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")
    }

    selected = node_by_id.get(selected_node_id)
    if selected is None:
        return _error_card(
            "节点 '{}' 在图中未找到。".format(selected_node_id)
        )

    kind = selected.get("kind", "")
    label = selected.get("label", selected_node_id)
    confidence = selected.get("confidence", "")

    # Dispatch by node kind.
    if kind == "project":
        return _build_project_card(selected, graph, evidence_index, max_evidence)
    if kind == "concept":
        return _build_concept_card(
            selected, graph, evidence_index, max_evidence,
        )
    if kind in ("mapping_claim", "claim"):
        return _build_claim_card(
            selected, graph, evidence_index, max_evidence,
        )
    if kind.startswith("rtl"):
        return _build_rtl_card(
            selected, graph, evidence_index, max_evidence,
        )

    # Unsupported kind — return partial card with limitations.
    return UnderstandingCardViewModel(
        is_loaded=True,
        node_id=selected_node_id,
        title=label,
        node_kind=kind,
        confidence=confidence,
        summary_text="节点类型 '{}' 的理解卡尚未完全实现。".format(kind),
        limitations=[
            "当前仅支持 project / concept / mapping_claim / rtl_* 节点类型。",
            "可在 Agent 问答页输入全局问题获取更多信息。",
        ],
    )


# ---------------------------------------------------------------------------
# Render helper (used by both tests and GUI)
# ---------------------------------------------------------------------------


def render_understanding_card_text(card: UnderstandingCardViewModel) -> str:
    """Render the card as readable text for QTextEdit display."""
    if not card.is_loaded:
        return card.load_error or "无法加载理解卡。"

    lines: list[str] = []

    # Header
    lines.append("📋 理解卡：{}".format(card.title))
    lines.append("类型: {} | 可信度: {}".format(card.node_kind, card.confidence or "—"))
    lines.append("")

    # Summary
    if card.summary_text:
        lines.append("【摘要】")
        lines.append(card.summary_text)
        lines.append("")

    # Relationships
    if card.relationships:
        lines.append("【关系】")
        for r in card.relationships:
            conf_part = " ({})".format(r.confidence) if r.confidence else ""
            note_part = " — {}".format(r.note) if r.note else ""
            lines.append("  • {} → {}{}".format(r.relation_type, r.target_label, conf_part + note_part))
        lines.append("")

    # Claims
    if card.claims:
        lines.append("【相关 Claims】")
        for c in card.claims:
            lines.append("  • {} (concept={}, conf={}, bridge={})".format(
                c.claim_id, c.concept, c.confidence, c.bridge_kind,
            ))
            if c.short_explanation:
                lines.append("    {}".format(c.short_explanation))
            lines.append("    证据: {} 条".format(c.evidence_count))
        lines.append("")

    # RTL targets
    if card.rtl_targets:
        lines.append("【RTL 目标】")
        for r in card.rtl_targets:
            fp = " ({})".format(r.file_path.split("/")[-1]) if r.file_path else ""
            lines.append("  • {}{} [{}]".format(r.label, fp, r.kind))
            if r.related_concepts:
                lines.append("    概念: {}".format(", ".join(r.related_concepts)))
            if r.related_claims:
                lines.append("    Claims: {}".format(", ".join(r.related_claims)))
        lines.append("")

    # Evidence snippets
    if card.evidence_snippets:
        lines.append("【Top 证据】")
        for ev in card.evidence_snippets:
            src_tag = "✓" if ev.is_source_available else "✗"
            lines.append("  {} {} | {} {} | {}".format(
                src_tag, ev.evidence_id, ev.file_path.split("/")[-1] if ev.file_path else "?",
                ev.line_range, ev.strength,
            ))
            if ev.symbol:
                lines.append("    符号: {}".format(ev.symbol))
            for cl in ev.code_preview_lines:
                lines.append("    {}".format(cl))
            if ev.why_this_matters:
                lines.append("    → {}".format(ev.why_this_matters))
        lines.append("")

    # Uncertainty notes
    if card.uncertainty_notes:
        lines.append("【不确定性】")
        for n in card.uncertainty_notes:
            lines.append("  ⚠ {}".format(n))
        lines.append("")

    # Suggested questions
    if card.suggested_questions:
        lines.append("【建议问题】")
        for q in card.suggested_questions:
            lines.append("  → {}".format(q))
        lines.append("")

    # Limitations
    if card.limitations:
        lines.append("【限制】")
        for lim in card.limitations:
            lines.append("  • {}".format(lim))
        lines.append("")

    lines.append("💡 更多证据可点击「📄 证据」，Evidence 页会按当前节点过滤。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------


def _error_card(msg: str) -> UnderstandingCardViewModel:
    return UnderstandingCardViewModel(is_loaded=False, load_error=msg)


def _build_project_card(
    node: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    max_evidence: int,
) -> UnderstandingCardViewModel:
    """Build card for the project root node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    label = node.get("label", "project")

    concept_count = sum(1 for n in raw_nodes if n.get("kind") == "concept")
    claim_count = sum(1 for n in raw_nodes if n.get("kind") == "mapping_claim")
    rtl_count = sum(1 for n in raw_nodes if str(n.get("kind", "")).startswith("rtl"))
    unknowns = sum(
        1 for n in raw_nodes
        if n.get("kind") == "concept" and n.get("confidence") == "unknown"
    )

    concepts = [n for n in raw_nodes if n.get("kind") == "concept"]
    concept_labels = [c.get("label", "") for c in concepts]

    # Relationships: project contains concepts.
    relationships: list[RelationshipItem] = []
    for c in concepts:
        relationships.append(RelationshipItem(
            relation_type="contains",
            target_id=c.get("node_id", ""),
            target_label=c.get("label", ""),
            confidence=c.get("confidence", ""),
        ))

    summary = (
        "项目 '{}' 的整体理解图。\n"
        "包含 {} 个概念、{} 个映射声明、{} 个 RTL 对象。\n"
        "其中 {} 个概念处于 unknown 状态。"
    ).format(label, concept_count, claim_count, rtl_count, unknowns)

    if concept_labels:
        summary += "\n概念列表：{}".format(", ".join(concept_labels))

    uncertainty_notes: list[str] = []
    if unknowns > 0:
        uncertainty_notes.append(
            "{} 个概念缺少足够证据，处于 unknown 状态。".format(unknowns)
        )

    # Top evidence from evidence_index.
    ev_ids = list(evidence_index.keys())[:max_evidence]
    snippets = _build_evidence_snippets(graph, evidence_index, ev_ids, max_evidence)
    if len(evidence_index) > max_evidence:
        pass  # limitations will note this

    limitations: list[str] = []
    if len(evidence_index) > max_evidence:
        limitations.append(
            "仅展示前 {} 条证据，另有 {} 条可在 Evidence 页查看。".format(
                max_evidence, len(evidence_index) - max_evidence,
            )
        )

    return UnderstandingCardViewModel(
        is_loaded=True,
        node_id=node.get("node_id", ""),
        title=label,
        node_kind="project",
        confidence="",
        summary_text=summary,
        relationships=relationships,
        claims=[],
        rtl_targets=[],
        evidence_snippets=snippets,
        uncertainty_notes=uncertainty_notes,
        suggested_questions=[
            "整体映射质量如何？",
            "哪些概念还不确定？",
            "哪些概念共享 RTL 文件？",
        ],
        limitations=limitations,
    )


def _build_concept_card(
    node: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    max_evidence: int,
) -> UnderstandingCardViewModel:
    """Build card for a concept node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    node_by_id: dict[str, dict[str, Any]] = {
        n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")
    }

    node_id = node.get("node_id", "")
    label = node.get("label", "")
    confidence = node.get("confidence", "unknown")

    # Related claims.
    related_claims = [
        n for n in raw_nodes
        if n.get("kind") == "mapping_claim" and n.get("concept") == label
    ]

    # Related RTL via realizes edges.
    related_rtl_ids: set[str] = set()
    for e in raw_edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            from_node = node_by_id.get(from_id, {})
            if from_node.get("kind") == "mapping_claim" and from_node.get("concept") == label:
                related_rtl_ids.add(to_id)

    # Shared edges.
    shared_with: list[RelationshipItem] = []
    for e in raw_edges:
        if e.get("edge_type") in ("shares_file", "shares_rtl_object"):
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            from_label = node_by_id.get(from_id, {}).get("label", "")
            to_label = node_by_id.get(to_id, {}).get("label", "")
            if from_label == label and to_label:
                shared_with.append(RelationshipItem(
                    relation_type=e.get("edge_type", ""),
                    target_id=to_id,
                    target_label=to_label,
                    confidence="inferred",
                    note="结构性推断，不等同于语义确认",
                ))

    # Claims summary.
    claim_summaries: list[ClaimSummary] = []
    for c in related_claims:
        conf = c.get("confidence", "unknown")
        bridge = c.get("bridge_kind", "unknown")
        ev_ids = c.get("evidence_ids", [])
        ev_count = len(ev_ids) if isinstance(ev_ids, list) else 0
        explanation = ""
        if conf == "supported":
            explanation = "有充分证据支撑，可信度较高"
        elif conf == "inferred":
            explanation = "基于命名匹配或单侧证据推断"
        elif conf == "unknown":
            explanation = "缺少足够证据"
        claim_summaries.append(ClaimSummary(
            claim_id=c.get("label", ""),
            concept=label,
            confidence=conf,
            bridge_kind=bridge,
            evidence_count=ev_count,
            short_explanation=explanation,
        ))

    # RTL targets.
    rtl_summaries: list[RtlTargetSummary] = []
    for rtl_id in related_rtl_ids:
        rtl_node = node_by_id.get(rtl_id, {})
        # Find related claims and concepts for this RTL.
        rtl_related_claims: list[str] = []
        rtl_related_concepts: set[str] = set()
        for e in raw_edges:
            if e.get("edge_type") == "realizes" and e.get("to_node_id") == rtl_id:
                from_node = node_by_id.get(e.get("from_node_id", ""), {})
                if from_node.get("kind") == "mapping_claim":
                    rtl_related_claims.append(from_node.get("label", ""))
                    concept = from_node.get("concept", "")
                    if concept:
                        rtl_related_concepts.add(concept)
        rtl_summaries.append(RtlTargetSummary(
            node_id=rtl_id,
            label=rtl_node.get("label", rtl_id),
            file_path=rtl_node.get("file_path", ""),
            kind=rtl_node.get("kind", "rtl"),
            related_concepts=sorted(rtl_related_concepts),
            related_claims=rtl_related_claims,
        ))

    # Evidence snippets: gather evidence_ids from related claims.
    all_ev_ids: list[str] = []
    for c in related_claims:
        ids = c.get("evidence_ids", [])
        if isinstance(ids, list):
            all_ev_ids.extend(ids)
    # Fallback: search evidence_index by concept name.
    if not all_ev_ids:
        for eid, info in evidence_index.items():
            if isinstance(info, dict) and info.get("concept", "") == label:
                all_ev_ids.append(eid)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_ev_ids: list[str] = []
    for eid in all_ev_ids:
        if eid not in seen:
            seen.add(eid)
            unique_ev_ids.append(eid)

    snippets = _build_evidence_snippets(
        graph, evidence_index, unique_ev_ids, max_evidence,
    )

    # Summary text.
    rtl_names = sorted(r.label for r in rtl_summaries)[:5]
    summary = "概念 '{}' 当前可信度为 {}。".format(label, confidence)
    if related_claims:
        summary += "\n有 {} 个映射声明关联此概念。".format(len(related_claims))
    if rtl_names:
        summary += "\n映射到的 RTL 对象：{}。".format(", ".join(rtl_names))
    if confidence == "supported":
        summary += "\nL5/L6 侧和 RTL 侧均有证据支撑，可信度较高。"
    elif confidence == "inferred":
        summary += "\n仅有命名匹配或单侧证据，建议补充更多证据。"
    elif confidence == "unknown":
        summary += "\n当前缺少足够证据，建议进一步调查。"

    uncertainty_notes: list[str] = []
    if confidence == "unknown":
        uncertainty_notes.append("概念 '{}' 处于 unknown 状态，缺少足够证据。".format(label))
    for c in claim_summaries:
        if c.confidence == "unknown":
            uncertainty_notes.append(
                "Claim '{}' 可信度为 unknown。".format(c.claim_id)
            )
        if c.confidence == "inferred":
            uncertainty_notes.append(
                "Claim '{}' 可信度为 inferred，证据可能不充分。".format(c.claim_id)
            )

    limitations: list[str] = []
    total_ev = len(unique_ev_ids)
    if total_ev > max_evidence:
        limitations.append(
            "仅展示前 {} 条证据，另有 {} 条可在 Evidence 页查看。".format(
                max_evidence, total_ev - max_evidence,
            )
        )

    return UnderstandingCardViewModel(
        is_loaded=True,
        node_id=node_id,
        title=label,
        node_kind="concept",
        confidence=confidence,
        summary_text=summary,
        relationships=shared_with,
        claims=claim_summaries,
        rtl_targets=rtl_summaries,
        evidence_snippets=snippets,
        uncertainty_notes=uncertainty_notes,
        suggested_questions=[
            "这个概念如何映射到 RTL？",
            "有哪些证据支持？",
            "它与其他概念有什么关系？",
        ],
        limitations=limitations,
    )


def _build_claim_card(
    node: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    max_evidence: int,
) -> UnderstandingCardViewModel:
    """Build card for a mapping_claim node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    node_by_id: dict[str, dict[str, Any]] = {
        n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")
    }

    node_id = node.get("node_id", "")
    label = node.get("label", "")
    concept = node.get("concept", "")
    confidence = node.get("confidence", "unknown")
    bridge = node.get("bridge_kind", "unknown")

    # Realizes RTL targets.
    realizes_rtls: list[RtlTargetSummary] = []
    for e in raw_edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            if from_id == node_id:
                rtl_node = node_by_id.get(to_id, {})
                realizes_rtls.append(RtlTargetSummary(
                    node_id=to_id,
                    label=rtl_node.get("label", to_id),
                    file_path=rtl_node.get("file_path", ""),
                    kind=rtl_node.get("kind", "rtl"),
                    related_concepts=[concept] if concept else [],
                    related_claims=[label],
                ))

    # Evidence IDs.
    ev_ids_raw = node.get("evidence_ids", [])
    ev_ids = ev_ids_raw if isinstance(ev_ids_raw, list) else []
    if not ev_ids and concept:
        for eid, info in evidence_index.items():
            if isinstance(info, dict) and info.get("concept", "") == concept:
                ev_ids.append(eid)

    snippets = _build_evidence_snippets(
        graph, evidence_index, ev_ids, max_evidence,
    )

    # Summary.
    summary = (
        "映射声明 '{}' 将概念 '{}' 映射到 RTL 实现。\n"
        "桥接类型: {} | 可信度: {}"
    ).format(label, concept, bridge, confidence)
    if realizes_rtls:
        rtl_names = sorted(r.label for r in realizes_rtls)[:5]
        summary += "\n映射到的 RTL: {}".format(", ".join(rtl_names))
    if confidence == "supported":
        summary += "\n该声明有充分证据支撑。"
    elif confidence == "inferred":
        summary += "\n该声明基于推断，证据可能不充分。"
    missing = node.get("required_missing_evidence", [])
    if isinstance(missing, list) and missing:
        summary += "\n缺少证据: {}".format(", ".join(missing))

    # Claim summary for self.
    claim_summaries = [ClaimSummary(
        claim_id=label,
        concept=concept,
        confidence=confidence,
        bridge_kind=bridge,
        evidence_count=len(ev_ids),
        short_explanation="概念 '{}' 的映射声明".format(concept),
    )]

    uncertainty_notes: list[str] = []
    if confidence != "supported":
        uncertainty_notes.append(
            "Claim 可信度为 '{}'，非 fully supported。".format(confidence)
        )
    if isinstance(missing, list) and missing:
        uncertainty_notes.append(
            "缺少证据类型: {}".format(", ".join(missing))
        )

    limitations: list[str] = []
    if len(ev_ids) > max_evidence:
        limitations.append(
            "仅展示前 {} 条证据，另有 {} 条可在 Evidence 页查看。".format(
                max_evidence, len(ev_ids) - max_evidence,
            )
        )

    return UnderstandingCardViewModel(
        is_loaded=True,
        node_id=node_id,
        title=label,
        node_kind="mapping_claim",
        confidence=confidence,
        summary_text=summary,
        relationships=[],
        claims=claim_summaries,
        rtl_targets=realizes_rtls,
        evidence_snippets=snippets,
        uncertainty_notes=uncertainty_notes,
        suggested_questions=[
            "这个 claim 的证据是否充分？",
            "映射到的 RTL 实现是什么？",
            "还有哪些证据可以加强这个 claim？",
        ],
        limitations=limitations,
    )


def _build_rtl_card(
    node: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    max_evidence: int,
) -> UnderstandingCardViewModel:
    """Build card for an rtl_module / rtl_aggregate node."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    node_by_id: dict[str, dict[str, Any]] = {
        n.get("node_id", ""): n for n in raw_nodes if n.get("node_id")
    }

    node_id = node.get("node_id", "")
    label = node.get("label", "")
    kind = node.get("kind", "rtl")
    file_path = node.get("file_path", "")

    # Find which claims/concepts use this RTL.
    related_concepts: set[str] = set()
    related_claim_nodes: list[dict[str, Any]] = []
    for e in raw_edges:
        if e.get("edge_type") == "realizes" and e.get("to_node_id") == node_id:
            from_node = node_by_id.get(e.get("from_node_id", ""), {})
            if from_node.get("kind") == "mapping_claim":
                related_claim_nodes.append(from_node)
                concept = from_node.get("concept", "")
                if concept:
                    related_concepts.add(concept)

    # Claim summaries.
    claim_summaries: list[ClaimSummary] = []
    for c in related_claim_nodes:
        ev_ids_raw = c.get("evidence_ids", [])
        ev_ids = ev_ids_raw if isinstance(ev_ids_raw, list) else []
        claim_summaries.append(ClaimSummary(
            claim_id=c.get("label", ""),
            concept=c.get("concept", ""),
            confidence=c.get("confidence", "unknown"),
            bridge_kind=c.get("bridge_kind", "unknown"),
            evidence_count=len(ev_ids),
            short_explanation="通过 realizes 边关联到 {}".format(label),
        ))

    # Evidence: collect from related claims.
    all_ev_ids: list[str] = []
    for c in related_claim_nodes:
        ids = c.get("evidence_ids", [])
        if isinstance(ids, list):
            all_ev_ids.extend(ids)
    # Fallback: search by concept names.
    if not all_ev_ids:
        for eid, info in evidence_index.items():
            if isinstance(info, dict) and info.get("concept", "") in related_concepts:
                all_ev_ids.append(eid)
    seen_ev: set[str] = set()
    unique_ev: list[str] = []
    for eid in all_ev_ids:
        if eid not in seen_ev:
            seen_ev.add(eid)
            unique_ev.append(eid)

    snippets = _build_evidence_snippets(
        graph, evidence_index, unique_ev, max_evidence,
    )

    # Summary.
    summary = "RTL {} '{}' 是 RTL 侧的实现证据。".format(kind, label)
    if file_path:
        summary += "\n文件: {}".format(file_path)
    if related_concepts:
        summary += "\n承载概念: {}".format(", ".join(sorted(related_concepts)))
    if related_claim_nodes:
        summary += "\n被 {} 个 mapping claim 引用。".format(len(related_claim_nodes))
    if not related_claim_nodes:
        summary += "\n当前未被任何 mapping claim 直接引用。"

    uncertainty_notes: list[str] = []
    for c in claim_summaries:
        if c.confidence != "supported":
            uncertainty_notes.append(
                "引用此 RTL 的 claim '{}' 可信度为 '{}'。".format(
                    c.claim_id, c.confidence,
                )
            )

    limitations: list[str] = []
    if len(unique_ev) > max_evidence:
        limitations.append(
            "仅展示前 {} 条证据，另有 {} 条可在 Evidence 页查看。".format(
                max_evidence, len(unique_ev) - max_evidence,
            )
        )

    return UnderstandingCardViewModel(
        is_loaded=True,
        node_id=node_id,
        title=label,
        node_kind=kind,
        confidence="",
        summary_text=summary,
        relationships=[],
        claims=claim_summaries,
        rtl_targets=[],
        evidence_snippets=snippets,
        uncertainty_notes=uncertainty_notes,
        suggested_questions=[
            "这个 RTL 模块承载哪些概念？",
            "相关的 claim 可信度如何？",
            "有哪些源码证据？",
        ],
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# Evidence snippet builder
# ---------------------------------------------------------------------------


def _build_evidence_snippets(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    ev_ids: list[str],
    max_evidence: int,
) -> list[EvidenceSnippet]:
    """Build evidence snippets using source context from T029."""
    # We need a bundle to call build_source_context_for_evidence, but we
    # don't have one here.  Instead, build snippets from evidence_index
    # metadata and add code preview via a late-binding approach.
    snippets: list[EvidenceSnippet] = []
    shown = 0
    for eid in ev_ids:
        if shown >= max_evidence:
            break
        info = evidence_index.get(eid)
        if not isinstance(info, dict):
            continue

        file_path = info.get("file_path", "")
        symbol = info.get("symbol", "")
        strength = info.get("strength", "unknown")
        source_type = info.get("source_type", "")

        # Parse line range from evidence_id.
        import re
        line_range = ""
        m = re.search(r":(\d+)(?:-(\d+))?:", eid)
        if m:
            if m.group(2):
                line_range = "{}-{}".format(m.group(1), m.group(2))
            else:
                line_range = m.group(1)

        why = ""
        if "rtl" in source_type.lower():
            why = "RTL 侧证据"
        elif "concept" in source_type.lower():
            why = "L5/L6 概念侧证据"
        else:
            why = "桥接/映射证据"
        if symbol:
            why += "，符号 '{}'".format(symbol)

        snippets.append(EvidenceSnippet(
            evidence_id=eid,
            file_path=file_path,
            line_range=line_range,
            symbol=symbol,
            strength=strength,
            why_this_matters=why,
            code_preview_lines=[],
            is_source_available=False,  # Will be populated lazily in GUI.
        ))
        shown += 1

    return snippets


def populate_snippet_source_context(
    bundle: ArtifactBundle,
    snippets: list[EvidenceSnippet],
    max_preview_lines: int = 8,
) -> None:
    """Populate code_preview_lines for each snippet using T029 source context.

    Mutates snippets in place.  Safe to call — does not crash on missing files.
    """
    for snip in snippets:
        if not snip.evidence_id:
            continue
        ctx = build_source_context_for_evidence(bundle, snip.evidence_id, context_lines=2)
        if ctx.is_loaded and ctx.lines:
            preview = ctx.lines[:max_preview_lines]
            for sl in preview:
                marker = "▶" if sl.is_evidence_line else " "
                snip.code_preview_lines.append(
                    "{} {:4d} | {}".format(marker, sl.line_no, sl.text)
                )
            snip.is_source_available = True
        elif ctx.load_error:
            snip.code_preview_lines.append(
                "（源码不可用: {}）".format(ctx.load_error)
            )
            snip.is_source_available = False
