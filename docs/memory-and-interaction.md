# Memory and Interaction

本文定义 `fpga_devmind` 的记忆和交互模型。真正的 Agent 不只是一次性分析器，它需要在多轮问题、用户确认和项目演化中维护语义记忆。

## 三类记忆

### Procedural Memory

程序性记忆记录 Agent 应如何在 FPGA 领域工作。

来源：

- `ai_project_template` 阶段规则。
- `.claude/skills`。
- `.claude/hooks`。
- `.claude/fpga/workflows`。
- L6 到 RTL 开发协议。
- Q 格式、AXIS、PipelineDelay、QInt 等外部模块语义。

用途：

- 判断 L1-L6 各阶段预期职责。
- 解释 `step()`、`AXISPort`、`PipelineDelay` 等模式。
- 约束 Agent 的调查计划。
- 避免把 FPGA 阶段语义当成普通 Python 代码解释。

### Semantic Memory

语义记忆记录项目本身的工程理解。

对象：

- ProjectGraph。
- StageGraph。
- ConceptGraph。
- ImplementationMappingGraph。
- EvidenceGraph。
- VerificationCoverageGraph。
- VisualizationSpec。

用途：

- 支持用户追问。
- 避免每次从零分析。
- 维护跨阶段概念映射。
- 记录源码、RTL、测试、文档证据。

### Episodic Memory

情节记忆记录本次或历史交互中的用户意图、确认和纠偏。

示例：

```text
用户确认：这里的 peak_idx 在当前项目中应解释为 LTS 起点估计，而不是普通峰值索引。

用户纠正：L6 的 FIFO2 不是缓存完整 packet，而是用于 LTS 窗口对齐。
```

用途：

- 后续回答优先使用用户已确认理解。
- 标注哪些解释经过用户确认。
- 保留决策历史。
- 为开发 Agent 后续修正提供上下文。

## 交互模式

`fpga_devmind` 不应只支持一次性命令。它应支持以下交互：

```text
Explain
  解释一个阶段、模块、信号、公式或测试。

Trace
  追踪概念跨阶段演化。

Compare
  比较两个阶段或 L6 与 RTL。

Drill down
  从图中节点进入源码证据。

Clarify
  用户纠正 Agent 的理解。

Confirm
  用户确认某个解释可接受。

Update memory
  把确认或纠偏写入语义记忆。
```

## 用户反馈类型

```text
confirmation
  用户确认解释正确或足够有用。

correction
  用户指出解释错误或概念含义不对。

preference
  用户希望图按某种方式组织。

domain_hint
  用户提供项目背景或算法背景。

decision
  用户基于解释做出下一步开发判断。
```

这些反馈应进入 Episodic Memory，并可影响 Semantic Memory。

## 记忆写入策略

并非所有对话都应写入长期记忆。

建议规则：

```text
write_semantic_memory
  当 Agent 基于证据形成项目语义节点、边或不确定项。

write_episodic_memory
  当用户确认、纠正或提供重要领域背景。

write_procedural_memory
  当 ai_project_template 规则或工作流发生稳定更新。
```

用户纠正应带来源：

```text
source: user_correction
confidence: user_asserted
requires_evidence: true / false
```

如果用户纠正与源码证据冲突，不应静默覆盖，而应生成 `conflicting_evidence`。

## 记忆新鲜度

Semantic Memory 不能被无条件复用。每个图谱节点、边和 claim 都应记录来源快照：

```text
MemoryProvenance
- source_snapshot_id
- source_file_hashes
- graph_schema_version
- tool_version
- model_id
- created_at
- validated_at
- stale_when_source_changed
```

读取记忆时必须先做 freshness check：

```text
1. 重新计算相关源文件 hash。
2. 对比 source_file_hashes。
3. 如果文件变化，标记相关节点为 stale。
4. stale 节点不能作为 strong evidence。
5. 需要重新查证后才能恢复 confirmed / supported 结论。
```

这对 `fpga_project_*` 尤其重要，因为目标项目会持续由 AI agent 或人工修改。没有失效机制，语义图会变成带证据外观的陈旧结论。

## 追问机制

当证据不足时，Agent 可以提出澄清问题，但应优先自查本地上下文。

适合追问的情况：

- 多个工程主线都合理，且选择会影响后续解释。
- 用户问题中的概念名在项目里有多个含义。
- 证据明显冲突，需要用户提供设计意图。

不适合追问的情况：

- 可以通过读取源码、文档、测试解决。
- 只是 Agent 还没有查足证据。
- 问题可以先输出 `unknown` 或 `inferred`。

## 与可视化的关系

交互不是只发生在文字里。未来 UI 应支持：

```text
点击图节点 → 查看 ImplementationView。
点击证据 → 打开源码位置。
点击不确定项 → 查看冲突证据。
用户在节点上确认 / 纠正 → 写入 Episodic Memory。
用户要求重画图 → 更新 VisualizationSpec。
```

这使 `fpga_devmind` 更接近可协作的工程理解 Agent，而不是静态报告工具。
