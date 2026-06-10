/* ------------------------------------------------------------------ */
/*  T042: External Disabled Provider Stub                             */
/*  Intentionally disabled — no API key, no network, no real calls    */
/* ------------------------------------------------------------------ */

import type { AgentProvider, AgentRunRequest, AgentRunResult } from "./providers";
import { generateTraceId, PROVIDER_CAPABILITIES } from "./providers";

export const externalDisabledProvider: AgentProvider = {
  kind: "external_disabled",
  capabilities: PROVIDER_CAPABILITIES.external_disabled,

  run(request: AgentRunRequest): AgentRunResult {
    const traceId = generateTraceId();

    const answer = {
      question: request.question,
      answer: `⚠️ External provider is intentionally disabled in T042.\n\n` +
        `当前版本（T042）不提供外部 LLM provider 接入。\n` +
        `原因：\n` +
        `• 外部 provider 需要 API key 安全策略评估（T043）\n` +
        `• 需要 provider 调用审计和风险审查\n` +
        `• 当前优先保证离线可验证性\n\n` +
        `请使用以下可用 provider：\n` +
        `• 确定性 Agent — 基于预定义规则匹配（推荐）\n` +
        `• Offline Mock Agent — 模拟多步导航（实验性）`,
      referenced_nodes: [],
      referenced_claims: [],
      referenced_evidence: [],
      follow_up_questions: [
        "从哪里开始理解这个项目？",
        "这个项目整体实现了什么？",
        "哪些概念达到了 supported 置信度？",
      ],
      conclusion: "External provider disabled in T042.",
      strength: "none",
      limitations_summary: "外部 LLM provider 在 T042 中被故意禁用。",
    };

    const trace = {
      trace_id: traceId,
      provider_kind: "external_disabled" as const,
      question: request.question,
      matched_intent: "external_disabled",
      steps: [
        {
          step_id: "step-1",
          kind: "check_provider_status",
          description: "External provider checked: marked as disabled",
          input_artifacts: [],
          output_summary: "Provider disabled, returning fallback message",
        },
      ],
      artifacts_used: [],
      evidence_ids: [],
      source_files: [],
      limitations: [
        "external_provider_disabled: 外部 LLM provider 在 T042 中被故意禁用。",
        "等待 T043 安全评估后才可能启用。",
      ],
      generated_at: new Date().toISOString(),
    };

    return {
      answer,
      provider: "external_disabled",
      trace,
      artifacts_used: [],
      evidence_ids: [],
      limitations: trace.limitations,
      external_calls_made: false,
    };
  },
};
