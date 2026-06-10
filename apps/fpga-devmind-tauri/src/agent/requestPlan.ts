/* ------------------------------------------------------------------ */
/*  T044: Dry-run External Request Plan                               */
/*  Builds a preview of what an external request WOULD look like,     */
/*  but is explicitly blocked by policy.  No API calls.  No secrets.  */
/* ------------------------------------------------------------------ */

import type { ProjectBundle } from "../types";
import { evaluateProviderPolicy } from "./policy";
import { buildLlmContext, type LlmContextBundle } from "./contextBuilder";

export const REQUEST_PLAN_VERSION = "dry-run-request-plan-0.1";

export interface ExternalRequestPlan {
  schema_version: string;
  dry_run: true;
  policy_allowed: false;
  blocked_reason: string;
  provider_kind: "external_disabled";
  policy_version: string;
  limitations: string[];

  /** Question preview (redacted if sensitive) */
  question_preview: string;
  selected_node_id: string | null;

  /** The LLM context bundle that WOULD be sent */
  context_bundle: LlmContextBundle;

  /** What the request body WOULD contain (for developer review) */
  hypothetical_request_preview: {
    model_name: string;
    purpose: string;
    message_count_estimate: number;
    total_tokens_estimate: number;
    system_prompt_preview: string;
    user_prompt_preview: string;
    context_items_summary: string[];
  };

  /** Artifacts used in context assembly */
  artifacts_used: string[];
  evidence_ids: string[];
  source_files: string[];
}

/** Build a dry-run external request plan.
 *
 *  This function NEVER calls an external API.
 *  It ONLY assembles local context and produces a preview.
 *  The plan is always blocked by policy (external_disabled).
 */
export function buildDryRunExternalRequestPlan(
  bundle: ProjectBundle | null,
  question: string,
  selectedNodeId: string | null
): ExternalRequestPlan {
  // T043: Evaluate policy — always blocked for external_disabled
  const policyResult = evaluateProviderPolicy({
    provider_kind: "external_disabled",
    question,
  });

  // T044: Build bounded LLM context from local artifacts
  const contextBundle = buildLlmContext(bundle, question, selectedNodeId);

  const contextItems = contextBundle.context_items;

  // Hypothetical request preview — for developer review only
  const systemPrompt = buildHypotheticalSystemPrompt(contextBundle);
  const userPrompt = buildHypotheticalUserPrompt(contextBundle, question);

  return {
    schema_version: REQUEST_PLAN_VERSION,
    dry_run: true,
    policy_allowed: false,
    blocked_reason:
      "外部 provider 被 T043 安全策略禁用，dry-run 仅用于展示可能发送的上下文",
    provider_kind: "external_disabled",
    policy_version: policyResult.policy_version,
    limitations: [
      "Dry-run only — 不会发送任何网络请求",
      "外部 provider 未启用，当前回答由本地确定性 provider 生成",
      "上下文数据仅限本地 bundle 中的 artifacts，不包含实时搜索或外部知识",
      ...policyResult.limitations,
      ...contextBundle.limitations,
    ],
    question_preview: contextBundle.question_preview,
    selected_node_id: selectedNodeId,
    context_bundle: contextBundle,
    hypothetical_request_preview: {
      model_name: "external-llm-placeholder",
      purpose: "Semantic Q&A over FPGA project bundle",
      message_count_estimate: 2, // system + user
      total_tokens_estimate: contextBundle.token_estimate_rough,
      system_prompt_preview: truncatePreview(systemPrompt, 300),
      user_prompt_preview: truncatePreview(userPrompt, 300),
      context_items_summary: contextItems.map(
        (item) => `${item.kind}: ${item.title} (${item.content_preview.length} chars)`
      ),
    },
    artifacts_used: contextBundle.artifacts_used,
    evidence_ids: contextBundle.evidence_ids,
    source_files: contextBundle.source_files,
  };
}

function truncatePreview(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max - 3) + "...";
}

function buildHypotheticalSystemPrompt(contextBundle: LlmContextBundle): string {
  const items = contextBundle.context_items;
  const summaries = items
    .filter((i) => i.kind === "semantic_summary")
    .map((i) => i.content_preview);

  return [
    "You are an FPGA design analysis assistant. Answer based ONLY on the provided project context.",
    "Project: " + (summaries[0] || "Unknown FPGA project"),
    "Available context items: " + items.length,
    "Artifacts: " + contextBundle.artifacts_used.join(", "),
    "Limitations: " + contextBundle.limitations.join("; "),
  ].join("\n");
}

function buildHypotheticalUserPrompt(contextBundle: LlmContextBundle, question: string): string {
  const items = contextBundle.context_items;
  const contextBody = items
    .map((item) => `[${item.kind}] ${item.title}:\n${item.content_preview}`)
    .join("\n\n");

  return [
    "Question: " + question,
    "",
    "Project context:",
    contextBody || "(No context items available)",
    "",
    "Please answer based on the above context only.",
  ].join("\n");
}
