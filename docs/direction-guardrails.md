# Direction Guardrails

本文是给后续实现和评审使用的短版方向护栏。详细设计见其他 `docs/*.md`，但任何实现决策都不能偏离本页。

## One Sentence

`fpga_devmind` 是 FPGA 开发-理解一体 Agent 的理解层原型，不是传统静态分析工具、审计工具或报告生成器。

## Must Preserve

- Agent-first：核心是计划、查证据、推理、记忆、grounding、自检、解释和追问。
- LLM / Agent 是主语义理解引擎。
- 静态分析只做证据抽取、索引、约束辅助。
- 结构化产物优先是 graph / claim / evidence，而不是普通报告。
- 输出必须可追溯到 evidence ids。
- 不确定性是一等输出。
- 先理解、建图、解释、可追溯；后续才谈 review / audit。
- `ai_project_template` 是 procedural memory 和领域协议来源。

## Must Avoid

- 退化成“扫描代码 + LLM 总结 + Mermaid”。
- 退化成 AST / 调用图 / 文件依赖图工具。
- 退化成 PASS/HOLD、finding、规则引擎或审计报告。
- 把注释、文档或命名相似当成强证据。
- 把 L6 和 RTL 自动说成等价。
- 为了补全所有维度而无边界扩大分析范围。

## Safety Boundaries

- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado。
- 不运行 synthesis / implementation / bitstream。
- 不泄露 API key。
- API key 不写入日志、报告或提交。
- 默认输出写入 `/tmp` 或 `/private/tmp`。

## Phase 1a North Star

P1a 只证明一个最小闭环：

```text
coarse_sync_glm L6
  → 计划
  → 读取 L6/config 必要证据
  → 生成 claims
  → grounding 检查
  → 写 project_graph.json
  → 从 graph 渲染 summary.md 和 flow.mmd
```

P1a 不做完整跨阶段、RTL 映射或验证覆盖。

## Decision Rule

如果某个实现选择能让系统更像 Agent，就优先考虑。

如果某个实现选择只是让报告更漂亮，但没有增强证据、图谱、记忆或自检，应推迟。
