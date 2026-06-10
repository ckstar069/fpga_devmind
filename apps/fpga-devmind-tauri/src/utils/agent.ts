import type { ProjectBundle, AgentAnswer } from "../types";
import { aggregateRtl } from "./transforms";

/* ================================================================== */
/*  Deterministic Agent Q&A (no LLM)                                  */
/* ================================================================== */

export const SUGGESTED_QUESTIONS = [
  "这个项目整体实现了什么？",
  "自动识别出了哪些概念？",
  "哪些概念达到了 supported 置信度？",
  "哪些概念缺失 RTL 证据？",
  "哪些 RTL 文件承载了多个概念？",
  "哪些证据最关键？",
  "项目的不确定性有哪些？",
  "为什么这些概念被选中？",
  "哪些概念缺少测试证据？",
  "发现质量如何？",
  "测试覆盖分析",
  "精确率和召回率是多少？",
  "哪些高分概念被过滤了？",
  "概念类别分布如何？",
  "画出项目理解图",
  "解释当前选中节点",
  "pipeline 有哪些阶段？",
  "实现细节有哪些？",
  "数据来源是什么？",
  "某个概念的 pipeline 路径是什么？",
  "哪些概念跨了所有阶段？",
  "dataflow 是怎样的？",
];

/** Helper to build a standard AgentAnswer with evidence-chain fields */
function makeAnswer(partial: {
  question: string;
  answer: string;
  referenced_nodes?: string[];
  referenced_claims?: string[];
  referenced_evidence?: string[];
  follow_up_questions?: string[];
  conclusion: string;
  strength: string;
  limitations_summary: string;
}): AgentAnswer {
  return {
    question: partial.question,
    answer: partial.answer,
    referenced_nodes: partial.referenced_nodes ?? [],
    referenced_claims: partial.referenced_claims ?? [],
    referenced_evidence: partial.referenced_evidence ?? [],
    follow_up_questions: partial.follow_up_questions ?? SUGGESTED_QUESTIONS.slice(0, 3),
    conclusion: partial.conclusion,
    strength: partial.strength,
    limitations_summary: partial.limitations_summary,
  };
}

export function answerQuestion(
  bundle: ProjectBundle | null,
  question: string,
  selectedNodeId: string | null,
): AgentAnswer {
  if (!bundle) {
    return makeAnswer({
      question,
      answer: "请先加载 project bundle。在 Settings 页面输入 bundle 路径或生成新的 bundle。",
      follow_up_questions: SUGGESTED_QUESTIONS.slice(0, 3),
      conclusion: "未加载数据，无法回答。",
      strength: "none",
      limitations_summary: "需要先加载 bundle 数据。",
    });
  }

  const q = question.trim();
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");

  // Pattern matching on question

  // "这个项目整体实现了什么？" / overall summary
  if (q.includes("整体") && (q.includes("实现") || q.includes("什么"))) {
    return answerProjectSummary(bundle, q);
  }

  // "哪些概念达到了 supported？" / "哪些概念是 supported/inferred?"
  if (q.includes("supported") || q.includes("supported 置信度")) {
    return answerSupportedConcepts(bundle, q);
  }

  // "哪些概念缺失 RTL 证据？" / "缺失" / "missing"
  if (q.includes("缺失") || q.includes("missing") || (q.includes("没有") && (q.includes("RTL") || q.includes("证据")))) {
    return answerMissingEvidence(bundle, q);
  }

  // "自动识别出了哪些概念？" / "识别出" / "哪些概念"
  if (q.includes("自动识别") || q.includes("识别出") || q.includes("哪些概念")) {
    return answerDiscoveredConcepts(bundle, q);
  }

  // Legacy: specific concept mapping questions
  if (q.includes("映射") || q.includes("L5") || q.includes("RTL")) {
    // Try to match any concept name from the bundle
    for (const c of concepts) {
      if (q.includes(c.label)) {
        return answerConceptMapping(bundle, c.label, q);
      }
    }
  }

  // "cfo 对应哪些 RTL?" style
  if (q.includes("RTL") || q.includes("对应") || q.includes("哪些")) {
    for (const c of concepts) {
      if (q.includes(c.label)) {
        return answerConceptRtl(bundle, c.label, q);
      }
    }
  }

  // "smooth_detect 为什么是 inferred?" style
  if (q.includes("inferred") || q.includes("为什么") || q.includes("推断")) {
    for (const c of concepts) {
      if (q.includes(c.label)) {
        return answerWhyInferred(bundle, c.label, q);
      }
    }
  }

  if (q.includes("多个概念") && (q.includes("RTL") || q.includes("文件") || q.includes("承载"))) {
    return answerSharedRtl(bundle, q);
  }

  if (q.includes("最关键") || q.includes("关键证据") || q.includes("哪些证据")) {
    return answerKeyEvidence(bundle, q);
  }

  // T038: Semantic summary driven Q&A — moved BEFORE legacy patterns for priority
  if (q.includes("pipeline") || q.includes("阶段") || q.includes("stage")) {
    return answerPipelineStages(bundle, q);
  }

  if (q.includes("实现细节") || q.includes("implementation")) {
    return answerImplementationDetails(bundle, q);
  }

  // T038: inferred/uncertainty via semantic summary takes priority over legacy answerUncertainty
  if ((q.includes("inferred") || q.includes("推断") || q.includes("不确定性")) && bundle.semantic_summary) {
    return answerInferredAreas(bundle, q);
  }

  if (q.includes("数据来源") || q.includes("data from") || q.includes("provenance")) {
    return answerDataProvenance(bundle, q);
  }

  // T038: "why.*selected" per concept via semantic summary takes priority over legacy answerSelectionReasons
  if (q.includes("为什么") && q.includes("选中") && bundle.semantic_summary) {
    for (const c of bundle.semantic_summary.core_concepts) {
      if (q.includes(c.canonical_name) || q.includes(c.display_name)) {
        return answerWhySelected(bundle, c.canonical_name, q);
      }
    }
  }

  if (q.includes("不能确认") || q.includes("不确定") || q.includes("还不能") || q.includes("不确定性")) {
    return answerUncertainty(bundle, q);
  }

  if (q.includes("图") || q.includes("画出") || q.includes("可视化")) {
    return answerDrawGraph(bundle, q);
  }

  if (q.includes("选中") || q.includes("解释") || q.includes("当前节点")) {
    return answerExplainSelected(bundle, q, selectedNodeId);
  }

  // T039/T040: Pipeline / dataflow questions
  if (q.includes("pipeline 路径") || q.includes("路径是什么") || q.includes("dataflow")) {
    return answerPipelinePath(bundle, q);
  }

  if (q.includes("跨了所有阶段") || q.includes("跨阶段") || q.includes("full pipeline")) {
    return answerFullPipelineConcepts(bundle, q);
  }

  if (q.includes("dataflow") || q.includes("数据流") || q.includes("数据流向")) {
    return answerDataflowSummary(bundle, q);
  }

  // T036: "为什么这些概念被选中？" / "selection reason"
  if (q.includes("为什么") && (q.includes("选中") || q.includes("选择") || q.includes("选出"))) {
    return answerSelectionReasons(bundle, q);
  }

  // T036: "哪些概念缺少测试证据？"
  if (q.includes("缺少") && q.includes("测试")) {
    return answerMissingTestEvidence(bundle, q);
  }

  // T036: "发现质量如何？"
  if (q.includes("发现质量") || (q.includes("发现") && q.includes("质量"))) {
    return answerDiscoveryQuality(bundle, q);
  }

  // T037: "测试覆盖分析"
  if (q.includes("测试覆盖") || q.includes("测试分析")) {
    return answerTestCoverage(bundle, q);
  }

  // T037: "精确率和召回率"
  if (q.includes("精确率") || q.includes("召回率") || q.includes("precision") || q.includes("recall")) {
    return answerPrecisionRecall(bundle, q);
  }

  // T037: "哪些高分概念被过滤了？"
  if ((q.includes("过滤") || q.includes("排除")) && (q.includes("概念") || q.includes("高分"))) {
    return answerFilteredConcepts(bundle, q);
  }

  // T037: "概念类别分布如何？"
  if (q.includes("类别分布") || (q.includes("概念") && q.includes("类别"))) {
    return answerCategoryDistribution(bundle, q);
  }

  // T037: "golden spec 匹配分析"
  if (q.includes("golden") || q.includes("基准匹配") || q.includes("标准匹配")) {
    return answerGoldenMatch(bundle, q);
  }

  // Generic concept name matching: if any concept name appears in the question
  for (const c of concepts) {
    if (q.includes(c.label)) {
      return answerConceptMapping(bundle, c.label, q);
    }
  }

  return makeAnswer({
    question: q,
    answer: `当前确定性 Agent 不完全理解这个问题。请尝试以下建议问题，或点击右侧链接：`,
    follow_up_questions: SUGGESTED_QUESTIONS,
    conclusion: "无法理解问题。",
    strength: "none",
    limitations_summary: "确定性 Agent 仅支持预定义问题模式。",
  });
}

