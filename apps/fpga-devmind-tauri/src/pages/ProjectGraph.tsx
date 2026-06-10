import { useState, useMemo, useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ProjectBundle, GraphMode } from "../types";
import {
  buildSummaryGraph,
  buildDetailGraph,
  buildFocusGraph,
  buildPipelineGraph,
  nodeColor,
  nodeKindLabel,
} from "../utils/transforms";
import { buildUnderstandingCard } from "../utils/cardBuilder";

/* ------------------------------------------------------------------ */
/*  Custom node component                                             */
/* ------------------------------------------------------------------ */

function CustomNode({ data }: NodeProps) {
  const kind = (data.kind as string) ?? "unknown";
  const label = (data.label as string) ?? "?";
  const confidence = (data.confidence as string) ?? "";
  const color = nodeColor(kind);
  const isSelected = data.selected as boolean;

  return (
    <div
      style={{
        padding: "8px 14px",
        borderRadius: 8,
        background: isSelected ? color : `${color}22`,
        border: `2px solid ${isSelected ? color : `${color}66`}`,
        color: isSelected ? "#fff" : "#e2e8f0",
        fontSize: 12,
        fontWeight: isSelected ? 700 : 500,
        minWidth: 80,
        maxWidth: 160,
        textAlign: "center",
        transition: "all 0.15s",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div style={{ fontSize: 10, opacity: 0.7, marginBottom: 2 }}>
        {nodeKindLabel(kind)}
      </div>
      <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {label}
      </div>
      {confidence && (
        <div style={{ fontSize: 9, marginTop: 2, opacity: 0.6 }}>
          {confidence}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { custom: CustomNode };

/* ------------------------------------------------------------------ */
/*  Page component                                                    */
/* ------------------------------------------------------------------ */

interface Props {
  bundle: ProjectBundle;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
}

const MODES: { key: GraphMode; label: string }[] = [
  { key: "summary", label: "Summary（推荐）" },
  { key: "detail", label: "Detail（全节点）" },
  { key: "focus", label: "Focus（选中邻域）" },
  { key: "pipeline", label: "Pipeline（阶段流）" },
];

function ProjectGraph({ bundle, selectedNodeId, onSelectNode }: Props) {
  const [mode, setMode] = useState<GraphMode>("summary");
  const [hideShared, setHideShared] = useState(false);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  // T040.1: Default to pipeline mode when semantic_pipeline_view is available
  useEffect(() => {
    if (bundle.semantic_pipeline_view) {
      setMode("pipeline");
    } else {
      setMode("summary");
    }
    setSelectedEdgeId(null);
  }, [bundle.path, bundle.semantic_pipeline_view]);

  const flowGraph = useMemo(() => {
    switch (mode) {
      case "summary":
        return buildSummaryGraph(bundle, selectedNodeId, hideShared);
      case "detail":
        return buildDetailGraph(bundle, selectedNodeId, hideShared);
      case "focus":
        return buildFocusGraph(bundle, selectedNodeId, 2);
      case "pipeline":
        return buildPipelineGraph(bundle);
      default:
        return buildSummaryGraph(bundle, selectedNodeId, hideShared);
    }
  }, [bundle, selectedNodeId, mode, hideShared]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onSelectNode(node.id === selectedNodeId ? null : node.id);
      setSelectedEdgeId(null);
    },
    [selectedNodeId, onSelectNode],
  );

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      setSelectedEdgeId(edge.id === selectedEdgeId ? null : edge.id);
      onSelectNode(null);
    },
    [selectedEdgeId, onSelectNode],
  );

  const onPaneClick = useCallback(() => {
    onSelectNode(null);
    setSelectedEdgeId(null);
  }, [onSelectNode]);

  const card = useMemo(
    () => (selectedNodeId ? buildUnderstandingCard(bundle, selectedNodeId) : null),
    [bundle, selectedNodeId],
  );

  // T040.1: selected edge data for pipeline mode
  const selectedEdge = useMemo(() => {
    if (!selectedEdgeId) return null;
    return flowGraph.edges.find((e) => e.id === selectedEdgeId) ?? null;
  }, [selectedEdgeId, flowGraph.edges]);

  return (
    <div>
      <div className="page-title">Project Graph</div>

      {/* Controls bar */}
      <div className="graph-controls">
        <div className="graph-mode-btns">
          {MODES.map((m) => (
            <button
              key={m.key}
              className={`btn ${mode === m.key ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setMode(m.key)}
              style={{ fontSize: 12 }}
            >
              {m.label}
            </button>
          ))}
        </div>
        <label className="graph-checkbox">
          <input
            type="checkbox"
            checked={hideShared}
            onChange={(e) => setHideShared(e.target.checked)}
          />
          隐藏 shared edges
        </label>
        <span className="graph-stats">
          {flowGraph.nodes.length} 节点 · {flowGraph.edges.length} 边
        </span>
      </div>

      <div className="graph-layout">
        {/* Graph */}
        <div className="graph-panel">
          <ReactFlow
            nodes={flowGraph.nodes}
            edges={flowGraph.edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            fitView
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#1e293b" gap={20} />
            <Controls
              style={{ background: "var(--surface)", borderRadius: 6 }}
            />
          </ReactFlow>
        </div>

        {/* Right panel: Understanding Card (compact) + Edge Detail */}
        <div className="detail-panel">
          <h3>理解卡</h3>

          {/* T040.1: Edge detail panel (pipeline mode) */}
          {selectedEdge && selectedEdge.data && (() => {
            const d = selectedEdge.data as {
              edge_type: string;
              confidence: string;
              from_lane: string;
              to_lane: string;
              reason?: string;
              evidence_ids?: string[];
              source_files?: string[];
            };
            return (
              <div className="detail-section" style={{ marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid var(--border)" }}>
                <div className="detail-section-title">边详情</div>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <div>
                    <strong>类型:</strong>{" "}
                    <span className={`badge badge-${d.confidence === "supported" ? "supported" : "inferred"}`}>
                      {d.edge_type}
                    </span>
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <strong>置信度:</strong> {d.confidence}
                    {d.confidence === "inferred" && (
                      <span style={{ color: "var(--yellow)", marginLeft: 6 }}>⚠ 推断</span>
                    )}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <strong>阶段:</strong> {d.from_lane} → {d.to_lane}
                  </div>
                  {d.reason && (
                    <div style={{ marginTop: 4 }}>
                      <strong>原因:</strong> {d.reason}
                    </div>
                  )}
                  {d.evidence_ids && d.evidence_ids.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      <strong>证据:</strong>{" "}
                      {d.evidence_ids.slice(0, 3).join(", ")}
                      {d.evidence_ids.length > 3 && " ..."}
                    </div>
                  )}
                  {d.source_files && d.source_files.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      <strong>源文件:</strong>{" "}
                      {d.source_files.slice(0, 2).map((f) => f.split("/").slice(-2).join("/")).join(", ")}
                      {d.source_files.length > 2 && " ..."}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {!card ? (
            <div className="detail-text" style={{ color: "var(--text2)" }}>
              点击左侧图中的节点查看理解卡。
            </div>
          ) : (
            <>
              <div className="detail-section">
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span
                    style={{
                      display: "inline-block",
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: nodeColor(card.kind),
                    }}
                  />
                  <strong>{card.label}</strong>
                  <span className={`badge badge-${
                    card.confidence === "supported" ? "supported"
                    : card.confidence === "inferred" ? "inferred"
                    : "unknown"
                  }`}>
                    {card.confidence}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--text2)" }}>
                  {nodeKindLabel(card.kind)}
                </div>
              </div>

              <div className="detail-section">
                <div className="detail-section-title">摘要</div>
                <div className="detail-text" style={{ fontSize: 13, lineHeight: 1.6 }}>
                  {card.summary}
                </div>
              </div>

              <div className="detail-section">
                <div className="detail-section-title">实现路径</div>
                <div className="detail-text" style={{ fontSize: 12 }}>
                  {card.implementation_path}
                </div>
              </div>

              {card.related_concepts.length > 0 && (
                <div className="detail-section">
                  <div className="detail-section-title">相关概念</div>
                  {card.related_concepts.map((c) => (
                    <div
                      key={c.id}
                      className="uc-related-item"
                      onClick={() => onSelectNode(c.id)}
                    >
                      <span>{c.label}</span>
                      <span className={`badge badge-${
                        c.confidence === "supported" ? "supported"
                        : c.confidence === "inferred" ? "inferred"
                        : "unknown"
                      }`} style={{ marginLeft: 6 }}>
                        {c.confidence}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {card.related_claims.length > 0 && (
                <div className="detail-section">
                  <div className="detail-section-title">Claims ({card.related_claims.length})</div>
                  {card.related_claims.map((cl) => (
                    <div key={cl.id} style={{ fontSize: 12, padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
                      {cl.label} <span className={`badge badge-${
                        cl.confidence === "supported" ? "supported"
                        : cl.confidence === "inferred" ? "inferred"
                        : "unknown"
                      }`}>{cl.confidence}</span>
                    </div>
                  ))}
                </div>
              )}

              {card.related_rtl.length > 0 && (
                <div className="detail-section">
                  <div className="detail-section-title">RTL ({card.related_rtl.length})</div>
                  {card.related_rtl.map((r) => (
                    <div key={r.id} style={{ fontSize: 12, padding: "3px 0" }}>
                      {r.label}
                      {r.file_path && (
                        <div style={{ fontSize: 10, color: "var(--text2)", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {r.file_path.split("/").slice(-2).join("/")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {card.top_evidence.length > 0 && (
                <div className="detail-section">
                  <div className="detail-section-title">Top 证据</div>
                  {card.top_evidence.map((ev) => (
                    <div key={ev.id} style={{ fontSize: 12, padding: "3px 0" }}>
                      <span style={{ color: "var(--text2)" }}>[{ev.source_type}]</span>{" "}
                      {ev.symbol ?? ev.id.slice(0, 30)}
                      {ev.strength && (
                        <span className={`badge badge-${
                          ev.strength === "strong" ? "supported"
                          : ev.strength === "medium" ? "inferred"
                          : "unknown"
                        }`} style={{ marginLeft: 6 }}>
                          {ev.strength}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {card.limitations.length > 0 && (
                <div className="detail-section">
                  <div className="detail-section-title">限制</div>
                  {card.limitations.map((l, i) => (
                    <div key={i} style={{ fontSize: 12, color: "var(--yellow)" }}>⚠ {l}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProjectGraph;
