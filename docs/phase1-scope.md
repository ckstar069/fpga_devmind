# Phase 1 Scope

Review 0001 指出 Phase 1 范围过大。本文将 Phase 1 收窄为可验收的 Understanding Agent 切片，避免一开始做成“大而全图谱平台”。

## Phase 1 Goal

Phase 1 的目标不是完成全部工作流，而是证明：

```text
fpga_devmind 能基于证据完成一次真实 FPGA 项目的 Agent-style 理解闭环：
计划 → 查证据 → 推理 → 写语义图 → grounding 检查 → 输出图和解释。
```

## P1a: Single Stage Understanding

目标：分析一个真实项目的单个阶段，生成 evidence-grounded Mermaid 和解释。

详细规格见 [Phase 1a: Single Stage Understanding](phase1a-single-stage-understanding.md)。

推荐样例：

```text
project: fpga_project_coarse_sync_glm
stage: L6_resource_opt
question: L6 资源优化阶段实际实现了什么？
```

原因：

- L6 有明确资源化语义。
- coarse sync 有 S0-S3 多 stage 结构。
- 适合验证主流程、数据流、Q 格式、资源化说明和不确定项。

输出：

```text
StageNode
ConceptNodes
ImplementationViews
EvidenceItems
CandidateClaims
GroundingDiagnostics
VisualizationSpec
summary.md
flow.mmd
```

验收指标：

```text
- 主要处理路径节点有 evidence ids。
- 至少区分 main path / auxiliary logic / resource refinement。
- 每个 confirmed claim 至少有符合 claim_type 规则的证据组合。
- unsupported confirmed claim 数量为 0。
- 不确定项明确列出。
```

## P1b: One Concept L5-L6-RTL Trace

目标：追踪一个概念从 L5/L6 到 RTL 的映射。

推荐样例：

```text
project: fpga_project_coarse_sync_glm
concept: peak_idx 或 metric
question: 这个概念如何从 L5/L6 映射到 RTL？哪些 RTL 细节是资源化细化？
```

备选样例：

```text
project: fpga_project_fine_cfo
concept: lts_start
question: lts_start 在 L1/L4/L6/RTL 中如何演化？
```

输出：

```text
ConceptNode
ImplementationViews by stage
L6-to-RTL mapping edges
RTLSignalSpec
FixedPointSpec / PipelineTimingSpec if applicable
EvidenceTraceGraph
UncertaintyNotes
```

验收指标：

```text
- 别名映射不只基于名字相似。
- L6-to-RTL mapping claim 使用 mapping_claim 规则判定。
- RTL-only / resource refinement 节点单独标注。
- weak mapping 必须降级为 inferred 或 supported。
- 至少生成一张 Concept Evolution Graph 或 L6-to-RTL Mapping Graph。
```

## P1c: Verification Coverage Slice

目标：解释测试覆盖了哪些语义节点，而不是只报告测试是否存在。

推荐样例：

```text
project: fpga_project_coarse_sync_glm
test: cocotb test_coarse_sync.py
question: cocotb 覆盖了 S0/S1/S2/S3 哪些语义节点？
```

输出：

```text
TestObservation
VerificationCoverageGraph
covered_concepts
covered_signals
coverage_limitations
```

验收指标：

```text
- 区分 stimulus、observed_signal、asserted_property、coverage_target。
- 不把测试名称当成覆盖证据。
- black-box coverage 和 internal signal coverage 分开标注。
- 未观察的重要语义节点列出。
```

## P1 Not Included

Phase 1 不做：

- 全部 `fpga_project_*` 自动支持。
- 完整交互式 UI。
- 自动审计结论。
- PASS / HOLD。
- finding 主体输出。
- Vivado / synthesis / implementation / bitstream。
- 自动修改目标项目。

## Sample Question Set

第一批验收问题：

```text
1. coarse_sync_glm 的 L6 做了什么？
2. coarse_sync_glm 的 peak_idx 如何从 L6 映射到 RTL？
3. coarse_sync_glm 的 RTL 中哪些 S0-S3 信号被 cocotb 观察？
4. fine_cfo 的 lts_start 在 L1/L4/L6/RTL 中如何演化？
```

这些问题覆盖：

- single-stage understanding。
- concept trace。
- L6-to-RTL mapping。
- verification coverage。
- source evidence and uncertainty。

## Quality Metrics

建议质量指标：

```text
evidence_coverage_rate
  主要 claim 中带 evidence_ids 的比例。

unsupported_confirmed_claim_count
  没有足够证据却被标为 confirmed 的 claim 数量，应为 0。

uncertainty_capture_count
  显式标注的不确定或冲突数量。

mapping_precision_sampled
  人工抽样检查 L6-to-RTL mapping 的准确率。

visualization_edge_completeness
  图中孤立主节点数量，应尽量为 0。

memory_freshness_check_rate
  使用已有语义记忆前执行 freshness check 的比例。
```

这些指标用于判断 Agent 是否比一次性 LLM 总结更可靠。
