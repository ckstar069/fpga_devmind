import { describe, it, expect } from "vitest";
import { answerQuestion, SUGGESTED_QUESTIONS } from "../utils/agent";
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
        { node_id: "CL_cfo", label: "cfo → RTL", kind: "mapping_claim", stage: "", confidence: "inferred", concept: "cfo", bridge_kind: "naming_only" },
        { node_id: "R1", label: "peak_sig", kind: "rtl_signal", stage: "", confidence: "supported", file_path: "/rtl/peak.v" },
        { node_id: "R2", label: "cfo_sig", kind: "rtl_signal", stage: "", confidence: "inferred", file_path: "/rtl/cfo.v" },
      ],
      edges: [
        { edge_id: "E1", from_node_id: "P1", to_node_id: "C_peak", edge_type: "contains" },
        { edge_id: "E2", from_node_id: "P1", to_node_id: "C_cfo", edge_type: "contains" },
        { edge_id: "E3", from_node_id: "C_peak", to_node_id: "CL_peak", edge_type: "has_claim" },
        { edge_id: "E4", from_node_id: "C_cfo", to_node_id: "CL_cfo", edge_type: "has_claim" },
        { edge_id: "E5", from_node_id: "CL_peak", to_node_id: "R1", edge_type: "realizes" },
        { edge_id: "E6", from_node_id: "CL_cfo", to_node_id: "R2", edge_type: "realizes" },
      ],
    },
    index: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      concept_index: {
        peak_idx: { status: "ok", claims: 1, evidence: 5, rtl_objects: 1 },
        cfo: { status: "ok", claims: 1, evidence: 2, rtl_objects: 1 },
      },
      claim_index: {
        CL_peak: { concept: "peak_idx", confidence: "supported", bridge_kind: "calculation_role" },
        CL_cfo: { concept: "cfo", confidence: "inferred", bridge_kind: "naming_only" },
      },
      evidence_index: {
        "E:strong:abc:10-20:001": {
          concept: "peak_idx",
          source_type: "concept_occurrence",
          file_path: "/model/py.py",
          symbol: "peak_idx",
          strength: "strong",
        },
        "E:weak:def:30-40:001": {
          concept: "cfo",
          source_type: "naming_match",
          file_path: "/rtl/cfo.v",
          symbol: "cfo_sig",
          strength: "weak",
        },
        "E:strong:cfo_l5:5-15:001": {
          concept: "cfo",
          source_type: "concept_occurrence",
          file_path: "/model/py.py",
          symbol: "cfo",
          strength: "medium",
        },
      },
    },
    metadata: {
      schema_version: "p1b-project-run-metadata-0.1",
      command: "p1b-trace-project",
      project_root: "/tmp/test",
      concepts_processed: ["peak_idx", "cfo"],
      status: "ok",
      mapping_claims: 2,
      evidence_items: 7,
      diagnostics: 0,
    },
  };
}

