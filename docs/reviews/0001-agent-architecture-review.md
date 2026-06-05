# Review 0001: Agent Architecture and Grounding

Date: 2026-06-05

Reviewer: independent Review Agent

## Review Summary

- overall_assessment: 方向总体正确，文档反复强调 Agent-first、LLM 主语义、静态分析做证据底座、先理解再审计。但当前仍偏“概念架构说明”，缺少足够可执行的 Agent runtime、证据判定规则和 FPGA 结构化语义模型。最大风险不是方向错，而是实现时退化成“扫描代码 + LLM 生成报告 + Mermaid”的薄包装。
- main_risks: Agent 闭环不可执行；L5/L6/RTL 关键领域语义结构化不足；证据强度到结论置信的规则不够硬；Phase 1 范围过大，容易同时做图谱、可视化、验证解释、L6-RTL 映射而没有可验收的最小闭环。
- recommended_priority: 先收窄 Phase 1：选 1-2 个真实项目、1 个阶段理解工作流、1 个 L6-to-RTL 概念追踪工作流，补齐 plan schema、tool observation schema、claim/evidence schema、grounding failure loop 和 graph invalidation 机制，再扩展验证解释和交互式 memory。

## Findings

### High: Runtime contract missing

- area: agent_architecture
- files: `docs/agent-runtime.md`, `docs/toolbox.md`
- issue: Runtime 写出了组件链路和生命周期，但没有定义 Plan step、Act request、Observation、Reasoning artifact、Reflection result 的结构化协议，也没有迭代预算、停止条件、失败回退或 checker 失败后的重跑路径。
- suggested_change: 增加最小可执行 runtime contract：TaskPlan schema、ToolCall schema、Observation schema、Claim schema、ReflectionDecision schema；规定每轮 ReAct 必须产生 evidence ids、candidate claims、uncertainties，并定义 checker fail 后回到 collecting_evidence 或降级输出。

### High: Claim confidence policy too loose

- area: grounding
- files: `docs/evidence-grounding-policy.md`, `docs/semantic-graph-model.md`
- issue: 证据强度、结论置信和映射置信之间没有统一判定规则。单个强证据可能被错误提升为 confirmed。
- suggested_change: 引入 claim_type 维度，例如 implementation_claim、mapping_claim、behavior_claim、lineage_claim、coverage_claim；为每类 claim 定义 confirmed/supported/inferred 的最低证据组合、反证降级规则和 required_missing_evidence。

### High: FPGA domain semantics too free-form

- area: fpga_domain
- files: `docs/semantic-graph-model.md`, `docs/agent-workflows.md`
- issue: ConceptNode 和 ImplementationView 只用 fixed_point_behavior、timing_behavior、resource_notes 等自由文本字段，未结构化表达 Q 格式、位宽增长、截断/舍入/饱和、valid-ready、latency、reset、clock、pipeline alignment、FSM transition、AXIS sideband。
- suggested_change: 增加 FixedPointSpec、StreamInterfaceSpec、PipelineTimingSpec、FSMBehaviorSpec、RTLSignalSpec。

### High: Phase 1 too broad

- area: product_scope
- files: `docs/roadmap.md`, `docs/agent-workflows.md`
- issue: Phase 1 同时包含 UnderstandProject、UnderstandStage、TraceConcept、MapL6ToRTL、ExplainVerification、EvidenceGraph、ConceptGraph、VisualizationSpec，范围过大且没有验收切片。
- suggested_change: 把 Phase 1 拆成 P1a/P1b/P1c。

### Medium: Source lineage missing as graph object

- area: fpga_domain
- files: `PROJECT_CONTEXT.md`, `docs/toolbox.md`, `docs/semantic-graph-model.md`
- issue: external_modules、urban_wireless/module_projects、历史模块来源链被提到，但语义图没有 SourceLineage 的正式对象模型。
- suggested_change: 增加 SourceLineageNode / SourceLineageEdge。

### Medium: Memory freshness missing

- area: agent_architecture
- files: `docs/memory-and-interaction.md`
- issue: Memory 写入策略没有版本、失效和再验证机制。
- suggested_change: 为 Semantic Memory 增加 source snapshot、file hash、tool version、model version、created_at、validated_at、stale_when_source_changed。

### Medium: Test evidence too coarse

- area: grounding
- files: `docs/evidence-grounding-policy.md`, `docs/toolbox.md`, `docs/agent-workflows.md`
- issue: cocotb/test 作为行为证据的粒度不足。
- suggested_change: 增加 TestObservation schema。

### Medium: Reflection is checklist, not loop

- area: agent_architecture
- files: `docs/agent-runtime.md`, `docs/toolbox.md`
- issue: Reflection / Critic 没有说明 checker 发现 weak mapping、missing evidence、conflict 后如何修改图、降级结论或追加调查。
- suggested_change: Grounding Checker 输出 blocking/non_blocking diagnostics，并规定处理动作。

### Medium: L0-L6 StageContract missing

- area: fpga_domain
- files: `PROJECT_CONTEXT.md`, `docs/semantic-graph-model.md`
- issue: L0-L6 阶段语义仍偏概括。
- suggested_change: 为 L0-L6 增加 StageContract。

### Medium: Toolbox lacks interface contracts

- area: grounding
- files: `docs/toolbox.md`
- issue: Toolbox 是能力清单，不是接口契约。
- suggested_change: 给第一批工具定义 JSON-like contract。

### Low: Findings format could be confused with product output

- area: docs_consistency
- files: `docs/evidence-grounding-policy.md`, `docs/review-process.md`
- issue: Review process 使用 Findings 作为 Review Agent 报告格式，但 Evidence policy 禁止当前产品输出以 finding 列表为主体。
- suggested_change: 明确 Findings 仅用于设计/架构评审，不代表 Understanding Agent 用户输出。

### Low: Acceptance examples missing

- area: product_scope
- files: `PROJECT_CONTEXT.md`, `docs/roadmap.md`
- issue: 成功标准偏体验描述，缺少可验收样例和质量指标。
- suggested_change: 选定样例项目和问题集，定义验收指标。

## Open Questions

- 第一版最小闭环要绑定哪个真实项目、哪个阶段、哪个典型问题？
- `ai_project_template` 的阶段规则、skills、hooks、L6/RTL 协议是否是权威 procedural memory？这些规则如何版本化读取？
- Semantic Memory 存储在哪里，是否允许写入当前 `fpga_devmind` 仓库、`/tmp`，还是独立 workspace cache？
- RTL 范围是否只支持 Verilog/SystemVerilog，还是包括 VHDL/IP-XACT/Vivado generated wrapper？

## Positive Notes

- Agent-first 方向应保留。
- `expected_role` 和 `actual_role_summary` 分离应保留。
- 不确定性作为一等对象应保留。
- 先理解、建图、解释、可追溯，再进入 Review/Audit 的路线应保留。
