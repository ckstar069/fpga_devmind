# T038 Project Semantic Understanding Pack — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or inline execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend fpga_devmind from concept lists to a structured Project Semantic Understanding Pack with pipeline stages, core concept categorization, implementation module mapping, evidence quality assessment, uncertainty tracking, and test coverage — all without external LLM calls.

**Architecture:** Build a new `project_semantic_summary.py` backend module that consumes existing T037 artifacts (graph, index, candidates, eval) and produces `project_semantic_summary.json`. Simultaneously fix T037 data consistency issues (missing project_id, canonical names, scores, is_selected flags). Update Tauri frontend to display semantic summary as first-class data.

**Tech Stack:** Python 3.14, pytest, Tauri (Rust + TypeScript/React), Vitest

---

## Module A: T037 Data Consistency Fixes

### Task A1: Fix run_metadata.json fields

**Files:**
- Modify: `src/fpga_devmind/p1b_project_cli.py`
- Test: `tests/test_t038_semantic_pack.py`

**Changes:**
1. `project_id` = `graph.project_id` (not None)
2. Add `selected_canonical_concepts` list
3. Add `selected_concept_count`
4. Ensure `eval_metrics` dict has `selected_precision_like` and `selected_recall_like`

```python
# In p1b_project_cli.py, when building metadata:
metadata["project_id"] = graph.project_id or project_root.name
metadata["selected_concepts"] = [c.name for c in selected]
metadata["selected_canonical_concepts"] = canonical_names
metadata["selected_concept_count"] = len(selected)
```

### Task A2: Fix concept_candidates.json fields

**Files:**
- Modify: `src/fpga_devmind/p1b_discovery.py`
- Modify: `src/fpga_devmind/p1b_project_cli.py`

**Changes:**
1. Add `canonical_name` field to ConceptCandidate
2. Ensure `score` = `score_breakdown.total` (never None)
3. Add `is_selected` boolean
4. Add `rejection_reason` string
5. Add `evidence_counts_by_stage` dict

```python
# In ConceptCandidate dataclass:
canonical_name: str = ""
score: int = 0
evidence_counts_by_stage: dict[str, int] = field(default_factory=dict)
```

### Task A3: Fix discovery_eval_result.json alignment

**Files:**
- Modify: `src/fpga_devmind/discovery_eval.py`

**Changes:**
1. Ensure `selected_concepts` / `selected_canonical_concepts` match bundle
2. Add alias match details per concept in `details`

---

## Module B: Discovery V2.2 — Core vs Implementation Detail

### Task B1: Strengthen core concept selection rules

**Files:**
- Modify: `src/fpga_devmind/p1b_discovery.py`

**Rules to add:**
- Demote `axis`, `valid`, `ready`, `data`, `addr`, `fifo` to `interface` or `generic_variable`
- Demote pure parameters (`pipe_depth`, `rom_addr`, `denom_bits`) unless golden spec says core
- Demote `pipeline` to `implementation_detail` if not matched by golden
- Prevent abbreviation: `peak` → `peak_idx` (if golden says peak_idx)
- `smooth` → `smooth_detect`

### Task B2: Update canonical name resolution

**Files:**
- Modify: `src/fpga_devmind/p1b_discovery.py`

**Changes:**
- `_pick_canonical` must prefer golden canonical names when aliases match
- If alias group contains `peak_idx` and `peak`, canonical must be `peak_idx`

---

## Module C: ProjectSemanticSummary Backend

### Task C1: Create project_semantic_summary.py

**Files:**
- Create: `src/fpga_devmind/project_semantic_summary.py`
- Test: `tests/test_t038_semantic_pack.py`

**Core function:**
```python
def build_semantic_summary(
    project_root: Path,
    graph: ProjectGraph,
    index: ProjectIndex,
    metadata: dict,
    candidates: list[ConceptCandidate],
    eval_result: EvalResult | None,
) -> dict:
    """Build deterministic semantic summary from existing artifacts."""
```

**Sub-functions:**
- `_infer_top_level_purpose(project_id, golden_concepts, files)` — deterministic rules
- `_extract_pipeline_stages(graph, index)` — from L5/L6/RTL file structure
- `_build_core_concepts(candidates, index, eval_result)` — categorized concept list
- `_build_implementation_modules(graph, index)` — RTL module aggregation
- `_build_dataflow_summary(graph)` — nodes and edges
- `_build_evidence_quality_summary(index)` — strong/medium/weak/inferred counts
- `_build_uncertainty_summary(graph, index)` — inferred claims, weak links, missing evidence
- `_build_test_coverage_summary(project_root, index)` — scan test files

### Task C2: Integrate semantic summary into project trace

**Files:**
- Modify: `src/fpga_devmind/p1b_project_cli.py`

**Changes:**
- After trace completes, call `build_semantic_summary()`
- Write `project_semantic_summary.json` to bundle dir
- Add to `metadata["artifacts"]` list
- Add `semantic_summary_path` to index

---

## Module D: Test Evidence Extraction Enhancement

### Task D1: Scan test files for concept matches

**Files:**
- Modify: `src/fpga_devmind/p1b_project_cli.py`

**Changes:**
- Scan `tests/` directory for `.py` files
- Extract test function names, class names, assert strings
- Match against concept aliases
- Update evidence chain with `test_name_match` or `test_assert_or_behavior_hint` status

---

## Module E: Bundle Generation

### Task E1: Generate 3 semantic bundles

**Commands:**
```bash
python -m fpga_devmind.cli p1b-trace-project \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concepts auto --out /tmp/fpga_devmind/t038_coarse_semantic \
  --golden-spec docs/benchmarks/coarse_sync_glm-golden-concepts.json

# Same for fine_cfo and fft
```

