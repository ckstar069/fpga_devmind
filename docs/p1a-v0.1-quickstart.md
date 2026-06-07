# P1a V0.1 Quickstart

P1a V0.1 是 `fpga_devmind` 的第一个可试用理解层原型。它不是完整 Agent，也不是审计工具；它用于验证：

```text
read L6 evidence -> build ProjectGraph -> build TraceIndex -> render summary/inferred flow -> answer grounded queries -> check freshness
```

## Smoke Check

运行两个只读样本：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-smoke \
  --out-root /tmp/fpga_devmind/p1a_smoke
```

输出：

```text
/tmp/fpga_devmind/p1a_smoke/
- smoke_report.json
- smoke_report.md
- coarse_sync_glm_l6/
- fine_cfo_l6/
```

期望结果：

```text
coarse_sync_glm_l6: passed
fine_cfo_l6: passed
blocking_diagnostics: 0
freshness: current
```

## Run One Project

主样例：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --out /tmp/fpga_devmind/p1a_coarse_sync_l6
```

Smoke 样例：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_fine_cfo \
  --stage L6_resource_opt \
  --out /tmp/fpga_devmind/p1a_fine_cfo_l6
```

## Artifacts

每次运行生成：

```text
project_graph.json
trace_index.json
memory_manifest.json
summary.md
flow.mmd
trace.md
run_metadata.json
```

用途：

```text
project_graph.json
  主结构化语义图。

trace_index.json
  claim/spec/evidence 反向索引。

memory_manifest.json
  源文件 hash 快照，用于 freshness check。

summary.md
  从图谱渲染的人类摘要。

flow.mmd
  Mermaid 主流程图。

trace.md
  claim 到源码证据的可读追踪视图。
```

## Query

示例：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-query \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6 \
  --question "L6 实现了什么流程"
```

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-query \
  --artifacts /tmp/fpga_devmind/p1a_fine_cfo_l6 \
  --question "资源估计 LUT DSP BRAM 来自哪里"
```

支持：

```text
- stage flow
- fixed-point / Q format
- stream interface
- pipeline timing
- resource estimates
- claim id drill-down, such as C001
- evidence id drill-down
```

注意：P1a V0.1 的 `flow.mmd` 展示的是 grounded concepts 的 inferred implementation order，不是已证明的 producer/consumer dataflow。

## Freshness

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-freshness \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6
```

如果目标源码变化，状态会变为 `stale`。`p1a-query` 会继续显示历史解释，但会先输出 `Freshness Warning`，提醒不要把旧 confirmed claim 当作当前理解。

## Boundaries

P1a V0.1 不做：

```text
- Vivado / synthesis / implementation / bitstream
- 修改任何 fpga_project_* 目标项目
- PASS / HOLD
- finding / audit
- L6-to-RTL mapping
- verification coverage
- LLM semantic reasoning
- proven dataflow extraction
```

当前价值是把“读懂、建图、解释、可追溯、可查询、可失效”跑通，为后续 LLM/ReAct Agent 层提供可复用底座。
