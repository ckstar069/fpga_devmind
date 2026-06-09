import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface Props {
  currentPath: string;
  onLoad: (path: string) => void;
  loading: boolean;
  error: string | null;
}

function Settings({ currentPath, onLoad, loading, error }: Props) {
  const [path, setPath] = useState(currentPath || "");
  const [traceProject, setTraceProject] = useState("");
  const [traceConcepts, setTraceConcepts] = useState("");
  const [traceOut, setTraceOut] = useState("");
  const [traceRunning, setTraceRunning] = useState(false);
  const [traceOutput, setTraceOutput] = useState<string | null>(null);

  const handleRunTrace = async () => {
    if (!traceProject.trim() || !traceConcepts.trim()) return;
    setTraceRunning(true);
    setTraceOutput(null);
    try {
      const out = traceOut.trim() || "/tmp/fpga_devmind/t033_project_smoke";
      const result = await invoke<string>("run_project_trace", {
        project: traceProject.trim(),
        concepts: traceConcepts.trim(),
        out,
      });
      setTraceOutput(result);
      setPath(out);
    } catch (e) {
      setTraceOutput(`错误: ${String(e)}`);
    } finally {
      setTraceRunning(false);
    }
  };

  return (
    <div>
      <div className="page-title">Settings</div>

      {/* Load existing bundle */}
      <div className="card">
        <div className="card-title">加载 Project Bundle</div>
        <div className="settings-form">
          <div className="form-group">
            <label className="form-label">Bundle 目录路径</label>
            <input
              className="form-input"
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/tmp/fpga_devmind/t033_project_smoke"
            />
          </div>
          <button
            className="btn btn-primary"
            disabled={loading || !path.trim()}
            onClick={() => onLoad(path.trim())}
          >
            {loading ? "加载中..." : "Load Bundle"}
          </button>
          {error && (
            <div style={{
              marginTop: 12, padding: "8px 12px",
              background: "rgba(239, 68, 68, 0.15)", borderRadius: 6,
              color: "var(--red)", fontSize: 13,
            }}>
              {error}
            </div>
          )}
          {currentPath && (
            <div style={{ marginTop: 12, fontSize: 13, color: "var(--text2)" }}>
              当前加载：<strong>{currentPath}</strong>
            </div>
          )}
        </div>
      </div>

      {/* Generate new bundle via Python CLI */}
      <div className="card">
        <div className="card-title">生成新 Bundle</div>
        <div style={{ fontSize: 12, color: "var(--text2)", marginBottom: 12 }}>
          调用 Python CLI 生成新的 project bundle。需要 fpga_devmind 项目已安装。
        </div>
        <div className="settings-form">
          <div className="form-group">
            <label className="form-label">项目路径 (--project)</label>
            <input
              className="form-input"
              type="text"
              value={traceProject}
              onChange={(e) => setTraceProject(e.target.value)}
              placeholder="/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
            />
          </div>
          <div className="form-group">
            <label className="form-label">概念 (--concepts，逗号分隔)</label>
            <input
              className="form-input"
              type="text"
              value={traceConcepts}
              onChange={(e) => setTraceConcepts(e.target.value)}
              placeholder="peak_idx,cfo,smooth_detect"
            />
          </div>
          <div className="form-group">
            <label className="form-label">输出路径 (--out)</label>
            <input
              className="form-input"
              type="text"
              value={traceOut}
              onChange={(e) => setTraceOut(e.target.value)}
              placeholder="/tmp/fpga_devmind/t033_project_smoke"
            />
          </div>
          <button
            className="btn btn-secondary"
            disabled={traceRunning || !traceProject.trim() || !traceConcepts.trim()}
            onClick={handleRunTrace}
          >
            {traceRunning ? "生成中..." : "运行 p1b-trace-project"}
          </button>
          {traceOutput && (
            <div className="source-context" style={{ marginTop: 12 }}>
              {traceOutput}
            </div>
          )}
        </div>
      </div>

      {/* Default paths */}
      <div className="card">
        <div className="card-title">开发模式默认路径</div>
        <div style={{ fontSize: 12, color: "var(--text2)", lineHeight: 1.8 }}>
          <div>
            <button className="table-link" onClick={() => { setPath("/tmp/fpga_devmind/t033_project_smoke"); }}>
              /tmp/fpga_devmind/t033_project_smoke
            </button>
          </div>
          <div>
            <button className="table-link" onClick={() => { setPath("/tmp/fpga_devmind/t031_gui_smoke"); }}>
              /tmp/fpga_devmind/t031_gui_smoke
            </button>
          </div>
          <div>
            <button className="table-link" onClick={() => { setPath("/tmp/fpga_devmind/t025_project_smoke"); }}>
              /tmp/fpga_devmind/t025_project_smoke
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
