use serde::{Deserialize, Serialize};
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
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConceptInfo {
    pub status: String,
    pub claims: u64,
    pub evidence: u64,
    pub rtl_objects: u64,
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
    pub concept_index: std::collections::HashMap<String, ConceptInfo>,
    pub claim_index: std::collections::HashMap<String, ClaimInfo>,
    pub evidence_index: std::collections::HashMap<String, EvidenceEntry>,
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

    Ok(ProjectBundle {
        path: dir.to_string_lossy().to_string(),
        graph,
        index,
        metadata,
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
/*  Source context reader                                              */
/* ------------------------------------------------------------------ */

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

    // Return last N lines as context (simple approach)
    let start = if total > context_lines {
        total - context_lines
    } else {
        0
    };

    let ctx: Vec<String> = (start..total)
        .map(|i| format!("{:>4} │ {}", i + 1, lines[i]))
        .collect();

    Ok(ctx.join("\n"))
}

/* ------------------------------------------------------------------ */
/*  Default sample bundle discovery                                   */
/* ------------------------------------------------------------------ */

pub fn find_default_bundle() -> Option<PathBuf> {
    let candidates = [
        "/tmp/fpga_devmind/t025_project_smoke",
        "/tmp/fpga_devmind/t031_gui_smoke",
        "/tmp/fpga_devmind/t024a_project_smoke",
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
    // std::io::Write would be needed for file creation in future tests

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
    fn test_read_source_context_missing() {
        let result = read_source_context("/nonexistent/file.v", 5);
        assert!(result.is_err());
    }

    #[test]
    fn test_find_default_bundle_none() {
        // This test may find one if smoke bundles exist, so just verify it doesn't panic
        let _ = find_default_bundle();
    }

    #[test]
    fn test_deserialize_graph_from_real_bundle() {
        let path = Path::new("/tmp/fpga_devmind/t025_project_smoke");
        if !path.join("project_understanding_graph.json").exists() {
            eprintln!("Skipping: real bundle not found");
            return;
        }
        let bundle = load_bundle(path).unwrap();
        assert!(!bundle.graph.nodes.is_empty());
        assert!(!bundle.graph.edges.is_empty());
        assert_eq!(bundle.graph.project_id, "fpga_project_coarse_sync_glm");

        // Verify node kinds
        let kinds: std::collections::HashSet<&str> =
            bundle.graph.nodes.iter().map(|n| n.kind.as_str()).collect();
        assert!(kinds.contains("project"));
        assert!(kinds.contains("concept"));
        assert!(kinds.contains("mapping_claim"));
    }
}
