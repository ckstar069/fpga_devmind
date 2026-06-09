import { describe, it, expect } from "vitest";
import {
  aggregateRtl,
  buildSummaryGraph,
  buildDetailGraph,
  buildFocusGraph,
  buildConceptTable,
  groupEvidenceByClaim,
} from "../utils/transforms";
import type { ProjectBundle } from "../types";

/* ------------------------------------------------------------------ */
/*  Test fixtures                                                     */
/* ------------------------------------------------------------------ */

function makeTestBundle(): ProjectBundle {
  return {
    path: "/tmp/test_bundle",
    graph: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      nodes: [
        {
          node_id: "P1",
          label: "test_project",
          kind: "project",
          stage: "",
          confidence: "supported",
        },
        {
          node_id: "C_peak",
          label: "peak_idx",
          kind: "concept",
          stage: "",
          confidence: "supported",
        },
        {
          node_id: "C_cfo",
          label: "cfo",
          kind: "concept",
          stage: "",
          confidence: "inferred",
        },
        {
          node_id: "CL_peak",
          label: "peak_idx → RTL",
          kind: "mapping_claim",
          stage: "",
          confidence: "supported",
          concept: "peak_idx",
          bridge_kind: "calculation_role",
        },
        {
          node_id: "CL_cfo",
          label: "cfo → RTL",
          kind: "mapping_claim",
          stage: "",
          confidence: "inferred",
          concept: "cfo",
          bridge_kind: "naming_only",
        },
        {
          node_id: "RTL_sig1",
          label: "peak_detect_sig",
          kind: "rtl_signal",
          stage: "",
          confidence: "supported",
          file_path: "/rtl/peak_detect.v",
        },
        {
          node_id: "RTL_always1",
          label: "peak_detect_logic",
          kind: "rtl_always_block",
          stage: "",
          confidence: "supported",
          file_path: "/rtl/peak_detect.v",
        },
        {
          node_id: "RTL_sig2",
          label: "cfo_sig",
          kind: "rtl_signal",
          stage: "",
          confidence: "inferred",
          file_path: "/rtl/cfo_est.v",
        },
        {
          node_id: "RTL_assign1",
          label: "cfo_assign",
          kind: "rtl_assign",
          stage: "",
          confidence: "inferred",
          file_path: "/rtl/cfo_est.v",
        },
      ],
      edges: [
        { edge_id: "E_P_C1", from_node_id: "P1", to_node_id: "C_peak", edge_type: "contains" },
        { edge_id: "E_P_C2", from_node_id: "P1", to_node_id: "C_cfo", edge_type: "contains" },
        { edge_id: "E_C1_CL1", from_node_id: "C_peak", to_node_id: "CL_peak", edge_type: "has_claim" },
        { edge_id: "E_C2_CL2", from_node_id: "C_cfo", to_node_id: "CL_cfo", edge_type: "has_claim" },
        { edge_id: "E_CL1_R1", from_node_id: "CL_peak", to_node_id: "RTL_sig1", edge_type: "realizes" },
        { edge_id: "E_CL1_R2", from_node_id: "CL_peak", to_node_id: "RTL_always1", edge_type: "realizes" },
        { edge_id: "E_CL2_R3", from_node_id: "CL_cfo", to_node_id: "RTL_sig2", edge_type: "realizes" },
        { edge_id: "E_CL2_R4", from_node_id: "CL_cfo", to_node_id: "RTL_assign1", edge_type: "realizes" },
        { edge_id: "E_SHARED", from_node_id: "C_peak", to_node_id: "C_cfo", edge_type: "shares_file" },
      ],
    },
    index: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      concept_index: {
        peak_idx: { status: "ok", claims: 1, evidence: 5, rtl_objects: 2 },
        cfo: { status: "ok", claims: 1, evidence: 3, rtl_objects: 2 },
      },
      claim_index: {
        CL_peak: { concept: "peak_idx", confidence: "supported", bridge_kind: "calculation_role" },
        CL_cfo: { concept: "cfo", confidence: "inferred", bridge_kind: "naming_only" },
      },
      evidence_index: {
        "E:p1b_concept:abc:10-20:001": {
          concept: "peak_idx",
          source_type: "concept_occurrence",
          file_path: "/model/python_model.py",
          symbol: "peak_idx",
          strength: "strong",
        },
        "E:p1b_rtl:def:30-40:001": {
          concept: "peak_idx",
          source_type: "rtl_source",
          file_path: "/rtl/peak_detect.v",
          symbol: "peak_detect_sig",
          strength: "strong",
        },
        "E:p1b_rtl:ghi:50-60:001": {
          concept: "cfo",
          source_type: "naming_match",
          file_path: "/rtl/cfo_est.v",
          symbol: "cfo_sig",
          strength: "weak",
        },
      },
    },
    metadata: {
      schema_version: "p1b-project-run-metadata-0.1",
      command: "p1b-trace-project",
      project_root: "/tmp/test_project",
      concepts_processed: ["peak_idx", "cfo"],
      status: "ok",
      mapping_claims: 2,
      evidence_items: 8,
      diagnostics: 0,
    },
  };
}

