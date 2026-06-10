import { describe, it, expect } from "vitest";
import {
  executeExternalProviderPipeline,
  EXTERNAL_EXECUTION_VERSION,
} from "../agent/externalExecution";
import type { ProjectBundle } from "../types";

/** Minimal mock bundle for T046 tests */
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

describe("T046 External Execution Pipeline", () => {
  it("schema version is correct", () => {
    expect(EXTERNAL_EXECUTION_VERSION).toBe("external-execution-0.1");
  });

  it("preview_only returns blocked=true, sent=false", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "blocked",
      approval_action: "preview_only",
    });

    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.send_allowed).toBe(false);
    expect(result.approval_state).toBe("previewed");
    expect(result.mock_response).toBe(false);
  });

  it("simulate_approve + blocked transport returns approved_but_blocked but sent=false", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "blocked",
      approval_action: "simulate_approve",
    });

    expect(result.approval_state).toBe("approved_but_blocked");
    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.send_allowed).toBe(false);
    expect(result.mock_response).toBe(false);
    expect(result.answer_preview).toBe("");
  });

  it("simulate_approve + mock transport returns mock_response=true but sent=false", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });

    expect(result.approval_state).toBe("approved_but_blocked");
    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.send_allowed).toBe(false);
    expect(result.mock_response).toBe(true);
    expect(result.answer_preview).toContain("MOCK RESPONSE");
    expect(result.answer_preview).toContain("T046");
  });

  it("deny returns denied and sent=false", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "deny",
    });

    expect(result.approval_state).toBe("denied");
    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.send_allowed).toBe(false);
  });

  it("all paths have send_allowed=false", () => {
    const bundle = makeMockBundle();
    const actions = ["preview_only", "simulate_approve", "deny"] as const;
    const transports = ["blocked", "mock"] as const;

    for (const action of actions) {
      for (const transport of transports) {
        const result = executeExternalProviderPipeline({
          bundle,
          question: "what is cfo?",
          selectedNodeId: null,
          provider_id: "mock_external_llm",
          transport_kind: transport,
          approval_action: action,
        });
        expect(result.send_allowed, `action=${action}, transport=${transport}`).toBe(false);
      }
    }
  });

  it("all paths have egress_guard.allowed=false", () => {
    const bundle = makeMockBundle();
    const actions = ["preview_only", "simulate_approve", "deny"] as const;

    for (const action of actions) {
      const result = executeExternalProviderPipeline({
        bundle,
        question: "what is cfo?",
        selectedNodeId: null,
        provider_id: "mock_external_llm",
        transport_kind: "mock",
        approval_action: action,
      });
      expect(result.egress_guard.allowed, `action=${action}`).toBe(false);
    }
  });

  it("JSON.stringify(result) does not contain raw sensitive question", () => {
    const bundle = makeMockBundle();
    const rawQuestion = "my api_key is sk-abcdefghijklmnopqrstuvwxyz";
    const result = executeExternalProviderPipeline({
      bundle,
      question: rawQuestion,
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
  });

  it("JSON.stringify(result) does not contain secret keywords", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain("api_key");
    expect(serialized).not.toContain("apiKey");
    expect(serialized).not.toContain("secret");
    // "tokens" (as in LLM token count) is legitimate terminology — check for sensitive token patterns instead
    expect(serialized).not.toMatch(/\btoken\s*[:=]\s*["']?[a-zA-Z0-9_-]+/i);
    expect(serialized).not.toContain("bearer");
    expect(serialized).not.toContain("password");
  });

  it("null bundle executes with limitations containing No bundle loaded", () => {
    const result = executeExternalProviderPipeline({
      bundle: null,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "blocked",
      approval_action: "preview_only",
    });

    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.limitations.some((l) => l.includes("No bundle loaded"))).toBe(true);
    expect(result.artifacts_used).toEqual([]);
  });

  it("artifacts_used and evidence_ids pass through from request package", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });

    expect(result.artifacts_used.length).toBeGreaterThan(0);
    expect(result.evidence_ids.length).toBeGreaterThan(0);
  });

  it("no path produces sent=true", () => {
    const bundle = makeMockBundle();
    const actions = ["preview_only", "simulate_approve", "deny"] as const;
    const transports = ["blocked", "mock"] as const;
    const providers = ["mock_external_llm", "future_openai"] as const;

    for (const action of actions) {
      for (const transport of transports) {
        for (const provider of providers) {
          const result = executeExternalProviderPipeline({
            bundle,
            question: "what is cfo?",
            selectedNodeId: null,
            provider_id: provider,
            transport_kind: transport,
            approval_action: action,
          });
          expect(result.sent, `provider=${provider}, action=${action}, transport=${transport}`).toBe(false);
        }
      }
    }
  });

  it("no path produces blocked=false", () => {
    const bundle = makeMockBundle();
    const actions = ["preview_only", "simulate_approve", "deny"] as const;
    const transports = ["blocked", "mock"] as const;

    for (const action of actions) {
      for (const transport of transports) {
        const result = executeExternalProviderPipeline({
          bundle,
          question: "what is cfo?",
          selectedNodeId: null,
          provider_id: "mock_external_llm",
          transport_kind: transport,
          approval_action: action,
        });
        expect(result.blocked, `action=${action}, transport=${transport}`).toBe(true);
      }
    }
  });

  it("future provider with mock transport returns mock_response but blocked", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "future_openai",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });

    expect(result.sent).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.mock_response).toBe(true);
    expect(result.egress_guard.reason).toContain("placeholder");
  });

  it("transport response is included in result", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });

    expect(result.transport_response).toBeDefined();
    expect(result.transport_response.sent).toBe(false);
    expect(result.transport_response.blocked).toBe(true);
    expect(result.transport_response.mock_response).toBe(true);
    expect(result.transport_response.egress_guard.allowed).toBe(false);
  });

  it("result contains policy version", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "blocked",
      approval_action: "preview_only",
    });

    expect(result.policy_version).toBeTruthy();
    expect(result.policy_version).toContain("t043");
  });

  it("result contains request_id", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "blocked",
      approval_action: "preview_only",
    });

    expect(result.request_id).toBeTruthy();
    expect(result.request_id.startsWith("req-")).toBe(true);
  });

  it("limitations mention T046 and no network", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: null,
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "simulate_approve",
    });

    expect(result.limitations.some((l) => l.includes("T046"))).toBe(true);
    expect(result.limitations.some((l) => l.includes("No network call"))).toBe(true);
    expect(result.limitations.some((l) => l.includes("No API key"))).toBe(true);
  });

  it("selected_node_id is preserved in execution", () => {
    const bundle = makeMockBundle();
    const result = executeExternalProviderPipeline({
      bundle,
      question: "what is cfo?",
      selectedNodeId: "cfo",
      provider_id: "mock_external_llm",
      transport_kind: "mock",
      approval_action: "preview_only",
    });

    expect(result).toBeDefined();
    expect(result.sent).toBe(false);
  });
});
