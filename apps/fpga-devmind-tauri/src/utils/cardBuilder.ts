import type { ProjectBundle, UnderstandingCard } from "../types";
import { aggregateRtl } from "./transforms";

export function buildUnderstandingCard(
  bundle: ProjectBundle,
  nodeId: string,
): UnderstandingCard | null {
  const node = bundle.graph.nodes.find((n) => n.node_id === nodeId);
  if (!node) return null;

  const graph = bundle.graph;
  const index = bundle.index;
  const { aggregates, claimToAgg } = aggregateRtl(graph.nodes, graph.edges);

  const related_concepts: UnderstandingCard["related_concepts"] = [];
  const related_claims: UnderstandingCard["related_claims"] = [];
  const related_rtl: UnderstandingCard["related_rtl"] = [];
  const top_evidence: UnderstandingCard["top_evidence"] = [];
  const limitations: string[] = [];
  const next_steps: string[] = [];
  let summary = "";
  let role_in_project = "";
  let implementation_path = "";
  let evidence_count = 0;

  switch (node.kind) {
    case "project": {
      const concepts = graph.nodes.filter((n) => n.kind === "concept");
      const claims = graph.nodes.filter((n) => n.kind === "mapping_claim");
      const supported = claims.filter((c) => c.confidence === "supported").length;
      const inferred = claims.filter((c) => c.confidence === "inferred").length;
      summary = `项目 "${node.label}" 识别出 ${concepts.length} 个概念（${concepts.map((c) => c.label).join("、")}），` +
        `${claims.length} 个 mapping claim（${supported} supported, ${inferred} inferred），` +
        `${bundle.metadata.evidence_items} 条证据。`;
      role_in_project = "项目根节点，包含所有概念理解和 RTL 映射。";
      implementation_path = `概念层 → Claim 层 → RTL 实现层（共 ${aggregates.length} 个 RTL 文件/模块）。`;

      for (const c of concepts) {
        const claimForConcept = claims.find((cl) => cl.concept === c.label);
        related_concepts.push({
          id: c.node_id,
          label: c.label,
          confidence: claimForConcept?.confidence ?? c.confidence ?? "unknown",
        });
      }

      next_steps.push("点击左侧 Project Graph 查看可视化理解图");
      next_steps.push("在图中点击 Concept 节点查看详细映射");
      next_steps.push("使用 Agent 问答提问项目相关问题");
      break;
    }
    case "concept": {
      const claims = graph.nodes.filter(
        (n) => n.kind === "mapping_claim" && n.concept === node.label,
      );
      const conceptInfo = index.concept_index[node.label];
      evidence_count = conceptInfo?.evidence ?? 0;
      const rtlCount = conceptInfo?.rtl_objects ?? 0;

      // Find RTL aggregates for this concept's claims
      for (const cl of claims) {
        const aggIds = claimToAgg.get(cl.node_id) ?? [];
        for (const aid of aggIds) {
          const agg = aggregates.find((a) => a.id === aid);
          if (agg) {
            related_rtl.push({ id: agg.id, label: agg.label, file_path: agg.file_path, kind: "rtl_aggregate" });
          }
        }
      }

      const conf = node.confidence ?? "unknown";
      summary = `概念 "${node.label}"：${claims.length} 个 mapping claim，` +
        `${evidence_count} 条证据，${related_rtl.length} 个 RTL 文件/模块。置信度：${conf}。`;

      role_in_project = `设计中的关键概念，代表一个具体的信号处理/计算功能。` +
        `在 coarse sync 流程中承担 ${node.label === "peak_idx" ? "峰值检测索引计算" : node.label === "cfo" ? "载波频偏估计" : node.label === "smooth_detect" ? "平滑检测" : "特定功能"}。`;

      implementation_path = claims.length > 0 && related_rtl.length > 0
        ? `L5/L6 模型 (${conceptInfo?.evidence ?? 0} 处引用) → Claim "${claims[0]?.label}" → RTL: ${related_rtl.map((r) => r.label).join(", ")}`
        : "暂未找到完整实现路径。";

      for (const cl of claims) {
        related_claims.push({
          id: cl.node_id,
          label: cl.label,
          concept: cl.concept ?? "",
          confidence: cl.confidence ?? "unknown",
          bridge_kind: cl.bridge_kind ?? "?",
        });
      }

      // Top evidence
      const evEntries = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === node.label)
        .sort((a, b) => {
          const order: Record<string, number> = { strong: 0, medium: 1, weak: 2 };
          return (order[a[1].strength ?? "weak"] ?? 3) - (order[b[1].strength ?? "weak"] ?? 3);
        })
        .slice(0, 5);
      for (const [id, ev] of evEntries) {
        top_evidence.push({ id, source_type: ev.source_type, file_path: ev.file_path, symbol: ev.symbol, strength: ev.strength });
      }

      if (conf === "unknown") limitations.push("概念置信度为 unknown，缺乏直接证据支持。");
      if (claims.length === 0) limitations.push("暂无 mapping claim，无法确认 RTL 映射。");
      if (rtlCount === 0) limitations.push("未找到相关 RTL 实现。");
      if (conf === "inferred") limitations.push("映射为推断性，可能存在假阳性。");

      next_steps.push(`查看 Evidence 页面了解 ${evidence_count} 条证据详情`);
      next_steps.push("点击相关 Claim 查看映射推理过程");
      if (related_rtl.length > 0) next_steps.push("查看 RTL 实现的源码上下文");
      break;
    }
    case "mapping_claim": {
      const concept = node.concept ?? "?";
      const bridge = node.bridge_kind ?? "?";
      const conceptInfo = index.concept_index[concept];
      evidence_count = conceptInfo?.evidence ?? 0;

      const aggIds = claimToAgg.get(node.node_id) ?? [];
      for (const aid of aggIds) {
        const agg = aggregates.find((a) => a.id === aid);
        if (agg) {
          related_rtl.push({ id: agg.id, label: agg.label, file_path: agg.file_path, kind: "rtl_aggregate" });
        }
      }

      const conceptNode = graph.nodes.find((n) => n.kind === "concept" && n.label === concept);
      if (conceptNode) {
        related_concepts.push({ id: conceptNode.node_id, label: conceptNode.label, confidence: conceptNode.confidence ?? "unknown" });
      }

      related_claims.push({
        id: node.node_id,
        label: node.label,
        concept,
        confidence: node.confidence ?? "unknown",
        bridge_kind: bridge,
      });

      summary = `Claim "${node.label}"：概念 ${concept} → RTL 映射。` +
        `bridge_kind=${bridge}，${related_rtl.length} 个 RTL 目标，` +
        `${evidence_count} 条证据。置信度：${node.confidence ?? "unknown"}。`;

      role_in_project = `声明概念 ${concept} 在 RTL 中有对应实现。` +
        (bridge === "calculation_role"
          ? "通过计算角色分析：L5/L6 中的数学运算在 RTL 中找到对应逻辑。"
          : bridge === "naming_plus_structure"
            ? "通过命名匹配和结构对比确认映射。"
            : bridge === "naming_only"
              ? "仅通过命名匹配推断。这可能产生假阳性。"
              : `映射方式：${bridge}。`);

      implementation_path = `概念 ${concept} → [${bridge}] → RTL: ${related_rtl.map((r) => r.label).join(", ") || "无"}`;

      // Top evidence
      const evEntries = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === concept)
        .sort((a, b) => {
          const order: Record<string, number> = { strong: 0, medium: 1, weak: 2 };
          return (order[a[1].strength ?? "weak"] ?? 3) - (order[b[1].strength ?? "weak"] ?? 3);
        })
        .slice(0, 5);
      for (const [id, ev] of evEntries) {
        top_evidence.push({ id, source_type: ev.source_type, file_path: ev.file_path, symbol: ev.symbol, strength: ev.strength });
      }

      if (bridge === "naming_only") limitations.push("bridge_kind 为 naming_only，仅有命名匹配，无结构/行为验证。这是弱证据。");
      if (node.confidence === "inferred") limitations.push("置信度为 inferred，需要更多证据确认。");
      if (related_rtl.length === 0) limitations.push("暂无 RTL 目标。");
      if (evidence_count === 0) limitations.push("无直接证据支持。");

      next_steps.push("查看 Evidence 了解证据强弱分布");
      next_steps.push("点击 RTL 目标查看源码上下文");
      break;
    }
    default: {
      // RTL aggregate or other
      summary = `节点 "${node.label}"（类型：${node.kind}）`;
      role_in_project = `RTL 实现层的组成部分。`;

      // Try to find as aggregate
      const agg = aggregates.find((a) => a.id === nodeId);
      if (agg) {
        evidence_count = agg.child_count;
        summary = `RTL 聚合 "${agg.label}"：包含 ${agg.child_count} 个 RTL 对象` +
          `（${agg.child_kinds.join("、")}）。涉及概念：${agg.concept_labels.join("、")}。`;
        role_in_project = agg.concept_labels.length > 1
          ? `承载多个概念（${agg.concept_labels.join("、")}）的共享 RTL 模块。`
          : `概念 ${agg.concept_labels[0] ?? "?"} 的 RTL 实现。`;
        implementation_path = `文件：${agg.file_path}`;
      }

      next_steps.push("切换到 Detail 模式查看具体 RTL 对象");
      break;
    }
  }

  return {
    node_id: node.node_id,
    label: node.label,
    kind: node.kind,
    confidence: node.confidence ?? "unknown",
    summary,
    role_in_project,
    related_concepts,
    related_claims,
    related_rtl,
    evidence_count,
    top_evidence,
    limitations,
    next_steps,
    implementation_path,
  };
}
