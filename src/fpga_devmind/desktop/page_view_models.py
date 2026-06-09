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
    get_project_graph,
    get_project_index,
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
    """A group of evidence rows with a title and optional description."""

    title: str
    rows: list[EvidenceRow] = field(default_factory=list)
    description: str = ""


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
    selected_node_id: str = "",
) -> EvidencePageViewModel:
    """Build evidence page data grouped by source type or concept."""
    if not bundle.is_complete:
        return EvidencePageViewModel(
            is_loaded=False,
            load_error="Bundle incomplete. Load a valid artifact bundle.",
        )

    if bundle.bundle_type == "project":
        return _build_project_evidence_page_view_model(bundle, selected_node_id)

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
        if row.source_type in (
            "concept_occurrence",
            "p1b_concept",
            "l5_l6",
            "concept",
        ):
            l5_l6_rows.append(row)
        elif row.source_type in (
            "rtl_source",
            "p1b_rtl",
            "rtl",
        ):
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


def _build_project_evidence_page_view_model(
    bundle: ArtifactBundle,
    selected_node_id: str = "",
) -> EvidencePageViewModel:
    """Build evidence page for project bundles grouped by mapping claim (T025).

    Each claim becomes an EvidenceGroup.  RTL nodes reachable via *realizes*
    edges from the claim are listed as RTL-side evidence rows.  L5/L6
    evidence is looked up from the project index by matching the claim's
    concept name.
    """
    graph = get_project_graph(bundle)
    index = get_project_index(bundle) or {}
    if graph is None:
        return EvidencePageViewModel(
            is_loaded=False,
            load_error="无法加载项目图数据。",
        )

    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    # Build lookup tables.
    node_by_id: dict[str, dict[str, Any]] = {}
    for n in raw_nodes:
        nid = n.get("node_id", "")
        if nid:
            node_by_id[nid] = n

    # Map claim_id -> list of target RTL node IDs (via realizes edges).
    claim_to_rtl: dict[str, list[str]] = {}
    for e in raw_edges:
        if e.get("edge_type") == "realizes":
            from_id = e.get("from_node_id", "")
            to_id = e.get("to_node_id", "")
            from_node = node_by_id.get(from_id, {})
            if from_node.get("kind") == "mapping_claim":
                claim_to_rtl.setdefault(from_id, []).append(to_id)

    # Evidence index keyed by concept.
    evidence_index = index.get("evidence_index", {})
    concept_to_evidence: dict[str, list[EvidenceRow]] = {}
    if isinstance(evidence_index, dict):
        for eid, info in evidence_index.items():
            if isinstance(info, dict):
                concept = info.get("concept", "")
                row = EvidenceRow(
                    evidence_id=eid,
                    source_type=info.get("source_type", "concept_occurrence"),
                    file_path=info.get("file_path", ""),
                    symbol=info.get("symbol", ""),
                    evidence_strength=info.get("strength", "unknown"),
                    referenced_by_claims=concept,
                )
                concept_to_evidence.setdefault(concept, []).append(row)

    # Build claim-centric groups.
    groups: list[EvidenceGroup] = []
    for n in raw_nodes:
        if n.get("kind") != "mapping_claim":
            continue
        claim_id = n.get("label", "")
        concept = n.get("concept", "")
        confidence = n.get("confidence", "unknown")
        bridge = n.get("bridge_kind", "unknown")

        # RTL-side evidence rows from realizes edges.
        rtl_rows: list[EvidenceRow] = []
        for rtl_id in claim_to_rtl.get(n.get("node_id", ""), []):
            rtl = node_by_id.get(rtl_id, {})
            rtl_rows.append(
                EvidenceRow(
                    evidence_id=rtl_id,
                    source_type=rtl.get("kind", "rtl"),
                    file_path=rtl.get("file_path", ""),
                    symbol=rtl.get("label", ""),
                    evidence_strength=rtl.get("confidence", "inferred"),
                    referenced_by_claims=claim_id,
                )
            )

        # L5/L6 evidence rows from index.
        l5_l6_rows = concept_to_evidence.get(concept, [])

        all_rows = l5_l6_rows + rtl_rows

        title = "Claim: {} (concept={}, confidence={})".format(
            claim_id, concept, confidence
        )
        desc = "bridge={} | L5/L6={} | RTL={}".format(
            bridge, len(l5_l6_rows), len(rtl_rows)
        )
        groups.append(
            EvidenceGroup(
                title=title,
                rows=all_rows,
                description=desc,
            )
        )

    # Filter by selected node (T028).
    if selected_node_id and groups:
        selected_node = node_by_id.get(selected_node_id, {})
        selected_kind = selected_node.get("kind", "")
        selected_label = selected_node.get("label", "")
        if selected_kind == "concept":
            groups = [
                g for g in groups
                if selected_label in g.title
            ]
        elif selected_kind in ("mapping_claim", "claim"):
            groups = [
                g for g in groups
                if selected_label in g.title
            ]
        elif selected_kind.startswith("rtl"):
            # Find claims that realize to this RTL node.
            realizing_claim_ids: set[str] = set()
            for e in raw_edges:
                if e.get("edge_type") == "realizes" and e.get("to_node_id") == selected_node_id:
                    from_node = node_by_id.get(e.get("from_node_id", ""), {})
                    if from_node.get("kind") == "mapping_claim":
                        realizing_claim_ids.add(from_node.get("label", ""))
            groups = [
                g for g in groups
                if any(cid in g.title for cid in realizing_claim_ids)
            ]
        else:
            # Unknown or nonexistent node kind — return empty.
            groups = []

    if not groups:
        return EvidencePageViewModel(
            is_loaded=True,
            groups=[
                EvidenceGroup(
                    title="项目证据",
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

    if bundle.bundle_type not in ("p1b", "project"):
        return UnknownsPageViewModel(
            is_loaded=False,
            load_error=(
                "当前 bundle 类型为 '{}'。不确定项页面需要 P1b / project trace bundle。".format(
                    bundle.bundle_type
                )
            ),
        )

    # Get uncertainty from graph
    if bundle.bundle_type == "project":
        graph = get_project_graph(bundle)
    else:
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

    if bundle.bundle_type == "project":
        graph = get_project_graph(bundle)
        meta = get_run_metadata(bundle) or {}

        claims_count = 0
        evidence_count = meta.get("evidence_items", 0)
        rtl_objects = 0
        unknowns = 0
        concept_count = 0

        if graph:
            for node in graph.get("nodes", []):
                kind = node.get("kind", "")
                if kind == "mapping_claim":
                    claims_count += 1
                elif kind.startswith("rtl_"):
                    rtl_objects += 1
                elif kind == "concept":
                    concept_count += 1
                    if node.get("confidence") == "unknown":
                        unknowns += 1

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
        # Check if noop_run exists in the same parent directory
        noop_path = bundle.directory.parent / "noop_run"
        noop_hint = ""
        if noop_path.exists():
            noop_hint = "\n\n已检测到 agent_runtime bundle:\n  {}".format(noop_path)
        return AgentRuntimePageState(
            is_visible=False,
            message=(
                "当前加载的是 {} bundle。"
                "Agent Runtime 页面需要 agent_runtime bundle。\n\n"
                "生成方式:\n"
                "  PYTHONPATH=src python -m fpga_devmind.cli desktop-sample-run\n"
                "  PYTHONPATH=src python -m fpga_devmind.desktop_app --recent"
                "{}"
            ).format(bundle.bundle_type, noop_hint),
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
