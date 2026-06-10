/* ------------------------------------------------------------------ */
/*  T042: Agent Provider Boundary                                     */
/*  Deterministic / Offline Mock / External Disabled                  */
/* ------------------------------------------------------------------ */

import type { ProjectBundle, AgentAnswer } from "../types";

/** Provider kind enum — extensible for future real LLM providers */
export type AgentProviderKind = "deterministic" | "offline_mock" | "external_disabled";

/** Capabilities of a provider */
export interface ProviderCapabilities {
  enabled: boolean;
  network_allowed: boolean;
  requires_api_key: boolean;
  label: string;
  description: string;
}

/** Request to run an agent answer */
export interface AgentRunRequest {
  question: string;
  selectedNodeId: string | null;
  bundle: ProjectBundle | null;
  providerKind: AgentProviderKind;
}

/** A single trace step — auditable, NOT chain-of-thought */
export interface AgentTraceStep {
  step_id: string;
  kind: string;
  description: string;
  input_artifacts: string[];
  output_summary: string;
}

/** Full run trace for display and audit */
export interface AgentRunTrace {
  trace_id: string;
  provider_kind: AgentProviderKind;
  question: string;
  matched_intent: string;
  steps: AgentTraceStep[];
  artifacts_used: string[];
  evidence_ids: string[];
  source_files: string[];
  limitations: string[];
  generated_at: string;
}

/** Minimal policy result reference (imported lazily to avoid cycles) */
export interface AgentRunPolicyResult {
  allowed: boolean;
  provider_kind: AgentProviderKind;
  reason: string;
  network_allowed: boolean;
  requires_api_key: boolean;
  external_calls_allowed: boolean;
  secret_storage_allowed: boolean;
  policy_version: string;
  limitations: string[];
}

/** Minimal audit event reference (imported lazily to avoid cycles) */
export interface AgentRunAuditEvent {
  event_id: string;
  timestamp: string;
  provider_kind: AgentProviderKind;
  question_preview: string;
  policy_allowed: boolean;
  policy_reason: string;
  external_calls_made: boolean;
  network_allowed: boolean;
  artifacts_used: string[];
  trace_id: string;
  limitations: string[];
  policy_version: string;
}

/** Result of an agent run */
export interface AgentRunResult {
  answer: AgentAnswer;
  provider: AgentProviderKind;
  trace: AgentRunTrace;
  artifacts_used: string[];
  evidence_ids: string[];
  limitations: string[];
  external_calls_made: boolean;
  policy_result: AgentRunPolicyResult;
  audit_event: AgentRunAuditEvent;
}

/** Provider interface */
export interface AgentProvider {
  kind: AgentProviderKind;
  capabilities: ProviderCapabilities;
  run(request: AgentRunRequest): AgentRunResult;
}

/** Map of all known providers by kind */
export const PROVIDER_CAPABILITIES: Record<AgentProviderKind, ProviderCapabilities> = {
  deterministic: {
    enabled: true,
    network_allowed: false,
    requires_api_key: false,
    label: "确定性 Agent",
    description: "基于预定义规则匹配和本地 artifacts 回答，不调用外部 LLM/API",
  },
  offline_mock: {
    enabled: true,
    network_allowed: false,
    requires_api_key: false,
    label: "Offline Mock Agent",
    description: "基于本地 artifacts 模拟多步 Agent 导航，用于验证 provider 生命周期",
  },
  external_disabled: {
    enabled: false,
    network_allowed: false,
    requires_api_key: true,
    label: "External Provider (Disabled)",
    description: "外部 LLM provider 在 T042 中被故意禁用，等待 T043 安全评估后启用",
  },
};

/** Generate a trace ID */
export function generateTraceId(): string {
  const now = Date.now();
  const rand = Math.floor(Math.random() * 10000)
    .toString(16)
    .padStart(4, "0");
  return `trace-${now}-${rand}`;
}

/** Collect artifacts used from a bundle */
export function collectArtifactsUsed(bundle: ProjectBundle | null): string[] {
  if (!bundle) return [];
  const artifacts: string[] = [];
  // graph 和 index 是基础 artifact
  if (bundle.graph) artifacts.push("project_understanding_graph.json");
  if (bundle.index) artifacts.push("project_understanding_index.json");
  if (bundle.semantic_summary) artifacts.push("project_semantic_summary.json");
  if (bundle.semantic_pipeline_view) artifacts.push("semantic_pipeline_view.json");
  if (bundle.agent_navigation_index) artifacts.push("agent_navigation_index.json");
  if (bundle.discovery_eval_result) artifacts.push("discovery_eval_result.json");
  if (bundle.concept_candidates) artifacts.push("concept_candidates.json");
  return artifacts;
}
