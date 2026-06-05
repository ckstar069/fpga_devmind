# Runtime Contracts

本文定义 `fpga_devmind` 第一阶段 Agent 运行时的最小结构化契约。目标是防止 ReAct 只停留在叙述层，让计划、工具调用、观察、语义结论、证据和自检都能被图谱和 checker 消费。

## Contract Overview

```text
TaskRequest
  ↓
TaskPlan
  ↓
PlanStep
  ↓
ToolCallRequest
  ↓
ToolObservation
  ↓
CandidateClaim
  ↓
GraphWriteProposal
  ↓
GroundingDiagnostic
  ↓
ReflectionDecision
```

## TaskRequest

```text
TaskRequest
- request_id
- user_intent
- workflow
  - UnderstandProject
  - UnderstandStage
  - TraceConcept
  - MapL6ToRTL
  - ExplainVerification
- project_root
- stage_id
- concept_query
- focus
- constraints
- created_at
```

## TaskPlan

```text
TaskPlan
- plan_id
- request_id
- workflow
- objective
- assumptions
- plan_steps
- evidence_targets
- max_iterations
- stop_conditions
- fallback_strategy
```

`max_iterations` 是硬约束，避免 Agent 无限调查。第一阶段建议默认 8-12 轮 ReAct。

`stop_conditions` 示例：

```text
- required_evidence_collected
- no_new_evidence_found
- max_iterations_reached
- blocking_conflict_found
- user_clarification_required
```

## PlanStep

```text
PlanStep
- step_id
- purpose
- expected_output
- tool_candidates
- required_evidence_types
- depends_on_steps
- status
  - pending
  - running
  - completed
  - skipped
  - failed
```

示例：

```text
purpose: Locate L6 stage implementation for peak_idx.
expected_output: L6 ImplementationView candidates with evidence ids.
tool_candidates:
- scan_project_tree
- extract_python_stage_patterns
required_evidence_types:
- source_code
- comment
```

## ToolCallRequest

```text
ToolCallRequest
- call_id
- step_id
- tool_name
- input
- expected_observation_type
- evidence_id_prefix
- read_only
- safety_constraints
```

安全要求：

```text
read_only: true for all fpga_project_* targets
forbidden:
- Vivado
- synthesis
- implementation
- bitstream
- writing API keys
```

## ToolObservation

```text
ToolObservation
- observation_id
- call_id
- observation_type
  - project_tree
  - python_symbols
  - rtl_modules
  - test_observations
  - docs
  - config
  - graph_query
- summary
- evidence_items
- candidate_symbols
- candidate_edges
- errors
- confidence_hint
```

每个 Observation 必须能追溯到工具调用和输入。

## CandidateClaim

```text
CandidateClaim
- claim_id
- claim_type
  - implementation_claim
  - mapping_claim
  - behavior_claim
  - lineage_claim
  - coverage_claim
  - uncertainty_claim
- statement
- scope
  - project
  - stage
  - concept
  - l6_to_rtl
  - verification
- subject_ids
- evidence_ids
- counter_evidence_ids
- confidence
  - confirmed
  - supported
  - inferred
  - unknown
  - conflicted
- required_missing_evidence
- generated_from_step
```

Claim 是 Agent 输出前的中间结论。所有图谱节点和解释都应从 Claim 生成，而不是直接从自由文本生成。

## GraphWriteProposal

```text
GraphWriteProposal
- proposal_id
- source_claim_ids
- nodes_to_create
- edges_to_create
- evidences_to_create
- uncertainties_to_create
- visualizations_to_create
- stale_nodes_to_mark
- confidence
```

写入前必须经过 Grounding Checker。

## GroundingDiagnostic

```text
GroundingDiagnostic
- diagnostic_id
- target_claim_id
- severity
  - blocking
  - non_blocking
- issue_type
  - missing_evidence
  - weak_mapping
  - single_source_overconfidence
  - conflicting_evidence
  - stale_memory
  - unsupported_claim
  - ambiguous_alias
  - unsafe_scope
- message
- recommended_action
  - collect_more_evidence
  - downgrade_confidence
  - create_uncertainty
  - split_concept
  - mark_conflict
  - refuse_confirmed_claim
  - ask_user_clarification
- related_evidence_ids
```

## ReflectionDecision

