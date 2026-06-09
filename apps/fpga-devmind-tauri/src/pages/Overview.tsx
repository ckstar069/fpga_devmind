import { useMemo } from "react";
import type { ProjectBundle, ProjectBundleSummary } from "../types";
import { buildConceptTable, aggregateRtl } from "../utils/transforms";

interface Props {
  summary: ProjectBundleSummary;
  bundle: ProjectBundle;
  onSelectNode: (id: string) => void;
  onNavigateGraph: () => void;
}

function buildImplementationStory(bundle: ProjectBundle): string {
  const concepts = bundle.graph.nodes.filter(n => n.kind === "concept");
  const claims = bundle.graph.nodes.filter(n => n.kind === "mapping_claim");
  const supported = claims.filter(c => c.confidence === "supported");
  const inferred = claims.filter(c => c.confidence === "inferred");
  const conceptNames = concepts.map(c => c.label);

  const l5l6Files = new Set<string>();
  const rtlFiles = new Set<string>();
  Object.values(bundle.index.evidence_index).forEach(ev => {
    if (ev.file_path) {
      if (ev.file_path.includes("L5_fixedpoint") || ev.file_path.includes("L6_resource_opt")) {
        l5l6Files.add(ev.file_path.split("/").slice(-1)[0]);
      } else if (ev.file_path.includes("rtl") || ev.file_path.endsWith(".v") || ev.file_path.endsWith(".sv")) {
        rtlFiles.add(ev.file_path.split("/").slice(-1)[0]);
      }
    }
  });

  let story = `本项目 "${bundle.graph.project_id}" 实现了 FPGA 上的 OFDM 通信功能模块。`;
  story += `\n\n识别出 ${concepts.length} 个核心概念：${conceptNames.join("、")}。`;
  story += `\n其中 ${supported.length} 个映射达到 supported 置信度，${inferred.length} 个为 inferred（推断性）。`;
  story += `\n\nL5/L6 Python 模型涉及 ${l5l6Files.size} 个文件，RTL 实现涉及 ${rtlFiles.size} 个文件。`;

  if (inferred.length > 0) {
    story += `\n\n${inferred.length} 个概念仍需进一步验证。`;
  }

  return story;
}

function Overview({ summary, bundle, onSelectNode, onNavigateGraph }: Props) {
  const concepts = bundle.graph.nodes.filter((n) => n.kind === "concept");
  const claims = bundle.graph.nodes.filter((n) => n.kind === "mapping_claim");
  const supported = claims.filter((c) => c.confidence === "supported").length;
  const inferred = claims.filter((c) => c.confidence === "inferred").length;
  const unknown = claims.filter((c) => c.confidence === "unknown" || !c.confidence).length;
  const { aggregates } = useMemo(
    () => aggregateRtl(bundle.graph.nodes, bundle.graph.edges),
    [bundle],
  );
  const conceptTable = useMemo(() => buildConceptTable(bundle), [bundle]);

  // Stage file counts for summary
  const stageCounts = useMemo(() => {
    const l5Files = new Set<string>();
    const l6Files = new Set<string>();
    const rtlFiles = new Set<string>();
    Object.values(bundle.index.evidence_index).forEach(ev => {
      if (ev.file_path) {
        if (ev.file_path.includes("L5_fixedpoint")) l5Files.add(ev.file_path);
        else if (ev.file_path.includes("L6_resource_opt")) l6Files.add(ev.file_path);
        else if (ev.source_type === "rtl_source" || ev.file_path.endsWith(".v") || ev.file_path.endsWith(".sv"))
          rtlFiles.add(ev.file_path);
      }
    });
    return { l5: l5Files.size, l6: l6Files.size, rtl: rtlFiles.size };
  }, [bundle]);

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

      {/* Project Implementation Story (T035) */}
      <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
        <div className="card-title">项目实现概述</div>
        <div className="summary-text">
          {buildImplementationStory(bundle)}
        </div>
      </div>

      {/* Stage Summary (T035) */}
      <div className="card">
        <div className="card-title">阶段概要</div>
        <div className="stat-row" style={{ marginBottom: 12 }}>
          <div className="stat-item">
            <div className="stat-value">{stageCounts.l5}</div>
            <div className="stat-label">L5 固定点文件</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{stageCounts.l6}</div>
            <div className="stat-label">L6 资源优化文件</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{stageCounts.rtl}</div>
            <div className="stat-label">RTL 文件</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{concepts.length}</div>
            <div className="stat-label">概念</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{bundle.metadata.evidence_items}</div>
            <div className="stat-label">证据</div>
          </div>
        </div>
      </div>

      {/* Concept Implementation Table (enhanced with L5/L6/RTL/Test/Uncertainty columns) */}
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
                <th>L5</th>
                <th>L6</th>
                <th>RTL</th>
                <th>Test</th>
                <th>Uncertainty</th>
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
                      <span style={{ color: "var(--text2)" }}>--</span>
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
                      : <span style={{ color: "var(--text2)" }}>--</span>
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
                  <td className="td-num">{row.l5_count}</td>
                  <td className="td-num">{row.l6_count}</td>
                  <td className="td-num">{row.rtl_ev_count}</td>
                  <td className="td-num">{row.test_count}</td>
                  <td className="td-small" style={{ color: row.uncertainty ? "var(--yellow)" : "var(--green)" }}>
                    {row.uncertainty || "OK"}
                  </td>
                  <td className="td-small">{row.limitations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Risks / Gaps (T035) */}
      {(() => {
        const gaps = conceptTable.filter(r => r.uncertainty);
        if (gaps.length === 0) return null;
        return (
          <div className="card" style={{ borderLeft: "3px solid var(--yellow)" }}>
            <div className="card-title">需要进一步确认 ({gaps.length})</div>
            {gaps.map((g, i) => (
              <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                <strong>{g.concept}</strong>: {g.uncertainty}
              </div>
            ))}
          </div>
        );
      })()}

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
