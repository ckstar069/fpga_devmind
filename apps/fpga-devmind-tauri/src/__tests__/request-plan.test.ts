import { describe, it, expect } from "vitest";
import {
  buildDryRunExternalRequestPlan,
  REQUEST_PLAN_VERSION,
} from "../agent/requestPlan";
import type { ProjectBundle } from "../types";

/** Minimal mock bundle for T044 tests */
function makeMockBundle(): ProjectBundle {
  return {
    project_id: "test-project",
    project_path: "/test",
    timestamp: "2024-01-01T00:00:00Z",
    semantic_summary: {
      project_id: "test-project",
      top_level_purpose: "Test FPGA project for coarse synchronization",
      core_concepts: [
        { display_name: "cfo", role_in_project: "carrier frequency offset estimation", confidence: "high" },
      ],
      pipeline_stages: [
        { label: "L5_fixedpoint", role: "algorithm model" },
        { label: "RTL", role: "hardware implementation" },
      ],
    },
    semantic_pipeline_view: {
      cross_stage_edges: [
        {
          edge_id: "edge-1",
          from_node_id: "n1",
          to_node_id: "n2",
          from_lane: "L5_fixedpoint",
          to_lane: "RTL",
          edge_type: "implements",
          confidence: "supported",
          reason: "Direct implementation",
          evidence_ids: ["ev-1"],
          source_files: ["src/cfo.py", "rtl/cfo.v"],
        },
      ],
      pipeline_summary: {
        total_nodes: 10,
        total_cross_stage_edges: 3,
        concepts_with_full_pipeline: ["cfo"],
        concepts_with_gaps: [],
      },
    },
    agent_navigation_index: {
      entrypoints: [
        { kind: "concept", target_id: "cfo", label: "CFO", available: true },
      ],
      concept_routes: [
        {
          node_id: "cfo",
          concept: "cfo",
          confidence: "supported",
          evidence_ids: ["ev-1"],
          source_files: ["src/cfo.py"],
        },
      ],
      edge_routes: [],
      limitations: [],
      quality_status: {
        golden_spec_used: true,
        selected_precision_like: 0.85,
        selected_recall_like: 0.90,
        matched_core_count: 5,
        missed_core_count: 1,
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
    graph: {
      nodes: [
        {
          node_id: "cfo",
          label: "cfo",
          kind: "concept",
          confidence: "supported",
          evidence_ids: ["ev-1"],
          file_path: "src/cfo.py",
        },
      ],
      edges: [],
    },
    evidence_chain: {},
    agent_suggested_questions: [],
  } as any;
}

describe("T044 Dry-run External Request Plan", () => {
  it("schema_version matches constant", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.schema_version).toBe(REQUEST_PLAN_VERSION);
    expect(plan.schema_version).toContain("dry-run");
  });

  it("always has dry_run=true", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.dry_run).toBe(true);
  });

  it("always has policy_allowed=false", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.policy_allowed).toBe(false);
  });

  it("provider_kind is external_disabled", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.provider_kind).toBe("external_disabled");
  });

  it("blocked_reason mentions external provider disabled", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.blocked_reason).toContain("禁用");
  });

  it("contains policy_version", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.policy_version).toBeTruthy();
  });

  it("includes context_bundle with items", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.context_bundle).toBeDefined();
    expect(plan.context_bundle.context_items.length).toBeGreaterThan(0);
  });

  it("hypothetical_request_preview has model_name", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.hypothetical_request_preview.model_name).toContain("placeholder");
  });

  it("hypothetical_request_preview has system_prompt_preview", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.hypothetical_request_preview.system_prompt_preview.length).toBeGreaterThan(0);
  });

  it("hypothetical_request_preview has user_prompt_preview", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.hypothetical_request_preview.user_prompt_preview.length).toBeGreaterThan(0);
  });

  it("context_items_summary matches context_bundle items", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.hypothetical_request_preview.context_items_summary.length).toBe(
      plan.context_bundle.context_items.length
    );
  });

  it("token_estimate matches context bundle", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.hypothetical_request_preview.total_tokens_estimate).toBe(
      plan.context_bundle.token_estimate_rough
    );
  });

  it("includes artifacts_used", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.artifacts_used.length).toBeGreaterThan(0);
  });

  it("question_preview is redacted for sensitive content", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(
      bundle,
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz",
      null
    );
    expect(plan.question_preview).toContain("redacted");
  });

  it("works with null bundle", () => {
    const plan = buildDryRunExternalRequestPlan(null, "what is cfo?", null);
    expect(plan.dry_run).toBe(true);
    expect(plan.policy_allowed).toBe(false);
    expect(plan.context_bundle.context_items).toEqual([]);
    expect(plan.limitations.some((l) => l.includes("No bundle loaded"))).toBe(true);
  });

  it("selected_node_id is preserved", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", "cfo");
    expect(plan.selected_node_id).toBe("cfo");
  });

  it("limitations include dry-run and policy notes", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.limitations.some((l) => l.includes("Dry-run"))).toBe(true);
    expect(plan.limitations.some((l) => l.includes("外部 provider"))).toBe(true);
  });

  it("no api_key or endpoint fields exist", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null) as any;
    expect(plan.api_key).toBeUndefined();
    expect(plan.endpoint).toBeUndefined();
    expect(plan.headers).toBeUndefined();
    expect(plan.base_url).toBeUndefined();
  });

  it("user_prompt_preview does not contain raw sensitive question", () => {
    const bundle = makeMockBundle();
    const rawQuestion =
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz and token ghp_abcdefghijklmnopqrstuvwxyz";
    const plan = buildDryRunExternalRequestPlan(bundle, rawQuestion, null);

    expect(plan.question_preview).toContain("redacted");
    expect(plan.hypothetical_request_preview.user_prompt_preview).toContain("redacted");
    expect(plan.hypothetical_request_preview.user_prompt_preview).not.toContain(rawQuestion);
    expect(plan.hypothetical_request_preview.user_prompt_preview).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
    expect(plan.hypothetical_request_preview.user_prompt_preview).not.toContain("ghp_abcdefghijklmnopqrstuvwxyz");
  });

  it("does not leak sensitive raw question anywhere in dry-run plan JSON", () => {
    const bundle = makeMockBundle();
    const rawQuestion =
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz and token ghp_abcdefghijklmnopqrstuvwxyz";
    const plan = buildDryRunExternalRequestPlan(bundle, rawQuestion, null);
    const serialized = JSON.stringify(plan);

    expect(plan.question_preview).toContain("redacted");
    expect(plan.hypothetical_request_preview.user_prompt_preview).toContain("redacted");

    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
    expect(serialized).not.toContain("ghp_abcdefghijklmnopqrstuvwxyz");
    expect(serialized).not.toContain("api_key is");
    expect(serialized).not.toContain("token ghp_");
  });

  it("does not leak raw sensitive question with other patterns", () => {
    const bundle = makeMockBundle();
    const rawQuestion = "password is secret123 and bearer abcdef";
    const plan = buildDryRunExternalRequestPlan(bundle, rawQuestion, null);
    const serialized = JSON.stringify(plan);

    expect(plan.question_preview).toContain("redacted");
    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("password is secret123");
    expect(serialized).not.toContain("bearer abcdef");
  });

  it("keeps non-sensitive question preview in hypothetical user prompt", () => {
    const bundle = makeMockBundle();
    const plan = buildDryRunExternalRequestPlan(bundle, "what is cfo?", null);
    expect(plan.hypothetical_request_preview.user_prompt_preview).toContain("what is cfo?");
  });
});
