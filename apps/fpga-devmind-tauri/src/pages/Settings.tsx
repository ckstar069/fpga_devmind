import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { ProjectInfo } from "../types";

interface Props {
  currentBundle: string | null;
  onLoad: (path: string) => void;
}

function SettingsPage({ currentBundle, onLoad }: Props) {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [conceptMode, setConceptMode] = useState<"auto" | "manual">("auto");
  const [manualConcepts, setManualConcepts] = useState("");
  const [maxConcepts, setMaxConcepts] = useState(12);
  const [outputDir, setOutputDir] = useState("/tmp/fpga_devmind/t035_out");
  const [runStatus, setRunStatus] = useState("");
  const [bundlePath, setBundlePath] = useState(currentBundle ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load project list on mount
  useEffect(() => {
    invoke<ProjectInfo[]>("list_fpga_projects")
      .then(setProjects)
      .catch(() => {});
  }, []);

  // Sync bundlePath when currentBundle changes externally
  useEffect(() => {
    if (currentBundle) setBundlePath(currentBundle);
  }, [currentBundle]);

  const handleRun = async () => {
    if (!selectedProject && conceptMode === "auto") {
      setError("请选择项目");
      return;
    }
    setLoading(true);
    setError("");

    const projectName = selectedProject.split("/").pop() ?? "project";
    const out = outputDir || `/tmp/fpga_devmind/t035_${projectName}`;

    try {
      if (conceptMode === "auto") {
        setRunStatus("tracing concepts (auto-discovery)...");
        await invoke<string>("run_project_trace", {
          project: selectedProject,
          concepts: "auto",
          out,
        });
      } else {
        if (!manualConcepts.trim()) {
          setError("请输入概念名称");
          setLoading(false);
          return;
        }
        setRunStatus("tracing concepts...");
        await invoke<string>("run_project_trace", {
          project: selectedProject,
          concepts: manualConcepts,
          out,
        });
      }

      setRunStatus("loading bundle...");
      await onLoad(out);
      setRunStatus("done");
    } catch (e) {
      setError(String(e));
      setRunStatus("error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-title">Settings</div>

      {/* Current bundle */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Current Bundle</div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="form-input"
            value={bundlePath}
            onChange={(e) => setBundlePath(e.target.value)}
            placeholder="/tmp/fpga_devmind/..."
          />
          <button
            className="btn btn-primary"
            onClick={() => onLoad(bundlePath)}
            disabled={!bundlePath}
          >
            Load
          </button>
        </div>
        {currentBundle && (
          <div style={{ fontSize: 12, color: "var(--green)", marginTop: 4 }}>
            Loaded: {currentBundle}
          </div>
        )}
      </div>

      {/* Project selector */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Run Project Understanding</div>

        <div className="form-group">
          <label className="form-label">Project</label>
          <select
            className="form-input"
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
          >
            <option value="">-- Select Project --</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.path}>
                {p.project_id}
                {!p.has_RTL ? " (no RTL)" : ""}
                {!p.has_tests ? " (no tests)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Concept Mode</label>
          <div style={{ display: "flex", gap: 12 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, cursor: "pointer" }}>
              <input
                type="radio"
                checked={conceptMode === "auto"}
                onChange={() => setConceptMode("auto")}
              />
              Auto-discover
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, cursor: "pointer" }}>
              <input
                type="radio"
                checked={conceptMode === "manual"}
                onChange={() => setConceptMode("manual")}
              />
              Manual
            </label>
          </div>
        </div>

        {conceptMode === "manual" && (
          <div className="form-group">
            <label className="form-label">Concepts (comma-separated)</label>
            <input
              className="form-input"
              value={manualConcepts}
              onChange={(e) => setManualConcepts(e.target.value)}
              placeholder="peak_idx,cfo,smooth_detect"
            />
          </div>
        )}

        {conceptMode === "auto" && (
          <div className="form-group">
            <label className="form-label">Max Concepts</label>
            <input
              className="form-input"
              type="number"
              value={maxConcepts}
              onChange={(e) => setMaxConcepts(Number(e.target.value))}
              min={1}
              max={30}
              style={{ width: 80 }}
            />
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Output Directory</label>
          <input
            className="form-input"
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            placeholder="/tmp/fpga_devmind/..."
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={handleRun}
          disabled={loading || !selectedProject}
          style={{ marginTop: 8 }}
        >
          {loading ? runStatus : "Run Understanding"}
        </button>

        {runStatus && !loading && (
          <div style={{
            fontSize: 13,
            marginTop: 8,
            color: runStatus === "done" ? "var(--green)" : runStatus === "error" ? "var(--red)" : "var(--text2)",
          }}>
            {runStatus === "done" ? "Done" : runStatus}
          </div>
        )}
        {error && (
          <div style={{ fontSize: 12, color: "var(--red)", marginTop: 8, whiteSpace: "pre-wrap" }}>
            {error}
          </div>
        )}
      </div>

      {/* Quick paths */}
      <div className="card">
        <div className="card-title">Quick Load</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[
            "/tmp/fpga_devmind/t035_coarse_auto",
            "/tmp/fpga_devmind/t035_fft_auto",
            "/tmp/fpga_devmind/t034_project_smoke",
          ].map((p) => (
            <button
              key={p}
              className="btn btn-secondary"
              style={{ fontSize: 11 }}
              onClick={() => { setBundlePath(p); onLoad(p); }}
            >
              {p.split("/").pop()}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