function answerProjectSummary(bundle: ProjectBundle, q: string): AgentAnswer {
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");
  const claims = nodes.filter((n) => n.kind === "mapping_claim");
  const supported = claims.filter((c) => c.confidence === "supported");
  const inferred = claims.filter((c) => c.confidence === "inferred");

  const { aggregates } = aggregateRtl(nodes, bundle.graph.edges);

  const conceptDesc = concepts.map((c) => {
    const ci = bundle.index.concept_index[c.label];
    return `• ${c.label}：${ci?.evidence ?? 0} 条证据，${ci?.rtl_objects ?? 0} 个 RTL 对象，置信度 ${c.confidence ?? "unknown"}`;
  }).join("\n");

  const answer = `项目 "${bundle.graph.project_id}" 是一个 FPGA 通信模块，` +
    `主要实现 OFDM 系统中接收端的同步/处理功能。\n\n` +
    `目前识别出 ${concepts.length} 个核心概念：\n${conceptDesc}\n\n` +
    `Mapping Claims：${claims.length} 个（${supported.length} supported，${inferred.length} inferred）\n` +
    `证据总数：${bundle.metadata.evidence_items} 条\n` +
    `RTL 文件/模块：${aggregates.length} 个\n\n` +
    (bundle.metadata.diagnostics === 0
      ? `当前无 blocking diagnostics。但注意：这只是证据抽取阶段未发现 blocking 问题，不代表设计已验证正确。仍需进一步确认映射准确性和设计完整性。`
      : `存在 ${bundle.metadata.diagnostics} 个 diagnostics，请查看 Evidence 页面。`);

  const refNodes = concepts.map((c) => c.node_id);
  const refClaims = claims.map((c) => c.node_id);

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: refNodes,
    referenced_claims: refClaims,
    referenced_evidence: [],
    follow_up_questions: [
      "自动识别出了哪些概念？",
      "哪些概念达到了 supported 置信度？",
      "哪些概念缺失 RTL 证据？",
    ],
    conclusion: `项目 "${bundle.graph.project_id}" 识别出 ${concepts.length} 个概念，${claims.length} 个映射声明（${supported.length} supported，${inferred.length} inferred），${bundle.metadata.evidence_items} 条证据。`,
    strength: supported.length > inferred.length ? "supported" : "mixed",
    limitations_summary: inferred.length > 0
      ? `有 ${inferred.length} 个推断性映射需进一步验证。仅基于静态分析，未经仿真或形式验证确认。`
      : "仅基于静态分析，未经仿真或形式验证确认。",
  });
}

function answerSupportedConcepts(bundle: ProjectBundle, q: string): AgentAnswer {
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");
  const claims = nodes.filter((n) => n.kind === "mapping_claim");

  const supported = concepts.filter((c) => {
    const claim = claims.find((cl) => cl.concept === c.label);
    return claim?.confidence === "supported";
  });
  const inferred = concepts.filter((c) => {
    const claim = claims.find((cl) => cl.concept === c.label);
    return claim?.confidence === "inferred";
  });
  const unknown = concepts.filter((c) => {
    const claim = claims.find((cl) => cl.concept === c.label);
    return !claim || claim.confidence === "unknown" || !claim.confidence;
  });

  const answer = `概念置信度分布：\n\n` +
    `Supported (${supported.length})：\n` +
    (supported.length > 0
      ? supported.map((c) => `  • ${c.label}`).join("\n")
      : "  无") +
    `\n\nInferred (${inferred.length})：\n` +
    (inferred.length > 0
      ? inferred.map((c) => `  • ${c.label}`).join("\n")
      : "  无") +
    `\n\nUnknown (${unknown.length})：\n` +
    (unknown.length > 0
      ? unknown.map((c) => `  • ${c.label}`).join("\n")
      : "  无");

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [...supported, ...inferred, ...unknown].map((c) => c.node_id),
    referenced_claims: claims.map((c) => c.node_id),
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念缺失 RTL 证据？",
      "项目的不确定性有哪些？",
      "哪些证据最关键？",
    ],
    conclusion: `${supported.length} supported, ${inferred.length} inferred, ${unknown.length} unknown。`,
    strength: inferred.length + unknown.length > 0 ? "mixed" : "supported",
    limitations_summary: inferred.length + unknown.length > 0
      ? `${inferred.length + unknown.length} 个概念需进一步验证。`
      : "所有概念均已确认。",
  });
}

function answerMissingEvidence(bundle: ProjectBundle, q: string): AgentAnswer {
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");

  const missingRtl: string[] = [];
  const missingL5L6: string[] = [];

  for (const c of concepts) {
    const evEntries = Object.entries(bundle.index.evidence_index)
      .filter(([, v]) => v.concept === c.label);
    const hasRtl = evEntries.some(([, v]) => v.source_type === "rtl_source");
    const hasL5L6 = evEntries.some(([, v]) =>
      v.file_path?.includes("L5_fixedpoint") || v.file_path?.includes("L6_resource_opt")
    );
    if (!hasRtl) missingRtl.push(c.label);
    if (!hasL5L6) missingL5L6.push(c.label);
  }

  const answer = `缺失证据分析：\n\n` +
    `缺失 RTL 证据的概念 (${missingRtl.length})：\n` +
    (missingRtl.length > 0
      ? missingRtl.map((name) => `  • ${name}`).join("\n")
      : "  所有概念都有 RTL 证据") +
    `\n\n缺失 L5/L6 证据的概念 (${missingL5L6.length})：\n` +
    (missingL5L6.length > 0
      ? missingL5L6.map((name) => `  • ${name}`).join("\n")
      : "  所有概念都有 L5/L6 证据");

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: concepts.map((c) => c.node_id),
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些证据最关键？",
      "哪些概念达到了 supported 置信度？",
      "这个项目整体实现了什么？",
    ],
    conclusion: `${missingRtl.length} 个概念缺失 RTL 证据，${missingL5L6.length} 个概念缺失 L5/L6 证据。`,
    strength: missingRtl.length + missingL5L6.length > 0 ? "inferred" : "supported",
    limitations_summary: "基于当前证据索引的静态分析。",
  });
}

function answerDiscoveredConcepts(bundle: ProjectBundle, q: string): AgentAnswer {
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");
  const processed = bundle.metadata.concepts_processed ?? [];

  const answer = `自动识别出 ${concepts.length} 个概念：\n\n` +
    concepts.map((c) => {
      const ci = bundle.index.concept_index[c.label];
      const evCount = ci?.evidence ?? 0;
      const rtlCount = ci?.rtl_objects ?? 0;
      const conf = c.confidence ?? "unknown";
      const marker = conf === "supported" ? "[supported]" : conf === "inferred" ? "[inferred]" : "[unknown]";
      return `• ${c.label} ${marker} — ${evCount} 条证据，${rtlCount} 个 RTL 对象`;
    }).join("\n") +
    `\n\n概念处理顺序：${processed.length > 0 ? processed.join(" → ") : "未记录"}`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: concepts.map((c) => c.node_id),
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念达到了 supported 置信度？",
      "哪些概念缺失 RTL 证据？",
      "项目的不确定性有哪些？",
    ],
    conclusion: `识别出 ${concepts.length} 个概念，${concepts.filter(c => c.confidence === "supported").length} 个 supported。`,
    strength: "supported",
    limitations_summary: "概念发现基于静态代码分析，可能遗漏隐含概念。",
  });
}

