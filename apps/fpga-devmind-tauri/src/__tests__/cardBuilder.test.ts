import { describe, it, expect } from "vitest";
import { buildUnderstandingCard } from "../utils/cardBuilder";
import type { ProjectBundle } from "../types";

function makeTestBundle(): ProjectBundle {
  return {
    path: "/tmp/test_bundle",
    graph: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      nodes: [
        { node_id: "P1", label: "test_project", kind: "project", stage: "", confidence: "supported" },
        { node_id: "C1", label: "peak_idx", kind: "concept", stage: "", confidence: "supported" },
        { node_id: "CL1", label: "peak_idx → RTL", kind: "mapping_claim", stage: "", confidence: "supported", concept: "peak_idx", bridge_kind: "calculation_role" },
        { node_id: "R1", label: "peak_sig", kind: "rtl_signal", stage: "", confidence: "supported", file_path: "/rtl/peak.v" },
        { node_id: "R2", label: "peak_logic", kind: "rtl_always_block", stage: "", confidence: "supported", file_path: "/rtl/peak.v" },
      ],
      edges: [
        { edge_id: "E1", from_node_id: "P1", to_node_id: "C1", edge_type: "contains" },
        { edge_id: "E2", from_node_id: "C1", to_node_id: "CL1", edge_type: "has_claim" },
        { edge_id: "E3", from_node_id: "CL1", to_node_id: "R1", edge_type: "realizes" },
        { edge_id: "E4", from_node_id: "CL1", to_node_id: "R2", edge_type: "realizes" },
      ],
    },
    index: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      concept_index: {
        peak_idx: { status: "ok", claims: 1, evidence: 3, rtl_objects: 2 },
      },
      claim_index: {
        CL1: { concept: "peak_idx", confidence: "supported", bridge_kind: "calculation_role" },
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
          concept: "peak_idx",
          source_type: "naming_match",
          symbol: "peak_sig",
          strength: "weak",
        },
      },
    },
    metadata: {
      schema_version: "p1b-project-run-metadata-0.1",
      command: "p1b-trace-project",
      project_root: "/tmp/test",
      concepts_processed: ["peak_idx"],
      status: "ok",
      mapping_claims: 1,
      evidence_items: 3,
      diagnostics: 0,
    },
  };
}

describe("buildUnderstandingCard", () => {
  it("returns null for unknown node", () => {
    const bundle = makeTestBundle();
    const card = buildUnderstandingCard(bundle, "NONEXISTENT");
    expect(card).toBeNull();
  });

  it("builds project card with concepts", () => {
    const bundle = makeTestBundle();
    const card = buildUnderstandingCard(bundle, "P1");
    expect(card).not.toBeNull();
    expect(card!.kind).toBe("project");
    expect(card!.related_concepts.length).toBe(1);
    expect(card!.data_provenance).toBeDefined();
    expect(card!.data_provenance.source_node_kind).toBe("project");
  });

  it("builds concept card with claims and RTL", () => {
    const bundle = makeTestBundle();
    const card = buildUnderstandingCard(bundle, "C1");
    expect(card).not.toBeNull();
    expect(card!.kind).toBe("concept");
    expect(card!.related_claims.length).toBe(1);
    expect(card!.related_rtl.length).toBeGreaterThan(0);
    expect(card!.evidence_count).toBe(3);
    expect(card!.top_evidence.length).toBeGreaterThan(0);
    expect(card!.data_provenance.raw_rtl_node_count).toBeGreaterThan(0);
  });

  it("builds claim card with bridge analysis", () => {
    const bundle = makeTestBundle();
    const card = buildUnderstandingCard(bundle, "CL1");
    expect(card).not.toBeNull();
    expect(card!.kind).toBe("mapping_claim");
    expect(card!.summary).toContain("calculation_role");
    expect(card!.related_concepts.length).toBe(1);
  });

  it("includes data_provenance for all node types", () => {
    const bundle = makeTestBundle();
    for (const nodeId of ["P1", "C1", "CL1"]) {
      const card = buildUnderstandingCard(bundle, nodeId);
      expect(card!.data_provenance).toBeDefined();
      expect(card!.data_provenance.source_node_id).toBe(nodeId);
    }
  });

  it("includes why_connected for concept node", () => {
    const bundle = makeTestBundle();
    const card = buildUnderstandingCard(bundle, "C1");
    expect(card!.why_connected.length).toBeGreaterThan(0);
    const hasClaimEdge = card!.why_connected.some(
      (wc) => wc.edge_type === "has_claim",
    );
    expect(hasClaimEdge).toBe(true);
  });

  it("includes traceable_evidence for concept node", () => {
    const bundle = makeTestBundle();
    const card = buildUnderstandingCard(bundle, "C1");
    expect(card!.traceable_evidence.length).toBeGreaterThan(0);
    // Should contain actual evidence IDs
    expect(card!.traceable_evidence[0]).toContain("E:");
  });
});
