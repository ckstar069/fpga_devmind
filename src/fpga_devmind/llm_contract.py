"""LLM contract helpers for the P1a+ semantic Agent layer.

This module does not call any model provider. It defines the prompt context and
response validation boundary that future providers must pass through before a
model result can affect graph proposals.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SEMANTIC_RESULT_SCHEMA_VERSION = "p1a-plus-semantic-result-0.1"

REQUIRED_RESULT_FIELDS = {
    "schema_version",
    "request_id",
    "plan_step_id",
    "reasoning_summary",
    "candidate_claims",
    "proposed_edges",
    "proposed_uncertainties",
    "requested_followup_tools",
    "self_check_notes",
}

REQUIRED_CLAIM_FIELDS = {
    "claim_type",
    "statement",
    "subject_ids",
    "evidence_ids",
    "confidence",
    "required_missing_evidence",
    "generated_from_step",
}

ALLOWED_CONFIDENCE = {"confirmed", "supported", "inferred", "unknown", "conflicted"}
ALLOWED_FOLLOWUP_TOOLS = {
    "p1a-understand-stage",
    "p1a-freshness",
    "p1a-query",
    "read_project_graph",
    "read_trace_index",
    "read_source_snippet",
}


def build_prompt_context(
    project_root: str,
    stage_id: str,
    question: str,
    graph: dict[str, Any],
    trace_index: dict[str, Any],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    """Build a redacted prompt context for a future semantic model call."""

    return {
        "schema_version": "p1a-plus-prompt-context-0.1",
        "role": "fpga_devmind_semantic_understanding_agent",
        "mode": "provider_contract_only",
        "task": {
            "request_id": graph.get("task_request", {}).get("request_id"),
            "workflow": "UnderstandStage",
            "project_root": project_root,
            "stage_id": stage_id,
            "question": question,
        },
        "safety_constraints": {
            "read_only_target_project": True,
            "forbidden_actions": [
                "modify_fpga_project_targets",
                "run_vivado",
                "run_synthesis",
                "run_implementation",
                "run_bitstream",
                "log_api_keys",
            ],
            "default_output_root": "/tmp/fpga_devmind",
        },
        "available_tools": [
            "p1a-understand-stage",
            "p1a-freshness",
            "p1a-query",
            "read_project_graph",
            "read_trace_index",
            "read_source_snippet",
        ],
        "known_evidence_ids": sorted(trace_index.get("evidence", {}).keys()),
        "known_claim_ids": sorted(trace_index.get("claims", {}).keys()),
        "current_graph_summary": {
            "project_id": graph.get("project_profile", {}).get("project_id"),
            "stage_id": graph.get("stage", {}).get("stage_id"),
            "concepts": [
                {
                    "concept_id": concept.get("concept_id"),
                    "canonical_name": concept.get("canonical_name"),
                    "confidence": concept.get("confidence"),
                    "evidence_ids": concept.get("evidence_ids", []),
                }
                for concept in graph.get("concepts", [])
            ],
            "uncertainty_notes": graph.get("uncertainty_notes", []),
        },
        "freshness": freshness,
        "required_output_schema": {
            "schema_version": SEMANTIC_RESULT_SCHEMA_VERSION,
            "required_result_fields": sorted(REQUIRED_RESULT_FIELDS),
            "required_candidate_claim_fields": sorted(REQUIRED_CLAIM_FIELDS),
            "confidence_values": sorted(ALLOWED_CONFIDENCE),
        },
        "redaction_policy": {
            "api_keys_included": False,
            "provider_secrets_included": False,
            "full_environment_included": False,
        },
    }


def validate_semantic_reasoning_result(
    result: dict[str, Any],
    known_evidence_ids: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate and normalize a model result before grounding.

    The validator is deliberately conservative. It downgrades claims that lack
    valid evidence and emits diagnostics instead of trusting model text.
    """

    normalized = deepcopy(result)
    diagnostics: list[dict[str, Any]] = []

    missing_fields = sorted(REQUIRED_RESULT_FIELDS - set(normalized))
    if missing_fields:
        diagnostics.append(
            _diagnostic(
                "MVD001",
                severity="blocking",
                issue_type="model_output_missing_fields",
                message=f"SemanticReasoningResult is missing fields: {', '.join(missing_fields)}.",
                recommended_action="retry_model_with_schema",
            )
        )

    schema_version = normalized.get("schema_version")
    if schema_version != SEMANTIC_RESULT_SCHEMA_VERSION:
        diagnostics.append(
            _diagnostic(
                "MVD003",
                severity="blocking",
                issue_type="model_output_schema_version_mismatch",
                message=(
                    f"SemanticReasoningResult schema_version must be "
                    f"`{SEMANTIC_RESULT_SCHEMA_VERSION}`, got `{schema_version}`."
                ),
                recommended_action="retry_model_with_current_schema",
            )
        )

    claims = normalized.get("candidate_claims")
    if not isinstance(claims, list):
        normalized["candidate_claims"] = []
        diagnostics.append(
            _diagnostic(
                "MVD002",
                severity="blocking",
                issue_type="model_claims_not_list",
                message="candidate_claims must be a list.",
                recommended_action="retry_model_with_schema",
            )
        )
        return normalized, diagnostics

    for idx, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            diagnostics.append(
                _diagnostic(
                    f"MVD{idx + 10:03d}",
                    severity="blocking",
                    issue_type="model_claim_not_object",
                    message=f"candidate_claims[{idx - 1}] is not an object.",
                    recommended_action="drop_claim",
                )
            )
            continue
        _normalize_claim(idx, claim, known_evidence_ids, diagnostics)

    _validate_requested_followup_tools(normalized, diagnostics)
    _validate_evidence_list_objects(
        normalized,
        field_name="proposed_edges",
        known_evidence_ids=known_evidence_ids,
        diagnostics=diagnostics,
    )
    _validate_evidence_list_objects(
        normalized,
        field_name="proposed_uncertainties",
        known_evidence_ids=known_evidence_ids,
        diagnostics=diagnostics,
    )
    _attach_claim_validation_status(normalized, diagnostics)
    return normalized, diagnostics


