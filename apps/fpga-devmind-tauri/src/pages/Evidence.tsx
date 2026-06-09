import { useState, useMemo } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { ProjectBundle, EvidenceGroup } from "../types";
import { groupEvidenceByClaim } from "../utils/transforms";

interface SourceContextResult {
  file_path: string;
  evidence_start: number;
  evidence_end: number;
  total_lines: number;
  context_start: number;
  context_end: number;
  lines: string[];
}

interface Props {
  bundle: ProjectBundle;
}

function Evidence({ bundle }: Props) {
  const groups = useMemo(() => groupEvidenceByClaim(bundle), [bundle]);
  const [selectedEvId, setSelectedEvId] = useState<string | null>(null);
  const [sourceContext, setSourceContext] = useState<SourceContextResult | null>(null);
  const [loadingCtx, setLoadingCtx] = useState(false);

  const handleSelectEvidence = async (evId: string, filePath?: string) => {
    setSelectedEvId(evId);
    if (!filePath) {
      setSourceContext(null);
      return;
    }
    setLoadingCtx(true);
    try {
      const ctx = await invoke<SourceContextResult>("read_evidence_source_context", {
        filePath,
        evidenceId: evId,
        contextLines: 5,
      });
      setSourceContext(ctx);
    } catch {
      // Fallback to legacy command
      try {
        const legacyCtx = await invoke<string>("read_source_context", {
          filePath,
          contextLines: 15,
        });
        setSourceContext({
          file_path: filePath,
          evidence_start: 0,
          evidence_end: 0,
          total_lines: 0,
          context_start: 0,
          context_end: 0,
          lines: legacyCtx.split("\n"),
        });
      } catch {
        setSourceContext(null);
      }
    } finally {
      setLoadingCtx(false);
    }
  };

  const selectedEv = selectedEvId
    ? bundle.index.evidence_index[selectedEvId]
    : null;

  // Find the group and item for selectedEvId to show why_matters
  const selectedGroup = useMemo(() => {
    if (!selectedEvId) return null;
    for (const g of groups) {
      const item = g.items.find((it) => it.id === selectedEvId);
      if (item) return { group: g, item };
    }
    return null;
  }, [groups, selectedEvId]);

  return (
    <div>
      <div className="page-title">Evidence</div>
      <div className="page-subtitle">
        按 Claim 分组，共 {groups.length} 组，{groups.reduce((sum, g) => sum + g.items.length, 0)} 条证据
      </div>

      <div style={{ display: "flex", gap: 16 }}>
        {/* Left: evidence groups */}
        <div style={{ flex: 1 }}>
          {groups.map((g) => (
            <EvidenceGroupComp
              key={g.claim_id}
              group={g}
              selectedEvId={selectedEvId}
              onSelect={handleSelectEvidence}
            />
          ))}
        </div>

        {/* Right: detail */}
        <div style={{ width: 460, minWidth: 360 }}>
          {selectedEv && selectedGroup ? (
            <div className="card">
              <div className="card-title">Evidence Detail</div>

              {/* Evidence ID */}
              <div className="detail-section">
                <div className="detail-section-title">Evidence ID</div>
                <div className="detail-text" style={{ fontSize: 11, fontFamily: "monospace", wordBreak: "break-all" }}>
                  {selectedEvId}
                </div>
              </div>

              <div className="detail-section">
                <div className="detail-section-title">所属 Claim</div>
                <div className="detail-text">{selectedGroup.group.claim_label}</div>
                <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 4 }}>
                  {selectedGroup.group.explanation}
                </div>
              </div>

              <div className="detail-section">
                <div className="detail-section-title">Why this matters</div>
                <div className="detail-text" style={{ color: "var(--yellow)" }}>
                  {selectedGroup.item.why_matters}
                </div>
                {/* Weak/naming evidence warning */}
                {(selectedEv.source_type === "naming_match" || selectedEv.strength === "weak") && (
                  <div style={{ fontSize: 12, color: "var(--red)", marginTop: 4, fontStyle: "italic" }}>
                    ⚠ 弱/命名证据：不能单独作为强映射证据
                  </div>
                )}
              </div>

              <div className="detail-section">
                <div className="detail-section-title">Source Type</div>
                <div className="detail-text">{selectedEv.source_type}</div>
              </div>

              {selectedEv.file_path && (
                <div className="detail-section">
                  <div className="detail-section-title">File</div>
                  <div className="detail-text" style={{ fontSize: 12, wordBreak: "break-all" }}>
                    {selectedEv.file_path}
                  </div>
                </div>
              )}

              {selectedEv.symbol && (
                <div className="detail-section">
                  <div className="detail-section-title">Symbol</div>
                  <div className="detail-text">{selectedEv.symbol}</div>
                </div>
              )}

              {selectedEv.strength && (
                <div className="detail-section">
                  <div className="detail-section-title">Strength</div>
                  <span className={`badge badge-${
                    selectedEv.strength === "strong" ? "supported"
                    : selectedEv.strength === "medium" ? "inferred"
                    : "unknown"
                  }`}>
                    {selectedEv.strength}
                  </span>
                </div>
              )}

              {/* Line range info */}
              {sourceContext && sourceContext.evidence_start > 0 && (
                <div className="detail-section">
                  <div className="detail-section-title">行号范围</div>
                  <div className="detail-text">
                    L{sourceContext.evidence_start}–L{sourceContext.evidence_end}（共 {sourceContext.evidence_end - sourceContext.evidence_start + 1} 行，文件共 {sourceContext.total_lines} 行）
                  </div>
                </div>
              )}

              {sourceContext && (
                <div className="detail-section">
                  <div className="detail-section-title">源码上下文</div>
                  {loadingCtx ? (
                    <div style={{ fontSize: 12, color: "var(--text2)" }}>加载中...</div>
                  ) : (
                    <div className="source-context">
                      {sourceContext.lines.join("\n")}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="card">
              <div className="detail-text" style={{ color: "var(--text2)" }}>
                点击左侧证据查看详情和「Why this matters」解释。
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EvidenceGroupComp({
  group,
  selectedEvId,
  onSelect,
}: {
  group: EvidenceGroup;
  selectedEvId: string | null;
  onSelect: (id: string, filePath?: string) => void;
}) {
  return (
    <div className="evidence-group">
      <div className="evidence-group-header">
        <span>
          <strong>{group.claim_label}</strong>
          <span style={{ marginLeft: 8, fontSize: 12, color: "var(--text2)" }}>
            {group.concept}
          </span>
        </span>
        <span>
          <span className={`badge badge-${
            group.confidence === "supported" ? "supported"
            : group.confidence === "inferred" ? "inferred"
            : "unknown"
          }`} style={{ marginRight: 8 }}>
            {group.confidence}
          </span>
          <span style={{ fontSize: 12, color: "var(--text2)" }}>
            {group.items.length} 项
          </span>
        </span>
      </div>

      {/* Claim explanation */}
      <div className="evidence-explanation">{group.explanation}</div>

      {group.items.slice(0, 20).map((ev) => (
        <div
          key={ev.id}
          className={`evidence-row ${selectedEvId === ev.id ? "selected" : ""}`}
          onClick={() => onSelect(ev.id, ev.file_path)}
        >
          <span style={{ color: "var(--text2)", fontSize: 11 }}>[{ev.source_type}]</span>{" "}
          {ev.symbol ?? ev.id.slice(0, 40)}
          {ev.strength && (
            <span className={`badge badge-${
              ev.strength === "strong" ? "supported"
              : ev.strength === "medium" ? "inferred"
              : "unknown"
            }`} style={{ marginLeft: 8 }}>
              {ev.strength}
            </span>
          )}
          {/* Weak evidence marker */}
          {(ev.source_type === "naming_match" || ev.strength === "weak") && (
            <span style={{ fontSize: 10, color: "var(--red)", marginLeft: 6 }}>⚠弱</span>
          )}
          <div style={{ fontSize: 10, color: "var(--text2)", marginTop: 2 }}>
            {ev.why_matters}
          </div>
        </div>
      ))}
      {group.items.length > 20 && (
        <div style={{ fontSize: 11, color: "var(--text2)", padding: "4px 12px", marginLeft: 12 }}>
          ...还有 {group.items.length - 20} 项未显示
        </div>
      )}
    </div>
  );
}

export default Evidence;
