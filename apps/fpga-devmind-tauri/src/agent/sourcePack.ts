/* ------------------------------------------------------------------ */
/*  T044: Source Evidence Pack                                        */
/*  Collects relevant concept, edge, evidence, and source files       */
/*  for a given question.  No file-system reads, no API calls.        */
/* ------------------------------------------------------------------ */

import type { ProjectBundle, AgentConceptRoute, AgentEdgeRoute, GraphNode } from "../types";
import { buildQuestionPreview } from "./audit";

export const SOURCE_EVIDENCE_PACK_VERSION = "source-evidence-pack-0.1";

export interface SourceEvidenceItem {
  kind: "concept" | "edge" | "node" | "limitation";
  id: string;
  label: string;
  artifact: string;
  evidence_ids: string[];
  source_files: string[];
  confidence?: string;
}

export interface SourceEvidencePack {
  schema_version: string;
  question_preview: string;
  selected_node_id: string | null;
  matched_concepts: string[];
  matched_edges: string[];
  items: SourceEvidenceItem[];
  evidence_ids: string[];
  source_files: string[];
  artifacts_used: string[];
  limitations: string[];
}

/** Build a source-evidence pack for the current question and selection.
 *
 *  Priority:
 *  1. agent_navigation_index (concept_routes, edge_routes)
 *  2. semantic_pipeline_view (cross_stage_edges)
 *  3. graph nodes (by selectedNodeId or question keyword match)
 *  4. Fallback for old bundles.
 */
export function buildSourceEvidencePack(
  bundle: ProjectBundle | null,
  question: string,
  selectedNodeId: string | null
): SourceEvidencePack {
  const preview = buildQuestionPreview(question);
  if (!bundle) {
    return {
      schema_version: SOURCE_EVIDENCE_PACK_VERSION,
      question_preview: preview,
      selected_node_id: null,
      matched_concepts: [],
      matched_edges: [],
      items: [],
      evidence_ids: [],
      source_files: [],
      artifacts_used: [],
      limitations: ["No bundle loaded — cannot build evidence pack."],
    };
  }

  const items: SourceEvidenceItem[] = [];
  const evidenceSet = new Set<string>();
  const sourceSet = new Set<string>();
  const artifactSet = new Set<string>();
  const limitations: string[] = [];
  const matchedConcepts: string[] = [];
  const matchedEdges: string[] = [];

  // ─── 1. Navigation index routes ─────────────────────────────────────
  const nav = bundle.agent_navigation_index;
  if (nav) {
    artifactSet.add("agent_navigation_index.json");

    // Match concept routes by question keywords
    const qLower = question.toLowerCase();
    const matchedConceptRoutes = nav.concept_routes.filter((r: AgentConceptRoute) => {
      if (selectedNodeId && r.node_id === selectedNodeId) return true;
      return qLower.includes(r.concept.toLowerCase());
    });

    for (const route of matchedConceptRoutes.slice(0, 8)) {
      items.push({
        kind: "concept",
        id: route.node_id,
        label: route.concept,
        artifact: "agent_navigation_index.json",
        evidence_ids: [...route.evidence_ids],
        source_files: [...route.source_files],
        confidence: route.confidence,
      });
      route.evidence_ids.forEach((e) => evidenceSet.add(e));
      route.source_files.forEach((s) => sourceSet.add(s));
      matchedConcepts.push(route.concept);
    }

    // Match edge routes
    const matchedEdgeRoutes = nav.edge_routes.filter((e: AgentEdgeRoute) => {
      if (selectedNodeId && (e.from_node_id === selectedNodeId || e.to_node_id === selectedNodeId)) return true;
      return false;
    });

    for (const edge of matchedEdgeRoutes.slice(0, 6)) {
      items.push({
        kind: "edge",
        id: edge.edge_id,
        label: `${edge.from_lane} → ${edge.to_lane} (${edge.edge_type})`,
        artifact: "agent_navigation_index.json",
        evidence_ids: [...edge.evidence_ids],
        source_files: [...edge.source_files],
        confidence: edge.confidence,
      });
      edge.evidence_ids.forEach((e) => evidenceSet.add(e));
      edge.source_files.forEach((s) => sourceSet.add(s));
      matchedEdges.push(edge.edge_id);
    }
  }

  // ─── 2. Semantic pipeline view ──────────────────────────────────────
  const pv = bundle.semantic_pipeline_view;
  if (pv) {
    artifactSet.add("semantic_pipeline_view.json");

    for (const edge of pv.cross_stage_edges.slice(0, 6)) {
      if (selectedNodeId && (edge.from_node_id === selectedNodeId || edge.to_node_id === selectedNodeId)) {
        items.push({
          kind: "edge",
          id: edge.edge_id,
          label: `${edge.from_lane} → ${edge.to_lane}`,
          artifact: "semantic_pipeline_view.json",
          evidence_ids: [...edge.evidence_ids],
          source_files: [...edge.source_files],
          confidence: edge.confidence,
        });
        edge.evidence_ids.forEach((e) => evidenceSet.add(e));
        edge.source_files.forEach((s) => sourceSet.add(s));
      }
    }
  }

  // ─── 3. Selected node from graph ────────────────────────────────────
  if (selectedNodeId && bundle.graph) {
    artifactSet.add("project_understanding_graph.json");
    const node = bundle.graph.nodes.find((n: GraphNode) => n.node_id === selectedNodeId);
    if (node) {
      items.push({
        kind: "node",
        id: node.node_id,
        label: node.label,
        artifact: "project_understanding_graph.json",
        evidence_ids: node.evidence_ids || [],
        source_files: node.file_path ? [node.file_path] : [],
        confidence: node.confidence,
      });
      (node.evidence_ids || []).forEach((e) => evidenceSet.add(e));
      if (node.file_path) sourceSet.add(node.file_path);
    }
  }

  // ─── 4. Fallback: keyword-match from graph nodes ────────────────────
  if (items.length === 0 && bundle.graph) {
    artifactSet.add("project_understanding_graph.json");
    limitations.push("No agent_navigation_index — using fallback keyword matching from graph.");

    const qLower = question.toLowerCase();
    const matchedNodes = bundle.graph.nodes.filter((n: GraphNode) => {
      return (
        qLower.includes(n.label.toLowerCase()) ||
        (n.concept && qLower.includes(n.concept.toLowerCase()))
      );
    });

    for (const node of matchedNodes.slice(0, 6)) {
      items.push({
        kind: "node",
        id: node.node_id,
        label: node.label,
        artifact: "project_understanding_graph.json",
        evidence_ids: node.evidence_ids || [],
        source_files: node.file_path ? [node.file_path] : [],
        confidence: node.confidence,
      });
      (node.evidence_ids || []).forEach((e) => evidenceSet.add(e));
      if (node.file_path) sourceSet.add(node.file_path);
    }
  }

  // ─── 5. Quality / limitations from nav ──────────────────────────────
  if (nav) {
    nav.limitations.forEach((lim) => {
      limitations.push(`[${lim.category}] ${lim.item}: ${lim.reason}`);
    });
  }

  if (!nav && !pv) {
    limitations.push("Old bundle without navigation index or pipeline view — context may be incomplete.");
  }

  return {
    schema_version: SOURCE_EVIDENCE_PACK_VERSION,
    question_preview: preview,
    selected_node_id: selectedNodeId,
    matched_concepts: matchedConcepts,
    matched_edges: matchedEdges,
    items,
    evidence_ids: [...evidenceSet],
    source_files: [...sourceSet],
    artifacts_used: [...artifactSet],
    limitations,
  };
}
