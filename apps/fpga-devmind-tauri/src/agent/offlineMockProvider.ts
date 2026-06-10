/* ------------------------------------------------------------------ */
/*  T042: Offline Mock Provider                                       */
/*  Simulates multi-step agent navigation using local artifacts only  */
/*  No network, no API key, no external LLM calls                     */
/* ------------------------------------------------------------------ */

import type { AgentProvider, AgentRunRequest, AgentRunResult, AgentTraceStep, AgentRunPolicyResult, AgentRunAuditEvent } from "./providers";
import type { AgentAnswer } from "../types";
import { generateTraceId, collectArtifactsUsed, PROVIDER_CAPABILITIES } from "./providers";
import { SUGGESTED_QUESTIONS } from "../utils/agent";

export const offlineMockProvider: AgentProvider = {
  kind: "offline_mock",
  capabilities: PROVIDER_CAPABILITIES.offline_mock,

  run(request: AgentRunRequest): AgentRunResult {
    const startTime = Date.now();
    const traceId = generateTraceId();
    const bundle = request.bundle;
    const question = request.question.trim();

    const steps: AgentTraceStep[] = [];
    const artifactsUsed = collectArtifactsUsed(bundle);

    // Step 1: identify intent
    let matchedIntent = _detectIntent(question);
    steps.push({
      step_id: "step-1",
      kind: "route_question",
      description: `Offline mock intent detection: ${matchedIntent}`,
      input_artifacts: [],
      output_summary: `Detected intent: ${matchedIntent}`,
    });

    // Step 2: select primary artifact
    const primaryArtifact = _selectPrimaryArtifact(matchedIntent, bundle);
    steps.push({
      step_id: "step-2",
      kind: "select_artifact",
      description: `Selected primary artifact: ${primaryArtifact}`,
      input_artifacts: artifactsUsed,
      output_summary: `Will read ${primaryArtifact} to build answer`,
    });

    // Step 3: collect evidence / routes
    const { evidenceIds, sourceFiles, collectedGaps } = _collectMockEvidence(matchedIntent, bundle);
    steps.push({
      step_id: "step-3",
      kind: "collect_evidence",
      description: `Collected ${evidenceIds.length} evidence items from ${sourceFiles.length} source files`,
      input_artifacts: [primaryArtifact],
      output_summary: `${evidenceIds.length} evidence items, ${collectedGaps.length} gaps noted`,
    });

    // Step 4: compose mock answer
    const answer = _composeMockAnswer(question, matchedIntent, bundle, evidenceIds, sourceFiles, collectedGaps);
    steps.push({
      step_id: "step-4",
      kind: "compose_answer",
      description: "Composed offline mock answer from local artifacts",
      input_artifacts: artifactsUsed,
      output_summary: `Answer: ${answer.conclusion.slice(0, 60)}${answer.conclusion.length > 60 ? "..." : ""}`,
    });

    const trace = {
      trace_id: traceId,
      provider_kind: "offline_mock" as const,
      question,
      matched_intent: matchedIntent,
      steps,
      artifacts_used: artifactsUsed,
      evidence_ids: evidenceIds,
      source_files: sourceFiles,
      limitations: [
        "Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。",
        "回答由预定义模板和本地数据拼接生成，不执行语义推理。",
        ...collectedGaps,
      ],
      generated_at: new Date(startTime).toISOString(),
    };

    const policy_result: AgentRunPolicyResult = {
      allowed: true,
      provider_kind: "offline_mock",
      reason: "Offline Mock provider 仅读取本地 artifacts，不调用外部 API，允许运行",
      network_allowed: false,
      requires_api_key: false,
      external_calls_allowed: false,
      secret_storage_allowed: false,
      policy_version: "t043.0",
      limitations: [
        "Offline Mock 回答由预定义模板和本地数据拼接生成，不执行语义推理",
      ],
    };

    const base: Omit<AgentRunResult, "policy_result" | "audit_event"> = {
      answer,
      provider: "offline_mock",
      trace,
      artifacts_used: artifactsUsed,
      evidence_ids: evidenceIds,
      limitations: trace.limitations,
      external_calls_made: false,
    };

    const audit_event: AgentRunAuditEvent = {
      event_id: `audit-${Date.now()}-${Math.floor(Math.random() * 10000).toString(16).padStart(4, "0")}`,
      timestamp: new Date().toISOString(),
      provider_kind: "offline_mock",
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

// ─── Internal helpers ──────────────────────────────────────────────

function _detectIntent(question: string): string {
  const q = question.toLowerCase();
  if (q.includes("从哪里开始") || q.includes("推荐") || q.includes("先看")) return "navigation_help";
  if (q.includes("下一步") || q.includes("点哪里")) return "next_steps";
  if (q.includes("噪声") || q.includes("假阳性")) return "noise_concepts";
  if (q.includes("完整证据链")) return "full_evidence_chain";
  if (q.includes("precision") || q.includes("recall") || q.includes("精确率") || q.includes("召回率")) return "quality_metrics";
  if (q.includes("golden")) return "golden_spec";
  if (q.includes("整体") || q.includes("实现")) return "project_summary";
  if (q.includes("pipeline") || q.includes("阶段")) return "pipeline_stages";
  if (q.includes("概念") || q.includes("识别")) return "discovered_concepts";
  if (q.includes("edge") || q.includes("边")) return "edge_evidence";
  if (q.includes("数据") && q.includes("来源")) return "data_provenance";
  return "general";
}

function _selectPrimaryArtifact(intent: string, bundle: AgentRunRequest["bundle"]): string {
  if (!bundle) return "project_understanding_graph.json";
  const nav = bundle.agent_navigation_index;
  const pv = bundle.semantic_pipeline_view;
  const ss = bundle.semantic_summary;
  switch (intent) {
    case "navigation_help": return nav ? "agent_navigation_index.json" : (ss ? "project_semantic_summary.json" : "project_understanding_graph.json");
    case "next_steps": return nav ? "agent_navigation_index.json" : "project_understanding_graph.json";
    case "noise_concepts": return "discovery_eval_result.json";
    case "quality_metrics": return "discovery_eval_result.json";
    case "golden_spec": return "discovery_eval_result.json";
    case "pipeline_stages": return pv ? "semantic_pipeline_view.json" : "project_semantic_summary.json";
    case "full_evidence_chain": return "project_understanding_index.json";
    case "edge_evidence": return pv ? "semantic_pipeline_view.json" : "project_understanding_graph.json";
    default: return ss ? "project_semantic_summary.json" : "project_understanding_graph.json";
  }
}

function _collectMockEvidence(
  intent: string,
  bundle: AgentRunRequest["bundle"],
): { evidenceIds: string[]; sourceFiles: string[]; collectedGaps: string[] } {
  if (!bundle) return { evidenceIds: [], sourceFiles: [], collectedGaps: ["No bundle loaded"] };

  const evidenceIds: string[] = [];
  const sourceFiles: string[] = [];
  const gaps: string[] = [];

  const nav = bundle.agent_navigation_index;
  const pv = bundle.semantic_pipeline_view;
  const ss = bundle.semantic_summary;

  if (intent === "navigation_help" && nav) {
    evidenceIds.push(...nav.entrypoints.map((e: any) => e.id));
    nav.entrypoints.forEach((e: any) => {
      if (e.available) evidenceIds.push(e.artifact);
    });
  }

  if (intent === "noise_concepts" && nav) {
    evidenceIds.push(...nav.quality_status.excluded_terms_selected);
    if (nav.quality_status.excluded_terms_selected.length === 0) {
      gaps.push("No excluded terms in selected concepts — noise assessment may be incomplete.");
    }
  }

  if (intent === "quality_metrics" && nav) {
    evidenceIds.push("quality_status");
    if (!nav.quality_status.golden_spec_used) {
      gaps.push("No golden spec used in this bundle.");
    }
  }

  if (intent === "pipeline_stages" && pv) {
    pv.lanes.forEach((lane: any) => {
      sourceFiles.push(...lane.nodes.map((n: any) => n.file_path).filter(Boolean));
    });
  }

  if (intent === "edge_evidence" && pv) {
    pv.cross_stage_edges.forEach((e: any) => {
      evidenceIds.push(...e.evidence_ids);
      sourceFiles.push(...e.source_files);
    });
  }

  if (intent === "full_evidence_chain" && nav) {
    const route = nav.concept_routes[0];
    if (route) {
      evidenceIds.push(...route.evidence_ids);
      sourceFiles.push(...route.source_files);
    }
  }

  if (!nav) gaps.push("agent_navigation_index.json not available — using fallback artifacts.");
  if (!pv && (intent === "pipeline_stages" || intent === "edge_evidence")) {
    gaps.push("semantic_pipeline_view.json not available — pipeline/edge answers are limited.");
  }
  if (!ss && !nav) {
    gaps.push("semantic_summary.json not available — answers based on raw graph only.");
  }

  return { evidenceIds: [...new Set(evidenceIds)], sourceFiles: [...new Set(sourceFiles)], collectedGaps: gaps };
}

function _composeMockAnswer(
  question: string,
  intent: string,
  bundle: AgentRunRequest["bundle"],
  _evidenceIds: string[],
  _sourceFiles: string[],
  gaps: string[],
): AgentAnswer {
  if (!bundle) {
    return _makeMockAnswer(question, "请先加载 project bundle。", "未加载数据", "none", ["需要先加载 bundle 数据。"]);
  }

  const nav = bundle.agent_navigation_index;
  const ss = bundle.semantic_summary;
  const pv = bundle.semantic_pipeline_view;
  const evalData = bundle.discovery_eval_result as any;

  switch (intent) {
    case "navigation_help": {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      if (nav) {
        answer += `项目 "${nav.project_id}" 导航入口：\n`;
        const available = nav.entrypoints.filter((e: any) => e.available);
        answer += `可用入口: ${available.length}/${nav.entrypoints.length}\n`;
        for (const ep of available.slice(0, 3)) {
          answer += `  • ${ep.label} — ${ep.description}\n`;
        }
      } else if (ss) {
        answer += `项目 "${ss.project_id}" 理解入口：\n`;
        answer += `Pipeline Stages: ${ss.pipeline_stages.length} | 核心概念: ${ss.core_concepts.length}\n`;
      } else {
        answer += `项目 "${bundle.graph.project_id}" 理解入口：\n`;
        answer += "请查看 Project Graph 和 Evidence 页面。\n";
      }
      return _makeMockAnswer(question, answer, "导航入口已列出", nav ? "supported" : "inferred", gaps);
    }

    case "quality_metrics": {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      const qs = nav?.quality_status;
      if (qs?.golden_spec_used) {
        answer += `Golden Spec 评估：\n`;
        answer += `• Precision: ${(qs.selected_precision_like * 100).toFixed(1)}%\n`;
        answer += `• Recall: ${(qs.selected_recall_like * 100).toFixed(1)}%\n`;
        answer += `• 核心匹配: ${qs.matched_core_count} / 遗漏: ${qs.missed_core_count}\n`;
        if (qs.excluded_terms_selected.length > 0) {
          answer += `• 排除项泄漏: ${qs.excluded_terms_selected.join(", ")}\n`;
        }
      } else if (evalData) {
        answer += `Discovery Eval：\n`;
        answer += `• Precision: ${(evalData.selected_precision_like * 100).toFixed(1)}%\n`;
        answer += `• Recall: ${(evalData.selected_recall_like * 100).toFixed(1)}%\n`;
      } else {
        answer += "当前 bundle 无 golden spec 评估数据。\n";
      }
      return _makeMockAnswer(question, answer, "质量评估完成", qs?.golden_spec_used ? "supported" : "inferred", gaps);
    }

    case "full_evidence_chain": {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      const conceptName = _extractConceptFromQuestion(question, bundle);
      const route = nav?.concept_routes?.find((r: any) => r.concept === conceptName);
      if (route) {
        answer += `概念 "${route.concept}" 证据链：\n`;
        answer += `• L5/L6 证据: ${route.has_l5_l6 ? "有" : "缺失"}\n`;
        answer += `• RTL 证据: ${route.has_rtl ? "有" : "缺失"}\n`;
        answer += `• 测试证据: ${route.has_test ? "有" : "缺失"}\n`;
        answer += `• Confidence: ${route.confidence}\n`;
        answer += `• Mapping: ${route.mapping_confidence} (${route.mapping_reason})\n`;
        if (route.known_gaps.length > 0) {
          answer += `• Gaps: ${route.known_gaps.join(", ")}\n`;
        }
      } else if (conceptName) {
        answer += `概念 "${conceptName}" 未在 navigation index 中找到。\n`;
      } else {
        answer += "未检测到具体概念名。\n";
      }
      return _makeMockAnswer(question, answer, `证据链: ${route ? route.concept : "未找到"}`, route ? route.confidence : "none", gaps);
    }

    case "pipeline_stages": {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      if (pv) {
        answer += `Pipeline（${pv.lanes.length} lanes）：\n`;
        for (const lane of pv.lanes) {
          answer += `• ${lane.label}: ${lane.nodes.length} nodes\n`;
        }
        answer += `\n跨阶段边: ${pv.cross_stage_edges.length}\n`;
      } else if (ss) {
        answer += `Pipeline Stages（${ss.pipeline_stages.length}）：\n`;
        for (const stage of ss.pipeline_stages) {
          answer += `• ${stage.label}\n`;
        }
      } else {
        answer += "当前无 pipeline view 或 semantic summary。\n";
      }
      return _makeMockAnswer(question, answer, "Pipeline 信息已列出", pv ? "supported" : "inferred", gaps);
    }

    case "edge_evidence": {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      if (pv) {
        const edges = pv.cross_stage_edges;
        answer += `跨阶段边（${edges.length}）：\n`;
        for (const e of edges.slice(0, 5)) {
          answer += `• ${e.from_lane} → ${e.to_lane} | ${e.edge_type} (${e.confidence})\n`;
          if (e.reason) answer += `  原因: ${e.reason}\n`;
        }
      } else {
        answer += "当前无 pipeline view 数据。\n";
      }
      return _makeMockAnswer(question, answer, `跨阶段边: ${pv?.cross_stage_edges?.length ?? 0}`, pv ? "supported" : "none", gaps);
    }

    case "data_provenance": {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      answer += "当前回答的数据来源：\n";
      const arts = collectArtifactsUsed(bundle);
      for (const a of arts) {
        answer += `• ${a}\n`;
      }
      return _makeMockAnswer(question, answer, `${arts.length} 个 artifact 来源`, "supported", gaps);
    }

    default: {
      let answer = "🤖 Offline Mock Agent：基于本地 artifacts 模拟多步导航，不是外部 LLM/API。\n\n";
      answer += `这是 Offline Mock 对 "${question}" 的模拟回答。\n\n`;
      if (ss) {
        answer += `项目: ${ss.project_id}\n`;
        answer += `目的: ${ss.top_level_purpose}\n`;
        answer += `核心概念: ${ss.core_concepts.map((c: any) => c.display_name).join(", ")}\n`;
      } else {
        const concepts = bundle.graph.nodes.filter((n) => n.kind === "concept");
        answer += `项目: ${bundle.graph.project_id}\n`;
        answer += `识别出 ${concepts.length} 个概念\n`;
      }
      return _makeMockAnswer(question, answer, "Offline Mock 通用回答", "inferred", gaps);
    }
  }
}

function _extractConceptFromQuestion(question: string, bundle: AgentRunRequest["bundle"]): string {
  if (!bundle) return "";
  const concepts = bundle.graph.nodes.filter((n) => n.kind === "concept");
  for (const c of concepts) {
    if (question.includes(c.label)) return c.label;
  }
  return "";
}

function _makeMockAnswer(
  question: string,
  answer: string,
  conclusion: string,
  strength: string,
  limitations: string[],
): AgentAnswer {
  return {
    question,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: SUGGESTED_QUESTIONS.slice(0, 3),
    conclusion,
    strength,
    limitations_summary: limitations.join("; ") || "Offline Mock 回答，不执行真实推理。",
  };
}