function answerConceptMapping(bundle: ProjectBundle, conceptName: string, q: string): AgentAnswer {
  const { nodes, edges } = bundle.graph;
  const concept = nodes.find((n) => n.kind === "concept" && n.label === conceptName);
  if (!concept) {
    return makeAnswer({
      question: q,
      answer: `未找到概念 "${conceptName}"。`,
      conclusion: `概念 "${conceptName}" 未在 bundle 中找到。`,
      strength: "none",
      limitations_summary: "无法分析不存在的概念。",
    });
  }

  const claim = nodes.find((n) => n.kind === "mapping_claim" && n.concept === conceptName);
  const { aggregates, claimToAgg } = aggregateRtl(nodes, edges);
  const ci = bundle.index.concept_index[conceptName];

  const aggIds = claim ? (claimToAgg.get(claim.node_id) ?? []) : [];
  const aggLabels = aggIds.map((id) => aggregates.find((a) => a.id === id)?.label).filter(Boolean) as string[];

  const l5Evidence = Object.entries(bundle.index.evidence_index)
    .filter(([, v]) => v.concept === conceptName && v.source_type === "concept_occurrence");
  const rtlEvidence = Object.entries(bundle.index.evidence_index)
    .filter(([, v]) => v.concept === conceptName && v.source_type === "rtl_source");

  const answer = `概念 "${conceptName}" 的映射路径：\n\n` +
    `1. L5/L6 证据层：${l5Evidence.length} 处概念出现\n` +
    l5Evidence.slice(0, 3).map(([, v]) =>
      `   • ${v.symbol ?? "?"} in ${(v.file_path ?? "").split("/").slice(-2).join("/")}`
    ).join("\n") + (l5Evidence.length > 3 ? `\n   ... 还有 ${l5Evidence.length - 3} 处` : "") + "\n\n" +
    `2. Mapping Claim：${claim?.label ?? "无"} (confidence: ${claim?.confidence ?? "?"}, bridge: ${claim?.bridge_kind ?? "?"})\n\n` +
    `3. RTL 实现层：${rtlEvidence.length} 处 RTL 证据\n` +
    `   RTL 文件：${aggLabels.length > 0 ? aggLabels.join("、") : "无聚合模块"}\n` +
    rtlEvidence.slice(0, 3).map(([, v]) =>
      `   • ${v.symbol ?? "?"} in ${(v.file_path ?? "").split("/").slice(-2).join("/")} (${v.strength})`
    ).join("\n") + "\n\n" +
    `总证据：${ci?.evidence ?? 0} 条，RTL 对象：${ci?.rtl_objects ?? 0} 个\n` +
    `bridge_kind=${claim?.bridge_kind ?? "?"}：` +
    (claim?.bridge_kind === "calculation_role"
      ? "通过计算角色分析确认 L5/L6 → RTL 映射。"
      : claim?.bridge_kind === "naming_plus_structure"
        ? "命名匹配 + 结构对比确认。"
        : claim?.bridge_kind === "naming_only"
          ? "仅命名匹配（弱证据）。"
          : "映射方式待确认。");

  const refEvidence = [...l5Evidence.slice(0, 3), ...rtlEvidence.slice(0, 3)].map(([id]) => id);

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [concept.node_id, ...(claim ? [claim.node_id] : [])],
    referenced_claims: claim ? [claim.node_id] : [],
    referenced_evidence: refEvidence,
    follow_up_questions: [
      "哪些概念达到了 supported 置信度？",
      "哪些证据最关键？",
      "哪些概念缺失 RTL 证据？",
    ],
    conclusion: `概念 "${conceptName}" 通过 ${claim?.bridge_kind ?? "?"} 映射到 RTL（${aggLabels.join("、") || "无"}），置信度 ${claim?.confidence ?? "unknown"}。`,
    strength: claim?.confidence === "supported" ? "supported" : claim?.confidence === "inferred" ? "inferred" : "unknown",
    limitations_summary: claim?.bridge_kind === "naming_only"
      ? "仅基于命名匹配，无结构/行为验证，可能存在假阳性。"
      : `证据总数 ${ci?.evidence ?? 0} 条，需确认 L5/L6 计算逻辑是否真正对应 RTL 实现。`,
  });
}

function answerConceptRtl(bundle: ProjectBundle, conceptName: string, q: string): AgentAnswer {
  const { nodes, edges } = bundle.graph;
  const claim = nodes.find((n) => n.kind === "mapping_claim" && n.concept === conceptName);
  const { aggregates, claimToAgg } = aggregateRtl(nodes, edges);

  const aggIds = claim ? (claimToAgg.get(claim.node_id) ?? []) : [];
  const relatedAggs = aggIds.map((id) => aggregates.find((a) => a.id === id)).filter(Boolean);

  const answer = `概念 "${conceptName}" 对应的 RTL 文件/模块：\n\n` +
    (relatedAggs.length > 0
      ? relatedAggs.map((a) =>
        `• ${a!.label}\n  文件：${a!.file_path}\n  包含 ${a!.child_count} 个 RTL 对象 (${a!.child_kinds.join("、")})\n  涉及概念：${a!.concept_labels.join("、")}`
      ).join("\n\n")
      : "未找到对应的 RTL 模块。") +
    `\n\nClaim：${claim?.label ?? "无"} (${claim?.confidence ?? "?"}, bridge: ${claim?.bridge_kind ?? "?"})`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: relatedAggs.map((a) => a!.id),
    referenced_claims: claim ? [claim.node_id] : [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些 RTL 文件承载了多个概念？",
      "哪些证据最关键？",
      "哪些概念缺失 RTL 证据？",
    ],
    conclusion: `概念 "${conceptName}" 对应 ${relatedAggs.length} 个 RTL 文件/模块${relatedAggs.length > 0 ? "：" + relatedAggs.map((a) => a!.label).join("、") : ""}。`,
    strength: claim?.confidence === "supported" ? "supported" : "inferred",
    limitations_summary: "RTL 聚合基于文件路径分组，不保证语义完整性。",
  });
}

function answerWhyInferred(bundle: ProjectBundle, conceptName: string, q: string): AgentAnswer {
  const { nodes, edges } = bundle.graph;
  const concept = nodes.find((n) => n.kind === "concept" && n.label === conceptName);
  const claim = nodes.find((n) => n.kind === "mapping_claim" && n.concept === conceptName);

  const { aggregates, claimToAgg } = aggregateRtl(nodes, edges);
  const aggIds = claim ? (claimToAgg.get(claim.node_id) ?? []) : [];
  const relatedAggs = aggIds.map((id) => aggregates.find((a) => a.id === id)).filter(Boolean);

  const bridge = claim?.bridge_kind ?? "?";
  const conf = claim?.confidence ?? "unknown";

  const evEntries = Object.entries(bundle.index.evidence_index)
    .filter(([, v]) => v.concept === conceptName);
  const strongEv = evEntries.filter(([, v]) => v.strength === "strong");
  const weakEv = evEntries.filter(([, v]) => v.strength === "weak" || !v.strength);
  const l5Ev = evEntries.filter(([, v]) => v.source_type === "concept_occurrence");
  const rtlEv = evEntries.filter(([, v]) => v.source_type === "rtl_source");

  const answer = `概念 "${conceptName}" 的置信度为 ${conf}，原因分析：\n\n` +
    `• bridge_kind = ${bridge}\n` +
    (bridge === "naming_only"
      ? "  仅通过命名匹配推断映射关系。命名匹配是最弱的映射方式——仅因为 RTL 信号/模块名与概念名相似就建立关联，\n" +
        "  没有验证 L5/L6 的计算逻辑是否真正对应 RTL 的实现。\n\n"
      : bridge === "calculation_role"
        ? "  通过计算角色分析推断。虽然分析了计算角色，但置信度仍为 inferred 而非 supported，\n" +
          "  可能因为证据不够充分或存在不确定性。\n\n"
        : `  映射方式：${bridge}\n\n`) +
    `• 证据分布：${strongEv.length} strong / ${evEntries.length - strongEv.length - weakEv.length} medium / ${weakEv.length} weak\n` +
    `  L5/L6 证据：${l5Ev.length} 条\n` +
    `  RTL 证据：${rtlEv.length} 条\n` +
    `  RTL 文件：${relatedAggs.map((a) => a!.label).join("、") || "无"}\n\n` +
    `• 原因总结：${bridge === "naming_only"
      ? "仅依赖命名匹配是推断而非确认的主要原因。建议检查 L5/L6 代码中的计算逻辑是否与 RTL 实现对应。"
      : "证据强度不足以达到 supported 级别。建议检查更多 L5/L6 与 RTL 的结构对比证据。"}`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [concept?.node_id ?? "", claim?.node_id ?? ""].filter(Boolean),
    referenced_claims: claim ? [claim.node_id] : [],
    referenced_evidence: evEntries.slice(0, 5).map(([id]) => id),
    follow_up_questions: [
      "哪些证据最关键？",
      "哪些概念达到了 supported 置信度？",
      "哪些概念缺失 RTL 证据？",
    ],
    conclusion: `"${conceptName}" 置信度为 ${conf}，因为 bridge_kind=${bridge}，${strongEv.length} 条 strong 证据 / ${evEntries.length} 条总证据。`,
    strength: conf,
    limitations_summary: bridge === "naming_only"
      ? "命名匹配可能产生假阳性，需进一步验证。"
      : "证据强度不足以达到 supported 级别。",
  });
}

