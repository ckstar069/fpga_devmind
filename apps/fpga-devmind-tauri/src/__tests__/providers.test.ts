import { describe, it, expect } from "vitest";
import {
  runAgent,
  deterministicProvider,
  offlineMockProvider,
  externalDisabledProvider,
  getAvailableProviderKinds,
  PROVIDER_CAPABILITIES,
} from "../agent";
import type { ProjectBundle } from "../types";

function makeTestBundle(): ProjectBundle {
  return {
    path: "/tmp/test_bundle",
    graph: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      nodes: [
        { node_id: "P1", label: "test_project", kind: "project", stage: "", confidence: "supported" },
        { node_id: "C_peak", label: "peak_idx", kind: "concept", stage: "", confidence: "supported" },
        { node_id: "C_cfo", label: "cfo", kind: "concept", stage: "", confidence: "inferred" },
        { node_id: "CL_peak", label: "peak_idx → RTL", kind: "mapping_claim", stage: "", confidence: "supported", concept: "peak_idx", bridge_kind: "calculation_role" },
        { node_id: "R1", label: "peak_sig", kind: "rtl_signal", stage: "", confidence: "supported", file_path: "/rtl/peak.v" },
      ],
      edges: [
        { edge_id: "E1", from_node_id: "P1", to_node_id: "C_peak", edge_type: "contains" },
        { edge_id: "E2", from_node_id: "C_peak", to_node_id: "CL_peak", edge_type: "has_claim" },
        { edge_id: "E3", from_node_id: "CL_peak", to_node_id: "R1", edge_type: "realizes" },
      ],
    },
    index: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      concept_index: {
        peak_idx: { status: "ok", claims: 1, evidence: 5, rtl_objects: 1 },
      },
      claim_index: {
        CL_peak: { concept: "peak_idx", confidence: "supported", bridge_kind: "calculation_role" },
      },
      evidence_index: {},
    },
    metadata: {
      schema_version: "p1b-project-run-metadata-0.1",
      command: "p1b-trace-project",
      project_root: "/tmp/test",
      concepts_processed: ["peak_idx"],
      status: "ok",
      mapping_claims: 1,
      evidence_items: 5,
      diagnostics: 0,
    },
  };
}

function makeNavBundle(): ProjectBundle {
  const base = makeTestBundle();
  return {
    ...base,
    semantic_summary: {
      schema_version: "project-semantic-summary-0.1",
      project_id: "test_project",
      project_root: "/tmp/test",
      project_kind_hint: "fpga_ofdm_sync",
      top_level_purpose: "Test project",
      pipeline_stages: [],
      core_concepts: [
        {
          canonical_name: "peak_idx",
          display_name: "peak_idx",
          category: "core_like",
          role_in_project: "peak detection",
          why_selected: "cross-stage evidence",
          aliases: [],
          l5_l6_evidence_count: 2,
          rtl_evidence_count: 1,
          test_evidence_count: 0,
          confidence: "supported",
          limitations: [],
        },
      ],
      implementation_modules: [],
      dataflow_summary: { nodes: [], edges: [] },
      l5_l6_to_rtl_summary: {
        concept_mappings: [],
        summary: {
          concepts_with_cross_stage_mapping: 0,
          concepts_missing_l5_l6: 0,
          concepts_missing_rtl: 0,
          inferred_only_mappings: 0,
        },
      },
      evidence_quality_summary: { strong_direct: 0, medium_structural: 0, weak_name_only: 0, inferred: 0 },
      uncertainty_summary: {
        inferred_claims: [],
        weak_only_links: [],
        naming_only_links: [],
        missing_l5_l6: [],
        missing_rtl: [],
        missing_test_evidence: [],
      },
      test_coverage_summary: {
        test_files_present: true,
        total_test_files: 1,
        concepts_with_test_match: 1,
        concepts_without_test_match: 0,
        per_concept: [],
      },
      source_provenance: {
        summary_generated_from: [],
        generation_timestamp: "2024-01-01T00:00:00Z",
        generator: "test",
      },
    },
    agent_navigation_index: {
      schema_version: "agent-navigation-index-0.1",
      project_id: "test_project",
      entrypoints: [
        { id: "overview", label: "项目整体理解", artifact: "project_semantic_summary.json", available: true, description: "Top-level purpose" },
        { id: "pipeline", label: "Pipeline / Dataflow", artifact: "semantic_pipeline_view.json", available: true, description: "Stage lanes" },
      ],
      question_routes: [
        { intent: "navigation_help", patterns: ["从哪里开始", "推荐"], primary_artifacts: ["agent_navigation_index.json"], fallback_artifacts: ["project_semantic_summary.json"] },
      ],
      concept_routes: [
        {
          concept: "peak_idx",
          node_id: "C_peak",
          confidence: "supported",
          mapping_confidence: "supported",
          mapping_reason: "Strong structural link",
          evidence_ids: ["ev1"],
          source_files: ["L5/peak.py"],
          known_gaps: [],
          has_l5_l6: true,
          has_rtl: true,
          has_test: false,
          claims: ["CL_peak"],
        },
      ],
      edge_routes: [],
      quality_status: {
        golden_spec_used: true,
        selected_precision_like: 0.75,
        selected_recall_like: 0.80,
        excluded_terms_selected: ["term1"],
        matched_core_count: 2,
        missed_core_count: 1,
        matched_secondary_count: 1,
      },
      limitations: [],
      source_provenance: {
        summary_generated_from: ["project_understanding_graph.json"],
        generation_timestamp: "2024-01-01T00:00:00Z",
        generator: "fpga_devmind.agent_navigator",
      },
    },
  };
}

