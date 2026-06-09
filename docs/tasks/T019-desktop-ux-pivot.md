# T019: Desktop Agent Shell UX Pivot

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Transform the Desktop Agent Shell from an artifact/debug viewer into a user-understandable FPGA Understanding Agent tool. The first screen and core interaction must be comprehensible to a human without prior knowledge of the internal data structures.

## Why T019

User trial feedback: "完全看不懂，离想要的还很远". The GUI was still an artifact viewer (Run Summary → JSON Tree → Markdown → Diagnostics → Concept Trace → Agent → Agent Runtime), not a user-facing FPGA Agent shell. Issues:

1. **Run Summary** was metadata, not a user perspective
2. **JSON Tree** was a debug tool, ranked second
3. **Concept Trace** showed only tables, no natural language summary
4. **Agent tab** had no guidance — blank state, English placeholder
5. **Agent Runtime** tab showed empty state for P1b bundles, confusing
6. **Window title** still said "T009"

## Hard Constraints

- No LLM, no API key, no external API call
- No Vivado / synthesis / implementation / bitstream
- No fpga_project_* mutation
- No graph write execution
- No PASS / HOLD / finding / audit
- No Web GUI / Electron / new dependencies
- All view models pure Python, testable without PySide6
- Existing tests must pass unchanged

## Changes

### 1. Overview Tab (new, replaces Run Summary as first screen)

- `OverviewViewModel` with: project_path, concept_name, bundle_type, current_understanding, evidence summaries, mapping confidence, unknown_limitations, suggested_questions
- Deterministic template generation from bundle data (no LLM)
- Human-oriented HTML rendering: concept name, current understanding paragraph, evidence overview table, mapping confidence, uncertainty list
- Graceful empty state for no bundle / incomplete / unknown bundle types

### 2. Concept Understanding (renamed from Concept Trace)

- Natural language summary widget at top (maxHeight 200px)
- `format_concept_trace_summary()` produces three-section text: L5/L6 side → Mapping claims → RTL side
- Structured sub-tables (Nodes/Edges/Claims/Evidence/Diagnostics) remain below
- Empty/help states for non-P1b bundles

### 3. Agent Tab (primary interaction entry)

- Suggested questions label at top (💡 emoji, Chinese text)
- Placeholder changed to Chinese: "输入问题，例如：概况、映射、证据、诊断、不确定、节点、边，或 claim/evidence ID"
- Plan preview placeholder: "选择上方问题，或输入自己的问题后点击 Ask。"
- Questions populated from `OverviewViewModel.suggested_questions`
- 6 P1b questions + 3 agent_runtime questions

### 4. Developer Tab (demoted JSON Tree)

- Renamed from "JSON Tree" to "Developer"
- Moved from index 1 to index 5 (near last)
- Same functionality — JSON artifact tree browser

### 5. Agent Runtime Tab (conditional visibility)

- Tab disabled when bundle type is not "agent_runtime"
- Non-agent_runtime bundles show info message about current type
- No confusing empty states

### 6. Window Title

- "fpga_devmind — Desktop Agent Shell (T009)" → "fpga_devmind — FPGA Understanding Agent Shell"

### 7. Empty/Help States

- Overview: descriptive HTML for no bundle / incomplete / loaded
- Concept Understanding: natural language for non-P1b bundles
- Agent: Chinese guidance when no bundle or empty question
- Diagnostics: "✓ 无诊断信息 — bundle 完整。" when clean
- Agent Runtime: disabled tab + contextual message

### 8. Tab Order

```
0. Overview (new)
1. Concept Understanding (renamed)
2. Agent (enhanced)
3. Markdown (unchanged)
4. Diagnostics (enhanced empty state)
5. Developer (renamed + demoted)
6. Agent Runtime (conditional)
```

## Files

```text
src/fpga_devmind/desktop/overview_models.py           — new (OverviewViewModel + format_concept_trace_summary)
tests/test_overview_models.py                         — new (15 tests)
src/fpga_devmind/desktop/_gui.py                      — modified (8 GUI changes)
docs/desktop-gui-smoke-test.md                        — modified (T019 updates)
docs/implementation-status.md                         — modified (T019 entry)
docs/tasks/T019-desktop-ux-pivot.md                   — this task card
```

## New APIs

### overview_models.py

```python
@dataclass
class SuggestedQuestion:
    text: str    # "这个概念的整体情况如何？"
    topic: str   # "summary"

@dataclass
class EvidenceStrengthSummary:
    strong: int = 0; medium: int = 0; weak: int = 0; unknown: int = 0; total: int = 0

@dataclass
class MappingConfidenceSummary:
    supported: int = 0; inferred: int = 0; unknown: int = 0; confirmed: int = 0; total: int = 0

@dataclass
class OverviewViewModel:
    project_path: str = ""
    concept_name: str = ""
    bundle_type: str = ""
    is_loaded: bool = False
    load_error: str | None = None
    current_understanding: str = ""
    l5_l6_evidence_summary: EvidenceStrengthSummary
    rtl_evidence_summary: EvidenceStrengthSummary
    mapping_confidence: MappingConfidenceSummary
    unknown_limitations: list[str]
    suggested_questions: list[SuggestedQuestion]

def build_overview_view_model(bundle: ArtifactBundle) -> OverviewViewModel

def format_concept_trace_summary(vm: ConceptTraceViewModel) -> str
```

## Tests (15 new)

### test_overview_models.py

1. `test_p1b_complete_bundle_loaded` — Complete P1b bundle produces is_loaded=True
2. `test_p1b_current_understanding_contains_concept` — current_understanding mentions concept name
3. `test_p1b_evidence_strength_counts` — L5/L6 and RTL evidence correctly split and counted
4. `test_p1b_mapping_confidence` — Mapping confidence counts are correct
5. `test_p1b_suggested_questions` — P1b bundle provides 6 Chinese suggested questions
6. `test_p1b_unknown_limitations` — Uncertainty notes collected into unknown_limitations
7. `test_agent_runtime_overview` — Agent runtime bundle produces correct overview
8. `test_incomplete_bundle_not_loaded` — Incomplete bundle produces is_loaded=False
9. `test_unknown_bundle_graceful` — Unknown bundle type degrades gracefully
10. `test_three_section_output` — format_concept_trace_summary contains L5/L6, Mapping claims, RTL sections
11. `test_not_loaded_returns_error` — Not-loaded VM returns error text
12. `test_increment_strength` — _increment_strength updates correct counters
13. `test_increment_confidence` — _increment_confidence updates correct counters
14. `test_format_confidence_summary` — _format_confidence_summary produces readable string
15. `test_translate_confidence` — _translate_confidence translates all known labels

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
PYTHONPATH=src python3 -m unittest tests.test_overview_models -v
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli desktop-sample-run
PYTHONPATH=src .venv/bin/python -m fpga_devmind.desktop_app --artifact-dir /private/tmp/fpga_devmind/desktop_sample/p1b
```

## Test Count

- Before T019: 407 tests
- T019 adds: 15 tests (overview_models)
- Total after T019: 422 tests

## Next Steps

- Real LLM provider integration
- Multi-turn ReAct loop with live trace streaming
- Richer Overview templates as more bundle types are added
