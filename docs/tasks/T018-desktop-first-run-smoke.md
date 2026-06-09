# T018: Desktop GUI First-Run Smoke and Usability Hardening

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Make the Desktop Shell go from "code-layer usable" to "user can actually start and see content" with minimum friction. One CLI command to generate sample artifacts, clear documentation, and explicit capability boundaries.

## Why T018

1. **User friction**: Before T018, users had to manually chain `p1b-trace-concept` → `agent-noop-run` → `desktop_app --artifact-dir` to see anything in the GUI.
2. **No first-run docs**: No single place describing the zero-to-GUI flow.
3. **Capability confusion**: No explicit declaration of what the GUI is and is not.
4. **Missing smoke validation**: No automated test for the one-click sample path.

## Dependencies

- T014: PySide6 optional dependency, sample artifact discovery
- T016: `agent-noop-run` CLI and runtime
- T007: `p1b-trace-concept` CLI

## Public API

### desktop_sample_run.py (new)

```python
DEFAULT_SAMPLE_PROJECT = Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm")
DEFAULT_SAMPLE_CONCEPT = "peak_idx"
DEFAULT_SAMPLE_QUESTION = "summary"
DEFAULT_SAMPLE_OUT = Path("/tmp/fpga_devmind/desktop_sample")

@dataclass
class DesktopSampleResult:
    p1b_dir: Path
    noop_dir: Path
    p1b_status: str
    noop_status: str
    status: str  # "ok" | "partial" | "error"
    messages: list[str] = field(default_factory=list)

def run_desktop_sample(
    project_root: Path = DEFAULT_SAMPLE_PROJECT,
    concept: str = DEFAULT_SAMPLE_CONCEPT,
    question: str = DEFAULT_SAMPLE_QUESTION,
    out_root: Path = DEFAULT_SAMPLE_OUT,
) -> DesktopSampleResult
```

### CLI subcommand

```
fpga-devmind desktop-sample-run [--project P] [--concept C] [--question Q] [--out O]
```

All arguments optional with sensible defaults.

## Behavior Flow

1. `ensure_safe_output_dir(out_root)` — reject paths inside fpga_project_*
2. `run_p1b_trace_concept(project_root, concept, out_root / "p1b")` — generate P1b bundle
3. If P1b fails → return error status immediately
4. `run_noop_agent_once(p1b_dir, question, out_root / "noop_run")` — generate agent runtime trace
5. If no-op fails → return partial status
6. Print both bundle paths + `desktop_app --artifact-dir` hint
7. Return `DesktopSampleResult`

## Files

```text
src/fpga_devmind/desktop_sample_run.py           — new module (sample artifact generator)
src/fpga_devmind/cli.py                          — register desktop-sample-run subcommand
tests/test_desktop_sample_run.py                 — 6 tests
docs/desktop-gui-smoke-test.md                   — Quick Start + Current GUI Capabilities
docs/p1a-v0.1-quickstart.md                      — desktop-sample-run one-click trial
docs/implementation-status.md                     — T018 entry
docs/tasks/T018-desktop-first-run-smoke.md       — this task card
```

## Tests (6 new)

### test_desktop_sample_run.py

1. `test_happy_path_creates_both_bundles` — P1b + agent-runtime bundles created
2. `test_p1b_artifacts_are_valid` — P1b JSON has nodes + edges
3. `test_noop_trace_is_valid` — agent_runtime_trace has valid schema
4. `test_unsafe_output_dir_raises` — path inside fpga_project_* rejected
5. `test_nonexistent_project_returns_error` — error status for missing project
6. `test_no_forbidden_imports` — no openai/anthropic/requests/vivado/subprocess

## Boundaries

```text
- No LLM, no API key, no external API call.
- No Vivado / synthesis / implementation / bitstream.
- No fpga_project_* mutation (read-only project tree scan).
- No graph write execution (only display of blocked proposals).
- No PASS / HOLD / finding / audit.
- No Web GUI / Web server.
- PySide6 is optional; fallback prints dependency hint and exits 0.
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_desktop_sample_run -v
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli desktop-sample-run
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```

## Next Steps

- Real LLM provider integration
- Multi-turn ReAct loop with live trace streaming
