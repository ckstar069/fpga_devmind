/* ------------------------------------------------------------------ */
/*  Artifact JSON schema types                                        */
/* ------------------------------------------------------------------ */

export interface GraphNode {
  node_id: string;
  label: string;
  kind: string;
  stage?: string;
  confidence?: string;
  concept?: string;
  bridge_kind?: string;
  evidence_ids?: string[];
  file_path?: string;
  [key: string]: unknown;
}

export interface GraphEdge {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: string;
  confidence?: string;
  [key: string]: unknown;
}

export interface ProjectGraph {
  schema_version: string;
  project_id: string;
  project_root?: string;
  concepts?: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  grounding_diagnostics?: unknown[];
  uncertainty_notes?: unknown[];
}

export interface EvidenceEntry {
  concept?: string;
  source_type: string;
  file_path?: string;
  symbol?: string;
  strength?: string;
  line_start?: number;
  line_end?: number;
  [key: string]: unknown;
}

export interface ConceptInfo {
  status: string;
  claims: number;
  evidence: number;
  rtl_objects: number;
}

export interface ClaimInfo {
  concept: string;
  confidence: string;
  bridge_kind: string;
}

export interface ProjectIndex {
  schema_version: string;
  project_id: string;
  concept_index: Record<string, ConceptInfo>;
  claim_index: Record<string, ClaimInfo>;
  evidence_index: Record<string, EvidenceEntry>;
}

export interface RunMetadata {
  schema_version: string;
  command: string;
  project_root: string;
  concepts_requested?: string[];
  concepts_processed?: string[];
  status: string;
  mapping_claims: number;
  evidence_items: number;
  diagnostics: number;
  elapsed_seconds?: number;
  [key: string]: unknown;
}

export interface ProjectBundle {
  path: string;
  graph: ProjectGraph;
  index: ProjectIndex;
  metadata: RunMetadata;
}

export interface ProjectBundleSummary {
  path: string;
  project_id: string;
  project_root: string;
  concepts: string[];
  mapping_claims: number;
  evidence_items: number;
  diagnostics: number;
  node_count: number;
  edge_count: number;
  status: string;
}

/* ------------------------------------------------------------------ */
/*  Understanding Card                                                */
/* ------------------------------------------------------------------ */

export interface UnderstandingCard {
  node_id: string;
  label: string;
  kind: string;
  confidence: string;
  summary: string;
  role_in_project: string;
  related_concepts: { id: string; label: string; confidence: string }[];
  related_claims: { id: string; label: string; concept: string; confidence: string; bridge_kind: string }[];
  related_rtl: { id: string; label: string; file_path?: string; kind: string }[];
  evidence_count: number;
  top_evidence: { id: string; source_type: string; file_path?: string; symbol?: string; strength?: string }[];
  limitations: string[];
  next_steps: string[];
  implementation_path: string;
}

/* ------------------------------------------------------------------ */
/*  Graph view model                                                  */
/* ------------------------------------------------------------------ */

export type GraphMode = "summary" | "detail" | "focus";

export interface RtlAggregate {
  id: string;
  label: string;
  file_path: string;
  child_count: number;
  child_kinds: string[];
  concept_labels: string[];
  confidence: string;
}

export interface FlowGraph {
  nodes: import("@xyflow/react").Node[];
  edges: import("@xyflow/react").Edge[];
}

/* ------------------------------------------------------------------ */
/*  Evidence                                                          */
/* ------------------------------------------------------------------ */

export interface EvidenceGroup {
  claim_id: string;
  claim_label: string;
  concept: string;
  confidence: string;
  bridge_kind: string;
  explanation: string;
  items: {
    id: string;
    source_type: string;
    file_path?: string;
    symbol?: string;
    strength?: string;
    why_matters: string;
  }[];
}

/* ------------------------------------------------------------------ */
/*  Agent Q&A                                                         */
/* ------------------------------------------------------------------ */

export interface AgentAnswer {
  question: string;
  answer: string;
  referenced_nodes: string[];
  referenced_claims: string[];
  referenced_evidence: string[];
  follow_up_questions: string[];
}

/* ------------------------------------------------------------------ */
/*  Overview Concept Table                                            */
/* ------------------------------------------------------------------ */

export interface ConceptTableRow {
  concept: string;
  concept_id: string;
  l5_l6_role: string;
  claim_label: string;
  claim_id: string;
  rtl_targets: string[];
  confidence: string;
  evidence_count: number;
  limitations: string;
}