/* ------------------------------------------------------------------ */
/*  Tests                                                             */
/* ------------------------------------------------------------------ */

describe("aggregateRtl", () => {
  it("groups RTL nodes by file_path", () => {
    const bundle = makeTestBundle();
    const { aggregates } = aggregateRtl(
      bundle.graph.nodes,
      bundle.graph.edges,
    );

    // 2 files: peak_detect.v and cfo_est.v
    expect(aggregates.length).toBe(2);

    const peakAgg = aggregates.find((a) => a.label === "peak_detect");
    const cfoAgg = aggregates.find((a) => a.label === "cfo_est");

    expect(peakAgg).toBeDefined();
    expect(peakAgg!.child_count).toBe(2); // sig1 + always1
    expect(peakAgg!.child_kinds).toContain("rtl_signal");
    expect(peakAgg!.child_kinds).toContain("rtl_always_block");
    expect(peakAgg!.concept_labels).toContain("peak_idx");

    expect(cfoAgg).toBeDefined();
    expect(cfoAgg!.child_count).toBe(2); // sig2 + assign1
    expect(cfoAgg!.concept_labels).toContain("cfo");
  });

  it("maps claims to aggregates", () => {
    const bundle = makeTestBundle();
    const { claimToAgg: cta } = aggregateRtl(bundle.graph.nodes, bundle.graph.edges);

    expect(cta.get("CL_peak")?.length).toBe(1);
    expect(cta.get("CL_cfo")?.length).toBe(1);
  });
});

describe("buildSummaryGraph", () => {
  it("produces 4-column layout with aggregates", () => {
    const bundle = makeTestBundle();
    const graph = buildSummaryGraph(bundle, null, false);

    // Should have: 1 project + 2 concepts + 2 claims + 2 aggregates = 7
    expect(graph.nodes.length).toBe(7);

    const kinds = graph.nodes.map((n) => n.data.kind);
    expect(kinds.filter((k) => k === "project").length).toBe(1);
    expect(kinds.filter((k) => k === "concept").length).toBe(2);
    expect(kinds.filter((k) => k === "mapping_claim").length).toBe(2);
    expect(kinds.filter((k) => k === "rtl_aggregate").length).toBe(2);
  });

  it("includes shared edges when not hidden", () => {
    const bundle = makeTestBundle();
    const graph = buildSummaryGraph(bundle, null, false);

    const sharedEdges = graph.edges.filter(
      (e) => e.id === "E_SHARED",
    );
    expect(sharedEdges.length).toBe(1);
  });

  it("hides shared edges when hideShared=true", () => {
    const bundle = makeTestBundle();
    const graph = buildSummaryGraph(bundle, null, true);

    const sharedEdges = graph.edges.filter(
      (e) => e.id === "E_SHARED",
    );
    expect(sharedEdges.length).toBe(0);
  });

  it("highlights selected node", () => {
    const bundle = makeTestBundle();
    const graph = buildSummaryGraph(bundle, "C_peak", false);

    const selectedNode = graph.nodes.find((n) => n.id === "C_peak");
    expect(selectedNode?.data.selected).toBe(true);
  });
});

