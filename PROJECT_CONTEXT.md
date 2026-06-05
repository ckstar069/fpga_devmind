# fpga_devmind 项目上下文

## 1. 项目名称

项目目录名：`fpga_devmind`

`devmind` 表示“面向 FPGA 开发过程的工程理解、语义记忆与辅助决策能力”。本项目定位为 FPGA 开发-理解一体 Agent 的理解层原型：先可靠读懂阶段实现、建立语义图和可视化解释，再逐步扩展到开发伴随、验证辅助和审计分析。

## 2. 软件要解决的问题

FPGA 模板项目通常不是一次性完成的，而是从早期算法模型开始，逐阶段推进到最终硬件实现。

在这个过程中，用户会使用 AI agent 或人工方式持续生成、修改大量代码。代码量增长后，用户很难逐行阅读所有实现，也很难仅靠文件名、函数名或测试结果判断当前阶段到底做了什么。

本软件的意义是：

帮助用户快速理解指定 FPGA 项目在指定阶段的实际实现，并以流程图、数据流图、公式、信号、模块说明等形式可视化展示出来。

当前阶段的重点不是替用户做最终判断，而是让用户能够看清实现内容。只有先可靠理解和可视化，后续的一致性检查、约束检查、风险提示、审计分析才有基础。

## 3. 要分析的项目是什么

本软件主要面向 `znxt_ofdm` 工作区下的 FPGA 模板项目。

模板项目位于：

`/Users/ckstar/Repo/znxt_ofdm/ai_project_template/`

被分析项目通常是基于该模板创建的实例项目，位于：

`/Users/ckstar/Repo/znxt_ofdm/`

典型目录名形如：

- `fpga_project_fine_cfo`
- `fpga_project_coarse_sync_glm`
- `fpga_project_coarse_sync_kimi`
- `fpga_project_*`

模板项目本身定义了 Python → Verilog → FPGA 的分层结构，包括：

- `src/python_model/L0_external/`
- `src/python_model/L1_prototype/`
- `src/python_model/L2_structured/`
- `src/python_model/L3_pipeline/`
- `src/python_model/L4_cycle_acc/`
- `src/python_model/L5_fixedpoint/`
- `src/python_model/L6_resource_opt/`
- `src/verilog_model/rtl/`

被分析项目一般通过模板创建，然后在这些阶段目录下逐步生成、导入或改写实现代码。

除了项目自身代码，本软件还需要理解外部模块来源。外部模块可能来自：

- 模板内置外部模块库：`/Users/ckstar/Repo/znxt_ofdm/ai_project_template/external_modules/`
- 实例项目本地外部模块：`/Users/ckstar/Repo/znxt_ofdm/fpga_project_*/external_modules/`
- 工作区中的模块项目集合：`/Users/ckstar/Repo/znxt_ofdm/urban_wireless/module_projects/`
- 工作区中的历史或独立模块项目，例如 `M02_scrambler`、`M03_cp`、`M04_modulate`、`M05_interleaver`、`M06_subcarrier_allocation` 等目录及其 `external_modules/`

这些外部模块可能包含接口、定点算术、流水线组件、基础寄存器/计数器、CORDIC、DSP 或其他可复用实现。分析某个阶段时，不能只看阶段目录本身，也要在必要时把相关外部模块作为证据纳入理解范围。

## 4. FPGA 模板项目的阶段特点

模板项目通常按阶段推进，例如：

- L0/L1/L2：早期算法、参考模型或探索实现
- L3/L4：更接近工程结构的算法实现
- L5/L6：定点化、资源优化、流水线或硬件友好实现
- RTL/Verilog/HDL：硬件代码实现

不同项目不一定完全一致，但大体上都存在“从算法到硬件实现”的演进过程。

用户可能要求分析任意阶段，也可能要求比较多个阶段，例如：

- 分析 L5 做了什么
- 分析 L6 做了什么
- 对比 L5 和 L6 的差异
- 分析 RTL 是否表达了某个阶段的核心流程
- 绘制某阶段的数据流图
- 解释某个信号、公式、模块或流水线

## 5. 用户为什么需要可视化

用户使用 AI agent 推进 FPGA 阶段实现时，可能出现：

- 算法实现路径与预期不一致
- 阶段之间的演进关系不清晰
- 定点化、Q 格式、位宽处理不容易读懂
- 主流程和辅助逻辑混在一起
- Python 模型和 RTL 实现之间的对应关系不明显
- 代码能跑测试，但用户仍然不知道内部到底实现了什么

因此，用户需要软件把代码中的工程结构转成直观内容：

- 主要处理流程
- 数据如何从输入走到输出
- 中间信号如何产生
- 每个处理模块的作用
- 关键公式是什么
- 定点/Q 格式/位宽如何处理
- 哪些内容是主路径，哪些是辅助逻辑
- 哪些地方证据明确，哪些地方不确定

## 6. 当前阶段的成功标准

当前阶段如果能做到以下几点，就已经有价值：

- 能读取指定 FPGA 项目的指定阶段代码。
- 能理解该阶段的主要处理流程。
- 能生成用户看得懂的流程图或数据流图。
- 图中节点之间有明确关系，而不是一堆孤立方块。
- 图中能体现输入、输出、中间数据、关键公式或数据变换。
- 能用自然语言说明每个主要模块在做什么。
- 能指出说明依据来自哪些源码文件或代码片段。
- 不确定的地方明确标注，不强行猜测。

