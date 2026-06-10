/* ------------------------------------------------------------------ */
/*  T042: Deterministic Provider                                      */
/*  Wraps existing answerQuestion() with AgentRunResult / trace       */
/* ------------------------------------------------------------------ */

import type { AgentProvider, AgentRunRequest, AgentRunResult, AgentTraceStep, AgentRunPolicyResult, AgentRunAuditEvent } from "./providers";
import { generateTraceId, collectArtifactsUsed, PROVIDER_CAPABILITIES } from "./providers";
import { answerQuestion } from "../utils/agent";

export const deterministicProvider: AgentProvider = {
  kind: "deterministic",
  capabilities: PROVIDER_CAPABILITIES.deterministic,

  run(request: AgentRunRequest): AgentRunResult {
    const startTime = Date.now();
    const traceId = generateTraceId();

    const steps: AgentTraceStep[] = [];
    const bundle = request.bundle;

    // Step 1: route question
    const question = request.question.trim();
    let matchedIntent = "unknown";

    // Simple intent detection matching answerQuestion internal patterns
    if (question.includes("从哪里开始") || question.includes("推荐") || question.includes("先看")) {
      matchedIntent = "navigation_help";
    } else if (question.includes("下一步") || question.includes("点哪里")) {
      matchedIntent = "next_steps";
    } else if (question.includes("噪声") || question.includes("假阳性")) {
      matchedIntent = "noise_concepts";
    } else if (question.includes("完整证据链")) {
      matchedIntent = "full_evidence_chain";
    } else if (question.includes("precision") || question.includes("recall") || question.includes("精确率") || question.includes("召回率")) {
      matchedIntent = "quality_metrics";
    } else if (question.includes("golden")) {
      matchedIntent = "golden_spec";
    } else if (question.includes("整体") || question.includes("实现")) {
      matchedIntent = "project_summary";
    } else if (question.includes("pipeline") || question.includes("阶段")) {
      matchedIntent = "pipeline_stages";
    } else if (question.includes("概念") || question.includes("识别")) {
      matchedIntent = "discovered_concepts";
    } else if (question.includes("edge") || question.includes("边")) {
      matchedIntent = "edge_evidence";
    }

    steps.push({
      step_id: "step-1",
      kind: "route_question",
      description: `Matched intent: ${matchedIntent}`,
      input_artifacts: [],
      output_summary: `Detected intent for "${question}"`,
    });

    // Step 2: inspect artifacts
    const artifactsUsed = collectArtifactsUsed(bundle);
    const availableNav = bundle?.agent_navigation_index ? "available" : "missing";
    const availablePipeline = bundle?.semantic_pipeline_view ? "available" : "missing";
    const availableSummary = bundle?.semantic_summary ? "available" : "missing";

    steps.push({
      step_id: "step-2",
      kind: "inspect_artifacts",
      description: `Checked bundle artifacts: nav=${availableNav}, pipeline=${availablePipeline}, summary=${availableSummary}`,
      input_artifacts: artifactsUsed,
      output_summary: `${artifactsUsed.length} artifacts available`,
    });

    // Step 3: call existing answerQuestion
    const answer = answerQuestion(bundle, question, request.selectedNodeId);

    steps.push({
      step_id: "step-3",
      kind: "compose_answer",
      description: "Composed deterministic answer using pre-defined pattern matching",
      input_artifacts: artifactsUsed,
      output_summary: `Answer generated: ${answer.conclusion.slice(0, 60)}${answer.conclusion.length > 60 ? "..." : ""}`,
    });

    const trace = {
      trace_id: traceId,
      provider_kind: "deterministic" as const,
      question,
      matched_intent: matchedIntent,
      steps,
      artifacts_used: artifactsUsed,
      evidence_ids: answer.referenced_evidence,
      source_files: [],
      limitations: answer.limitations_summary ? [answer.limitations_summary] : [],
      generated_at: new Date(startTime).toISOString(),
    };

    const policy_result: AgentRunPolicyResult = {
      allowed: true,
      provider_kind: "deterministic",
      reason: "确定性 provider 基于本地规则匹配，不调用外部 API，允许运行",
      network_allowed: false,
      requires_api_key: false,
      external_calls_allowed: false,
      secret_storage_allowed: false,
      policy_version: "t043.0",
      limitations: [
        "确定性 provider 仅执行预定义规则匹配，不提供语义推理",
      ],
    };

    const base: Omit<AgentRunResult, "policy_result" | "audit_event"> = {
      answer,
      provider: "deterministic",
      trace,
      artifacts_used: artifactsUsed,
      evidence_ids: answer.referenced_evidence,
      limitations: answer.limitations_summary ? [answer.limitations_summary] : [],
      external_calls_made: false,
    };

    const audit_event: AgentRunAuditEvent = {
      event_id: `audit-${Date.now()}-${Math.floor(Math.random() * 10000).toString(16).padStart(4, "0")}`,
      timestamp: new Date().toISOString(),
      provider_kind: "deterministic",
      question_preview: question.length <= 80 ? question : question.slice(0, 77) + "...",
      policy_allowed: policy_result.allowed,
      policy_reason: policy_result.reason,
      external_calls_made: false,
      network_allowed: false,
      artifacts_used: artifactsUsed,
      trace_id: trace.trace_id,
      limitations: [...base.limitations, ...policy_result.limitations],
      policy_version: policy_result.policy_version,
    };

    return { ...base, policy_result, audit_event };
  },
};
