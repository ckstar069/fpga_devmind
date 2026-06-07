# Review Response 0002

本文记录对 [Review 0002](reviews/0002-phase1a-review.md) 的处理决定。

## Summary

评审意见接受。P1a 方向正确，但需要继续收紧成 implementation-ready 规格。

## Accepted Changes

- 将 P1a evidence 和 claim 分为 mandatory / conditional / prohibited。
- 新增 `docs/phase1a-schema.md`。
- 修订 resource refinement confirmed 规则。
- 将 diagnostics → reflection → recheck 写入 P1a 必需循环。
- 新增 coarse_sync L6 专项 checklist。
- 要求 summary 和 Mermaid 图节点/边绑定 claim/evidence。
- 扩展 `extract_python_stage_patterns` 工具输出语义事件。
- 统一 P1a acceptance matrix。

## Decisions

### Explicit Q/interface/pipeline absence

如果 L6 中没有显式 Q format、AXIS/valid-ready 或 pipeline latency，P1a 不失败。Agent 必须输出 `unknown` 或 `not_observed_in_p1a_evidence`，并绑定 evidence search 结果。

### Artifact format

P1a graph artifact 采用 JSON 文件作为第一版落盘格式：

```text
/tmp/fpga_devmind/p1a_coarse_sync_l6/project_graph.json
/tmp/fpga_devmind/p1a_coarse_sync_l6/summary.md
/tmp/fpga_devmind/p1a_coarse_sync_l6/flow.mmd
```

后续可以扩展 JSONL、SQLite 或图数据库，但 P1a 不引入。

### RTL/tests boundary

P1a 默认禁止使用 RTL/tests 生成 confirmed claim。RTL/tests 只能用于：

- 生成 future-entry uncertainty。
- 说明 P1b/P1c 的后续入口。
- 作为 `supported` 以下的弱背景，不得确认 L6 行为。

### Evidence pack clipping

P1a evidence pack 不能截断函数、class、关键公式上下文、Q/width 定义和 import/source-lineage 上下文。具体规则补入 `phase1a-schema.md` 和 `tool-contracts.md`。
