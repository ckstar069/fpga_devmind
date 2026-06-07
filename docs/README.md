# fpga_devmind 文档索引

`fpga_devmind` 的方向是 FPGA 开发-理解一体 Agent 的理解层原型。当前阶段仍是总体架构、调研和规划，不急于实现。

## 核心文档

- [Agent-first architecture](agent-first-architecture.md)：总体定位、Agent 机制、普通软件底座的职责边界。
- [Agent runtime](agent-runtime.md)：Agent 运行时组件、任务生命周期和最小可行运行时。
- [Runtime contracts](runtime-contracts.md)：TaskPlan、ToolObservation、Claim、GroundingDiagnostic、ReflectionDecision 等最小可执行契约。
- [Agent workflows](agent-workflows.md)：第一批核心 Agent 工作流，包括项目理解、阶段理解、概念追踪、L6 到 RTL 映射和验证解释。
- [Evidence grounding policy](evidence-grounding-policy.md)：证据强度、结论置信、映射规则和冲突处理。
- [Domain semantics](domain-semantics.md)：StageContract、FixedPointSpec、StreamInterfaceSpec、PipelineTimingSpec、RTLSignalSpec、TestObservation、SourceLineage 等 FPGA 领域对象。
- [Memory and interaction](memory-and-interaction.md)：程序性记忆、语义记忆、情节记忆和多轮交互机制。
- [Phase 1 scope](phase1-scope.md)：Phase 1a / 1b / 1c 收窄切片、样例项目和验收指标。
- [Phase 1a single stage understanding](phase1a-single-stage-understanding.md)：`coarse_sync_glm` L6 单阶段 Understanding Agent 的详细规格。
- [Review process](review-process.md)：独立 Review Agent 的角色、审核视角、流程和 prompt 模板。
- [Review response 0001](review-response-0001.md)：第一次独立 Review Agent 评审的处理决定。
- [Semantic graph model](semantic-graph-model.md)：ProjectGraph / StageGraph / ConceptGraph / EvidenceGraph / VisualizationSpec 的对象模型草案。
- [Toolbox](toolbox.md)：未来 Agent 可调用的确定性工具箱边界。
- [Tool contracts](tool-contracts.md)：第一批确定性工具的输入输出、evidence id、错误模式和片段边界规则。
- [Roadmap](roadmap.md)：从 Understanding Agent 到 Develop-Understand-Verify Agent 的演进路线。

## 评审记录

- [Review 0001: Agent Architecture and Grounding](reviews/0001-agent-architecture-review.md)

## 约束

- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不泄露 API key。
- API key 不写入日志、报告或提交。
- 默认输出写入 `/tmp` 或 `/private/tmp`。
