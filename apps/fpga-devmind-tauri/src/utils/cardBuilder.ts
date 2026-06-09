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
  const why_connected: UnderstandingCard["why_connected"] = [];
  const traceable_evidence: string[] = [];
  let summary = "";
  let role_in_project = "";
  let implementation_path = "";
  let evidence_count = 0;
  let raw_rtl_node_count = 0;
  const edge_types: string[] = [];

  // Collect edge types for this node
  for (const e of graph.edges) {
    if (e.from_node_id === nodeId || e.to_node_id === nodeId) {
      if (!edge_types.includes(e.edge_type)) edge_types.push(e.edge_type);
    }
  }

  switch (node.kind) {
    case "project": {
      const concepts = graph.nodes.filter((n) => n.kind === "concept");
      const claims = graph.nodes.filter((n) => n.kind === "mapping_claim");
      const supported = claims.filter((c) => c.confidence === "supported").length;
      const inferred = claims.filter((c) => c.confidence === "inferred").length;

      summary = `项目 "${node.label}" 识别出 ${concepts.length} 个概念（${concepts.map((c) => c.label).join("、")}），` +
        `${claims.length} 个 mapping claim（${supported} supported, ${inferred} inferred），` +
        `${bundle.metadata.evidence_items} 条证据，${aggregates.length} 个 RTL 文件/模块。`;
      role_in_project = "项目根节点，包含所有概念理解和 RTL 映射。Coarse sync 是 OFDM 接收端的粗同步模块，负责峰值检测、频偏估计和信号平滑。";
      implementation_path = `概念层 (${concepts.length}) → Claim 层 (${claims.length}) → RTL 实现层（${aggregates.length} 个聚合）。` +
        `\n路径：Project → Concept → MappingClaim → RTL Aggregate`;

      for (const c of concepts) {
        const claimForConcept = claims.find((cl) => cl.concept === c.label);
        related_concepts.push({
          id: c.node_id,
          label: c.label,
          confidence: claimForConcept?.confidence ?? c.confidence ?? "unknown",
        });
      }

      // Why connected
      for (const c of concepts) {
        why_connected.push({
          neighbor_id: c.node_id,
          edge_type: "contains",
          explanation: `项目包含概念 "${c.label}"`,
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

      // Count raw RTL nodes for this concept
      const conceptRtlEdges = graph.edges.filter(
        (e) => e.edge_type === "realizes" && claims.some((cl) => cl.node_id === e.from_node_id),
      );
      raw_rtl_node_count = conceptRtlEdges.length;

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

      // Deepen summary with L5/L6 details
      const l5Evidence = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === node.label && v.source_type === "concept_occurrence");
      const rtlEvidence = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === node.label && v.source_type === "rtl_source");

      summary = `概念 "${node.label}"：${claims.length} 个 mapping claim，` +
        `${evidence_count} 条证据（L5/L6 ${l5Evidence.length} 条，RTL ${rtlEvidence.length} 条），` +
        `${related_rtl.length} 个 RTL 文件/模块。置信度：${conf}。` +
        `\nL5/L6 引用：${l5Evidence.slice(0, 3).map(([, v]) => v.symbol ?? "?").join("、")}` +
        (l5Evidence.length > 3 ? ` 等 ${l5Evidence.length} 处` : "");

      role_in_project = `设计中的关键概念，代表一个具体的信号处理/计算功能。` +
        `在 coarse sync 流程中承担 ${node.label === "peak_idx" ? "峰值检测索引计算" : node.label === "cfo" ? "载波频偏估计" : node.label === "smooth_detect" ? "平滑检测" : "特定功能"}。` +
        `\nL5/L6 层：${l5Evidence.length > 0 ? `在 python_model 中有 ${l5Evidence.length} 处引用` : "无直接 L5/L6 引用"}` +
        `\nRTL 层：${rtlEvidence.length > 0 ? `${rtlEvidence.length} 处 RTL 源码证据` : "无直接 RTL 证据"}`;

      implementation_path = claims.length > 0 && related_rtl.length > 0
        ? `L5/L6 模型 (${l5Evidence.length} 处引用) → Claim "${claims[0]?.label}" [${claims[0]?.bridge_kind}] → RTL: ${related_rtl.map((r) => r.label).join(", ")}`
        : "暂未找到完整实现路径。";

      for (const cl of claims) {
        related_claims.push({
          id: cl.node_id,
          label: cl.label,
          concept: cl.concept ?? "",
          confidence: cl.confidence ?? "unknown",
          bridge_kind: cl.bridge_kind ?? "?",
        });
        why_connected.push({
          neighbor_id: cl.node_id,
          edge_type: "has_claim",
          explanation: `概念 "${node.label}" 有 mapping claim "${cl.label}"，bridge_kind=${cl.bridge_kind}`,
        });
      }

      // Why connected to RTL aggregates
      for (const r of related_rtl) {
        why_connected.push({
          neighbor_id: r.id,
          edge_type: "realizes",
          explanation: `Claim 声明概念 "${node.label}" 在 RTL 文件 ${r.label} 中有实现`,
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
        traceable_evidence.push(id);
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
          raw_rtl_node_count += agg.child_count;
        }
      }

      const conceptNode = graph.nodes.find((n) => n.kind === "concept" && n.label === concept);
      if (conceptNode) {
        related_concepts.push({ id: conceptNode.node_id, label: conceptNode.label, confidence: conceptNode.confidence ?? "unknown" });
        why_connected.push({
          neighbor_id: conceptNode.node_id,
          edge_type: "has_claim",
          explanation: `Claim 声明概念 ${concept} 映射到 RTL，bridge_kind=${bridge}`,
        });
      }

      related_claims.push({
        id: node.node_id,
        label: node.label,
        concept,
        confidence: node.confidence ?? "unknown",
        bridge_kind: bridge,
      });

      // Deepen: L5/L6 vs RTL evidence breakdown
      const l5Ev = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === concept && v.source_type === "concept_occurrence");
      const rtlEv = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === concept && v.source_type === "rtl_source");
      const namingEv = Object.entries(index.evidence_index)
        .filter(([, v]) => v.concept === concept && (v.source_type === "naming_match" || v.strength === "weak"));

      summary = `Claim "${node.label}"：概念 ${concept} → RTL 映射。` +
        `bridge_kind=${bridge}，${related_rtl.length} 个 RTL 目标（含 ${raw_rtl_node_count} 个原始 RTL 对象），` +
        `${evidence_count} 条证据（L5/L6 ${l5Ev.length}，RTL ${rtlEv.length}，命名 ${namingEv.length}）。` +
        `置信度：${node.confidence ?? "unknown"}。`;

      role_in_project = `声明概念 ${concept} 在 RTL 中有对应实现。` +
        (bridge === "calculation_role"
          ? "通过计算角色分析：L5/L6 中的数学运算在 RTL 中找到对应逻辑。\n" +
            "这意味着分析器追踪了概念在 python 模型中的计算角色（如峰值索引计算），并在 RTL 代码中找到执行相同功能的逻辑块。"
          : bridge === "naming_plus_structure"
            ? "通过命名匹配和结构对比确认映射。\n命名匹配找到同名信号/模块，结构对比验证了代码组织的一致性。"
            : bridge === "naming_only"
              ? "仅通过命名匹配推断。这意味着只因为 RTL 信号名与概念名相似就建立关联。\n⚠ 这是最弱的映射方式，可能产生假阳性。"
              : `映射方式：${bridge}。`);

      implementation_path = `概念 ${concept} → [${bridge}] → RTL: ${related_rtl.map((r) => r.label).join(", ") || "无"}`;

      // Why connected to RTL aggregates
      for (const r of related_rtl) {
        why_connected.push({
          neighbor_id: r.id,
          edge_type: "realizes",
          explanation: `Claim 声明概念 ${concept} 在 RTL 聚合 ${r.label} 中有实现`,
        });
      }

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
        traceable_evidence.push(id);
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
        raw_rtl_node_count = agg.child_count;

        // Find raw RTL nodes that belong to this aggregate
        const rawChildren = graph.nodes.filter(
          (n) => n.kind.startsWith("rtl_") && n.file_path === agg.file_path,
        );
        const childKindBreakdown: Record<string, number> = {};
        for (const child of rawChildren) {
          childKindBreakdown[child.kind] = (childKindBreakdown[child.kind] ?? 0) + 1;
        }
        const breakdownStr = Object.entries(childKindBreakdown)
          .map(([k, v]) => `${k}: ${v}`)
          .join("、");

        summary = `RTL 聚合 "${agg.label}"：包含 ${agg.child_count} 个 RTL 对象` +
          `（${agg.child_kinds.join("、")}）。涉及概念：${agg.concept_labels.join("、")}。\n` +
          `原始节点明细：${breakdownStr}`;
        role_in_project = agg.concept_labels.length > 1
          ? `承载多个概念（${agg.concept_labels.join("、")}）的共享 RTL 模块。\n⚠ 共享 RTL 表示概念之间可能存在耦合，shared edges 是 structural inferred，不代表语义确认。`
          : `概念 ${agg.concept_labels[0] ?? "?"} 的 RTL 实现。`;
        implementation_path = `文件：${agg.file_path}`;

        // Why connected — find claims pointing here
        for (const [claimId, aIds] of claimToAgg) {
          if (aIds.includes(agg.id)) {
            const claimNode = graph.nodes.find((n) => n.node_id === claimId);
            if (claimNode) {
              why_connected.push({
                neighbor_id: claimId,
                edge_type: "realizes",
                explanation: `Claim "${claimNode.label}" 声明此 RTL 模块实现了概念 ${claimNode.concept}`,
              });
            }
          }
        }

        // Traceable evidence from raw children
        for (const child of rawChildren) {
          if (child.evidence_ids) {
            traceable_evidence.push(...child.evidence_ids);
          }
        }
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
    data_provenance: {
      source_node_id: node.node_id,
      source_node_kind: node.kind,
      raw_rtl_node_count,
      edge_types,
    },
    why_connected,
    traceable_evidence: traceable_evidence.slice(0, 20),
  };
}
