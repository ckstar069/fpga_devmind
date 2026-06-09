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
  l5_count?: number;
  l6_count?: number;
  test_count?: number;
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
  evidence_chain?: Record<string, EvidenceChain>;
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
  /** T034: Data provenance */
  data_provenance: {
    source_node_id: string;
    source_node_kind: string;
    raw_rtl_node_count: number;
    edge_types: string[];
  };
  /** T034: Why connected to neighbors */
  why_connected: { neighbor_id: string; edge_type: string; explanation: string }[];
  /** T034: Clickable evidence IDs */
  traceable_evidence: string[];
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
  /** T034: Evidence-chain fields */
  conclusion: string;
  strength: string;
  limitations_summary: string;
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
  l5_count: number;
  l6_count: number;
  rtl_ev_count: number;
  test_count: number;
  uncertainty: string;
}

/* ------------------------------------------------------------------ */
/*  T035: Evidence Chain, Concept Discovery, Project List            */
/* ------------------------------------------------------------------ */

/** Stage-categorized evidence chain for a concept */
export interface EvidenceChain {
  l5_l6_evidence: EvidenceChainItem[];
  claims: { claim_id: string; bridge_kind: string; confidence: string }[];
  rtl_evidence: EvidenceChainItem[];
  test_evidence: EvidenceChainItem[];
  missing: string[];
}

export interface EvidenceChainItem {
  evidence_id: string;
  file_path: string;
  symbol: string;
  strength: string;
}

/** Auto-discovered concept candidate */
export interface ConceptCandidate {
  name: string;
  source_sections: string[];
  occurrence_count: number;
  confidence: string;
  reason: string;
  representative_files: string[];
  likely_stage: string;
}

/** FPGA project info from list_fpga_projects */
export interface ProjectInfo {
  project_id: string;
  path: string;
  has_L5: boolean;
  has_L6: boolean;
  has_RTL: boolean;
  has_tests: boolean;
}
