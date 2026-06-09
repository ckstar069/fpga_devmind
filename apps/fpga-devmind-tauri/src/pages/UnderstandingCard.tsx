import { useMemo } from "react";
import type { ProjectBundle } from "../types";
import { buildUnderstandingCard } from "../utils/cardBuilder";
import { nodeColor, nodeKindLabel } from "../utils/transforms";

interface Props {
  bundle: ProjectBundle;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
}

function UnderstandingCardPage({ bundle, selectedNodeId, onSelectNode }: Props) {
  const card = useMemo(
    () => (selectedNodeId ? buildUnderstandingCard(bundle, selectedNodeId) : null),
    [bundle, selectedNodeId],
  );

  if (!card) {
    return (
      <div>
        <div className="page-title">Understanding Card</div>
        <div className="card" style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>🧠</div>
          <div style={{ fontSize: 15, color: "var(--text)", marginBottom: 8 }}>
            请先在 Project Graph 或 Agent 问答中选择一个节点
          </div>
          <div style={{ fontSize: 13, color: "var(--text2)" }}>
            点击图中的任意节点，或使用 Agent 问答中的「解释当前选中节点」，然后切回此页面查看详细理解卡。
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-title">Understanding Card</div>
      <div className="uc-layout">
        {/* Main card */}
        <div className="uc-main">
          {/* Header */}
          <div className="card uc-header">
            <div className="uc-header-top">
              <span
                className="uc-color-dot"
                style={{ background: nodeColor(card.kind) }}
              />
              <span className="uc-label">{card.label}</span>
              <span className={`badge badge-${
                card.confidence === "supported" ? "supported"
                : card.confidence === "inferred" ? "inferred"
                : "unknown"
              }`}>
                {card.confidence}
              </span>
              <span className="uc-kind-tag">{nodeKindLabel(card.kind)}</span>
            </div>
            <div className="uc-summary">{card.summary}</div>
          </div>

          {/* Role & Implementation Path */}
          <div className="card">
            <div className="card-title">在项目中的角色</div>
            <div className="detail-text" style={{ whiteSpace: "pre-wrap" }}>{card.role_in_project}</div>
          </div>

          <div className="card">
            <div className="card-title">实现路径</div>
            <div className="uc-path">{card.implementation_path}</div>
          </div>

          {/* Data Provenance (T034) */}
          <div className="card" style={{ borderLeft: "3px solid var(--accent2)" }}>
            <div className="card-title">📦 数据来源 (Data Provenance)</div>
            <div style={{ fontSize: 12, lineHeight: 1.8 }}>
              <div>
                <span style={{ color: "var(--text2)" }}>源节点：</span>
                <span style={{ fontFamily: "monospace" }}>{card.data_provenance.source_node_id}</span>
                <span style={{ color: "var(--text2)", marginLeft: 8 }}>({card.data_provenance.source_node_kind})</span>
              </div>
              {card.data_provenance.raw_rtl_node_count > 0 && (
                <div>
                  <span style={{ color: "var(--text2)" }}>原始 RTL 节点数：</span>
                  {card.data_provenance.raw_rtl_node_count}
                </div>
              )}
              {card.data_provenance.edge_types.length > 0 && (
                <div>
                  <span style={{ color: "var(--text2)" }}>连接边类型：</span>
                  {card.data_provenance.edge_types.join("、")}
                </div>
              )}
            </div>
          </div>

          {/* Why Connected (T034) */}
          {card.why_connected.length > 0 && (
            <div className="card">
              <div className="card-title">🔗 为什么连接到邻居</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {card.why_connected.slice(0, 10).map((wc, i) => (
                  <div
                    key={i}
                    className="uc-related-item"
                    onClick={() => onSelectNode(wc.neighbor_id)}
                  >
                    <span className="uc-ev-source">{wc.edge_type}</span>
                    <span style={{ fontSize: 12, flex: 1 }}>{wc.explanation}</span>
                    <span style={{ fontSize: 11, color: "var(--accent)" }}>→</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related Concepts */}
          {card.related_concepts.length > 0 && (
            <div className="card">
              <div className="card-title">相关概念 ({card.related_concepts.length})</div>
              <div className="uc-related-list">
                {card.related_concepts.map((c) => (
                  <div
                    key={c.id}
                    className="uc-related-item"
                    onClick={() => onSelectNode(c.id)}
                  >
                    <span className="uc-related-label">{c.label}</span>
                    <span className={`badge badge-${
                      c.confidence === "supported" ? "supported"
                      : c.confidence === "inferred" ? "inferred"
                      : "unknown"
                    }`}>
                      {c.confidence}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related Claims */}
          {card.related_claims.length > 0 && (
            <div className="card">
              <div className="card-title">相关 Claims ({card.related_claims.length})</div>
              <div className="uc-related-list">
                {card.related_claims.map((cl) => (
                  <div
                    key={cl.id}
                    className="uc-related-item"
                    onClick={() => onSelectNode(cl.id)}
                  >
                    <span className="uc-related-label">{cl.label}</span>
                    <span className="uc-related-detail">
                      {cl.concept} · {cl.bridge_kind}
                    </span>
                    <span className={`badge badge-${
                      cl.confidence === "supported" ? "supported"
                      : cl.confidence === "inferred" ? "inferred"
                      : "unknown"
                    }`}>
                      {cl.confidence}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related RTL */}
          {card.related_rtl.length > 0 && (
            <div className="card">
              <div className="card-title">RTL 目标 ({card.related_rtl.length})</div>
              <div className="uc-related-list">
                {card.related_rtl.map((r) => (
                  <div
                    key={r.id}
                    className="uc-related-item"
                    onClick={() => onSelectNode(r.id)}
                  >
                    <span className="uc-related-label">{r.label}</span>
                    {r.file_path && (
                      <span className="uc-related-detail">
                        {r.file_path.split("/").slice(-2).join("/")}
                      </span>
                    )}
                    <span className="uc-related-tag">{r.kind}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top Evidence */}
          {card.top_evidence.length > 0 && (
            <div className="card">
              <div className="card-title">
                关键证据 ({card.evidence_count} 条中 Top {card.top_evidence.length})
              </div>
              <div className="uc-evidence-list">
                {card.top_evidence.map((ev) => (
                  <div key={ev.id} className="uc-evidence-item">
                    <span className="uc-ev-source">{ev.source_type}</span>
                    <span className="uc-ev-symbol">
                      {ev.symbol ?? ev.id.slice(0, 30)}
                    </span>
                    {ev.strength && (
                      <span className={`badge badge-${
                        ev.strength === "strong" ? "supported"
                        : ev.strength === "medium" ? "inferred"
                        : "unknown"
                      }`}>
                        {ev.strength}
                      </span>
                    )}
                    {ev.file_path && (
                      <span className="uc-ev-file">
                        {ev.file_path.split("/").slice(-2).join("/")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Traceable Evidence IDs (T034) */}
          {card.traceable_evidence.length > 0 && (
            <div className="card">
              <div className="card-title">🔍 可追溯证据 ID ({card.traceable_evidence.length})</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {card.traceable_evidence.map((eid) => (
                  <span
                    key={eid}
                    className="uc-ev-source"
                    style={{ cursor: "pointer", fontSize: 10 }}
                    title={eid}
                  >
                    {eid.length > 30 ? eid.slice(0, 30) + "…" : eid}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Limitations */}
          {card.limitations.length > 0 && (
            <div className="card uc-limitations">
              <div className="card-title">⚠ 局限性</div>
              {card.limitations.map((l, i) => (
                <div key={i} className="uc-limitation-item">{l}</div>
              ))}
            </div>
          )}

          {/* Next Steps */}
          {card.next_steps.length > 0 && (
            <div className="card">
              <div className="card-title">下一步建议</div>
              <ul className="uc-next-steps">
                {card.next_steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default UnderstandingCardPage;
