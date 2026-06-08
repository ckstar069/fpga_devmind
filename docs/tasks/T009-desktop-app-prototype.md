# T009: Desktop App Prototype

## Objective

Implement the minimum viable desktop Agent Shell that can read P1a/P1b
artifact bundles and display basic views.  This is a **prototype**, not a
production UI.  The goal is to validate the desktop shell architecture before
building rich views (T010).

## Technology Stack

**Primary: PySide6 (Python-native Qt binding)**

- Chosen because it stays in the Python codebase and reuses `fpga_devmind`
  dataclasses directly.
- If PySide6 is not installed, the loader / view-model layer still works;
  the GUI entry point prints a dependency message and exits gracefully.
- Tauri/WebView remains a future alternative if binary size proves critical.

## Scope

### 1. Artifact Directory Picker / Path Input

- User selects or types an artifact directory path.
- Supports P1b 6-artifact bundles and P1a fallback bundles.
- Produces structured diagnostics for missing files; never crashes.

### 2. Run Summary View

- Reads `run_metadata.json`.
- Displays: concept, status, mapping_claims, evidence_items,
  blocking_diagnostics, elapsed_seconds, output_dir.
- `status == "ok"` and `status == "blocked"` are both displayed neutrally
  (green/blue vs orange, not red error).

### 3. JSON Tree Browser

- Browses any JSON artifact (`concept_trace_graph.json`,
  `concept_trace_index.json`, `grounding_report.json`, `run_metadata.json`).
- Tree widget with collapsible nodes.
- Key / Value / Type columns.
- Max-depth protection for deeply nested JSON.

### 4. Markdown Preview

- Reads `concept_trace.md`.
- Read-only plain text display (no rich Markdown renderer in T009).
- Falls back to `concept_trace.mmd` if `.md` is missing.

### 5. Diagnostics Tab

- Lists all `ArtifactDiagnostic` items from bundle validation.
- Severity-colored labels: error (red), warning (yellow), info (gray).

### 6. Safety / Boundary

- Read-only artifact viewer; never writes to artifact directory.
- Never reads `fpga_project_*` source trees.
- Never runs Vivado / synthesis / implementation / bitstream.
- Never loads API keys or calls external LLMs.
- Unknown confidence is normal, not an error.
- Grounding diagnostics are warnings, not PASS/HOLD audit results.

## Files

```text
src/fpga_devmind/desktop/__init__.py
src/fpga_devmind/desktop/artifact_loader.py   # Bundle detection, validation, loading
src/fpga_devmind/desktop/view_models.py        # RunSummary, JsonTree, MarkdownPreview VMs
src/fpga_devmind/desktop/_gui.py               # PySide6 GUI (imported only when available)
src/fpga_devmind/desktop_app.py                # Entry point with graceful fallback
tests/test_desktop_artifact_loader.py          # Loader tests
tests/test_desktop_view_models.py              # View-model tests
```

## Entry Point

```bash
# If PySide6 is installed:
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --artifact-dir /tmp/fpga_devmind/p1b_peak_idx

# If PySide6 is missing:
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
# → prints dependency message and exits 0
```

## Acceptance

- [x] Artifact loader detects P1b/P1a/unknown bundles correctly.
- [x] Incomplete bundles produce structured diagnostics, not crashes.
- [x] Run Summary view-model parses `run_metadata.json` correctly.
- [x] JSON Tree view-model handles nested dicts/lists and max-depth.
- [x] Markdown Preview view-model reads `.md` and `.mmd` files.
- [x] GUI entry point launches with directory picker, tabs, and load button.
- [x] PySide6 missing → graceful message, exit 0.
- [x] All 229 tests pass (194 P1a/P1b + 35 desktop).
- [x] No regression in existing CLI commands.

## Not Implemented (T010)

- Rich concept trace graph view (interactive node/edge navigation).
- Evidence browser with filtering and cross-reference popovers.
- Mapping claim detail cards with expandable evidence.
- Grounding diagnostic overlay on claims.
- Mermaid live rendering (only source text display).
- Agent interaction panel (query, response, tool calls).

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```
