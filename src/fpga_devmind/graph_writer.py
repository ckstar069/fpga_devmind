"""GraphWriter dry-run helpers for P1a+."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def apply_graph_write_proposal_dry_run(
    source_graph: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply accepted model claim candidates to a proposed graph copy.

    This never mutates the source graph object or the on-disk project_graph.json.
    """

    proposed_graph = copy.deepcopy(source_graph)
    existing_claim_ids = {
        claim.get("claim_id")
        for claim in proposed_graph.get("candidate_claims", [])
        if isinstance(claim, dict)
    }

    accepted_claims = [
        claim
        for claim in proposal.get("model_claims_to_create", [])
        if isinstance(claim, dict) and claim.get("validation_status") == "accepted_for_grounding"
    ]
    claims_added = []
    skipped_claims = []
    for claim in accepted_claims:
        claim_id = claim.get("claim_id")
        if not claim_id:
            skipped_claims.append({"claim_id": None, "reason": "missing_claim_id"})
            continue
        if claim_id in existing_claim_ids:
            skipped_claims.append({"claim_id": claim_id, "reason": "duplicate_claim_id"})
            continue
        proposed_claim = copy.deepcopy(claim)
        proposed_claim["claim_layer"] = proposed_claim.get("claim_layer", "p1a_plus_model_proposal")
        proposed_claim["source_plan_step_id"] = proposed_claim.get("generated_from_step")
        proposed_graph.setdefault("candidate_claims", []).append(proposed_claim)
        existing_claim_ids.add(claim_id)
        claims_added.append(claim_id)

    run_metadata = proposed_graph.setdefault("run_metadata", {})
    run_metadata["p1a_plus_graph_writer"] = {
        "mode": "dry_run_proposed_graph",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project_graph": proposal.get("source_project_graph"),
        "claims_added": claims_added,
        "skipped_claims": skipped_claims,
        "rejected_model_claim_ids": proposal.get("rejected_model_claim_ids", []),
    }

    report = {
        "schema_version": "p1a-plus-graph-write-report-0.1",
        "mode": "dry_run_proposed_graph",
        "source_project_graph": proposal.get("source_project_graph"),
        "claims_considered": len(accepted_claims),
        "claims_added": claims_added,
        "claims_skipped": skipped_claims,
        "rejected_model_claim_ids": proposal.get("rejected_model_claim_ids", []),
        "project_graph_mutated": False,
        "proposed_graph_artifact": "project_graph_proposed.json",
        "proposed_trace_index_artifact": "trace_index_proposed.json",
        "proposed_trace_index_complete": True,
    }
    proposed_trace_index = build_trace_index_for_graph(proposed_graph)
    proposed_trace_index["run_metadata"] = {
        "mode": "dry_run_proposed_trace_index",
        "created_at": run_metadata["p1a_plus_graph_writer"]["created_at"],
        "source_project_graph": proposal.get("source_project_graph"),
        "source_trace_index": "p1a_artifacts/trace_index.json",
        "project_graph_proposed": "project_graph_proposed.json",
        "claims_added": claims_added,
        "claims_skipped": skipped_claims,
        "project_graph_mutated": False,
    }
    return proposed_graph, proposed_trace_index, report


