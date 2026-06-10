import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { ProjectInfo, GoldenSpec, EvalResult } from "../types";

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
  const [goldenSpecPath, setGoldenSpecPath] = useState("");
  const [goldenSpec, setGoldenSpec] = useState<GoldenSpec | null>(null);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState("");

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
            "/tmp/fpga_devmind/t037_coarse_auto",
            "/tmp/fpga_devmind/t037_fine_cfo_auto",
            "/tmp/fpga_devmind/t037_fft_auto",
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

      {/* Golden Benchmark (T036) */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">Golden Benchmark</div>

        <div className="form-group">
          <label className="form-label">Golden Spec JSON Path</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              className="form-input"
              value={goldenSpecPath}
              onChange={(e) => setGoldenSpecPath(e.target.value)}
              placeholder="/path/to/golden_spec.json"
            />
            <button
              className="btn btn-secondary"
              onClick={async () => {
                if (!goldenSpecPath) return;
                try {
                  const resp = await fetch(`file://${goldenSpecPath}`);
                  const data: GoldenSpec = await resp.json();
                  setGoldenSpec(data);
                  setEvalError("");
                } catch {
                  // Fallback: try reading via Tauri backend
                  try {
                    const content = await invoke<string>("read_file_content", { path: goldenSpecPath });
                    const data: GoldenSpec = JSON.parse(content);
                    setGoldenSpec(data);
                    setEvalError("");
                  } catch (e2) {
                    setGoldenSpec(null);
                    setEvalError(`Failed to load golden spec: ${e2}`);
                  }
                }
              }}
              disabled={!goldenSpecPath}
            >
              Load
            </button>
          </div>
        </div>

        {goldenSpec && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: "var(--text2)", marginBottom: 8 }}>
              Project: {goldenSpec.project_id} | Core: {goldenSpec.expected_core_concepts.length} | Secondary: {goldenSpec.expected_secondary_concepts.length}
            </div>

            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Expected Core Concepts:</div>
            {goldenSpec.expected_core_concepts.map((gc) => (
              <div key={gc.concept} style={{ fontSize: 12, padding: "3px 0", display: "flex", alignItems: "center", gap: 6 }}>
                <input type="checkbox" checked readOnly />
                <strong>{gc.concept}</strong>
                {gc.aliases.length > 0 && (
                  <span style={{ color: "var(--text2)" }}>(aliases: {gc.aliases.join(", ")})</span>
                )}
                <span style={{ color: "var(--text2)", fontSize: 11 }}>— {gc.why_core}</span>
              </div>
            ))}

            {goldenSpec.expected_secondary_concepts.length > 0 && (
              <>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 8, marginBottom: 4 }}>Expected Secondary Concepts:</div>
                {goldenSpec.expected_secondary_concepts.map((gc) => (
                  <div key={gc.concept} style={{ fontSize: 12, padding: "3px 0", display: "flex", alignItems: "center", gap: 6 }}>
                    <input type="checkbox" checked readOnly />
                    <strong>{gc.concept}</strong>
                    <span style={{ color: "var(--text2)", fontSize: 11 }}>— {gc.why_core}</span>
                  </div>
                ))}
              </>
            )}

            <button
              className="btn btn-primary"
              style={{ marginTop: 12 }}
              disabled={evalLoading || !selectedProject}
              onClick={async () => {
                setEvalLoading(true);
                setEvalError("");
                setEvalResult(null);
                try {
                  const result = await invoke<EvalResult>("evaluate_discovery", {
                    project: selectedProject,
                    goldenSpec: goldenSpecPath,
                    out: outputDir || "/tmp/fpga_devmind/eval_out",
                  });
                  setEvalResult(result);
                } catch (e) {
                  setEvalError(String(e));
                } finally {
                  setEvalLoading(false);
                }
              }}
            >
              {evalLoading ? "Evaluating..." : "Run Evaluation"}
            </button>
          </div>
        )}

        {evalResult && (
          <div style={{ marginTop: 12, padding: "8px 12px", backgroundColor: "rgba(128,128,128,0.06)", borderRadius: 4 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Evaluation Result</div>
            <div style={{ fontSize: 12, color: "var(--green)" }}>
              Matched core ({evalResult.matched_core.length}/{evalResult.golden_core_count}): {evalResult.matched_core.join(", ") || "none"}
            </div>
            {evalResult.missed_core.length > 0 && (
              <div style={{ fontSize: 12, color: "var(--red)" }}>
                Missed core: {evalResult.missed_core.join(", ")}
              </div>
            )}
            {evalResult.unexpected_selected.length > 0 && (
              <div style={{ fontSize: 12, color: "var(--yellow)" }}>
                Unexpected selected: {evalResult.unexpected_selected.join(", ")}
              </div>
            )}
            <div style={{ fontSize: 12, marginTop: 4 }}>
              Precision: {(evalResult.precision_like * 100).toFixed(1)}% | Recall: {(evalResult.recall_like * 100).toFixed(1)}%
            </div>
          </div>
        )}

        {evalError && (
          <div style={{ fontSize: 12, color: "var(--red)", marginTop: 8, whiteSpace: "pre-wrap" }}>
            {evalError}
          </div>
        )}
      </div>

      {/* Golden Spec Auto Trace (T037) */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">Golden Spec Auto Trace (T037)</div>
        <div style={{ fontSize: 12, color: "var(--text2)", marginBottom: 8 }}>
          使用 Golden Spec 驱动自动概念发现和 trace，生成带评估指标的 bundle。
        </div>

        <div className="form-group">
          <label className="form-label">Golden Spec JSON</label>
          <input
            className="form-input"
            value={goldenSpecPath}
            onChange={(e) => setGoldenSpecPath(e.target.value)}
            placeholder="/path/to/golden-concepts.json"
          />
        </div>

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
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Output Directory</label>
          <input
            className="form-input"
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            placeholder="/tmp/fpga_devmind/t037_auto"
          />
        </div>

        <button
          className="btn btn-primary"
          disabled={loading || !selectedProject || !goldenSpecPath}
          onClick={async () => {
            setLoading(true);
            setError("");
            setRunStatus("");
            const projectName = selectedProject.split("/").pop() ?? "project";
            const out = outputDir || `/tmp/fpga_devmind/t037_${projectName}`;
            try {
              setRunStatus("running golden-spec auto-trace...");
              await invoke<string>("run_project_trace", {
                project: selectedProject,
                concepts: "auto",
                out,
                goldenSpec: goldenSpecPath,
                discoveryMode: "auto",
                maxConcepts: maxConcepts,
              });
              setRunStatus("loading bundle...");
              await onLoad(out);
              setRunStatus("done");
            } catch (e) {
              setError(String(e));
              setRunStatus("error");
            } finally {
              setLoading(false);
            }
          }}
          style={{ marginTop: 4 }}
        >
          {loading && runStatus ? runStatus : "Run Golden Auto Trace"}
        </button>

        {runStatus && !loading && (
          <div style={{
            fontSize: 13,
            marginTop: 8,
            color: runStatus === "done" ? "var(--green)" : runStatus === "error" ? "var(--red)" : "var(--text2)",
          }}>
            {runStatus === "done" ? "✓ Auto trace with golden spec completed" : runStatus}
          </div>
        )}
        {error && (
          <div style={{ fontSize: 12, color: "var(--red)", marginTop: 8, whiteSpace: "pre-wrap" }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

export default SettingsPage;
