"""Semantic provider adapters for P1a+.

These adapters are provider-safe scaffolding only. They do not call external
APIs or read credentials. Real providers must implement the same interface and
still pass through llm_contract validation before graph writes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


@dataclass
class SemanticProviderResponse:
    provider_id: str
    mode: str
    result: dict[str, Any]
    call_record: dict[str, Any]


class SemanticProvider(Protocol):
    provider_id: str
    mode: str

    def run(self, prompt_context: dict[str, Any]) -> SemanticProviderResponse:
        """Return a SemanticReasoningResult-like payload."""


class NoopSemanticProvider:
    provider_id = "noop"
    mode = "deterministic_dry_run_no_llm"

    def run(self, prompt_context: dict[str, Any]) -> SemanticProviderResponse:
        request_id = prompt_context.get("task", {}).get("request_id") or "unknown"
        result = {
            "schema_version": "p1a-plus-semantic-result-0.1",
            "request_id": request_id,
            "plan_step_id": "S002",
            "reasoning_summary": "No model provider was called in deterministic dry-run mode.",
            "candidate_claims": [],
            "proposed_edges": [],
            "proposed_uncertainties": [],
            "requested_followup_tools": [],
            "self_check_notes": [
                "provider_not_called",
                "no_model_generated_claims",
            ],
        }
        return SemanticProviderResponse(
            provider_id=self.provider_id,
            mode=self.mode,
            result=result,
            call_record=_offline_call_record(
                provider_id=self.provider_id,
                mode=self.mode,
                prompt_context=prompt_context,
                source=None,
                status="completed",
            ),
        )


class FixtureSemanticProvider:
    provider_id = "fixture"
    mode = "deterministic_dry_run_with_model_fixture"

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def run(self, prompt_context: dict[str, Any]) -> SemanticProviderResponse:
        result = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        return SemanticProviderResponse(
            provider_id=self.provider_id,
            mode=self.mode,
            result=result,
            call_record=_offline_call_record(
                provider_id=self.provider_id,
                mode=self.mode,
                prompt_context=prompt_context,
                source=str(self.fixture_path),
                status="completed",
            ),
        )


def provider_for_fixture(model_result_path: Path | None) -> SemanticProvider:
    return FixtureSemanticProvider(model_result_path) if model_result_path else NoopSemanticProvider()


def response_to_dict(response: SemanticProviderResponse) -> dict[str, Any]:
    return asdict(response)


def _offline_call_record(
    provider_id: str,
    mode: str,
    prompt_context: dict[str, Any],
    source: str | None,
    status: str,
) -> dict[str, Any]:
    return {
        "schema_version": "p1a-plus-provider-call-0.1",
        "provider_id": provider_id,
        "mode": mode,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "external_api_called": False,
        "api_key_used": False,
        "api_key_logged": False,
        "prompt_context_schema_version": prompt_context.get("schema_version"),
        "known_evidence_count": len(prompt_context.get("known_evidence_ids", [])),
        "known_claim_count": len(prompt_context.get("known_claim_ids", [])),
        "redaction_policy": prompt_context.get("redaction_policy", {}),
    }
