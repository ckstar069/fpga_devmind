import { useState, useMemo } from "react";
import type { ProjectBundle, AgentAnswer } from "../types";
import { answerQuestion, SUGGESTED_QUESTIONS } from "../utils/agent";

interface Props {
  bundle: ProjectBundle | null;
  selectedNodeId: string | null;
  onNavigateNode: (id: string) => void;
}

function AgentQA({ bundle, selectedNodeId, onNavigateNode }: Props) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<AgentAnswer[]>([]);

  const handleAsk = () => {
    const q = question.trim();
    if (!q) return;
    const answer = answerQuestion(bundle, q, selectedNodeId);
    setHistory((prev) => [answer, ...prev]);
    setQuestion("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  const handleSuggested = (q: string) => {
    const answer = answerQuestion(bundle, q, selectedNodeId);
    setHistory((prev) => [answer, ...prev]);
  };

  const suggestedToShow = useMemo(() => {
    if (history.length === 0) return SUGGESTED_QUESTIONS;
    return history[0].follow_up_questions.length > 0
      ? history[0].follow_up_questions
      : SUGGESTED_QUESTIONS;
  }, [history]);

  return (
    <div>
      <div className="page-title">Agent 问答</div>
      <div className="page-subtitle">
        确定性问答系统（不调用外部 LLM），基于当前 bundle 数据回答
      </div>

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
      {history.map((a, idx) => (
        <div key={idx} className="card qa-answer-card">
          <div className="qa-question">{a.question}</div>
          <div className="qa-answer">{a.answer}</div>

          {/* Evidence-chain summary (T034) */}
          <div className="qa-chain">
            <div className="qa-chain-item">
              <span className="qa-chain-label">结论：</span>
              <span className="qa-chain-text">{a.conclusion}</span>
            </div>
            <div className="qa-chain-item">
              <span className="qa-chain-label">强度：</span>
              <span className={`badge badge-${
                a.strength === "supported" ? "supported"
                : a.strength === "inferred" ? "inferred"
                : "unknown"
              }`}>
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

          {/* Referenced evidence IDs (clickable concept for now) */}
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
          {idx === 0 && a.follow_up_questions.length > 0 && (
            <div className="qa-followup">
              <span className="qa-refs-label">继续提问：</span>
              {a.follow_up_questions.slice(0, 3).map((q) => (
                <button
                  key={q}
                  className="btn btn-secondary qa-suggestion-btn"
                  style={{ fontSize: 11 }}
                  onClick={() => handleSuggested(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}

      {history.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 14, color: "var(--text2)", marginBottom: 12 }}>
            点击上方建议问题，或直接输入您的问题。
          </div>
          <div style={{ fontSize: 12, color: "var(--text2)" }}>
            支持 9 类问题：项目概述、概念映射、RTL 对应、置信度解释、共享 RTL、关键证据、不确定性、导航指引、节点解释
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentQA;
