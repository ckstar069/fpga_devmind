"""P1a+ semantic agent dry-run runtime.

This module is intentionally provider-free. It exercises the Agent runtime
artifact shape around the deterministic P1a evidence shell before any LLM is
connected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm_contract import build_prompt_context, validate_semantic_reasoning_result
from .p1a import run_p1a
from .graph_writer import apply_graph_write_proposal_dry_run
from .providers import provider_for_mode, response_to_dict
from .query import answer_question, check_freshness
from .safety import ensure_safe_output_dir


DEFAULT_AGENT_OUT = Path("/tmp/fpga_devmind/p1a_agent_l6")


def run_p1a_semantic_agent_dry_run(
    project_root: Path,
    stage_id: str,
    question: str,
    out_dir: Path = DEFAULT_AGENT_OUT,
    artifact_dir: Path | None = None,
    model_result_path: Path | None = None,
    use_mock_semantic: bool = False,
) -> dict[str, Any]:
    """Run a provider-free P1a+ Agent shell over P1a artifacts.

    The result is not an LLM semantic interpretation. It is a deterministic
    runtime scaffold that records the future Agent loop artifacts and reuses the
    existing grounded P1a graph/query behavior.
    """

    if stage_id != "L6_resource_opt":
        raise ValueError("P1a+ dry-run currently only supports L6_resource_opt")

    out_dir = ensure_safe_output_dir(out_dir, "P1a+ agent output")
    p1a_artifacts = ensure_safe_output_dir(artifact_dir or (out_dir / "p1a_artifacts"), "P1a+ artifact output")
    out_dir.mkdir(parents=True, exist_ok=True)
    provider = provider_for_mode(model_result_path, use_mock_semantic=use_mock_semantic)
    runtime_mode = provider.mode

    plan = _build_task_plan(project_root, stage_id, question, out_dir, p1a_artifacts)
    trace_events: list[dict[str, Any]] = []

    trace_events.append(
        _trace_event(
            iteration=1,
            plan_step_id="S001",
            reason="Ensure current grounded P1a artifacts exist for the requested stage.",
            action={
                "tool_name": "p1a-understand-stage",
                "input": {
                    "project_root": str(project_root),
                    "stage_id": stage_id,
                    "out_dir": str(p1a_artifacts),
                },
                "read_only_target": True,
            },
        )
    )
    graph_obj = run_p1a(project_root, p1a_artifacts)
    freshness = check_freshness(p1a_artifacts)
    graph = graph_obj.to_dict()
    trace_events[-1]["observe"] = {
        "observation_id": "O001",
        "observation_type": "p1a_artifacts",
        "artifact_dir": str(p1a_artifacts),
        "claims": len(graph["candidate_claims"]),
        "evidence_items": len(graph["evidence_items"]),
        "uncertainty_notes": len(graph["uncertainty_notes"]),
        "freshness_status": freshness["status"],
    }
    trace_events[-1]["claim_delta"] = {
        "selected_claim_ids": [claim["claim_id"] for claim in graph["candidate_claims"]],
        "new_claims": [],
        "note": "Dry-run reuses deterministic P1a claims; no LLM claims are generated.",
    }
    trace_events[-1]["reflect"] = _reflection_from_diagnostics(graph["grounding_diagnostics"], freshness)

    trace_events.append(
        _trace_event(
            iteration=2,
            plan_step_id="S002",
            reason="Answer the user question from the grounded ProjectGraph and TraceIndex.",
            action={
                "tool_name": "p1a-query",
                "input": {
                    "artifact_dir": str(p1a_artifacts),
                    "question": question,
                },
                "read_only_target": True,
            },
        )
    )
    grounded_answer = answer_question(p1a_artifacts, question)
    trace_events[-1]["observe"] = {
        "observation_id": "O002",
        "observation_type": "grounded_query_answer",
        "answer_chars": len(grounded_answer),
        "freshness_status": freshness["status"],
    }
    trace_events[-1]["claim_delta"] = {
        "selected_claim_ids": _claim_ids_for_question(graph, question),
        "new_claims": [],
        "note": "Answer is rendered from accepted P1a graph data.",
    }
    trace_events[-1]["reflect"] = _reflection_from_diagnostics(graph["grounding_diagnostics"], freshness)

    claim_proposals = {
        "schema_version": "p1a-plus-claim-proposals-0.1",
        "mode": runtime_mode,
        "source_project_graph": str(p1a_artifacts / "project_graph.json"),
        "candidate_claims": graph["candidate_claims"],
        "model_candidate_claims": [],
        "notes": [
            "No model-generated claims are present in this dry-run.",
            "Future LLM claims must include evidence_ids before grounding.",
        ],
    }
    prompt_context = build_prompt_context(
        project_root=str(project_root),
        stage_id=stage_id,
        question=question,
        graph=graph,
        trace_index=_read_json(p1a_artifacts / "trace_index.json"),
        freshness=freshness,
    )
    provider_response = provider.run(prompt_context)
    normalized_model_result, model_diagnostics = validate_semantic_reasoning_result(
        provider_response.result,
        known_evidence_ids=set(prompt_context["known_evidence_ids"]),
    )
    claim_proposals["model_candidate_claims"] = normalized_model_result.get("candidate_claims", [])
    claim_proposals["model_claim_summary"] = _model_claim_summary(normalized_model_result)
    if model_result_path:
        claim_proposals["notes"] = [
            f"Model result fixture read from {model_result_path}.",
            "Fixture claims are validated but not written to ProjectGraph in this slice.",
        ]
    graph_write_proposal = _build_graph_write_proposal(graph, p1a_artifacts, runtime_mode, normalized_model_result)
    proposed_graph, graph_write_report = apply_graph_write_proposal_dry_run(graph, graph_write_proposal)
    grounding_report = _build_grounding_report(graph, freshness, model_diagnostics, runtime_mode)
    agent_trace = {
        "schema_version": "p1a-plus-agent-trace-0.1",
        "mode": runtime_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_id": provider_response.provider_id,
        "model_result_source": provider_response.call_record.get("source"),
        "task_plan": plan,
        "events": trace_events,
        "safety": {
            "target_project_modified": False,
            "vivado_run": False,
            "synthesis_or_bitstream_run": False,
            "api_key_used": False,
            "api_key_logged": False,
        },
    }

    answer_md = _render_agent_answer(question, p1a_artifacts, grounded_answer, grounding_report, runtime_mode)

    _write_json(out_dir / "agent_trace.json", agent_trace)
    _write_json(out_dir / "prompt_context.json", prompt_context)
    _write_json(out_dir / "provider_call.json", response_to_dict(provider_response)["call_record"])
    _write_json(out_dir / "model_result_normalized.json", normalized_model_result)
    _write_json(out_dir / "claim_proposals.json", claim_proposals)
    _write_json(out_dir / "graph_write_proposal.json", graph_write_proposal)
    _write_json(out_dir / "project_graph_proposed.json", proposed_graph)
    _write_json(out_dir / "graph_write_report.json", graph_write_report)
    _write_json(out_dir / "grounding_report.json", grounding_report)
    (out_dir / "answer.md").write_text(answer_md, encoding="utf-8")

    return {
        "out_dir": str(out_dir),
        "artifact_dir": str(p1a_artifacts),
        "agent_trace": agent_trace,
        "prompt_context": prompt_context,
        "provider_call": provider_response.call_record,
        "model_result_normalized": normalized_model_result,
        "claim_proposals": claim_proposals,
        "graph_write_proposal": graph_write_proposal,
        "project_graph_proposed": proposed_graph,
        "graph_write_report": graph_write_report,
        "grounding_report": grounding_report,
        "answer_md": str(out_dir / "answer.md"),
    }


def _build_task_plan(
    project_root: Path,
    stage_id: str,
    question: str,
    out_dir: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    return {
        "plan_id": f"p1a-plus-{project_root.name}-{stage_id}",
        "workflow": "UnderstandStage",
        "objective": question,
        "assumptions": [
            "P1a+ dry-run does not call an LLM provider.",
            "Existing deterministic P1a artifacts are the evidence shell.",
            "Confirmed semantic expansion is deferred until model output is grounded.",
        ],
        "plan_steps": [
            {
                "step_id": "S001",
                "purpose": "Generate or refresh grounded P1a artifacts.",
                "expected_output": "ProjectGraph, TraceIndex, MemoryManifest",
                "tool_candidates": ["p1a-understand-stage"],
                "status": "completed",
            },
            {
                "step_id": "S002",
                "purpose": "Answer the user question from graph and trace artifacts.",
                "expected_output": "Grounded answer markdown",
                "tool_candidates": ["p1a-query"],
                "status": "completed",
            },
        ],
        "evidence_targets": [
            str(project_root / "src" / "python_model" / stage_id),
            str(project_root / "config"),
        ],
        "max_iterations": 8,
        "stop_conditions": ["required_evidence_collected", "blocking_conflict_found", "max_iterations_reached"],
        "fallback_strategy": "write_partial_answer_with_uncertainties",
        "output_dir": str(out_dir),
        "artifact_dir": str(artifact_dir),
    }


def _trace_event(iteration: int, plan_step_id: str, reason: str, action: dict[str, Any]) -> dict[str, Any]:
    return {
        "iteration": iteration,
        "plan_step_id": plan_step_id,
        "reason": reason,
        "act": action,
        "observe": None,
        "claim_delta": None,
        "reflect": None,
    }


def _reflection_from_diagnostics(diagnostics: list[dict[str, Any]], freshness: dict[str, Any]) -> dict[str, Any]:
    blocking = [d for d in diagnostics if d.get("severity") == "blocking"]
    if blocking:
        return {
            "action": "stop_insufficient_evidence",
            "blocking_diagnostics": [d["diagnostic_id"] for d in blocking],
            "rationale": "Blocking grounding diagnostics remain.",
        }
    if freshness["status"] != "current":
        return {
            "action": "downgrade_and_write",
            "blocking_diagnostics": [],
            "rationale": "Artifacts are not current; answer must carry freshness warning.",
        }
    return {
        "action": "write_graph",
        "blocking_diagnostics": [],
        "rationale": "No blocking diagnostics and source snapshot is current.",
    }


def _claim_ids_for_question(graph: dict[str, Any], question: str) -> list[str]:
    normalized = question.lower()
    selected: list[str] = []
    for claim in graph["candidate_claims"]:
        claim_type = claim["claim_type"]
        if claim_type == "implementation_claim" and _has_any(normalized, ["flow", "stage", "流程", "实现"]):
            selected.append(claim["claim_id"])
        elif claim_type == "resource_refinement_claim" and _has_any(normalized, ["resource", "lut", "dsp", "bram", "资源"]):
            selected.append(claim["claim_id"])
        elif claim_type == "fixed_point_claim" and _has_any(normalized, ["fixed", "q", "定点", "位宽"]):
            selected.append(claim["claim_id"])
        elif claim_type == "interface_claim" and _has_any(normalized, ["axis", "valid", "ready", "接口"]):
            selected.append(claim["claim_id"])
        elif claim_type == "implementation_order_claim" and _has_any(normalized, ["dataflow", "flow", "流程", "主线"]):
            selected.append(claim["claim_id"])
    if selected:
        return selected
    return [claim["claim_id"] for claim in graph["candidate_claims"][:5]]


def _build_graph_write_proposal(
    graph: dict[str, Any],
    artifact_dir: Path,
    runtime_mode: str,
    model_result: dict[str, Any],
) -> dict[str, Any]:
    model_claims = [claim for claim in model_result.get("candidate_claims", []) if isinstance(claim, dict)]
    accepted_model_claims = [
        claim for claim in model_claims if claim.get("validation_status") == "accepted_for_grounding"
    ]
    rejected_model_claim_ids = [
        claim.get("claim_id", "unknown")
        for claim in model_claims
        if claim.get("validation_status") == "rejected"
    ]
    return {
        "schema_version": "p1a-plus-graph-write-proposal-0.1",
        "mode": runtime_mode,
        "source_project_graph": str(artifact_dir / "project_graph.json"),
        "source_claim_ids": [claim["claim_id"] for claim in graph["candidate_claims"]],
        "model_claims_to_create": accepted_model_claims,
        "rejected_model_claim_ids": rejected_model_claim_ids,
        "nodes_to_create": [],
        "edges_to_create": [],
        "evidences_to_create": [],
        "uncertainties_to_create": [],
        "visualizations_to_create": [],
        "stale_nodes_to_mark": [],
        "confidence": "supported",
        "note": "Dry-run records accepted model claims as graph-write candidates but does not mutate ProjectGraph.",
    }


def _build_grounding_report(
    graph: dict[str, Any],
    freshness: dict[str, Any],
    model_diagnostics: list[dict[str, Any]],
    runtime_mode: str,
) -> dict[str, Any]:
    blocking = [d for d in graph["grounding_diagnostics"] if d.get("severity") == "blocking"]
    model_blocking = [d for d in model_diagnostics if d.get("severity") == "blocking"]
    unsupported_confirmed = [
        claim["claim_id"]
        for claim in graph["candidate_claims"]
        if claim.get("confidence") == "confirmed" and not claim.get("evidence_ids")
    ]
    return {
        "schema_version": "p1a-plus-grounding-report-0.1",
        "mode": runtime_mode,
        "freshness": freshness,
        "diagnostics": graph["grounding_diagnostics"],
        "model_output_diagnostics": model_diagnostics,
        "summary": {
            "candidate_claims": len(graph["candidate_claims"]),
            "blocking_diagnostics": len(blocking),
            "model_output_blocking_diagnostics": len(model_blocking),
            "unsupported_confirmed_claims": len(unsupported_confirmed),
            "uncertainty_notes": len(graph["uncertainty_notes"]),
        },
        "reflection_decision": _reflection_from_diagnostics(graph["grounding_diagnostics"], freshness),
    }


def _render_agent_answer(
    question: str,
    artifact_dir: Path,
    grounded_answer: str,
    grounding_report: dict[str, Any],
    runtime_mode: str,
) -> str:
    summary = grounding_report["summary"]
    lines = [
        "# P1a+ Semantic Agent Dry Run Answer",
        "",
        f"Question: {question}",
        "",
        f"Mode: `{runtime_mode}`.",
        "",
        "This run exercises the Agent runtime artifact shape over P1a evidence. It does not call an LLM provider.",
        "",
        "## Runtime Status",
        "",
        f"- P1a artifacts: `{artifact_dir}`",
        f"- Freshness: `{grounding_report['freshness']['status']}`",
        f"- Candidate claims: {summary['candidate_claims']}",
        f"- Blocking diagnostics: {summary['blocking_diagnostics']}",
        f"- Model output blocking diagnostics: {summary['model_output_blocking_diagnostics']}",
        f"- Uncertainty notes: {summary['uncertainty_notes']}",
        "",
        "## Grounded Answer",
        "",
        grounded_answer.rstrip(),
    ]
    return "\n".join(lines) + "\n"


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _model_claim_summary(model_result: dict[str, Any]) -> dict[str, int]:
    claims = [claim for claim in model_result.get("candidate_claims", []) if isinstance(claim, dict)]
    return {
        "total": len(claims),
        "accepted_for_grounding": sum(1 for claim in claims if claim.get("validation_status") == "accepted_for_grounding"),
        "rejected": sum(1 for claim in claims if claim.get("validation_status") == "rejected"),
    }