function answerSharedRtl(bundle: ProjectBundle, q: string): AgentAnswer {
  const { nodes, edges } = bundle.graph;
  const { aggregates } = aggregateRtl(nodes, edges);

  const shared = aggregates.filter((a) => a.concept_labels.length > 1);

  const answer = shared.length > 0
    ? `承载多个概念的 RTL 文件：\n\n` +
      shared.map((a) =>
        `• ${a.label}\n  文件：${a.file_path}\n  包含 ${a.child_count} 个 RTL 对象\n  承载概念：${a.concept_labels.join("、")}\n  这是概念之间共享 RTL 资源的表现，shared edges 是 structural inferred，不代表语义确认。`
      ).join("\n\n")
    : "当前未发现承载多个概念的 RTL 文件。所有概念都映射到独立的 RTL 模块。";

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: shared.map((a) => a.id),
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些证据最关键？",
      "这个项目整体实现了什么？",
      "哪些概念缺失 RTL 证据？",
    ],
    conclusion: shared.length > 0
      ? `发现 ${shared.length} 个承载多个概念的 RTL 文件。`
      : "所有概念映射到独立 RTL 模块。",
    strength: shared.length > 0 ? "inferred" : "supported",
    limitations_summary: "shared edges 是结构推断，不是语义确认。",
  });
}

function answerKeyEvidence(bundle: ProjectBundle, q: string): AgentAnswer {
  const entries = Object.entries(bundle.index.evidence_index);
  const strong = entries.filter(([, v]) => v.strength === "strong");
  const byConcept = new Map<string, typeof entries>();
  for (const [id, ev] of strong) {
    const c = ev.concept ?? "?";
    if (!byConcept.has(c)) byConcept.set(c, []);
    byConcept.get(c)!.push([id, ev]);
  }

  const answer = `关键证据（strong 级别）共 ${strong.length} 条：\n\n` +
    [...byConcept.entries()].map(([concept, evs]) =>
      `概念 "${concept}"：${evs.length} 条 strong 证据\n` +
      evs.slice(0, 3).map(([, v]) =>
        `  • ${v.symbol ?? "?"} in ${(v.file_path ?? "").split("/").slice(-2).join("/")} [${v.source_type}]`
      ).join("\n") +
      (evs.length > 3 ? `\n  ... 还有 ${evs.length - 3} 条` : "")
    ).join("\n\n") +
    `\n\n共 ${entries.length} 条证据中，strong ${strong.length} 条，` +
    `medium ${entries.filter(([, v]) => v.strength === "medium").length} 条，` +
    `weak/其他 ${entries.length - strong.length - entries.filter(([, v]) => v.strength === "medium").length} 条。\n\n` +
    `strong 证据是最可靠的：它们来自 L5/L6 代码中直接使用概念计算逻辑的地方，或 RTL 代码中有明确对应实现的证据。\n` +
    `weak/naming 证据仅基于命名匹配，不能作为确认依据。`;

  const strongEvIds = strong.slice(0, 10).map(([id]) => id);

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: strongEvIds,
    follow_up_questions: [
      "哪些概念达到了 supported 置信度？",
      "哪些概念缺失 RTL 证据？",
      "哪些 RTL 文件承载了多个概念？",
    ],
    conclusion: `${strong.length} 条 strong 证据（共 ${entries.length} 条）。Strong 证据是映射确认的核心依据。`,
    strength: strong.length > 0 ? "supported" : "weak",
    limitations_summary: `仅 ${strong.length} / ${entries.length} 条为 strong 级别，其余需进一步验证。`,
  });
}

function answerUncertainty(bundle: ProjectBundle, q: string): AgentAnswer {
  const { nodes } = bundle.graph;
  const unknownConcepts = nodes.filter((n) => n.kind === "concept" && n.confidence === "unknown");
  const inferredConcepts = nodes.filter((n) => n.kind === "concept" && n.confidence === "inferred");
  const inferredClaims = nodes.filter((n) => n.kind === "mapping_claim" && n.confidence === "inferred");
  const namingOnlyClaims = nodes.filter((n) => n.kind === "mapping_claim" && n.bridge_kind === "naming_only");

  const weakEv = Object.entries(bundle.index.evidence_index)
    .filter(([, v]) => v.strength === "weak" || !v.strength);

  const answer = `当前不确定性分析：\n\n` +
    `1. 未知置信度概念（${unknownConcepts.length} 个）：\n` +
    (unknownConcepts.length > 0
      ? unknownConcepts.map((c) => `   • ${c.label}`).join("\n")
      : "   无。但这只说明证据抽取阶段未发现 blocking unknown，不代表设计已验证正确。") + "\n\n" +
    `2. 推断性概念（${inferredConcepts.length} 个）：\n` +
    inferredConcepts.map((c) => `   • ${c.label} — 映射可能存在假阳性`).join("\n") + "\n\n" +
    `3. naming_only claims（${namingOnlyClaims.length} 个）：\n` +
    namingOnlyClaims.map((c) => `   • ${c.label} (${c.concept}) — 仅命名匹配`).join("\n") + "\n\n" +
    `4. 弱证据（${weakEv.length} 条）：这些不能作为确认依据\n` +
    (weakEv.length > 0
      ? weakEv.slice(0, 5).map(([, v]) => `   • ${v.symbol ?? "?"} in ${(v.file_path ?? "").split("/").slice(-2).join("/")}`).join("\n")
      : "   无弱证据") + "\n\n" +
    `建议：重点验证 inferred 概念的映射准确性，特别是 naming_only claim 对应的概念。`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [...unknownConcepts, ...inferredConcepts].map((n) => n.node_id),
    referenced_claims: [...inferredClaims, ...namingOnlyClaims].map((n) => n.node_id),
    referenced_evidence: weakEv.slice(0, 5).map(([id]) => id),
    follow_up_questions: [
      "哪些概念达到了 supported 置信度？",
      "哪些证据最关键？",
      "这个项目整体实现了什么？",
    ],
    conclusion: `${inferredConcepts.length} 个推断性概念，${namingOnlyClaims.length} 个 naming_only claim，${weakEv.length} 条弱证据。`,
    strength: inferredConcepts.length > 0 ? "inferred" : "supported",
    limitations_summary: "不确定性分析基于静态证据抽取，未经仿真或形式验证。",
  });
}

function answerDrawGraph(_bundle: ProjectBundle, q: string): AgentAnswer {
  return makeAnswer({
    question: q,
    answer: "请点击左侧导航栏的「Project Graph」查看可视化理解图。\n\n图支持三种模式：\n• Summary：项目 → 概念 → Claim → RTL 聚合（推荐）\n• Detail：展开所有 RTL 细节节点\n• Focus：只看选中节点的相邻关系\n\n在图中点击任意节点，右侧会显示理解卡。",
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "这个项目整体实现了什么？",
      "解释当前选中节点",
      "自动识别出了哪些概念？",
    ],
    conclusion: "请前往 Project Graph 页面查看可视化图。",
    strength: "none",
    limitations_summary: "文字描述无法替代图形可视化。",
  });
}

