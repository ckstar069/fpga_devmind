# T017: Desktop Agent Runtime Trace Viewer

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Extend the PySide6 Desktop Shell to recognize, load, and display `agent_runtime_trace.json` produced by T016's `agent-noop-run`. Pure viewer — no Agent execution, no LLM.

## Why T017

1. **T016 produces `agent_runtime_trace.json`** but the GUI can only display P1a/P1b bundles. T017 bridges this gap.
2. **First GUI rendering of Agent runtime output**: Enables visual inspection of the observe→plan→propose→result→answer→graph-write trace.
3. **Reuses existing patterns**: artifact_loader detection, view model dataclass rows, QTableWidget population — consistent with T010 Concept Trace tab.
4. **No new dependencies**: Pure PySide6 widget code + pure-Python view model.

## Dependencies

- T014: PySide6 optional dependency, sample artifact discovery, `--recent` flag
- T016: `agent-noop-run` outputs `agent_runtime_trace.json` + `answer.md`

## Public API

### artifact_loader.py additions

```python
AGENT_RUNTIME_REQUIRED_ARTIFACTS: tuple[str, ...] = ("agent_runtime_trace.json",)
AGENT_RUNTIME_OPTIONAL_ARTIFACTS: tuple[str, ...] = ("answer.md",)

def get_agent_runtime_trace(bundle: ArtifactBundle) -> dict[str, Any] | None
```

### agent_trace_view_models.py (new)

```python
@dataclass
class AgentTraceSummaryRow:
    field: str
    value: str

@dataclass
class AgentTraceStepRow:
    section: str      # task|observation|reasoning|plan|proposal|result|answer|graph_write
    item_id: str
    title: str
    status: str       # never PASS/HOLD
    summary: str
    references: str

@dataclass
class AgentTraceDiagnosticRow:
    severity: str
    message: str

@dataclass
class AgentRuntimeTraceViewModel:
    summary_rows: list[AgentTraceSummaryRow]
    step_rows: list[AgentTraceStepRow]
    diagnostic_rows: list[AgentTraceDiagnosticRow]
    is_loaded: bool = False
    load_error: str | None = None

def build_agent_runtime_trace_view_model(bundle: ArtifactBundle) -> AgentRuntimeTraceViewModel
```

## Behavior Flow

1. User loads a directory containing `agent_runtime_trace.json`
2. `detect_bundle_type()` returns `"agent_runtime"` (checked before P1b/P1a)
3. `load_bundle()` loads trace JSON + optional `answer.md`
4. `_update_agent_runtime()` calls `build_agent_runtime_trace_view_model()`
5. Summary form populated with schema version, task, counts
6. Steps table populated with task/observation/reasoning/plan/proposal/result/answer/graph_write rows
7. Diagnostics table populated from `runtime_diagnostics`

## GUI Tab: "Agent Runtime"

- **Summary form**: QFormLayout with key-value pairs (Schema Version, Task ID, Question, counts, etc.)
- **Steps table**: 6 columns (Section, ID, Title, Status, Summary, References)
- **Diagnostics table**: 2 columns (Severity, Message) — hidden when empty

Empty states:
- No bundle → "No bundle loaded."
- Non-agent_runtime bundle → "Load an agent runtime bundle containing agent_runtime_trace.json."

## Files

```text
src/fpga_devmind/desktop/artifact_loader.py          — agent_runtime detection/validation/helper
src/fpga_devmind/desktop/agent_trace_view_models.py  — new view model (13 rows types + builder)
src/fpga_devmind/desktop/_gui.py                     — Agent Runtime tab + _update_agent_runtime()
tests/test_desktop_agent_trace_view_models.py        — 13 tests
tests/test_sample_artifacts.py                       — +1 test (agent_runtime bundle discovery)
```

## Tests (14 new)

### test_desktop_agent_trace_view_models.py (13 tests)

1. detect agent_runtime bundle type
2. load bundle with trace + answer.md
3. invalid JSON yields load diagnostic
4. view model happy path (is_loaded=True)
5. summary counts correct (all sections)
6. step rows include all 8 sections (task/observation/reasoning/plan/proposal/result/answer/graph_write)
7. runtime diagnostics displayed
8. graph write shows "blocked", never PASS/HOLD
9. non-agent_runtime bundle → is_loaded=False
10. missing trace JSON → load_error
11. answer limitations shown in summary
12. graph write allowed → status "allowed" (viewer-only: current T016 no-op always produces blocked; "allowed" display proves forward-compatibility with future schema-compatible traces, does not mean the Agent Shell can execute graph writes)
13. constraints shown in summary

### test_sample_artifacts.py (+1 test)

14. discovers agent_runtime bundle

## Boundaries

```text
- No Agent execution.
- No LLM / API key / external API.
- No Vivado / synthesis / implementation / bitstream.
- No fpga_project_* mutation.
- No graph writes (only proposals, displayed as "blocked" or "allowed"). T016 no-op runtime generates only "blocked" proposals; "allowed" display exists for forward-compatibility and does not indicate the Agent Shell can modify graphs or target projects.
- No PASS / HOLD / finding / audit semantics.
- Pure viewer: read-only display of existing trace JSON.
- No Web GUI / Electron.
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_desktop_agent_trace_view_models -v
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src basedpyright src/fpga_devmind/desktop/agent_trace_view_models.py src/fpga_devmind/desktop/artifact_loader.py
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```

## Next Steps

- T018 (future): Real LLM provider integration
- T019 (future): Multi-turn ReAct loop with live trace streaming
