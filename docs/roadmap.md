# Roadmap

本文描述 `fpga_devmind` 从理解层原型走向 FPGA 开发-理解-验证一体 Agent 的演进路线。

## 总原则

- 按真正的 Agent 方向设计。
- 第一批能力可以用普通软件形态支撑，但产品内核必须是 Agent。
- 先理解，再审计。
- 先建语义图，再生成报告。
- LLM / Agent 是主语义理解引擎，静态分析是证据和约束工具。
- 所有结论必须有证据锚点。
- 不确定必须显式表达。

## Phase 1: Understanding Agent

目标：只读项目，建语义图，解释阶段实现，生成可视化，支持追问。

Review 0001 后，Phase 1 已收窄为 P1a / P1b / P1c 三个可验收切片，详见 [Phase 1 Scope](phase1-scope.md)。第一阶段不再试图一次完成所有工作流，而是先证明单项目单阶段理解、一个概念 L5-L6-RTL trace、一个 cocotb 覆盖解释闭环。

核心能力：

- UnderstandProject。
- UnderstandStage。
- TraceConcept。
- MapL6ToRTL。
- ExplainVerification。
- EvidenceGraph / ConceptGraph / VisualizationSpec。
- 本地 GUI artifact viewer，用于查看图、证据、诊断和不确定项。

这一阶段不追求自动开发，也不以审计结论为主。

## Phase 2: Development Companion Agent

目标：融入 `ai_project_template` 开发过程，在每次阶段推进后维护语义记忆。

核心能力：

- 在开发 Agent 推进 L0-L6/RTL 后自动更新 ProjectGraph。
- 记录阶段演化和用户确认。
- 展示当前实现与上一阶段的主要变化。
- 为开发 Agent 生成可追溯的理解反馈。

这一阶段开始把 `fpga_devmind` 从离线理解工具变成开发伴随 Agent。

## Phase 3: Review / Audit Agent

目标：基于已经可靠的理解图，再做偏差、风险、验证缺口分析。

核心能力：

- 阶段职责漂移识别。
- 文档、源码、RTL、测试之间的冲突提示。
- L5/L6/RTL 映射缺口。
- 验证覆盖缺口。
- 高风险不确定项聚合。

这一阶段可以引入 review / audit，但不能回退成 PASS/HOLD 或 finding 堆叠工具。

## Phase 4: Develop-Understand-Verify Agent

目标：与 `ai_project_template` 深度融合，形成真正的 FPGA Domain Agent Platform。

长期形态：

```text
用户目标
  ↓
开发 Agent 按 ai_project_template 推进代码
  ↓
fpga_devmind 持续理解代码和阶段演化
  ↓
用户看图、看证据、做判断
  ↓
fpga_devmind 把偏差 / 决策反馈给开发 Agent
  ↓
继续修改、验证、沉淀记忆
```

最终能力：

- 开发。
- 理解。
- 语义记忆。
- 可视化。
- 验证辅助。
- 偏差和风险分析。
- 用户决策闭环。

## 当前边界

当前已经完成 P1a V0.1 候选的确定性 evidence shell，并已落地 P1a+ external-API-free Agent dry-run。P1a+ 现在可以生成 provider contract、model result validation、graph write proposal、`project_graph_proposed.json` 和 `trace_index_proposed.json`，但仍未接入真实 LLM provider。

当前代码能力仍限制在只读理解原型：

```text
- P1a V0.1: deterministic read / graph / trace / query / freshness.
- P1a+: external-API-free Agent runtime and provider contract dry-run over P1a artifacts.
- P1b: ready for controlled implementation planning; not implemented yet.
- P1c: not implemented yet.
```

下一步可编码实施应从 P1b 单概念 L5/L6-to-RTL trace 开始，详见 [P1b Implementation Plan](implementation-plan-p1b.md) 和 [Agent Handoff: Claude + Kimi Implementation](agent-handoff-claude-kimi.md)。用户希望有图形界面，因此 P1b 之后应进入 [UI Prototype Plan](ui-prototype-plan.md)，实现本地只读 artifact viewer。GUI 目标同时包括 Web GUI 和桌面端软件，桌面优先 macOS / Linux，Windows 次之。不要在 P1b 前抢先接真实 provider 或扩大成通用 RTL 审计工具。

硬边界：

- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不泄露 API key。
- API key 不写入日志、报告或提交。
- 默认输出写入 `/tmp` 或 `/private/tmp`。