function makeTestBundleWithPipeline(): ProjectBundle {
  const base = makeTestBundle();
  return {
    ...base,
    semantic_pipeline_view: {
      schema_version: "semantic-pipeline-view-0.1",
      project_id: "test_project",
      lanes: [
        {
          lane_id: "L5_fixedpoint",
          label: "L5 Fixed-Point Python Model",
          stage_id: "L5_fixedpoint",
          nodes: [
            { node_id: "E_L5_001", label: "compute_peak_idx", kind: "evidence", stage: "L5_fixedpoint", source_type: "concept_occurrence", strength: "strong", file_path: "src/python_model/L5_fixedpoint/test_l5.py", concept: "peak_idx" },
          ],
          edges: [],
        },
        {
          lane_id: "L6_resource_opt",
          label: "L6 Resource-Optimized Python Model",
          stage_id: "L6_resource_opt",
          nodes: [
            { node_id: "C_peak", label: "peak_idx", kind: "concept", confidence: "supported", stages_present: ["L5_fixedpoint", "L6_resource_opt", "RTL"], primary_stage: "L6_resource_opt" },
            { node_id: "E_L6_001", label: "optimized_peak_idx", kind: "evidence", stage: "L6_resource_opt", source_type: "concept_occurrence", strength: "strong", file_path: "src/python_model/L6_resource_opt/test_l6.py", concept: "peak_idx" },
          ],
          edges: [],
        },
        {
          lane_id: "RTL",
          label: "RTL Implementation",
          stage_id: "RTL",
          nodes: [
            { node_id: "CL_peak", label: "peak_idx → RTL", kind: "mapping_claim", confidence: "supported", concept: "peak_idx" },
            { node_id: "R1", label: "peak_sig", kind: "rtl_signal", confidence: "supported", file_path: "/rtl/peak.v" },
          ],
          edges: [],
        },
        {
          lane_id: "tests",
          label: "Tests & Verification",
          stage_id: "tests",
          nodes: [
            { node_id: "E_TEST_001", label: "test_peak_idx", kind: "evidence", stage: "tests", source_type: "test_evidence", strength: "medium", file_path: "tests/test_peak.py", concept: "peak_idx" },
          ],
          edges: [],
        },
      ],
      cross_stage_edges: [
        {
          edge_id: "E_peak_CL",
          from_lane: "L6_resource_opt",
          to_lane: "RTL",
          from_node_id: "C_peak",
          to_node_id: "CL_peak",
          edge_type: "has_claim",
          confidence: "supported",
          reason: "概念 'peak_idx' 通过 mapping claim 连接到 RTL 实现。",
          evidence_ids: ["E_L5_001", "E_L6_001"],
          source_files: ["src/python_model/L5_fixedpoint/test_l5.py", "src/python_model/L6_resource_opt/test_l6.py"],
        },
        {
          edge_id: "E_CL_R1",
          from_lane: "RTL",
          to_lane: "RTL",
          from_node_id: "CL_peak",
          to_node_id: "R1",
          edge_type: "realizes",
          confidence: "supported",
          reason: "Mapping claim 将概念 'peak_idx' 实现为 RTL 模块。",
          evidence_ids: ["E_RTL_001"],
          source_files: ["/rtl/peak.v"],
        },
      ],
      pipeline_summary: {
        concept_count_per_stage: { L5_fixedpoint: 0, L6_resource_opt: 1, RTL: 0, tests: 0 },
        evidence_count_per_stage: { L5_fixedpoint: 1, L6_resource_opt: 1, RTL: 0, tests: 1 },
        cross_stage_claim_count: 1,
        dataflow_edge_count: 2,
        concepts_with_full_pipeline: ["peak_idx"],
        concepts_with_gaps: [],
        total_nodes: 5,
        total_cross_stage_edges: 2,
      },
      uncertainty_flags: [],
      source_provenance: {
        summary_generated_from: ["project_understanding_graph.json", "project_understanding_index.json"],
        generation_timestamp: "2024-01-01T00:00:00Z",
        generator: "fpga_devmind.semantic_pipeline_view",
      },
    },
    semantic_summary: {
      schema_version: "project-semantic-summary-0.1",
      project_id: "test_project",
      project_root: "/tmp/test",
      project_kind_hint: "fpga_ofdm_sync",
      top_level_purpose: "Test project for T040",
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
          test_evidence_count: 1,
          confidence: "supported",
          limitations: [],
        },
      ],
      implementation_modules: [],
      dataflow_summary: { nodes: [], edges: [] },
      l5_l6_to_rtl_summary: {
        concept_mappings: [
          {
            concept: "peak_idx",
            l5_l6_sources: [{ file_path: "src/L5/test.py", symbol: "compute_peak_idx", evidence_id: "E1", strength: "strong" }],
            rtl_targets: [{ module_or_file: "/rtl/peak.v", symbol: "peak_sig", evidence_id: "E2", strength: "medium" }],
            claims: ["CL_peak"],
            mapping_confidence: "supported",
            mapping_reason: "calculation_role",
            gaps: [],
          },
        ],
        summary: {
          concepts_with_cross_stage_mapping: 1,
          concepts_missing_l5_l6: 0,
          concepts_missing_rtl: 0,
          inferred_only_mappings: 0,
        },
      },
      evidence_quality_summary: { strong_direct: 1, medium_structural: 0, weak_name_only: 0, inferred: 0 },
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
  };
}