function answerExplainSelected(
  bundle: ProjectBundle,
  q: string,
  selectedNodeId: string | null,
): AgentAnswer {
  if (!selectedNodeId) {
    return makeAnswer({
      question: q,
      answer: "当前没有选中节点。请在 Project Graph 中点击一个节点，然后再问这个问题。",
      follow_up_questions: ["这个项目整体实现了什么？", "画出项目理解图"],
      conclusion: "未选中节点。",
      strength: "none",
      limitations_summary: "需要先在图中选择一个节点。",
    });
  }

  const node = bundle.graph.nodes.find((n) => n.node_id === selectedNodeId);
  if (!node) {
    return makeAnswer({
      question: q,
      answer: `未找到节点 "${selectedNodeId}"。`,
      follow_up_questions: SUGGESTED_QUESTIONS,
      conclusion: `节点 "${selectedNodeId}" 不在 bundle 中。`,
      strength: "none",
      limitations_summary: "节点可能属于聚合节点或已移除。",
    });
  }

  // Use the concept mapping answer for concept nodes
  if (node.kind === "concept") {
    return answerConceptMapping(bundle, node.label, q);
  }

  // For claim nodes
  if (node.kind === "mapping_claim") {
    return answerConceptMapping(bundle, node.concept ?? "", q);
  }

  // For project node
  if (node.kind === "project") {
    return answerProjectSummary(bundle, q);
  }

  return makeAnswer({
    question: q,
    answer: `节点 "${node.label}"（类型：${node.kind}，置信度：${node.confidence ?? "unknown"}）。请在 Understanding Card 页面查看完整分析。`,
    referenced_nodes: [node.node_id],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: SUGGESTED_QUESTIONS.slice(0, 3),
    conclusion: `节点 "${node.label}"（${node.kind}），置信度 ${node.confidence ?? "unknown"}。`,
    strength: node.confidence ?? "unknown",
    limitations_summary: "此节点类型的分析有限，请在 Understanding Card 查看详情。",
  });
}

/* ================================================================== */
/*  T036: Discovery Quality Agent Answers                             */
/* ================================================================== */

function answerSelectionReasons(bundle: ProjectBundle, q: string): AgentAnswer {
  const chainData = bundle.index.evidence_chain;
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");

  if (!chainData || Object.keys(chainData).length === 0) {
    return makeAnswer({
      question: q,
      answer: `当前 bundle 没有 V2 evidence chain 数据，无法提供选择原因。\n\n识别出的概念：\n` +
        concepts.map((c) => `  • ${c.label} (${c.confidence ?? "unknown"})`).join("\n"),
      referenced_nodes: concepts.map((c) => c.node_id),
      referenced_claims: [],
      referenced_evidence: [],
      follow_up_questions: ["自动识别出了哪些概念？", "哪些概念达到了 supported 置信度？"],
      conclusion: "无 V2 选择原因数据。",
      strength: "none",
      limitations_summary: "需要运行带有 V2 discovery 的 trace 才能获取选择原因。",
    });
  }

  const entries = Object.entries(chainData);
  const withReason = entries.filter(([_, chain]: [string, any]) => (chain as any).selection_reason);

  const answer = `概念选择原因分析（${withReason.length}/${entries.length} 概念有选择原因）：\n\n` +
    entries.map(([concept, chain]: [string, any]) => {
      const c = chain as any;
      return `• ${concept}\n` +
        (c.selection_reason ? `  选择原因：${c.selection_reason}\n` : "  选择原因：未记录\n") +
        (c.why_core_or_secondary ? `  分类：${c.why_core_or_secondary === "core" ? "核心概念" : "次要概念"}\n` : "") +
        (c.confidence_explanation ? `  置信度说明：${c.confidence_explanation}\n` : "") +
        (c.aliases && c.aliases.length > 0 ? `  别名：${c.aliases.join("、")}\n` : "");
    }).join("\n");

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: concepts.map((c) => c.node_id),
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "发现质量如何？",
      "哪些概念缺少测试证据？",
      "自动识别出了哪些概念？",
    ],
    conclusion: `${withReason.length} 个概念有选择原因记录。`,
    strength: withReason.length > 0 ? "supported" : "inferred",
    limitations_summary: "选择原因由 V2 discovery 自动生成，仅反映静态分析结果。",
  });
}

function answerMissingTestEvidence(bundle: ProjectBundle, q: string): AgentAnswer {
  const chainData = bundle.index.evidence_chain;
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");

  const missingTest: string[] = [];
  const hasTest: string[] = [];

  for (const c of concepts) {
    const evEntries = Object.entries(bundle.index.evidence_index)
      .filter(([, v]) => v.concept === c.label);
    const hasTestEv = evEntries.some(([, v]) =>
      v.source_type.startsWith("test_") || (v.file_path?.includes("test") ?? false)
    );

    // Also check evidence chain if available
    if (chainData) {
      const chain = (chainData as any)[c.label] as any;
      if (chain?.missing && chain.missing.some((m: string) => m.toLowerCase().includes("test"))) {
        missingTest.push(c.label);
        continue;
      }
    }

    if (hasTestEv) {
      hasTest.push(c.label);
    } else {
      missingTest.push(c.label);
    }
  }

  const answer = `测试证据分析：\n\n` +
    `缺少测试证据的概念 (${missingTest.length})：\n` +
    (missingTest.length > 0
      ? missingTest.map((name) => `  • ${name}`).join("\n")
      : "  所有概念都有测试证据") +
    `\n\n有测试证据的概念 (${hasTest.length})：\n` +
    (hasTest.length > 0
      ? hasTest.map((name) => `  • ${name}`).join("\n")
      : "  无");

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: concepts.map((c) => c.node_id),
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念缺失 RTL 证据？",
      "发现质量如何？",
      "这个项目整体实现了什么？",
    ],
    conclusion: `${missingTest.length} 个概念缺少测试证据（共 ${concepts.length} 个概念）。`,
    strength: missingTest.length === 0 ? "supported" : "inferred",
    limitations_summary: "测试证据基于文件路径和 source_type 匹配，可能遗漏非标准命名的测试。",
  });
}

function answerDiscoveryQuality(bundle: ProjectBundle, q: string): AgentAnswer {
  const chainData = bundle.index.evidence_chain;
  const { nodes } = bundle.graph;
  const concepts = nodes.filter((n) => n.kind === "concept");
  const claims = nodes.filter((n) => n.kind === "mapping_claim");
  const supported = claims.filter((c) => c.confidence === "supported");
  const inferred = claims.filter((c) => c.confidence === "inferred");

  let answer = `发现质量概要：\n\n` +
    `• 概念数量：${concepts.length}\n` +
    `• 映射声明：${claims.length}（${supported.length} supported，${inferred.length} inferred）\n` +
    `• 证据总数：${bundle.metadata.evidence_items}\n`;

  if (chainData && Object.keys(chainData).length > 0) {
    const entries = Object.entries(chainData);
    const coreCount = entries.filter(([_, chain]: [string, any]) =>
      (chain as any).why_core_or_secondary === "core"
    ).length;
    const secondaryCount = entries.filter(([_, chain]: [string, any]) =>
      (chain as any).why_core_or_secondary === "secondary"
    ).length;
    const withMissing = entries.filter(([_, chain]: [string, any]) =>
      (chain as any).missing && (chain as any).missing.length > 0
    );

    answer += `\nV2 Discovery 质量指标：\n` +
      `• 核心概念：${coreCount}，次要概念：${secondaryCount}\n` +
      `• 有缺失证据的概念：${withMissing.length}/${entries.length}\n`;

    if (withMissing.length > 0) {
      answer += `\n缺失证据详情：\n` +
        withMissing.map(([concept, chain]: [string, any]) =>
          `  • ${concept}: ${(chain as any).missing.join(", ")}`
        ).join("\n");
    }
  } else {
    answer += `\n（当前无 V2 discovery 数据，无法提供详细质量分析。运行 V2 discovery 后可获取更多信息。）`;
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: concepts.map((c) => c.node_id),
    referenced_claims: claims.map((c) => c.node_id),
    referenced_evidence: [],
    follow_up_questions: [
      "为什么这些概念被选中？",
      "哪些概念缺少测试证据？",
      "哪些概念达到了 supported 置信度？",
    ],
    conclusion: `发现质量：${concepts.length} 个概念，${supported.length}/${claims.length} supported，${bundle.metadata.evidence_items} 条证据。`,
    strength: supported.length >= concepts.length * 0.7 ? "supported" : "mixed",
    limitations_summary: "质量评估基于静态分析，未经仿真或形式验证确认。",
  });
}

/* ================================================================== */
/*  T037: New Q&A patterns                                             */
/* ================================================================== */