## 7. 当前阶段不承担的职责

当前阶段不要求软件替用户判断实现是否正确，也不要求自动给出最终审核结论。

暂不把以下能力作为第一目标：

- 自动判定代码正确或错误
- 自动给出放行/阻断结论
- 完整审计报告
- 完整规则引擎
- 对所有红线约束自动判定
- 替用户决定实现是否符合预期

这些能力未来可以扩展，但前提是基础的代码理解和可视化足够可靠。

## 8. LLM / AI Agent 的必要性

本软件应主要依赖 LLM / AI Agent 完成工程语义理解，纯静态分析只作为证据提取和约束辅助。

纯静态分析可以提取文件、函数、调用、变量、模块、RTL 实例、注释和测试等证据，但它通常只能告诉用户“代码结构是什么”，很难可靠回答“这段实现的工程含义是什么”。例如：

- 哪些函数属于主算法路径
- 哪些类只是配置、工具或资源估算
- 某个变量在算法中代表什么物理含义
- 某段 RTL 对应 Python 阶段中的哪一步
- 某个公式是核心算法还是辅助计算
- 多个阶段之间的实现变化代表什么

因此，本软件的核心能力应来自 LLM / AI Agent 对源码证据的阅读、归纳、组织和解释。静态分析负责把证据准备好、把上下文收集全、把明显结构提取出来；LLM / AI Agent 负责理解工程语义、拼接模块关系、判断主路径与辅助路径、解释公式和信号含义，并把这些内容组织成用户能看懂的可视化结果。

可使用的模型包括 DeepSeek、GLM 或其他可配置模型。无论使用哪种模型，都必须要求模型基于源码证据回答，不能凭空编造。

## 9. 输出内容的期望形态

用户最希望看到的是类似工程师现场阅读代码后画出的说明图和解释，而不是原始代码列表。

理想输出包括：

- 一张或多张主流程图
- 数据流图
- 输入/输出信号表
- 关键中间信号说明
- 模块作用说明
- 关键公式与数据变换
- Q 格式、位宽、定点实现说明
- 阶段差异说明
- 源码证据引用
- 不确定项说明

其中，图形应优先服务于理解。图不是为了“把所有代码节点画出来”，而是为了让用户快速理解实现结构。

## 10. 外部参考项目和调研线索

后续做技术方案时，可以参考外部开源项目和已有调研笔记，但这些参考只用于启发，不应直接决定本项目架构。

本地调研索引位于：

`/Users/ckstar/Documents/Obsidian/techNote/GitHub研究/📌 GitHub研究 总览.md`

其中与本项目方向相关的条目包括：

- `Graphify 分析`：代码库知识图谱，结合本地 AST 与 AI 语义提取，把项目转为可查询图谱。
- `Understand-Anything 分析`：多 Agent 流水线分析代码库，生成交互式知识图谱和 Dashboard。
- `next-ai-draw-io 分析`：AI 图表生成，支持自然语言生成 Draw.io 架构图/流程图。
- `markdown-viewer-skills 分析`：多图表引擎 Skill，可参考其 Markdown 内图表表达能力。
- `AetherViz Master 分析`：AI 生成交互式可视化网页，可参考其“解释性可视化”思路。

外部项目调研时可重点关注：

- 代码库理解和知识图谱工具，例如 Graphify、Understand-Anything、Codebase-Memory。
- AI 生成图表工具，例如 next-ai-draw-io、DeepDiagram、ArchToCode。
- 交互式图形展示工具，例如 React Flow / xyflow、NodeFlow。
- 文本图表与可移植格式，例如 Mermaid、Graphviz、Draw.io XML、PlantUML。

这些项目的参考价值主要在于：

- 如何把代码证据组织成 LLM 能理解的上下文。
- 如何把 LLM 的语义理解转成结构化图形。
- 如何让用户在图中继续 drill down 到源码证据。
- 如何区分主流程、辅助逻辑、输入输出、公式和不确定项。

## 11. 使用边界与安全要求

分析目标项目时必须只读。

基本约束：

- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不泄露 API key。
- API key 不写入日志、报告或提交。
- 默认输出写入 `/tmp` 或 `/private/tmp`。

## 12. 给后续实现者的提醒

本文档只说明项目背景、使用场景和目标，不规定具体架构、数据模型、前端框架或实现方式。

后续实现者需要先基于本文档理解用户需求，再提出技术方案。不要直接假设本项目是传统静态分析工具，也不要一开始就围绕审计结论或规则系统设计。

## 13. 架构规划文档

当前阶段的架构规划沉淀在 `docs/` 目录：

- `docs/agent-first-architecture.md`：Agent-first 总体架构与机制。
- `docs/agent-workflows.md`：UnderstandProject、UnderstandStage、TraceConcept、MapL6ToRTL、ExplainVerification 等核心工作流。
- `docs/semantic-graph-model.md`：ProjectGraph、StageGraph、ConceptGraph、EvidenceGraph、VisualizationSpec 等语义图对象模型。
- `docs/toolbox.md`：未来 Agent 可调用的证据抽取、图谱读写、可视化和 Grounding 检查工具箱。
- `docs/roadmap.md`：从 Understanding Agent 到 Develop-Understand-Verify Agent 的演进路线。

这些文档延续本文档的定位：`fpga_devmind` 应按真正的 Agent 方向设计，普通软件模块只作为 Agent 的确定性基础设施。
