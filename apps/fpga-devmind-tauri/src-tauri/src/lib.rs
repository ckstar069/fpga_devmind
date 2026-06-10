mod artifact_loader;
mod provider_runtime;

use artifact_loader::{self as loader};
use std::sync::Mutex;
use tauri::State;

/* ------------------------------------------------------------------ */
/*  Shared state                                                      */
/* ------------------------------------------------------------------ */

struct AppState {
    bundle: Mutex<Option<loader::ProjectBundle>>,
}

/* ------------------------------------------------------------------ */
/*  Tauri commands                                                    */
/* ------------------------------------------------------------------ */

#[tauri::command]
fn load_project_bundle(path: String, state: State<'_, AppState>) -> Result<loader::ProjectBundle, String> {
    let dir = std::path::Path::new(&path);
    let bundle = loader::load_bundle(dir)?;
    let mut lock = state.bundle.lock().map_err(|e| e.to_string())?;
    let result = bundle.clone();
    *lock = Some(bundle);
    Ok(result)
}

#[tauri::command]
fn get_bundle_summary(state: State<'_, AppState>) -> Result<loader::ProjectBundleSummary, String> {
    let lock = state.bundle.lock().map_err(|e| e.to_string())?;
    match lock.as_ref() {
        Some(bundle) => Ok(loader::bundle_summary(bundle)),
        None => Err("No bundle loaded".into()),
    }
}

#[tauri::command]
fn read_source_context(
    file_path: String,
    context_lines: Option<usize>,
    _state: State<'_, AppState>,
) -> Result<String, String> {
    let lines = context_lines.unwrap_or(15);
    loader::read_source_context(&file_path, lines)
}

/// Read source context for a specific evidence item.
/// Uses evidence_id to determine line range, returns structured context
/// with evidence lines highlighted.
#[tauri::command]
fn read_evidence_source_context(
    file_path: String,
    evidence_id: Option<String>,
    line_start: Option<u64>,
    line_end: Option<u64>,
    context_lines: Option<usize>,
    state: State<'_, AppState>,
) -> Result<loader::SourceContext, String> {
    let ctx_lines = context_lines.unwrap_or(5);
    let lock = state.bundle.lock().map_err(|e| e.to_string())?;
    let bundle_ref = lock.as_ref();
    loader::read_source_context_for_evidence(
        &file_path,
        evidence_id.as_deref(),
        line_start,
        line_end,
        ctx_lines,
        bundle_ref,
    )
}

#[tauri::command]
fn get_default_bundle_path() -> Option<String> {
    loader::find_default_bundle().map(|p| p.to_string_lossy().to_string())
}

/// Run Python CLI to generate a project bundle.
/// Calls: python -m fpga_devmind.cli p1b-trace-project --project <project> --concepts <concepts> --out <out>
#[tauri::command]
fn run_project_trace(
    project: String,
    concepts: String,
    out: String,
    golden_spec: Option<String>,
    discovery_mode: Option<String>,
    max_concepts: Option<u32>,
) -> Result<String, String> {
    // Find the fpga_devmind project root (parent of apps/fpga-devmind-tauri)
    let exe_dir = std::env::current_dir().map_err(|e| format!("Cannot get CWD: {}", e))?;
    let project_root = exe_dir
        .parent()
        .and_then(|p| p.parent())
        .ok_or("Cannot determine project root")?;

    let python = which_python()?;

    let mut args: Vec<String> = vec![
        "-m".into(), "fpga_devmind.cli".into(),
        "p1b-trace-project".into(),
        "--project".into(), project,
        "--concepts".into(), concepts,
        "--out".into(), out,
    ];

    if let Some(spec) = golden_spec {
        args.push("--golden-spec".into());
        args.push(spec);
    }
    if let Some(mode) = discovery_mode {
        args.push("--discovery-mode".into());
        args.push(mode);
    }
    if let Some(max) = max_concepts {
        args.push("--max-concepts".into());
        args.push(max.to_string());
    }

    let output = std::process::Command::new(&python)
        .args(&args)
        .env("PYTHONPATH", project_root.join("src").to_string_lossy().to_string())
        .output()
        .map_err(|e| format!("Failed to run Python: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        Ok(format!("✅ 成功\n{}\n{}", stdout, if stderr.is_empty() { String::new() } else { format!("stderr:\n{}", stderr) }))
    } else {
        Err(format!("❌ 失败 (exit {:?})\n{}\n{}", output.status.code(), stdout, stderr))
    }
}

#[tauri::command]
fn list_fpga_projects(parent_dir: Option<String>) -> Result<Vec<serde_json::Value>, String> {
    let parent = match parent_dir {
        Some(p) => std::path::PathBuf::from(p),
        None => std::path::PathBuf::from("/Users/ckstar/Repo/znxt_ofdm"),
    };
    if !parent.is_dir() {
        return Err(format!("Parent directory does not exist: {}", parent.display()));
    }
    let mut projects = Vec::new();
    let entries = std::fs::read_dir(&parent).map_err(|e| e.to_string())?;
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let name = entry.file_name().to_string_lossy().to_string();
        if !name.starts_with("fpga_project_") {
            continue;
        }
        if !entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
            continue;
        }
        let path = entry.path();
        projects.push(serde_json::json!({
            "project_id": name,
            "path": path.to_string_lossy(),
            "has_L5": path.join("src/python_model/L5_fixedpoint").is_dir(),
            "has_L6": path.join("src/python_model/L6_resource_opt").is_dir(),
            "has_RTL": path.join("src/verilog_model/rtl").is_dir(),
            "has_tests": path.join("tests").is_dir(),
        }));
    }
    projects.sort_by(|a, b| a["project_id"].as_str().cmp(&b["project_id"].as_str()));
    Ok(projects)
}