function answerTestCoverage(bundle: ProjectBundle, q: string): AgentAnswer {
  const chainData = bundle.index.evidence_chain;
  if (!chainData || Object.keys(chainData).length === 0) {
    return makeAnswer({
      question: q,
      answer: "当前无 evidence chain 数据，无法分析测试覆盖。请运行 auto-trace 生成完整 bundle。",
      conclusion: "无数据",
      strength: "none",
      limitations_summary: "需要运行带 discovery 的 auto-trace。",
    });
  }

  const entries = Object.entries(chainData);
  const statusGroups: Record<string, string[]> = {};
  for (const [concept, chain] of entries) {
    const status = (chain as any).test_evidence_status || "unknown";
    if (!statusGroups[status]) statusGroups[status] = [];
    statusGroups[status].push(concept);
  }

  const statusLabels: Record<string, string> = {
    test_evidence_found: "已找到测试证据",
    test_extraction_not_supported: "测试提取未覆盖",
    test_files_exist_but_no_alias_match: "测试文件存在但无匹配",
    no_test_files: "无测试文件",
  };

  let answer = `测试覆盖分析（共 ${entries.length} 个概念）：\n\n`;
  for (const [status, concepts] of Object.entries(statusGroups)) {
    const label = statusLabels[status] || status;
    answer += `• ${label} (${concepts.length})：${concepts.slice(0, 6).join("、")}${concepts.length > 6 ? " ..." : ""}\n`;
  }

  const noExtraction = statusGroups["test_extraction_not_supported"]?.length ?? 0;
  if (noExtraction > 0) {
    answer += `\n注：${noExtraction} 个概念的测试提取尚未支持。概念 trace 目前仅扫描 L5/L6/RTL，` +
      `测试文件通过 discovery pipeline 发现但不纳入 trace evidence。`;
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念缺少测试证据？",
      "发现质量如何？",
      "精确率和召回率是多少？",
    ],
    conclusion: `测试覆盖：${noExtraction} 个概念测试提取未覆盖，${statusGroups["test_evidence_found"]?.length ?? 0} 个已找到测试证据。`,
    strength: noExtraction === 0 ? "supported" : "mixed",
    limitations_summary: "测试覆盖分析基于 evidence chain 的 test_evidence_status 字段。",
  });
}

function answerPrecisionRecall(bundle: ProjectBundle, q: string): AgentAnswer {
  const evalData = (bundle.discovery_eval_result as any) ?? (bundle.index as any).discovery_eval_result;
  if (!evalData) {
    return makeAnswer({
      question: q,
      answer: "当前无 discovery eval 数据。请使用 --golden-spec 运行 auto-trace 以生成精确率/召回率指标。",
      conclusion: "无评估数据",
      strength: "none",
      limitations_summary: "需要 golden spec 基准。",
    });
  }

  const prec = evalData.selected_precision_like ?? 0;
  const rec = evalData.selected_recall_like ?? 0;
  const allPrec = evalData.precision_like ?? 0;
  const allRec = evalData.recall_like ?? 0;

  const precGate = prec >= 0.5 ? "✅ 达标" : "❌ 未达标";
  const recGate = rec >= 0.75 ? "✅ 达标" : "❌ 未达标";

  let answer = `Discovery 评估指标：\n\n` +
    `**Selected Top ${evalData.max_concepts ?? 12}**\n` +
    `• 精确率 (selected_precision_like): ${(prec * 100).toFixed(1)}% ${precGate}\n` +
    `• 召回率 (selected_recall_like): ${(rec * 100).toFixed(1)}% ${recGate}\n\n` +
    `**全部候选**\n` +
    `• 精确率 (precision_like): ${(allPrec * 100).toFixed(1)}%\n` +
    `• 召回率 (recall_like): ${(allRec * 100).toFixed(1)}%\n\n`;

  if (evalData.excluded_terms_selected?.length > 0) {
    answer += `⚠️ 排除项泄漏：${evalData.excluded_terms_selected.join("、")}\n`;
  }
  if (evalData.missed_core?.length > 0) {
    answer += `❌ 遗漏核心概念：${evalData.missed_core.join("、")}\n`;
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些高分概念被过滤了？",
      "概念类别分布如何？",
      "测试覆盖分析",
    ],
    conclusion: `Selected 精确率 ${(prec * 100).toFixed(1)}%，召回率 ${(rec * 100).toFixed(1)}%。`,
    strength: prec >= 0.5 && rec >= 0.75 ? "supported" : "mixed",
    limitations_summary: "指标基于 golden spec 基准比对，反映自动发现的准确性和覆盖度。",
  });
}

function answerFilteredConcepts(bundle: ProjectBundle, q: string): AgentAnswer {
  const evalData = (bundle.index as any).discovery_eval_result;
  if (!evalData?.rejected_top_terms?.length) {
    return makeAnswer({
      question: q,
      answer: "无被过滤的高分概念数据，或所有高分概念均被选中。",
      conclusion: "无过滤数据",
      strength: "supported",
      limitations_summary: "需要 golden spec eval 数据。",
    });
  }

  let answer = `被过滤的高分概念（共 ${evalData.rejected_top_terms.length} 个）：\n\n`;
  for (const r of evalData.rejected_top_terms.slice(0, 10)) {
    answer += `• ${r.name}（score=${r.score}，类别=${r.category}）：${r.reason}\n`;
  }

  answer += `\n这些概念因类别不在 core_like/secondary_like 而被过滤，不影响 auto-trace 选择。`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "概念类别分布如何？",
      "精确率和召回率是多少？",
      "发现质量如何？",
    ],
    conclusion: `${evalData.rejected_top_terms.length} 个高分概念因类别被过滤。`,
    strength: "supported",
    limitations_summary: "过滤基于概念类别规则，确保 auto-trace 选取最有意义的概念。",
  });
}

function answerCategoryDistribution(bundle: ProjectBundle, q: string): AgentAnswer {
  const candidates = (bundle.concept_candidates as any) ?? (bundle.index as any).concept_candidates;
  if (!candidates?.length) {
    return makeAnswer({
      question: q,
      answer: "无 concept candidates 数据。请运行 auto-discovery 生成候选列表。",
      conclusion: "无候选数据",
      strength: "none",
      limitations_summary: "需要 discovery 数据。",
    });
  }

  const catGroups: Record<string, number> = {};
  for (const c of candidates) {
    const cat = c.category || "unknown";
    catGroups[cat] = (catGroups[cat] || 0) + 1;
  }

  const catOrder = ["core_like", "secondary_like", "parameter_like", "weak_candidate", "test_artifact", "framework_artifact", "generic_variable"];
  const catLabels: Record<string, string> = {
    core_like: "核心概念",
    secondary_like: "次要概念",
    parameter_like: "参数型",
    weak_candidate: "弱候选",
    test_artifact: "测试产物",
    framework_artifact: "框架产物",
    generic_variable: "通用变量",
  };

  let answer = `概念类别分布（共 ${candidates.length} 个候选）：\n\n`;
  for (const cat of catOrder) {
    if (catGroups[cat]) {
      const bar = "█".repeat(Math.round(catGroups[cat] / candidates.length * 20));
      answer += `• ${catLabels[cat] || cat}: ${catGroups[cat]} ${bar}\n`;
    }
  }

  const selectable = (catGroups["core_like"] ?? 0) + (catGroups["secondary_like"] ?? 0);
  answer += `\n可选概念（core_like + secondary_like）：${selectable} 个`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些高分概念被过滤了？",
      "精确率和召回率是多少？",
      "为什么这些概念被选中？",
    ],
    conclusion: `类别分布：${selectable} 个可选，${candidates.length - selectable} 个被过滤。`,
    strength: "supported",
    limitations_summary: "类别由 V2.1 分类规则自动判定。",
  });
}

function answerGoldenMatch(bundle: ProjectBundle, q: string): AgentAnswer {
  const evalData = (bundle.index as any).discovery_eval_result;
  if (!evalData) {
    return makeAnswer({
      question: q,
      answer: "无 golden spec 匹配数据。请使用 --golden-spec 运行 auto-trace。",
      conclusion: "无 golden 数据",
      strength: "none",
      limitations_summary: "需要 golden spec 基准。",
    });
  }

  let answer = `Golden Spec 匹配分析：\n\n` +
    `**基准概念**\n` +
    `• 核心概念：${evalData.golden_core_count ?? "?"} 个\n` +
    `• 次要概念：${evalData.golden_secondary_count ?? "?"} 个\n\n`;

  if (evalData.matched_core?.length > 0) {
    answer += `**匹配的核心概念** (${evalData.matched_core.length}/${evalData.golden_core_count})\n`;
    for (const c of evalData.matched_core) {
      answer += `  ✅ ${c}\n`;
    }
  }
  if (evalData.missed_core?.length > 0) {
    answer += `\n**遗漏的核心概念**\n`;
    for (const c of evalData.missed_core) {
      answer += `  ❌ ${c}\n`;
    }
  }
  if (evalData.matched_secondary?.length > 0) {
    answer += `\n**匹配的次要概念** (${evalData.matched_secondary.length}/${evalData.golden_secondary_count})\n`;
    for (const c of evalData.matched_secondary) {
      answer += `  ✅ ${c}\n`;
    }
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "精确率和召回率是多少？",
      "测试覆盖分析",
      "发现质量如何？",
    ],
    conclusion: `Golden 匹配：核心 ${evalData.matched_core?.length ?? 0}/${evalData.golden_core_count ?? "?"}，次要 ${evalData.matched_secondary?.length ?? 0}/${evalData.golden_secondary_count ?? "?"}。`,
    strength: (evalData.missed_core?.length ?? 0) === 0 ? "supported" : "mixed",
    limitations_summary: "匹配基于名称和别名比对，不涉及语义分析。",
  });
}

