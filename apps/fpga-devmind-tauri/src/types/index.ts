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
  /** T038: Optional semantic summary */
  semantic_summary?: ProjectSemanticSummary;
  /** T038.1: Discovery eval result loaded from JSON */
  discovery_eval_result?: EvalResult | unknown;
  /** T038.1: Concept candidates loaded from JSON */
  concept_candidates?: ConceptCandidateV2[] | unknown;
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
  // V2 fields (optional for backward compat)
  aliases?: string[];
  selection_reason?: string;
  confidence_explanation?: string;
  why_core_or_secondary?: string;
  // V2.1 fields (T037)
  test_evidence_status?: string;
  test_files_scanned?: number;
  matched_test_symbols?: string[];
  missing_reason?: string;
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

/* ------------------------------------------------------------------ */
/*  T036: Discovery Quality, Golden Spec, Agent Q&A                  */
/* ------------------------------------------------------------------ */

/** V2 discovery result from Python backend */
export interface DiscoveryResultV2 {
  schema_version: string;
  project_id: string;
  candidates: ConceptCandidateV2[];
  mode: string;
  total_raw_symbols: number;
  total_after_filter: number;
}

export interface ConceptCandidateV2 {
  name: string;
  aliases: string[];
  source_sections: string[];
  occurrence_count: number;
  confidence: string;
  reason: string;
  representative_files: string[];
  likely_stage: string;
  semantic_role: string;
  score_breakdown: ScoreBreakdown;
  selection_reason: string;
  compound_source: string;
}

export interface ScoreBreakdown {
  cross_stage_bonus: number;
  key_position_bonus: number;
  domain_term_bonus: number;
  test_presence_bonus: number;
  occurrence_score: number;
  alias_group_bonus: number;
  generic_penalty: number;
  total: number;
}

/** Golden benchmark spec */
export interface GoldenSpec {
  schema_version: string;
  project_id: string;
  expected_core_concepts: GoldenConcept[];
  expected_secondary_concepts: GoldenConcept[];
  excluded_terms: Array<{ term: string; reason: string }>;
}

export interface GoldenConcept {
  concept: string;
  aliases: string[];
  why_core: string;
  expected_l5_l6_files: string[];
  expected_rtl_files: string[];
  semantic_role: string;
}

/** Evaluation result */
export interface EvalResult {
  project_id: string;
  golden_core_count: number;
  matched_core: string[];
  missed_core: string[];
  unexpected_selected: string[];
  precision_like: number;
  recall_like: number;
}

/** Evidence chain V2 per concept */
export interface EvidenceChainV2 {
  l5_l6_evidence: EvidenceChainItem[];
  claims: Array<{ claim_id: string; bridge_kind: string; confidence: string }>;
  rtl_evidence: EvidenceChainItem[];
  test_evidence: EvidenceChainItem[];
  missing: string[];
  aliases: string[];
  selection_reason: string;
  confidence_explanation: string;
  why_core_or_secondary: string;
}

/* ------------------------------------------------------------------ */
/*  T038: Project Semantic Summary                                    */
/* ------------------------------------------------------------------ */

export interface ProjectSemanticSummary {
  schema_version: string;
  project_id: string;
  project_root: string;
  project_kind_hint: string;
  top_level_purpose: string;
  pipeline_stages: PipelineStage[];
  core_concepts: CoreConcept[];
  implementation_modules: ImplementationModule[];
  dataflow_summary: DataflowSummary;
  l5_l6_to_rtl_summary: L5L6ToRtlSummary;
  evidence_quality_summary: EvidenceQualitySummary;
  uncertainty_summary: UncertaintySummary;
  test_coverage_summary: TestCoverageSummary;
  source_provenance: SourceProvenance;
}

export interface PipelineStage {
  stage_id: string;
  label: string;
  role: string;
  source_files: string[];
  related_concepts: string[];
  related_rtl_modules: string[];
  confidence: string;
  evidence_ids: string[];
}

export interface CoreConcept {
  canonical_name: string;
  display_name: string;
  category: string;
  role_in_project: string;
  why_selected: string;
  aliases: string[];
  l5_l6_evidence_count: number;
  rtl_evidence_count: number;
  test_evidence_count: number;
  confidence: string;
  limitations: string[];
}

export interface ImplementationModule {
  module_or_file: string;
  role_hint: string;
  concepts_realized: string[];
  claims: string[];
  strong_evidence_count: number;
  medium_evidence_count: number;
  weak_evidence_count: number;
  is_shared_by_multiple_concepts: boolean;
}

export interface DataflowSummary {
  nodes: DataflowNode[];
  edges: DataflowEdge[];
}

export interface DataflowNode {
  id: string;
  label: string;
  kind: string;
}

export interface DataflowEdge {
  from: string;
  to: string;
  type: string;
  confidence: string;
  inferred: boolean;
}

export interface EvidenceQualitySummary {
  strong_direct: number;
  medium_structural: number;
  weak_name_only: number;
  inferred: number;
}

export interface UncertaintySummary {
  inferred_claims: string[];
  weak_only_links: string[];
  naming_only_links: string[];
  missing_l5_l6: string[];
  missing_rtl: string[];
  missing_test_evidence: string[];
}

export interface TestCoverageSummary {
  test_files_present: boolean;
  total_test_files: number;
  concepts_with_test_match: number;
  concepts_without_test_match: number;
  per_concept: PerConceptTestCoverage[];
}

export interface PerConceptTestCoverage {
  concept: string;
  test_files_present: boolean;
  matched_test_symbols: string[];
  matched_test_names: string[];
  test_evidence_status: string;
}

export interface L5L6ToRtlSummary {
  concept_mappings: ConceptMapping[];
  summary: {
    concepts_with_cross_stage_mapping: number;
    concepts_missing_l5_l6: number;
    concepts_missing_rtl: number;
    inferred_only_mappings: number;
  };
}

export interface ConceptMapping {
  concept: string;
  l5_l6_sources: EvidenceSource[];
  rtl_targets: RtlTarget[];
  claims: string[];
  mapping_confidence: string;
  mapping_reason: string;
  gaps: string[];
}

export interface EvidenceSource {
  file_path: string;
  symbol: string;
  evidence_id: string;
  strength: string;
}

export interface RtlTarget {
  module_or_file: string;
  symbol: string;
  evidence_id: string;
  strength: string;
}

export interface SourceProvenance {
  summary_generated_from: string[];
  generation_timestamp: string;
  generator: string;
}
