import { useState, useMemo } from "react";
import type { ProjectBundle } from "../types";
import { SUGGESTED_QUESTIONS } from "../utils/agent";
import {
  runAgent,
  PROVIDER_CAPABILITIES,
  getAvailableProviderKinds,
  evaluateProviderPolicy,
  buildDryRunExternalRequestPlan,
  buildExternalRequestPackage,
  createPreviewDecision,
  approveExternalRequest,
  denyExternalRequest,
  getSelectableExternalProviderIds,
  getExternalProviderDescriptor,
  executeExternalProviderPipeline,
  createEmptyEphemeralProviderSession,
  createEphemeralProviderSession,
  clearEphemeralProviderSession,
  touchEphemeralProviderSession,
  evaluateRealSendGate,
  buildRealProviderAuditSummary,
  appendRealProviderAudit,
} from "../agent";
import type { AgentRunResult, AgentProviderKind } from "../agent";
import type { ExternalRequestPlan, ExternalRequestPackage, ApprovalDecision } from "../agent";
import type { ExternalExecutionResult, ExternalProviderId, ExternalTransportKind } from "../agent";
import type {
  EphemeralProviderSessionState,
  RealProviderInvocationResult,
  RealSendGateDecision,
} from "../agent";

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
          bundle={bundle}
          selectedNodeId={selectedNodeId}
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
  bundle,
  selectedNodeId,
}: {
  result: AgentRunResult;
  isLatest: boolean;
  onNavigateNode: (id: string) => void;
  onSuggested: (q: string) => void;
  bundle: ProjectBundle | null;
  selectedNodeId: string | null;
}) {
  const a = result.answer;
  const trace = result.trace;
  const [showTrace, setShowTrace] = useState(false);
  const [showContextPreview, setShowContextPreview] = useState(false);
  const [dryRunPlan, setDryRunPlan] = useState<ExternalRequestPlan | null>(null);

  // T045: External request package preview + approval gate
  const [showT045Preview, setShowT045Preview] = useState(false);
  const [extPkg, setExtPkg] = useState<ExternalRequestPackage | null>(null);
  const [approvalDecision, setApprovalDecision] = useState<ApprovalDecision | null>(null);

  // T046: External execution pipeline preview
  const [showT046Execution, setShowT046Execution] = useState(false);
  const [t046ExecResult, setT046ExecResult] = useState<ExternalExecutionResult | null>(null);
  const [t046ProviderId, setT046ProviderId] = useState<ExternalProviderId>("mock_external_llm");
  const [t046TransportKind, setT046TransportKind] = useState<ExternalTransportKind>("mock");

  // T047: Ephemeral real provider adapter
  const [showT047Adapter, setShowT047Adapter] = useState(false);
  const [t047Session, setT047Session] = useState<EphemeralProviderSessionState>(
    createEmptyEphemeralProviderSession()
  );
  const [t047EndpointUrl, setT047EndpointUrl] = useState("");
  const [t047ModelName, setT047ModelName] = useState("gpt-4o-mini");
  const [t047ApiKey, setT047ApiKey] = useState("");
  const [t047SendGate, setT047SendGate] = useState<RealSendGateDecision | null>(null);
  const [t047RealResult, setT047RealResult] = useState<RealProviderInvocationResult | null>(null);
  const [t047ShowConfirm, setT047ShowConfirm] = useState(false);
  const [t047Loading, setT047Loading] = useState(false);

  const handleShowContextPreview = () => {
    if (!showContextPreview) {
      // Build dry-run plan on first open
      const plan = buildDryRunExternalRequestPlan(bundle, a.question, selectedNodeId);
      setDryRunPlan(plan);
    }
    setShowContextPreview((s) => !s);
  };

  const handleShowT045Preview = () => {
    if (!showT045Preview) {
      const pkg = buildExternalRequestPackage(bundle, a.question, selectedNodeId);
      setExtPkg(pkg);
      setApprovalDecision(createPreviewDecision(pkg));
    }
    setShowT045Preview((s) => !s);
  };

  const handleSimulateApprove = () => {
    if (extPkg) {
      setApprovalDecision(approveExternalRequest(extPkg));
    }
  };

  const handleDeny = () => {
    if (extPkg) {
      setApprovalDecision(denyExternalRequest(extPkg, "User denied this request."));
    }
  };

  // T046: Run execution pipeline
  const runT046Execution = (approvalAction: "preview_only" | "simulate_approve" | "deny") => {
    const execResult = executeExternalProviderPipeline({
      bundle,
      question: a.question,
      selectedNodeId,
      provider_id: t046ProviderId,
      transport_kind: t046TransportKind,
      approval_action: approvalAction,
    });
    setT046ExecResult(execResult);
  };

  const handleShowT046Execution = () => {
    if (!showT046Execution) {
      // Run initial preview on first open
      runT046Execution("preview_only");
    }
    setShowT046Execution((s) => !s);
  };

  // T047: Ephemeral provider handlers
  const handleConfigureT047Session = () => {
    if (t047ApiKey.trim() && t047EndpointUrl.trim()) {
      const session = createEphemeralProviderSession({
        api_key: t047ApiKey,
        endpoint_url: t047EndpointUrl,
        model_name: t047ModelName,
      });
      setT047Session(session);
      // Evaluate send gate immediately after config
      evaluateT047SendGate(session);
    }
  };

  const handleClearT047Session = () => {
    setT047Session(clearEphemeralProviderSession(t047Session));
    setT047ApiKey("");
    setT047SendGate(null);
    setT047RealResult(null);
    setT047ShowConfirm(false);
  };

  const evaluateT047SendGate = (session: EphemeralProviderSessionState) => {
    const pkg = buildExternalRequestPackage(bundle, a.question, selectedNodeId);
    const decision = approveExternalRequest(pkg);
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: pkg.request_id,
      approval_state: decision.state,
      send_allowed_by_user: true,
      session,
      endpoint_url: t047EndpointUrl,
    });
    setT047SendGate(gate);
  };

  const handleT047RealSend = async () => {
    if (!t047SendGate?.allowed) return;
    setT047Loading(true);
    setT047ShowConfirm(false);

    try {
      const pkg = buildExternalRequestPackage(bundle, a.question, selectedNodeId);
      const touchedSession = touchEphemeralProviderSession(t047Session);
      setT047Session(touchedSession);

      // Extract prompt previews from request package
      const systemPrompt =
        pkg.request_plan.hypothetical_request_preview.system_prompt_preview;
      const userPrompt =
        pkg.request_plan.hypothetical_request_preview.user_prompt_preview;

      // Invoke Tauri backend command
      const result: RealProviderInvocationResult = await (window as any).__TAURI__.core.invoke(
        "invoke_openai_compatible_ephemeral",
        {
          endpoint_url: t047EndpointUrl,
          model_name: t047ModelName,
          api_key: t047ApiKey,
          system_prompt: systemPrompt,
          user_prompt: userPrompt,
          request_id: pkg.request_id,
        }
      );

      setT047RealResult(result);

      // Record redacted audit
      const audit = buildRealProviderAuditSummary(
        pkg.request_id,
        "openai_compatible_ephemeral",
        t047ModelName,
        t047Session.endpoint_origin_preview,
        t047Session.key_fingerprint,
        result.sent,
        result.status,
        result.answer_text_preview
      );
      appendRealProviderAudit(audit);
    } catch (err: any) {
      setT047RealResult({
        schema_version: "real-provider-contract-0.1",
        request_id: "req-error",
        provider_id: "openai_compatible_ephemeral",
        sent: false,
        blocked: true,
        status: "network_error",
        answer_text_preview: "",
        error_preview: String(err),
        raw_response_stored: false,
        audit_redacted: true,
        created_at: new Date().toISOString(),
      } as RealProviderInvocationResult);
    } finally {
      setT047Loading(false);
    }
  };

  const handleShowT047Adapter = () => {
    if (!showT047Adapter) {
      // Evaluate gate on first open if session exists
      if (t047Session.configured) {
        evaluateT047SendGate(t047Session);
      }
    }
    setShowT047Adapter((s) => !s);
  };

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
        <button
          className="btn btn-secondary"
          style={{ fontSize: 10, padding: "2px 8px" }}
          onClick={handleShowContextPreview}
        >
          {showContextPreview ? "隐藏上下文预览" : "上下文预览 (Dry-run)"}
        </button>
        <button
          className="btn btn-secondary"
          style={{ fontSize: 10, padding: "2px 8px" }}
          onClick={handleShowT045Preview}
        >
          {showT045Preview ? "隐藏 T045 预览" : "T045 请求包预览"}
        </button>
        <button
          className="btn btn-secondary"
          style={{ fontSize: 10, padding: "2px 8px" }}
          onClick={handleShowT046Execution}
        >
          {showT046Execution ? "隐藏 T046 执行" : "T046 执行管线"}
        </button>
        <button
          className="btn btn-secondary"
          style={{ fontSize: 10, padding: "2px 8px" }}
          onClick={handleShowT047Adapter}
        >
          {showT047Adapter ? "隐藏 T047 真实 Provider" : "T047 真实 Provider"}
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

      {/* T044: Dry-run Context Preview */}
      {showContextPreview && dryRunPlan && (
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
            Dry-run 外部请求上下文预览 ({dryRunPlan.schema_version})
          </div>
          <div style={{ color: "var(--red)", marginBottom: 6, fontWeight: "bold" }}>
            ⚠️ {dryRunPlan.blocked_reason}
          </div>
          <div style={{ color: "var(--text2)", marginBottom: 4 }}>
            策略版本: {dryRunPlan.policy_version} | 预估 Token: {dryRunPlan.context_bundle.token_estimate_rough}
          </div>

          {/* Artifacts used */}
          {dryRunPlan.artifacts_used.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontWeight: "bold" }}>使用 Artifacts:</span>{" "}
              {dryRunPlan.artifacts_used.join(", ")}
            </div>
          )}

          {/* Context items summary */}
          {dryRunPlan.hypothetical_request_preview.context_items_summary.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontWeight: "bold", marginBottom: 2 }}>上下文项 ({dryRunPlan.context_bundle.context_items.length}):</div>
              {dryRunPlan.hypothetical_request_preview.context_items_summary.map((summary, idx) => (
                <div key={idx} style={{ paddingLeft: 8, color: "var(--text2)" }}>
                  • {summary}
                </div>
              ))}
            </div>
          )}

          {/* System prompt preview */}
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontWeight: "bold", marginBottom: 2 }}>System Prompt 预览:</div>
            <pre style={{ margin: 0, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {dryRunPlan.hypothetical_request_preview.system_prompt_preview}
            </pre>
          </div>

          {/* User prompt preview */}
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontWeight: "bold", marginBottom: 2 }}>User Prompt 预览:</div>
            <pre style={{ margin: 0, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {dryRunPlan.hypothetical_request_preview.user_prompt_preview}
            </pre>
          </div>

          {/* Limitations */}
          {dryRunPlan.limitations.length > 0 && (
            <div style={{ marginTop: 6, color: "var(--yellow)" }}>
              <span style={{ fontWeight: "bold" }}>局限:</span>{" "}
              {dryRunPlan.limitations.join("; ")}
            </div>
          )}
        </div>
      )}

      {/* T045: External Request Package Preview + Approval Gate */}
      {showT045Preview && extPkg && (
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
            T045 外部请求包预览 ({extPkg.schema_version})
          </div>
          <div style={{ color: "var(--red)", marginBottom: 6, fontWeight: "bold" }}>
            ⚠️ Network send remains blocked in T045
          </div>

          {/* Request metadata */}
          <div style={{ marginBottom: 6, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <span><strong>Request ID:</strong> {extPkg.request_id}</span>
            <span><strong>State:</strong> {approvalDecision?.state || "not_requested"}</span>
            <span><strong>Send Allowed:</strong> {extPkg.send_allowed ? "Yes" : "No"}</span>
            <span><strong>Provider:</strong> {extPkg.provider_kind}</span>
            <span><strong>Policy:</strong> v{extPkg.policy_version}</span>
            <span><strong>Tokens:</strong> {extPkg.request_body_preview.total_tokens_estimate}</span>
            <span><strong>Items:</strong> {extPkg.request_body_preview.context_items_count}</span>
          </div>

          {/* Risk summary */}
          <div style={{ marginBottom: 6, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
            <div style={{ fontWeight: "bold", marginBottom: 2 }}>Risk Summary:</div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <span>Sensitive: {extPkg.risk_summary.contains_sensitive_question ? "Yes" : "No"}</span>
              <span>Raw question: {extPkg.risk_summary.raw_question_included ? "Included" : "Excluded"}</span>
              <span>API key: {extPkg.risk_summary.api_key_required ? "Required" : "Not required"}</span>
              <span>Network: {extPkg.risk_summary.network_call_planned ? "Planned" : "Blocked"}</span>
              <span>Secret storage: {extPkg.risk_summary.secret_storage_planned ? "Planned" : "Blocked"}</span>
              <span>Policy block: {extPkg.risk_summary.external_call_blocked_by_policy ? "Yes" : "No"}</span>
            </div>
          </div>

          {/* Artifacts used */}
          {extPkg.artifacts_used.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontWeight: "bold" }}>使用 Artifacts:</span>{" "}
              {extPkg.artifacts_used.join(", ")}
            </div>
          )}

          {/* Messages preview */}
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontWeight: "bold", marginBottom: 2 }}>Messages Preview:</div>
            {extPkg.request_body_preview.messages_preview.map((msg, idx) => (
              <div key={idx} style={{ marginBottom: 4 }}>
                <div style={{ fontWeight: "bold", fontSize: 10 }}>[{msg.role}]</div>
                <pre style={{ margin: 0, padding: 4, background: "rgba(0,0,0,0.3)", borderRadius: 4, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 10 }}>
                  {msg.content_preview}
                </pre>
              </div>
            ))}
          </div>

          {/* Limitations */}
          {extPkg.limitations.length > 0 && (
            <div style={{ marginBottom: 6, color: "var(--yellow)" }}>
              <span style={{ fontWeight: "bold" }}>Limitations:</span>{" "}
              {extPkg.limitations.join("; ")}
            </div>
          )}

          {/* Approval decision display */}
          {approvalDecision && (
            <div style={{ marginBottom: 6, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
              <div style={{ fontWeight: "bold", marginBottom: 2 }}>Approval Decision ({approvalDecision.schema_version}):</div>
              <div>State: <span style={{ fontWeight: "bold", color: approvalDecision.state === "approved_but_blocked" ? "var(--green)" : approvalDecision.state === "denied" ? "var(--red)" : "var(--text2)" }}>{approvalDecision.state}</span></div>
              <div>Send allowed: {approvalDecision.send_allowed ? "Yes" : "No"}</div>
              <div style={{ color: "var(--text2)", marginTop: 2 }}>{approvalDecision.reason}</div>
            </div>
          )}

          {/* Approval gate buttons */}
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              className="btn btn-primary"
              style={{ fontSize: 10, padding: "2px 8px" }}
              onClick={handleSimulateApprove}
              disabled={!extPkg || approvalDecision?.state === "approved_but_blocked"}
            >
              Simulate Manual Approval
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 10, padding: "2px 8px" }}
              onClick={handleDeny}
              disabled={!extPkg || approvalDecision?.state === "denied"}
            >
              Deny
            </button>
          </div>
        </div>
      )}

      {/* T046: External Execution Pipeline Preview */}
      {showT046Execution && t046ExecResult && (
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
            T046 外部执行管线预览 ({t046ExecResult.schema_version})
          </div>

          {/* Safety banner */}
          <div style={{ color: "var(--red)", marginBottom: 6, fontWeight: "bold" }}>
            ⚠️ No real network call is available in T046
          </div>
          <div style={{ color: "var(--text2)", marginBottom: 6, fontSize: 10 }}>
            Mock transport is deterministic and offline only
          </div>

          {/* Provider selector */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: "bold", marginBottom: 4, fontSize: 11 }}>Provider:</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {getSelectableExternalProviderIds().map((id) => {
                const desc = getExternalProviderDescriptor(id);
                return (
                  <button
                    key={id}
                    className={`btn ${t046ProviderId === id ? "btn-primary" : "btn-secondary"}`}
                    style={{ fontSize: 10, padding: "2px 8px" }}
                    onClick={() => setT046ProviderId(id)}
                    title={desc?.description || ""}
                  >
                    {desc?.label || id}
                    {desc?.status === "future" && " (Future)"}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Transport kind selector */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: "bold", marginBottom: 4, fontSize: 11 }}>Transport:</div>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className={`btn ${t046TransportKind === "blocked" ? "btn-primary" : "btn-secondary"}`}
                style={{ fontSize: 10, padding: "2px 8px" }}
                onClick={() => setT046TransportKind("blocked")}
              >
                Blocked
              </button>
              <button
                className={`btn ${t046TransportKind === "mock" ? "btn-primary" : "btn-secondary"}`}
                style={{ fontSize: 10, padding: "2px 8px" }}
                onClick={() => setT046TransportKind("mock")}
              >
                Mock
              </button>
            </div>
          </div>

          {/* Execution result */}
          <div style={{ marginBottom: 8, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
            <div style={{ fontWeight: "bold", marginBottom: 4 }}>Execution Result:</div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <span>Sent: <strong>{t046ExecResult.sent ? "Yes" : "No"}</strong></span>
              <span>Blocked: <strong>{t046ExecResult.blocked ? "Yes" : "No"}</strong></span>
              <span>Mock: <strong>{t046ExecResult.mock_response ? "Yes" : "No"}</strong></span>
              <span>Send allowed: <strong>{t046ExecResult.send_allowed ? "Yes" : "No"}</strong></span>
              <span>Approval: <strong>{t046ExecResult.approval_state}</strong></span>
              <span>Provider: <strong>{t046ExecResult.provider_id}</strong></span>
            </div>
          </div>

          {/* Egress guard */}
          <div style={{ marginBottom: 8, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
            <div style={{ fontWeight: "bold", marginBottom: 2 }}>Egress Guard ({t046ExecResult.egress_guard.schema_version}):</div>
            <div>Allowed: <strong>{t046ExecResult.egress_guard.allowed ? "Yes" : "No"}</strong></div>
            <div style={{ color: "var(--text2)", marginTop: 2 }}>{t046ExecResult.egress_guard.reason}</div>
          </div>

          {/* Mock answer preview */}
          {t046ExecResult.mock_response && t046ExecResult.answer_preview && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontWeight: "bold", marginBottom: 2 }}>Mock Answer Preview:</div>
              <pre style={{ margin: 0, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 10 }}>
                {t046ExecResult.answer_preview}
              </pre>
            </div>
          )}

          {/* Artifacts & evidence */}
          {t046ExecResult.artifacts_used.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontWeight: "bold" }}>Artifacts:</span>{" "}
              {t046ExecResult.artifacts_used.join(", ")}
            </div>
          )}
          {t046ExecResult.evidence_ids.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontWeight: "bold" }}>Evidence:</span>{" "}
              {t046ExecResult.evidence_ids.slice(0, 5).join(", ")}
              {t046ExecResult.evidence_ids.length > 5 && ` +${t046ExecResult.evidence_ids.length - 5} more`}
            </div>
          )}

          {/* Limitations */}
          {t046ExecResult.limitations.length > 0 && (
            <div style={{ marginBottom: 6, color: "var(--yellow)" }}>
              <span style={{ fontWeight: "bold" }}>Limitations:</span>{" "}
              {t046ExecResult.limitations.join("; ")}
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            <button
              className="btn btn-primary"
              style={{ fontSize: 10, padding: "2px 8px" }}
              onClick={() => runT046Execution("preview_only")}
            >
              Preview only
            </button>
            <button
              className="btn btn-primary"
              style={{ fontSize: 10, padding: "2px 8px" }}
              onClick={() => runT046Execution("simulate_approve")}
            >
              Simulate approval + {t046TransportKind}
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 10, padding: "2px 8px" }}
              onClick={() => runT046Execution("deny")}
            >
              Deny
            </button>
          </div>
        </div>
      )}

      {/* T047: Ephemeral Real Provider Adapter */}
      {showT047Adapter && (
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
            T047 真实 Provider 适配器（Ephemeral）
          </div>

          {/* Safety banner */}
          <div style={{ color: "var(--red)", marginBottom: 6, fontWeight: "bold" }}>
            ⚠️ 真实网络请求 — 仅用于明确了解风险的用户
          </div>
          <div style={{ color: "var(--text2)", marginBottom: 6, fontSize: 10 }}>
            API key 仅在内存中存在，不会写入磁盘、localStorage 或任何日志
          </div>
          <div style={{ color: "var(--text2)", marginBottom: 6, fontSize: 10 }}>
            Raw key 永远不会写入项目文件或审计日志
          </div>

          {/* Session configuration */}
          {!t047Session.configured ? (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontWeight: "bold", marginBottom: 4 }}>配置 Ephemeral Session:</div>
              <div style={{ marginBottom: 4 }}>
                <label style={{ display: "block", fontSize: 10, marginBottom: 2 }}>Endpoint URL (HTTPS only):</label>
                <input
                  type="text"
                  className="form-input"
                  style={{ fontSize: 11, padding: "3px 6px", width: "100%" }}
                  placeholder="https://api.openai.com/v1/chat/completions"
                  value={t047EndpointUrl}
                  onChange={(e) => setT047EndpointUrl(e.target.value)}
                />
              </div>
              <div style={{ marginBottom: 4 }}>
                <label style={{ display: "block", fontSize: 10, marginBottom: 2 }}>Model name:</label>
                <input
                  type="text"
                  className="form-input"
                  style={{ fontSize: 11, padding: "3px 6px", width: "100%" }}
                  placeholder="gpt-4o-mini"
                  value={t047ModelName}
                  onChange={(e) => setT047ModelName(e.target.value)}
                />
              </div>
              <div style={{ marginBottom: 6 }}>
                <label style={{ display: "block", fontSize: 10, marginBottom: 2 }}>API Key (仅内存，不保存):</label>
                <input
                  type="password"
                  className="form-input"
                  style={{ fontSize: 11, padding: "3px 6px", width: "100%" }}
                  placeholder="sk-..."
                  value={t047ApiKey}
                  onChange={(e) => setT047ApiKey(e.target.value)}
                />
              </div>
              <button
                className="btn btn-primary"
                style={{ fontSize: 10, padding: "2px 8px" }}
                onClick={handleConfigureT047Session}
                disabled={!t047EndpointUrl.trim() || !t047ApiKey.trim()}
              >
                配置 Session
              </button>
            </div>
          ) : (
            <div style={{ marginBottom: 8, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
              <div style={{ fontWeight: "bold", marginBottom: 2 }}>Session Status:</div>
              <div>Provider: {t047Session.provider_id}</div>
              <div>Model: {t047Session.model_name}</div>
              <div>Endpoint: {t047Session.endpoint_origin_preview}</div>
              <div>Key fingerprint: {t047Session.key_fingerprint}</div>
              <div>Storage: <strong>{t047Session.storage}</strong></div>
              <div>Configured: {t047Session.configured ? "Yes" : "No"}</div>
              <button
                className="btn btn-secondary"
                style={{ fontSize: 10, padding: "2px 8px", marginTop: 6 }}
                onClick={handleClearT047Session}
              >
                清除 Session
              </button>
            </div>
          )}

          {/* Real send gate */}
          {t047SendGate && (
            <div style={{ marginBottom: 8, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
              <div style={{ fontWeight: "bold", marginBottom: 2 }}>
                Real Send Gate ({t047SendGate.schema_version}):
              </div>
              <div>
                Allowed:{" "}
                <strong style={{ color: t047SendGate.allowed ? "var(--green)" : "var(--red)" }}>
                  {t047SendGate.allowed ? "Yes" : "No"}
                </strong>
              </div>
              <div style={{ color: "var(--text2)", marginTop: 2 }}>{t047SendGate.reason}</div>
              <div style={{ marginTop: 4, fontSize: 10 }}>
                Conditions: session={t047SendGate.conditions_met.session_configured ? "✓" : "✗"} |{" "}
                key={t047SendGate.conditions_met.key_present ? "✓" : "✗"} |{" "}
                https={t047SendGate.conditions_met.endpoint_https ? "✓" : "✗"} |{" "}
                approval={t047SendGate.conditions_met.approval_adequate ? "✓" : "✗"} |{" "}
                consent={t047SendGate.conditions_met.user_explicit_consent ? "✓" : "✗"}
              </div>
            </div>
          )}

          {/* Confirmation dialog */}
          {t047ShowConfirm && (
            <div style={{ marginBottom: 8, padding: 6, background: "rgba(255,0,0,0.1)", borderRadius: 4, border: "1px solid var(--red)" }}>
              <div style={{ fontWeight: "bold", color: "var(--red)", marginBottom: 4 }}>
                确认真实发送
              </div>
              <div style={{ marginBottom: 6 }}>
                我了解这将使用我的临时 API key 发起真实外部网络请求。
                此操作不可撤销，可能产生费用。
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn btn-primary"
                  style={{ fontSize: 10, padding: "2px 8px" }}
                  onClick={handleT047RealSend}
                  disabled={t047Loading}
                >
                  {t047Loading ? "发送中..." : "确认发送一次"}
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: 10, padding: "2px 8px" }}
                  onClick={() => setT047ShowConfirm(false)}
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {/* Real send button */}
          {!t047ShowConfirm && t047Session.configured && (
            <div style={{ marginBottom: 8 }}>
              <button
                className="btn btn-primary"
                style={{ fontSize: 10, padding: "2px 8px" }}
                onClick={() => {
                  evaluateT047SendGate(t047Session);
                  setT047ShowConfirm(true);
                }}
                disabled={t047Loading}
              >
                {t047Loading ? "发送中..." : "发起真实发送"}
              </button>
            </div>
          )}

          {/* Real result */}
          {t047RealResult && (
            <div style={{ marginBottom: 8, padding: 6, background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
              <div style={{ fontWeight: "bold", marginBottom: 4 }}>
                Provider Result ({t047RealResult.schema_version}):
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <span>Sent: <strong>{t047RealResult.sent ? "Yes" : "No"}</strong></span>
                <span>Blocked: <strong>{t047RealResult.blocked ? "Yes" : "No"}</strong></span>
                <span>Status: <strong>{t047RealResult.status}</strong></span>
              </div>
              {t047RealResult.answer_text_preview && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontWeight: "bold", marginBottom: 2 }}>Answer Preview:</div>
                  <pre
                    style={{
                      margin: 0,
                      padding: 6,
                      background: "rgba(0,0,0,0.3)",
                      borderRadius: 4,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      fontSize: 10,
                    }}
                  >
                    {t047RealResult.answer_text_preview}
                  </pre>
                </div>
              )}
              {t047RealResult.error_preview && (
                <div style={{ marginTop: 6, color: "var(--red)" }}>
                  <span style={{ fontWeight: "bold" }}>Error:</span> {t047RealResult.error_preview}
                </div>
              )}
            </div>
          )}

          {/* Limitations */}
          <div style={{ color: "var(--yellow)", fontSize: 10 }}>
            <span style={{ fontWeight: "bold" }}>Limitations:</span>{" "}
            T047 只支持单次发送，不支持 streaming。默认仍使用 mock/blocked transport。
          </div>
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
