/* ------------------------------------------------------------------ */
/*  T044: LLM Context Builder                                         */
/*  Builds bounded local context from bundle artifacts only.          */
/*  No file-system reads beyond existing bundle.  No API calls.       */
/* ------------------------------------------------------------------ */

import type { ProjectBundle } from "../types";
import { buildQuestionPreview } from "./audit";
import { buildSourceEvidencePack } from "./sourcePack";

export const LLM_CONTEXT_VERSION = "llm-context-bundle-0.1";

export interface LlmContextItem {
  id: string;
  kind:
    | "semantic_summary"
    | "pipeline_edge"
    | "concept_route"
    | "quality_status"
    | "limitation"
    | "node_fallback"
    | "discovery_eval";
  title: string;
  content_preview: string;
  artifact: string;
  evidence_ids: string[];
  source_files: string[];
  confidence?: string;
}

export interface LlmContextBundle {
  schema_version: string;
  question_preview: string;
  context_items: LlmContextItem[];
  artifacts_used: string[];
  evidence_ids: string[];
  source_files: string[];
  limitations: string[];
  token_estimate_rough: number;
}

const MAX_CONTEXT_ITEMS = 20;
const MAX_CONTENT_PREVIEW = 500;

function truncateContent(content: string, max = MAX_CONTENT_PREVIEW): string {
  if (content.length <= max) return content;
  return content.slice(0, max - 3) + "...";
}

function estimateTokensRough(text: string): number {
  return Math.ceil(text.length / 4);
}

/** Build a bounded LLM context bundle from local artifacts.
 *
 *  Does not read the filesystem beyond the bundle.
 *  Does not call any external API.
 *  Question preview is redacted if it contains sensitive-looking content.
 */