describe("T042 Provider Boundary", () => {
  it("lists all provider kinds", () => {
    const kinds = getAvailableProviderKinds();
    expect(kinds).toContain("deterministic");
    expect(kinds).toContain("offline_mock");
    expect(kinds).toContain("external_disabled");
    expect(kinds.length).toBe(3);
  });

  it("PROVIDER_CAPABILITIES has correct flags", () => {
    expect(PROVIDER_CAPABILITIES.deterministic.enabled).toBe(true);
    expect(PROVIDER_CAPABILITIES.deterministic.network_allowed).toBe(false);
    expect(PROVIDER_CAPABILITIES.deterministic.requires_api_key).toBe(false);

    expect(PROVIDER_CAPABILITIES.offline_mock.enabled).toBe(true);
    expect(PROVIDER_CAPABILITIES.offline_mock.network_allowed).toBe(false);
    expect(PROVIDER_CAPABILITIES.offline_mock.requires_api_key).toBe(false);

    expect(PROVIDER_CAPABILITIES.external_disabled.enabled).toBe(false);
    expect(PROVIDER_CAPABILITIES.external_disabled.network_allowed).toBe(false);
    expect(PROVIDER_CAPABILITIES.external_disabled.requires_api_key).toBe(true);
  });

  describe("deterministic provider", () => {
    it("returns AgentRunResult with trace", () => {
      const bundle = makeTestBundle();
      const result = deterministicProvider.run({
        question: "这个项目整体实现了什么？",
        selectedNodeId: null,
        bundle,
        providerKind: "deterministic",
      });
      expect(result.provider).toBe("deterministic");
      expect(result.external_calls_made).toBe(false);
      expect(result.artifacts_used.length).toBeGreaterThan(0);
      expect(result.trace.trace_id).toMatch(/^trace-/);
      expect(result.trace.provider_kind).toBe("deterministic");
      expect(result.trace.steps.length).toBeGreaterThanOrEqual(1);
      expect(result.answer.conclusion).toBeTruthy();
      expect(result.answer.strength).toBeTruthy();
    });

    it("detects intent in trace", () => {
      const bundle = makeTestBundle();
      const result = deterministicProvider.run({
        question: "precision/recall 是多少？",
        selectedNodeId: null,
        bundle,
        providerKind: "deterministic",
      });
      expect(result.trace.matched_intent).toBe("quality_metrics");
    });
  });

  describe("offline mock provider", () => {
    it("returns AgentRunResult with trace and mock answer", () => {
      const bundle = makeNavBundle();
      const result = offlineMockProvider.run({
        question: "从哪里开始理解这个项目？",
        selectedNodeId: null,
        bundle,
        providerKind: "offline_mock",
      });
      expect(result.provider).toBe("offline_mock");
      expect(result.external_calls_made).toBe(false);
      expect(result.answer.answer).toContain("Offline Mock Agent");
      expect(result.trace.trace_id).toMatch(/^trace-/);
      expect(result.trace.steps.length).toBeGreaterThanOrEqual(2);
      expect(result.trace.artifacts_used.length).toBeGreaterThan(0);
    });

    it("detects navigation intent", () => {
      const bundle = makeNavBundle();
      const result = offlineMockProvider.run({
        question: "从哪里开始",
        selectedNodeId: null,
        bundle,
        providerKind: "offline_mock",
      });
      expect(result.trace.matched_intent).toBe("navigation_help");
      expect(result.answer.answer).toContain("入口");
    });

    it("handles null bundle gracefully", () => {
      const result = offlineMockProvider.run({
        question: "test",
        selectedNodeId: null,
        bundle: null,
        providerKind: "offline_mock",
      });
      expect(result.answer.answer).toContain("请先加载");
      expect(result.external_calls_made).toBe(false);
      expect(result.limitations.length).toBeGreaterThan(0);
    });

    it("returns quality metrics when asked", () => {
      const bundle = makeNavBundle();
      const result = offlineMockProvider.run({
        question: "precision/recall",
        selectedNodeId: null,
        bundle,
        providerKind: "offline_mock",
      });
      expect(result.trace.matched_intent).toBe("quality_metrics");
      expect(result.answer.answer).toContain("75.0%");
      expect(result.answer.answer).toContain("80.0%");
    });

    it("returns pipeline stages when asked", () => {
      const bundle = makeNavBundle();
      const result = offlineMockProvider.run({
        question: "pipeline stages",
        selectedNodeId: null,
        bundle,
        providerKind: "offline_mock",
      });
      expect(result.trace.matched_intent).toBe("pipeline_stages");
      expect(result.answer.answer).toContain("Offline Mock Agent");
    });

    it("returns data provenance when asked", () => {
      const bundle = makeNavBundle();
      const result = offlineMockProvider.run({
        question: "数据来源",
        selectedNodeId: null,
        bundle,
        providerKind: "offline_mock",
      });
      expect(result.trace.matched_intent).toBe("data_provenance");
      expect(result.answer.answer).toContain("artifact");
    });
  });

  describe("external disabled provider", () => {
    it("returns disabled message with no external calls", () => {
      const result = externalDisabledProvider.run({
        question: "test question",
        selectedNodeId: null,
        bundle: null,
        providerKind: "external_disabled",
      });
      expect(result.provider).toBe("external_disabled");
      expect(result.external_calls_made).toBe(false);
      expect(result.answer.answer).toContain("disabled");
      expect(result.answer.strength).toBe("none");
      expect(result.trace.matched_intent).toBe("external_disabled");
      expect(result.trace.steps[0].kind).toBe("check_provider_status");
    });
  });

  describe("runAgent dispatcher", () => {
    it("dispatches to deterministic by default", () => {
      const bundle = makeTestBundle();
      const result = runAgent({
        question: "test",
        selectedNodeId: null,
        bundle,
        providerKind: "deterministic",
      });
      expect(result.provider).toBe("deterministic");
      expect(result.external_calls_made).toBe(false);
    });

    it("dispatches to offline_mock when requested", () => {
      const bundle = makeNavBundle();
      const result = runAgent({
        question: "test",
        selectedNodeId: null,
        bundle,
        providerKind: "offline_mock",
      });
      expect(result.provider).toBe("offline_mock");
      expect(result.external_calls_made).toBe(false);
    });

    it("dispatches to external_disabled when requested", () => {
      const result = runAgent({
        question: "test",
        selectedNodeId: null,
        bundle: null,
        providerKind: "external_disabled",
      });
      expect(result.provider).toBe("external_disabled");
      expect(result.external_calls_made).toBe(false);
    });

    it("falls back to deterministic for unknown provider", () => {
      const bundle = makeTestBundle();
      const result = runAgent({
        question: "test",
        selectedNodeId: null,
        bundle,
        providerKind: "unknown" as any,
      });
      expect(result.provider).toBe("deterministic");
      expect(result.external_calls_made).toBe(false);
    });
  });
});
