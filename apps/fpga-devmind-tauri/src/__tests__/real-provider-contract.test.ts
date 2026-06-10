import { describe, it, expect } from "vitest";
import {
  REAL_PROVIDER_CONTRACT_VERSION,
  buildRealProviderInvocationRequest,
  buildBlockedRealProviderResult,
  buildNotConfiguredResult,
} from "../agent/realProviderContract";
import { buildExternalRequestPackage } from "../agent/externalRequestPackage";
import type { ProjectBundle } from "../types";

function makeMockBundle(): ProjectBundle {
  return {
    project_id: "test-project",
    project_path: "/test",
    timestamp: "2024-01-01T00:00:00Z",
    semantic_summary: {
      project_id: "test-project",
      top_level_purpose: "Test",
      core_concepts: [
        { display_name: "cfo", role_in_project: "test", confidence: "high" },
      ],
      pipeline_stages: [{ label: "RTL", role: "test" }],
    },
    semantic_pipeline_view: {
      cross_stage_edges: [],
      pipeline_summary: {
        total_nodes: 1,
        total_cross_stage_edges: 0,
        concepts_with_full_pipeline: [],
        concepts_with_gaps: [],
      },
    },
    agent_navigation_index: {
      entrypoints: [],
      concept_routes: [],
      edge_routes: [],
      limitations: [],
      quality_status: {
        golden_spec_used: false,
        selected_precision_like: 0,
        selected_recall_like: 0,
        matched_core_count: 0,
        missed_core_count: 0,
      },
    },
    project_understanding_index: {
      project_id: "test-project",
      concepts: [],
      claims: [],
      evidence: [],
      rtl_modules: [],
      test_modules: [],
      limitations: [],
    },
    graph: { nodes: [], edges: [] },
    evidence_chain: {},
    agent_suggested_questions: [],
  } as any;
}

describe("T047 Real Provider Contract", () => {
  it("contract version is correct", () => {
    expect(REAL_PROVIDER_CONTRACT_VERSION).toBe("real-provider-contract-0.1");
  });

  it("invocation request schema is correct", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const req = buildRealProviderInvocationRequest(
      pkg,
      "gpt-4o-mini",
      "https://api.example.com/v1/chat/completions"
    );

    expect(req.schema_version).toBe(REAL_PROVIDER_CONTRACT_VERSION);
    expect(req.provider_id).toBe("openai_compatible_ephemeral");
    expect(req.model_name).toBe("gpt-4o-mini");
    expect(req.endpoint_url).toBe("https://api.example.com/v1/chat/completions");
    expect(req.approval_state).toBe("approved_but_blocked");
    expect(req.send_allowed_by_user).toBe(true);
    expect(req.request_id).toBe(pkg.request_id);
  });

  it("TS request contract does not contain api_key field", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const req = buildRealProviderInvocationRequest(
      pkg,
      "gpt-4o-mini",
      "https://api.example.com/v1/chat/completions"
    );
    const serialized = JSON.stringify(req);
    // The request_package contains risk_summary.api_key_required (schema metadata, not a secret).
    // We check for actual secret values and patterns instead.
    expect(serialized).not.toContain("sk-");
    expect(serialized).not.toContain("ghp_");
    expect(serialized).not.toContain("xoxb-");
    expect(serialized).not.toContain("password123");
    // Ensure the contract itself has no api_key field at top level
    const contractKeys = Object.keys(req);
    expect(contractKeys).not.toContain("api_key");
    expect(contractKeys).not.toContain("apiKey");
    expect(contractKeys).not.toContain("secret");
    expect(contractKeys).not.toContain("password");
  });

  it("TS request contract does not contain token/bearer fields", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const req = buildRealProviderInvocationRequest(
      pkg,
      "gpt-4o-mini",
      "https://api.example.com/v1/chat/completions"
    );
    const serialized = JSON.stringify(req);
    // "token" as in LLM token is legitimate; check for bearer/auth patterns
    expect(serialized).not.toContain("bearer");
    expect(serialized).not.toContain("authorization");
  });

  it("invocation result has raw_response_stored=false", () => {
    const result = buildBlockedRealProviderResult("req-test", "Test blocked");
    expect(result.raw_response_stored).toBe(false);
    expect(result.audit_redacted).toBe(true);
  });

  it("answer_text_preview is empty for blocked result", () => {
    const result = buildBlockedRealProviderResult("req-test", "Blocked");
    expect(result.answer_text_preview).toBe("");
    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.status).toBe("blocked");
  });

  it("error_preview is redacted and never contains raw key", () => {
    const result = buildBlockedRealProviderResult("req-test", "Some error");
    expect(result.error_preview).toBe("Some error");
    // The build function itself should not inject keys
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain("sk-");
  });

  it("not_configured result has correct status", () => {
    const result = buildNotConfiguredResult("req-test");
    expect(result.status).toBe("blocked");
    expect(result.sent).toBe(false);
    expect(result.error_preview).toContain("not configured");
  });

  it("JSON.stringify(contract) does not contain raw sensitive question", () => {
    const rawQuestion = "my api_key is sk-abcdefghijklmnopqrstuvwxyz";
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, rawQuestion, null);
    const req = buildRealProviderInvocationRequest(
      pkg,
      "gpt-4o-mini",
      "https://api.example.com/v1/chat/completions"
    );
    const serialized = JSON.stringify(req);
    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
  });

  it("JSON.stringify(result) does not contain raw API key", () => {
    const result = buildBlockedRealProviderResult("req-test", "Error");
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain("sk-");
    expect(serialized).not.toContain("api_key");
  });

  it("result created_at is valid ISO string", () => {
    const result = buildBlockedRealProviderResult("req-test", "Error");
    expect(new Date(result.created_at).toISOString()).toBe(result.created_at);
  });
});
