# Agent Toolbox

本文定义未来 `fpga_devmind` Agent 可以调用的确定性工具箱。工具箱不是产品核心，核心是 Agent 的调查、推理和语义记忆。

第一批工具的输入输出、evidence id 生成、错误模式和片段边界规则见 [Tool Contracts](tool-contracts.md)。

## Tooling 原则

- 工具只负责证据、索引、解析、存储、渲染。
- 工具不直接给最终工程语义结论。
- 目标 `fpga_project_*` 只读。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不把 API key 写入日志、报告或提交。
- 默认输出到 `/tmp` 或 `/private/tmp`。

## 文件与项目工具

```text
scan_project_tree
  扫描项目目录，识别候选阶段、RTL、tests、docs、config、external_modules。

classify_project_layout
  判断标准模板布局、flat package、package-dir mapping、混合布局。

detect_stage_coverage
  判断 L0-L6/RTL/tests/docs/vivado 的实际覆盖。

resolve_external_sources
  查找 ai_project_template external_modules、项目本地 external_modules、urban_wireless/module_projects、其他 fpga_project_* 依赖。
```

## Python 证据工具

```text
extract_python_symbols
  提取 class、function、method、imports、calls、constants。

extract_python_formulas
  提取关键表达式、复数运算、数组处理、shift、scale、truncate、saturate。

extract_python_stage_patterns
  识别 step、process_block、PipelineDelay、AXISPort、QInt、QFormat、state。

extract_python_comments_and_docstrings
  提取 docstring 和关键注释，作为中等或弱证据。
```

## RTL 证据工具

```text
extract_rtl_modules
  提取 module、port、parameter、localparam。

extract_rtl_signals
  提取 wire、reg、logic、位宽、切片、拼接。

extract_rtl_behavior
  提取 assign、always block、FSM 线索、时序逻辑、组合逻辑。

extract_rtl_instances
  提取子模块实例化和连接关系。

extract_rtl_comments
  提取头注释和模块注释，不能单独作为强证据。
```

## 测试证据工具

```text
extract_pytest_evidence
  提取测试输入、断言、期望值、被测函数。

extract_cocotb_evidence
  提取 DUT 端口访问、层级信号访问、时钟复位、断言、行为检查。

map_test_to_concepts
  把测试观察点映射到 ConceptGraph 或 RTL Mapping。
```

## 文档和配置工具

```text
extract_design_docs
  提取 docs/design、README、阶段说明中的架构描述和公式。

extract_parameters
  读取 config/parameters.py、external_libs.yaml、projects.yaml 等。

query_template_rules
  查询 ai_project_template 的阶段规则、skills、hooks、workflows。
```

## 语义图工具

```text
read_graph_memory
  读取已有 ProjectGraph / ConceptGraph / EvidenceGraph。

write_graph_memory
  写入 Agent 新生成的语义节点、边、证据和不确定项。

query_concept
  查询概念、别名、阶段实现视图。

query_evidence
  查询某个结论绑定的证据。
```

## 可视化工具

```text
render_mermaid
  从 VisualizationSpec 生成 Mermaid。

render_graphviz
  从 VisualizationSpec 生成 Graphviz。

render_drawio
  后续生成 Draw.io XML。

render_interactive_graph
  后续供 React Flow / xyflow 桌面端或 Web UI 使用。
```

## Grounding 检查工具

```text
check_evidence_coverage
  检查主要结论是否都有 evidence_ids。

check_weak_mappings
  检查映射是否只基于命名或注释。

check_conflicts
  检查源码、RTL、文档、测试之间是否有冲突。

check_uncertainties
  检查是否需要补充 UncertaintyNote。
```

这些工具应服务 Reflection / Critic，让 Agent 输出前先检查自己的理解是否可靠。
