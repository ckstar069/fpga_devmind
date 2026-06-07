# Product Target

`fpga_devmind` 的最终目标是一个 FPGA 开发-理解一体 Agent 软件。它不是传统静态分析器、审计检查器、报告生成器，也不是只会打开 JSON artifact 的普通 Web 工具。

## Final Product Form

最终完整形态应是桌面端 Agent 软件：

```text
fpga_devmind Desktop Agent
  -> macOS / Linux first
  -> Windows second
  -> local project access
  -> local semantic memory
  -> graph / evidence / source navigation
  -> Agent planning, reading, reasoning, reflection and follow-up questions
```

Web GUI 不作为当前实施目标。

桌面端是完整产品形态，因为 FPGA Agent 需要长期支持：

```text
- 本地工程目录访问
- 本地 artifact / semantic memory 管理
- 多项目工作区
- 文件系统 watch / freshness
- 与 ai_project_template 的本地开发流程融合
- 后续可选的本地工具调用、验证辅助和 Agent 工作流编排
- 更完整的用户交互、状态保持和权限边界
```

## Product Kernel

产品内核是 Agent，不是 UI。

```text
Agent kernel
  -> Project Profiler
  -> Evidence Collector
  -> Semantic Reasoner
  -> Grounding Checker
  -> Semantic Graph Store
  -> Visualization Planner
  -> Human Interaction Layer
```

普通软件能力仍然需要，但它们是 Agent 的基础设施：

```text
- CLI
- artifact storage
- local server
- desktop shell
- file indexing
- cache
- config
- rendering
```

它们不能取代 Agent 的语义理解、计划、查证、推理、记忆和追问能力。

## Development Route

当前路线应理解为从基础设施走向桌面端 Agent，而不是停在 CLI / Web 工具：

```text
P1a
  deterministic evidence shell
  ProjectGraph / TraceIndex / freshness

P1a+
  Agent runtime dry-run
  provider contract
  claim validation
  graph write proposal

P1b
  one-concept L5/L6-to-RTL trace
  ConceptTraceGraph / EvidenceGraph-style artifacts

P1c
  verification coverage explanation

P1d
  desktop app shell
  macOS / Linux first, Windows second
  artifact viewer + Agent interaction shell

P2
  Development Companion Agent
  integration with ai_project_template workflow
  semantic memory maintained during development

P3
  Review / Audit Agent
  only after understanding graph is reliable

P4
  Develop-Understand-Verify Agent platform
```

## Non-Negotiable Direction

The project must not drift into:

```text
- static analyzer with a GUI
- PASS/HOLD checker
- audit finding dashboard
- Markdown report generator
- desktop app that merely wraps static reports
```

The GUI must show what the Agent understands and why it believes it, including evidence, uncertainty and provenance.

## Desktop Acceptance Direction

The desktop product becomes meaningful when it can:

```text
- open a local FPGA project workspace
- run or load understanding artifacts safely
- display project/stage/concept graphs
- show evidence line ranges and source provenance
- answer grounded follow-up questions
- track stale semantic memory
- preserve uncertainty and inferred status
- keep target projects read-only unless a future explicit development workflow allows edits
```

Until those exist, CLI artifacts are prototypes and infrastructure, not the final product.
