import type {
  ProjectBundle,
  GraphNode,
  GraphEdge,
  RtlAggregate,
  FlowGraph,
  ConceptTableRow,
  EvidenceGroup,
} from "../types";
import type { Node, Edge } from "@xyflow/react";

/* ================================================================== */
/*  Constants                                                         */
/* ================================================================== */

const KIND_COLORS: Record<string, string> = {
  project: "#6366f1",
  concept: "#3b82f6",
  mapping_claim: "#10b981",
  rtl_aggregate: "#f59e0b",
  rtl_module: "#f59e0b",
  rtl_signal: "#d97706",
  rtl_always_block: "#ea580c",
  rtl_assign: "#dc2626",
  rtl_comment: "#94a3b8",
  rtl_file: "#8b5cf6",
};

export function nodeColor(kind: string): string {
  return KIND_COLORS[kind] ?? "#94a3b8";
}

export function nodeKindLabel(kind: string): string {
  const map: Record<string, string> = {
    project: "Project",
    concept: "Concept",
    mapping_claim: "Claim",
    rtl_aggregate: "RTL Aggregate",
    rtl_module: "Module",
    rtl_signal: "Signal",
    rtl_always_block: "Always",
    rtl_assign: "Assign",
    rtl_comment: "Comment",
    rtl_file: "File",
  };
  return map[kind] ?? kind;
}

/* ================================================================== */
/*  RTL Aggregation                                                   */
/* ================================================================== */

export function aggregateRtl(nodes: GraphNode[], edges: GraphEdge[]): {
  aggregates: RtlAggregate[];
  claimToAgg: Map<string, string[]>;
} {
  const rtlNodes = nodes.filter((n) => n.kind.startsWith("rtl_"));
  const byFile = new Map<string, GraphNode[]>();

  for (const n of rtlNodes) {
    const fp = n.file_path ?? "unknown";
    if (!byFile.has(fp)) byFile.set(fp, []);
    byFile.get(fp)!.push(n);
  }

  const aggregates: RtlAggregate[] = [];
  const claimToAgg = new Map<string, string[]>();

  for (const [fp, children] of byFile) {
    const basename = fp.split("/").pop()?.replace(/\.[^.]+$/, "") ?? fp;
    const aggId = `AGG_${basename.replace(/[^a-zA-Z0-9_]/g, "_")}`;
    const kinds = [...new Set(children.map((c) => c.kind))];
    const confidences = children.map((c) => c.confidence).filter(Boolean);
    const bestConf = confidences.includes("supported")
      ? "supported"
      : confidences.includes("inferred")
        ? "inferred"
        : "unknown";

    // Which concepts are linked via edges?
    const childIds = new Set(children.map((c) => c.node_id));
    const parentClaims = new Set<string>();
    for (const e of edges) {
      if (e.edge_type === "realizes" && childIds.has(e.to_node_id)) {
        parentClaims.add(e.from_node_id);
      }
    }

    // Find concept labels for those claims
    const conceptLabels = new Set<string>();
    const nodeMap = new Map(nodes.map((n) => [n.node_id, n]));
    for (const claimId of parentClaims) {
      const claimNode = nodeMap.get(claimId);
      if (claimNode?.concept) conceptLabels.add(claimNode.concept);
    }

    aggregates.push({
      id: aggId,
      label: basename,
      file_path: fp,
      child_count: children.length,
      child_kinds: kinds,
      concept_labels: [...conceptLabels],
      confidence: bestConf,
    });

    for (const claimId of parentClaims) {
      if (!claimToAgg.has(claimId)) claimToAgg.set(claimId, []);
      claimToAgg.get(claimId)!.push(aggId);
    }
  }

  return { aggregates, claimToAgg };
}

/* ================================================================== */
/*  Graph Mode Builders                                               */
/* ================================================================== */

function makeNode(
  id: string,
  label: string,
  kind: string,
  confidence: string,
  col: number,
  row: number,
  selected: boolean,
): Node {
  const COL_X = [80, 300, 520, 740];
  const ROW_GAP = 100;
  return {
    id,
    type: "custom",
    position: { x: COL_X[col] ?? 300, y: 40 + row * ROW_GAP },
    data: { label, kind, confidence, selected },
  };
}