def build_trace_index_for_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Build a TraceIndex-like reverse index from a graph dict.

    This mirrors the P1a trace-index shape but works on proposed graph dicts
    after model-claim dry-run additions.
    """

    evidence_by_id = {
        item.get("evidence_id"): item
        for item in graph.get("evidence_items", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    claims = [claim for claim in graph.get("candidate_claims", []) if isinstance(claim, dict)]
    outputs_by_claim: dict[str, list[dict[str, Any]]] = {}
    outputs_by_evidence: dict[str, list[dict[str, Any]]] = {}

    def attach(
        output_id: str | None,
        output_type: str,
        source_claim_ids: list[str],
        evidence_ids: list[str],
    ) -> None:
        if not output_id:
            return
        output_ref = {"output_id": output_id, "output_type": output_type}
        for claim_id in source_claim_ids:
            if output_ref not in outputs_by_claim.setdefault(claim_id, []):
                outputs_by_claim[claim_id].append(output_ref)
        for evidence_id in evidence_ids:
            if output_ref not in outputs_by_evidence.setdefault(evidence_id, []):
                outputs_by_evidence[evidence_id].append(output_ref)

    stage = graph.get("stage", {})
    stage_id = stage.get("stage_id")
    stage_claim_ids = [
        claim["claim_id"]
        for claim in claims
        if claim.get("claim_id")
        and claim.get("claim_type") == "implementation_claim"
        and (
            not claim.get("subject_ids")
            or stage_id in _list_or_empty(claim.get("subject_ids"))
            or f"stage:{stage_id}" in _list_or_empty(claim.get("subject_ids"))
        )
    ]
    attach(stage_id, "stage", stage_claim_ids, _list_or_empty(stage.get("evidence_ids")))

    for concept in graph.get("concepts", []):
        if not isinstance(concept, dict):
            continue
        concept_id = concept.get("concept_id")
        source_claim_ids = [
            claim["claim_id"]
            for claim in claims
            if claim.get("claim_id") and concept_id in _list_or_empty(claim.get("subject_ids"))
        ]
        attach(concept_id, "concept", source_claim_ids, _list_or_empty(concept.get("evidence_ids")))

    for view in graph.get("implementation_views", []):
        if isinstance(view, dict):
            attach(
                view.get("view_id"),
                "implementation_view",
                _list_or_empty(view.get("source_claim_ids")),
                _list_or_empty(view.get("evidence_ids")),
            )
    for spec in graph.get("fixed_point_specs", []):
        if isinstance(spec, dict):
            attach(
                spec.get("spec_id"),
                "fixed_point_spec",
                _list_or_empty(spec.get("source_claim_ids")),
                _list_or_empty(spec.get("evidence_ids")),
            )
    for spec in graph.get("stream_interface_specs", []):
        if isinstance(spec, dict):
            attach(
                spec.get("interface_id"),
                "stream_interface_spec",
                _list_or_empty(spec.get("source_claim_ids")),
                _list_or_empty(spec.get("evidence_ids")),
            )
    for spec in graph.get("pipeline_timing_specs", []):
        if isinstance(spec, dict):
            attach(
                spec.get("timing_id"),
                "pipeline_timing_spec",
                _list_or_empty(spec.get("source_claim_ids")),
                _list_or_empty(spec.get("evidence_ids")),
            )
    for spec in graph.get("resource_estimate_specs", []):
        if isinstance(spec, dict):
            attach(
                spec.get("spec_id"),
                "resource_estimate_spec",
                _list_or_empty(spec.get("source_claim_ids")),
                _list_or_empty(spec.get("evidence_ids")),
            )
    for viz in graph.get("visualization_specs", []):
        if not isinstance(viz, dict):
            continue
        for node in viz.get("nodes", []):
            if isinstance(node, dict):
                attach(
                    node.get("node_id"),
                    "visualization_node",
                    _list_or_empty(node.get("source_claim_ids")),
                    _list_or_empty(node.get("evidence_ids")),
                )
        for edge in viz.get("edges", []):
            if isinstance(edge, dict):
                attach(
                    edge.get("edge_id"),
                    "visualization_edge",
                    _list_or_empty(edge.get("source_claim_ids")),
                    _list_or_empty(edge.get("evidence_ids")),
                )

    trace_claims = {}
    for claim in claims:
        claim_id = claim.get("claim_id")
        if not claim_id:
            continue
        evidence_ids = _list_or_empty(claim.get("evidence_ids"))
        trace_claims[claim_id] = {
            "claim_type": claim.get("claim_type"),
            "claim_layer": claim.get("claim_layer"),
            "confidence": claim.get("confidence"),
            "statement": claim.get("statement"),
            "subject_ids": _list_or_empty(claim.get("subject_ids")),
            "evidence_ids": evidence_ids,
            "evidence_refs": [
                evidence_by_id[eid] for eid in evidence_ids if eid in evidence_by_id
            ],
            "linked_outputs": outputs_by_claim.get(claim_id, []),
        }

    trace_evidence = {}
    for evidence_id, item in evidence_by_id.items():
        trace_evidence[evidence_id] = {
            **item,
            "supporting_claim_ids": [
                claim["claim_id"]
                for claim in claims
                if claim.get("claim_id") and evidence_id in _list_or_empty(claim.get("evidence_ids"))
            ],
            "linked_outputs": outputs_by_evidence.get(evidence_id, []),
        }

    return {
        "schema_version": "trace-0.1",
        "project_id": graph.get("project_profile", {}).get("project_id"),
        "stage_id": stage_id,
        "claims": trace_claims,
        "evidence": trace_evidence,
        "diagnostics": graph.get("grounding_diagnostics", []),
    }


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
