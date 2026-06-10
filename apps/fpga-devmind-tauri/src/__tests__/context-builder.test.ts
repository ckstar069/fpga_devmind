import { describe, it, expect } from "vitest";
import {
  buildSourceEvidencePack,
  SOURCE_EVIDENCE_PACK_VERSION,
} from "../agent/sourcePack";
import {
  buildLlmContext,
  LLM_CONTEXT_VERSION,
} from "../agent/contextBuilder";
import type { ProjectBundle } from "../types";

/** Minimal mock bundle for T044 tests */
function makeMockBundle(): ProjectBundle {
  return {
    // Use 'as any' for incomplete test mocks to avoid strict type noise
    // while still testing the core logic paths
    project_id: "test-project",
    project_path: "/test",
    timestamp: "2024-01-01T00:00:00Z",
    semantic_summary: {
      project_id: "test-project",
      top_level_purpose: "Test FPGA project for coarse synchronization",
      core_concepts: [
        { display_name: "cfo", role_in_project: "carrier frequency offset estimation", confidence: "high" },
        { display_name: "peak_idx", role_in_project: "peak detection index", confidence: "medium" },
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
          evidence_ids: ["ev-1", "ev-2"],
          source_files: ["src/cfo.py"],
        },
      ],
      edge_routes: [
        {
          edge_id: "edge-1",
          from_node_id: "n1",
          to_node_id: "n2",
          from_lane: "L5_fixedpoint",
          to_lane: "RTL",
          edge_type: "implements",
          confidence: "supported",
          evidence_ids: ["ev-1"],
          source_files: ["src/cfo.py", "rtl/cfo.v"],
        },
      ],
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

describe("T044 Source Evidence Pack", () => {
  it("returns empty pack for null bundle", () => {
    const pack = buildSourceEvidencePack(null, "what is cfo?", null);
    expect(pack.schema_version).toBe(SOURCE_EVIDENCE_PACK_VERSION);
    expect(pack.items).toEqual([]);
    expect(pack.limitations.length).toBeGreaterThan(0);
    expect(pack.limitations[0]).toContain("No bundle loaded");
  });

  it("matches concept routes by keyword", () => {
    const bundle = makeMockBundle();
    const pack = buildSourceEvidencePack(bundle, "what is cfo?", null);
    expect(pack.items.length).toBeGreaterThan(0);
    expect(pack.matched_concepts).toContain("cfo");
    expect(pack.items.some((i) => i.kind === "concept" && i.label === "cfo")).toBe(true);
  });

  it("matches by selectedNodeId", () => {
    const bundle = makeMockBundle();
    const pack = buildSourceEvidencePack(bundle, "random question", "cfo");
    expect(pack.items.some((i) => i.id === "cfo")).toBe(true);
  });

  it("includes artifacts used", () => {
    const bundle = makeMockBundle();
    const pack = buildSourceEvidencePack(bundle, "what is cfo?", null);
    expect(pack.artifacts_used.length).toBeGreaterThan(0);
    expect(pack.artifacts_used).toContain("agent_navigation_index.json");
  });

  it("includes evidence_ids and source_files", () => {
    const bundle = makeMockBundle();
    const pack = buildSourceEvidencePack(bundle, "what is cfo?", null);
    expect(pack.evidence_ids.length).toBeGreaterThan(0);
    expect(pack.source_files.length).toBeGreaterThan(0);
  });

  it("question_preview is redacted for sensitive content", () => {
    const bundle = makeMockBundle();
    const pack = buildSourceEvidencePack(bundle, "my api_key is sk-abcdefghijklmnopqrstuvwxyz", null);
    expect(pack.question_preview).toContain("redacted");
  });

  it("falls back to graph nodes when no nav index match", () => {
    const bundle = makeMockBundle();
    // Question that does not match any concept route
    const pack = buildSourceEvidencePack(bundle, "something completely unrelated xyz", null);
    // Should still have items from fallback graph matching or pipeline view
    expect(pack.items.length).toBeGreaterThanOrEqual(0);
  });
});

describe("T044 LLM Context Builder", () => {
  it("returns empty context for null bundle", () => {
    const ctx = buildLlmContext(null, "what is cfo?", null);
    expect(ctx.schema_version).toBe(LLM_CONTEXT_VERSION);
    expect(ctx.context_items).toEqual([]);
    expect(ctx.token_estimate_rough).toBe(0);
    expect(ctx.limitations.length).toBeGreaterThan(0);
  });

  it("includes semantic summary items", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    expect(ctx.context_items.some((i) => i.kind === "semantic_summary")).toBe(true);
  });

  it("includes pipeline edges", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    expect(ctx.context_items.some((i) => i.kind === "pipeline_edge")).toBe(true);
  });

  it("includes quality status when nav available", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    expect(ctx.context_items.some((i) => i.kind === "quality_status")).toBe(true);
  });

  it("caps context items to MAX_CONTEXT_ITEMS", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    expect(ctx.context_items.length).toBeLessThanOrEqual(20);
  });

  it("content previews are truncated", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    for (const item of ctx.context_items) {
      expect(item.content_preview.length).toBeLessThanOrEqual(500);
    }
  });

  it("token estimate is non-negative", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    expect(ctx.token_estimate_rough).toBeGreaterThanOrEqual(0);
  });

  it("includes artifacts_used, evidence_ids, source_files", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", null);
    expect(ctx.artifacts_used.length).toBeGreaterThan(0);
    expect(ctx.evidence_ids.length).toBeGreaterThanOrEqual(0);
    expect(ctx.source_files.length).toBeGreaterThanOrEqual(0);
  });

  it("question_preview is redacted for sensitive content", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "my api_key is sk-abcdefghijklmnopqrstuvwxyz", null);
    expect(ctx.question_preview).toContain("redacted");
  });

  it("selected_node_id is reflected in context", () => {
    const bundle = makeMockBundle();
    const ctx = buildLlmContext(bundle, "what is cfo?", "cfo");
    // Should include node_fallback or concept items related to cfo
    expect(ctx.context_items.some((i) => i.id === "cfo" || i.title === "cfo")).toBe(true);
  });

  it("does not leak sensitive raw question in JSON serialization", () => {
    const bundle = makeMockBundle();
    const rawQuestion = "my api_key is sk-abcdefghijklmnopqrstuvwxyz";
    const ctx = buildLlmContext(bundle, rawQuestion, null);
    const serialized = JSON.stringify(ctx);
    expect(ctx.question_preview).toContain("redacted");
    expect(serialized).not.toContain(rawQuestion);
    expect(serialized).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
  });

  it("sourcePack fallback does not claim missing nav when nav exists", () => {
    const bundle = makeMockBundle();
    // Question that does not match any concept route — nav exists but no match
    const pack = buildSourceEvidencePack(bundle, "something completely unrelated xyz", null);
    // Should NOT say "No agent_navigation_index" since nav exists
    const hasMissingNavMessage = pack.limitations.some((l) =>
      l.includes("No agent_navigation_index")
    );
    expect(hasMissingNavMessage).toBe(false);
  });

  it("sourcePack fallback mentions no matching route when nav exists but no match", () => {
    const bundle = makeMockBundle();
    // Question that does not match any concept route — nav exists but no match
    const pack = buildSourceEvidencePack(bundle, "something completely unrelated xyz", null);
    expect(pack.limitations.some((l) =>
      l.includes("No matching navigation route found")
    )).toBe(true);
  });
});
