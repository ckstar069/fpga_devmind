# Desktop GUI Smoke Test (T014 / T018 / T019)

手工 smoke 文档：验证桌面 GUI 可打开、可加载 bundle、各 tab 可浏览。

## Quick Start (T018)

从零到 GUI 内容的最少步骤。

### 0. 安装桌面依赖

```bash
pip install -e ".[desktop]"
```

### 1. 一键生成 sample artifact

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli desktop-sample-run
```

默认参数：project=`fpga_project_coarse_sync_glm`, concept=`peak_idx`, question=`summary`, out=`/tmp/fpga_devmind/desktop_sample`。

期望输出包含：
- `P1b bundle:   /tmp/fpga_devmind/desktop_sample/p1b`
- `No-op bundle: /tmp/fpga_devmind/desktop_sample/noop_run`

### 2. 启动 GUI

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```

或直接指定 bundle：

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app \
  --artifact-dir /tmp/fpga_devmind/desktop_sample/p1b
```

### 3. 观察结果

推荐浏览顺序：**Overview → Concept Understanding → Agent**

| Bundle | 可查看 Tab |
|---|---|
| P1b bundle (`.../p1b`) | Overview, Concept Understanding, Agent, Markdown, Diagnostics, Developer |
| Agent Runtime bundle (`.../noop_run`) | Overview, Agent Runtime (自动启用) |

> **注意**: 如果未安装 PySide6，入口点会打印依赖提示并以 exit code 0 退出。这是正常的 fallback 行为。安装后重新执行即可。

## Current GUI Capabilities (T019)

**当前是：**
- FPGA Understanding Agent Shell（用户可理解的概览 + 交互式查询）
- Overview 首屏：自动生成人类可读的概念理解摘要、证据概览、映射可信度
- Concept Understanding：三段式自然语言摘要（L5/L6 侧 → 映射声明 → RTL 侧）+ 结构化表格
- Agent 查询面板：中文建议问题 + 确定性本地查询（9 类问题，中英双语关键词）
- Read-only tool plan preview（展示未来 Agent 模式需要读取什么）
- No-op runtime trace viewer（observe→plan→propose→result→answer→graph-write 时间线）
- 一键 sample 生成（`desktop-sample-run` CLI 子命令）

**还不是：**
- Real LLM Agent
- 自动开发 FPGA 的 Agent
- 可修改工程/graph 的工具
- Vivado wrapper
- 审计器 / PASS/HOLD
- Web GUI / Web server
- Multi-turn ReAct loop

## 详细 Smoke 步骤

以下步骤覆盖每个 Tab 的详细验证。

### 1. 安装 PySide6

```bash
cd /path/to/fpga_devmind
pip install -e ".[desktop]"
```

或直接安装：

```bash
pip3 install pyside6
```

## 2. 生成 P1b Artifact

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_devmind/p1b_peak_idx
```

期望：`Status: ok`，6 个 artifact 写入 `/tmp/fpga_devmind/p1b_peak_idx`。

## 3. 启动 Desktop Shell

方式一 — 直接指定 artifact 目录：

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app \
  --artifact-dir /tmp/fpga_devmind/p1b_peak_idx
```

方式二 — 自动选择最近的 bundle：

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```

方式三 — 先启动再手动选择：

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app
```

然后在 GUI 顶部的输入框输入路径或点击 Browse...。

## 4. 每个 Tab 应看到什么

### Overview（首屏）

- 显示概念名 `peak_idx`、bundle 类型 `p1b`、项目路径
- "当前理解" 自然语言段落：节点数、映射声明数、证据数
- 证据概览表格：L5/L6 证据和 RTL 证据的强/中/弱/未知分布
- 映射可信度：supported/inferred/unknown 计数
- 不确定与限制：列表（如有）
- 状态："正常，无阻断性诊断"

### Concept Understanding

- 顶部：三段式自然语言摘要（L5/L6 代码侧 → 映射声明 → RTL 侧）
- 下方 5 个子表（与之前 Concept Trace 相同）：
  - **Nodes**: 至少包含 `N_CONCEPT_peak_idx` 节点
  - **Edges**: 可能为空或包含 bridge edge
  - **Claims**: 包含 mapping claims
  - **Evidence**: 包含 concept/RTL evidence
  - **Diagnostics**: grounding diagnostics

### Agent

- 顶部显示建议问题列表（中文）
- 在输入框输入 `summary` 或 `概况`，点击 Ask
- **Answer** 区域应显示 concept summary
- **Plan Preview** 区域应显示只读工具计划预览（intent, steps, safety notes）

测试其他问题：
```
映射
证据
诊断
不确定
节点
边
MC_peak_idx_001
E:p1b_concept:path:1:10:1
```

每种问题都应返回非空 answer 和 plan preview。

### Markdown

- 显示 `concept_trace.md` 的内容

### Diagnostics

- 如果 bundle 完整，显示 "✓ 无诊断信息 — bundle 完整。"
- 如果 bundle 不完整，显示 missing/error 诊断

### Developer（原 JSON Tree）

- 下拉框应列出 JSON artifact（concept_trace_graph.json, concept_trace_index.json 等）
- 选择后显示树形结构

## 5. Agent No-op Dry Run（CLI）

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli agent-noop-run \
  --artifact-dir /tmp/fpga_devmind/p1b_peak_idx \
  --question "summary" \
  --out /tmp/fpga_devmind/noop_run
```

期望输出：
- `/tmp/fpga_devmind/noop_run/agent_runtime_trace.json`
- `/tmp/fpga_devmind/noop_run/answer.md`
- Console 显示 status, task_id, confidence

## 6. Agent Runtime Trace Tab（T017）

加载 agent runtime bundle 后查看结构化 trace：

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app \
  --artifact-dir /tmp/fpga_devmind/noop_run
```

或使用 `--recent` 自动选择：

```bash
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```

### Agent Runtime Tab 应看到什么

- Tab 自动启用（非 agent_runtime bundle 时禁用）
- **Summary form**: Schema Version, Task ID, Question, Bundle Type, Concept, Constraints, 各 section counts
- **Steps table**: 按 section 排列的 trace 时间线（task → observation → reasoning → plan → proposal → result → answer → graph_write）
  - 每行显示 Section, ID, Title, Status, Summary, References
  - Graph Write Proposal 的 Status 应显示 "blocked"（T016 no-op 生成的全部 blocked）或 "allowed"（仅表示 viewer 能显示未来 schema-compatible trace，当前 Agent Shell 不执行写图，不修改 graph 或目标项目），绝无 PASS/HOLD
- **Diagnostics table**: runtime_diagnostics 中的条目（Severity, Message）

## 7. 安全边界确认

- GUI 只读浏览 artifact，不写入 artifact 目录
- 不读取 fpga_project_* 源码
- 不运行 Vivado
- 不加载 API key
- 不调用外部 LLM
- Plan Preview 不提供执行按钮

## 8. --recent 无 bundle 时的行为

```bash
# 确保 /tmp/fpga_devmind 下无 bundle
PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent
```

期望：打印 "No artifact bundles found" 提示，exit 0。
