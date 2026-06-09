"""Local No-op ReAct Dry Run (T016).

Deterministic single-turn Agent runtime that chains T011 (query)
+ T012 (plan preview) + T015 (runtime contract) into one
observe -> plan -> propose -> simulated-result -> answer ->
blocked-graph-write trace.

No LLM, no external API, no tool execution, no target project mutation.
"""

# pyright: reportUnusedCallResult=false

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_runtime_contract import (
    GRAPH_WRITE_DISABLED_REASON,
    AgentRuntimeTrace,
    Answer,
    GraphWriteProposal,
    Observation,
    ReasoningSummary,
    ToolCallProposal,
    ToolPlan,
    ToolResult,
    UserTask,
    validate_runtime_trace,
)
from .desktop.agent_panel_models import query_artifact_bundle
from .desktop.agent_plan_models import build_agent_plan_preview
from .desktop.artifact_loader import (
    ArtifactBundle,
    get_run_metadata,
    load_bundle,
)
from .safety import ensure_safe_output_dir


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass
class NoopAgentRunResult:
    """Result of a single no-op Agent dry run."""

    trace: AgentRuntimeTrace
    output_dir: str
    artifact_path: str
    diagnostics: list[dict[str, str]]
    status: str  # "ok" | "blocked" | "load_error"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_UNKNOWN_CONFIDENCE_KINDS: frozenset[str] = frozenset({"unsupported", "unknown"})


def _deterministic_task_id(artifact_dir: Path, question: str) -> str:
    """Generate a deterministic task_id from inputs."""
    payload = "{}:{}".format(str(artifact_dir), question)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return "noop-{}".format(digest)


def _map_confidence(response_kind: str) -> str:
    """Map T011 response_kind to T015 Answer.confidence."""
    if response_kind in _UNKNOWN_CONFIDENCE_KINDS:
        return "unknown"
    return "inferred"


def _extract_concept(bundle: ArtifactBundle) -> str | None:
    """Extract concept from bundle run_metadata, if available."""
    meta = get_run_metadata(bundle)
    if meta and "concept" in meta:
        return str(meta["concept"])
    return None