export function buildLlmContext(
  bundle: ProjectBundle | null,
  question: string,
  selectedNodeId: string | null
): LlmContextBundle {
  const preview = buildQuestionPreview(question);

  if (!bundle) {
    return {
      schema_version: LLM_CONTEXT_VERSION,
      question_preview: preview,
      context_items: [],
      artifacts_used: [],
      evidence_ids: [],
      source_files: [],
      limitations: ["No bundle loaded — cannot build LLM context."],
      token_estimate_rough: 0,
    };
  }

  const items: LlmContextItem[] = [];
  const evidenceSet = new Set<string>();
  const sourceSet = new Set<string>();
  const artifactSet = new Set<string>();
  const limitations: string[] = [];

  // ─── 1. Semantic summary ────────────────────────────────────────────
  const ss = bundle.semantic_summary;
  if (ss) {
    artifactSet.add("project_semantic_summary.json");
    items.push({
      id: "semantic-summary-purpose",
      kind: "semantic_summary",
      title: `Project: ${ss.project_id}`,
      content_preview: truncateContent(ss.top_level_purpose),
      artifact: "project_semantic_summary.json",
      evidence_ids: [],
      source_files: [],
      confidence: "supported",
    });

    if (ss.core_concepts && ss.core_concepts.length > 0) {
      const conceptsText = ss.core_concepts
        .map((c: any) => `- ${c.display_name}: ${c.role_in_project} (${c.confidence})`)
        .join("\n");
      items.push({
        id: "semantic-summary-concepts",
        kind: "semantic_summary",
        title: "Core Concepts",
        content_preview: truncateContent(conceptsText),
        artifact: "project_semantic_summary.json",
        evidence_ids: [],
        source_files: [],
        confidence: "supported",
      });
    }

    if (ss.pipeline_stages && ss.pipeline_stages.length > 0) {
      const stagesText = ss.pipeline_stages
        .map((s) => `- ${s.label}: ${s.role}`)
        .join("\n");
      items.push({
        id: "semantic-summary-stages",
        kind: "semantic_summary",
        title: "Pipeline Stages",
        content_preview: truncateContent(stagesText),
        artifact: "project_semantic_summary.json",
        evidence_ids: [],
        source_files: [],
        confidence: "supported",
      });
    }
  }

  // ─── 2. Source evidence pack ────────────────────────────────────────
  const sourcePack = buildSourceEvidencePack(bundle, question, selectedNodeId);
  if (sourcePack.artifacts_used.length > 0) {
    sourcePack.artifacts_used.forEach((a) => artifactSet.add(a));
    sourcePack.evidence_ids.forEach((e) => evidenceSet.add(e));
    sourcePack.source_files.forEach((s) => sourceSet.add(s));
    limitations.push(...sourcePack.limitations);

    for (const item of sourcePack.items.slice(0, 12)) {
      const content =
        item.kind === "concept"
          ? `Concept ${item.label}: confidence=${item.confidence}, evidence=${item.evidence_ids.length}, sources=${item.source_files.length}`
          : item.kind === "edge"
          ? `Edge ${item.label}: confidence=${item.confidence}, evidence=${item.evidence_ids.length}`
          : `Node ${item.label}: kind=${item.kind}, confidence=${item.confidence}`;

      items.push({
        id: item.id,
        kind: item.kind === "node" ? "node_fallback" : (item.kind as any),
        title: item.label,
        content_preview: truncateContent(content),
        artifact: item.artifact,
        evidence_ids: item.evidence_ids,
        source_files: item.source_files,
        confidence: item.confidence,
      });
    }
  }

  // ─── 3. Pipeline view edges ────────────────────────────────────────
  const pv = bundle.semantic_pipeline_view;
  if (pv) {
    artifactSet.add("semantic_pipeline_view.json");

    const edges = pv.cross_stage_edges.slice(0, 5);
    for (const edge of edges) {
      items.push({
        id: edge.edge_id,
        kind: "pipeline_edge",
        title: `${edge.from_lane} → ${edge.to_lane}`,
        content_preview: truncateContent(
          `Type: ${edge.edge_type}, Confidence: ${edge.confidence}, Reason: ${edge.reason || "N/A"}`
        ),
        artifact: "semantic_pipeline_view.json",
        evidence_ids: edge.evidence_ids,
        source_files: edge.source_files,
        confidence: edge.confidence,
      });
      edge.evidence_ids.forEach((e) => evidenceSet.add(e));
      edge.source_files.forEach((s) => sourceSet.add(s));
    }

    // Pipeline summary
    const summary = pv.pipeline_summary;
    if (summary) {
      items.push({
        id: "pipeline-summary",
        kind: "pipeline_edge",
        title: "Pipeline Summary",
        content_preview: truncateContent(
          `Nodes: ${summary.total_nodes}, Cross-stage edges: ${summary.total_cross_stage_edges}, ` +
          `Full-pipeline concepts: ${summary.concepts_with_full_pipeline.length}, ` +
          `Gaps: ${summary.concepts_with_gaps.length}`
        ),
        artifact: "semantic_pipeline_view.json",
        evidence_ids: [],
        source_files: [],
        confidence: "supported",
      });
    }
  }

  // ─── 4. Navigation index quality ────────────────────────────────────
  const nav = bundle.agent_navigation_index;
  if (nav) {
    artifactSet.add("agent_navigation_index.json");

    const qs = nav.quality_status;
    if (qs) {
      const qualityText = qs.golden_spec_used
        ? `Golden spec: P=${(qs.selected_precision_like * 100).toFixed(0)}% R=${(qs.selected_recall_like * 100).toFixed(0)}% (core ${qs.matched_core_count}/${qs.matched_core_count + qs.missed_core_count})`
        : "No golden spec used in this bundle.";

      items.push({
        id: "nav-quality",
        kind: "quality_status",
        title: "Quality Status",
        content_preview: truncateContent(qualityText),
        artifact: "agent_navigation_index.json",
        evidence_ids: [],
        source_files: [],
        confidence: qs.golden_spec_used ? "supported" : "unknown",
      });
    }
  }

  // ─── 5. Discovery eval result ──────────────────────────────────────
  const evalResult = bundle.discovery_eval_result;
  if (evalResult) {
    artifactSet.add("discovery_eval_result.json");
    const ev = evalResult as any;
    const evalText =
      `Precision: ${ev.precision_like !== undefined ? (ev.precision_like * 100).toFixed(0) : "N/A"}%, ` +
      `Recall: ${ev.recall_like !== undefined ? (ev.recall_like * 100).toFixed(0) : "N/A"}%, ` +
      `Matched core: ${ev.matched_core?.length ?? 0}/${ev.golden_core_count ?? "N/A"}`;

    items.push({
      id: "discovery-eval",
      kind: "discovery_eval",
      title: "Discovery Eval",
      content_preview: truncateContent(evalText),
      artifact: "discovery_eval_result.json",
      evidence_ids: [],
      source_files: [],
      confidence: "supported",
    });
  }

  // ─── 6. Cap items ──────────────────────────────────────────────────
  if (items.length > MAX_CONTEXT_ITEMS) {
    limitations.push(`Context capped from ${items.length} to ${MAX_CONTEXT_ITEMS} items.`);
  }
  const finalItems = items.slice(0, MAX_CONTEXT_ITEMS);

  // Token estimate: all preview text + metadata
  const allText = finalItems.map((i) => i.content_preview).join("\n") + preview;
  const tokenEstimate = estimateTokensRough(allText);

  return {
    schema_version: LLM_CONTEXT_VERSION,
    question_preview: preview,
    context_items: finalItems,
    artifacts_used: [...artifactSet],
    evidence_ids: [...evidenceSet],
    source_files: [...sourceSet],
    limitations,
    token_estimate_rough: tokenEstimate,
  };
}
