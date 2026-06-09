# T022: Graph-first Concept Understanding + Agent Query Fix

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

T021 made the product shell useful with content. T022 makes the concept understanding experience visual and fixes Agent QA routing for Chinese questions.

No schema changes, no LLM integration, no new backend features.

## Changes

### 1. Fix Chinese Suggested Question Routing (P0)

**Root cause**: Keyword-based routing order was wrong:
- "有什么证据支持这些映射？" contains "映射" → routed to claims instead of evidence
- "节点之间的关系是什么？" contains "节点" → routed to nodes instead of edges
- "这个概念的整体情况如何？" → returned unsupported (missing "概况" keyword)

**Fix**: Reordered checks in `agent_panel_models.py`:
```python
# Summary first (broadest)
if has_any(normalized, ["summary", "概况", "整体情况", ...]):
    return _answer_summary(...)

# Evidence before claims
if has_any(normalized, ["evidence", "证据", "proof"]):
    return _answer_evidence(...)

# Claims after evidence
if has_any(normalized, ["claims", "mapping", "映射", ...]):
    return _answer_claims(...)

# Edges before nodes
if has_any(normalized, ["edges", "edge", "边", "关系"]):
    return _answer_edges(...)
```

Added keywords: "整体情况" for summary, "关系" for edges.

All 6 Chinese suggested questions now route correctly:
- "这个概念的整体情况如何？" → summary
- "有哪些映射声明？可信度如何？" → claims
- "有什么证据支持这些映射？" → evidence
- "有哪些不确定或未确认的部分？" → unknown
- "有哪些诊断信息？" → diagnostics
- "节点之间的关系是什么？" → edges

### 2. Concept Graph View (QGraphicsView/QGraphicsScene)

**New file**: `src/fpga_devmind/desktop/concept_graph_view.py`

View model classes:
- `GraphNode` — node_id, label, kind, stage, confidence, evidence_count, x, y
- `GraphEdge` — edge_id, from_id, to_id, edge_type, confidence
- `ConceptGraphViewModel` — nodes, edges, is_loaded, load_error

Builder:
```python
def build_concept_graph_view_model(bundle: ArtifactBundle) -> ConceptGraphViewModel
```

Renderer:
- `ConceptGraphScene(QGraphicsScene)` — renders nodes as colored ellipses, edges as lines
- Colors by kind: blue (L5/L6), purple (claim/bridge), green (RTL module/always), yellow (RTL signal/assign), red (unknown)
- Edge styles by confidence: solid (supported/confirmed), dash (inferred), dot (unknown)
- Simple three-column layout: L5/L6 (col 0) → mapping (col 1) → RTL (col 2)
- Click handler emits `node_clicked` signal with node details

### 3. Concept Trace Page Reordered (Graph First)

Modified `product_shell.py`:
- Concept Graph section at the top (label "概念图", QGraphicsView, 280px min height)
- Node info label below graph shows clicked node details
- Understanding summary below graph
- Tables (Nodes, Edges, Claims, Evidence, Diagnostics) in sub-tabs at the bottom

### 4. Evidence Page "Why Important" Explanations

Added evidence strength explanation header to evidence page:
```
证据强度说明：
  • strong — 高置信度匹配，可直接支撑 mapping claim
  • medium — 中等置信度，需要额外验证或上下文确认
  • weak — 低置信度，仅供参考，不建议单独作为映射依据
  • unknown — 未评估或无法判断强度

证据越多、越强，mapping claim 的可信度就越高。
```

### 5. Agent Answers Natural Language Templates

All answer builders in `agent_panel_models.py` rewritten with Chinese natural language:

| Kind | Before | After |
|------|--------|-------|
| summary | "## Summary\n- Concept: X\n- Status: ok..." | "概念 'X' 的追踪概况如下：\n当前状态为 ok，共有 N 条映射声明..." |
| claims | "## Mapping Claims\n- MC_001 \| confidence: supported..." | "共有 N 条映射声明：\n• MC_001 — 可信度：supported \| 桥接类型：..." |
| evidence | "## Evidence Items\n- EV_0 \| source: ..." | "共有 N 条证据支持当前概念追踪：\nL5/L6 代码证据 X 条\nRTL 证据 Y 条\n• EV_0 — 来源：..." |
| edges | "## Edges (N)\n- E1 \| A -> B..." | "概念图中共 N 条关系边：\n• E1 — A → B \| 关系类型：..." |
| nodes | "## Nodes (N)\n- N1 \| label: ..." | "概念图中共 N 个节点：\n• N1 — 标签：... \| 类型：..." |
| diagnostics | "## Diagnostics\n- GD_001 \| severity: ..." | "共 N 条诊断信息：\n• GD_001 — 严重级别：..." |
| unknown | "## Unknown / Uncertainty\n### Claims..." | "有 N 条映射声明的可信度为 unknown：\n  • MC_001 — 缺失证据：..." |
| claim_detail | "## Claim: X\n- concept_ref: ..." | "映射声明 X 的详情：\n概念引用：...\n可信度：..." |
| evidence_detail | "## Evidence: X\n- source_type: ..." | "证据 X 的详情：\n来源类型：...\n文件路径：..." |

### 6. Tests

**New test file**: `tests/test_concept_graph_view.py` (9 tests)
- `test_p1b_bundle_loaded`
- `test_nodes_extracted`
- `test_node_fields`
- `test_edges_extracted`
- `test_layout_columns`
- `test_incomplete_bundle`
- `test_non_p1b_bundle`
- `test_graph_node_defaults`
- `test_graph_edge_defaults`

**Updated tests**:
- `tests/test_desktop_agent_panel_models.py` — 4 assertions updated for Chinese natural language output
- `tests/test_agent_panel.py` — verified existing tests still pass with new templates

### 7. Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

Results:
- 463 tests pass
- compileall clean

## Files

```text
src/fpga_devmind/desktop/concept_graph_view.py         — new (graph view model + renderer)
src/fpga_devmind/desktop/agent_panel_models.py         — modified (routing fix + natural language)
src/fpga_devmind/desktop/product_shell.py              — modified (graph view integration + evidence header)
tests/test_concept_graph_view.py                       — new (9 tests)
tests/test_desktop_agent_panel_models.py               — modified (4 assertions updated)
docs/tasks/T022-graph-first-concept-understanding.md   — new (this file)
```

## Test Count

- Before T022: 454 tests
- T022 adds: 9 tests
- Total after T022: 463 tests

## Boundaries

- No LLM, no API key, no external API
- No Vivado / synthesis / implementation / bitstream
- No fpga_project_* mutation
- No graph write execution
- No PASS/HOLD/finding/audit
- No Web GUI / Web server