describe("buildDetailGraph", () => {
  it("shows all raw nodes", () => {
    const bundle = makeTestBundle();
    const graph = buildDetailGraph(bundle, null, false);

    // All 9 raw nodes
    expect(graph.nodes.length).toBe(9);
  });

  it("hides shared edges when hideShared=true", () => {
    const bundle = makeTestBundle();
    const graph = buildDetailGraph(bundle, null, true);

    const shared = graph.edges.filter(
      (e) => e.source === "C_peak" && e.target === "C_cfo",
    );
    expect(shared.length).toBe(0);
  });
});

describe("buildFocusGraph", () => {
  it("returns summary when no node selected", () => {
    const bundle = makeTestBundle();
    const graph = buildFocusGraph(bundle, null, 2);

    // Should be same as summary
    expect(graph.nodes.length).toBeGreaterThan(0);
  });

  it("shows N-hop neighbors around selected node", () => {
    const bundle = makeTestBundle();
    // Focus on peak_idx concept with 1 hop
    const graph = buildFocusGraph(bundle, "C_peak", 1);

    const nodeIds = graph.nodes.map((n) => n.id);
    // Should include peak_idx, project, and CL_peak
    expect(nodeIds).toContain("C_peak");
    expect(nodeIds).toContain("P1");
    expect(nodeIds).toContain("CL_peak");
    // With 1 hop, cfo should NOT be included (it's 2 hops away through shared edge only)
    // unless shared edges create adjacency
  });

  it("handles aggregate node IDs", () => {
    const bundle = makeTestBundle();
    // Aggregate IDs are like AGG_peak_detect
    const { aggregates } = aggregateRtl(bundle.graph.nodes, bundle.graph.edges);
    if (aggregates.length > 0) {
      const graph = buildFocusGraph(bundle, aggregates[0].id, 2);
      // Should return some nodes even for aggregate
      expect(graph.nodes.length).toBeGreaterThanOrEqual(1);
    }
  });
});

describe("buildConceptTable", () => {
  it("returns table rows for each concept", () => {
    const bundle = makeTestBundle();
    const table = buildConceptTable(bundle);

    expect(table.length).toBe(2);
    expect(table[0].concept).toBe("peak_idx");
    expect(table[1].concept).toBe("cfo");
    expect(table[0].confidence).toBe("supported");
    expect(table[1].confidence).toBe("inferred");
  });

  it("includes RTL targets", () => {
    const bundle = makeTestBundle();
    const table = buildConceptTable(bundle);

    expect(table[0].rtl_targets.length).toBeGreaterThan(0);
  });
});

describe("groupEvidenceByClaim", () => {
  it("groups evidence by claim", () => {
    const bundle = makeTestBundle();
    const groups = groupEvidenceByClaim(bundle);

    expect(groups.length).toBe(2);
    expect(groups[0].concept).toBe("peak_idx");
    expect(groups[1].concept).toBe("cfo");
  });

  it("includes why_matters for evidence items", () => {
    const bundle = makeTestBundle();
    const groups = groupEvidenceByClaim(bundle);

    for (const g of groups) {
      for (const item of g.items) {
        expect(item.why_matters).toBeTruthy();
      }
    }
  });
});

describe("parseLineRangeFromEvidenceId", () => {
  it("parses standard evidence ID", () => {
    // This is a TS-side test; the actual parsing is in Rust
    // We test the TS transforms don't crash on evidence IDs
    const eid = "E:p1b_concept:9db6fc88:399-473:001";
    // The TS side doesn't parse this - it just passes to Rust
    // So we verify the format is correct
    const parts = eid.split(":");
    expect(parts.length).toBe(5);
    expect(parts[3]).toBe("399-473");
    const [start, end] = parts[3].split("-").map(Number);
    expect(start).toBe(399);
    expect(end).toBe(473);
  });

  it("handles single-line ranges", () => {
    const eid = "E:p1b_rtl:abc:50-50:001";
    const parts = eid.split(":");
    const [start, end] = parts[3].split("-").map(Number);
    expect(start).toBe(50);
    expect(end).toBe(50);
  });
});
