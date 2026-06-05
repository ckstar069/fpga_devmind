# Agent-first Architecture

## 定位

`fpga_devmind` 不是传统静态分析工具、审计工具或一次性报告生成器。它应按真正的 Agent 方向设计，短期落地为 FPGA Understanding Agent，长期与 `ai_project_template` 融合为 FPGA 开发-理解-验证一体 Agent。

更准确的定位是：

> 面向 `ai_project_template` 生态的 FPGA 工程理解 Agent，用于把 AI agent 推进出来的阶段代码、RTL、测试、文档和外部来源，转成可追溯的工程语义图和可视化解释。

## Agent-first 而不是 Tool-first

设计顺序应是：

```text
Agent 能力与工作流
  ↓
Agent 需要的语义记忆
  ↓
证据抽取和普通软件基础设施
  ↓
CLI / UI / 图形渲染
```

普通软件能力仍然重要，但它们是 Agent 的底座：

- 文件扫描、索引、缓存、配置管理。
- Python / RTL / 测试 / 文档证据抽取。
- 语义图存储和查询。
- Mermaid、Graphviz、Draw.io、React Flow 等渲染。
- CLI、桌面端或 Web UI 交互。

真正的产品内核是 Agent 的阅读、计划、查证、推理、记忆、解释和追问能力。

## 核心循环

`fpga_devmind` 的核心循环应是：

```text
User Intent
  ↓
Intent Interpreter
  ↓
Investigation Planner
  ↓
ReAct Evidence Loop
  ↓
Evidence-grounded Reasoner
  ↓
Graph Memory Writer
  ↓
Grounding Checker / Reflection
  ↓
Visualization Planner
  ↓
Explanation / Dialogue
  ↓
User Feedback
  ↓
Memory Update
```

这不同于普通软件的：

```text
输入参数 → 扫描文件 → 生成报告
```

## Agent 机制

### Plan-and-Execute

用于较大的工程理解任务。Agent 先制定调查计划，再逐步执行。

示例任务：

```text
分析 fpga_project_coarse_sync_glm 的 L6 到 RTL 映射。
```

计划可能包括：

```text
1. 识别项目布局和阶段覆盖。
2. 找到 L6 主模型。
3. 找到 RTL top 和子模块。
4. 提取 L6 类、函数、状态、接口。
5. 提取 RTL module、signal、always block、实例化。
6. 查 cocotb 测试覆盖了哪些层级信号。
7. 建立 L6 ↔ RTL 映射。
8. 标注不确定项。
```

### ReAct

用于逐步查证：

```text
Reason → Act → Observe → Reason again
```

在本项目中的例子：

```text
Reason:
  需要确认 L6 是否把 coarse sync 分成 S0-S3。

Act:
  搜索 L6_resource_opt 目录。

Observe:
  发现 L6 中存在 S0/S1/S2/S3 类或函数。

Reason:
  需要确认 RTL 是否存在对应子模块。

Act:
  读取 RTL top 和子模块。

Observe:
  发现 top 中实例化 s0/s1/s2/s3 模块。
```

### Evidence Grounding

所有主要结论必须绑定证据。没有证据时只能输出 `unknown`、`inferred` 或 `needs_more_evidence`。

证据可以来自：

- 源码实现。
- RTL module / signal / always block。
- 测试断言和层级信号观测。
- 设计文档。
- 配置参数。
- 模板规则、skills、hooks。
- 注释，但注释不能被盲信。

### Reflection / Critic

Agent 输出前应自检：

- 这个解释是否有源码或 RTL 证据？
- 这个映射是否只是名字相似？
- 文档和代码是否冲突？
- 注释是否被当成了事实？
- 测试是否真的验证了该语义节点？
- 哪些内容应该标注为 `inferred` 或 `unknown`？

这个 Critic 不是审计目标项目，而是审查 Agent 自己的理解是否可靠。

### Memory

`fpga_devmind` 必须有记忆，否则只是一次性工具。

```text
Procedural Memory
  ai_project_template 的阶段规则、skills、hooks、L6 / RTL 协议、Q 格式规则。

Semantic Memory
  ProjectGraph、StageGraph、ConceptGraph、EvidenceGraph、VisualizationSpec。

Episodic Memory
  用户问过什么、确认过什么、纠正过什么、哪些解释已被接受。
```

## 与 ai_project_template 的融合关系

`ai_project_template` 当前更像开发执行协议层：

- 阶段结构。
- 领域规则。
- 参数系统。
- external_modules。
- skills / workflows / hooks。
- 测试和阶段门控。
- L6 到 RTL 的开发约束。

`fpga_devmind` 应补上理解与记忆层：

- 读懂项目。
- 建立工程语义图。
- 可视化阶段演化和数据流。
- 解释证据。
- 标注不确定和漂移。
- 接受用户反馈并更新记忆。
- 后续把偏差或决策反馈给开发 Agent。

长期目标不是两个项目长期分离，而是融合成：

```text
FPGA Domain Agent Platform
  = Develop + Understand + Verify + Memory + Visualization
```

## 当前不做

当前阶段不把以下内容作为主线：

- PASS / HOLD。
- finding / checklist 作为主要输出。
- 规则引擎优先。
- 自动审计结论。
- 自动修改目标 `fpga_project_*`。
- Vivado、synthesis、implementation、bitstream。
