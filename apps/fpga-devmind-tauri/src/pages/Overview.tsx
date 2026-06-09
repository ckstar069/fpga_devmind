import { useMemo } from "react";
import type { ProjectBundle, ProjectBundleSummary } from "../types";
import { buildConceptTable, nodeColor, aggregateRtl } from "../utils/transforms";

interface Props {
  summary: ProjectBundleSummary;
  bundle: ProjectBundle;
  onSelectNode: (id: string) => void;
  onNavigateGraph: () => void;
}

function Overview({ summary, bundle, onSelectNode, onNavigateGraph }: Props) {
  const concepts = bundle.graph.nodes.filter((n) => n.kind === "concept");
  const claims = bundle.graph.nodes.filter((n) => n.kind === "mapping_claim");
  const supported = claims.filter((c) => c.confidence === "supported").length;
  const inferred = claims.filter((c) => c.confidence === "inferred").length;
  const unknown = claims.filter((c) => c.confidence === "unknown" || !c.confidence).length;
  const sharedEdges = bundle.graph.edges.filter(
    (e) => e.edge_type === "shares_file" || e.edge_type === "shares_rtl_object",
  );
  const { aggregates } = useMemo(
    () => aggregateRtl(bundle.graph.nodes, bundle.graph.edges),
    [bundle],
  );
  const conceptTable = useMemo(() => buildConceptTable(bundle), [bundle]);

  return (
    <div>
      <div className="page-title">Overview</div>
      <div className="page-subtitle">
        项目 <strong>{summary.project_id}</strong> 的整体理解
      </div>

      {/* Stats */}
      <div className="card">
        <div className="stat-row">
          <div className="stat-item">
            <div className="stat-value">{concepts.length}</div>
            <div className="stat-label">概念</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{claims.length}</div>
            <div className="stat-label">Claims</div>
          </div>
          <div className="stat-item">
            <div className="stat-value" style={{ color: "var(--green)" }}>{supported}</div>
            <div className="stat-label">Supported</div>
          </div>
          <div className="stat-item">
            <div className="stat-value" style={{ color: "var(--yellow)" }}>{inferred}</div>
            <div className="stat-label">Inferred</div>
          </div>
          <div className="stat-item">
            <div className="stat-value" style={{ color: "var(--red)" }}>{unknown}</div>
            <div className="stat-label">Unknown</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{summary.evidence_items}</div>
            <div className="stat-label">证据</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{aggregates.length}</div>
            <div className="stat-label">RTL 文件</div>
          </div>
        </div>
      </div>

      {/* Chinese summary */}
      <div className="card">
        <div className="card-title">项目理解摘要</div>
        <div className="summary-text">
          项目 <strong>{summary.project_id}</strong> 是一个 FPGA coarse sync 模块。
          识别出 <strong>{concepts.length}</strong> 个核心概念（{concepts.map((c) => c.label).join("、")}），
          共 <strong>{claims.length}</strong> 个 mapping claim（{supported} supported / {inferred} inferred / {unknown} unknown），
          <strong>{summary.evidence_items}</strong> 条证据，
          涉及 <strong>{aggregates.length}</strong> 个 RTL 文件/模块。
          {sharedEdges.length > 0 &&
            ` 存在 ${sharedEdges.length} 条共享边（structural inferred，不代表语义确认）。`}
        </div>
      </div>

      {/* Concept Implementation Table */}
      <div className="card">
        <div className="card-title">概念实现表</div>
        <div className="concept-table-wrapper">
          <table className="concept-table">
            <thead>
              <tr>
                <th>概念</th>
                <th>L5/L6 角色</th>
                <th>Claim</th>
                <th>RTL 目标</th>
                <th>置信度</th>
                <th>证据</th>
                <th>局限</th>
              </tr>
            </thead>
            <tbody>
              {conceptTable.map((row) => (
                <tr key={row.concept_id}>
                  <td>
                    <button
                      className="table-link"
                      onClick={() => onSelectNode(row.concept_id)}
                    >
                      {row.concept}
                    </button>
                  </td>
                  <td className="td-small">{row.l5_l6_role}</td>
                  <td>
                    {row.claim_id ? (
                      <button
                        className="table-link"
                        onClick={() => onSelectNode(row.claim_id)}
                      >
                        {row.claim_label}
                      </button>
                    ) : (
                      <span style={{ color: "var(--text2)" }}>—</span>
                    )}
                  </td>
                  <td>
                    {row.rtl_targets.length > 0
                      ? row.rtl_targets.map((t, i) => (
                          <span key={i}>
                            {i > 0 && ", "}
                            <span className="rtl-target-chip">{t}</span>
                          </span>
                        ))
                      : <span style={{ color: "var(--text2)" }}>—</span>
                    }
                  </td>
                  <td>
                    <span className={`badge badge-${
                      row.confidence === "supported" ? "supported"
                      : row.confidence === "inferred" ? "inferred"
                      : "unknown"
                    }`}>
                      {row.confidence}
                    </span>
                  </td>
                  <td className="td-num">{row.evidence_count}</td>
                  <td className="td-small">{row.limitations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick actions */}
      <div className="card">
        <div className="card-title">快速操作</div>
        <div className="summary-text">
          <ul style={{ paddingLeft: 20, lineHeight: 2 }}>
            <li>
              <button className="table-link" onClick={onNavigateGraph}>
                打开 Project Graph
              </button>{" "}
              查看概念 → Claim → RTL 映射图
            </li>
            <li>在 Agent 问答中输入「这个项目整体实现了什么？」获取概述</li>
            <li>点击上表中的概念名跳转到 Understanding Card</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default Overview;
