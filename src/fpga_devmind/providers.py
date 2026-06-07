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

from .provider_config import build_provider_config_draft


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


class MockSemanticProvider:
    provider_id = "mock_semantic"
    mode = "deterministic_dry_run_with_mock_semantic"

    def run(self, prompt_context: dict[str, Any]) -> SemanticProviderResponse:
        request_id = prompt_context.get("task", {}).get("request_id") or "unknown"
        evidence_ids = prompt_context.get("known_evidence_ids", [])
        first_evidence_id = evidence_ids[0] if evidence_ids else None
        candidate_claims = []
        if first_evidence_id:
            candidate_claims.append(
                {
                    "claim_id": "M001",
                    "claim_type": "implementation_claim",
                    "statement": (
                        "Mock semantic provider proposes a supported stage interpretation "
                        "anchored to an existing evidence item."
                    ),
                    "subject_ids": ["stage:L6_resource_opt"],
                    "evidence_ids": [first_evidence_id],
                    "confidence": "supported",
                    "required_missing_evidence": [],
                    "generated_from_step": "S002",
                }
            )
        result = {
            "schema_version": "p1a-plus-semantic-result-0.1",
            "request_id": request_id,
            "plan_step_id": "S002",
            "reasoning_summary": "Mock semantic provider generated one evidence-anchored claim.",
            "candidate_claims": candidate_claims,
            "proposed_edges": [],
            "proposed_uncertainties": [],
            "requested_followup_tools": [],
            "self_check_notes": [
                "mock_semantic_provider",
                "no_external_api_called",
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


class ExternalProviderStub:
    mode = "external_provider_disabled"

    def __init__(self, provider_id: str, allow_external_api: bool = False) -> None:
        self.config = build_provider_config_draft(provider_id)
        self.provider_id = provider_id
        self.allow_external_api = allow_external_api
        if allow_external_api:
            self.mode = "external_provider_not_implemented"

    def run(self, prompt_context: dict[str, Any]) -> SemanticProviderResponse:
        request_id = prompt_context.get("task", {}).get("request_id") or "unknown"
        if self.allow_external_api:
            status = "blocked_adapter_not_implemented"
            reason = (
                f"External provider `{self.provider_id}` passed the explicit allow flag, "
                "but the real adapter is not implemented. No API key was loaded and no API call was made."
            )
            self_check_notes = [
                "external_provider_not_implemented",
                "no_external_api_called",
                "api_key_not_loaded",
            ]
        else:
            status = "blocked_disabled_provider"
            reason = (
                f"External provider `{self.provider_id}` is configured only as a disabled draft. "
                "No API call was made."
            )
            self_check_notes = [
                "external_provider_disabled",
                "no_external_api_called",
                "api_key_not_loaded",
            ]
        result = {
            "schema_version": "p1a-plus-semantic-result-0.1",
            "request_id": request_id,
            "plan_step_id": "S002",
            "reasoning_summary": reason,
            "candidate_claims": [],
            "proposed_edges": [],
            "proposed_uncertainties": [],
            "requested_followup_tools": [],
            "self_check_notes": self_check_notes,
        }
        return SemanticProviderResponse(
            provider_id=self.provider_id,
            mode=self.mode,
            result=result,
            call_record={
                **_offline_call_record(
                    provider_id=self.provider_id,
                    mode=self.mode,
                    prompt_context=prompt_context,
                    source=None,
                    status=status,
                ),
                "adapter_status": self.config["adapter_status"],
                "external_api_allowed": self.allow_external_api,
                "api_key_env": self.config["api_key_env"],
                "api_key_value_included": False,
            },
        )


def provider_for_mode(
    model_result_path: Path | None,
    use_mock_semantic: bool = False,
    external_provider: str | None = None,
    allow_external_api: bool = False,
) -> SemanticProvider:
    selected = [bool(model_result_path), use_mock_semantic, bool(external_provider)]
    if sum(1 for item in selected if item) > 1:
        raise ValueError("--model-result, --mock-semantic and --external-provider are mutually exclusive")
    if allow_external_api and not external_provider:
        raise ValueError("--allow-external-api requires --external-provider")
    if external_provider:
        return ExternalProviderStub(external_provider, allow_external_api=allow_external_api)
    if model_result_path:
        return FixtureSemanticProvider(model_result_path)
    if use_mock_semantic:
        return MockSemanticProvider()
    return NoopSemanticProvider()


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
