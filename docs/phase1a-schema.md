# Phase 1a Schema

本文定义 P1a implementation-ready 的最小 JSON schema 草案。正式实现可用 Pydantic 或 JSON Schema 表达，本文先定义字段和约束。

## Artifact Layout

P1a 默认输出：

```text
/tmp/fpga_devmind/p1a_coarse_sync_l6/
- project_graph.json
- summary.md
- flow.mmd
- run_metadata.json
```

`project_graph.json` 是 P1a 的主结构化产物。`summary.md` 和 `flow.mmd` 必须从该结构化产物渲染，不能加入未 grounded 的额外结论。

## ProjectGraphP1a

```text
ProjectGraphP1a
- schema_version
- task_request
- project_profile
- stage
- concepts
- implementation_views
- fixed_point_specs
- stream_interface_specs
- pipeline_timing_specs
- resource_estimate_specs
- evidence_items
- candidate_claims
- grounding_diagnostics
- uncertainty_notes
- visualization_specs
- run_metadata
```

## TaskRequestP1a

```text
TaskRequestP1a
- request_id
- workflow: UnderstandStage
- project_root
- stage_id: L6_resource_opt
- user_intent
- focus
- constraints
```

Constraints:

```text
- read_only_target: true
- forbid_rtl_confirmed_claims: true
- forbid_test_confirmed_claims: true
- forbid_vivado: true
- output_root: /tmp/fpga_devmind/p1a_coarse_sync_l6
```

## ProjectProfileP1a

```text
ProjectProfileP1a
- project_id
- name
- root_path
- layout_type
- stage_coverage
- l6_path
- config_paths
- optional_context_paths
- evidence_ids
- confidence
```

## StageNodeP1a

```text
StageNodeP1a
- stage_id
- stage_name
- expected_role
- actual_role_summary
- source_files
- main_entry_candidates
- selected_main_entries
- key_concept_ids
- implementation_style
- evidence_ids
- uncertainty_ids
- confidence
```

## ConceptNodeP1a

```text
ConceptNodeP1a
- concept_id
- canonical_name
- aliases
- domain_type
  - algorithm_concept
  - signal
  - state
  - formula
  - data_buffer
  - interface
  - fixed_point_format
  - resource
- meaning
- stage_id
- implementation_view_ids
- upstream_concept_ids
- downstream_concept_ids
- evidence_ids
- confidence
```

## ImplementationViewP1a

```text
ImplementationViewP1a
- view_id
- concept_id
- stage_id
- file_path
- symbol_refs
- implementation_kind
  - formula
  - function
  - class
  - pipeline_stage
  - state
  - resource_note
  - interface
- explanation
- input_concept_ids
- output_concept_ids
- fixed_point_spec_ids
- stream_interface_spec_ids
- pipeline_timing_spec_ids
- resource_estimate_spec_ids
- source_claim_ids
- evidence_ids
- confidence
```

## ResourceEstimateSpecP1a

```text
ResourceEstimateSpecP1a
- spec_id
- stage_or_concept_id
- estimate_name
- lut
- ff
- dsp48
- bram18k
- scale_expression
- condition
- target_device
- source_claim_ids
- evidence_ids
- confidence
```

Rules:

```text
- A numeric estimate is supported only when it is extracted from ResourceEstimate(...) source evidence.
- If a value is multiplied by a symbolic parameter, keep the base value and record scale_expression instead of silently evaluating it.
- Conditional branches, such as weight_mode alternatives, must keep condition rather than collapse into one total.
```

## EvidenceItemP1a

```text
EvidenceItemP1a
- evidence_id
- source_type
  - source_code
  - config
  - doc
  - comment
  - external_module
- file_path
- start_line
- end_line
- symbol
- excerpt_summary
- evidence_strength
  - strong
  - medium
  - weak
- snippet_complete
- reliability_note
```

P1a 不使用 RTL/test evidence 生成 confirmed claim。如果读取 RTL/tests，只能标为 weak context 或 future-entry evidence。

## CandidateClaimP1a

```text
CandidateClaimP1a
- claim_id
- claim_type
  - implementation_claim
  - dataflow_claim
  - fixed_point_claim
  - resource_refinement_claim
  - interface_claim
  - pipeline_timing_claim
  - uncertainty_claim
- claim_layer
  - mandatory
  - conditional
  - prohibited
- statement
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
- source_plan_step_id
```

## GroundingDiagnosticP1a

```text
GroundingDiagnosticP1a
- diagnostic_id
- target_claim_id
- target_output_id
- severity
  - blocking
  - non_blocking
- issue_type
  - missing_evidence
  - weak_mapping
  - unsupported_confirmed_claim
  - unsupported_visual_node
  - unsupported_visual_edge
  - unsupported_summary_statement
  - single_source_overconfidence
  - prohibited_claim_source
  - stale_memory
  - conflicting_evidence
- recommended_action
- related_evidence_ids
```

## UncertaintyNoteP1a

```text
UncertaintyNoteP1a
- uncertainty_id
- topic
- scope
- reason
  - missing_evidence
  - ambiguous_main_path
  - comment_code_mismatch
  - not_observed_in_p1a_evidence
  - future_p1b_or_p1c_scope
- current_interpretation
- needed_evidence
- source_claim_ids
- evidence_ids
- severity_for_understanding
```

## VisualizationSpecP1a

```text
VisualizationSpecP1a
- viz_id
- title
- viz_type
  - stage_flow
  - dataflow
- nodes
- edges
- uncertainty_display_policy
- evidence_display_policy
```

每个 node：

```text
- node_id
- label
- kind
- source_concept_id
- source_claim_ids
- evidence_ids
- confidence
```

每条 edge：

```text
- edge_id
- from_node_id
- to_node_id
- label
- source_claim_ids
- evidence_ids
- confidence
```

## Summary Contract

`summary.md` 每个主要段落必须引用 claim ids：

```text
## Stage Purpose
... [C001, C002]

## Main Flow
... [C010-C014]

## Uncertainties
... [U001]
```

Renderer 不得从 LLM 自由文本直接生成未绑定 claim 的结论。

## Evidence Pack Clipping Rules

P1a evidence pack 不得截断：

```text
- 完整 class definition。
- 完整 function / method definition。
- 关键公式所在语句和必要上下文变量定义。
- Q format / width / scale 定义。
- import 语句和本地 external module 来源。
- resource estimate 表达式或表格。
- stage pipeline 类之间的 producer/consumer 关系。
```

如果 token 限制要求裁剪，应先保留：

```text
1. main entry classes/functions。
2. fixed-point / Q format definitions。
3. state / interface / step methods。
4. resource notes backed by executable code or config.
5. comments only after source_code evidence.
```
