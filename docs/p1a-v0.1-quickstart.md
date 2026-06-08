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
- uncertainty / known limitations
```

注意：P1a V0.1 的 `flow.mmd` 展示的是 grounded concepts 的 inferred implementation order，不是已证明的 producer/consumer dataflow。

查询不确定项：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-query \
  --artifacts /tmp/fpga_devmind/p1a_fine_cfo_l6 \
  --question "有哪些不确定"
```

## Freshness

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-freshness \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6
```

如果目标源码变化，状态会变为 `stale`。`p1a-query` 会继续显示历史解释，但会先输出 `Freshness Warning`，提醒不要把旧 confirmed claim 当作当前理解。

## P1a+ Agent Dry Run

P1a V0.1 之后已经有一个默认不调用 provider 的 P1a+ Agent dry-run 命令：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6
```

输出：

```text
/tmp/fpga_devmind/p1a_agent_l6/
- agent_trace.json
- prompt_context.json
- provider_call.json
- model_result_normalized.json
- claim_proposals.json
- graph_write_proposal.json
- project_graph_proposed.json
- trace_index_proposed.json
- graph_write_report.json
- grounding_report.json
- answer.md
- p1a_artifacts/
```

注意：默认 mode 是 `deterministic_dry_run_no_llm`。它不调用 LLM provider，不读取 API key，不生成模型语义结论；它只把 P1a evidence shell 包进 TaskPlan / ToolObservation / CandidateClaim / GroundingDiagnostic / answer 的最小 Agent runtime artifact，并生成未来 provider 必须遵守的 prompt context 和 model result validation 产物。

如果需要提前验证模型输出格式，可以传入本地 fixture：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --model-result /tmp/fpga_devmind/model_result_fixture.json
```

该 fixture 只用于 validation，不代表已经接入 provider；未知 evidence id、缺字段、schema/domain 不合格 claim 或无证据高置信 claim 会进入 `model_output_diagnostics`。只要存在 blocking `model_output_diagnostics`，`graph_write_proposal.json` 会设置 `graph_write_blocked=true` 且 `model_claims_to_create=[]`，`trace_index_proposed.json` 也不会包含被拒绝的模型 claim。

也可以使用内置 mock semantic provider 走一条正向模型路径：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --mock-semantic
```

`--mock-semantic` 不调用外部 API。它只从已知 evidence id 中选择一个，生成一个合法 supported model claim，用于验证 validation -> graph_write_proposal -> project_graph_proposed 的正向链路。

## Provider Config Draft

生成真实 provider 接入前的 redacted 配置草案：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli provider-config-draft \
  --provider deepseek \
  --out /tmp/fpga_devmind/provider_config
```

支持 `deepseek`、`glm`、`openai`。该命令不读取 API key 值，不调用外部 API，只写环境变量名称、redaction 规则和默认禁用策略。

显式选择 future external provider 也仍然不会调用 API：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --external-provider deepseek
```

当前该模式会被 `external_provider_disabled` 阻断，并产生 `model_output_blocking_diagnostics`。

即使显式添加 `--allow-external-api`，当前也仍然不会调用外部 API：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --external-provider deepseek \
  --allow-external-api
```

当前结果是 `external_provider_not_implemented`，用于验证真实 provider 接入前的显式门控。该路径同样会阻断 model claim 写图提案。

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

当前价值是把”读懂、建图、解释、可追溯、可查询、可失效”跑通，为后续 LLM/ReAct Agent 层提供可复用底座。

---

## P1b Quickstart

P1b 在 P1a 基础上增加 L5/L6-to-RTL 单概念 trace 能力。它不调用 LLM，不运行 Vivado，不修改目标项目。

### Smoke

```bash
PYTHONPATH=src python3 -m unittest tests.test_p1b -v
```

194 tests (18 P1a + 176 P1b) 应全部通过。

### Run One Concept

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_devmind/p1b_peak_idx
```

输出 6 个 artifact：

```text
/tmp/fpga_devmind/p1b_peak_idx/
├── concept_trace_graph.json
├── concept_trace_index.json
├── concept_trace.md
├── concept_trace.mmd
├── grounding_report.json
└── run_metadata.json
```

### Unknown Concept

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept nonexistent_xyz \
  --out /tmp/fpga_devmind/p1b_unknown
```

期望 `Status: ok`，因为合法 unknown 不产生 blocking diagnostics。graph 中会包含 `N_CONCEPT_nonexistent_xyz` 节点和 `N_RTL_UNKNOWN` 占位节点，edge 端点完整无悬空。

### Artifacts

| Artifact | 内容 |
|---|---|
| `concept_trace_graph.json` | `ConceptTraceGraph`：nodes、edges、mapping_claims、evidence_items、grounding_diagnostics、uncertainty_notes |
| `concept_trace_index.json` | `ConceptTraceIndex`：claim_index、evidence_index、node_index、edge_index、cross_references |
| `concept_trace.md` | Markdown 摘要：Summary、L5/L6 Evidence、RTL Evidence、Mapping Claims、Grounding Diagnostics |
| `concept_trace.mmd` | Mermaid 流程图：`graph TD` 语法，可在支持 Mermaid 的 viewer 中渲染 |
| `grounding_report.json` | T006 grounding checker 输出：blocking/non_blocking diagnostics、summary counts |
| `run_metadata.json` | 运行元数据：elapsed_seconds、status、mapping_claims 数、evidence_items 数、artifact 列表 |

### Boundaries

P1b 不做：

```text
- LLM semantic reasoning
- Full SystemVerilog parser（仅用 regex 行匹配）
- 批量多概念 trace（每次只跑一个 concept）
- 交互式 graph 编辑
- 实时 Mermaid 渲染 viewer
- 跨概念 structural / evolution edge
- AST 级 def-use 或 proven dataflow
- Vivado / synthesis / implementation / bitstream
- 修改任何 fpga_project_* 目标项目
- PASS / HOLD / finding / audit
```

### Next Steps

P1b artifact 就绪后，下一阶段是桌面端 Agent 壳（T008–T010）：

- T008: Artifact viewer contract — 定义壳如何读取 P1a/P1b artifact。
- T009: Desktop app prototype — 最小可运行壳（artifact 目录选择、JSON 树浏览、Markdown 渲染）。
- T010: P1b concept trace view — 在壳中渲染 concept trace（节点、边、claim、diagnostic 高亮）。

约束：不做 Web/Desktop UI（壳层不是 Electron/Qt/Web 应用），而是 Agent runtime shell。
