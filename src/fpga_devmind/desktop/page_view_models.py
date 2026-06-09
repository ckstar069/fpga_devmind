"""Page view models for the T020 AgentScope-style product shell.

Pure Python view models that prepare data for each page of the desktop
product shell.  No PySide6 dependency.  Deterministic templates only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_agent_runtime_trace,
    get_graph,
    get_run_metadata,
)
from fpga_devmind.desktop.trace_view_models import (
    EvidenceRow,
    build_concept_trace_view_model,
)


# ---------------------------------------------------------------------------
# Evidence page
# ---------------------------------------------------------------------------


@dataclass
class EvidenceGroup:
    """A group of evidence rows with a title."""

    title: str
    rows: list[EvidenceRow] = field(default_factory=list)


@dataclass
class EvidencePageViewModel:
    """View model for the Evidence page."""

    is_loaded: bool = False
    load_error: str | None = None
    groups: list[EvidenceGroup] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Unknowns page
# ---------------------------------------------------------------------------


@dataclass
class UnknownsPageViewModel:
    """View model for the Unknowns / Uncertainty page."""

    is_loaded: bool = False
    load_error: str | None = None
    limitations: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    grounding_diagnostics: list[dict[str, Any]] = field(  # pyright: ignore[reportExplicitAny]
        default_factory=list
    )
    why_not_confirmed: str = ""


# ---------------------------------------------------------------------------
# Overview metrics
# ---------------------------------------------------------------------------


@dataclass
class OverviewMetrics:
    """Key metrics for the Overview page cards."""

    mapping_claims: int = 0
    evidence_items: int = 0
    rtl_objects: int = 0
    unknowns: int = 0
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Agent Runtime page state
# ---------------------------------------------------------------------------


@dataclass
class AgentRuntimePageState:
    """State description for the Agent Runtime page."""

    is_visible: bool = False
    is_loaded: bool = False
    load_error: str | None = None
    message: str = ""
    has_trace: bool = False


# ---------------------------------------------------------------------------
# Plan / Tools page state
# ---------------------------------------------------------------------------


@dataclass
class PlanToolsPageState:
    """State for the Plan & Tools page."""

    has_plan: bool = False
    display_text: str = ""


def build_plan_tools_page_state(plan_preview_text: str) -> PlanToolsPageState:
    """Build plan tools page state from the last plan preview text."""
    if not plan_preview_text:
        return PlanToolsPageState(
            has_plan=False,
            display_text=(
                "请先在 Agent 问答页选择建议问题或输入问题，"
                "系统会在这里显示只读工具计划。"
            ),
        )
    return PlanToolsPageState(has_plan=True, display_text=plan_preview_text)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_evidence_page_view_model(
    bundle: ArtifactBundle,
) -> EvidencePageViewModel:
    """Build evidence page data grouped by source type."""
    if not bundle.is_complete:
        return EvidencePageViewModel(
            is_loaded=False,
            load_error="Bundle incomplete. Load a valid artifact bundle.",
        )

    if bundle.bundle_type != "p1b":
        return EvidencePageViewModel(
            is_loaded=False,
            load_error=(
                "当前 bundle 类型为 '{}'，不包含 P1b 证据数据。".format(
                    bundle.bundle_type
                )
            ),
        )

    trace_vm = build_concept_trace_view_model(bundle)
    if not trace_vm.is_loaded:
        return EvidencePageViewModel(
            is_loaded=False,
            load_error=trace_vm.load_error or "无法加载证据数据。",
        )

    l5_l6_rows: list[EvidenceRow] = []
    rtl_rows: list[EvidenceRow] = []
    bridge_rows: list[EvidenceRow] = []

    for row in trace_vm.evidence:
        if row.source_type.startswith("p1b_concept") or row.source_type in (
            "concept",
            "l5_l6",
        ):
            l5_l6_rows.append(row)
        elif row.source_type.startswith("p1b_rtl") or row.source_type == "rtl":
            rtl_rows.append(row)
        else:
            bridge_rows.append(row)

    groups: list[EvidenceGroup] = []
    if l5_l6_rows:
        groups.append(EvidenceGroup(title="L5/L6 代码证据", rows=l5_l6_rows))
    if rtl_rows:
        groups.append(EvidenceGroup(title="RTL 证据", rows=rtl_rows))
    if bridge_rows:
        groups.append(EvidenceGroup(title="桥接/映射证据", rows=bridge_rows))

    if not groups:
        return EvidencePageViewModel(
            is_loaded=True,
            load_error=None,
            groups=[
                EvidenceGroup(
                    title="证据",
                    rows=[],
                )
            ],
        )

    return EvidencePageViewModel(is_loaded=True, groups=groups)


def build_unknowns_page_view_model(
    bundle: ArtifactBundle,
) -> UnknownsPageViewModel:
    """Build unknowns / uncertainty page data."""
    if not bundle.is_complete:
        return UnknownsPageViewModel(
            is_loaded=False,
            load_error="Bundle incomplete. Load a valid artifact bundle.",
        )

    if bundle.bundle_type != "p1b":
        return UnknownsPageViewModel(
            is_loaded=False,
            load_error=(
                "当前 bundle 类型为 '{}'。不确定项页面需要 P1b concept trace bundle。".format(
                    bundle.bundle_type
                )
            ),
        )

    # Get uncertainty from graph
    graph = get_graph(bundle)
    limitations: list[str] = []
    uncertainty_notes: list[str] = []
    grounding_diags: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    if graph:
        for note in graph.get("uncertainty_notes", []):
            reason = note.get("reason", "")
            if reason:
                uncertainty_notes.append(reason)

        for claim in graph.get("mapping_claims", []):
            if claim.get("confidence") == "unknown":
                missing = claim.get("required_missing_evidence", [])
                if isinstance(missing, list) and missing:
                    limitations.append(
                        "映射声明 {} 缺少证据: {}".format(
                            claim.get("claim_id", ""),
                            ", ".join(missing),
                        )
                    )

        grounding = graph.get("grounding_diagnostics", [])
        if grounding:
            grounding_diags = grounding

    # Why not confirmed explanation
    why_not = (
        "当前 mapping claims 未标记为 confirmed，原因包括:\n"
        "1. 证据强度不足（命名匹配 alone 只能得到 inferred）\n"
        "2. 缺少 RTL 侧或 L5/L6 侧的对应证据\n"
        "3. bridge_kind 为 naming_only 时 confidence 自动降级\n"
        "4. 需要人工 review 后才能提升到 supported 或 confirmed"
    )

    return UnknownsPageViewModel(
        is_loaded=True,
        limitations=limitations,
        uncertainty_notes=uncertainty_notes,
        grounding_diagnostics=grounding_diags,
        why_not_confirmed=why_not,
    )


def build_overview_metrics(bundle: ArtifactBundle) -> OverviewMetrics:
    """Build overview metrics card data."""
    if not bundle.is_complete:
        return OverviewMetrics(is_loaded=False)

    if bundle.bundle_type == "p1b":
        graph = get_graph(bundle)
        meta = get_run_metadata(bundle) or {}

        claims_count = 0
        evidence_count = 0
        rtl_objects = 0
        unknowns = 0

        if graph:
            claims_count = len(graph.get("mapping_claims", []))
            evidence_count = len(graph.get("evidence_items", []))
            for node in graph.get("nodes", []):
                if node.get("kind", "").startswith("rtl_"):
                    rtl_objects += 1
            unknowns = len(graph.get("uncertainty_notes", []))

        return OverviewMetrics(
            mapping_claims=claims_count,
            evidence_items=evidence_count,
            rtl_objects=rtl_objects,
            unknowns=unknowns,
            is_loaded=True,
        )

    if bundle.bundle_type == "agent_runtime":
        trace = get_agent_runtime_trace(bundle)
        if trace:
            steps = len(trace.get("steps", []))
            answers = len(trace.get("answers", []))
            writes = len(trace.get("graph_write_proposals", []))
            return OverviewMetrics(
                mapping_claims=answers,
                evidence_items=steps,
                rtl_objects=writes,
                unknowns=0,
                is_loaded=True,
            )

    return OverviewMetrics(is_loaded=True)


def build_agent_runtime_page_state(
    bundle: ArtifactBundle,
) -> AgentRuntimePageState:
    """Determine Agent Runtime page visibility and state."""
    if bundle is None or not bundle.is_complete:
        return AgentRuntimePageState(
            is_visible=False,
            message="请先加载 artifact bundle。",
        )

    if bundle.bundle_type != "agent_runtime":
        return AgentRuntimePageState(
            is_visible=False,
            message=(
                "当前加载的是 {} bundle。"
                "Agent Runtime 页面需要 agent_runtime bundle。\n\n"
                "生成方式:\n"
                "  PYTHONPATH=src python -m fpga_devmind.cli desktop-sample-run\n"
                "  PYTHONPATH=src python -m fpga_devmind.desktop_app --recent"
            ).format(bundle.bundle_type),
        )

    trace = get_agent_runtime_trace(bundle)
    if trace is None:
        return AgentRuntimePageState(
            is_visible=True,
            is_loaded=False,
            load_error="agent_runtime_trace.json not found or invalid.",
        )

    return AgentRuntimePageState(
        is_visible=True,
        is_loaded=True,
        has_trace=True,
    )
