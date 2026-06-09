"""Agent tool plan preview models for the Desktop Agent Shell (T012).

Read-only plan preview: shows what tools/artifacts a future Agent mode
would need, but does NOT execute them.  No LLM, no external API,
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
    get_run_metadata,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AgentPlanStep:
    """A single read-only step in an Agent tool plan preview."""

    step_id: str = ""
    title: str = ""
    rationale: str = ""
    read_artifacts: list[str] = field(default_factory=list)
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    allowed_action: str = "read_only_preview"
    is_executable_now: bool = False


@dataclass
class AgentPlanPreview:
    """Read-only preview of the tool/action plan for a user question."""

    question: str = ""
    intent: str = ""
    steps: list[AgentPlanStep] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_agent_plan_preview(
    bundle: ArtifactBundle,
    question: str,
    response: Any | None = None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    """Build a read-only tool plan preview for *question*.

    Never raises; all errors return ``is_loaded=False``.
    """
    if not bundle.is_complete:
        errors = [
            d.message for d in bundle.diagnostics if d.severity == "error"
        ]
        return AgentPlanPreview(
            question=question,
            is_loaded=False,
            load_error="; ".join(errors) if errors else "Incomplete bundle",
        )

    if bundle.bundle_type not in ("p1b", "p1a"):
        return AgentPlanPreview(
            question=question,
            is_loaded=False,
            load_error="Agent plan available for P1a/P1b bundles only",
        )

    graph = get_graph(bundle)
    index = get_index(bundle) or {}
    grounding = get_grounding_report(bundle) or {}
    _meta = get_run_metadata(bundle) or {}  # noqa: F841

    normalized = question.strip().lower()

    # Specific ID lookups first (use original question to preserve case).
    claim_match = extract_claim_id(question)
    if claim_match:
        return _plan_claim_detail(
            question, graph, claim_match, index, grounding, response
        )

    evidence_match = extract_evidence_id(question)
    if evidence_match:
        return _plan_evidence_detail(
            question, graph, evidence_match, index, response
        )

    # Keyword-based routing — MUST match agent_panel_models.py order.
    # Summary first (broadest).
    if has_any(
        normalized, ["summary", "概况", "整体情况", "做了什么", "overview", "about"]
    ):
        return _plan_summary(question, graph, _meta, grounding, response)

    # Evidence before claims to avoid "有什么证据支持这些映射"
    # being mis-routed to claims because it contains "映射".
    if has_any(normalized, ["evidence", "证据", "proof"]):
        return _plan_evidence(question, graph, index, response)

    if has_any(
        normalized, ["claims", "mapping", "映射", "claim", "mapping claims"]
    ):
        return _plan_claims(question, graph, index, response)

    if has_any(
        normalized, ["diagnostics", "grounding", "诊断", "checker"]
    ):
        return _plan_diagnostics(question, graph, grounding, response)

    if has_any(
        normalized, ["unknown", "不确定", "uncertainty", "unsure"]
    ):
        return _plan_unknown(question, graph, response)

    # Edges before nodes to avoid "节点之间的关系是什么"
    # being mis-routed to nodes because it contains "节点".
    if has_any(normalized, ["edges", "edge", "边", "关系"]):
        return _plan_edges(question, graph, response)

    if has_any(normalized, ["nodes", "node", "节点"]):
        return _plan_nodes(question, graph, response)

    # Fallback.
    return AgentPlanPreview(
        question=question,
        intent="unsupported",
        steps=[],
        safety_notes=_default_safety_notes(),
        unsupported_reason="question_type_not_recognized",
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_safety_notes() -> list[str]:
    return [
        "read-only artifact query — no write to artifact directory",
        "no external LLM / API call",
        "no API key loading",
        "no Vivado / synthesis / implementation / bitstream",
        "no mutation to fpga_project_* target projects",
        "this is a preview plan; steps are not executed automatically",
    ]


def _base_step(
    step_id: str,
    title: str,
    rationale: str,
    read_artifacts: list[str] | None = None,
    response: Any | None = None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanStep:
    """Create a plan step, optionally inheriting referenced IDs from *response*."""
    step = AgentPlanStep(
        step_id=step_id,
        title=title,
        rationale=rationale,
        read_artifacts=list(read_artifacts) if read_artifacts else [],
    )
    if response:
        step.referenced_claim_ids = list(
            getattr(response, "referenced_claim_ids", [])
        )
        step.referenced_evidence_ids = list(
            getattr(response, "referenced_evidence_ids", [])
        )
        step.referenced_node_ids = list(
            getattr(response, "referenced_node_ids", [])
        )
        step.referenced_diagnostic_ids = list(
            getattr(response, "referenced_diagnostic_ids", [])
        )
    return step


# ---------------------------------------------------------------------------
# Plan builders
# ---------------------------------------------------------------------------


def _plan_summary(
    question: str,
    _graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    _meta: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    _grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps = [
        _base_step(
            "S1",
            "Read run_metadata",
            "Obtain concept, status, claim/evidence counts, elapsed time.",
            ["run_metadata.json"],
        ),
        _base_step(
            "S2",
            "Read concept_trace_graph",
            "Obtain node/edge counts and graph topology.",
            ["concept_trace_graph.json"],
            response,
        ),
        _base_step(
            "S3",
            "Read grounding_report",
            "Obtain diagnostic summary counts.",
            ["grounding_report.json"],
        ),
    ]
    return AgentPlanPreview(
        question=question,
        intent="summary",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_claims(
    question: str,
    _graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "Enumerate mapping_claims and classify by confidence/bridge.",
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    if index:
        steps.append(
            _base_step(
                "S2",
                "Read concept_trace_index",
                "Cross-reference claims via claim_index.",
                ["concept_trace_index.json"],
            )
        )
    return AgentPlanPreview(
        question=question,
        intent="claims",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_evidence(
    question: str,
    _graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "Enumerate evidence_items with source_type, symbol, strength.",
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    if index:
        steps.append(
            _base_step(
                "S2",
                "Read concept_trace_index",
                "Cross-reference evidence via evidence_index.",
                ["concept_trace_index.json"],
            )
        )
    return AgentPlanPreview(
        question=question,
        intent="evidence",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_diagnostics(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    diags = deduplicate_diagnostics(graph, grounding)
    steps = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "Collect grounding_diagnostics from graph.",
            ["concept_trace_graph.json"],
            response,
        ),
        _base_step(
            "S2",
            "Read grounding_report",
            "Collect diagnostics from grounding report and merge with dedup.",
            ["grounding_report.json"],
        ),
    ]
    if diags:
        steps.append(
            AgentPlanStep(
                step_id="S3",
                title="Merge and deduplicate",
                rationale=(
                    "Primary key: diagnostic_id; fallback: "
                    "(target_claim_id, issue_type, message)."
                ),
                read_artifacts=[],
                referenced_diagnostic_ids=[
                    d.get("diagnostic_id", "") for d in diags
                ],
            )
        )
    return AgentPlanPreview(
        question=question,
        intent="diagnostics",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_unknown(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "Filter claims by confidence == 'unknown'. Collect uncertainty_notes.",
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    if graph:
        unknown_claims = [
            c for c in graph.get("mapping_claims", [])
            if c.get("confidence") == "unknown"
        ]
        if unknown_claims:
            steps.append(
                AgentPlanStep(
                    step_id="S2",
                    title="Inspect required_missing_evidence",
                    rationale=(
                        "List what evidence is missing for each "
                        "unknown-confidence claim."
                    ),
                    read_artifacts=[],
                    referenced_claim_ids=[
                        c.get("claim_id", "") for c in unknown_claims
                    ],
                )
            )
    return AgentPlanPreview(
        question=question,
        intent="unknown",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_nodes(
    question: str,
    _graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "List all nodes with id, label, kind, stage, confidence.",
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    return AgentPlanPreview(
        question=question,
        intent="nodes",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_edges(
    question: str,
    _graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "List all edges with id, from/to nodes, type, confidence.",
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    return AgentPlanPreview(
        question=question,
        intent="edges",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_claim_detail(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    claim_id: str,
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps: list[AgentPlanStep] = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "Locate claim {} and its evidence references.".format(claim_id),
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    if index:
        steps.append(
            _base_step(
                "S2",
                "Read concept_trace_index",
                "Cross-reference claim via claim_index.",
                ["concept_trace_index.json"],
            )
        )
    # Add dedup diagnostics step if any exist.
    all_diags = deduplicate_diagnostics(graph, grounding)
    matching = [d for d in all_diags if d.get("target_claim_id") == claim_id]
    if matching:
        steps.append(
            AgentPlanStep(
                step_id="S3",
                title="Read grounding diagnostics",
                rationale=(
                    "Count deduplicated diagnostics targeting {}.".format(
                        claim_id
                    )
                ),
                read_artifacts=["grounding_report.json"],
                referenced_diagnostic_ids=[
                    d.get("diagnostic_id", "") for d in matching
                ],
            )
        )
    return AgentPlanPreview(
        question=question,
        intent="claim_detail",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )


def _plan_evidence_detail(
    question: str,
    _graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    evidence_id: str,
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    response: Any | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPlanPreview:
    steps: list[AgentPlanStep] = [
        _base_step(
            "S1",
            "Read concept_trace_graph",
            "Locate evidence {} and its claim references.".format(evidence_id),
            ["concept_trace_graph.json"],
            response,
        ),
    ]
    if index:
        steps.append(
            _base_step(
                "S2",
                "Read concept_trace_index",
                "Cross-reference evidence via evidence_index.",
                ["concept_trace_index.json"],
            )
        )
    return AgentPlanPreview(
        question=question,
        intent="evidence_detail",
        steps=steps,
        safety_notes=_default_safety_notes(),
        is_loaded=True,
    )
