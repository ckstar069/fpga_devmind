import { useState, useMemo } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { ProjectBundle, EvidenceGroup, EvidenceChain } from "../types";
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
  const [viewMode, setViewMode] = useState<"byClaim" | "byChain">("byClaim");
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
        共 {groups.length} 组，{groups.reduce((sum, g) => sum + g.items.length, 0)} 条证据
      </div>

      {/* View mode toggle */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          className={`btn ${viewMode === "byClaim" ? "btn-primary" : "btn-secondary"}`}
          style={{ fontSize: 12 }}
          onClick={() => setViewMode("byClaim")}
        >
          By Claim
        </button>
        <button
          className={`btn ${viewMode === "byChain" ? "btn-primary" : "btn-secondary"}`}
          style={{ fontSize: 12 }}
          onClick={() => setViewMode("byChain")}
        >
          By Chain (T035)
        </button>
      </div>

      <div style={{ display: "flex", gap: 16 }}>
        {/* Left: evidence groups or chain view */}
        <div style={{ flex: 1 }}>
          {viewMode === "byClaim" ? (
            groups.map((g) => (
              <EvidenceGroupComp
                key={g.claim_id}
                group={g}
                selectedEvId={selectedEvId}
                onSelect={handleSelectEvidence}
              />
            ))
          ) : (
            <ConceptChainView
              bundle={bundle}
              selectedEvId={selectedEvId}
              onSelect={handleSelectEvidence}
            />
          )}
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
                    Weak/naming evidence: cannot serve as strong mapping evidence alone
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

/* ================================================================== */
/*  Evidence Group (by Claim)                                         */
/* ================================================================== */

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
            <span style={{ fontSize: 10, color: "var(--red)", marginLeft: 6 }}>weak</span>
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

/* ================================================================== */
/*  Concept Chain View (T035)                                         */
/* ================================================================== */

function ConceptChainView({
  bundle,
  selectedEvId,
  onSelect,
}: {
  bundle: ProjectBundle;
  selectedEvId: string | null;
  onSelect: (id: string, filePath?: string) => void;
}) {
  const [filterConcept, setFilterConcept] = useState<string>("");
  const [filterStrength, setFilterStrength] = useState<string>("");

  // Build chain data from evidence_index, grouped by concept
  const chains = useMemo(() => {
    const concepts = bundle.graph.nodes.filter(n => n.kind === "concept");
    const evByConcept = new Map<string, { id: string; source_type: string; file_path?: string; symbol?: string; strength?: string }[]>();

    for (const [id, ev] of Object.entries(bundle.index.evidence_index)) {
      const concept = ev.concept ?? "";
      if (!evByConcept.has(concept)) evByConcept.set(concept, []);
      evByConcept.get(concept)!.push({
        id,
        source_type: ev.source_type,
        file_path: ev.file_path,
        symbol: ev.symbol,
        strength: ev.strength,
      });
    }

    // Also check if bundle has evidence_chain from index
    const chainData = bundle.index.evidence_chain;

    return concepts.map(c => {
      const evItems = evByConcept.get(c.label) ?? [];

      // Categorize by stage
      const l5l6: typeof evItems = [];
      const rtl: typeof evItems = [];
      const test: typeof evItems = [];
      const other: typeof evItems = [];

      for (const item of evItems) {
        const fp = item.file_path ?? "";
        if (fp.includes("L5_fixedpoint") || fp.includes("L6_resource_opt")) {
          l5l6.push(item);
        } else if (item.source_type === "rtl_source" || fp.endsWith(".v") || fp.endsWith(".sv")) {
          rtl.push(item);
        } else if (fp.includes("test") || item.source_type.startsWith("test_")) {
          test.push(item);
        } else {
          other.push(item);
        }
      }

      // Get claim info
      const claim = bundle.graph.nodes.find(n => n.kind === "mapping_claim" && n.concept === c.label);
      const claimConf = claim?.confidence ?? "unknown";

      // Build missing list
      const missing: string[] = [];
      if (l5l6.length === 0) missing.push("L5/L6 evidence");
      if (rtl.length === 0) missing.push("RTL evidence");
      if (test.length === 0) missing.push("Test evidence");

      // Use evidence_chain data if available
      let chain: EvidenceChain | undefined;
      if (chainData && chainData[c.label]) {
        try {
          chain = chainData[c.label] as EvidenceChain;
        } catch {
          // ignore parse errors
        }
      }

      return {
        concept: c.label,
        conceptId: c.node_id,
        confidence: c.confidence ?? "unknown",
        claimConf,
        bridgeKind: claim?.bridge_kind,
        l5l6,
        rtl,
        test,
        other,
        missing,
        chain,
      };
    });
  }, [bundle]);

  const filtered = chains.filter(ch => {
    if (filterConcept && !ch.concept.includes(filterConcept)) return false;
    if (filterStrength === "missing_rtl" && ch.rtl.length > 0) return false;
    if (filterStrength === "missing_l5l6" && ch.l5l6.length > 0) return false;
    return true;
  });

  return (
    <div>
      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <input
          className="form-input"
          value={filterConcept}
          onChange={(e) => setFilterConcept(e.target.value)}
          placeholder="Filter concept..."
          style={{ fontSize: 12, width: 180 }}
        />
        <select
          className="form-input"
          value={filterStrength}
          onChange={(e) => setFilterStrength(e.target.value)}
          style={{ fontSize: 12, width: 160 }}
        >
          <option value="">-- All --</option>
          <option value="missing_rtl">Missing RTL</option>
          <option value="missing_l5l6">Missing L5/L6</option>
        </select>
      </div>

      {filtered.map((ch) => (
        <div key={ch.conceptId} className="evidence-group">
          <div className="evidence-group-header">
            <span>
              <strong>{ch.concept}</strong>
              <span style={{ marginLeft: 8, fontSize: 12, color: "var(--text2)" }}>
                {ch.claimConf} / {ch.bridgeKind ?? "?"}
              </span>
            </span>
            <span>
              <span className={`badge badge-${
                ch.confidence === "supported" ? "supported"
                : ch.confidence === "inferred" ? "inferred"
                : "unknown"
              }`}>
                {ch.confidence}
              </span>
            </span>
          </div>

          {/* Chain stages */}
          <div style={{ padding: "8px 12px" }}>
            <ChainStage
              label="L5/L6"
              items={ch.l5l6}
              selectedEvId={selectedEvId}
              onSelect={onSelect}
            />
            <ChainStage
              label="RTL"
              items={ch.rtl}
              selectedEvId={selectedEvId}
              onSelect={onSelect}
            />
            <ChainStage
              label="Test"
              items={ch.test}
              selectedEvId={selectedEvId}
              onSelect={onSelect}
            />
            {ch.other.length > 0 && (
              <ChainStage
                label="Other"
                items={ch.other}
                selectedEvId={selectedEvId}
                onSelect={onSelect}
              />
            )}
            {ch.missing.length > 0 && (
              <div style={{ fontSize: 11, color: "var(--yellow)", marginTop: 4 }}>
                Missing: {ch.missing.join(", ")}
              </div>
            )}

            {/* T036: V2 evidence chain fields */}
            {ch.chain && (
              <div style={{ marginTop: 6, padding: "4px 8px", backgroundColor: "rgba(128,128,128,0.06)", borderRadius: 4 }}>
                {ch.chain.selection_reason && (
                  <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 2 }}>
                    <strong>Selection:</strong> {ch.chain.selection_reason}
                  </div>
                )}
                {ch.chain.confidence_explanation && (
                  <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 2 }}>
                    <strong>Confidence:</strong> {ch.chain.confidence_explanation}
                  </div>
                )}
                {ch.chain.why_core_or_secondary && (
                  <div style={{ fontSize: 11, marginTop: 2 }}>
                    <span style={{
                      display: "inline-block",
                      padding: "1px 6px",
                      borderRadius: 3,
                      fontSize: 10,
                      fontWeight: 600,
                      backgroundColor: ch.chain.why_core_or_secondary === "core" ? "var(--green)" : "var(--yellow)",
                      color: ch.chain.why_core_or_secondary === "core" ? "#fff" : "#000",
                    }}>
                      {ch.chain.why_core_or_secondary === "core" ? "Core" : "Secondary"}
                    </span>
                  </div>
                )}
                {ch.chain.aliases && ch.chain.aliases.length > 0 && (
                  <div style={{ fontSize: 10, color: "var(--text2)", marginTop: 2 }}>
                    Aliases: {ch.chain.aliases.join(", ")}
                  </div>
                )}
                {ch.chain.missing && ch.chain.missing.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--red)", marginTop: 4, fontWeight: 600 }}>
                    Missing evidence: {ch.chain.missing.join(", ")}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ChainStage({
  label,
  items,
  selectedEvId,
  onSelect,
}: {
  label: string;
  items: { id: string; source_type: string; file_path?: string; symbol?: string; strength?: string }[];
  selectedEvId: string | null;
  onSelect: (id: string, filePath?: string) => void;
}) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ fontSize: 11, color: "var(--text2)", fontWeight: 600, marginBottom: 2 }}>
        {label} ({items.length})
      </div>
      {items.slice(0, 10).map((item) => (
        <div
          key={item.id}
          className={`evidence-row ${selectedEvId === item.id ? "selected" : ""}`}
          onClick={() => onSelect(item.id, item.file_path)}
          style={{ padding: "3px 8px", fontSize: 12 }}
        >
          <span style={{ color: "var(--text2)", fontSize: 10 }}>[{item.source_type}]</span>{" "}
          {item.symbol ?? item.id.slice(0, 30)}
          {item.strength && (
            <span className={`badge badge-${
              item.strength === "strong" ? "supported"
              : item.strength === "medium" ? "inferred"
              : "unknown"
            }`} style={{ marginLeft: 6, fontSize: 10 }}>
              {item.strength}
            </span>
          )}
        </div>
      ))}
      {items.length > 10 && (
        <div style={{ fontSize: 10, color: "var(--text2)", paddingLeft: 8 }}>
          ...+{items.length - 10} more
        </div>
      )}
      {items.length === 0 && (
        <div style={{ fontSize: 11, color: "var(--text2)", paddingLeft: 8, fontStyle: "italic" }}>
          None
        </div>
      )}
    </div>
  );
}

export default Evidence;