```text
ReflectionDecision
- decision_id
- diagnostics
- action
  - continue_collecting
  - revise_claims
  - write_graph
  - downgrade_and_write
  - ask_user
  - stop_insufficient_evidence
- rationale
- next_plan_steps
```

规则：

- `blocking` diagnostic 不能直接进入 confirmed 输出。
- 如果能通过本地证据解决，优先 `continue_collecting`。
- 如果证据不足但已有部分解释，允许 `downgrade_and_write`，同时创建 `UncertaintyNote`。
- 只有用户设计意图会影响解释分支时，才 `ask_user`。

## Claim Confidence Rules

Claim 置信规则在 [Evidence Grounding Policy](evidence-grounding-policy.md) 中定义。运行时必须在 GraphWriteProposal 前执行。

### implementation_claim

用于描述某阶段或某文件实际实现了什么。

`confirmed` 最低要求：

```text
- 至少 1 个 strong source_code 或 rtl evidence。
- claim 的 subject 能定位到具体符号、表达式、module、signal 或 always block。
- 没有 counter_evidence。
```

`supported`：

```text
- 有 strong evidence，但实现范围不完整；或
- 有 medium doc/comment evidence，并被部分 source_code/rtl evidence 支持。
```

`inferred`：

```text
- 主要基于命名、文件结构或上下文推断。
```

### mapping_claim

用于 L5/L6/RTL 或跨阶段概念映射。

`confirmed` 最低要求：

```text
- 至少 2 类互补证据，例如：
  - L6 class/function/state evidence
  - RTL module/signal/instance evidence
  - top-level connection evidence
  - test observation evidence
- 映射关系不只依赖名字相似。
- 没有冲突证据。
```

`supported`：

```text
- 有一侧强证据和另一侧中等证据；或
- 注释声明映射，并有部分结构证据支持。
```

`inferred`：

```text
- 只有命名相似、注释声明或结构相似。
```

### behavior_claim

用于测试、状态机、时序或接口行为解释。

`confirmed` 最低要求：

```text
- 有 test assertion、RTL always/assign、Python step() 或明确状态转移证据。
- 行为的输入条件、输出结果或观测信号明确。
```

`supported`：

```text
- 有测试场景或文档说明，但缺少完整断言或内部观测。
```

`inferred`：

```text
- 仅从测试名、注释或信号名推断行为。
```

### lineage_claim

用于说明代码、模块或概念来自哪里。

`confirmed` 最低要求：

```text
- 有 import/include/copy path、配置文件、显式引用或内容哈希证据。
- resolved_path 明确。
```

`supported`：

```text
- 文档声明来源，并存在相似路径或模块名。
```

`inferred`：

```text
- 只有命名相似或目录相似。
```

### coverage_claim

用于说明测试覆盖了哪些语义节点。

`confirmed` 最低要求：

```text
- 有 TestObservation。
- observed_signal 或 asserted_property 映射到 ConceptNode / ImplementationView。
- coverage_target 明确。
```

`supported`：

```text
- 测试调用了目标模块或函数，但内部语义节点未被直接观测。
```

`inferred`：

```text
- 仅根据测试名称或注释推断覆盖。
```

## Downgrade Rules

任何 claim 遇到以下情况必须降级或转为 `conflicted`：

```text
single_source_overconfidence
  单一证据不足以支撑跨阶段或跨语言映射。

comment_only
  只有注释或文档，没有源码/RTL/测试支持。

ambiguous_alias
  别名可能同名不同义。

stale_memory
  语义记忆依赖的源文件已经变化。

conflicting_evidence
  代码、RTL、文档或测试之间存在冲突。
```

## Runtime Failure Loop

```text
GroundingDiagnostic(blocking)
  ↓
ReflectionDecision
  ↓
collect_more_evidence 或 downgrade_confidence
  ↓
更新 CandidateClaim
  ↓
重新检查
```

这使 Reflection 成为闭环机制，而不是输出前 checklist。

## Memory Freshness

每次读取 Semantic Memory 时必须检查：

```text
- source_snapshot_id
- file_hashes
- graph_schema_version
- tool_version
- model_id
- created_at
- validated_at
```

如果源文件变化，应标注对应节点为 `stale`，并要求重新验证后才能作为强证据使用。