def _render_answer_md(
    question: str,
    answer_text: str,
    intent: str,
    step_count: int,
    step_titles: list[str],
) -> str:
    """Render a human-readable answer markdown file."""
    lines = [
        "# No-op Agent Dry Run Answer",
        "",
        "Question: {}".format(question),
        "",
        "Mode: deterministic (no LLM, no external API).",
        "",
        "## Answer",
        "",
        answer_text,
        "",
        "## Plan Preview",
        "",
        "Intent: {}".format(intent),
        "Steps: {}".format(step_count),
        "",
    ]
    for title in step_titles:
        lines.append("- {}".format(title))
    lines.append("")
    lines.append("Graph write: **blocked**")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_noop_agent_once(
    artifact_dir: Path,
    question: str,
    out_dir: Path,
) -> NoopAgentRunResult:
    """Run a single deterministic no-op Agent loop iteration.

    Parameters
    ----------
    artifact_dir : Path
        Directory containing a P1a or P1b artifact bundle.
    question : str
        User question to answer.
    out_dir : Path
        Output directory for the runtime trace. Must be in a temp area.

    Returns
    -------
    NoopAgentRunResult
        Complete result with trace, output paths, diagnostics, and status.
    """
    # 1. Safety guard
    out_dir = ensure_safe_output_dir(out_dir, "noop agent output")

    # 2. Load bundle
    bundle = load_bundle(artifact_dir)

    # 3. Handle incomplete bundle
    if not bundle.is_complete:
        errors = [
            d.message for d in bundle.diagnostics if d.severity == "error"
        ]
        error_msg = "; ".join(errors) if errors else "Incomplete bundle"
        task_id = _deterministic_task_id(artifact_dir, question)

        error_task = UserTask(
            task_id=task_id,
            question=question,
            created_at=datetime.now(timezone.utc).isoformat(),
            artifact_bundle_path=str(artifact_dir),
            bundle_type=bundle.bundle_type,
        )
        error_trace = AgentRuntimeTrace(
            task=error_task,
            runtime_diagnostics=[{
                "severity": "error",
                "message": "Bundle load failed: {}".format(error_msg),
            }],
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        trace_path = out_dir / "agent_runtime_trace.json"
        trace_path.write_text(error_trace.to_json(), encoding="utf-8")
        return NoopAgentRunResult(
            trace=error_trace,
            output_dir=str(out_dir),
            artifact_path=str(trace_path),
            diagnostics=[{"severity": "error", "message": error_msg}],
            status="load_error",
        )

    # 4. Create UserTask
    task_id = _deterministic_task_id(artifact_dir, question)
    task = UserTask(
        task_id=task_id,
        question=question,
        created_at=datetime.now(timezone.utc).isoformat(),
        artifact_bundle_path=str(artifact_dir),
        bundle_type=bundle.bundle_type,
        concept=_extract_concept(bundle),
    )

    # 5. Create Observation
    artifact_refs = sorted(bundle.artifacts.keys())
    observation = Observation(
        observation_id="{}_OBS_001".format(task_id),
        task_id=task_id,
        artifact_refs=artifact_refs,
        summary="Loaded {} bundle with {} artifacts".format(
            bundle.bundle_type, len(artifact_refs)
        ),
    )

    # 6. Call query (T011)
    response = query_artifact_bundle(bundle, question)

    # 7. Call plan preview (T012)
    preview = build_agent_plan_preview(bundle, question, response)

    # 8. Create ReasoningSummary
    reasoning = ReasoningSummary(
        reasoning_id="{}_RSN_001".format(task_id),
        task_id=task_id,
        mode="deterministic",
        summary="Query response_kind='{}'; plan intent='{}'; {} plan steps.".format(
            response.response_kind, preview.intent, len(preview.steps)
        ),
        assumptions=[
            "Deterministic keyword routing; no LLM semantic reasoning.",
            "Plan steps are read-only previews; no tool execution.",
        ],
        unknowns=response.uncertainty_notes,
        confidence=_map_confidence(response.response_kind),
        referenced_observation_ids=[observation.observation_id],
    )

    # 9. Map AgentPlanPreview.steps -> ToolPlan + ToolCallProposals
    proposals: list[ToolCallProposal] = []
    for idx, step in enumerate(preview.steps):
        proposal = ToolCallProposal(
            proposal_id="{}_PROP_{:03d}".format(task_id, idx + 1),
            task_id=task_id,
            tool_name="read_artifact",
            params={
                "step_title": step.title,
                "read_artifacts": step.read_artifacts,
            },
            rationale=step.rationale,
            expected_read_artifacts=step.read_artifacts,
            allowed_action=step.allowed_action,
            referenced_claim_ids=step.referenced_claim_ids,
            referenced_evidence_ids=step.referenced_evidence_ids,
            referenced_node_ids=step.referenced_node_ids,
            referenced_diagnostic_ids=step.referenced_diagnostic_ids,
        )
        proposals.append(proposal)

    plan = ToolPlan(
        plan_id="{}_PLAN_001".format(task_id),
        task_id=task_id,
        intent=preview.intent,
        steps=proposals,
    )

    # 10. Create ToolResult (status="simulated")
    tool_results: list[ToolResult] = []
    for idx, proposal in enumerate(proposals):
        tr = ToolResult(
            result_id="{}_RES_{:03d}".format(task_id, idx + 1),
            proposal_id=proposal.proposal_id,
            task_id=task_id,
            status="simulated",
            result_summary="Simulated: {}".format(proposal.rationale),
            referenced_claim_ids=proposal.referenced_claim_ids,
            referenced_evidence_ids=proposal.referenced_evidence_ids,
            referenced_node_ids=proposal.referenced_node_ids,
            referenced_diagnostic_ids=proposal.referenced_diagnostic_ids,
        )
        tool_results.append(tr)

    # 11. Create Answer
    result_ids = [tr.result_id for tr in tool_results]
    answer = Answer(
        answer_id="{}_ANS_001".format(task_id),
        task_id=task_id,
        answer_text=response.answer_text or "(no answer text)",
        confidence=_map_confidence(response.response_kind),
        referenced_result_ids=result_ids,
        referenced_claim_ids=response.referenced_claim_ids,
        referenced_evidence_ids=response.referenced_evidence_ids,
        referenced_node_ids=response.referenced_node_ids,
        referenced_diagnostic_ids=response.referenced_diagnostic_ids,
        uncertainty_notes=response.uncertainty_notes,
    )

    # 12. Create GraphWriteProposal (blocked)
    graph_write = GraphWriteProposal(
        graph_write_id="{}_GWP_001".format(task_id),
        task_id=task_id,
        referenced_answer_ids=[answer.answer_id],
        blocking_reasons=[GRAPH_WRITE_DISABLED_REASON],
    )

    # 13. Assemble AgentRuntimeTrace
    trace = AgentRuntimeTrace(
        task=task,
        observations=[observation],
        reasoning=[reasoning],
        plans=[plan],
        tool_results=tool_results,
        answers=[answer],
        graph_write_proposals=[graph_write],
    )

    # 14. Validate
    diagnostics = validate_runtime_trace(trace)

    # 15. Write agent_runtime_trace.json
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "agent_runtime_trace.json"
    trace_path.write_text(trace.to_json(), encoding="utf-8")

    # 16. Write answer.md
    step_titles = [s.title for s in preview.steps]
    answer_md = _render_answer_md(
        question=question,
        answer_text=response.answer_text or "(no answer text)",
        intent=preview.intent,
        step_count=len(preview.steps),
        step_titles=step_titles,
    )
    (out_dir / "answer.md").write_text(answer_md, encoding="utf-8")

    # 17. Determine status
    status = "ok"
    if response.response_kind == "unsupported":
        status = "blocked"

    return NoopAgentRunResult(
        trace=trace,
        output_dir=str(out_dir),
        artifact_path=str(trace_path),
        diagnostics=diagnostics,
        status=status,
    )
