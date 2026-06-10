import { describe, it, expect } from "vitest";
import {
  buildExternalRequestPackage,
  EXTERNAL_REQUEST_PACKAGE_VERSION,
} from "../agent/externalRequestPackage";
import type { ProjectBundle } from "../types";

/** Minimal mock bundle for T045 tests */
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

describe("T045 External Request Package", () => {
  it("schema_version matches constant", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.schema_version).toBe(EXTERNAL_REQUEST_PACKAGE_VERSION);
    expect(pkg.schema_version).toContain("external-request-package");
  });

  it("always has dry_run=true", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.dry_run).toBe(true);
  });

  it("always has send_allowed=false", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.send_allowed).toBe(false);
  });

  it("always has approval_required=true", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.approval_required).toBe(true);
  });

  it("initial approval_state is not_requested", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.approval_state).toBe("not_requested");
  });

  it("provider_kind is external_disabled", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.provider_kind).toBe("external_disabled");
  });

  it("contains policy_version", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.policy_version).toBeTruthy();
  });

  it("contains request_id", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.request_id).toBeTruthy();
    expect(pkg.request_id.startsWith("req-")).toBe(true);
  });

  it("contains created_at timestamp", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.created_at).toBeTruthy();
    expect(new Date(pkg.created_at).toISOString()).toBe(pkg.created_at);
  });

  it("includes context_bundle with items", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.context_bundle).toBeDefined();
    expect(pkg.context_bundle.context_items.length).toBeGreaterThan(0);
  });

  it("includes request_plan", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.request_plan).toBeDefined();
    expect(pkg.request_plan.dry_run).toBe(true);
    expect(pkg.request_plan.policy_allowed).toBe(false);
  });

  it("request_body_preview has messages_preview", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.request_body_preview.messages_preview.length).toBe(2);
    expect(pkg.request_body_preview.messages_preview[0].role).toBe("system");
    expect(pkg.request_body_preview.messages_preview[1].role).toBe("user");
  });

  it("request_body_preview has context_items_count", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.request_body_preview.context_items_count).toBe(
      pkg.context_bundle.context_items.length
    );
  });

  it("request_body_preview has total_tokens_estimate", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.request_body_preview.total_tokens_estimate).toBe(
      pkg.context_bundle.token_estimate_rough
    );
  });

  it("risk_summary has correct defaults", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.risk_summary.raw_question_included).toBe(false);
    expect(pkg.risk_summary.api_key_required).toBe(false);
    expect(pkg.risk_summary.network_call_planned).toBe(false);
    expect(pkg.risk_summary.secret_storage_planned).toBe(false);
    expect(pkg.risk_summary.external_call_blocked_by_policy).toBe(true);
  });

  it("risk_summary detects non-sensitive question", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.risk_summary.contains_sensitive_question).toBe(false);
  });

  it("risk_summary detects sensitive question", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(
      bundle,
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz",
      null
    );
    expect(pkg.risk_summary.contains_sensitive_question).toBe(true);
  });

  it("question_preview is redacted for sensitive content", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(
      bundle,
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz",
      null
    );
    expect(pkg.question_preview).toContain("redacted");
  });

  it("user message preview contains redacted marker for sensitive question", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(
      bundle,
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz",
      null
    );
    const userMsg = pkg.request_body_preview.messages_preview.find(
      (m) => m.role === "user"
    );
    expect(userMsg).toBeDefined();
    expect(userMsg!.content_preview).toContain("redacted");
  });

  it("does not leak sensitive raw question anywhere in package JSON", () => {
    const bundle = makeMockBundle();
    const rawQuestion =
      "my api_key is sk-abcdefghijklmnopqrstuvwxyz and token ghp_abcdefghijklmnopqrstuvwxyz";
    const pkg = buildExternalRequestPackage(bundle, rawQuestion, null);
    const serialized = JSON.stringify(pkg);

    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
    expect(serialized).not.toContain("ghp_abcdefghijklmnopqrstuvwxyz");
    expect(serialized).not.toContain("api_key is");
    expect(serialized).not.toContain("token ghp_");
  });

  it("does not leak other sensitive patterns in package JSON", () => {
    const bundle = makeMockBundle();
    const rawQuestion = "password is secret123 and bearer abcdef";
    const pkg = buildExternalRequestPackage(bundle, rawQuestion, null);
    const serialized = JSON.stringify(pkg);

    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("password is secret123");
    expect(serialized).not.toContain("bearer abcdef");
  });

  it("keeps non-sensitive question preview in request body", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const userMsg = pkg.request_body_preview.messages_preview.find(
      (m) => m.role === "user"
    );
    expect(userMsg).toBeDefined();
    expect(userMsg!.content_preview).toContain("what is cfo?");
  });

  it("works with null bundle", () => {
    const pkg = buildExternalRequestPackage(null, "what is cfo?", null);
    expect(pkg.dry_run).toBe(true);
    expect(pkg.send_allowed).toBe(false);
    expect(pkg.context_bundle.context_items).toEqual([]);
    expect(pkg.limitations.some((l) => l.includes("No bundle loaded"))).toBe(true);
  });

  it("selected_node_id is preserved", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", "cfo");
    expect(pkg.selected_node_id).toBe("cfo");
  });

  it("includes artifacts_used", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.artifacts_used.length).toBeGreaterThan(0);
  });

  it("limitations include T045 notes", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.limitations.some((l) => l.includes("T045"))).toBe(true);
    expect(pkg.limitations.some((l) => l.includes("no network send"))).toBe(true);
  });
});
