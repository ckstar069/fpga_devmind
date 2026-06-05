# Agent Runtime

本文定义 `fpga_devmind` 的 Agent 运行时草案。它回答一个问题：当用户提出一个工程理解问题时，Agent 内部如何组织调查、推理、记忆和输出。

## 运行时定位

第一阶段不建议直接做复杂多 Agent 系统。更稳妥的方式是：

```text
Single Orchestrating Agent
  + deterministic tools
  + graph memory
  + grounding checker
```

也就是一个主 Agent 负责计划、推理和对话，确定性工具负责证据抽取、图谱读写和渲染。后续如果任务复杂度上升，再把 Planner、Extractor、Reasoner、Critic 拆成多个 Agent。

## 运行时组件

```text
User Request
  ↓
Intent Interpreter
  ↓
Task Planner
  ↓
Investigation Loop
  ↓
Semantic Reasoner
  ↓
Graph Memory Writer
  ↓
Grounding Checker
  ↓
Visualization Planner
  ↓
Dialogue Response
```

### Intent Interpreter

把用户自然语言问题转成结构化任务。

示例：

```text
用户: 解释 coarse_sync_glm 的 S2 peak_idx 来自哪里。

任务:
- workflow: TraceConcept
- project_hint: fpga_project_coarse_sync_glm
- concept_query: s2_peak_idx / peak_idx
- required_views:
  - stage evolution
  - L6-to-RTL mapping
  - evidence trace
```

### Task Planner

制定调查计划。它不直接下结论，只决定需要哪些证据。

示例计划：

```text
1. 读取 ProjectProfile，确认项目布局。
2. 搜索 peak_idx、s2、peak、detect 相关符号。
3. 读取 L3/L5/L6 中的 peak detect 实现。
4. 读取 RTL S2 模块和 top 连接。
5. 读取 cocotb 对 S2/peak_idx 的层级检查。
6. 建立 ConceptGraph 和 EvidenceGraph。
7. 检查是否存在同名不同义或映射断点。
```

### Investigation Loop

执行 ReAct 循环：

```text
Reason:
  下一步要确认 peak_idx 在 L6 中如何产生。

Act:
  调用 Python / text evidence 工具搜索 L6_resource_opt。

Observe:
  返回候选文件、符号、代码片段和 evidence ids。

Reason:
  需要确认 RTL 是否有对应 signal 或 module。
```

每次 Act 都应产生可追溯证据，不能只返回无结构文本。

### Semantic Reasoner

基于证据形成工程语义理解。

它负责回答：

- 主路径是什么。
- 某个变量或信号代表什么工程概念。
- 哪些阶段视图属于同一概念。
- 哪些 RTL 细节是 L6 的直接映射，哪些是资源化细化。
- 测试覆盖了哪些语义节点。
- 哪些结论只是推断。

### Graph Memory Writer

把推理结果写入语义图，而不是只写一段报告。

输出对象包括：

- ProjectProfile。
- StageNode。
- ConceptNode。
- ImplementationView。
- EvidenceItem。
- GraphEdge。
- UncertaintyNote。
- VisualizationSpec。

### Grounding Checker

检查 Agent 自己的输出是否可靠。

最低检查项：

```text
1. 每个主要结论是否绑定 evidence_ids。
2. 映射是否只基于命名相似。
3. 注释是否被当成强证据。
4. 文档、代码、RTL、测试是否存在冲突。
5. 是否存在应标注但未标注的不确定项。
6. 输出是否误用了 PASS/HOLD/finding 等审计语言。
```

### Visualization Planner

根据语义图选择合适图形，而不是强行画一张大图。

示例：

```text
TraceConcept → Concept Evolution Graph + Evidence Trace Graph
MapL6ToRTL → L6-to-RTL Mapping Graph + Unmapped Item List
ExplainVerification → Verification Coverage Graph + Test-to-Concept Matrix
```

## 任务生命周期

```text
created
  ↓
planned
  ↓
collecting_evidence
  ↓
reasoning
  ↓
writing_graph
  ↓
checking_grounding
  ↓
rendering
  ↓
answered
  ↓
feedback_update
```

失败或不确定状态：

```text
blocked_missing_project
blocked_missing_stage
insufficient_evidence
ambiguous_mapping
conflicting_evidence
tool_error
model_output_invalid
```

失败不等于输出空结果。Agent 应解释当前查到了什么、哪里不确定、下一步需要什么证据。

## 最小可行运行时

第一版运行时可以保持很薄：

```text
CLI / local command
  ↓
Agent session
  ↓
tool calls
  ↓
/tmp graph artifacts
  ↓
Markdown + Mermaid response
```

但即使外壳是 CLI，也必须保留 Agent 运行时概念：

- 任务计划。
- 证据循环。
- 语义图写入。
- Grounding 检查。
- 用户追问和记忆更新。

## 未来拆分

当复杂度上升后，可以逐步拆分为：

```text
Planner Agent
Evidence Agent
Semantic Reasoner Agent
Visualization Agent
Critic Agent
Dialogue Agent
```

但这不是第一阶段必须做的事情。第一阶段的重点是先把 Agent 循环跑通，并让输出可靠、可追溯。
