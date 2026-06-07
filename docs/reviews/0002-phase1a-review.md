# Review 0002: Phase 1a Single Stage Understanding

Date: 2026-06-07

Reviewer: independent Review Agent

## Review Summary

- overall_assessment: P1a 已明显收窄到单项目、单阶段、单问题，方向正确；但还没到“可直接实现”的程度。主要缺口在 schema/tool 契约闭合、P1a 范围分层、grounding checker 可执行规则，以及 L6/coarse sync 专项语义清单。
- main_risks: P1a 仍可能滑向“大量扫描 + LLM 总结”；部分 confirmed 规则存在文档冲突；Graph/Claim/Tool 输出未完全可机器校验；resource refinement、Q format、pipeline、interface 的验收边界不够硬。
- recommended_priority: 先补齐 P1a implementation-ready 最小闭环：schema、工具缺口、claim 分层、Mermaid/summary grounding 检查，再进入编码。

## Findings

### High: P1a scope can still expand

- area: product_scope
- file: `docs/phase1a-single-stage-understanding.md`
- issue: Secondary/external evidence 范围包含 L5、docs、RTL、tests、external modules，required claims 又覆盖 stage purpose、main flow、dataflow、fixed point、resource refinement、interface、uncertainty，实际执行时仍可能膨胀。
- suggested_change: 将 claim 和 evidence 分为 mandatory / conditional / prohibited 三层。RTL/tests 默认禁止进入 confirmed claim，只能产生 future-entry uncertainty。

### High: Schema and tool contracts not closed

- area: docs_consistency
- files: `docs/phase1a-single-stage-understanding.md`, `docs/tool-contracts.md`
- issue: Agent Plan 使用 `extract_parameters`，但 tool contracts 未定义该工具；Graph Output 中的 ProjectProfile、StageNode、ConceptNode、ImplementationView、VisualizationSpec 等也未在本组文档内给出 P1a 可执行 schema。
- suggested_change: 补 `p1a-schema.md`，至少定义 TaskRequest、CandidateClaim、EvidenceItem、StageNode、ConceptNode、ImplementationView、VisualizationSpec、UncertaintyNote，并补齐 `extract_parameters`。

### High: Resource refinement confirmed rule is too loose

- area: grounding
- files: `docs/phase1a-single-stage-understanding.md`, `docs/evidence-grounding-policy.md`
- issue: `resource_refinement_claim confirmed` 允许 “L6 source_code 或明确 resource note strong/medium evidence”，但 confirmed 应至少需要 strong evidence。
- suggested_change: 只有执行逻辑、配置参数、资源估算表达式或结构化 resource table 可支撑 confirmed；仅 doc/comment/resource note 最多 supported。

### Medium: Reflection loop not mandatory in P1a

- area: agent_architecture
- files: `docs/phase1a-single-stage-understanding.md`, `docs/runtime-contracts.md`
- issue: P1a Agent Plan 基本是一遍 scan/extract/check/write/render，没有把 diagnostics → reflection → collect/downgrade → recheck 作为必经闭环。
- suggested_change: 在 P1a TaskPlan 中加入必需循环。

### Medium: coarse_sync L6 checklist missing

- area: fpga_domain
- files: `docs/domain-semantics.md`, `docs/phase1a-single-stage-understanding.md`
- issue: 对 `coarse_sync_glm` L6 的专项语义仍偏通用，没有定义 S0/S1/S2/S3、metric、peak_idx、归一化、reciprocal/LUT、延迟对齐、valid 传播等 P1a 检查清单。
- suggested_change: 增加 `P1aCoarseSyncDomainChecklist`。

### Medium: visual and summary grounding missing

- area: grounding
- file: `docs/phase1a-single-stage-understanding.md`
- issue: 没有明确 summary.md 和 flow.mmd 中每个主要节点、边、标签必须可追溯到 claim_id/evidence_id。
- suggested_change: VisualizationSpec node/edge 带 `source_claim_ids` 和 `evidence_ids`；summary 每个主要段落引用 claim ids。

### Medium: python extraction lacks semantic events

- area: agent_architecture
- files: `docs/tool-contracts.md`, `docs/phase1a-single-stage-understanding.md`
- issue: `extract_python_stage_patterns` 没有明确 def-use、producer/consumer、state transition、valid propagation、Q operation width-growth 的结构化输出。
- suggested_change: 扩展工具输出 `dataflow_edges`、`state_transitions`、`interface_events`、`q_operations`、`width_growth_events`、`pipeline_events`。

### Low: acceptance criteria inconsistent

- area: docs_consistency
- files: `docs/phase1-scope.md`, `docs/phase1a-single-stage-understanding.md`
- issue: P1a 验收维度口径不一致。
- suggested_change: 统一为验收矩阵：main path 必须有；auxiliary/resource refinement 必须区分；fixed-point/interface/pipeline 按证据存在情况输出或标 unknown。

## Open Questions

- 如果 L6 中没有显式 Q format、AXIS/valid-ready 或 pipeline latency，P1a 是通过并输出 unknown，还是验收失败？
- P1a graph artifact 的最终落盘格式是 JSON、JSONL、SQLite、Markdown frontmatter，还是图数据库导出？
- RTL/tests 在 P1a 中到底是默认禁止、按需允许，还是仅可用于 uncertainty？
- evidence pack token 裁剪策略如何保证不截断函数、公式上下文和 Q/width 定义？

## Positive Notes

- 固定 `fpga_project_coarse_sync_glm` + `L6_resource_opt` 是正确收窄。
- Claim-first、GraphWriteProposal 前 grounding check、unsupported confirmed claim 为 0 的方向正确。
- 不确定项作为一等输出是必要设计。
- 只读目标项目、不运行 Vivado/synthesis/implementation/bitstream 的边界清楚。