**Verify:**
- 9 files per bundle (new: project_semantic_summary.json)
- run_metadata has project_id, selected_canonical_concepts, eval_metrics
- concept_candidates have canonical_name, score, is_selected
- project_semantic_summary.json exists and has all required fields

---

## Module F: Frontend Types & Loading

### Task F1: Add TypeScript types

**Files:**
- Modify: `apps/fpga-devmind-tauri/src/types/index.ts`

**New types:**
```typescript
export interface ProjectSemanticSummary {
  schema_version: string;
  project_id: string;
  project_root: string;
  project_kind_hint: string;
  top_level_purpose: string;
  pipeline_stages: PipelineStage[];
  core_concepts: CoreConcept[];
  implementation_modules: ImplementationModule[];
  dataflow_summary: DataflowSummary;
  evidence_quality_summary: EvidenceQualitySummary;
  uncertainty_summary: UncertaintySummary;
  test_coverage_summary: TestCoverageSummary;
  source_provenance: SourceProvenance;
}
```

### Task F2: Extend ProjectBundle type

**Changes:**
- Add `semantic_summary?: ProjectSemanticSummary` to `ProjectBundle`

### Task F3: Update Rust artifact loader

**Files:**
- Modify: `apps/fpga-devmind-tauri/src-tauri/src/artifact_loader.rs`

**Changes:**
- Load `project_semantic_summary.json` if present
- Attach to `ProjectBundle`

---

## Module G: Frontend Pages

### Task G1: Overview.tsx — Semantic Summary Display

**Changes:**
- Top section: Project purpose, kind hint, pipeline stages overview
- Concept table: columns = Concept, Category, Role, L5/L6, RTL, Test, Confidence, Limitations
- Evidence quality bar chart (strong/medium/weak/inferred)
- Uncertainty list
- Test coverage summary

### Task G2: ProjectGraph.tsx — Stage-Aware Layout

**Changes:**
- Summary mode: project → stage → concept → RTL module
- Detail mode: preserve claim/evidence details
- Focus mode: fix neighborhood rendering (ensure nodes exist for edges)
- Right panel: show node provenance (which artifact field, which files)

### Task G3: UnderstandingCard.tsx — Per-Node-Type Cards

**Changes:**
- Project card: purpose, stages, core concepts, dataflow
- Stage card: role, source files, related concepts, related RTL
- Concept card: role, L5/L6 evidence, RTL implementation, test coverage, confidence, limitations, next steps
- RTL module card: file path, realized concepts, claims, evidence snippets, shared flag
- Claim card: bridge kind, confidence, evidence list, why inferred

### Task G4: Evidence.tsx — Concept-Grouped View

**Changes:**
- Default grouping: concept → claim → evidence
- Test evidence in separate section
- Weak/comment-only evidence collapsed by default
- Show "why these evidence support this concept" per group

### Task G5: Settings.tsx — Quick Load T038 Bundles

**Changes:**
- Add quick load buttons for t038_* bundles

---

## Module H: Agent Q&A Enhancement

### Task H1: New answer functions

**Files:**
- Modify: `apps/fpga-devmind-tauri/src/utils/agent.ts`

**New patterns:**
- "pipeline" → answerPipelineStages(bundle)
- "stage.*RTL" → answerStageToRtl(bundle)
- "why.*selected" → answerWhySelected(bundle, concept)
- "implementation detail" → answerImplementationDetails(bundle)
- "test.*cover" → answerTestCoverageDetail(bundle)
- "inferred" → answerInferredAreas(bundle)
- "data.*from" → answerDataProvenance(bundle)

**All answers must:**
- Reference specific concept/stage/module/evidence IDs
- Explicitly state evidence-backed vs inferred

---

## Module I: Tests & Validation

### Task I1: Python tests

**Files:**
- Create: `tests/test_t038_semantic_pack.py`

**Tests:**
- Metadata consistency (project_id, canonical names, scores, is_selected)
- Semantic summary schema validation
- Stage extraction (>=2 stages for coarse)
- Core concept canonicalization (peak_idx not peak, smooth_detect not smooth)
- Test evidence extraction
- Bundle completeness (9 files)
- Real project gates (coarse: top_level_purpose mentions OFDM coarse sync)

### Task I2: TypeScript tests

**Files:**
- Modify: `apps/fpga-devmind-tauri/src/__tests__/transforms.test.ts`
- Modify: `apps/fpga-devmind-tauri/src/__tests__/agent.test.ts`
- Modify: `apps/fpga-devmind-tauri/src/__tests__/cardBuilder.test.ts`

**Tests:**
- Overview semantic summary rendering
- Project graph stage layout
- Focus mode neighborhood
- Understanding card per node type
- Evidence concept grouping
- Agent semantic questions

---

## Self-Review Checklist

- [x] Spec coverage: All 7 sections from user spec have corresponding tasks
- [x] Placeholder scan: No TBD/TODO/fill-in-details
- [x] Type consistency: `ProjectSemanticSummary` fields match schema in spec
- [x] File paths: All paths verified against actual codebase
- [x] No external LLM/API calls in any task
- [x] No Vivado/synthesis references
- [x] Output goes to /tmp

---

## Execution Order

Recommended order (dependencies):
1. A1-A3 (T037 fixes) — foundation for everything
2. B1-B2 (Discovery V2.2) — affects candidate quality
3. C1-C2 (Semantic Summary backend) — core deliverable
4. D1 (Test evidence) — enriches summary
5. E1 (Bundle generation) — produces artifacts
6. F1-F3 (Frontend types/loading)
7. G1-G5 (Frontend pages)
8. H1 (Agent)
9. I1-I2 (Tests)
