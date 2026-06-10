import { useMemo } from "react";
import type { ProjectBundle, ProjectBundleSummary, ProjectSemanticSummary } from "../types";
import { buildConceptTable, aggregateRtl } from "../utils/transforms";

interface Props {
  summary: ProjectBundleSummary;
  bundle: ProjectBundle;
  onSelectNode: (id: string) => void;
  onNavigateGraph: () => void;
}

function buildImplementationStory(bundle: ProjectBundle): string {
  // T038.1: Prefer semantic summary when available to avoid hardcoded OFDM text
  const ss = bundle.semantic_summary;
  if (ss) {
    const concepts = ss.core_concepts.map(c => c.display_name).join("、");
    const stages = ss.pipeline_stages.map(s => s.label).join(" → ");
    const ev = ss.evidence_quality_summary;
    const unc = ss.uncertainty_summary;
    const inferredCount = ss.core_concepts.filter(c => c.confidence === "inferred").length;

    let story = `项目 "${ss.project_id}" — ${ss.project_kind_hint}\n${ss.top_level_purpose}。`;
    story += `\n\nPipeline Stages：${stages}`;
    story += `\n\n核心概念（${ss.core_concepts.length} 个）：${concepts}`;
    story += `\n证据质量：strong=${ev.strong_direct}, medium=${ev.medium_structural}, weak=${ev.weak_name_only}, inferred=${ev.inferred}`;
    if (inferredCount > 0) {
      story += `\n${inferredCount} 个概念为 inferred 置信度，需进一步验证。`;
    }
    if (unc.inferred_claims.length > 0) {
      story += `\n推断性 Claims：${unc.inferred_claims.join("、")}`;
    }
    return story;
  }

  // Legacy fallback when semantic summary is absent
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

  let story = `本项目 "${bundle.graph.project_id}" 是一个 FPGA 信号处理模块。`;
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

      {/* T038: Semantic Summary — top section */}
      {bundle.semantic_summary && (
        <SemanticSummarySection
          summary={bundle.semantic_summary}
          onSelectNode={onSelectNode}
        />
      )}

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

      {/* Discovery Quality (T036/T037) */}
      {(() => {
        // Extract V2 fields from evidence chain
        const chains = Object.entries(bundle.index.evidence_chain || {});
        if (chains.length === 0) return null;

        const withSelectionReason = chains.filter(([_, chain]: [string, any]) =>
          chain.selection_reason
        );

        if (withSelectionReason.length === 0) return null;

        // T037: extract eval metrics from discovery_eval_result
        const evalData = (bundle.index as any).discovery_eval_result;
        // T037: test evidence status summary
        const testStatusCounts: Record<string, number> = {};
        for (const [_, chain] of chains) {
          const st = (chain as any).test_evidence_status || "unknown";
          testStatusCounts[st] = (testStatusCounts[st] || 0) + 1;
        }

        return (
          <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
            <div className="card-title">Discovery Quality</div>
            <div style={{ fontSize: 13 }}>
              {/* T037: Eval metrics summary */}
              {evalData && (
                <div style={{ marginBottom: 10, padding: "6px 8px", background: "var(--bg2)", borderRadius: 4 }}>
                  <strong>Selected Metrics (top {evalData.max_concepts ?? 12})</strong>
                  <div style={{ marginTop: 4 }}>
                    Precision: <span style={{ color: evalData.selected_precision_like >= 0.5 ? "var(--green)" : "var(--red)", fontWeight: 600 }}>
                      {((evalData.selected_precision_like ?? 0) * 100).toFixed(1)}%
                    </span>
                    {" | "}
                    Recall: <span style={{ color: evalData.selected_recall_like >= 0.75 ? "var(--green)" : "var(--red)", fontWeight: 600 }}>
                      {((evalData.selected_recall_like ?? 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  {evalData.excluded_terms_selected?.length > 0 && (
                    <div style={{ color: "var(--red)", marginTop: 2, fontSize: 12 }}>
                      ⚠ Excluded terms leaked: {evalData.excluded_terms_selected.join(", ")}
                    </div>
                  )}
                </div>
              )}

              {/* T037: Test evidence status summary */}
              {Object.keys(testStatusCounts).length > 0 && (
                <div style={{ marginBottom: 10, fontSize: 12, color: "var(--text2)" }}>
                  Test Status: {Object.entries(testStatusCounts).map(([st, cnt]) => `${st}: ${cnt}`).join(" | ")}
                </div>
              )}

              {withSelectionReason.map(([concept, chain]: [string, any]) => (
                <div key={concept} style={{ marginBottom: 8, padding: "4px 0" }}>
                  <strong>{concept}</strong>
                  {chain.aliases && chain.aliases.length > 0 && (
                    <span style={{ color: "var(--text2)", marginLeft: 8 }}>
                      aliases: {chain.aliases.join(", ")}
                    </span>
                  )}
                  <div style={{ color: "var(--text2)", marginTop: 2 }}>
                    {chain.selection_reason || "No selection reason"}
                  </div>
                  <div style={{ color: chain.why_core_or_secondary === "core" ? "var(--green)" : "var(--yellow)", marginTop: 2 }}>
                    {chain.why_core_or_secondary === "core" ? "● Core" : "○ Secondary"}
                    {chain.confidence_explanation && ` — ${chain.confidence_explanation}`}
                  </div>
                  {chain.missing && chain.missing.length > 0 && (
                    <div style={{ color: "var(--red)", marginTop: 2 }}>
                      Missing: {chain.missing.join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
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

/* ------------------------------------------------------------------ */
/*  T038: Semantic Summary Section                                    */
/* ------------------------------------------------------------------ */

interface SemanticSummaryProps {
  summary: ProjectSemanticSummary;
  onSelectNode: (id: string) => void;
}

function SemanticSummarySection({ summary, onSelectNode }: SemanticSummaryProps) {
  const ev = summary.evidence_quality_summary;
  const evTotal = ev.strong_direct + ev.medium_structural + ev.weak_name_only + ev.inferred;
  const unc = summary.uncertainty_summary;
  const tc = summary.test_coverage_summary;

  const bar = (label: string, count: number, color: string) => {
    const pct = evTotal > 0 ? (count / evTotal) * 100 : 0;
    return (
      <div style={{ marginBottom: 4, display: "flex", alignItems: "center" }}>
        <span style={{ width: 80, fontSize: 12, color: "var(--text2)" }}>{label}</span>
        <div style={{ flex: 1, height: 16, background: "var(--bg2)", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3 }} />
        </div>
        <span style={{ width: 40, textAlign: "right", fontSize: 12, fontWeight: 600 }}>{count}</span>
      </div>
    );
  };

  return (
    <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
      <div className="card-title">
        {summary.project_kind_hint} — {summary.top_level_purpose}
      </div>

      {/* Pipeline stages */}
      {summary.pipeline_stages.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--text2)" }}>
            Pipeline Stages
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {summary.pipeline_stages.map((stage) => (
              <div key={stage.stage_id} style={{
                padding: "6px 10px",
                background: "var(--bg2)",
                borderRadius: 4,
                fontSize: 12,
              }}>
                <strong>{stage.label}</strong>
                <span style={{ color: "var(--text2)", marginLeft: 6 }}>
                  {stage.source_files.length} files
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evidence quality bar chart */}
      {evTotal > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--text2)" }}>
            Evidence Quality ({evTotal} total)
          </div>
          {bar("Strong", ev.strong_direct, "var(--green)")}
          {bar("Medium", ev.medium_structural, "var(--yellow)")}
          {bar("Weak", ev.weak_name_only, "var(--orange)")}
          {bar("Inferred", ev.inferred, "var(--red)")}
        </div>
      )}

      {/* Core concepts mini-table */}
      {summary.core_concepts.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--text2)" }}>
            Core Concepts ({summary.core_concepts.length})
          </div>
          <div className="concept-table-wrapper">
            <table className="concept-table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Concept</th>
                  <th>Category</th>
                  <th>Role</th>
                  <th>L5/L6</th>
                  <th>RTL</th>
                  <th>Test</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {summary.core_concepts.map((c) => (
                  <tr key={c.canonical_name}>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => onSelectNode(`PUG_CONCEPT_${c.canonical_name}`)}
                      >
                        {c.display_name}
                      </button>
                    </td>
                    <td>{c.category}</td>
                    <td>{c.role_in_project}</td>
                    <td className="td-num">{c.l5_l6_evidence_count}</td>
                    <td className="td-num">{c.rtl_evidence_count}</td>
                    <td className="td-num">{c.test_evidence_count}</td>
                    <td>
                      <span className={`badge badge-${
                        c.confidence === "supported" ? "supported"
                        : c.confidence === "inferred" ? "inferred"
                        : "unknown"
                      }`}>
                        {c.confidence}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Uncertainty summary */}
      {(() => {
        const items = [
          ...(unc.inferred_claims?.length ? [{ label: "Inferred claims", list: unc.inferred_claims, color: "var(--red)" }] : []),
          ...(unc.weak_only_links?.length ? [{ label: "Weak-only links", list: unc.weak_only_links, color: "var(--orange)" }] : []),
          ...(unc.naming_only_links?.length ? [{ label: "Naming-only links", list: unc.naming_only_links, color: "var(--yellow)" }] : []),
          ...(unc.missing_l5_l6?.length ? [{ label: "Missing L5/L6", list: unc.missing_l5_l6, color: "var(--text2)" }] : []),
          ...(unc.missing_rtl?.length ? [{ label: "Missing RTL", list: unc.missing_rtl, color: "var(--text2)" }] : []),
          ...(unc.missing_test_evidence?.length ? [{ label: "Missing test evidence", list: unc.missing_test_evidence, color: "var(--text2)" }] : []),
        ];
        if (items.length === 0) return null;
        return (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--text2)" }}>
              Uncertainty / Gaps
            </div>
            {items.map((item) => (
              <div key={item.label} style={{ marginBottom: 4, fontSize: 12 }}>
                <span style={{ color: item.color, fontWeight: 600 }}>{item.label}:</span>{" "}
                <span style={{ color: "var(--text2)" }}>{item.list.join(", ")}</span>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Test coverage */}
      {tc.total_test_files > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: "var(--text2)" }}>
            Test Coverage
          </div>
          <div style={{ fontSize: 12, color: "var(--text2)" }}>
            {tc.total_test_files} test files |{" "}
            <span style={{ color: "var(--green)" }}>{tc.concepts_with_test_match} concepts matched</span>{" "}
            | <span style={{ color: "var(--red)" }}>{tc.concepts_without_test_match} unmatched</span>
          </div>
        </div>
      )}

      {/* Provenance */}
      <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 6 }}>
        Generated from: {summary.source_provenance.summary_generated_from.join(", ")} at{" "}
        {summary.source_provenance.generation_timestamp}
      </div>
    </div>
  );
}

export default Overview;
