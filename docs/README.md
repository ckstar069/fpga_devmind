# fpga_devmind 文档总索引

`fpga_devmind` 的方向是 FPGA 开发-理解一体 Agent 的理解层原型。它不是传统静态分析器、审计检查器、报告生成器，也不是只会打开 JSON artifact 的普通 UI。当前主线是：先可靠读懂 FPGA 阶段实现，建立语义图、证据链和可视化解释，再逐步扩展到真实模型辅助、开发伴随、验证辅助和审计分析。

## 0. 新会话 / 新 Agent 必读顺序

后续 Web GPT 或本地 Agent 进入项目时，先按这个顺序读：

1. [`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)：原始项目背景、用户问题、当前阶段成功标准。
2. [`current-position-and-drift.md`](current-position-and-drift.md)：T047/T047.1 后的当前定位和偏差分析。
3. [`documentation-map.md`](documentation-map.md)：完整文档分组和阅读路线。
4. [`product-target.md`](product-target.md)：最终产品形态和不可偏离方向。
5. [`roadmap.md`](roadmap.md)：长期阶段路线。
6. [`implementation-status.md`](implementation-status.md)：当前实现状态和未完成事项。

如果时间有限，至少阅读前 3 个。

## 1. 当前关键判断

当前实现已经在 CLI、Tauri 桌面端、artifact viewer、Agent Q&A、安全 provider boundary、dry-run request package、approval gate、blocked/mock transport、real provider adapter 方面推进较快。

但项目的核心目标仍然是：

```text
源码证据
  -> LLM/Agent 工程语义理解
  -> 结构化 claim / evidence / uncertainty
  -> 语义图与可视化规划
  -> 用户可读流程图 / 数据流图 / 信号表 / 公式解释
  -> 可追问、可追证据、可标注不确定
```

T047/T047.1 解决的是“真实模型可安全进入系统”的基础问题，不是最终产品目标。T047.1 之后优先做真实项目 dogfood 和语义理解闭环，不要继续堆 provider 功能。

推荐下一阶段：

```text
T048: Real Project Dogfood Against Original Understanding Goals
```

## 2. 文档分组

完整分组见 [`documentation-map.md`](documentation-map.md)。这里保留快速入口。

### 2.1 方向 / 架构 / 约束

- [`direction-guardrails.md`](direction-guardrails.md)：短版方向护栏。
- [`product-target.md`](product-target.md)：最终产品形态。
- [`agent-first-architecture.md`](agent-first-architecture.md)：Agent-first 架构。
- [`agent-runtime.md`](agent-runtime.md)：Agent 运行时。
- [`runtime-contracts.md`](runtime-contracts.md)：TaskPlan、ToolObservation、Claim、GroundingDiagnostic、ReflectionDecision 等契约。
- [`agent-workflows.md`](agent-workflows.md)：UnderstandProject、UnderstandStage、TraceConcept、MapL6ToRTL、ExplainVerification。
- [`evidence-grounding-policy.md`](evidence-grounding-policy.md)：证据强度、置信、映射规则、冲突处理。
- [`domain-semantics.md`](domain-semantics.md)：FPGA 领域对象。
- [`semantic-graph-model.md`](semantic-graph-model.md)：语义图模型。
- [`toolbox.md`](toolbox.md)：未来 Agent 工具箱。
- [`tool-contracts.md`](tool-contracts.md)：确定性工具契约。
- [`memory-and-interaction.md`](memory-and-interaction.md)：记忆和交互。

### 2.2 阶段规划

- [`phase1-scope.md`](phase1-scope.md)：P1a/P1b/P1c 范围。
- [`phase1a-single-stage-understanding.md`](phase1a-single-stage-understanding.md)：P1a 单阶段理解规格。
- [`phase1a-schema.md`](phase1a-schema.md)：P1a artifact schema。
- [`p1a-implementation-prep.md`](p1a-implementation-prep.md)：P1a 实施准备。
- [`p1a-v0.1-quickstart.md`](p1a-v0.1-quickstart.md)：P1a V0.1 快速使用。
- [`p1a-v0.1-acceptance.md`](p1a-v0.1-acceptance.md)：P1a V0.1 验收。
- [`p1a-plus-semantic-agent.md`](p1a-plus-semantic-agent.md)：P1a+ 语义 Agent 层。
- [`implementation-plan-p1b.md`](implementation-plan-p1b.md)：P1b 单概念 L5/L6-to-RTL trace。
- [`ui-prototype-plan.md`](ui-prototype-plan.md)：桌面端 artifact viewer / Agent interaction shell。

### 2.3 当前状态 / 偏差记录 / 总览

- [`implementation-status.md`](implementation-status.md)：当前累计实现状态。
- [`current-position-and-drift.md`](current-position-and-drift.md)：当前定位、偏差和后续路线建议。
- [`documentation-map.md`](documentation-map.md)：文档地图。

### 2.4 实施任务卡

早期 P1b / 桌面任务：

- [`tasks/T001-p1b-schema-artifact-contract.md`](tasks/T001-p1b-schema-artifact-contract.md)
- [`tasks/T002-p1b-readonly-source-collector.md`](tasks/T002-p1b-readonly-source-collector.md)
- [`tasks/T003-p1b-concept-evidence-collector.md`](tasks/T003-p1b-concept-evidence-collector.md)
- [`tasks/T004-p1b-rtl-evidence-collector.md`](tasks/T004-p1b-rtl-evidence-collector.md)
- [`tasks/T005-p1b-mapping-claim-builder.md`](tasks/T005-p1b-mapping-claim-builder.md)
- [`tasks/T006-p1b-grounding-report.md`](tasks/T006-p1b-grounding-report.md)
- [`tasks/T007-p1b-cli-render-smoke.md`](tasks/T007-p1b-cli-render-smoke.md)
- [`tasks/T008-desktop-artifact-viewer-contract.md`](tasks/T008-desktop-artifact-viewer-contract.md)
- [`tasks/T009-desktop-app-prototype.md`](tasks/T009-desktop-app-prototype.md)
- [`tasks/T010-desktop-p1b-concept-trace-view.md`](tasks/T010-desktop-p1b-concept-trace-view.md)

近期 Agent Q&A / Provider 任务：

- [`tasks/T044-llm-context-builder-dry-run.md`](tasks/T044-llm-context-builder-dry-run.md)
- [`tasks/T045-approval-gated-external-runtime.md`](tasks/T045-approval-gated-external-runtime.md)
- [`tasks/T046-external-execution-pipeline.md`](tasks/T046-external-execution-pipeline.md)
- [`tasks/T047-ephemeral-real-provider-adapter.md`](tasks/T047-ephemeral-real-provider-adapter.md)

### 2.5 评审记录

- [`review-process.md`](review-process.md)：独立 Review Agent 流程。
- [`reviews/0001-agent-architecture-review.md`](reviews/0001-agent-architecture-review.md)
- [`reviews/0002-phase1a-review.md`](reviews/0002-phase1a-review.md)
- [`reviews/0003-p1a-v0.1-review.md`](reviews/0003-p1a-v0.1-review.md)
- [`reviews/0004-p1a-plus-provider-contract-review.md`](reviews/0004-p1a-plus-provider-contract-review.md)
- [`reviews/0005-p1a-plus-graph-write-safety-review.md`](reviews/0005-p1a-plus-graph-write-safety-review.md)
- [`reviews/0006-p1b-handoff-readiness-review.md`](reviews/0006-p1b-handoff-readiness-review.md)
- [`review-response-0001.md`](review-response-0001.md)
- [`review-response-0002.md`](review-response-0002.md)
- [`review-response-0003.md`](review-response-0003.md)
- [`review-response-0004.md`](review-response-0004.md)
- [`review-response-0005.md`](review-response-0005.md)
- [`review-response-0006.md`](review-response-0006.md)

## 3. 硬约束

- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不把敏感凭据写入日志、报告或提交。
- 默认输出写入 `/tmp` 或 `/private/tmp`。
- 不把审计 / PASS-HOLD / finding dashboard 提前作为主线。
- 不让 provider/UI 功能扩展替代证据约束的 FPGA 语义理解闭环。
