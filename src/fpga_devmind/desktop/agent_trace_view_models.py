"""Agent Runtime Trace view models for the Desktop Agent Shell (T017).

Reads agent_runtime_trace.json from a loaded artifact bundle and produces
structured row data for GUI table rendering.

Does not execute Agent logic, call LLMs, or write artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .artifact_loader import ArtifactBundle, get_agent_runtime_trace


# ---------------------------------------------------------------------------
# Row types
# ---------------------------------------------------------------------------


@dataclass
class AgentTraceSummaryRow:
    """A single key-value summary field."""

    field: str
    value: str


@dataclass
class AgentTraceStepRow:
    """One row in the trace timeline table."""

    section: str
    item_id: str
    title: str
    status: str
    summary: str
    references: str


@dataclass
class AgentTraceDiagnosticRow:
    """A runtime diagnostic entry."""

    severity: str
    message: str


# ---------------------------------------------------------------------------
# Aggregate view model
# ---------------------------------------------------------------------------


@dataclass
class AgentRuntimeTraceViewModel:
    """View model for the Agent Runtime Trace tab."""

    summary_rows: list[AgentTraceSummaryRow] = field(default_factory=list)
    step_rows: list[AgentTraceStepRow] = field(default_factory=list)
    diagnostic_rows: list[AgentTraceDiagnosticRow] = field(
        default_factory=list
    )
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _join_ids(ids: list[str] | Any, max_items: int = 5) -> str:
    """Join a list of IDs into a comma-separated string, truncating if long."""
    if not isinstance(ids, list):
        return ""
    items = ids[:max_items]
    suffix = ", ..." if len(ids) > max_items else ""
    return ", ".join(str(i) for i in items) + suffix


def _safe_str(val: Any, default: str = "") -> str:  # pyright: ignore[reportExplicitAny]
    """Safely convert a value to string."""
    if val is None:
        return default
    return str(val)


def _safe_list(val: Any) -> list[Any]:  # pyright: ignore[reportExplicitAny]
    """Safely convert to list."""
    if isinstance(val, list):
        return val
    return []


def _safe_dict(val: Any) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Safely convert to dict."""
    if isinstance(val, dict):
        return val
    return {}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_agent_runtime_trace_view_model(
    bundle: ArtifactBundle,
) -> AgentRuntimeTraceViewModel:
    """Build a view model from a loaded agent_runtime bundle.

    Never raises; returns is_loaded=False with a load_error on failure.
    """
    vm = AgentRuntimeTraceViewModel()

    # 1. Check bundle type
    if bundle.bundle_type != "agent_runtime":
        vm.load_error = (
            "Not an agent runtime bundle "
            "(type={}).".format(bundle.bundle_type)
        )
        return vm

    # 2. Get the trace JSON
    trace_data = get_agent_runtime_trace(bundle)
    if trace_data is None:
        vm.load_error = "agent_runtime_trace.json not found or not a dict."
        return vm

    # 3. Build summary rows
    task = _safe_dict(trace_data.get("task"))
    summary_rows: list[AgentTraceSummaryRow] = []

    summary_rows.append(
        AgentTraceSummaryRow(
            field="Schema Version",
            value=_safe_str(trace_data.get("schema_version")),
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Task ID", value=_safe_str(task.get("task_id"))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Question", value=_safe_str(task.get("question"))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Bundle Type", value=_safe_str(task.get("bundle_type"))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Concept", value=_safe_str(task.get("concept"), "N/A")
        )
    )

    constraints = _safe_list(task.get("constraints"))
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Constraints",
            value=", ".join(str(c) for c in constraints) if constraints else "none",
        )
    )

    # Counts
    observations = _safe_list(trace_data.get("observations"))
    reasoning = _safe_list(trace_data.get("reasoning"))
    plans = _safe_list(trace_data.get("plans"))
    tool_results = _safe_list(trace_data.get("tool_results"))
    answers = _safe_list(trace_data.get("answers"))
    graph_writes = _safe_list(trace_data.get("graph_write_proposals"))
    runtime_diags = _safe_list(trace_data.get("runtime_diagnostics"))

    summary_rows.append(
        AgentTraceSummaryRow(
            field="Observations", value=str(len(observations))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Reasoning", value=str(len(reasoning))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Plans", value=str(len(plans))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Tool Results", value=str(len(tool_results))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Answers", value=str(len(answers))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Graph Write Proposals", value=str(len(graph_writes))
        )
    )
    summary_rows.append(
        AgentTraceSummaryRow(
            field="Runtime Diagnostics", value=str(len(runtime_diags))
        )
    )

    # Answer limitations
    for ans in answers:
        ans_dict = _safe_dict(ans)
        limitations = _safe_list(ans_dict.get("limitations"))
        if limitations:
            summary_rows.append(
                AgentTraceSummaryRow(
                    field="Answer Limitations",
                    value=", ".join(str(l) for l in limitations),
                )
            )
            break  # show once

    vm.summary_rows = summary_rows

    # 4. Build step rows
    step_rows: list[AgentTraceStepRow] = []

    # Task
    step_rows.append(
        AgentTraceStepRow(
            section="task",
            item_id=_safe_str(task.get("task_id")),
            title="User Task",
            status=_safe_str(task.get("bundle_type")),
            summary=_safe_str(task.get("question")),
            references="",
        )
    )

    # Observations
    for obs in observations:
        obs_dict = _safe_dict(obs)
        refs = _safe_list(obs_dict.get("artifact_refs"))
        step_rows.append(
            AgentTraceStepRow(
                section="observation",
                item_id=_safe_str(obs_dict.get("observation_id")),
                title="Observation",
                status="loaded",
                summary=_safe_str(obs_dict.get("summary")),
                references=_join_ids(refs),
            )
        )

    # Reasoning
    for rsn in reasoning:
        rsn_dict = _safe_dict(rsn)
        step_rows.append(
            AgentTraceStepRow(
                section="reasoning",
                item_id=_safe_str(rsn_dict.get("reasoning_id")),
                title="Reasoning",
                status=_safe_str(rsn_dict.get("confidence")),
                summary=_safe_str(rsn_dict.get("summary")),
                references=_join_ids(
                    _safe_list(rsn_dict.get("referenced_observation_ids"))
                ),
            )
        )

    # Plans + Proposals (nested)
    for plan in plans:
        plan_dict = _safe_dict(plan)
        plan_steps = _safe_list(plan_dict.get("steps"))
        step_rows.append(
            AgentTraceStepRow(
                section="plan",
                item_id=_safe_str(plan_dict.get("plan_id")),
                title="Tool Plan",
                status=_safe_str(plan_dict.get("intent")),
                summary="{} steps".format(len(plan_steps)),
                references="",
            )
        )
        for prop in plan_steps:
            prop_dict = _safe_dict(prop)
            step_rows.append(
                AgentTraceStepRow(
                    section="proposal",
                    item_id=_safe_str(prop_dict.get("proposal_id")),
                    title="Tool Call Proposal",
                    status=_safe_str(prop_dict.get("allowed_action")),
                    summary=_safe_str(prop_dict.get("rationale")),
                    references=_join_ids(
                        _safe_list(prop_dict.get("expected_read_artifacts"))
                    ),
                )
            )

    # Tool Results
    for tr in tool_results:
        tr_dict = _safe_dict(tr)
        step_rows.append(
            AgentTraceStepRow(
                section="result",
                item_id=_safe_str(tr_dict.get("result_id")),
                title="Tool Result",
                status=_safe_str(tr_dict.get("status")),
                summary=_safe_str(tr_dict.get("result_summary")),
                references="",
            )
        )

    # Answers
    for ans in answers:
        ans_dict = _safe_dict(ans)
        limitations = _safe_list(ans_dict.get("limitations"))
        step_rows.append(
            AgentTraceStepRow(
                section="answer",
                item_id=_safe_str(ans_dict.get("answer_id")),
                title="Answer",
                status=_safe_str(ans_dict.get("confidence")),
                summary=_safe_str(ans_dict.get("answer_text"), "")[:120],
                references=", ".join(
                    str(l) for l in limitations
                ) if limitations else "",
            )
        )

    # Graph Write Proposals
    for gw in graph_writes:
        gw_dict = _safe_dict(gw)
        is_allowed = gw_dict.get("is_write_allowed", False)
        blocking = _safe_list(gw_dict.get("blocking_reasons"))
        gw_status = "allowed" if is_allowed else "blocked"
        step_rows.append(
            AgentTraceStepRow(
                section="graph_write",
                item_id=_safe_str(gw_dict.get("graph_write_id")),
                title="Graph Write Proposal",
                status=gw_status,
                summary=", ".join(str(b) for b in blocking) if blocking else "no blocking reasons",
                references=_join_ids(
                    _safe_list(gw_dict.get("referenced_answer_ids"))
                ),
            )
        )

    vm.step_rows = step_rows

    # 5. Build diagnostic rows
    diag_rows: list[AgentTraceDiagnosticRow] = []
    for d in runtime_diags:
        d_dict = _safe_dict(d)
        diag_rows.append(
            AgentTraceDiagnosticRow(
                severity=_safe_str(d_dict.get("severity"), "unknown"),
                message=_safe_str(d_dict.get("message"), ""),
            )
        )
    vm.diagnostic_rows = diag_rows

    vm.is_loaded = True
    return vm
