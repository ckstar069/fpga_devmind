# T038 Design: Project Semantic Understanding Pack

## Decision

ProjectSemanticSummary 使用独立 artifact：`project_semantic_summary.json`。

## Requirements (from user)

1. `run_metadata.json` 的 `artifacts` 列表必须包含 `project_semantic_summary.json`。
2. GUI loader 必须把它作为 project bundle 的一等 artifact 加载。
3. `project_understanding_index.json` 保留轻量引用字段 `semantic_summary_path`，不嵌入完整 summary。
4. Index 承担索引/反查职责；summary 承担面向用户和 Agent 的语义摘要职责。
5. Overview / Understanding Card / Agent Q&A 优先读取 summary；缺失时 fallback 到 graph/index。

## Architecture

### Backend (Python)

New file: `src/fpga_devmind/project_semantic_summary.py`
- `build_semantic_summary(project_root, graph, index, metadata, candidates, eval_result) -> dict`
- Deterministic rules only (no LLM)
- Input: existing artifacts from T037
- Output: `project_semantic_summary.json`

Modified files:
- `p1b_project_cli.py`: call `build_semantic_summary()` after trace, write artifact, add to metadata.artifacts
- `cli.py`: no changes needed

### Data Schema: project_semantic_summary.json

```json
{
  "schema_version": "project-semantic-summary-0.1",
  "project_id": "...",
  "project_root": "...",
  "project_kind_hint": "OFDM FPGA module",
  "top_level_purpose": "Deterministic summary from project name + golden concepts + file names",
  "pipeline_stages": [
    {
      "stage_id": "s1_coarse_detect",
      "label": "Coarse Detection",
      "role": "Initial peak and sync detection using autocorrelation",
      "source_files": ["L5/peak_detect.py", "rtl/peak_detect.v"],
      "related_concepts": ["peak_idx", "autocorr"],
      "related_rtl_modules": ["peak_detect"],
      "confidence": "supported",
      "evidence_ids": ["ev_001"]
    }
  ],
  "core_concepts": [
    {
      "canonical_name": "peak_idx",
      "display_name": "Peak Index Detection",
      "category": "algorithm",
      "role_in_project": "Identifies symbol boundary via autocorrelation peak",
      "why_selected": "Cross-stage evidence: L5 model + RTL module + golden spec core",
      "aliases": ["peak", "peak_detect"],
      "l5_l6_evidence_count": 5,
      "rtl_evidence_count": 3,
      "test_evidence_count": 0,
      "confidence": "supported",
      "limitations": ["Test evidence extraction not supported"]
    }
  ],
  "implementation_modules": [
    {
      "module_or_file": "rtl/peak_detect.v",
      "role_hint": "RTL implementation of peak_idx detection",
      "concepts_realized": ["peak_idx"],
      "claims": ["peak_idx_realized_in_peak_detect"],
      "strong_evidence_count": 2,
      "medium_evidence_count": 1,
      "weak_evidence_count": 0,
      "is_shared_by_multiple_concepts": false
    }
  ],
  "dataflow_summary": {
    "nodes": [...],
    "edges": [...]
  },
  "evidence_quality_summary": {
    "strong_direct": 10,
    "medium_structural": 5,
    "weak_name_only": 2,
    "inferred": 3
  },
  "uncertainty_summary": {
    "inferred_claims": [...],
    "weak_only_links": [...],
    "naming_only_links": [...],
    "missing_l5_l6": [...],
    "missing_rtl": [...],
    "missing_test_evidence": [...]
  },
  "test_coverage_summary": {
    "test_files_present": true,
    "total_test_files": 3,
    "concepts_with_test_match": 0,
    "concepts_without_test_match": 12,
    "per_concept": [...]
  },
  "source_provenance": {
    "summary_generated_from": ["project_understanding_graph.json", "project_understanding_index.json", "concept_candidates.json", "discovery_eval_result.json"],
    "generation_timestamp": "..."
  }
}
```

### T037 Fixes (Data Consistency)

1. `run_metadata.json`:
   - `project_id` = `graph.project_id` (fix None)
   - `discovery_mode` = discovery mode string
   - `golden_spec_used` = boolean
   - `selected_concepts` = list of selected names
   - `selected_canonical_concepts` = canonicalized names
   - `selected_concept_count` = len(selected)
   - `eval_metrics` = dict with precision/recall

2. `concept_candidates.json`:
   - `canonical_name` = after alias resolution
   - `score` = score_breakdown.total (not None)
   - `is_selected` = boolean
   - `rejection_reason` = string if not selected
   - `evidence_counts_by_stage` = {"L5": 3, "RTL": 2}

3. `discovery_eval_result.json`:
   - `selected_concepts` / `selected_canonical_concepts` aligned with bundle
   - Alias match details per concept

### Discovery V2.2

Rules for distinguishing core concepts from implementation details:
- **Core**: golden core/alias hits, cross L5+L6+RTL algorithm concepts, stable domain terms in class/module names
- **Demote**: pure parameters (nfft, pipe_depth, rom_addr), pure interfaces (axis, valid, ready), test-only names (TestL1, fixture), overly broad words (sync, stage, core, process)
- **Canonical names must not abbreviate**: peak → peak_idx (if golden says peak_idx), smooth → smooth_detect

### Frontend (Tauri/TS)

New/modified files:
- `types/index.ts`: `ProjectSemanticSummary`, `PipelineStage`, `CoreConcept`, `ImplementationModule`, `DataflowSummary`, `EvidenceQualitySummary`, `UncertaintySummary`, `TestCoverageSummary`
- `utils/artifact_loader.ts` (or equivalent): load `project_semantic_summary.json` as first-class artifact
- `pages/Overview.tsx`: show semantic summary at top, concept table with category/role/evidence columns
- `pages/ProjectGraph.tsx`: summary mode shows project → stage → concept → RTL module
- `pages/UnderstandingCard.tsx`: per-node-type cards (project/stage/concept/claim/rtl)
- `pages/Evidence.tsx`: group by concept → claim → evidence, separate test evidence section
- `utils/agent.ts`: new Q&A patterns for pipeline, stage mapping, concept selection reasons, inferred vs evidence-backed, test coverage

### Validation Gates

1. **coarse_sync_glm**:
   - selected canonical includes peak_idx, cfo, smooth_detect (or canonicalized aliases)
   - top_level_purpose mentions "coarse sync" / "OFDM"
   - pipeline_stages >= 2

2. **fine_cfo**:
   - selected canonical includes fine_cfo/cfo, correlator, cordic, lts/first_path
   - top_level_purpose mentions "fine CFO" / "frequency offset"

3. **fft**:
   - selected canonical includes fft, butterfly, twiddle, dft
   - top_level_purpose mentions "FFT/DFT"
   - axis_interface demoted to interface category

4. **All three**:
   - run_metadata.project_id non-empty
   - selected_canonical_concepts matches traced concepts
   - concept_candidates have score and is_selected
   - project_semantic_summary.json exists
   - No target project modification
   - No Vivado
