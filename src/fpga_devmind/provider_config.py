"""Provider configuration drafts for future real model adapters.

No function in this module reads environment variable values or calls a network
API. It only describes the contract real providers must satisfy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .safety import ensure_safe_output_dir


DEFAULT_PROVIDER_CONFIG_OUT = Path("/tmp/fpga_devmind/provider_config")

SUPPORTED_PROVIDER_DRAFTS = {
    "deepseek": {
        "provider_id": "deepseek",
        "adapter_status": "draft_not_implemented",
        "api_key_env": "FPGA_DEVMIND_DEEPSEEK_API_KEY",
        "base_url_env": "FPGA_DEVMIND_DEEPSEEK_BASE_URL",
        "model_env": "FPGA_DEVMIND_DEEPSEEK_MODEL",
    },
    "glm": {
        "provider_id": "glm",
        "adapter_status": "draft_not_implemented",
        "api_key_env": "FPGA_DEVMIND_GLM_API_KEY",
        "base_url_env": "FPGA_DEVMIND_GLM_BASE_URL",
        "model_env": "FPGA_DEVMIND_GLM_MODEL",
    },
    "openai": {
        "provider_id": "openai",
        "adapter_status": "draft_not_implemented",
        "api_key_env": "FPGA_DEVMIND_OPENAI_API_KEY",
        "base_url_env": "FPGA_DEVMIND_OPENAI_BASE_URL",
        "model_env": "FPGA_DEVMIND_OPENAI_MODEL",
    },
}


def build_provider_config_draft(provider_id: str) -> dict[str, Any]:
    provider = SUPPORTED_PROVIDER_DRAFTS.get(provider_id)
    if provider is None:
        supported = ", ".join(sorted(SUPPORTED_PROVIDER_DRAFTS))
        raise ValueError(f"unsupported provider draft `{provider_id}`; supported: {supported}")

    return {
        "schema_version": "p1a-plus-provider-config-draft-0.1",
        **provider,
        "enabled_by_default": False,
        "external_api_allowed_by_default": False,
        "api_key_value_included": False,
        "provider_secret_value_included": False,
        "redaction_rules": [
            "Do not write API key values to provider_call.json.",
            "Do not write API key values to agent_trace.json.",
            "Do not write API key values to prompt_context.json.",
            "Do not write full environment variables to artifacts.",
            "Record only env var names and boolean presence flags.",
        ],
        "required_runtime_gates": [
            "explicit provider selection",
            "safe output path validation",
            "prompt_context redaction",
            "SemanticReasoningResult schema validation",
            "evidence id validation",
            "requested_followup_tools allowlist validation",
            "graph_write_proposal dry-run before ProjectGraph mutation",
        ],
        "not_implemented": [
            "network call",
            "API key loading",
            "provider-specific retry",
            "token accounting",
            "streaming response",
        ],
    }


def write_provider_config_draft(provider_id: str, out_dir: Path = DEFAULT_PROVIDER_CONFIG_OUT) -> dict[str, Any]:
    out_dir = ensure_safe_output_dir(out_dir, "provider config draft output")
    out_dir.mkdir(parents=True, exist_ok=True)
    draft = build_provider_config_draft(provider_id)
    path = out_dir / f"{provider_id}_provider_config_draft.json"
    path.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "out_dir": str(out_dir),
        "path": str(path),
        "draft": draft,
    }