def _normalize_claim(
    idx: int,
    claim: dict[str, Any],
    known_evidence_ids: set[str],
    diagnostics: list[dict[str, Any]],
) -> None:
    claim.setdefault("claim_id", f"M{idx:03d}")
    claim.setdefault("validation_status", "accepted_for_grounding")
    claim.setdefault("diagnostic_ids", [])
    missing = sorted(REQUIRED_CLAIM_FIELDS - set(claim))
    if missing:
        diagnostics.append(
            _diagnostic(
                f"MVC{idx:03d}",
                target_claim_id=claim["claim_id"],
                severity="blocking",
                issue_type="model_claim_missing_fields",
                message=f"Model claim is missing fields: {', '.join(missing)}.",
                recommended_action="drop_or_retry_claim",
            )
        )

    confidence = claim.get("confidence", "unknown")
    if confidence not in ALLOWED_CONFIDENCE:
        diagnostics.append(
            _diagnostic(
                f"MVC{idx + 100:03d}",
                target_claim_id=claim["claim_id"],
                severity="non_blocking",
                issue_type="invalid_confidence",
                message=f"Invalid confidence `{confidence}` was downgraded to unknown.",
                recommended_action="downgrade_confidence",
            )
        )
        claim["confidence"] = "unknown"

    evidence_ids = claim.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        evidence_ids = []
        claim["evidence_ids"] = evidence_ids
        diagnostics.append(
            _diagnostic(
                f"MVC{idx + 200:03d}",
                target_claim_id=claim["claim_id"],
                severity="blocking",
                issue_type="claim_evidence_ids_not_list",
                message="evidence_ids must be a list.",
                recommended_action="drop_or_retry_claim",
            )
        )

    unknown_evidence = [eid for eid in evidence_ids if eid not in known_evidence_ids]
    if unknown_evidence:
        diagnostics.append(
            _diagnostic(
                f"MVC{idx + 300:03d}",
                target_claim_id=claim["claim_id"],
                severity="blocking",
                issue_type="unknown_evidence_id",
                message=f"Model referenced unknown evidence ids: {', '.join(unknown_evidence)}.",
                recommended_action="collect_more_evidence_or_drop_claim",
                related_evidence_ids=unknown_evidence,
            )
        )
        claim["evidence_ids"] = [eid for eid in evidence_ids if eid in known_evidence_ids]

    if not claim.get("evidence_ids") and claim.get("confidence") != "unknown":
        diagnostics.append(
            _diagnostic(
                f"MVC{idx + 400:03d}",
                target_claim_id=claim["claim_id"],
                severity="blocking" if claim.get("confidence") == "confirmed" else "non_blocking",
                issue_type="model_claim_without_evidence",
                message="Model claim without valid evidence was downgraded to unknown.",
                recommended_action="downgrade_confidence",
            )
        )
        claim["confidence"] = "unknown"

    if claim.get("confidence") == "confirmed" and len(claim.get("evidence_ids", [])) < 1:
        diagnostics.append(
            _diagnostic(
                f"MVC{idx + 500:03d}",
                target_claim_id=claim["claim_id"],
                severity="blocking",
                issue_type="unsupported_confirmed_claim",
                message="Confirmed model claim needs at least one known evidence id.",
                recommended_action="downgrade_confidence",
            )
        )
        claim["confidence"] = "unknown"


