# T012: Agent Tool Plan Preview

## Objective

在 Desktop Agent Shell 的 Agent tab 中增加一个只读的 **Tool Plan Preview** 区域。当用户提出问题时，除了返回确定性答案（T011），还展示一个“如果未来进入 Agent 模式，需要查看哪些 artifact、调用哪些本地只读能力”的计划预览。

**注意：** T012 仍然不是 ReAct 循环，不调用 LLM，不执行工具，不修改目标项目，不运行 Vivado。它只是“计划预览/下一步建议”，用于建立 Agent 机制骨架。

## Approach

### 1. View Model 层

**文件：** `src/fpga_devmind/desktop/agent_plan_models.py`

- `AgentPlanStep` dataclass：
  - `step_id`, `title`, `rationale`
  - `read_artifacts` — 本步需要读取的 artifact 文件名
  - `referenced_claim_ids`, `referenced_evidence_ids`, `referenced_node_ids`, `referenced_diagnostic_ids`
  - `allowed_action` 固定 `"read_only_preview"`
  - `is_executable_now` 固定 `False`

- `AgentPlanPreview` dataclass：
  - `question`, `intent`, `steps`, `safety_notes`, `unsupported_reason`

- `build_agent_plan_preview(bundle, question, response=None)` 工厂函数：
  - 永不抛异常；所有错误返回 `is_loaded=False`。
  - 仅对 P1a/P1b bundle 生效。
  - 与 T011 使用相同的关键词路由（summary、claims、evidence、diagnostics、unknown、nodes、edges、claim_detail、evidence_detail、unsupported）。
  - 每个 intent 对应一组 `AgentPlanStep`，说明需要读取哪些 artifact 以及为什么。
  - `response` 参数可选：如果传入 T011 的 `AgentPanelResponse`，plan steps 会继承其中引用的 claim/evidence/node/diagnostic IDs。

### 2. GUI 层

**文件：** `src/fpga_devmind/desktop/_gui.py`

在 Agent tab 的 Answer 输出下方新增 **Plan Preview** 区域：
- `QPlainTextEdit(readOnly=True)`
- 用户点击 Ask 后，同时更新 answer 和 plan preview。
- Plan Preview 展示：
  - Intent
  - Steps（含 rationale、read artifacts、referenced IDs、action 类型、executable 状态）
  - Safety Notes

### 3. 安全边界（Safety Notes）

每个 plan preview 都包含固定的 safety notes：
- read-only artifact query — no write to artifact directory
- no external LLM / API call
- no API key loading
- no Vivado / synthesis / implementation / bitstream
- no mutation to fpga_project_* target projects
- this is a preview plan; steps are not executed automatically

### 4. 计划类型覆盖

| Intent | Steps |
|---|---|
| summary | Read run_metadata → Read concept_trace_graph → Read grounding_report |
| claims | Read concept_trace_graph → (optional) Read concept_trace_index |
| evidence | Read concept_trace_graph → (optional) Read concept_trace_index |
| diagnostics | Read concept_trace_graph → Read grounding_report → Merge/deduplicate |
| unknown | Read concept_trace_graph → Inspect required_missing_evidence |
| nodes | Read concept_trace_graph |
| edges | Read concept_trace_graph |
| claim_detail | Read concept_trace_graph → (optional) Read concept_trace_index → (optional) Read grounding diagnostics |
| evidence_detail | Read concept_trace_graph → (optional) Read concept_trace_index |
| unsupported | No steps generated |

### 5. 测试

**文件：** `tests/test_desktop_agent_plan_models.py`

19 个测试，覆盖：
- 不完整 bundle 与非 P1a/P1b bundle 的降级处理
- 9 类 intent 各至少一个测试（summary、claims、evidence、diagnostics、unknown、nodes、edges、claim_detail、evidence_detail）
- unsupported 不生成可执行步骤
- safety notes 始终存在且包含 read-only / no external LLM 字样
- claim_detail / evidence_detail 继承 response 中的 referenced IDs
- 所有 step 的 `is_executable_now=False` 和 `allowed_action="read_only_preview"`

### 6. 文档

- `docs/tasks/T012-agent-tool-plan-preview.md`（本文件）
- `docs/implementation-status.md` 更新 T012 完成状态
- `docs/p1a-v0.1-quickstart.md` 更新 Desktop Agent Shell 小节

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
```

## 安全边界

```text
- 只读 artifact preview，不写入 artifact 目录。
- 不读取 fpga_project_* 源码。
- 不运行 Vivado / synthesis / implementation / bitstream。
- 不加载 API key，不调用外部 LLM。
- unknown confidence 正常展示，不标记为错误。
- blocking diagnostic 是 overclaim warning，不是 PASS/HOLD 结果。
- Plan Preview 是纯文本展示，不提供执行按钮。
```
