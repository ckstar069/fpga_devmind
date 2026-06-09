import { useState, useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import type {
  ProjectBundle,
  ProjectBundleSummary,
} from "./types";
import Overview from "./pages/Overview";
import ProjectGraph from "./pages/ProjectGraph";
import UnderstandingCardPage from "./pages/UnderstandingCard";
import Evidence from "./pages/Evidence";
import AgentQA from "./pages/AgentQA";
import RawData from "./pages/RawData";
import Settings from "./pages/Settings";

type Page = "overview" | "graph" | "card" | "evidence" | "agent" | "raw" | "settings";

const NAV_ITEMS: { key: Page; icon: string; label: string }[] = [
  { key: "overview", icon: "📊", label: "Overview" },
  { key: "graph", icon: "🔗", label: "Project Graph" },
  { key: "card", icon: "🧠", label: "Understanding Card" },
  { key: "evidence", icon: "📄", label: "Evidence" },
  { key: "agent", icon: "💬", label: "Agent 问答" },
  { key: "raw", icon: "📋", label: "Raw Data" },
  { key: "settings", icon: "⚙️", label: "Settings" },
];

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [bundle, setBundle] = useState<ProjectBundle | null>(null);
  const [summary, setSummary] = useState<ProjectBundleSummary | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-load default bundle on startup
  useEffect(() => {
    (async () => {
      try {
        const defaultPath = await invoke<string | null>("get_default_bundle_path");
        if (defaultPath) {
          setLoading(true);
          const result = await invoke<ProjectBundle>("load_project_bundle", {
            path: defaultPath,
          });
          setBundle(result);
          const s = await invoke<ProjectBundleSummary>("get_bundle_summary");
          setSummary(s);
        }
      } catch {
        // silently ignore
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const loadBundle = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await invoke<ProjectBundle>("load_project_bundle", {
        path,
      });
      setBundle(result);
      const s = await invoke<ProjectBundleSummary>("get_bundle_summary");
      setSummary(s);
      setSelectedNodeId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleNavigateNode = useCallback((id: string) => {
    setSelectedNodeId(id);
  }, []);

  const handleNavigateGraph = useCallback(() => {
    setPage("graph");
  }, []);

  const handleNavigateFromAgent = useCallback((id: string) => {
    setSelectedNodeId(id);
    setPage("card");
  }, []);

  const renderPage = () => {
    if (!bundle || !summary) {
      return (
        <div className="empty-state">
          <h2>FPGA DevMind</h2>
          <p>请选择 project_understanding bundle 目录。前往 Settings 页面输入路径。</p>
          <button
            className="btn btn-primary"
            style={{ marginTop: 16 }}
            onClick={() => setPage("settings")}
          >
            前往 Settings
          </button>
        </div>
      );
    }

    switch (page) {
      case "overview":
        return (
          <Overview
            summary={summary}
            bundle={bundle}
            onSelectNode={handleNavigateNode}
            onNavigateGraph={handleNavigateGraph}
          />
        );
      case "graph":
        return (
          <ProjectGraph
            bundle={bundle}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
        );
      case "card":
        return (
          <UnderstandingCardPage
            bundle={bundle}
            selectedNodeId={selectedNodeId}
            onSelectNode={handleNavigateNode}
          />
        );
      case "evidence":
        return <Evidence bundle={bundle} />;
      case "agent":
        return (
          <AgentQA
            bundle={bundle}
            selectedNodeId={selectedNodeId}
            onNavigateNode={handleNavigateFromAgent}
          />
        );
      case "raw":
        return <RawData bundle={bundle} />;
      case "settings":
        return (
          <Settings
            currentPath={summary.path}
            onLoad={loadBundle}
            loading={loading}
            error={error}
          />
        );
    }
  };

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-title">FPGA DevMind</div>
        <div className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <div
              key={item.key}
              className={`nav-item ${page === item.key ? "active" : ""}`}
              onClick={() => setPage(item.key)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>
        {summary && (
          <div style={{ padding: "8px 16px", fontSize: 11, color: "var(--text2)" }}>
            {summary.project_id}
          </div>
        )}
        {selectedNodeId && (
          <div
            style={{
              padding: "6px 16px",
              fontSize: 11,
              color: "var(--accent)",
              borderTop: "1px solid var(--border)",
              marginTop: 4,
              cursor: "pointer",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            onClick={() => setPage("card")}
          >
            📍 {selectedNodeId.slice(0, 24)}…
          </div>
        )}
      </nav>
      <main className="main-content">{renderPage()}</main>
    </div>
  );
}

export default App;