/* ================================================================== */
/*  T038: Semantic Summary driven Agent Q&A                           */
/* ================================================================== */

function answerPipelineStages(bundle: ProjectBundle, q: string): AgentAnswer {
  const ss = bundle.semantic_summary;
  if (!ss || ss.pipeline_stages.length === 0) {
    return makeAnswer({
      question: q,
      answer: "当前 bundle 没有 pipeline stages 数据。请加载 T038 semantic summary bundle。",
      conclusion: "无 pipeline 数据",
      strength: "none",
      limitations_summary: "需要 T038 semantic summary。",
    });
  }

  let answer = `项目 "${ss.project_id}" 的 Pipeline Stages（${ss.pipeline_stages.length} 个）：\n\n`;
  for (const stage of ss.pipeline_stages) {
    answer += `• ${stage.label}\n`;
    answer += `  ID: ${stage.stage_id} | 源文件: ${stage.source_files.length} 个\n`;
    answer += `  相关概念: ${stage.related_concepts.slice(0, 5).join("、")}${stage.related_concepts.length > 5 ? " ..." : ""}\n`;
    answer += `  相关 RTL: ${stage.related_rtl_modules.slice(0, 5).join("、")}${stage.related_rtl_modules.length > 5 ? " ..." : ""}\n`;
    answer += `  置信度: ${stage.confidence}\n\n`;
  }

  answer += `项目目的: ${ss.top_level_purpose}`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: ss.pipeline_stages.map((s) => s.stage_id),
    referenced_claims: [],
    referenced_evidence: ss.pipeline_stages.flatMap((s) => s.evidence_ids).slice(0, 10),
    follow_up_questions: [
      "哪些概念是核心概念？",
      "测试覆盖分析",
      "项目的不确定性有哪些？",
    ],
    conclusion: `${ss.pipeline_stages.length} 个 pipeline stages，项目类型: ${ss.project_kind_hint}。`,
    strength: "supported",
    limitations_summary: "Pipeline stages 基于文件结构推断。",
  });
}

function answerImplementationDetails(bundle: ProjectBundle, q: string): AgentAnswer {
  const ss = bundle.semantic_summary;
  if (!ss || ss.implementation_modules.length === 0) {
    return makeAnswer({
      question: q,
      answer: "当前无 implementation modules 数据。",
      conclusion: "无实现细节数据",
      strength: "none",
      limitations_summary: "需要 T038 semantic summary。",
    });
  }

  let answer = `Implementation Modules（${ss.implementation_modules.length} 个）：\n\n`;
  for (const mod of ss.implementation_modules.slice(0, 10)) {
    answer += `• ${mod.module_or_file}\n`;
    answer += `  角色: ${mod.role_hint}\n`;
    answer += `  实现概念: ${mod.concepts_realized.join("、") || "无"}\n`;
    answer += `  证据强度: strong=${mod.strong_evidence_count}, medium=${mod.medium_evidence_count}, weak=${mod.weak_evidence_count}\n`;
    if (mod.is_shared_by_multiple_concepts) {
      answer += `  [共享模块] 被多个概念共用\n`;
    }
    answer += `\n`;
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些 RTL 文件承载了多个概念？",
      "pipeline 有哪些阶段？",
      "项目的不确定性有哪些？",
    ],
    conclusion: `${ss.implementation_modules.length} 个 implementation modules。`,
    strength: "supported",
    limitations_summary: "模块聚合基于文件路径和 claim 映射。",
  });
}

function answerInferredAreas(bundle: ProjectBundle, q: string): AgentAnswer {
  const ss = bundle.semantic_summary;
  if (!ss) {
    return answerUncertainty(bundle, q);
  }

  const unc = ss.uncertainty_summary;
  const items = [
    ...(unc.inferred_claims?.length ? [`推断 Claims: ${unc.inferred_claims.join("、")}`] : []),
    ...(unc.weak_only_links?.length ? [`弱链接: ${unc.weak_only_links.join("、")}`] : []),
    ...(unc.naming_only_links?.length ? [`仅命名链接: ${unc.naming_only_links.join("、")}`] : []),
    ...(unc.missing_l5_l6?.length ? [`缺失 L5/L6: ${unc.missing_l5_l6.join("、")}`] : []),
    ...(unc.missing_rtl?.length ? [`缺失 RTL: ${unc.missing_rtl.join("、")}`] : []),
    ...(unc.missing_test_evidence?.length ? [`缺失测试证据: ${unc.missing_test_evidence.join("、")}`] : []),
  ];

  const answer = items.length > 0
    ? `不确定性 / 推断区域分析：\n\n${items.map((s) => `• ${s}`).join("\n")}`
    : "当前无显著不确定性或推断区域。所有概念均有充分证据支持。";

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念达到了 supported 置信度？",
      "测试覆盖分析",
      "pipeline 有哪些阶段？",
    ],
    conclusion: items.length > 0 ? `发现 ${items.length} 类不确定性。` : "无显著不确定性。",
    strength: items.length > 0 ? "inferred" : "supported",
    limitations_summary: "不确定性基于证据质量静态分析。",
  });
}

function answerDataProvenance(bundle: ProjectBundle, q: string): AgentAnswer {
  const ss = bundle.semantic_summary;
  if (!ss) {
    return makeAnswer({
      question: q,
      answer: `数据来源说明：\n\n` +
        `• project_understanding_graph.json — 节点和边结构\n` +
        `• project_understanding_index.json — 概念/claim/证据索引\n` +
        `• run_metadata.json — 运行元数据\n` +
        `• concept_candidates.json — 自动发现的概念候选（T037）\n` +
        `• discovery_eval_result.json — Golden spec 评估结果（T037）\n\n` +
        `加载 T038 semantic summary 可获取更详细的数据来源信息。`,
      conclusion: "数据来源基于 T037 artifacts。",
      strength: "supported",
      limitations_summary: "证据来自静态代码分析，未经仿真验证。",
    });
  }

  const prov = ss.source_provenance;
  const answer = `Semantic Summary 数据来源：\n\n` +
    `• 生成时间: ${prov.generation_timestamp}\n` +
    `• 生成器: ${prov.generator}\n` +
    `• 来源文件:\n` +
    prov.summary_generated_from.map((f) => `  - ${f}`).join("\n") +
    `\n\n所有结论均基于上述静态分析产物，未经仿真或形式验证确认。`;

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "pipeline 有哪些阶段？",
      "项目的不确定性有哪些？",
      "测试覆盖分析",
    ],
    conclusion: `数据来源于 ${prov.summary_generated_from.length} 个 artifact 文件。`,
    strength: "supported",
    limitations_summary: "所有数据来自静态分析，未经仿真验证。",
  });
}