#[tauri::command]
fn run_concept_discovery(project: String, out: String) -> Result<String, String> {
    let out_path = std::path::Path::new(&out);
    if !out_path.starts_with("/tmp") && !out_path.starts_with("/private/tmp") {
        return Err("Output directory must be under /tmp".to_string());
    }
    let python = which_python()?;
    let exe_dir = std::env::current_dir().map_err(|e| format!("Cannot get CWD: {}", e))?;
    let project_root = exe_dir
        .parent()
        .and_then(|p| p.parent())
        .ok_or("Cannot determine project root")?;
    let pythonpath = project_root
        .join("src")
        .to_string_lossy()
        .to_string();
    let output = std::process::Command::new(&python)
        .args([
            "-m", "fpga_devmind.cli",
            "p1b-discover-concepts",
            "--project", &project,
            "--out", &out,
        ])
        .env("PYTHONPATH", &pythonpath)
        .output()
        .map_err(|e| format!("Failed to run discovery: {}", e))?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() {
        return Err(format!("Discovery failed:\n{}\n{}", stdout, stderr));
    }
    Ok(stdout)
}

/// Read a file's content as a string. Used by Settings for golden spec loading.
#[tauri::command]
fn read_file_content(path: String) -> Result<String, String> {
    let p = std::path::Path::new(&path);
    if !p.exists() {
        return Err(format!("File not found: {}", path));
    }
    std::fs::read_to_string(p).map_err(|e| format!("Cannot read file: {}", e))
}

/// Run evaluation against a golden spec.
/// Calls: python -m fpga_devmind.cli p1b-evaluate-discovery --project ... --golden-spec ... --out ...
#[tauri::command]
fn evaluate_discovery(
    project: String,
    golden_spec: String,
    out: String,
) -> Result<serde_json::Value, String> {
    let exe_dir = std::env::current_dir().map_err(|e| format!("Cannot get CWD: {}", e))?;
    let project_root = exe_dir
        .parent()
        .and_then(|p| p.parent())
        .ok_or("Cannot determine project root")?;

    let python = which_python()?;

    let output = std::process::Command::new(&python)
        .args([
            "-m", "fpga_devmind.cli",
            "p1b-evaluate-discovery",
            "--project", &project,
            "--golden-spec", &golden_spec,
            "--out", &out,
        ])
        .env("PYTHONPATH", project_root.join("src").to_string_lossy().to_string())
        .output()
        .map_err(|e| format!("Failed to run evaluation: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!(
            "Evaluation failed (exit {:?}):\n{}\n{}",
            output.status.code(),
            stdout,
            stderr
        ));
    }

    // Try to parse stdout as JSON (the eval result)
    let result: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse evaluation result: {}\nOutput:\n{}", e, stdout))?;

    Ok(result)
}

/// Find python executable
fn which_python() -> Result<String, String> {
    // Try .venv/bin/python first (project-local venv)
    let candidates = [
        ".venv/bin/python",
        "venv/bin/python",
        "python3",
        "python",
    ];
    for candidate in &candidates {
        // Check if path exists relative to likely project root
        if std::path::Path::new(candidate).exists() {
            return Ok(candidate.to_string());
        }
    }
    // Fallback: just use python3 and hope it's on PATH
    Ok("python3".to_string())
}

/* ------------------------------------------------------------------ */
/*  App setup                                                         */
/* ------------------------------------------------------------------ */

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState {
            bundle: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            load_project_bundle,
            get_bundle_summary,
            read_source_context,
            read_evidence_source_context,
            get_default_bundle_path,
            run_project_trace,
            list_fpga_projects,
            run_concept_discovery,
            read_file_content,
            evaluate_discovery,
            provider_runtime::invoke_openai_compatible_ephemeral,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
