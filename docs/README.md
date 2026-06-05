# fpga_devmind 文档索引

`fpga_devmind` 的方向是 FPGA 开发-理解一体 Agent 的理解层原型。当前阶段仍是总体架构、调研和规划，不急于实现。

## 核心文档

- [Agent-first architecture](agent-first-architecture.md)：总体定位、Agent 机制、普通软件底座的职责边界。
- [Agent runtime](agent-runtime.md)：Agent 运行时组件、任务生命周期和最小可行运行时。
- [Agent workflows](agent-workflows.md)：第一批核心 Agent 工作流，包括项目理解、阶段理解、概念追踪、L6 到 RTL 映射和验证解释。
- [Evidence grounding policy](evidence-grounding-policy.md)：证据强度、结论置信、映射规则和冲突处理。
- [Memory and interaction](memory-and-interaction.md)：程序性记忆、语义记忆、情节记忆和多轮交互机制。
- [Review process](review-process.md)：独立 Review Agent 的角色、审核视角、流程和 prompt 模板。
- [Semantic graph model](semantic-graph-model.md)：ProjectGraph / StageGraph / ConceptGraph / EvidenceGraph / VisualizationSpec 的对象模型草案。
- [Toolbox](toolbox.md)：未来 Agent 可调用的确定性工具箱边界。
- [Roadmap](roadmap.md)：从 Understanding Agent 到 Develop-Understand-Verify Agent 的演进路线。

## 约束

- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不泄露 API key。
- API key 不写入日志、报告或提交。
- 默认输出写入 `/tmp` 或 `/private/tmp`。
