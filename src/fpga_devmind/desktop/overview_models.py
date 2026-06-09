"""Overview view models for the Desktop Agent Shell (T019).

User-facing overview that synthesizes bundle data into a human-readable
summary with suggested questions.  Deterministic templates only — no LLM.

Pure Python; testable without PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_agent_runtime_trace,
    get_graph,
    get_project_graph,
    get_run_metadata,
)
from fpga_devmind.desktop.trace_view_models import ConceptTraceViewModel


# ---------------------------------------------------------------------------
# Suggested questions
# ---------------------------------------------------------------------------


@dataclass
class SuggestedQuestion:
    """A suggested question for the Agent tab."""

    text: str  # e.g. "这个概念的整体情况如何？"
    topic: str  # e.g. "summary"


# ---------------------------------------------------------------------------
# Evidence / confidence summaries
# ---------------------------------------------------------------------------


@dataclass
class EvidenceStrengthSummary:
    """Counts of evidence items by strength level."""

    strong: int = 0
    medium: int = 0
    weak: int = 0
    unknown: int = 0
    total: int = 0


@dataclass
class MappingConfidenceSummary:
    """Counts of mapping claims by confidence level."""

    supported: int = 0
    inferred: int = 0
    unknown: int = 0
    confirmed: int = 0  # forward-compat; P1b never produces this
    total: int = 0


# ---------------------------------------------------------------------------
# Overview view model
# ---------------------------------------------------------------------------


@dataclass
class OverviewViewModel:
    """Human-oriented overview synthesized from artifact data."""

    # Identity
    project_path: str = ""
    concept_name: str = ""
    bundle_type: str = ""
    is_loaded: bool = False
    load_error: str | None = None

    # Natural language summary
    current_understanding: str = ""

    # Evidence summaries
    l5_l6_evidence_summary: EvidenceStrengthSummary = field(
        default_factory=EvidenceStrengthSummary
    )
    rtl_evidence_summary: EvidenceStrengthSummary = field(
        default_factory=EvidenceStrengthSummary
    )

    # Mapping confidence
    mapping_confidence: MappingConfidenceSummary = field(
        default_factory=MappingConfidenceSummary
    )

    # Uncertainty
    unknown_limitations: list[str] = field(default_factory=list)

    # Suggested questions
    suggested_questions: list[SuggestedQuestion] = field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Default question sets
# ---------------------------------------------------------------------------

_P1B_QUESTIONS: list[SuggestedQuestion] = [
    SuggestedQuestion(
        text="这个概念的整体情况如何？", topic="summary"
    ),
    SuggestedQuestion(
        text="有哪些映射声明？可信度如何？", topic="claims"
    ),
    SuggestedQuestion(
        text="有什么证据支持这些映射？", topic="evidence"
    ),
    SuggestedQuestion(
        text="有哪些不确定或未确认的部分？", topic="unknown"
    ),
    SuggestedQuestion(
        text="有哪些诊断信息？", topic="diagnostics"
    ),
    SuggestedQuestion(
        text="节点之间的关系是什么？", topic="edges"
    ),
]

_AGENT_RUNTIME_QUESTIONS: list[SuggestedQuestion] = [
    SuggestedQuestion(
        text="Agent 执行了什么任务？", topic="summary"
    ),
    SuggestedQuestion(
        text="Agent 的推理过程是什么？", topic="reasoning"
    ),
    SuggestedQuestion(
        text="Agent 产出了什么答案？", topic="answer"
    ),
]

_PROJECT_QUESTIONS: list[SuggestedQuestion] = [
    SuggestedQuestion(
        text="这个项目整体实现了什么？", topic="summary"
    ),
    SuggestedQuestion(
        text="有哪些概念？", topic="concepts"
    ),
    SuggestedQuestion(
        text="哪些概念有 RTL 映射？", topic="mapped"
    ),
    SuggestedQuestion(
        text="哪些概念还不确定？", topic="unknown"
    ),
    SuggestedQuestion(
        text="哪些 RTL 文件承载了多个概念？", topic="shared"
    ),
    SuggestedQuestion(
        text="画出项目理解图", topic="graph"
    ),
]

_NO_BUNDLE_QUESTIONS: list[SuggestedQuestion] = [
    SuggestedQuestion(
        text="请在上方输入 artifact 目录，或使用 Browse... 选择。", topic="help"
    ),
]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_overview_view_model(
    bundle: ArtifactBundle,
) -> OverviewViewModel:
    """Build an OverviewViewModel from a loaded bundle.

    Never raises; all errors produce is_loaded=False with helpful messages.
    """
    if not bundle.is_complete:
        errors = [
            d.message
            for d in bundle.diagnostics
            if d.severity == "error"
        ]
        return OverviewViewModel(
            bundle_type=bundle.bundle_type,
            is_loaded=False,
            load_error="; ".join(errors) if errors else "Incomplete bundle",
            suggested_questions=_NO_BUNDLE_QUESTIONS,
        )

    if bundle.bundle_type == "p1b":
        return _build_p1b_overview(bundle)

    if bundle.bundle_type == "project":
        return _build_project_overview(bundle)

    if bundle.bundle_type == "agent_runtime":
        return _build_agent_runtime_overview(bundle)

    if bundle.bundle_type == "p1a":
        return _build_p1a_overview(bundle)

    return OverviewViewModel(
        bundle_type="unknown",
        is_loaded=False,
        load_error="Unknown bundle type. Expected P1b, project, P1a, or agent_runtime.",
        suggested_questions=_NO_BUNDLE_QUESTIONS,
    )


# ---------------------------------------------------------------------------
# P1b overview
# ---------------------------------------------------------------------------


def _build_p1b_overview(
    bundle: ArtifactBundle,
) -> OverviewViewModel:
    """Build overview for a P1b concept trace bundle."""
    meta = get_run_metadata(bundle) or {}
    graph = get_graph(bundle)

    concept = meta.get("concept", "")
    project = meta.get("project_root", "")

    # Evidence summaries
    l5_l6_ev = EvidenceStrengthSummary()
    rtl_ev = EvidenceStrengthSummary()

    evidence_items: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    if graph:
        evidence_items = graph.get("evidence_items", [])

    for item in evidence_items:
        source = item.get("source_type", "")
        strength = item.get("evidence_strength", "unknown")
        if source in ("concept_occurrence", "p1b_concept", "l5_l6"):
            target = l5_l6_ev
        elif source in ("rtl_source", "p1b_rtl", "rtl"):
            target = rtl_ev
        else:
            target = rtl_ev
        _increment_strength(target, strength)

    # Mapping confidence
    mapping_conf = MappingConfidenceSummary()
    claims: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    if graph:
        claims = graph.get("mapping_claims", [])

    for claim in claims:
        conf = claim.get("confidence", "unknown")
        _increment_confidence(mapping_conf, conf)

    # Current understanding
    nodes: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    if graph:
        nodes = graph.get("nodes", [])

    node_kinds: dict[str, int] = {}
    for node in nodes:
        kind = node.get("kind", "unknown")
        node_kinds[kind] = node_kinds.get(kind, 0) + 1

    kind_parts = ", ".join(
        "{} {}".format(v, k) for k, v in sorted(node_kinds.items())
    )
    claim_parts = _format_confidence_summary(mapping_conf)
    ev_total = l5_l6_ev.total + rtl_ev.total

    # Extract L5/L6 symbols and files
    l5_files: set[str] = set()
    l5_symbols: set[str] = set()
    rtl_files: set[str] = set()
    rtl_modules: set[str] = set()
    rtl_signals: set[str] = set()
    for item in evidence_items:
        src = item.get("source_type", "")
        sym = item.get("symbol", "")
        fp = item.get("file_path", "")
        if src in ("concept_occurrence", "p1b_concept", "l5_l6"):
            if sym:
                l5_symbols.add(sym)
            if fp:
                l5_files.add(fp.split("/")[-1])
        elif src in ("rtl_source", "p1b_rtl", "rtl"):
            if fp:
                rtl_files.add(fp.split("/")[-1])
            if sym:
                # Classify RTL symbols by node kind if available
                rtl_signals.add(sym)

    # Extract mapping claim details
    claim_details: list[str] = []
    for claim in claims[:3]:
        cid = claim.get("claim_id", "")
        conf = claim.get("confidence", "unknown")
        bridge = claim.get("bridge_kind", "unknown")
        l5_ids = claim.get("l5_l6_evidence_ids", [])
        rtl_ids = claim.get("rtl_evidence_ids", [])
        l5_n = len(l5_ids) if isinstance(l5_ids, list) else 0
        rtl_n = len(rtl_ids) if isinstance(rtl_ids, list) else 0
        claim_details.append(
            "{} — 可信度 {}，桥接类型 {}（L5/L6 证据 {} 条，RTL 证据 {} 条）".format(
                cid, conf, bridge, l5_n, rtl_n
            )
        )

    understanding_lines: list[str] = []
    understanding_lines.append(
        "概念 '{}' 在 L5/L6 Python 代码和 RTL Verilog 之间建立了映射追踪。".format(
            concept
        )
    )
    understanding_lines.append("")

    # L5/L6 side
    if l5_symbols:
        syms = ", ".join(sorted(l5_symbols)[:8])
        if len(l5_symbols) > 8:
            syms += " 等 {} 个符号".format(len(l5_symbols))
        understanding_lines.append(
            "L5/L6 侧：在 {} 个源码文件中发现 {} 个相关符号，包括 {}。".format(
                len(l5_files), len(l5_symbols), syms
            )
        )
    else:
        understanding_lines.append("L5/L6 侧：未提取到相关符号。")

    # RTL side
    if rtl_files:
        files = ", ".join(sorted(rtl_files)[:5])
        if len(rtl_files) > 5:
            files += " 等"
        understanding_lines.append(
            "RTL 侧：在 {} 个 Verilog 文件中发现 {} 个相关模块/信号/always/assign。".format(
                len(rtl_files),
                sum(1 for n in nodes if n.get("kind", "").startswith("rtl_")),
            )
        )
    else:
        understanding_lines.append("RTL 侧：未提取到相关模块/信号。")

    understanding_lines.append("")

    # Mapping claims
    if claim_details:
        understanding_lines.append("映射声明：")
        for cd in claim_details:
            understanding_lines.append("  " + cd)
    else:
        understanding_lines.append("映射声明：暂无。")

    understanding_lines.append("")
    understanding_lines.append(
        "证据统计：共 {} 条（L5/L6 {} 条，RTL {} 条）。".format(
            ev_total, l5_l6_ev.total, rtl_ev.total
        )
    )

    # Why not confirmed
    understanding_lines.append("")
    why_not = (
        "当前 mapping claims 未标记为 confirmed。原因："
        "证据强度不足（命名匹配 alone 只能得到 inferred）；"
        "需要人工 review 后才能提升到 supported 或 confirmed。"
    )
    understanding_lines.append(why_not)

    # Unknown / limitations
    limitations: list[str] = []
    if graph:
        for note in graph.get("uncertainty_notes", []):
            reason = note.get("reason", "")
            if reason:
                limitations.append(reason)
    for claim in claims:
        if claim.get("confidence") == "unknown":
            missing = claim.get("required_missing_evidence", [])
            if isinstance(missing, list) and missing:
                limitations.append(
                    "映射声明 {} 缺少证据: {}".format(
                        claim.get("claim_id", ""),
                        ", ".join(missing),
                    )
                )

    # Status note
    status = meta.get("status", "unknown")
    blocking = meta.get("blocking_diagnostics", 0)
    if blocking > 0:
        limitations.append(
            "存在 {} 条阻断性诊断，建议检查。".format(blocking)
        )
    elif status == "ok":
        understanding_lines.append("")
        understanding_lines.append("状态：正常，无阻断性诊断。")

    return OverviewViewModel(
        project_path=project,
        concept_name=concept,
        bundle_type="p1b",
        is_loaded=True,
        current_understanding="\n".join(understanding_lines),
        l5_l6_evidence_summary=l5_l6_ev,
        rtl_evidence_summary=rtl_ev,
        mapping_confidence=mapping_conf,
        unknown_limitations=limitations,
        suggested_questions=_P1B_QUESTIONS,
    )


# ---------------------------------------------------------------------------
# Project overview
# ---------------------------------------------------------------------------


def _build_project_overview(
    bundle: ArtifactBundle,
) -> OverviewViewModel:
    """Build overview for a project-level understanding bundle."""
    graph = get_project_graph(bundle)
    meta = get_run_metadata(bundle) or {}

    project = meta.get("project_root", "")
    concepts = meta.get("concepts_processed", [])
    failed = meta.get("concepts_failed", [])

    # Aggregate evidence and claims across all concepts.
    l5_l6_ev = EvidenceStrengthSummary()
    rtl_ev = EvidenceStrengthSummary()
    mapping_conf = MappingConfidenceSummary()
    total_evidence = 0
    total_claims = 0
    rtl_objects = 0
    unknowns = 0

    if graph:
        for node in graph.get("nodes", []):
            if node.get("kind", "").startswith("rtl_"):
                rtl_objects += 1
            if node.get("kind", "") == "concept":
                conf = node.get("confidence", "unknown")
                if conf == "unknown":
                    unknowns += 1
        total_claims = sum(
            1 for n in graph.get("nodes", []) if n.get("kind") == "mapping_claim"
        )

    # Try to get evidence counts from metadata.
    total_evidence = meta.get("evidence_items", 0)

    # Build understanding text.
    lines: list[str] = []
    lines.append(
        "项目 '{}' 识别出 {} 个概念：{}。".format(
            project, len(concepts), ", ".join(concepts)
        )
    )
    if failed:
        lines.append(
            "其中 {} 个概念 trace 失败: {}。".format(
                len(failed), ", ".join(failed)
            )
        )
    lines.append("")
    lines.append(
        "聚合统计：{} 个 mapping claims，{} 条证据，{} 个 RTL 对象。".format(
            total_claims, total_evidence, rtl_objects
        )
    )
    if unknowns:
        lines.append("{} 个概念存在 unknown 状态。".format(unknowns))
    lines.append("")
    lines.append(
        "项目级理解图展示了概念之间的结构关系（shared file / shared RTL）。"
    )

    # Limitations from graph diagnostics.
    limitations: list[str] = []
    if graph:
        for diag in graph.get("grounding_diagnostics", []):
            msg = diag.get("message", "")
            if msg:
                limitations.append(msg)

    return OverviewViewModel(
        project_path=project,
        concept_name=", ".join(concepts) if concepts else "",
        bundle_type="project",
        is_loaded=True,
        current_understanding="\n".join(lines),
        l5_l6_evidence_summary=l5_l6_ev,
        rtl_evidence_summary=rtl_ev,
        mapping_confidence=mapping_conf,
        unknown_limitations=limitations,
        suggested_questions=_PROJECT_QUESTIONS,
    )


# ---------------------------------------------------------------------------
# Agent Runtime overview
# ---------------------------------------------------------------------------


def _build_agent_runtime_overview(
    bundle: ArtifactBundle,
) -> OverviewViewModel:
    """Build overview for an agent_runtime bundle."""
    trace = get_agent_runtime_trace(bundle)
    if trace is None:
        return OverviewViewModel(
            bundle_type="agent_runtime",
            is_loaded=False,
            load_error="agent_runtime_trace.json not found or invalid",
            suggested_questions=_NO_BUNDLE_QUESTIONS,
        )

    task = trace.get("task", {})
    task_id = task.get("task_id", "")
    question = task.get("question", "")
    concept = task.get("concept", "")
    bundle_path = task.get("artifact_bundle_path", "")

    answers = trace.get("answers", [])
    steps = trace.get("steps", [])
    graph_writes = trace.get("graph_write_proposals", [])

    understanding_lines: list[str] = []
    understanding_lines.append(
        "Agent 运行 '{}' 的 trace。".format(task_id)
    )
    understanding_lines.append("")
    understanding_lines.append(
        "问题: {}".format(question)
    )
    if concept:
        understanding_lines.append("概念: {}".format(concept))
    understanding_lines.append(
        "步骤: {} | 答案: {} | Graph write 提案: {}".format(
            len(steps), len(answers), len(graph_writes)
        )
    )

    # Constraints
    constraints = task.get("constraints", [])
    if constraints:
        understanding_lines.append("")
        understanding_lines.append(
            "约束: {}".format(", ".join(constraints))
        )

    return OverviewViewModel(
        project_path=bundle_path,
        concept_name=concept,
        bundle_type="agent_runtime",
        is_loaded=True,
        current_understanding="\n".join(understanding_lines),
        suggested_questions=_AGENT_RUNTIME_QUESTIONS,
    )


# ---------------------------------------------------------------------------
# P1a overview (minimal)
# ---------------------------------------------------------------------------


def _build_p1a_overview(
    bundle: ArtifactBundle,
) -> OverviewViewModel:
    """Build overview for a P1a bundle (limited information)."""
    meta = get_run_metadata(bundle) or {}
    project = meta.get("project_root", "")
    concept = meta.get("concept", "")

    return OverviewViewModel(
        project_path=project,
        concept_name=concept,
        bundle_type="p1a",
        is_loaded=True,
        current_understanding=(
            "P1a 项目理解 artifact。"
            "项目: {}。概念: {}。".format(
                project, concept or "(未指定)"
            )
        ),
        suggested_questions=_P1B_QUESTIONS,  # reuse P1b questions
    )


# ---------------------------------------------------------------------------
# Concept trace summary formatter
# ---------------------------------------------------------------------------


def format_concept_trace_summary(
    vm: ConceptTraceViewModel,
) -> str:
    """Format a ConceptTraceViewModel into a three-section natural-language
    summary: L5/L6 side → Mapping claims → RTL side.

    Deterministic template — no LLM.
    """
    if not vm.is_loaded:
        return vm.load_error or "无法加载概念 trace 数据。"

    sections: list[str] = []

    # --- L5/L6 side ---
    l5_files: set[str] = set()
    l5_symbols: list[str] = []
    l5_strengths: dict[str, int] = {}

    for row in vm.evidence:
        if row.source_type in (
            "concept_occurrence",
            "p1b_concept",
            "concept",
            "l5_l6",
        ):
            if row.file_path:
                l5_files.add(row.file_path)
            if row.symbol:
                l5_symbols.append(row.symbol)
            s = row.evidence_strength or "unknown"
            l5_strengths[s] = l5_strengths.get(s, 0) + 1

    if l5_files or l5_symbols:
        sections.append("## L5/L6 代码侧")
        sections.append("")
        if l5_files:
            sections.append(
                "涉及文件: {}".format(
                    ", ".join(sorted(f.split("/")[-1] for f in l5_files))
                )
            )
        if l5_symbols:
            # Deduplicate
            unique_syms = sorted(set(l5_symbols))[:10]
            sections.append(
                "符号: {}".format(", ".join(unique_syms))
            )
            if len(set(l5_symbols)) > 10:
                sections.append(
                    "  ... 等 {} 个符号".format(len(set(l5_symbols)))
                )
        if l5_strengths:
            parts = [
                "{}: {}".format(k, v)
                for k, v in sorted(l5_strengths.items())
            ]
            sections.append("证据强度: {}".format(", ".join(parts)))
        sections.append("")

    # --- Mapping claims ---
    if vm.claims:
        sections.append("## 映射声明")
        sections.append("")
        for claim in vm.claims:
            line = "{} — 可信度: {}, 桥接类型: {}".format(
                claim.claim_id,
                _translate_confidence(claim.confidence),
                claim.bridge_kind,
            )
            if claim.required_missing_evidence:
                line += ", 缺少: {}".format(claim.required_missing_evidence)
            sections.append(line)
        sections.append("")

    # --- RTL side ---
    rtl_files: set[str] = set()
    rtl_kinds: dict[str, int] = {}

    for row in vm.evidence:
        if row.source_type in (
            "rtl_source",
            "p1b_rtl",
            "rtl",
        ):
            if row.file_path:
                rtl_files.add(row.file_path)
            sym = row.symbol or ""
            if sym:
                rtl_kinds[sym] = rtl_kinds.get(sym, 0) + 1

    if rtl_files or rtl_kinds:
        sections.append("## RTL 侧")
        sections.append("")
        if rtl_files:
            sections.append(
                "涉及文件: {}".format(
                    ", ".join(sorted(f.split("/")[-1] for f in rtl_files))
                )
            )
        if rtl_kinds:
            kind_parts = [
                "{}: {}".format(k, v)
                for k, v in sorted(rtl_kinds.items())
            ]
            sections.append("证据类型: {}".format(", ".join(kind_parts)))
        sections.append("")

    if not sections:
        return "暂无 L5/L6 或 RTL 证据数据。"

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _increment_strength(
    target: EvidenceStrengthSummary, strength: str
) -> None:
    """Increment the appropriate strength counter."""
    target.total += 1
    if strength == "strong":
        target.strong += 1
    elif strength == "medium":
        target.medium += 1
    elif strength == "weak":
        target.weak += 1
    else:
        target.unknown += 1


def _increment_confidence(
    target: MappingConfidenceSummary, confidence: str
) -> None:
    """Increment the appropriate confidence counter."""
    target.total += 1
    if confidence == "supported":
        target.supported += 1
    elif confidence == "inferred":
        target.inferred += 1
    elif confidence == "confirmed":
        target.confirmed += 1
    else:
        target.unknown += 1


def _format_confidence_summary(mc: MappingConfidenceSummary) -> str:
    """Format mapping confidence as a readable string."""
    parts: list[str] = []
    if mc.supported:
        parts.append("{} supported".format(mc.supported))
    if mc.inferred:
        parts.append("{} inferred".format(mc.inferred))
    if mc.unknown:
        parts.append("{} unknown".format(mc.unknown))
    if mc.confirmed:
        parts.append("{} confirmed".format(mc.confirmed))
    return ", ".join(parts) if parts else "none"


def _translate_confidence(confidence: str) -> str:
    """Translate confidence label to Chinese."""
    mapping = {
        "supported": "有支持",
        "inferred": "推断",
        "unknown": "未知",
        "confirmed": "已确认",
    }
    return mapping.get(confidence, confidence)
