# T011: Local Agent Interaction Panel

## Objective

在 PySide6 Desktop Shell 中新增一个 **Agent** tab，让用户可以输入问题，系统基于当前已加载的 artifact bundle（P1a/P1b）做本地确定性/规则化查询并返回答案。

**硬约束：**
- 不调用外部 LLM（无 provider、无 API key、无网络请求）。
- 不启动 Web server。
- 不修改目标项目。
- 不生成 PASS/HOLD/finding/audit 语义。
- unknown confidence 正常展示，不标记为错误。

## Approach

### 1. View Model 层

**文件：** `src/fpga_devmind/desktop/agent_panel_models.py`

- `AgentPanelResponse` dataclass：
  - `question`, `answer_text`, `response_kind`
  - `referenced_claim_ids`, `referenced_evidence_ids`, `referenced_node_ids`, `referenced_diagnostic_ids`
  - `uncertainty_notes`, `unsupported_reason`
  - `is_loaded`, `load_error`

- `query_artifact_bundle(bundle, question)` 工厂函数：
  - 永不抛异常；所有错误返回 `is_loaded=False`。
  - 仅对 P1a/P1b bundle 生效。
  - 先尝试提取 `MC_*` claim ID 和 `E:*` evidence ID（大小写不敏感）。
  - 再按关键词子串匹配路由到 9 种回答器：
    - `summary` / `概况` / `做了什么`
    - `claims` / `映射` / `mapping`
    - `evidence` / `证据`
    - `diagnostics` / `grounding` / `诊断`
    - `unknown` / `不确定` / `uncertainty`
    - `nodes` / `节点`
    - `edges` / `边`
    - claim detail（`MC_*` 匹配）
    - evidence detail（`E:*` 匹配）
  - 无法识别的问题返回 `response_kind="unsupported"`，并明确说明不调用 LLM。

- 所有回答器直接读取 `graph` / `index` / `grounding` / `meta`，引用实际 artifact 数据，不编造。

### 2. GUI 层

**文件：** `src/fpga_devmind/desktop/_gui.py`

在 `MainWindow.__init__` 中新增 **Agent** tab（位于 Concept Trace 之后）：
- 输入行：`QHBoxLayout(QLineEdit + QPushButton("Ask"))`
- 回答区：`QPlainTextEdit(readOnly=True)`
- `_on_agent_ask()` slot：
  1. 读取 `QLineEdit` 文本。
  2. 调用 `query_artifact_bundle(self._bundle, question)`。
  3. 将 `answer_text` 和引用列表写入 `QPlainTextEdit`。

### 3. 测试

**文件：** `tests/test_desktop_agent_panel_models.py`

35 个测试，覆盖：
- 不完整 bundle 与非 P1a/P1b bundle 的降级处理
- summary / claims / evidence / diagnostics / unknown / nodes / edges 8 类问题（含中文）
- 特定 claim ID 与 evidence ID 查询（命中与缺失）
- unsupported 问题与空问题
- unknown confidence 不呈现为 pass/fail/error
- 所有回答均引用实际 artifact 数据

### 4. 文档

- `docs/tasks/T011-desktop-local-agent-panel.md`（本文件）
- `docs/implementation-status.md` 更新 T011 完成状态

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
```

## 安全边界

```text
- 只读 artifact viewer，不写入 artifact 目录。
- 不读取 fpga_project_* 源码。
- 不运行 Vivado / synthesis / implementation / bitstream。
- 不加载 API key，不调用外部 LLM。
- unknown confidence 正常展示，不标记为错误。
- blocking diagnostic 是 overclaim warning，不是 PASS/HOLD 结果。
```
