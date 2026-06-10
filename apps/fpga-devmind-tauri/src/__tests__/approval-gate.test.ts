import { describe, it, expect } from "vitest";
import {
  createPreviewDecision,
  approveExternalRequest,
  denyExternalRequest,
  APPROVAL_GATE_VERSION,
} from "../agent/approvalGate";
import { buildExternalRequestPackage } from "../agent/externalRequestPackage";
import type { ProjectBundle } from "../types";

/** Minimal mock bundle for T045 tests */
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
    graph: {
      nodes: [],
      edges: [],
    },
    evidence_chain: {},
    agent_suggested_questions: [],
  } as any;
}

describe("T045 Approval Gate", () => {
  it("createPreviewDecision returns previewed state", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const decision = createPreviewDecision(pkg);

    expect(decision.schema_version).toBe(APPROVAL_GATE_VERSION);
    expect(decision.state).toBe("previewed");
    expect(decision.send_allowed).toBe(false);
    expect(decision.request_id).toBe(pkg.request_id);
    expect(decision.policy_version).toBeTruthy();
    expect(decision.decided_at).toBeTruthy();
    expect(new Date(decision.decided_at).toISOString()).toBe(decision.decided_at);
  });

  it("approveExternalRequest returns approved_but_blocked", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const decision = approveExternalRequest(pkg);

    expect(decision.state).toBe("approved_but_blocked");
    expect(decision.send_allowed).toBe(false);
    expect(decision.request_id).toBe(pkg.request_id);
    expect(decision.reason).toContain("blocked");
    expect(decision.reason).toContain("T045");
  });

  it("denyExternalRequest returns denied", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const decision = denyExternalRequest(pkg);

    expect(decision.state).toBe("denied");
    expect(decision.send_allowed).toBe(false);
    expect(decision.request_id).toBe(pkg.request_id);
    expect(decision.reason).toContain("Denied");
  });

  it("denyExternalRequest accepts custom reason", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    const decision = denyExternalRequest(pkg, "Custom denial reason");

    expect(decision.state).toBe("denied");
    expect(decision.reason).toBe("Custom denial reason");
  });

  it("all decisions have send_allowed=false", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);

    const preview = createPreviewDecision(pkg);
    const approved = approveExternalRequest(pkg);
    const denied = denyExternalRequest(pkg);

    expect(preview.send_allowed).toBe(false);
    expect(approved.send_allowed).toBe(false);
    expect(denied.send_allowed).toBe(false);
  });

  it("approve does not change package.send_allowed", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);
    expect(pkg.send_allowed).toBe(false);

    approveExternalRequest(pkg);
    expect(pkg.send_allowed).toBe(false);
  });

  it("no state allows sending", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);

    const preview = createPreviewDecision(pkg);
    const approved = approveExternalRequest(pkg);
    const denied = denyExternalRequest(pkg);

    const allStates = [preview.state, approved.state, denied.state];
    expect(allStates).not.toContain("sent");
    expect(allStates).not.toContain("sending");
    expect(allStates).not.toContain("allowed");
  });

  it("decisions reference correct request_id", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);

    const preview = createPreviewDecision(pkg);
    const approved = approveExternalRequest(pkg);
    const denied = denyExternalRequest(pkg);

    expect(preview.request_id).toBe(pkg.request_id);
    expect(approved.request_id).toBe(pkg.request_id);
    expect(denied.request_id).toBe(pkg.request_id);
  });

  it("decisions contain policy_version", () => {
    const bundle = makeMockBundle();
    const pkg = buildExternalRequestPackage(bundle, "what is cfo?", null);

    const preview = createPreviewDecision(pkg);
    expect(preview.policy_version).toBeTruthy();
  });

  it("JSON serialization does not leak raw sensitive question", () => {
    const bundle = makeMockBundle();
    const rawQuestion = "my api_key is sk-abcdefghijklmnopqrstuvwxyz";
    const pkg = buildExternalRequestPackage(bundle, rawQuestion, null);
    const decision = approveExternalRequest(pkg);
    const serialized = JSON.stringify(decision);

    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
  });
});