describe("Agent Q&A", () => {
  it("returns suggested questions", () => {
    expect(SUGGESTED_QUESTIONS.length).toBeGreaterThanOrEqual(9);
  });

  it("handles null bundle", () => {
    const answer = answerQuestion(null, "test", null);
    expect(answer.answer).toContain("加载");
    expect(answer.conclusion).toBeTruthy();
    expect(answer.strength).toBe("none");
    expect(answer.limitations_summary).toBeTruthy();
  });

  it("answers project summary question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "这个项目整体实现了什么？", null);
    expect(answer.answer).toContain("test_project");
    expect(answer.answer).toContain("概念");
    expect(answer.referenced_nodes.length).toBeGreaterThan(0);
    expect(answer.conclusion).toContain("test_project");
    expect(answer.strength).toBeTruthy();
    expect(answer.limitations_summary).toBeTruthy();
  });

  it("answers concept mapping question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "peak_idx 是怎么映射到 RTL 的？", null);
    expect(answer.answer).toContain("peak_idx");
    expect(answer.answer).toContain("calculation_role");
    expect(answer.referenced_evidence.length).toBeGreaterThan(0);
    expect(answer.conclusion).toContain("peak_idx");
  });

  it("answers concept RTL question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "cfo 对应哪些 RTL？", null);
    expect(answer.answer).toContain("cfo");
    expect(answer.referenced_nodes.length).toBeGreaterThan(0);
    expect(answer.conclusion).toBeTruthy();
  });

  it("answers why inferred question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "cfo 为什么是 inferred？", null);
    expect(answer.answer).toContain("naming_only");
    expect(answer.referenced_evidence.length).toBeGreaterThan(0);
    expect(answer.limitations_summary).toBeTruthy();
  });

  it("answers shared RTL question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "哪些 RTL 文件承载了多个概念？", null);
    expect(answer.conclusion).toBeTruthy();
    expect(answer.strength).toBeTruthy();
  });

  it("answers key evidence question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "哪些证据最关键？", null);
    expect(answer.answer).toContain("strong");
    expect(answer.referenced_evidence.length).toBeGreaterThan(0);
    expect(answer.conclusion).toContain("strong");
  });

  it("answers uncertainty question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "哪些地方还不能确认？", null);
    expect(answer.answer).toContain("cfo");
    expect(answer.referenced_nodes.length).toBeGreaterThan(0);
    expect(answer.limitations_summary).toBeTruthy();
  });

  it("answers draw graph question", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "画出项目理解图", null);
    expect(answer.answer).toContain("Project Graph");
    expect(answer.strength).toBe("none");
  });

  it("answers explain selected node", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "解释当前选中节点", "C_peak");
    expect(answer.answer).toContain("peak_idx");
    expect(answer.conclusion).toContain("peak_idx");
  });

  it("handles explain with no selection", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "解释当前选中节点", null);
    expect(answer.answer).toContain("没有选中");
  });

  it("returns follow_up_questions", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "这个项目整体实现了什么？", null);
    expect(answer.follow_up_questions.length).toBeGreaterThan(0);
    expect(answer.follow_up_questions.length).toBeLessThanOrEqual(3);
  });

  it("falls back for unknown questions", () => {
    const bundle = makeTestBundle();
    const answer = answerQuestion(bundle, "什么是宇宙的终极答案？", null);
    expect(answer.answer).toContain("不完全理解");
    expect(answer.conclusion).toBeTruthy();
  });

  // T040.1: Pipeline / Dataflow Q&A tests
  it("answers pipeline path question", () => {
    const bundle = makeTestBundleWithPipeline();
    const answer = answerQuestion(bundle, "某个概念的 pipeline 路径是什么？", null);
    expect(answer.answer).toContain("peak_idx");
    expect(answer.answer).toContain("完整跨阶段证据链");
    expect(answer.conclusion).toContain("pipeline");
  });

  it("answers full pipeline concepts question", () => {
    const bundle = makeTestBundleWithPipeline();
    const answer = answerQuestion(bundle, "哪些概念跨了所有阶段？", null);
    expect(answer.answer).toContain("peak_idx");
    expect(answer.answer).toContain("完整");
    expect(answer.conclusion).toContain("跨了所有阶段");
  });

  it("answers dataflow question", () => {
    const bundle = makeTestBundleWithPipeline();
    const answer = answerQuestion(bundle, "dataflow 是怎样的？", null);
    expect(answer.answer).toContain("Pipeline Dataflow");
    expect(answer.answer).toContain("节点");
    expect(answer.conclusion).toContain("Dataflow");
  });

  it("answers which concepts have L5/L6 to RTL mapping", () => {
    const bundle = makeTestBundleWithPipeline();
    const answer = answerQuestion(bundle, "哪些概念完成了 L5/L6 到 RTL 的映射？", null);
    expect(answer.answer).toContain("peak_idx");
    expect(answer.conclusion).toContain("跨了所有阶段");
  });

  it("answers which concepts are missing RTL", () => {
    const bundle = makeTestBundleWithPipeline();
    const answer = answerQuestion(bundle, "哪些概念缺少 RTL？", null);
    expect(answer.answer).toContain("缺失 RTL");
    expect(answer.conclusion).toBeTruthy();
  });

  it("answers pipeline data provenance question", () => {
    const bundle = makeTestBundleWithPipeline();
    const answer = answerQuestion(bundle, "pipeline/dataflow 图的数据来自哪里？", null);
    expect(answer.answer).toContain("来源");
    expect(answer.conclusion).toBeTruthy();
  });
});
