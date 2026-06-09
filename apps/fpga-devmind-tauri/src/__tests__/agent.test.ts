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

describe("Agent Q&A", () => {
  it("returns 9 suggested questions", () => {
    expect(SUGGESTED_QUESTIONS.length).toBe(9);
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
});
