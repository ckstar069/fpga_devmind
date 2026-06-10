use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

/* ------------------------------------------------------------------ */
/*  Data types matching the JSON schemas                              */
/* ------------------------------------------------------------------ */

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphNode {
    pub node_id: String,
    pub label: String,
    pub kind: String,
    #[serde(default)]
    pub stage: String,
    #[serde(default)]
    pub confidence: String,
    #[serde(default)]
    pub concept: Option<String>,
    #[serde(default)]
    pub bridge_kind: Option<String>,
    #[serde(default)]
    pub evidence_ids: Vec<String>,
    #[serde(default)]
    pub file_path: Option<String>,
    #[serde(default)]
    pub line_start: Option<u64>,
    #[serde(default)]
    pub line_end: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdge {
    pub edge_id: String,
    pub from_node_id: String,
    pub to_node_id: String,
    pub edge_type: String,
    #[serde(default)]
    pub confidence: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct ProjectGraph {
    pub schema_version: String,
    pub project_id: String,
    #[serde(default)]
    pub project_root: Option<String>,
    #[serde(default)]
    pub concepts: Vec<String>,
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<GraphEdge>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvidenceEntry {
    #[serde(default)]
    pub concept: Option<String>,
    pub source_type: String,
    #[serde(default)]
    pub file_path: Option<String>,
    #[serde(default)]
    pub symbol: Option<String>,
    #[serde(default)]
    pub strength: Option<String>,
    #[serde(default)]
    pub line_start: Option<u64>,
    #[serde(default)]
    pub line_end: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConceptInfo {
    pub status: String,
    pub claims: u64,
    pub evidence: u64,
    pub rtl_objects: u64,
    #[serde(default)]
    pub l5_count: u64,
    #[serde(default)]
    pub l6_count: u64,
    #[serde(default)]
    pub test_count: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimInfo {
    pub concept: String,
    pub confidence: String,
    pub bridge_kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct ProjectIndex {
    pub schema_version: String,
    pub project_id: String,
    pub concept_index: HashMap<String, ConceptInfo>,
    pub claim_index: HashMap<String, ClaimInfo>,
    pub evidence_index: HashMap<String, EvidenceEntry>,
    #[serde(default)]
    pub evidence_chain: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct RunMetadata {
    pub schema_version: String,
    pub command: String,
    pub project_root: String,
    #[serde(default)]
    pub concepts_requested: Vec<String>,
    #[serde(default)]
    pub concepts_processed: Vec<String>,
    pub status: String,
    pub mapping_claims: u64,
    pub evidence_items: u64,
    pub diagnostics: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectBundle {
    pub path: String,
    pub graph: ProjectGraph,
    pub index: ProjectIndex,
    pub metadata: RunMetadata,
    #[serde(default)]
    pub semantic_summary: Option<serde_json::Value>,
    #[serde(default)]
    pub discovery_eval_result: Option<serde_json::Value>,
    #[serde(default)]
    pub concept_candidates: Option<serde_json::Value>,
    /// T039/T040: Semantic pipeline view (lane-based dataflow)
    #[serde(default)]
    pub semantic_pipeline_view: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectBundleSummary {
    pub path: String,
    pub project_id: String,
    pub project_root: String,
    pub concepts: Vec<String>,
    pub mapping_claims: u64,
    pub evidence_items: u64,
    pub diagnostics: u64,
    pub node_count: usize,
    pub edge_count: usize,
    pub status: String,
}

/* ------------------------------------------------------------------ */
/*  Loader                                                            */
/* ------------------------------------------------------------------ */

pub fn load_bundle(dir: &Path) -> Result<ProjectBundle, String> {
    let graph_path = dir.join("project_understanding_graph.json");
    let index_path = dir.join("project_understanding_index.json");
    let meta_path = dir.join("run_metadata.json");

    if !graph_path.exists() {
        return Err(format!(
            "project_understanding_graph.json not found in {}",
            dir.display()
        ));
    }
    if !index_path.exists() {
        return Err(format!(
            "project_understanding_index.json not found in {}",
            dir.display()
        ));
    }
    if !meta_path.exists() {
        return Err(format!(
            "run_metadata.json not found in {}",
            dir.display()
        ));
    }

    let graph: ProjectGraph = serde_json::from_str(
        &fs::read_to_string(&graph_path).map_err(|e| e.to_string())?,
    )
    .map_err(|e| format!("graph parse error: {e}"))?;

    let index: ProjectIndex = serde_json::from_str(
        &fs::read_to_string(&index_path).map_err(|e| e.to_string())?,
    )
    .map_err(|e| format!("index parse error: {e}"))?;

    let metadata: RunMetadata = serde_json::from_str(
        &fs::read_to_string(&meta_path).map_err(|e| e.to_string())?,
    )
    .map_err(|e| format!("metadata parse error: {e}"))?;

    // T038: Load semantic summary if present
    let semantic_summary_path = dir.join("project_semantic_summary.json");
    let semantic_summary = if semantic_summary_path.exists() {
        match fs::read_to_string(&semantic_summary_path) {
            Ok(content) => match serde_json::from_str(&content) {
                Ok(val) => Some(val),
                Err(e) => {
                    eprintln!("Warning: failed to parse project_semantic_summary.json: {e}");
                    None
                }
            },
            Err(e) => {
                eprintln!("Warning: failed to read project_semantic_summary.json: {e}");
                None
            }
        }
    } else {
        None
    };

    // T038.1: Load discovery eval result if present
    let eval_path = dir.join("discovery_eval_result.json");
    let discovery_eval_result = if eval_path.exists() {
        match fs::read_to_string(&eval_path) {
            Ok(content) => match serde_json::from_str(&content) {
                Ok(val) => Some(val),
                Err(e) => {
                    eprintln!("Warning: failed to parse discovery_eval_result.json: {e}");
                    None
                }
            },
            Err(e) => {
                eprintln!("Warning: failed to read discovery_eval_result.json: {e}");
                None
            }
        }
    } else {
        None
    };

    // T038.1: Load concept candidates if present
    let candidates_path = dir.join("concept_candidates.json");
    let concept_candidates = if candidates_path.exists() {
        match fs::read_to_string(&candidates_path) {
            Ok(content) => match serde_json::from_str(&content) {
                Ok(val) => Some(val),
                Err(e) => {
                    eprintln!("Warning: failed to parse concept_candidates.json: {e}");
                    None
                }
            },
            Err(e) => {
                eprintln!("Warning: failed to read concept_candidates.json: {e}");
                None
            }
        }
    } else {
        None
    };

    // T039/T040: Load semantic pipeline view if present
    let pipeline_view_path = dir.join("semantic_pipeline_view.json");
    let semantic_pipeline_view = if pipeline_view_path.exists() {
        match fs::read_to_string(&pipeline_view_path) {
            Ok(content) => match serde_json::from_str(&content) {
                Ok(val) => Some(val),
                Err(e) => {
                    eprintln!("Warning: failed to parse semantic_pipeline_view.json: {e}");
                    None
                }
            },
            Err(e) => {
                eprintln!("Warning: failed to read semantic_pipeline_view.json: {e}");
                None
            }
        }
    } else {
        None
    };

    Ok(ProjectBundle {
        path: dir.to_string_lossy().to_string(),
        graph,
        index,
        metadata,
        semantic_summary,
        discovery_eval_result,
        concept_candidates,
        semantic_pipeline_view,
    })
}

pub fn bundle_summary(bundle: &ProjectBundle) -> ProjectBundleSummary {
    ProjectBundleSummary {
        path: bundle.path.clone(),
        project_id: bundle.graph.project_id.clone(),
        project_root: bundle.metadata.project_root.clone(),
        concepts: bundle.metadata.concepts_processed.clone(),
        mapping_claims: bundle.metadata.mapping_claims,
        evidence_items: bundle.metadata.evidence_items,
        diagnostics: bundle.metadata.diagnostics,
        node_count: bundle.graph.nodes.len(),
        edge_count: bundle.graph.edges.len(),
        status: bundle.metadata.status.clone(),
    }
}

/* ------------------------------------------------------------------ */
/*  Evidence line range parsing                                        */
/* ------------------------------------------------------------------ */

/// Parse an evidence_id like "E:p1b_concept:9db6fc88:399-473:001"
/// Returns (start_line, end_line) as 1-based line numbers.
pub fn parse_line_range_from_evidence_id(evidence_id: &str) -> Option<(usize, usize)> {
    // Format: E:source_type:hash:start-end:seq
    // Example: E:p1b_concept:9db6fc88:399-473:001
    // parts: ["E", "p1b_concept", "9db6fc88", "399-473", "001"]
    let parts: Vec<&str> = evidence_id.split(':').collect();
    if parts.len() >= 5 {
        // parts[3] should be like "399-473"
        if let Some(range_part) = parts.get(3) {
            let range_parts: Vec<&str> = range_part.split('-').collect();
            if range_parts.len() == 2 {
                if let (Ok(start), Ok(end)) = (range_parts[0].parse::<usize>(), range_parts[1].parse::<usize>()) {
                    if start > 0 && end >= start {
                        return Some((start, end));
                    }
                }
            }
        }
    }
    None
}

/// Mask secrets in a line of source code.
fn mask_secrets(line: &str) -> String {
    let mut result = line.to_string();

    // Mask sk- tokens (OpenAI-style)
    if let Ok(re) = regex::Regex::new(r"sk-[a-zA-Z0-9]{20,}") {
        result = re.replace_all(&result, "sk-***MASKED***").to_string();
    }

    // Mask Bearer tokens
    if let Ok(re) = regex::Regex::new(r"(?i)(Bearer\s+)[a-zA-Z0-9._-]{20,}") {
        result = re.replace_all(&result, "${1}***MASKED***").to_string();
    }

    // Mask api_key / password / secret / token values
    if let Ok(re) = regex::Regex::new(r#"(?i)(api_key\s*[:=]\s*)['"][^'"]*['"]"#) {
        result = re.replace_all(&result, "${1}***MASKED***").to_string();
    }
    if let Ok(re) = regex::Regex::new(r#"(?i)(password\s*[:=]\s*)['"][^'"]*['"]"#) {
        result = re.replace_all(&result, "${1}***MASKED***").to_string();
    }
    if let Ok(re) = regex::Regex::new(r#"(?i)(secret\s*[:=]\s*)['"][^'"]{8,}['"]"#) {
        result = re.replace_all(&result, "${1}***MASKED***").to_string();
    }
    if let Ok(re) = regex::Regex::new(r#"(?i)(token\s*[:=]\s*)['"][^'"]{16,}['"]"#) {
        result = re.replace_all(&result, "${1}***MASKED***").to_string();
    }

    result
}

/// Read source context around evidence lines.
///
/// If `evidence_id` is provided, parses line range from it.
/// Falls back to `line_start`/`line_end` fields from the evidence index.
/// Returns context lines with evidence lines marked with "▶".
pub fn read_source_context_for_evidence(
    file_path: &str,
    evidence_id: Option<&str>,
    line_start: Option<u64>,
    line_end: Option<u64>,
    context_lines: usize,
    bundle: Option<&ProjectBundle>,
) -> Result<SourceContext, String> {
    let path = Path::new(file_path);
    if !path.exists() {
        return Err(format!("File not found: {}", file_path));
    }

    let content = fs::read_to_string(path).map_err(|e| format!("Cannot read file: {}", e))?;
    let all_lines: Vec<&str> = content.lines().collect();
    let total_lines = all_lines.len();

    if total_lines == 0 {
        return Err("File is empty".into());
    }

    // Determine evidence line range
    let (ev_start, ev_end) = resolve_line_range(evidence_id, line_start, line_end, bundle)?;

    // Convert to usize and clamp to file bounds (1-based)
    let total = total_lines as u64;
    let ev_start = (ev_start.max(1).min(total)) as usize;
    let ev_end = (ev_end.max(ev_start as u64).min(total)) as usize;

    // Compute context window
    let ctx_pad = context_lines.max(5).min(60);
    let show_start = ev_start.saturating_sub(ctx_pad + 1) + 1; // 1-based
    let show_end = (ev_end + ctx_pad).min(total_lines);

    // Cap at 120 lines
    let max_lines = 120;
    let show_end = show_end.min(show_start + max_lines - 1);

    // Build output with evidence lines marked
    let mut lines = Vec::new();
    for i in show_start..=show_end {
        let idx = i - 1; // 0-based index
        if idx >= all_lines.len() {
            break;
        }
        let is_evidence = i >= ev_start as usize && i <= ev_end as usize;
        let marker = if is_evidence { "▶" } else { " " };
        let masked = mask_secrets(all_lines[idx]);
        lines.push(format!("{:>4} {}│ {}", i, marker, masked));
    }

    Ok(SourceContext {
        file_path: file_path.to_string(),
        evidence_start: ev_start as u64,
        evidence_end: ev_end as u64,
        total_lines: total_lines as u64,
        context_start: show_start as u64,
        context_end: show_end as u64,
        lines,
    })
}

/// Legacy function for backward compatibility.
pub fn read_source_context(
    file_path: &str,
    context_lines: usize,
) -> Result<String, String> {
    let path = Path::new(file_path);
    if !path.exists() {
        return Err(format!("File not found: {file_path}"));
    }

    let content = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let lines: Vec<&str> = content.lines().collect();
    let total = lines.len();

    let start = if total > context_lines {
        total - context_lines
    } else {
        0
    };

    let ctx: Vec<String> = (start..total)
        .map(|i| format!("{:>4} │ {}", i + 1, mask_secrets(lines[i])))
        .collect();

    Ok(ctx.join("\n"))
}

/// Resolve evidence line range from multiple sources.
fn resolve_line_range(
    evidence_id: Option<&str>,
    line_start: Option<u64>,
    line_end: Option<u64>,
    bundle: Option<&ProjectBundle>,
) -> Result<(u64, u64), String> {
    // 1. Try parsing from evidence_id
    if let Some(eid) = evidence_id {
        if let Some((s, e)) = parse_line_range_from_evidence_id(eid) {
            return Ok((s as u64, e as u64));
        }
    }

    // 2. Try explicit line_start/line_end
    if let (Some(s), Some(e)) = (line_start, line_end) {
        if s > 0 && e >= s {
            return Ok((s, e));
        }
    }

    // 3. Try looking up from bundle evidence_index
    if let (Some(b), Some(eid)) = (bundle, evidence_id) {
        if let Some(ev) = b.index.evidence_index.get(eid) {
            if let (Some(s), Some(e)) = (ev.line_start, ev.line_end) {
                if s > 0 && e >= s {
                    return Ok((s, e));
                }
            }
        }
    }

    Err(format!(
        "Cannot determine line range for evidence. evidence_id={:?}, line_start={:?}, line_end={:?}",
        evidence_id, line_start, line_end
    ))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceContext {
    pub file_path: String,
    pub evidence_start: u64,
    pub evidence_end: u64,
    pub total_lines: u64,
    pub context_start: u64,
    pub context_end: u64,
    pub lines: Vec<String>,
}

/* ------------------------------------------------------------------ */
/*  Default sample bundle discovery                                   */
/* ------------------------------------------------------------------ */

pub fn find_default_bundle() -> Option<PathBuf> {
    let candidates = [
        "/tmp/fpga_devmind/t040_coarse",
        "/tmp/fpga_devmind/t040_fine_cfo",
        "/tmp/fpga_devmind/t040_fft",
        "/tmp/fpga_devmind/t038_coarse_semantic",
        "/tmp/fpga_devmind/t038_fine_cfo_semantic",
        "/tmp/fpga_devmind/t038_fft_semantic",
        "/tmp/fpga_devmind/t034_project_smoke",
        "/tmp/fpga_devmind/t033_project_smoke",
        "/tmp/fpga_devmind/t025_project_smoke",
    ];

    for c in &candidates {
        let p = PathBuf::from(c);
        if p.join("project_understanding_graph.json").exists() {
            return Some(p);
        }
    }
    None
}

/* ------------------------------------------------------------------ */
/*  Tests                                                             */
/* ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_bundle_missing_dir() {
        let result = load_bundle(Path::new("/nonexistent/path"));
        assert!(result.is_err());
    }

    #[test]
    fn test_load_bundle_valid() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path();

        let graph = serde_json::json!({
            "schema_version": "project-understanding-0.1",
            "project_id": "test",
            "nodes": [
                {"node_id": "P", "label": "test", "kind": "project", "stage": "", "confidence": "supported"}
            ],
            "edges": []
        });
        let index = serde_json::json!({
            "schema_version": "project-understanding-0.1",
            "project_id": "test",
            "concept_index": {},
            "claim_index": {},
            "evidence_index": {}
        });
        let metadata = serde_json::json!({
            "schema_version": "p1b-project-run-metadata-0.1",
            "command": "test",
            "project_root": "/tmp/test",
            "status": "ok",
            "mapping_claims": 0,
            "evidence_items": 0,
            "diagnostics": 0
        });

        fs::write(dir.join("project_understanding_graph.json"), graph.to_string()).unwrap();
        fs::write(dir.join("project_understanding_index.json"), index.to_string()).unwrap();
        fs::write(dir.join("run_metadata.json"), metadata.to_string()).unwrap();

        let bundle = load_bundle(dir).unwrap();
        assert_eq!(bundle.graph.project_id, "test");
        assert_eq!(bundle.graph.nodes.len(), 1);
        assert_eq!(bundle.metadata.status, "ok");

        let summary = bundle_summary(&bundle);
        assert_eq!(summary.project_id, "test");
        assert_eq!(summary.node_count, 1);
        assert_eq!(summary.edge_count, 0);
    }

    #[test]
    fn test_summary_counts() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path();

        let graph = serde_json::json!({
            "schema_version": "project-understanding-0.1",
            "project_id": "cnt_test",
            "nodes": [
                {"node_id": "P", "label": "p", "kind": "project", "stage": "", "confidence": "supported"},
                {"node_id": "C1", "label": "c1", "kind": "concept", "stage": "", "confidence": "supported"},
                {"node_id": "CL1", "label": "cl1", "kind": "mapping_claim", "stage": "", "confidence": "supported", "concept": "c1"}
            ],
            "edges": [
                {"edge_id": "E1", "from_node_id": "P", "to_node_id": "C1", "edge_type": "contains"}
            ]
        });
        let index = serde_json::json!({
            "schema_version": "project-understanding-0.1",
            "project_id": "cnt_test",
            "concept_index": {},
            "claim_index": {},
            "evidence_index": {}
        });
        let metadata = serde_json::json!({
            "schema_version": "p1b-project-run-metadata-0.1",
            "command": "test",
            "project_root": "/tmp",
            "status": "ok",
            "mapping_claims": 1,
            "evidence_items": 5,
            "diagnostics": 0
        });

        fs::write(dir.join("project_understanding_graph.json"), graph.to_string()).unwrap();
        fs::write(dir.join("project_understanding_index.json"), index.to_string()).unwrap();
        fs::write(dir.join("run_metadata.json"), metadata.to_string()).unwrap();

        let bundle = load_bundle(dir).unwrap();
        let summary = bundle_summary(&bundle);
        assert_eq!(summary.node_count, 3);
        assert_eq!(summary.edge_count, 1);
        assert_eq!(summary.mapping_claims, 1);
        assert_eq!(summary.evidence_items, 5);
    }

    #[test]
    fn test_parse_line_range_from_evidence_id() {
        // Standard format: E:source_type:hash:start-end:seq
        assert_eq!(
            parse_line_range_from_evidence_id("E:p1b_concept:9db6fc88:399-473:001"),
            Some((399, 473))
        );
        assert_eq!(
            parse_line_range_from_evidence_id("E:p1b_rtl:abcd:124-143:001"),
            Some((124, 143))
        );
        assert_eq!(
            parse_line_range_from_evidence_id("E:p1b_concept:180d8fc3:47-214:007"),
            Some((47, 214))
        );
        // Single line
        assert_eq!(
            parse_line_range_from_evidence_id("E:p1b_rtl:abc:50-50:001"),
            Some((50, 50))
        );
        // Invalid formats
        assert_eq!(parse_line_range_from_evidence_id("invalid"), None);
        assert_eq!(parse_line_range_from_evidence_id("E:a:b:c"), None);
        assert_eq!(parse_line_range_from_evidence_id(""), None);
    }

    #[test]
    fn test_read_source_context_for_evidence() {
        let tmp = tempfile::tempdir().unwrap();
        let file_path = tmp.path().join("test.py");
        // Create a file with 100 lines
        let content: String = (1..=100).map(|i| format!("line {} content\n", i)).collect();
        fs::write(&file_path, &content).unwrap();

        let path_str = file_path.to_string_lossy().to_string();

        // Test with evidence_id containing line range
        let ctx = read_source_context_for_evidence(
            &path_str,
            Some("E:p1b_concept:abc:10-15:001"),
            None,
            None,
            5,
            None,
        ).unwrap();

        assert_eq!(ctx.evidence_start, 10);
        assert_eq!(ctx.evidence_end, 15);
        assert_eq!(ctx.total_lines, 100);

        // Check that evidence lines are marked with ▶
        let evidence_lines: Vec<&String> = ctx.lines.iter().filter(|l| l.contains("▶")).collect();
        assert!(evidence_lines.len() >= 6, "Should have 6 evidence lines (10-15)");

        // First line should be around line 5 (evidence_start - 5 - 1)
        assert!(ctx.context_start <= 6);
        assert!(ctx.context_end >= 15);
    }

    #[test]
    fn test_read_source_context_fallback_line_fields() {
        let tmp = tempfile::tempdir().unwrap();
        let file_path = tmp.path().join("test.v");
        let content: String = (1..=50).map(|i| format!("assign x = {};\n", i)).collect();
        fs::write(&file_path, &content).unwrap();

        let path_str = file_path.to_string_lossy().to_string();

        // No evidence_id, use line_start/line_end
        let ctx = read_source_context_for_evidence(
            &path_str,
            None,
            Some(20),
            Some(25),
            3,
            None,
        ).unwrap();

        assert_eq!(ctx.evidence_start, 20);
        assert_eq!(ctx.evidence_end, 25);
    }

    #[test]
    fn test_read_source_context_missing_file() {
        let result = read_source_context_for_evidence(
            "/nonexistent/file.v",
            Some("E:p1b_concept:abc:10-15:001"),
            None,
            None,
            5,
            None,
        );
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not found"));
    }

    #[test]
    fn test_read_source_context_no_line_info() {
        let tmp = tempfile::tempdir().unwrap();
        let file_path = tmp.path().join("test.py");
        fs::write(&file_path, "hello\n").unwrap();

        let result = read_source_context_for_evidence(
            &file_path.to_string_lossy(),
            Some("invalid_evidence_id"),
            None,
            None,
            5,
            None,
        );
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Cannot determine line range"));
    }

    #[test]
    fn test_mask_secrets() {
        assert!(mask_secrets("api_key = \"sk-abc123\"").contains("***MASKED***"));
        assert!(mask_secrets("password = \"secret123\"").contains("***MASKED***"));
        assert!(mask_secrets("token = \"abcdef1234567890\"").contains("***MASKED***"));
        assert!(!mask_secrets("x = 42").contains("***MASKED***"));
    }

    #[test]
    fn test_find_default_bundle_none() {
        let _ = find_default_bundle();
    }

    #[test]
    fn test_deserialize_graph_from_real_bundle() {
        let path = Path::new("/tmp/fpga_devmind/t034_project_smoke");
        if !path.join("project_understanding_graph.json").exists() {
            // Fallback to older bundles
            let path = Path::new("/tmp/fpga_devmind/t025_project_smoke");
            if !path.join("project_understanding_graph.json").exists() {
                eprintln!("Skipping: real bundle not found");
                return;
            }
        }
        let bundle = load_bundle(path).unwrap();
        assert!(!bundle.graph.nodes.is_empty());
        assert!(!bundle.graph.edges.is_empty());
        assert_eq!(bundle.graph.project_id, "fpga_project_coarse_sync_glm");

        let kinds: std::collections::HashSet<&str> =
            bundle.graph.nodes.iter().map(|n| n.kind.as_str()).collect();
        assert!(kinds.contains("project"));
        assert!(kinds.contains("concept"));
        assert!(kinds.contains("mapping_claim"));
    }

    #[test]
    fn test_read_source_context_real_evidence() {
        let path = Path::new("/tmp/fpga_devmind/t034_project_smoke");
        if !path.join("project_understanding_index.json").exists() {
            eprintln!("Skipping: real bundle not found");
            return;
        }
        let bundle = load_bundle(path).unwrap();

        // Find a concept evidence with known line range
        let target_eid = "E:p1b_concept:9db6fc88:399-473:001";
        let ev = match bundle.index.evidence_index.get(target_eid) {
            Some(e) => e,
            None => {
                eprintln!("Skipping: evidence {} not found", target_eid);
                return;
            }
        };

        let file_path = match &ev.file_path {
            Some(f) => f.clone(),
            None => {
                eprintln!("Skipping: no file_path");
                return;
            }
        };

        if !Path::new(&file_path).exists() {
            eprintln!("Skipping: source file not found: {}", file_path);
            return;
        }

        let ctx = read_source_context_for_evidence(
            &file_path,
            Some(target_eid),
            None,
            None,
            5,
            Some(&bundle),
        ).unwrap();

        assert_eq!(ctx.evidence_start, 399);
        assert_eq!(ctx.evidence_end, 473);

        // Verify evidence lines are marked
        let evidence_lines: Vec<&String> = ctx.lines.iter().filter(|l| l.contains("▶")).collect();
        assert!(evidence_lines.len() > 0, "Evidence lines should be marked");

        // Verify first context line is before 399
        assert!(ctx.context_start < 399, "Context should start before evidence");

        // Verify line 399 content is present
        let line_399 = ctx.lines.iter().find(|l| l.contains("▶") && l.contains("399"));
        assert!(line_399.is_some(), "Line 399 should be in context");
    }
}
