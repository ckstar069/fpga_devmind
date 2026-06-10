import { useState, useMemo } from "react";
import type { ProjectBundle } from "../types";
import { SUGGESTED_QUESTIONS } from "../utils/agent";
import {
  runAgent,
  PROVIDER_CAPABILITIES,
  getAvailableProviderKinds,
  evaluateProviderPolicy,
} from "../agent";
import type { AgentRunResult, AgentProviderKind } from "../agent";

interface Props {
  bundle: ProjectBundle | null;
  selectedNodeId: string | null;
  onNavigateNode: (id: string) => void;
}

function AgentQA({ bundle, selectedNodeId, onNavigateNode }: Props) {
  const [question, setQuestion] = useState("");
  const [providerKind, setProviderKind] = useState<AgentProviderKind>("deterministic");
  const [history, setHistory] = useState<AgentRunResult[]>([]);

  const handleAsk = () => {
    const q = question.trim();
    if (!q) return;
    const result = runAgent({
      question: q,
      selectedNodeId,
      bundle,
      providerKind,
    });
    setHistory((prev) => [result, ...prev]);
    setQuestion("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  const handleSuggested = (q: string) => {
    const result = runAgent({
      question: q,
      selectedNodeId,
      bundle,
      providerKind,
    });
    setHistory((prev) => [result, ...prev]);
  };

  const suggestedToShow = useMemo(() => {
    if (history.length === 0) return SUGGESTED_QUESTIONS;
    return history[0].answer.follow_up_questions.length > 0
      ? history[0].answer.follow_up_questions
      : SUGGESTED_QUESTIONS;
  }, [history]);

  // T041: Navigation index status
  const nav = bundle?.agent_navigation_index;
  const hasNav = !!nav;
  const qs = nav?.quality_status;

  return (
    <div>
      <div className="page-title">Agent 问答</div>
      <div className="page-subtitle">
        确定性问答系统（不调用外部 LLM），基于当前 bundle 数据回答
      </div>

      {/* T042/T043: Provider selection + Policy status */}
      <div className="card" style={{ padding: "10px 14px", marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: "var(--text2)", marginBottom: 6 }}>
          Provider 选择（T042）
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {getAvailableProviderKinds().map((kind) => {
            const cap = PROVIDER_CAPABILITIES[kind];
            return (
              <button
                key={kind}
                className={`btn ${providerKind === kind ? "btn-primary" : "btn-secondary"}`}
                style={{ fontSize: 11, padding: "4px 10px" }}
                onClick={() => setProviderKind(kind)}
                title={cap.description}
              >
                {cap.label}
                {!cap.enabled && " (Disabled)"}
                {cap.network_allowed && " 🌐"}
              </button>
            );
          })}
        </div>
        <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 6 }}>
          {PROVIDER_CAPABILITIES[providerKind].description}
        </div>
        {/* T043: Policy status line */}
        {(() => {
          const policy = evaluateProviderPolicy({ provider_kind: providerKind, question: "" });
          return (
            <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 11 }}>
              <span className={`badge badge-${policy.allowed ? "supported" : "unknown"}`} style={{ fontSize: 10 }}>
                策略: {policy.allowed ? "允许" : "拒绝"}
              </span>
              <span style={{ color: "var(--text2)" }}>
                联网: {policy.network_allowed ? "允许" : "禁止"}
              </span>
              <span style={{ color: "var(--text2)" }}>
                外部调用: {policy.external_calls_allowed ? "允许" : "禁止"}
              </span>
              <span style={{ color: "var(--text2)" }}>
                Secret 存储: {policy.secret_storage_allowed ? "允许" : "禁止"}
              </span>
              {!policy.allowed && (
                <span style={{ color: "var(--red)", fontWeight: "bold" }}>
                  {policy.reason}
                </span>
              )}
            </div>
          );
        })()}
      </div>

      {/* T041: Navigation index status banner */}
      {bundle && (
        <div
          className="card"
          style={{
            padding: "8px 14px",
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontSize: 12,
            flexWrap: "wrap",
          }}
        >
          <span
            className={`badge badge-${hasNav ? "supported" : "unknown"}`}
            style={{ fontSize: 11 }}
          >
            {hasNav ? "T041 导航索引" : "旧版 Bundle"}
          </span>
          {hasNav && nav && (
            <>
              <span style={{ color: "var(--text2)" }}>
                入口: {nav.entrypoints.filter((e: any) => e.available).length} /
                {nav.entrypoints.length} 可用
              </span>
              <span style={{ color: "var(--text2)" }}>
                概念路由: {nav.concept_routes.length}
              </span>
              <span style={{ color: "var(--text2)" }}>
                边路由: {nav.edge_routes.length}
              </span>
            </>
          )}
          {qs?.golden_spec_used && (
            <span style={{ color: "var(--green)" }}>
              P={(qs.selected_precision_like * 100).toFixed(0)}% R=
              {(qs.selected_recall_like * 100).toFixed(0)}%
            </span>
          )}
          {hasNav && nav.limitations.length > 0 && (
            <span style={{ color: "var(--yellow)" }}>
              局限: {nav.limitations.length}
            </span>
          )}
        </div>
      )}

      {/* Input area */}
      <div className="qa-input-area">
        <textarea
          className="form-input qa-input"
          rows={2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，如：这个项目整体实现了什么？"
        />
        <button
          className="btn btn-primary"
          onClick={handleAsk}
          disabled={!question.trim()}
        >
          提问
        </button>
      </div>

      {/* Suggested questions */}
      <div className="qa-suggestions">
        {suggestedToShow.map((q) => (
          <button
            key={q}
            className="btn btn-secondary qa-suggestion-btn"
            onClick={() => handleSuggested(q)}
          >
            {q}
          </button>
        ))}
      </div>

      {/* History */}
      {history.map((result, idx) => (
        <AgentQAResultCard
          key={idx}
          result={result}
          isLatest={idx === 0}
          onNavigateNode={onNavigateNode}
          onSuggested={handleSuggested}
        />
      ))}

      {history.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 14, color: "var(--text2)", marginBottom: 12 }}>
            点击上方建议问题，或直接输入您的问题。
          </div>
          <div style={{ fontSize: 12, color: "var(--text2)" }}>
            支持 {hasNav ? "12" : "9"} 类问题：项目概述、概念映射、RTL 对应、置信度解释、共享 RTL、关键证据、不确定性、节点解释
            {hasNav && "、导航入口、下一步建议、噪声概念、完整证据链、边证据、质量评估"}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Single result card with trace display                             */