function makeEdge(
  id: string,
  source: string,
  target: string,
  edgeType: string,
  _confidence?: string,
  hideLabel = false,
): Edge {
  const isShared =
    edgeType === "shares_file" || edgeType === "shares_rtl_object";
  return {
    id,
    source,
    target,
    animated: false,
    style: {
      stroke: isShared ? "#f59e0b66" : "#475569",
      strokeWidth: isShared ? 1 : 1.5,
      strokeDasharray: isShared ? "6 4" : undefined,
      opacity: isShared ? 0.5 : 1,
    },
    label: hideLabel || isShared ? "" : edgeType === "has_claim" ? "" : edgeType,
    labelStyle: { fontSize: 9, fill: "#64748b" },
  };
}

/** Summary graph: Project → Concepts → Claims → RTL Aggregates */
export function buildSummaryGraph(
  bundle: ProjectBundle,
  selectedNodeId: string | null,
  hideShared: boolean,
): FlowGraph {
  const { nodes: rawNodes, edges: rawEdges } = bundle.graph;
  const { aggregates, claimToAgg } = aggregateRtl(rawNodes, rawEdges);

  const flowNodes: Node[] = [];
  const flowEdges: Edge[] = [];

  // Column 0: Project
  const project = rawNodes.find((n) => n.kind === "project");
  const concepts = rawNodes.filter((n) => n.kind === "concept");
  const claims = rawNodes.filter((n) => n.kind === "mapping_claim");

  if (project) {
    flowNodes.push(
      makeNode(
        project.node_id,
        project.label,
        "project",
        project.confidence ?? "supported",
        0,
        1,
        project.node_id === selectedNodeId,
      ),
    );
  }

  // Column 1: Concepts (sorted)
  const conceptOrder = bundle.metadata.concepts_processed ?? concepts.map((c) => c.label);
  const sortedConcepts = [...concepts].sort((a, b) => {
    const ia = conceptOrder.indexOf(a.label);
    const ib = conceptOrder.indexOf(b.label);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  sortedConcepts.forEach((c, i) => {
    flowNodes.push(
      makeNode(c.node_id, c.label, "concept", c.confidence ?? "unknown", 1, i, c.node_id === selectedNodeId),
    );
    if (project) {
      flowEdges.push(makeEdge(`e_${project.node_id}_${c.node_id}`, project.node_id, c.node_id, "contains"));
    }
  });

  // Column 2: Claims
  claims.forEach((cl, i) => {
    flowNodes.push(
      makeNode(cl.node_id, cl.label, "mapping_claim", cl.confidence ?? "unknown", 2, i, cl.node_id === selectedNodeId),
    );
    const parentConcept = sortedConcepts.find((c) => c.label === cl.concept);
    if (parentConcept) {
      flowEdges.push(
        makeEdge(`e_${parentConcept.node_id}_${cl.node_id}`, parentConcept.node_id, cl.node_id, "has_claim"),
      );
    }
  });

  // Column 3: RTL Aggregates
  aggregates.forEach((agg, i) => {
    flowNodes.push(
      makeNode(agg.id, agg.label, "rtl_aggregate", agg.confidence, 3, i, agg.id === selectedNodeId),
    );
  });

  // Claim → Aggregate edges
  for (const [claimId, aggIds] of claimToAgg) {
    for (const aggId of aggIds) {
      flowEdges.push(
        makeEdge(`e_${claimId}_${aggId}`, claimId, aggId, "realizes"),
      );
    }
  }

  // Shared edges between concepts
  if (!hideShared) {
    const conceptNodeIds = new Set(sortedConcepts.map((c) => c.node_id));
    for (const e of rawEdges) {
      if (
        (e.edge_type === "shares_file" || e.edge_type === "shares_rtl_object") &&
        conceptNodeIds.has(e.from_node_id) &&
        conceptNodeIds.has(e.to_node_id)
      ) {
        flowEdges.push(
          makeEdge(e.edge_id, e.from_node_id, e.to_node_id, e.edge_type, e.confidence, true),
        );
      }
    }
  }

  return { nodes: flowNodes, edges: flowEdges };
}

/** Detail graph: show all raw nodes */
export function buildDetailGraph(
  bundle: ProjectBundle,
  selectedNodeId: string | null,
  hideShared: boolean,
): FlowGraph {
  const { nodes: rawNodes, edges: rawEdges } = bundle.graph;
  const flowNodes: Node[] = [];
  const flowEdges: Edge[] = [];

  // Simple column by kind
  const kindCol: Record<string, number> = {
    project: 0,
    concept: 1,
    mapping_claim: 2,
    rtl_module: 3,
    rtl_signal: 4,
    rtl_always_block: 4,
    rtl_assign: 4,
    rtl_comment: 4,
  };

  const colCounts: Record<number, number> = {};
  for (const n of rawNodes) {
    const col = kindCol[n.kind] ?? 3;
    const row = colCounts[col] ?? 0;
    colCounts[col] = row + 1;
    flowNodes.push(
      makeNode(n.node_id, n.label, n.kind, n.confidence ?? "unknown", col, row, n.node_id === selectedNodeId),
    );
  }

  for (const e of rawEdges) {
    if (hideShared && (e.edge_type === "shares_file" || e.edge_type === "shares_rtl_object")) {
      continue;
    }
    flowEdges.push(
      makeEdge(e.edge_id, e.from_node_id, e.to_node_id, e.edge_type, e.confidence),
    );
  }

  return { nodes: flowNodes, edges: flowEdges };
}

/** Focus graph: only selected node + 1-2 hop neighbors */
export function buildFocusGraph(
  bundle: ProjectBundle,
  selectedNodeId: string | null,
  hops: number,
): FlowGraph {
  if (!selectedNodeId) return buildSummaryGraph(bundle, null, false);

  const { nodes: rawNodes, edges: rawEdges } = bundle.graph;
  const { claimToAgg } = aggregateRtl(rawNodes, rawEdges);

  // Build adjacency using summary graph
  const summary = buildSummaryGraph(bundle, selectedNodeId, true);

  // BFS from selected node
  const adj = new Map<string, string[]>();
  for (const e of summary.edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    if (!adj.has(e.target)) adj.set(e.target, []);
    adj.get(e.source)!.push(e.target);
    adj.get(e.target)!.push(e.source);
  }

  const visited = new Set<string>();
  const queue: [string, number][] = [[selectedNodeId, 0]];
  visited.add(selectedNodeId);

  while (queue.length > 0) {
    const [nodeId, dist] = queue.shift()!;
    if (dist >= hops) continue;
    for (const neighbor of adj.get(nodeId) ?? []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([neighbor, dist + 1]);
      }
    }
  }

  // Also include aggregates connected to visible claims
  for (const [claimId, aggIds] of claimToAgg) {
    if (visited.has(claimId)) {
      for (const aid of aggIds) visited.add(aid);
    }
  }

  const flowNodes = summary.nodes.filter((n) => visited.has(n.id)).map((n) => ({
    ...n,
    data: { ...n.data, selected: n.id === selectedNodeId },
  }));

  const flowEdges = summary.edges.filter(
    (e) => visited.has(e.source) && visited.has(e.target),
  );

  return { nodes: flowNodes, edges: flowEdges };
}

/* ================================================================== */
/*  Concept Table (Overview)                                          */
/* ================================================================== */

export function buildConceptTable(bundle: ProjectBundle): ConceptTableRow[] {
  const { nodes, edges } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");
  const claims = nodes.filter((n) => n.kind === "mapping_claim");
  const { aggregates, claimToAgg } = aggregateRtl(nodes, edges);

  return concepts.map((c) => {
    const claim = claims.find((cl) => cl.concept === c.label);
    const conceptInfo = bundle.index.concept_index[c.label];
    const evCount = conceptInfo?.evidence ?? 0;

    // Find RTL targets
    const rtlTargets: string[] = [];
    if (claim) {
      const aggIds = claimToAgg.get(claim.node_id) ?? [];
      for (const aid of aggIds) {
        const agg = aggregates.find((a) => a.id === aid);
        if (agg) rtlTargets.push(agg.label);
      }
    }

    // L5/L6 role
    const evEntries = Object.entries(bundle.index.evidence_index)
      .filter(([, v]) => v.concept === c.label);
    const l5Sources = evEntries.filter(([, v]) =>
      v.source_type === "concept_occurrence" && v.file_path?.includes("python_model")
    );
    const l5_l6_role = l5Sources.length > 0
      ? `在 L5/L6 固定点模型中实现 (${l5Sources.length} 处)`
      : "无直接 L5/L6 代码引用";

    // Limitations
    const conf = c.confidence ?? "unknown";
    const bridge = claim?.bridge_kind ?? "?";
    let limitations = "";
    if (conf === "unknown") limitations = "置信度未知，缺乏证据";
    else if (conf === "inferred") {
      if (bridge === "naming_only") limitations = "仅命名匹配，无结构/行为验证";
      else limitations = "推断性映射，需进一步验证";
    } else {
      limitations = "—";
    }

    // T035: Stage-categorized evidence counts
    const l5 = evEntries.filter(([, v]) => v.file_path?.includes("L5_fixedpoint")).length;
    const l6 = evEntries.filter(([, v]) => v.file_path?.includes("L6_resource_opt")).length;
    const rtl = evEntries.filter(([, v]) => v.source_type === "rtl_source").length;
    const test = evEntries.filter(([, v]) => v.file_path?.includes("test") || v.source_type?.startsWith("test_")).length;

    // Build uncertainty text
    let uncertainty = "";
    if (conf === "unknown") uncertainty = "无映射";
    else if (conf === "inferred") {
      const namingOnly = claims.find((cl: any) => cl.concept === c.label && cl.bridge_kind === "naming_only");
      uncertainty = namingOnly ? "仅命名匹配" : "推断性";
    }
    if (rtl === 0) uncertainty += (uncertainty ? "、" : "") + "无RTL证据";
    if (l5 + l6 === 0) uncertainty += (uncertainty ? "、" : "") + "无L5/L6证据";

    return {
      concept: c.label,
      concept_id: c.node_id,
      l5_l6_role,
      claim_label: claim?.label ?? "—",
      claim_id: claim?.node_id ?? "",
      rtl_targets: rtlTargets,
      confidence: conf,
      evidence_count: evCount,
      limitations,
      l5_count: l5,
      l6_count: l6,
      rtl_ev_count: rtl,
      test_count: test,
      uncertainty,
    };
  });
}

/* ================================================================== */
/*  Evidence grouping with explanations                               */
/* ================================================================== */

export function groupEvidenceByClaim(bundle: ProjectBundle): EvidenceGroup[] {
  const claims = bundle.graph.nodes.filter((n) => n.kind === "mapping_claim");
  const groups: EvidenceGroup[] = [];

  for (const claim of claims) {
    const concept = claim.concept ?? "?";
    const bridge = claim.bridge_kind ?? "?";
    const conf = claim.confidence ?? "unknown";

    // Build explanation
    let explanation = "";
    if (conf === "supported") {
      explanation = `Claim "${claim.label}" 声明概念 ${concept} 在 RTL 中有对应实现。`;
      if (bridge === "calculation_role") {
        explanation += " 通过计算角色分析确认：L5/L6 中的数学运算在 RTL 中有对应逻辑。";
      } else if (bridge === "naming_plus_structure") {
        explanation += " 通过命名匹配和结构对比确认。";
      } else {
        explanation += ` bridge_kind=${bridge}。`;
      }
    } else if (conf === "inferred") {
      explanation = `Claim "${claim.label}" 声明概念 ${concept} 可能在 RTL 中有对应，但置信度为 inferred。`;
      if (bridge === "naming_only") {
        explanation += " 仅通过命名匹配推断，没有结构或行为层面的验证。这可能产生假阳性。";
      } else {
        explanation += ` bridge_kind=${bridge}。需要更多证据确认。`;
      }
    } else {
      explanation = `Claim "${claim.label}" 置信度未知，暂无法确认概念 ${concept} 的 RTL 映射。`;
    }

    // Gather evidence
    const evEntries = Object.entries(bundle.index.evidence_index)
      .filter(([, v]) => v.concept === concept);

    const items = evEntries.map(([id, ev]) => {
      const isStrong = ev.strength === "strong";
      const isMedium = ev.strength === "medium";
      const isNaming = ev.source_type === "naming_match" || ev.file_path?.includes("comment");

      let why = "";
      if (ev.source_type === "concept_occurrence") {
        why = isStrong
          ? "强证据：L5/L6 代码中直接使用了该概念的计算逻辑。"
          : "概念出现：L5/L6 中包含相关引用。";
      } else if (ev.source_type === "rtl_source") {
        why = isStrong || isMedium
          ? "RTL 源码证据：RTL 代码中存在对应实现。"
          : "弱 RTL 证据：仅存在间接关联。";
      } else if (isNaming) {
        why = "⚠ 弱证据：仅命名匹配，不能作为强确认依据。";
      } else {
        why = `${ev.source_type} 类型证据。`;
      }

      return {
        id,
        source_type: ev.source_type,
        file_path: ev.file_path,
        symbol: ev.symbol,
        strength: ev.strength,
        why_matters: why,
      };
    });

    groups.push({
      claim_id: claim.node_id,
      claim_label: claim.label,
      concept,
      confidence: conf,
      bridge_kind: bridge,
      explanation,
      items,
    });
  }

  return groups;
}
