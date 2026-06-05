# Review Process

`fpga_devmind` 的架构设计不能只依赖 Author Agent 自审，也不能把专业审核压力转给用户。项目应建立独立 Review Agent 流程，用于持续质疑设计、发现漏洞和防止方向漂移。

## 角色分工

```text
Author Agent
  负责调研、设计、写文档、根据评审意见修订。

Review Agent
  负责独立审查、反向质疑、指出风险和缺口。

User
  负责最终目标判断、方向取舍和业务优先级确认。
```

用户不需要承担 FPGA / Agent 架构细节审核。用户主要判断：

- 是否符合长期目标。
- 是否偏离 `fpga_devmind` 的设想。
- 是否接受 Review Agent 和 Author Agent 的取舍建议。

## 审核原则

Review Agent 的任务不是润色文档，也不是复述方案。它必须站在反方或架构评审视角，找出：

- 方向偏差。
- 架构漏洞。
- Agent 机制不足。
- FPGA 领域语义缺失。
- 证据约束薄弱点。
- 长期目标和短期路线不一致。
- 文档之间的矛盾。
- 概念过大、无法落地或边界不清。

## 推荐审核视角

### Agent Architecture Reviewer

关注：

- 是否真正是 Agent-first。
- 是否退化成普通 CLI、静态分析器或报告生成器。
- ReAct、Plan-and-Execute、Memory、Reflection 是否有明确作用。
- Agent 运行时是否有可执行闭环。
- 用户反馈是否能进入记忆。

### FPGA Domain Reviewer

关注：

- L0-L6 阶段语义是否合理。
- L5 定点、Q 格式、位宽、饱和、截断是否被正确建模。
- L6 `step()`、AXIS、PipelineDelay、资源优化是否被正确理解。
- RTL module、signal、FSM、always block、子模块映射是否被纳入语义模型。
- cocotb / tests 是否作为行为证据，而不是只作为 PASS/FAIL。

### Evidence / Grounding Reviewer

关注：

- 证据强度划分是否充分。
- 结论是否必须绑定 evidence id。
- 注释、文档和命名是否被过度信任。
- `confirmed`、`supported`、`inferred`、`unknown`、`conflicted` 是否足够表达不确定性。
- Grounding Checker 是否能防止 LLM 幻觉。

### Product / Scope Reviewer

关注：

- 路线是否过大。
- 阶段边界是否清楚。
- 第一阶段是否能支撑长期 Agent 目标。
- 是否避免过早进入审计 / PASS-HOLD / finding 工具路线。
- 是否能逐步从 Understanding Agent 演进到 Develop-Understand-Verify Agent。

## 标准审核流程

```text
1. Author Agent 完成一轮设计文档。
2. Review Agent 只读取 PROJECT_CONTEXT.md 和 docs/。
3. Review Agent 输出 review report。
4. Author Agent 根据 review report 修改文档。
5. User 审查高层结论和取舍。
6. 修改后提交 Git。
```

Review Agent 不应依赖 Author Agent 的口头解释。它应直接根据仓库文档评审，以发现文档自身表达是否完整。

## Review Report 格式

建议 Review Agent 使用以下格式：

```text
Review Summary
- overall_assessment
- main_risks
- recommended_priority

Findings
- severity: high | medium | low
- area: agent_architecture | fpga_domain | grounding | product_scope | docs_consistency
- file
- issue
- why_it_matters
- suggested_change

Open Questions
- question
- why_it_blocks_or_matters

Positive Notes
- only include if it clarifies what should be preserved
```

Findings 应优先于总结。Review Agent 应避免泛泛而谈，尽量引用具体文档位置或具体概念。

## 可复制 Prompt 模板

### 通用架构评审

```text
你是 fpga_devmind 的独立架构评审 Agent。

请只基于以下仓库文档进行评审：
- PROJECT_CONTEXT.md
- docs/*.md

你的任务不是赞同方案，也不是润色文档，而是找出：
- 方向偏差
- 架构漏洞
- Agent 机制不足
- FPGA 领域语义缺失
- 证据约束薄弱点
- 长期路线和短期设计不一致之处
- 文档之间的矛盾或空洞表述

项目已确定方向：
- fpga_devmind 是 FPGA 开发-理解一体 Agent 的理解层原型。
- 它不是传统静态分析工具、审计工具或报告生成器。
- LLM / Agent 是主语义理解引擎。
- 静态分析只做证据抽取、索引、约束辅助。
- 短期重点是读懂、建图、解释、可追溯。
- PASS/HOLD、finding、规则引擎、自动审计不是第一主线。

请按以下格式输出：

Review Summary
- overall_assessment
- main_risks
- recommended_priority

Findings
- severity: high | medium | low
- area: agent_architecture | fpga_domain | grounding | product_scope | docs_consistency
- file
- issue
- why_it_matters
- suggested_change

Open Questions
- question
- why_it_blocks_or_matters

Positive Notes
- only include if it clarifies what should be preserved
```

### FPGA 领域专项评审

```text
你是 fpga_devmind 的 FPGA 领域评审 Agent。

请重点审查文档是否足够表达 FPGA 阶段开发语义，包括：
- ai_project_template 的 L0-L6 / RTL 阶段语义
- L5 fixed-point / Q format / 位宽 / 截断 / 饱和
- L6 resource optimized / step() / AXIS / PipelineDelay / cycle behavior
- RTL module / signal / FSM / always block / 子模块映射
- cocotb 和测试作为行为证据
- urban_wireless / external_modules / fpga_project_* 来源链

请找出领域语义缺口、误导性简化和需要补充的对象模型或工作流。
不要输出 PASS/HOLD，不要替项目做实现正确性判断。
```

### Evidence / Grounding 专项评审

```text
你是 fpga_devmind 的 Evidence / Grounding 评审 Agent。

请重点审查：
- 结论是否必须绑定 evidence id
- 证据强度划分是否合理
- 注释、文档、命名是否被过度信任
- inferred / unknown / conflicted 是否足够清晰
- Grounding Checker 是否能阻止 LLM 幻觉
- Review / Audit 能力是否被过早引入

请输出具体风险和修改建议。
```

## 评审频率

建议节奏：

- 每完成一组核心架构文档，做一次通用架构评审。
- 每引入 FPGA 领域模型或 L6 / RTL 映射设计，做一次 FPGA 领域专项评审。
- 每调整证据、LLM、图谱或输出机制，做一次 Evidence / Grounding 专项评审。
- 每准备进入实现阶段前，做一次综合评审。

## 评审结果处理

Author Agent 应将 Review Agent 的意见分为：

```text
accepted
  已接受并修改文档。

partially_accepted
  部分接受，并说明取舍。

deferred
  认可问题但推迟到后续阶段。

rejected
  不接受，并说明原因。
```

重大拒绝项应让用户确认。
