# Tool Contracts

本文定义第一批确定性工具的 JSON-like 接口契约。它们服务 Agent runtime，不直接产生最终工程语义结论。

## Common Rules

所有工具输出必须包含：

```text
- tool_name
- call_id
- status
  - ok
  - partial
  - error
- input_summary
- observations
- evidence_items
- errors
- warnings
```

所有目标 `fpga_project_*` 访问必须只读。

所有 evidence id 应稳定、可追溯：

```text
E:<tool_short_name>:<file_hash_prefix>:<line_start>-<line_end>:<ordinal>
```

示例：

```text
E:py_stage:a1b2c3d4:42-78:001
E:rtl_mod:9f88e123:10-120:002
```

## scan_project_tree

输入：

```text
ScanProjectTreeInput
- project_root
- max_depth
- include_patterns
- exclude_patterns
```

输出：

```text
ScanProjectTreeOutput
- layout_hints
- stage_directories
- rtl_locations
- test_locations
- docs_locations
- config_locations
- external_module_locations
- package_roots
- evidence_items
- warnings
```

错误模式：

```text
- project_root_missing
- permission_denied
- unsafe_target
```

## extract_python_stage_patterns

输入：

```text
ExtractPythonStagePatternsInput
- files
- stage_id
- project_root
- include_source_snippets
```

输出：

```text
ExtractPythonStagePatternsOutput
- classes
- functions
- methods
- imports
- call_edges
- constants
- formulas
- q_format_candidates
- step_candidates
- process_block_candidates
- state_candidates
- interface_candidates
- pipeline_delay_candidates
- evidence_items
- warnings
```

每个 symbol 输出至少包含：

```text
- name
- qualified_name
- file_path
- start_line
- end_line
- role_hint
- evidence_ids
```

## extract_rtl_instances

输入：

```text
ExtractRTLInstancesInput
- rtl_files
- top_module_hint
- include_signals
```

输出：

```text
ExtractRTLInstancesOutput
- modules
- ports
- parameters
- signals
- assigns
- always_blocks
- instances
- fsm_candidates
- bit_slice_candidates
- evidence_items
- warnings
```

每个 instance 输出：

```text
- instance_name
- module_name
- parent_module
- connections
- file_path
- start_line
- end_line
- evidence_ids
```

## extract_cocotb_evidence

输入：

```text
ExtractCocotbEvidenceInput
- test_files
- project_root
- dut_name_hint
```

输出：

```text
ExtractCocotbEvidenceOutput
- tests
- test_observations
- clock_reset_setups
- dut_signal_accesses
- assertions
- stimulus_summaries
- coverage_targets
- evidence_items
- warnings
```

每个 `test_observation` 应可映射到 [TestObservation](domain-semantics.md)：

```text
- test_name
- dut_path
- observed_signal
- asserted_property
- expected_value
- sample_time_or_cycle
- coverage_limitations
- evidence_ids
```

## query_template_rules

输入：

```text
QueryTemplateRulesInput
- template_root
- stage_id
- rule_scope
  - stage_contract
  - skills
  - hooks
  - workflows
  - external_modules
```

输出：

```text
QueryTemplateRulesOutput
- template_version_hint
- matched_rules
- stage_contract_candidates
- procedural_memory_items
- evidence_items
- warnings
```

该工具用于 Procedural Memory，不应用来直接判断目标项目正确或错误。

## write_graph_memory

输入：

```text
WriteGraphMemoryInput
- graph_store_path
- graph_write_proposal
- provenance
- allow_overwrite
```

输出：

```text
WriteGraphMemoryOutput
- written_nodes
- written_edges
- written_evidence
- written_uncertainties
- stale_nodes_marked
- rejected_writes
- warnings
```

写入前要求：

```text
- GroundingDiagnostic 已处理。
- blocking diagnostics 不存在，或已降级为 UncertaintyNote。
- source_snapshot_id 已记录。
```

## check_evidence_coverage

输入：

```text
CheckEvidenceCoverageInput
- candidate_claims
- evidence_items
- graph_memory_context
```

输出：

```text
CheckEvidenceCoverageOutput
- diagnostics
- claim_confidence_updates
- required_missing_evidence
- recommended_next_steps
```

输出 diagnostics 应符合 [Runtime Contracts](runtime-contracts.md) 中的 `GroundingDiagnostic`。

## Snippet Boundary Rules

证据片段应尽量小，但必须包含完整语义：

```text
Python function / method:
  包含 def line 到函数结束。

Python formula:
  包含表达式所在语句和必要上下文变量定义。

RTL module:
  module header、ports、相关 signal、相关 always/assign 或 instance。

cocotb assertion:
  包含 stimulus、observed signal、assertion、expected value 来源。
```

避免把整文件作为单个 evidence，除非文件本身很短且不可切分。