/* ------------------------------------------------------------------ */

function AgentQAResultCard({
  result,
  isLatest,
  onNavigateNode,
  onSuggested,
}: {
  result: AgentRunResult;
  isLatest: boolean;
  onNavigateNode: (id: string) => void;
  onSuggested: (q: string) => void;
}) {
  const a = result.answer;
  const trace = result.trace;
  const [showTrace, setShowTrace] = useState(false);

  return (
    <div className="card qa-answer-card">
      <div className="qa-question">{a.question}</div>

      {/* Provider badge + T043 policy/audit */}
      <div style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span
          className={`badge badge-${
            result.provider === "deterministic"
              ? "supported"
              : result.provider === "offline_mock"
              ? "inferred"
              : "unknown"
          }`}
          style={{ fontSize: 10 }}
        >
          {result.provider === "deterministic"
            ? "确定性 Agent"
            : result.provider === "offline_mock"
            ? "Offline Mock"
            : "External Disabled"}
        </span>
        {/* T043: Policy decision badge */}
        <span
          className={`badge badge-${result.policy_result.allowed ? "supported" : "unknown"}`}
          style={{ fontSize: 10 }}
        >
          策略: {result.policy_result.allowed ? "允许" : "拒绝"}
        </span>
        <span style={{ fontSize: 11, color: "var(--text2)" }}>
          外部调用: {result.external_calls_made ? "是" : "否"}
        </span>
        {result.artifacts_used.length > 0 && (
          <span style={{ fontSize: 11, color: "var(--text2)" }}>
            artifacts: {result.artifacts_used.length}
          </span>
        )}
        <button
          className="btn btn-secondary"
          style={{ fontSize: 10, padding: "2px 8px", marginLeft: "auto" }}
          onClick={() => setShowTrace((s) => !s)}
        >
          {showTrace ? "隐藏 Trace" : "查看 Trace"}
        </button>
      </div>

      {/* T043: Audit event summary */}
      <div style={{ marginBottom: 8, fontSize: 10, color: "var(--text2)", display: "flex", gap: 10, flexWrap: "wrap" }}>
        <span>Audit: {result.audit_event.event_id}</span>
        <span>预览: {result.audit_event.question_preview}</span>
        <span>策略原因: {result.audit_event.policy_reason.slice(0, 60)}{result.audit_event.policy_reason.length > 60 ? "..." : ""}</span>
      </div>

      <div className="qa-answer">{a.answer}</div>

      {/* Evidence-chain summary (T034) */}
      <div className="qa-chain">
        <div className="qa-chain-item">
          <span className="qa-chain-label">结论：</span>
          <span className="qa-chain-text">{a.conclusion}</span>
        </div>
        <div className="qa-chain-item">
          <span className="qa-chain-label">强度：</span>
          <span
            className={`badge badge-${
              a.strength === "supported"
                ? "supported"
                : a.strength === "inferred"
                ? "inferred"
                : "unknown"
            }`}
          >
            {a.strength}
          </span>
        </div>
        <div className="qa-chain-item">
          <span className="qa-chain-label">局限：</span>
          <span className="qa-chain-text" style={{ color: "var(--yellow)" }}>
            {a.limitations_summary}
          </span>
        </div>
      </div>

      {/* Trace display (T042) */}
      {showTrace && (
        <div
          className="card"
          style={{
            marginTop: 10,
            padding: 10,
            background: "rgba(0,0,0,0.2)",
            fontSize: 11,
          }}
        >
          <div style={{ fontWeight: "bold", marginBottom: 6, fontSize: 12 }}>
            Run Trace ({trace.trace_id}) | Policy v{result.policy_result.policy_version}
          </div>
          <div style={{ color: "var(--text2)", marginBottom: 4 }}>
            Provider: {trace.provider_kind} | Intent: {trace.matched_intent}
          </div>
          {trace.steps.map((step) => (
            <div key={step.step_id} style={{ marginBottom: 6, paddingLeft: 8, borderLeft: "2px solid var(--border)" }}>
              <span style={{ fontWeight: "bold" }}>{step.kind}</span>
              <span style={{ color: "var(--text2)", marginLeft: 6 }}>
                {step.description}
              </span>
              {step.input_artifacts.length > 0 && (
                <div style={{ color: "var(--text2)", marginTop: 2 }}>
                  输入: {step.input_artifacts.join(", ")}
                </div>
              )}
              <div style={{ color: "var(--green)", marginTop: 2 }}>
                输出: {step.output_summary}
              </div>
            </div>
          ))}
          {trace.artifacts_used.length > 0 && (
            <div style={{ marginTop: 6 }}>
              <span style={{ fontWeight: "bold" }}>Artifacts used:</span>{" "}
              {trace.artifacts_used.join(", ")}
            </div>
          )}
          {trace.evidence_ids.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <span style={{ fontWeight: "bold" }}>Evidence IDs:</span>{" "}
              {trace.evidence_ids.slice(0, 5).join(", ")}
              {trace.evidence_ids.length > 5 && ` +${trace.evidence_ids.length - 5} more`}
            </div>
          )}
          {trace.limitations.length > 0 && (
            <div style={{ marginTop: 4, color: "var(--yellow)" }}>
              <span style={{ fontWeight: "bold" }}>Limitations:</span>{" "}
              {trace.limitations.join("; ")}
            </div>
          )}
        </div>
      )}

      {/* Referenced nodes (clickable) */}
      {a.referenced_nodes.length > 0 && (
        <div className="qa-refs">
          <span className="qa-refs-label">相关节点：</span>
          {a.referenced_nodes.slice(0, 8).map((id) => (
            <button
              key={id}
              className="qa-ref-btn"
              onClick={() => onNavigateNode(id)}
            >
              {id.length > 20 ? id.slice(0, 20) + "…" : id}
            </button>
          ))}
        </div>
      )}

      {/* Referenced claims (clickable) */}
      {a.referenced_claims.length > 0 && (
        <div className="qa-refs">
          <span className="qa-refs-label">Claims：</span>
          {a.referenced_claims.slice(0, 8).map((id) => (
            <button
              key={id}
              className="qa-ref-btn"
              onClick={() => onNavigateNode(id)}
            >
              {id.length > 20 ? id.slice(0, 20) + "…" : id}
            </button>
          ))}
        </div>
      )}

      {/* Referenced evidence IDs */}
      {a.referenced_evidence.length > 0 && (
        <div className="qa-refs">
          <span className="qa-refs-label">证据 ID：</span>
          {a.referenced_evidence.slice(0, 6).map((id) => (
            <span
              key={id}
              className="qa-ref-btn"
              style={{ cursor: "default" }}
              title={id}
            >
              {id.length > 25 ? id.slice(0, 25) + "…" : id}
            </span>
          ))}
          {a.referenced_evidence.length > 6 && (
            <span style={{ fontSize: 10, color: "var(--text2)" }}>
              +{a.referenced_evidence.length - 6} 条
            </span>
          )}
        </div>
      )}

      {/* Follow up */}
      {isLatest && a.follow_up_questions.length > 0 && (
        <div className="qa-followup">
          <span className="qa-refs-label">继续提问：</span>
          {a.follow_up_questions.slice(0, 3).map((q) => (
            <button
              key={q}
              className="btn btn-secondary qa-suggestion-btn"
              style={{ fontSize: 11 }}
              onClick={() => onSuggested(q)}
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default AgentQA;
