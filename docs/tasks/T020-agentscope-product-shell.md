# T020: AgentScope-style Desktop Product Shell

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Transform the PySide6 tab widget into an AgentScope-style product shell with left navigation, main workspace, and card-based overview. The GUI must look like a stable desktop Agent product, not an artifact/debug viewer.

## Background

T019 improved the first screen (Overview-first), but review concluded: direction correct, 力度不够. The GUI was still a PySide6 tab tool. User references AgentScope screenshot and wants fpga_devmind to form a clear product shell: left navigation, main workspace, project/concept entry, Agent entry — not a row of internal tabs.

## Changes

### 1. Left Navigation Sidebar

- Dark sidebar (#1e1e2e) with grouped navigation items
- Groups: 项目理解, Agent, 开发者, 设置
- Active item highlighted with accent color (#89b4fa) left border
- Click switches main content area

### 2. Main Workspace

- Top bar: project name / concept name / bundle status (small), Load Artifact button
- Content area: QStackedWidget with 12 pages
- No more tab row at the top

### 3. 概览 Page (Product Homepage)

- Title: FPGA DevMind
- Subtitle: FPGA Understanding Agent Shell
- Project card + Concept card
- Metrics cards: Mapping Claims / Evidence Items / RTL Objects / Unknowns
- Current understanding summary
- Suggested questions (clickable)
- Next-step buttons: 查看概念追踪, 询问 Agent, 查看证据

### 4. 概念追踪 Page

- Three-section natural language summary at top
- Sub-tabs: Nodes / Edges / Claims / Evidence / Diagnostics

### 5. 证据 Page (New)

- Evidence grouped by source: L5/L6, RTL, Bridge/Mapping
- Tables per group with file, symbol, strength, claim refs

### 6. 不确定项 Page (New)

- Unknown limitations list
- Uncertainty notes list
- Grounding diagnostics table
- "Why not confirmed" explanation

### 7. Agent 问答 Page

- Dominant navigation entry (not a small tab)
- Suggested questions as pill buttons
- Input + Ask
- Structured output: Answer, Evidence referenced, Limitations, Plan Preview

### 8. Agent Runtime Page

- Conditional: disabled/hidden guidance for P1b bundles
- Full trace display for agent_runtime bundles

### 9. 计划与工具 Page

- Plan preview display

### 10. 开发者区

- Raw Data (JSON Tree)
- Markdown preview
- Diagnostics list

### 11. 设置

- 项目设置: artifact path, Browse/Load, bundle info
- 通用设置: placeholder

### 12. Visual Design

- Dark left nav + light content area
- Card-based layout with borders and rounded corners
- Window title: "FPGA DevMind"
- Size: 1400x900

## Files

```text
src/fpga_devmind/desktop/product_shell.py         — new (MainWindow + 12 pages)
src/fpga_devmind/desktop/page_view_models.py      — new (EvidencePageViewModel, UnknownsPageViewModel, etc.)
tests/test_page_view_models.py                    — new (15 tests)
src/fpga_devmind/desktop/_gui.py                  — rewritten (thin wrapper)
docs/desktop-gui-smoke-test.md                    — modified (T020 navigation docs)
docs/implementation-status.md                     — modified (T020 entry)
docs/tasks/T020-agentscope-product-shell.md       — this task card
```

## New APIs

### page_view_models.py

```python
@dataclass
class EvidenceGroup:
    title: str
    rows: list[EvidenceRow]

@dataclass
class EvidencePageViewModel:
    is_loaded: bool
    load_error: str | None
    groups: list[EvidenceGroup]

@dataclass
class UnknownsPageViewModel:
    is_loaded: bool
    load_error: str | None
    limitations: list[str]
    uncertainty_notes: list[str]
    grounding_diagnostics: list[dict]
    why_not_confirmed: str

@dataclass
class OverviewMetrics:
    mapping_claims: int
    evidence_items: int
    rtl_objects: int
    unknowns: int

@dataclass
class AgentRuntimePageState:
    is_visible: bool
    is_loaded: bool
    load_error: str | None
    message: str
    has_trace: bool

def build_evidence_page_view_model(bundle) -> EvidencePageViewModel
def build_unknowns_page_view_model(bundle) -> UnknownsPageViewModel
def build_overview_metrics(bundle) -> OverviewMetrics
def build_agent_runtime_page_state(bundle) -> AgentRuntimePageState
```

## Tests (15 new)

### test_page_view_models.py

1. `test_p1b_three_groups` — P1b bundle produces L5/L6 and RTL evidence groups
2. `test_p1b_group_counts` — Evidence rows correctly split between groups
3. `test_incomplete_bundle` — Incomplete bundle produces is_loaded=False
4. `test_non_p1b_bundle` — Non-P1b bundle shows helpful message
5. `test_p1b_limitations` — P1b bundle extracts limitations from unknown claims
6. `test_p1b_uncertainty_notes` — P1b bundle extracts uncertainty notes
7. `test_p1b_why_not_confirmed` — Why-not-confirmed explanation present
8. `test_non_p1b_bundle_unknowns` — Non-P1b bundle shows helpful message
9. `test_p1b_metrics` — P1b bundle produces correct metric counts
10. `test_agent_runtime_metrics` — Agent runtime bundle produces metrics from trace
11. `test_incomplete_bundle_metrics` — Incomplete bundle produces is_loaded=False
12. `test_p1b_bundle_not_visible` — P1b bundle makes Agent Runtime page not visible with message
13. `test_agent_runtime_bundle_visible` — Agent runtime bundle makes page visible and loaded
14. `test_no_bundle` — No bundle shows prompt message
15. `test_no_forbidden_imports` — No LLM/API/Vivado imports

## Test Count

- Before T020: 422 tests
- T020 adds: 15 tests (page_view_models)
- Total after T020: 437 tests

## Boundaries

```text
- No LLM, no API key, no external API call.
- No Vivado / synthesis / implementation / bitstream.
- No fpga_project_* mutation (read-only project tree scan).
- No graph write execution (only display of blocked proposals).
- No PASS / HOLD / finding / audit.
- No Web GUI / Web server.
- PySide6 is optional; fallback prints dependency hint and exits 0.
- All view models pure Python, testable without PySide6.
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_page_view_models -v
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli desktop-sample-run
PYTHONPATH=src .venv/bin/python -m fpga_devmind.desktop_app --artifact-dir /private/tmp/fpga_devmind/desktop_sample/p1b
```

## Next Steps

- Real LLM provider integration
- Multi-turn ReAct loop with live trace streaming
- Richer page templates as more bundle types are added
