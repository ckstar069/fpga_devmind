# T021: Make Product Shell Actually Useful

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

T020/T020a built the product shell structure, but the core pages had little usable content. T021 fixes this by making Overview, Agent QA, Concept Trace, Evidence, and Agent Runtime pages actually display meaningful, readable content.

No schema changes, no LLM integration, no new backend features.

## Changes

### 1. Fix Overview Empty "Current Understanding" (P0)

**Root cause**: Evidence `source_type` in real bundles is `concept_occurrence` / `rtl_source`, but code checked for `startswith("p1b_concept")` / `startswith("p1b_rtl")`. This caused:
- L5/L6 evidence count to be 0 in Overview
- Concept trace summary L5/L6 section to be empty
- Evidence page grouping to misclassify all evidence as RTL

**Fix**: Updated source_type classification in three files:
- `overview_models.py`: `_build_p1b_overview()` and `format_concept_trace_summary()`
- `page_view_models.py`: `build_evidence_page_view_model()`
- `trace_view_models.py`: L5/L6 and RTL classification in `format_concept_trace_summary()`

Now supports both old (`p1b_concept`, `p1b_rtl`) and new (`concept_occurrence`, `rtl_source`) source types.

**Enhanced current_understanding text**: Rewrote to include:
- L5/L6 side: files and symbols found
- RTL side: Verilog files and module/signal/always counts
- Mapping claims with confidence, bridge_kind, evidence counts
- Evidence totals split by L5/L6 vs RTL
- Why not confirmed explanation
- Status note

Example output for peak_idx:
```
概念 'peak_idx' 在 L5/L6 Python 代码和 RTL Verilog 之间建立了映射追踪。

L5/L6 侧：在 3 个源码文件中发现 12 个相关符号，包括 CFOFixedStage, CFOOptimized, CoarseSyncPipelineL5, CoarseSyncPipelineL6, SmoothDetectFixedStage, SmoothDetectOptimized, __init__, _empty_result 等 12 个符号。
RTL 侧：在 3 个 Verilog 文件中发现 12 个相关模块/信号/always/assign。

映射声明：
  MC_peak_idx_001 — 可信度 supported，桥接类型 calculation_role（L5/L6 证据 20 条，RTL 证据 12 条）

证据统计：共 32 条（L5/L6 20 条，RTL 12 条）。

当前 mapping claims 未标记为 confirmed。原因：证据强度不足（命名匹配 alone 只能得到 inferred）；需要人工 review 后才能提升到 supported 或 confirmed。

状态：正常，无阻断性诊断。
```

### 2. Metric Cards with Descriptions

`_make_metric_card()` now accepts a `description` parameter. Each metric card shows:
- **Mapping Claims**: "L5/L6 与 RTL 的映射声明"
- **Evidence Items**: "支持理解的源码/RTL 证据"
- **RTL Objects**: "相关 RTL module/signal/always/assign"
- **Unknowns**: "不确定或缺失证据项"

### 3. Suggested Questions → Clickable Entry

Already implemented in T020 (`_go_to_agent_with_question()`). Verified working:
- Click suggestion → navigates to Agent QA page
- Auto-fills question
- Auto-triggers Ask
- Displays Answer / Evidence / Limitations / Plan Preview

### 4. Agent QA Page Usability

Added a prominent note at the top:
> "当前为本地确定性 Agent，基于已加载的 artifact 做规则化查询，不调用外部 LLM / API。"

Styled with light blue background and border for visibility.

### 5. Concept Trace Summary Enhanced

`format_concept_trace_summary()` now properly classifies evidence by source_type and produces:
- L5/L6 section with files, symbols, strength counts
- Mapping claims with confidence (Chinese translation), bridge_kind, missing evidence
- RTL section with files and evidence types

### 6. Evidence Page with Group Descriptions

Each evidence group now has a description label:
- **L5/L6 代码证据**: "从 L5/L6 Python 代码中提取的符号、类、函数、方法等证据项。"
- **RTL 证据**: "从 RTL Verilog/SystemVerilog 中提取的模块、信号、always、assign 等证据项。"
- **桥接/映射证据**: "连接 L5/L6 和 RTL 两边的桥接证据项。"

Empty groups show "当前没有该类证据。" instead of blank.

### 7. Top Bar Path Display

`_update_top_bar()` now updates `_dir_input` to show the current artifact directory (truncated to 45 chars). Users can see what bundle is loaded.

### 8. Agent Runtime Page Enhanced

`build_agent_runtime_page_state()` now detects if `noop_run` exists in the same parent directory and includes its path in the message for P1b bundles.

### 9. Tests

**New test file**: `tests/test_agent_panel.py` (10 tests)
- `test_summary_answer_not_empty`
- `test_claims_answer_not_empty`
- `test_evidence_answer_not_empty`
- `test_diagnostics_answer_not_empty`
- `test_nodes_answer_not_empty`
- `test_edges_answer_not_empty`
- `test_unknown_answer_not_empty`
- `test_no_bundle_shows_error`
- `test_unsupported_question`
- `test_evidence_with_new_source_types`

**Updated tests**:
- `tests/test_overview_models.py`: +4 tests for current_understanding content (L5/L6 side, RTL side, mapping claims, why-not-confirmed)

## Files

```text
src/fpga_devmind/desktop/overview_models.py         — modified (source_type fix + enhanced understanding)
src/fpga_devmind/desktop/page_view_models.py        — modified (source_type fix + noop path detection)
src/fpga_devmind/desktop/trace_view_models.py       — modified (source_type fix)
src/fpga_devmind/desktop/product_shell.py           — modified (UI improvements)
tests/test_overview_models.py                       — modified (+4 tests)
tests/test_agent_panel.py                           — new (10 tests)
docs/tasks/T021-make-product-shell-actually-useful.md — new (this file)
```

## Test Count

- Before T021: 440 tests
- T021 adds: 14 tests (4 overview + 10 agent panel)
- Total after T021: 454 tests

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src basedpyright src/fpga_devmind/desktop/product_shell.py src/fpga_devmind/desktop/page_view_models.py src/fpga_devmind/desktop/overview_models.py src/fpga_devmind/desktop/_gui.py tests/test_page_view_models.py tests/test_overview_models.py tests/test_agent_panel.py
```

Results:
- 0 basedpyright errors (408 warnings)
- 454 tests pass
- compileall clean

## Boundaries

- No LLM, no API key, no external API
- No Vivado / synthesis / implementation / bitstream
- No fpga_project_* mutation
- No graph write execution
- No PASS/HOLD/finding/audit
- No Web GUI / Web server