def _validate_requested_followup_tools(normalized: dict[str, Any], diagnostics: list[dict[str, Any]]) -> None:
    tools = normalized.get("requested_followup_tools")
    if not isinstance(tools, list):
        diagnostics.append(
            _diagnostic(
                "MVD020",
                severity="blocking",
                issue_type="requested_followup_tools_not_list",
                message="requested_followup_tools must be a list.",
                recommended_action="retry_model_with_schema",
            )
        )
        normalized["requested_followup_tools"] = []
        return

    safe_tools = []
    for idx, tool in enumerate(tools, start=1):
        tool_name = tool.get("tool_name") if isinstance(tool, dict) else tool
        if tool_name not in ALLOWED_FOLLOWUP_TOOLS:
            diagnostics.append(
                _diagnostic(
                    f"MVT{idx:03d}",
                    severity="blocking",
                    issue_type="forbidden_followup_tool",
                    message=f"Model requested forbidden or unknown follow-up tool: {tool_name}.",
                    recommended_action="drop_tool_request",
                )
            )
            continue
        safe_tools.append(tool)
    normalized["requested_followup_tools"] = safe_tools


def _validate_evidence_list_objects(
    normalized: dict[str, Any],
    field_name: str,
    known_evidence_ids: set[str],
    diagnostics: list[dict[str, Any]],
) -> None:
    items = normalized.get(field_name)
    if not isinstance(items, list):
        diagnostics.append(
            _diagnostic(
                f"MVD_{field_name}",
                severity="blocking",
                issue_type=f"{field_name}_not_list",
                message=f"{field_name} must be a list.",
                recommended_action="retry_model_with_schema",
            )
        )
        normalized[field_name] = []
        return

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            diagnostics.append(
                _diagnostic(
                    f"MVO{idx:03d}",
                    severity="blocking",
                    issue_type=f"{field_name}_item_not_object",
                    message=f"{field_name}[{idx - 1}] must be an object.",
                    recommended_action="drop_item",
                )
            )
            continue
        evidence_ids = item.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            diagnostics.append(
                _diagnostic(
                    f"MVO{idx + 100:03d}",
                    severity="blocking",
                    issue_type=f"{field_name}_evidence_ids_not_list",
                    message=f"{field_name}[{idx - 1}].evidence_ids must be a list.",
                    recommended_action="drop_or_retry_item",
                )
            )
            item["evidence_ids"] = []
            continue
        unknown = [eid for eid in evidence_ids if eid not in known_evidence_ids]
        if unknown:
            diagnostics.append(
                _diagnostic(
                    f"MVO{idx + 200:03d}",
                    severity="blocking",
                    issue_type=f"{field_name}_unknown_evidence_id",
                    message=f"{field_name}[{idx - 1}] references unknown evidence ids: {', '.join(unknown)}.",
                    recommended_action="collect_more_evidence_or_drop_item",
                    related_evidence_ids=unknown,
                )
            )
            item["evidence_ids"] = [eid for eid in evidence_ids if eid in known_evidence_ids]


def _attach_claim_validation_status(normalized: dict[str, Any], diagnostics: list[dict[str, Any]]) -> None:
    diagnostics_by_claim: dict[str, list[str]] = {}
    blocking_by_claim: set[str] = set()
    for diagnostic in diagnostics:
        claim_id = diagnostic.get("target_claim_id")
        if not claim_id:
            continue
        diagnostics_by_claim.setdefault(claim_id, []).append(diagnostic["diagnostic_id"])
        if diagnostic.get("severity") == "blocking":
            blocking_by_claim.add(claim_id)
    for claim in normalized.get("candidate_claims", []):
        if not isinstance(claim, dict):
            continue
        claim_id = claim.get("claim_id")
        claim["diagnostic_ids"] = diagnostics_by_claim.get(claim_id, [])
        claim["validation_status"] = "rejected" if claim_id in blocking_by_claim else "accepted_for_grounding"


def _diagnostic(
    diagnostic_id: str,
    severity: str,
    issue_type: str,
    message: str,
    recommended_action: str,
    target_claim_id: str | None = None,
    related_evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "diagnostic_id": diagnostic_id,
        "target_claim_id": target_claim_id,
        "severity": severity,
        "issue_type": issue_type,
        "recommended_action": recommended_action,
        "related_evidence_ids": related_evidence_ids or [],
        "message": message,
    }
