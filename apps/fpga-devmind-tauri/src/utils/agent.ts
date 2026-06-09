import type { ProjectBundle, AgentAnswer } from "../types";
import { aggregateRtl } from "./transforms";

/* ================================================================== */
/*  Deterministic Agent Q&A (no LLM)                                  */
/* ================================================================== */

const SUGGESTED_QUESTIONS = [
  "这个项目整体实现了什么？",
  "peak_idx 是怎么从 L5/L6 映射到 RTL 的？",
  "cfo 对应哪些 RTL？",
  "smooth_detect 为什么是 inferred？",
  "哪些 RTL 文件承载了多个概念？",
  "哪些证据最关键？",
  "哪些地方还不能确认？",
  "画出项目理解图",
  "解释当前选中节点",
];

export { SUGGESTED_QUESTIONS };

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
  if (q.includes("整体") && (q.includes("实现") || q.includes("什么"))) {
    return answerProjectSummary(bundle, q);
  }

  if (q.includes("peak_idx") && (q.includes("映射") || q.includes("L5") || q.includes("RTL"))) {
    return answerConceptMapping(bundle, "peak_idx", q);
  }

  if (q.includes("cfo") && (q.includes("RTL") || q.includes("对应") || q.includes("哪些"))) {
    return answerConceptRtl(bundle, "cfo", q);
  }

  if (q.includes("smooth_detect") && (q.includes("inferred") || q.includes("为什么") || q.includes("推断"))) {
    return answerWhyInferred(bundle, "smooth_detect", q);
  }

  if (q.includes("多个概念") && (q.includes("RTL") || q.includes("文件") || q.includes("承载"))) {
    return answerSharedRtl(bundle, q);
  }

  if (q.includes("最关键") || q.includes("关键证据") || q.includes("哪些证据")) {
    return answerKeyEvidence(bundle, q);
  }

  if (q.includes("不能确认") || q.includes("不确定") || q.includes("还不能")) {
    return answerUncertainty(bundle, q);
  }

  if (q.includes("图") || q.includes("画出") || q.includes("可视化")) {
    return answerDrawGraph(bundle, q);
  }

  if (q.includes("选中") || q.includes("解释") || q.includes("当前节点")) {
    return answerExplainSelected(bundle, q, selectedNodeId);
  }

  // Check for concept name in question
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

  const answer = `项目 "${bundle.graph.project_id}" 是一个 FPGA coarse sync（粗同步）模块，` +
    `主要实现 OFDM 系统中接收端的粗同步功能。\n\n` +
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
      "peak_idx 是怎么从 L5/L6 映射到 RTL 的？",
      "哪些 RTL 文件承载了多个概念？",
      "哪些地方还不能确认？",
    ],
    conclusion: `项目 "${bundle.graph.project_id}" 实现了 OFDM coarse sync，识别出 ${concepts.length} 个概念，${claims.length} 个映射声明（${supported.length} supported，${inferred.length} inferred），${bundle.metadata.evidence_items} 条证据。`,
    strength: supported.length > inferred.length ? "supported" : "mixed",
    limitations_summary: inferred.length > 0
      ? `有 ${inferred.length} 个推断性映射需进一步验证。仅基于静态分析，未经仿真或形式验证确认。`
      : "仅基于静态分析，未经仿真或形式验证确认。",
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
      `cfo 对应哪些 RTL？`,
      "哪些证据最关键？",
      "哪些地方还不能确认？",
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
      `${conceptName} 是怎么从 L5/L6 映射到 RTL 的？`,
      "哪些 RTL 文件承载了多个概念？",
      "哪些证据最关键？",
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
      "peak_idx 是怎么从 L5/L6 映射到 RTL 的？",
      "哪些地方还不能确认？",
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
      "哪些地方还不能确认？",
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
      "peak_idx 是怎么从 L5/L6 映射到 RTL 的？",
      "哪些地方还不能确认？",
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
      "smooth_detect 为什么是 inferred？",
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
      "peak_idx 是怎么从 L5/L6 映射到 RTL 的？",
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
