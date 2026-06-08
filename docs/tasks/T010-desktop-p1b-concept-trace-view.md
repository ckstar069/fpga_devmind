# T010: Desktop P1b Concept Trace View

## Objective

Add a structured interactive table view for P1b concept trace artifacts inside
the T009 Desktop Agent Shell.  This is **not** a graph layout engine, **not**
an Agent chat panel, and **not** a claim editor — it is a read-only structured
table viewer.

## Scope

### 1. Trace View Model Layer (pure Python, no PySide6)

**File:** `src/fpga_devmind/desktop/trace_view_models.py`

Transforms `concept_trace_graph.json`, `concept_trace_index.json`, and
`grounding_report.json` into view-ready row structures:

- **NodeRow**: node_id, label, kind, stage_id, confidence, evidence_count, has_diagnostics
- **EdgeRow**: edge_id, from_label, to_label, edge_type, confidence, claim_refs
- **ClaimRow**: claim_id, concept_ref, confidence, bridge_kind, l5_l6_evidence_count,
  rtl_evidence_count, bridge_evidence_count, required_missing_evidence, diagnostic_count
- **EvidenceRow**: evidence_id, source_type, file_path, symbol, evidence_strength,
  referenced_by_claims
- **DiagnosticRow**: diagnostic_id, severity, issue_type, target_claim_id, message,
  recommended_action

**Factory:** `build_concept_trace_view_model(bundle) -> ConceptTraceViewModel`

- Checks `bundle.is_complete` and `bundle.bundle_type == "p1b"`.
- Uses `get_graph()`, `get_index()`, `get_grounding_report()` from artifact_loader.
- Never raises; returns `is_loaded=False` with descriptive `load_error`.
- Cross-reference resolution:
  - Edge from_label/to_label via node_id -> label mapping; dangling endpoints
    marked `(unresolved: <node_id>)`.
  - Evidence referenced_by_claims via index.evidence_index claim_ids.
  - Claim diagnostic_count via graph.grounding_diagnostics + grounding_report.diagnostics.
- Dangling references are preserved and marked unresolved; no crashes.

### 2. Cross-reference Semantics

- `confidence == "unknown"` is normal, not an error.
- `blocking` diagnostic is an overclaim warning, not a PASS/HOLD audit result.
- `non_blocking` diagnostic is an acknowledged uncertainty.
- View model uses raw `severity` and `confidence` fields; does not generate
  pass/fail/false/true status.

### 3. GUI Layer

**File:** `src/fpga_devmind/desktop/_gui.py`

New **"Concept Trace"** tab added to the main tab widget.  Inside it, a nested
QTabWidget provides 5 sub-tabs:

| Sub-tab | Columns |
|---|---|
| **Nodes** | Node ID, Label, Kind, Stage, Confidence, Evidence, Diagnostics |
| **Edges** | Edge ID, From, To, Type, Confidence, Claims |
| **Claims** | Claim ID, Concept, Confidence, Bridge, L5/L6 Ev., RTL Ev., Bridge Ev., Missing, Diagnostics |
| **Evidence** | Evidence ID, Source, File, Symbol, Strength, Claim Refs |
| **Diagnostics** | ID, Severity, Issue Type, Target Claim, Message, Action |

- Each sub-tab uses `QTableWidget` with row selection.
- If bundle is not P1b, shows "Trace view available for P1b bundles only".
- If view model fails to load, shows the `load_error` message.
- No graph layout, no node-edge diagram rendering, no click-through popovers.

### 4. Not Implemented

- Graph layout engine / node-edge visual diagram.
- Click-to-navigate cross-reference popovers.
- Evidence filtering or search.
- Claim detail cards with expandable evidence.
- Mermaid live rendering (still source-text only).
- Agent interaction panel (T011).
- Claim editing / artifact mutation.

### 5. Tests

**File:** `tests/test_desktop_trace_view_models.py`

Pure-Python tests (no PySide6):

- `test_trace_vm_loads_complete_p1b`
- `test_non_p1b_bundle_shows_message`
- `test_incomplete_bundle_load_error`
- `test_nodes_parsed_from_graph`
- `test_node_evidence_count`
- `test_node_has_diagnostics`
- `test_edges_with_resolved_labels`
- `test_dangling_edge_endpoint_marked_unresolved`
- `test_claims_with_evidence_counts`
- `test_unknown_claim_counts`
- `test_evidence_referenced_by_claims`
- `test_diagnostics_linked_to_claims`
- `test_diagnostics_from_grounding_report`
- `test_unknown_confidence_not_error`
- `test_empty_graph_loads_empty_rows`
- `test_missing_graph_returns_load_error`

### 6. Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
```

## Safety / Boundary

- Read-only artifact viewer; never writes to artifact directory.
- Never reads `fpga_project_*` source trees.
- Never runs Vivado / synthesis / implementation / bitstream.
- Never loads API keys or calls external LLMs.
- Unknown confidence is normal, not an error.
- Grounding diagnostics are warnings, not PASS/HOLD audit results.
