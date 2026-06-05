# Agent Workflows

本文定义 `fpga_devmind` 第一批核心 Agent 工作流。它们不是普通命令集合，而是 Agent 的调查和理解模式。

## 1. UnderstandProject

目标：识别项目是什么，避免选错分析入口。

输入：

```text
project_root
optional user_goal
```

Agent 计划：

```text
1. 读取项目根目录结构。
2. 检查是否有 ai_project_template 标志。
3. 检查 src/python_model/L0-L6。
4. 检查 package 布局、pyproject、src/*。
5. 检查 RTL 位置：src/verilog_model/rtl、vivado/src。
6. 检查 tests、docs、config、external_modules。
7. 判断项目角色和成熟度。
8. 找出可能的工程主线。
```

输出：

```text
ProjectProfile
StageGraph skeleton
SourceLineage candidates
main_entry_candidates
UncertaintyNotes
```

可视化：

```text
Project Overview Graph
Stage Coverage Map
Source / Dependency Map
```

典型不确定：

- `.current_stage` 缺失。
- L6 空但 RTL 存在。
- `src/verilog_model/rtl` 与 `vivado/src` 并存。
- 多套 package 入口并存。

## 2. UnderstandStage

目标：解释某个阶段实际实现了什么。

输入：

```text
project_root
stage_id
optional focus
```

Agent 计划：

```text
1. 加载 ProjectProfile。
2. 读取阶段目录和相关参数。
3. 找主入口文件和辅助文件。
4. 抽取类、函数、step、process_block、公式、状态、接口。
5. 检索相关 docs、tests、external_modules。
6. 判断主处理流程。
7. 提取输入、输出、中间信号、模块职责。
8. 标注定点、位宽、时序、资源化信息。
9. 写入 StageGraph / ConceptGraph / EvidenceGraph。
```

输出：

```text
StageNode
ConceptNodes
ImplementationViews
DataflowGraph
EvidenceItems
UncertaintyNotes
```

可视化：

```text
Stage Main Flow
Stage Dataflow
Signal / Variable Table
Formula / Transformation View
```

典型不确定：

- 多个主入口。
- 代码和文档不一致。
- 公式只在注释中出现。
- 辅助工具逻辑与主数据路径混杂。

## 3. TraceConcept

目标：追踪一个工程概念跨阶段如何演化。

输入：

```text
project_root
concept_query
optional stage_range
```

示例概念：

```text
lts_start
peak_idx
coarse CFO
fine CFO
FIFO
CORDIC
metric
valid
Q1.11
```

Agent 计划：

```text
1. 查询已有 ConceptGraph。
2. 搜索概念名、别名、相关信号和文档描述。
3. 在各阶段查找实现视图。
4. 识别别名和语义等价关系。
5. 建立 evolves_to / refines / maps_to 边。
6. 检查断点、重命名、语义漂移。
7. 生成概念演化解释。
```

输出：

```text
ConceptNode
ImplementationViews by stage
Concept Evolution Edges
Evidence Trace
UncertaintyNotes
```

可视化：

```text
Concept Evolution Graph
Evidence Trace Graph
Stage-by-stage Concept Table
```

典型不确定：

- 名称相似但语义不确定。
- 同名不同义。
- 某阶段没有显式实现视图。
- 从算法概念到 RTL 信号之间缺少中间证据。

## 4. MapL6ToRTL

目标：建立 L6 Python 规格与 RTL 实现的对应关系。

输入：

```text
project_root
optional module_or_concept
```

Agent 计划：

```text
1. 加载 L6_resource_opt。
2. 找 L6 顶层类、step、state、interface。
3. 加载 RTL top 和子模块。
4. 提取 RTL ports、signals、parameters、always、assign、instances。
5. 读取 RTL 注释和 design docs。
6. 检查 tests / cocotb 层级观测。
7. 建立 L6 class / function / state ↔ RTL module / signal / FSM 映射。
8. 区分直接映射、资源化细化、RTL-only 细节。
9. 标注不确定和缺失映射。
```

输出：

```text
ImplementationMappingGraph
L6 ImplementationViews
RTL ImplementationViews
EvidenceItems
VerificationCoverage edges
UncertaintyNotes
```

可视化：

```text
L6-to-RTL Mapping Graph
RTL Module / Signal Map
Resource Refinement Graph
Unmapped Item List
```

典型不确定：

- RTL 有 LUT、DSP、更宽内部位宽，但 L6 未显式表达。
- L6 状态没有清晰 RTL 对应信号。
- 映射只由注释声明，代码证据不足。
- RTL 与 L6 在数据对齐、shift、divide、latency 上存在实现细化。

## 5. ExplainVerification

目标：解释测试到底覆盖了哪些工程语义节点。

输入：

```text
project_root
optional test_scope
optional concept_or_stage
```

Agent 计划：

```text
1. 读取 tests 目录。
2. 区分 Python 单元测试、cross-compare、cocotb、仿真脚本。
3. 提取测试输入、断言、层级信号访问、预期行为。
4. 映射到 StageGraph / ConceptGraph / RTL Mapping。
5. 标注每个测试覆盖的语义节点。
6. 找出重要但未被测试观察的节点。
```

输出：

```text
VerificationCoverageGraph
Test EvidenceItems
covered_concepts
covered_signals
uncovered_or_unclear_nodes
UncertaintyNotes
```

可视化：

```text
Verification Coverage Graph
Test-to-Concept Matrix
Observed RTL Signal Map
```

典型不确定：

- 测试只跑通但缺少断言。
- 只检查输出，不检查关键中间语义节点。
- 层级信号名和 RTL 当前实现不一致。
- 测试验证行为，但不能证明算法完全等价。

## 工作流组合

典型完整链路：

```text
UnderstandProject
  ↓
UnderstandStage
  ↓
TraceConcept
  ↓
MapL6ToRTL
  ↓
ExplainVerification
```

用户也可以直接从任一工作流开始。比如用户问：

```text
这个 RTL 的 s2_peak_idx 来自哪里？
```

Agent 应从 `TraceConcept` 或 `MapL6ToRTL` 开始；如果项目画像不存在，再自动补做局部 `UnderstandProject`。
