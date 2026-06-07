# Desktop UI Plan

`fpga_devmind` 的图形界面目标是桌面端 Agent 软件，不做 Web GUI 实施路线。

桌面端是完整产品 shell：

```text
fpga_devmind Desktop Agent
  -> macOS / Linux first
  -> Windows second
  -> local project workspace
  -> local artifacts and semantic memory
  -> graph / evidence / source navigation
  -> Agent interaction and follow-up questions
```

UI 不是语义事实来源。UI 展示 Agent 产出的结构化 artifact、语义图、证据、诊断和不确定项；真正的语义理解来自 Agent runtime、Evidence Collector、Semantic Reasoner、Grounding Checker 和 Semantic Graph Store。

## Why Desktop Only

FPGA Agent 需要完整本地能力：

```text
- 打开本地 FPGA project workspace
- 读取本地源码和生成 artifact
- 管理语义记忆和 freshness
- 关联 ai_project_template 的本地阶段推进
- 后续承载安全受控的工具调用和 Agent 工作流
- 提供稳定的用户交互状态
```

Web GUI 无法保证这些能力都能完整、稳定、可控地实现，因此不作为本项目实施目标。

## First Desktop Prototype

第一个桌面原型应是只读 artifact viewer + Agent interaction shell 的雏形：

```text
- artifact directory selector
- loaded project / stage / concept metadata
- graph visualization
- claim list grouped by confidence
- evidence list
- selected claim -> evidence refs
- selected evidence -> file path and line range
- grounding diagnostics
- uncertainty notes
- generated markdown preview
- raw JSON inspection
```

它可以先只读取 P1a / P1a+ / P1b artifacts，但布局和状态管理应为后续 Agent 追问留出空间。

## Non-Goals

第一版桌面 UI 不做：

```text
- 修改 fpga_project_* 目标项目
- 运行 Vivado
- 运行 synthesis / implementation / bitstream
- 调用真实 provider API
- API key 配置界面
- PASS/HOLD dashboard
- audit finding workflow
- graph editing as source of truth
```

## Suggested Technology

优先考虑能长期支撑桌面 Agent 的方案：

```text
Tauri
  Preferred for macOS / Linux first if adding Rust shell is acceptable.

Electron
  Acceptable if implementation speed and UI ecosystem matter more than app size.

Native Python desktop shell
  Acceptable only for a minimal artifact browser, but likely weaker for rich graph UI and long-term Agent interaction.
```

技术选择必须服务于桌面端 Agent，不应为了快速展示而变成一次性 Web demo。

## Information Architecture

First screen:

```text
Top bar
  workspace / artifact directory selector
  freshness status
  current workflow status

Left pane
  projects / stages / concepts
  claims
  evidence ids
  uncertainty notes

Center pane
  graph visualization
  concept trace / stage flow

Right pane
  selected claim / evidence / diagnostic detail
  source location and excerpt

Bottom or secondary tab
  Agent trace
  generated markdown preview
  raw JSON
```

## Artifact Contract

The desktop UI should support these artifact groups:

```text
P1a:
  project_graph.json
  trace_index.json
  summary.md
  flow.mmd
  trace.md
  memory_manifest.json

P1a+:
  agent_trace.json
  prompt_context.json
  provider_call.json
  project_graph_proposed.json
  trace_index_proposed.json
  graph_write_report.json
  grounding_report.json
  answer.md

P1b:
  concept_trace_graph.json
  concept_trace_index.json
  concept_trace.md
  concept_trace.mmd
  grounding_report.json
  run_metadata.json
```

Missing artifacts must produce explicit UI diagnostics.

## Safety Rules

The desktop app may read:

```text
/tmp/fpga_devmind/**
/private/tmp/fpga_devmind/**
explicit user-selected artifact directories
explicit user-selected project workspaces, read-only in first version
```

The desktop app must not write into:

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
any path component beginning with fpga_project_
```

The first desktop UI is read-only.

## Acceptance

The desktop prototype is acceptable when:

```text
- macOS app can open a synthetic artifact directory.
- Linux path is documented and at least dev-mode runnable.
- Windows is documented as secondary and may be deferred.
- it can open generated P1a artifacts.
- it can open generated P1a+ artifacts.
- after P1b exists, it can open P1b concept trace artifacts.
- graph renders nonblank.
- selecting a claim shows evidence ids.
- selecting evidence shows file path and line range.
- grounding diagnostics are visible.
- inferred / unknown / conflicted states are visually distinct.
- missing artifact states are handled.
- no target project files are modified.
```

## Review Gate

Before treating the desktop UI as usable, run a review focused on:

```text
- whether displayed facts are artifact-grounded
- whether uncertainty is visible
- whether the UI encourages unsupported conclusions
- whether it remains read-only
- whether text and graph layout are usable on desktop
- whether it remains aligned with Agent workflow rather than becoming a static report viewer
```
