# T020a: Product Shell Static Cleanup and Plan/Tools Page Activation

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Fix basedpyright errors in T020 product shell and activate the previously-placeholder Plan/Tools page.

## Changes

### 1. Basedpyright Error Fixes (0 errors)

Fixed 26 errors across 4 files:

- **Qt enum access**: `QtCore.Qt.AlignCenter` → `QtCore.Qt.AlignmentFlag.AlignCenter`, `QtCore.Qt.PointingHandCursor` → `QtCore.Qt.CursorShape.PointingHandCursor`
- **Optional layout items**: `takeAt()` returns `QLayoutItem | None`; added `item is not None` checks before `item.widget()`
- **QWidget dynamic attributes**: Replaced direct `card._value` access with `getattr(card, "_value")`, added `None` checks
- **Uninitialized instance variables**: Added `_un_limitations_label`, `_un_notes_label`, `_un_diagnostics_label`, `_un_why_label`, `_art_summary` to `__init__`
- **Removed unused imports**: `ConceptTraceViewModel`, `EvidencePageViewModel`, `UnknownsPageViewModel`, `OverviewMetrics`, `AgentRuntimePageState` from `product_shell.py`
- **Cleaned up `_gui.py`**: Removed unnecessary `pyright: ignore` comments, kept `reportMissingImports` guard for PySide6 optional dependency

### 2. Plan/Tools Page Activation

- `_update_plan_tools()` now displays actual content instead of `pass`
- Added `self._last_plan_preview_text` to store the most recent plan preview
- When user asks in Agent QA page, plan text is saved and Plan/Tools page shows it
- Empty state: "请先在 Agent 问答页选择建议问题或输入问题，系统会在这里显示只读工具计划。"
- Added `PlanToolsPageState` dataclass and `build_plan_tools_page_state()` builder in `page_view_models.py`

### 3. Tests

- Added 3 new tests for `PlanToolsPageState`:
  - `test_empty_plan` — empty text shows guidance
  - `test_plan_present` — non-empty text passes through
  - `test_plan_format` — verifies safety notes in plan text

## Files

```text
src/fpga_devmind/desktop/product_shell.py      — modified (error fixes + plan activation)
src/fpga_devmind/desktop/page_view_models.py   — modified (PlanToolsPageState + builder)
src/fpga_devmind/desktop/_gui.py               — modified (cleanup)
tests/test_page_view_models.py                 — modified (+3 tests)
docs/desktop-gui-smoke-test.md                 — modified (plan page docs)
docs/tasks/T020-agentscope-product-shell.md    — modified (plan page description)
```

## Test Count

- Before T020a: 437 tests
- T020a adds: 3 tests (PlanToolsPageState)
- Total after T020a: 440 tests

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src basedpyright src/fpga_devmind/desktop/product_shell.py src/fpga_devmind/desktop/page_view_models.py src/fpga_devmind/desktop/_gui.py tests/test_page_view_models.py
```

Results:
- 0 basedpyright errors (297 warnings)
- 440 tests pass
- compileall clean

## Boundaries

- No LLM, no API key, no external API
- No Vivado / synthesis / implementation / bitstream
- No fpga_project_* mutation
- No graph write execution
- No PASS/HOLD/finding/audit
- No Web GUI / Web server
