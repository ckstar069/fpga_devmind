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

## Desktop Shell (T009–T012)

PySide6 桌面 Agent Shell 用于浏览 P1a/P1b artifact bundle。

- **V0.1 Readiness Review** (T009–T010): `docs/reviews/0007-p1b-desktop-v0.1-readiness-review.md`
- **V0.2 Readiness Review** (T011–T012a): `docs/reviews/0008-desktop-agent-shell-v0.2-readiness-review.md` — Desktop Agent Shell 已从 artifact viewer 进化到本地确定性 Agent shell 原型。结论: READY WITH LIMITATIONS。推荐下一步: T015 Agent Runtime Contract。

### 依赖

```bash
pip install -e ".[desktop]"
```

或直接安装：

```bash
pip3 install pyside6
```

如果未安装，入口点会打印依赖提示（包含 `pip install -e ".[desktop]"` 命令）并以 exit code 0 退出。

### 启动

```bash
# 直接指定 artifact 目录
PYTHONPATH=src python3 -m fpga_devmind.desktop_app \
  --artifact-dir /tmp/fpga_devmind/p1b_peak_idx

# 自动选择最近的 bundle
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent

# 或先启动再手动选择目录
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
```

### 视图

| Tab | 内容 |
|---|---|
| **Run Summary** | concept, status, claims, evidence, elapsed time |
| **JSON Tree** | 任意 JSON artifact 的树形浏览（graph, index, grounding, metadata） |
| **Markdown** | concept_trace.md 只读预览（fallback 到 .mmd） |
| **Diagnostics** | bundle 加载时的 missing/load_error 诊断 |
| **Concept Trace** | P1b 结构化表格：Nodes / Edges / Claims / Evidence / Diagnostics |
| **Agent** | T011 本地确定性查询 + T012 只读工具计划预览 |
| **Agent Runtime** | T017 Agent Runtime Trace 结构化浏览（Summary + Steps + Diagnostics） |

### Concept Trace 子表

- **Nodes**: node_id, label, kind, stage, confidence, evidence count, diagnostics flag
- **Edges**: edge_id, from→to label, type, confidence, claim refs
- **Claims**: claim_id, concept, confidence, bridge_kind, evidence counts, missing evidence, diagnostics
- **Evidence**: evidence_id, source_type, file, symbol, strength, claim refs
- **Diagnostics**: id, severity, issue_type, target claim, message, action

### Agent Tab（T011 + T012）

- **Answer**（T011）：用户输入问题后，系统基于当前已加载的 P1a/P1b bundle 做本地确定性查询并返回答案。支持 summary、claims、evidence、diagnostics、unknown、nodes、edges、claim_detail、evidence_detail 共 9 类问题类型，中英双语关键词匹配。不调用外部 LLM。
- **Plan Preview**（T012）：同时展示只读工具计划预览，说明如果未来进入 Agent 模式，需要读取哪些 artifact、为什么需要这些证据。不执行工具，不提供执行按钮，不调用 LLM。

### 安全边界

```text
- 只读 artifact viewer，不写入 artifact 目录。
- 不读取 fpga_project_* 源码。
- 不运行 Vivado / synthesis / implementation / bitstream。
- 不加载 API key，不调用外部 LLM。
- unknown confidence 正常展示，不标记为错误。
- blocking diagnostic 是 overclaim warning，不是 PASS/HOLD 结果。
- Plan Preview 是纯文本展示，不提供执行按钮。
```

## V0.1 完整边界

P1b + Desktop Shell V0.1 不做：

```text
- LLM semantic reasoning / provider-backed model calls
- Multi-turn ReAct loop 或 Agent chat 面板
- Full SystemVerilog parser（regex-only RTL scanning）
- 批量多概念 trace（单次仅一个 concept）
- 交互式 graph 编辑或 claim 修改
- 图布局引擎 / 实时 Mermaid 渲染
- 跨概念 structural / evolution edge
- AST 级 def-use 或 proven dataflow
- Vivado / synthesis / implementation / bitstream
- 修改任何 fpga_project_* 目标项目
- PASS / HOLD / finding / audit
- Web GUI / Web server / browser URL
```

## 下一阶段

### 已完成

- ✅ T011: Agent interaction panel — 查询输入、响应展示、工具建议（只读）。详见 `docs/tasks/T011-desktop-local-agent-panel.md`。
- ✅ T012: Agent Tool Plan Preview — 只读工具计划预览。详见 `docs/tasks/T012-agent-tool-plan-preview.md`。
- ✅ T012a: Import cycle / helper cleanup。
- ✅ T013: Desktop Agent Shell V0.2 Readiness Review — 结论: READY WITH LIMITATIONS。详见 `docs/reviews/0008-desktop-agent-shell-v0.2-readiness-review.md`。
- ✅ T015: Agent Runtime Contract — 9 dataclasses + validate_runtime_trace，schema `agent-runtime-contract-0.1`。详见 `docs/tasks/T015-agent-runtime-contract.md`。
- ✅ T015a: Strengthen cross-reference validation — ToolPlan.steps task_id check, ToolResult.proposal_id existence, Answer limitations auto-ensure。68 tests。361 total。
- ✅ T016: Local No-op ReAct Dry Run — 确定性单轮 Agent runtime，串联 T011/T012/T015 输出 contract-backed trace。19 tests。380 total。
- ✅ T014: Desktop Shell Usability Hardening — PySide6 可选依赖、sample artifact 发现、`--recent` 标志、GUI 空状态改善、手工 smoke 文档。6 tests。387 total。
- ✅ T017: Desktop Agent Runtime Trace Viewer — GUI 读取并展示 `agent_runtime_trace.json` 的结构化 trace。Summary form + Steps 时间线 + Diagnostics 表格。14 tests。401 total。

### Agent No-op Dry Run

T016 是第一个基于 Agent Runtime Contract 的本地确定性 Agent dry run。它把 T011（查询）+ T012（计划预览）+ T015（contract）串成一条 observe→plan→propose→simulated-result→answer→blocked-graph-write trace。

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli agent-noop-run \
  --artifact-dir /tmp/fpga_devmind/p1b_peak_idx \
  --question "summary" \
  --out /tmp/fpga_devmind/noop_run
```

输出：

```text
/tmp/fpga_devmind/noop_run/
- agent_runtime_trace.json   # 完整 contract-backed Agent trace
- answer.md                  # 人类可读答案
```

不调用 LLM，不调用外部 API，不执行工具，不修改目标项目，所有 graph write 都 blocked by default。

### 推荐下一步: Real LLM Provider Integration

### 后续阶段

- **T017** ✅: Desktop Agent Runtime Trace Viewer — 在 GUI 中渲染 `agent_runtime_trace.json`。已完成。
- **真实 LLM provider integration** 是推荐下一步。
- P1b+: 批量多概念 trace、partial SystemVerilog parser、跨概念 structural edge。
- P1c: Verification coverage trace。
