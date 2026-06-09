# Desktop GUI Smoke Test (T014 / T018 / T019 / T020)

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

推荐浏览顺序：**概览 → 概念追踪 → Agent 问答**

| Bundle | 可查看页面 |
|---|---|
| P1b bundle (`.../p1b`) | 概览、概念追踪、证据、不确定项、Agent 问答、开发者区 |
| Agent Runtime bundle (`.../noop_run`) | 概览、Agent Runtime、Agent 问答 |

左侧导航结构：
- **项目理解**：概览、概念追踪、证据、不确定项
- **Agent**：Agent 问答、Agent Runtime、计划与工具
- **开发者**：Raw Data、Markdown、Diagnostics
- **设置**：项目设置、通用设置

> **注意**: 如果未安装 PySide6，入口点会打印依赖提示并以 exit code 0 退出。这是正常的 fallback 行为。安装后重新执行即可。

## Current GUI Capabilities (T020)

**当前是：**
- FPGA DevMind Desktop Product Shell（AgentScope-style 左侧导航 + 主工作区）
- 左侧导航：项目理解 / Agent / 开发者 / 设置 四大模块
- 概览首页：项目卡、概念卡、指标卡、理解摘要、建议问题、下一步入口
- 概念追踪：三段式自然语言摘要 + 结构化子表
- 证据页：按 L5/L6 / RTL / Bridge 分组展示
- 不确定项：limitations、uncertainty notes、grounding diagnostics、为什么不是 confirmed
- Agent 问答：建议问题、回答、引用证据、限制、计划预览
- Agent Runtime：条件显示（P1b 下显示引导说明）
- 计划与工具：同步显示最近一次 Agent 问答生成的只读计划预览（当前不执行工具、不执行 graph write）
- 开发者区：Raw Data / Markdown / Diagnostics
- 确定性本地查询（9 类问题，中英双语关键词）
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

## 4. 每个页面应看到什么

### 概览（首屏）

- 大标题：FPGA DevMind
- 副标题：FPGA Understanding Agent Shell
- 项目卡：项目路径、bundle 类型、完整性
- 概念卡：concept name `peak_idx`
- 指标卡：Mapping Claims / Evidence Items / RTL Objects / Unknowns
- "当前理解" 自然语言段落
- 建议问题列表（可点击）
- 下一步按钮：查看概念追踪、询问 Agent、查看证据

### 概念追踪

- 顶部：三段式自然语言摘要（L5/L6 代码侧 → 映射声明 → RTL 侧）
- 下方 5 个子表：
  - **Nodes**: 至少包含 `N_CONCEPT_peak_idx` 节点
  - **Edges**: 可能为空或包含 bridge edge
  - **Claims**: 包含 mapping claims
  - **Evidence**: 包含 concept/RTL evidence
  - **Diagnostics**: grounding diagnostics

### 证据

- 按来源分组展示：L5/L6 证据、RTL 证据、桥接/映射证据
- 每组一个表格，显示：Evidence ID、Source、File、Symbol、Strength、Claim Refs

### 不确定项

- Unknown Limitations 列表
- Uncertainty Notes 列表
- Grounding Diagnostics 表格
- "为什么不是 Confirmed" 说明

### Agent 问答

- 建议问题（ pill 按钮）
- 输入框 + Ask 按钮
- 回答区
- 引用的证据
- 限制与不确定
- 计划预览

测试问题：
```
概况
映射
证据
诊断
不确定
节点
边
MC_peak_idx_001
E:p1b_concept:path:1:10:1
```

### Agent Runtime

- P1b bundle 下显示说明：当前是 concept trace artifact，如需查看 runtime 请运行 desktop-sample-run
- agent_runtime bundle 下显示：Summary form、Steps table、Diagnostics table

### 开发者区

- **Raw Data**: JSON artifact 树形浏览
- **Markdown**: concept_trace.md 预览
- **Diagnostics**: bundle 加载诊断

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