function answerWhySelected(bundle: ProjectBundle, conceptName: string, q: string): AgentAnswer {
  const ss = bundle.semantic_summary;
  if (!ss) {
    return makeAnswer({
      question: q,
      answer: `未加载 semantic summary，无法提供选择原因。`,
      conclusion: "无 semantic summary 数据",
      strength: "none",
      limitations_summary: "需要 T038 semantic summary。",
    });
  }

  const cc = ss.core_concepts.find((c) => c.canonical_name === conceptName);
  if (!cc) {
    return makeAnswer({
      question: q,
      answer: `概念 "${conceptName}" 不在 core concepts 列表中。`,
      conclusion: `"${conceptName}" 不是核心概念。`,
      strength: "none",
      limitations_summary: "该概念可能未被选中或已被过滤。",
    });
  }

  const answer = `概念 "${cc.display_name}" (${cc.canonical_name}) 被选中的原因：\n\n` +
    `• 类别: ${cc.category}\n` +
    `• 项目角色: ${cc.role_in_project}\n` +
    `• 选择原因: ${cc.why_selected}\n` +
    `• 别名: ${cc.aliases.join("、") || "无"}\n` +
    `• 证据分布: L5/L6=${cc.l5_l6_evidence_count}, RTL=${cc.rtl_evidence_count}, Test=${cc.test_evidence_count}\n` +
    `• 置信度: ${cc.confidence}\n` +
    (cc.limitations.length > 0 ? `• 局限: ${cc.limitations.join("；")}\n` : "");

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "pipeline 有哪些阶段？",
      "项目的不确定性有哪些？",
      "测试覆盖分析",
    ],
    conclusion: `"${cc.display_name}" 因 ${cc.why_selected} 被选中，置信度 ${cc.confidence}。`,
    strength: cc.confidence,
    limitations_summary: cc.limitations.length > 0 ? cc.limitations.join("；") : "无已知局限。",
  });
}

/* ================================================================== */
/*  T039/T040: Pipeline / Dataflow Agent Answers                      */
/* ================================================================== */

function answerPipelinePath(bundle: ProjectBundle, q: string): AgentAnswer {
  const pv = bundle.semantic_pipeline_view;
  if (!pv) {
    return makeAnswer({
      question: q,
      answer: "当前 bundle 没有 pipeline view 数据。请加载 T039+ bundle 或重新生成项目 trace。",
      conclusion: "无 pipeline view 数据",
      strength: "none",
      limitations_summary: "需要 T039/T040 semantic pipeline view artifact。",
    });
  }

  // Try to match a specific concept from the question
  const concepts = pv.pipeline_summary.concepts_with_full_pipeline;
  let targetConcept = "";
  for (const c of concepts) {
    if (q.includes(c)) {
      targetConcept = c;
      break;
    }
  }

  // If no specific concept matched, give an overview of all full-pipeline concepts
  if (!targetConcept) {
    const full = pv.pipeline_summary.concepts_with_full_pipeline;
    const gaps = pv.pipeline_summary.concepts_with_gaps;
    const answer = `Pipeline 路径概览：\n\n` +
      `具有完整跨阶段证据链的概念 (${full.length})：\n` +
      (full.length > 0
        ? full.map((c) => `  • ${c}`).join("\n")
        : "  无") +
      `\n\n证据链存在缺口的概念 (${gaps.length})：\n` +
      (gaps.length > 0
        ? gaps.map((c) => `  • ${c}`).join("\n")
        : "  无");

    return makeAnswer({
      question: q,
      answer,
      referenced_nodes: [],
      referenced_claims: [],
      referenced_evidence: [],
      follow_up_questions: [
        "哪些概念跨了所有阶段？",
        "dataflow 是怎样的？",
        "哪些概念缺失 RTL 证据？",
      ],
      conclusion: `${full.length} 个概念具有完整 pipeline，${gaps.length} 个存在缺口。`,
      strength: full.length > gaps.length ? "supported" : "mixed",
      limitations_summary: "Pipeline 路径基于静态证据链推断。",
    });
  }

  // Specific concept pipeline path
  const lanes = pv.lanes;
  let answer = `概念 "${targetConcept}" 的 Pipeline 路径：\n\n`;

  for (const lane of lanes) {
    const laneNodes = lane.nodes.filter(
      (n) => n.concept === targetConcept || n.label === targetConcept
    );
    if (laneNodes.length > 0) {
      answer += `【${lane.label}】\n`;
      for (const n of laneNodes) {
        answer += `  • ${n.label} (${n.kind}, ${n.confidence ?? "unknown"})\n`;
      }
    }
  }

  // Find cross-stage edges for this concept
  const conceptEdges = pv.cross_stage_edges.filter(
    (e) => e.from_node_id.includes(targetConcept) || e.to_node_id.includes(targetConcept)
  );
  if (conceptEdges.length > 0) {
    answer += `\n跨阶段连接：\n`;
    for (const e of conceptEdges) {
      answer += `  ${e.from_lane} → ${e.to_lane} | ${e.edge_type} (${e.confidence})\n`;
    }
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念跨了所有阶段？",
      "dataflow 是怎样的？",
      "项目的不确定性有哪些？",
    ],
    conclusion: `"${targetConcept}" 的 pipeline 路径已列出。`,
    strength: "supported",
    limitations_summary: "路径基于 evidence chain 的 stage 分类。",
  });
}

function answerFullPipelineConcepts(bundle: ProjectBundle, q: string): AgentAnswer {
  const pv = bundle.semantic_pipeline_view;
  const ss = bundle.semantic_summary;

  if (!pv && !ss) {
    return makeAnswer({
      question: q,
      answer: "当前无 pipeline view 或 semantic summary 数据。",
      conclusion: "无数据",
      strength: "none",
      limitations_summary: "需要 T039+ artifact。",
    });
  }

  const full = pv?.pipeline_summary.concepts_with_full_pipeline ?? [];
  const cross = ss?.l5_l6_to_rtl_summary.summary.concepts_with_cross_stage_mapping ?? 0;

  const answer = `跨阶段概念分析：\n\n` +
    `具有完整 L5/L6 → RTL 证据链的概念 (${full.length})：\n` +
    (full.length > 0
      ? full.map((c) => `  • ${c}`).join("\n")
      : "  无") +
    `\n\n` +
    (cross > 0
      ? `L5/L6-to-RTL 映射总结：${cross} 个概念具有跨阶段映射（来自 semantic summary）。`
      : "无 L5/L6-to-RTL 映射总结数据。");

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "某个概念的 pipeline 路径是什么？",
      "dataflow 是怎样的？",
      "哪些概念缺失 RTL 证据？",
    ],
    conclusion: `${full.length} 个概念跨了所有阶段。`,
    strength: full.length > 0 ? "supported" : "inferred",
    limitations_summary: "跨阶段判断基于 evidence chain 的 stage 覆盖。",
  });
}

function answerDataflowSummary(bundle: ProjectBundle, q: string): AgentAnswer {
  const pv = bundle.semantic_pipeline_view;
  if (!pv) {
    return makeAnswer({
      question: q,
      answer: "当前无 pipeline view 数据。请加载 T039+ bundle。",
      conclusion: "无数据",
      strength: "none",
      limitations_summary: "需要 semantic_pipeline_view.json。",
    });
  }

  const summary = pv.pipeline_summary;
  const lanes = pv.lanes;

  let answer = `Pipeline Dataflow 概览：\n\n`;
  answer += `阶段节点分布：\n`;
  for (const lane of lanes) {
    const concepts = lane.nodes.filter((n) => n.kind === "concept").length;
    const evidence = lane.nodes.filter((n) => n.kind === "evidence").length;
    answer += `  • ${lane.label}: ${concepts} 概念, ${evidence} 证据\n`;
  }

  answer += `\n跨阶段连接：${summary.cross_stage_claim_count} 条 claim/realize 边，`;
  answer += `${summary.dataflow_edge_count} 条总跨阶段边。\n`;

  if (summary.concepts_with_full_pipeline.length > 0) {
    answer += `\n完整 pipeline 概念 (${summary.concepts_with_full_pipeline.length})：` +
      summary.concepts_with_full_pipeline.slice(0, 8).join("、") +
      (summary.concepts_with_full_pipeline.length > 8 ? " ..." : "") +
      "\n";
  }

  if (summary.concepts_with_gaps.length > 0) {
    answer += `\n存在证据缺口的概念 (${summary.concepts_with_gaps.length})：` +
      summary.concepts_with_gaps.slice(0, 8).join("、") +
      (summary.concepts_with_gaps.length > 8 ? " ..." : "") +
      "\n";
  }

  return makeAnswer({
    question: q,
    answer,
    referenced_nodes: [],
    referenced_claims: [],
    referenced_evidence: [],
    follow_up_questions: [
      "哪些概念跨了所有阶段？",
      "某个概念的 pipeline 路径是什么？",
      "项目的不确定性有哪些？",
    ],
    conclusion: `Dataflow: ${summary.total_nodes} 节点, ${summary.total_cross_stage_edges} 跨阶段边。`,
    strength: summary.concepts_with_full_pipeline.length > 0 ? "supported" : "inferred",
    limitations_summary: "Dataflow 基于静态证据链，非动态仿真结果。",
  });
}
