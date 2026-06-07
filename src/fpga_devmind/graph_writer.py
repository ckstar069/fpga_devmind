"""GraphWriter dry-run helpers for P1a+."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def apply_graph_write_proposal_dry_run(
    source_graph: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    }
    return proposed_graph, report
