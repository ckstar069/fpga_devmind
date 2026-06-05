# FPGA Domain Semantics

本文补充 `fpga_devmind` 的 FPGA 领域结构化对象。它们用于约束 LLM 理解 L5 fixed-point、L6 cycle/resource model、RTL 映射和测试覆盖，避免自由文本解释过度。

## StageContract

`StageContract` 描述每个阶段的预期职责和证据优先级。

```text
StageContract
- stage_id
- expected_role
- expected_artifacts
- typical_entrypoints
- expected_abstractions
- key_domain_patterns
- evidence_priorities
- forbidden_assumptions
- known_template_conventions
```

示例：

```text
L5_fixedpoint
- expected_role: fixed_point
- expected_artifacts:
  - fixed-point Python model
  - Q format definitions
  - quantization / saturation behavior
  - fixed-point tests or cross-compare
- key_domain_patterns:
  - QInt
  - QFormat
  - shift / scale / truncate / saturate
  - integer multiply width growth
- forbidden_assumptions:
  - Do not assume L5 is equivalent to L4 without evidence.
  - Do not treat float expressions as fixed-point behavior.
```

```text
L6_resource_opt
- expected_role: resource_optimized
- expected_artifacts:
  - step() cycle model
  - state / interface exposure
  - resource notes
  - pipeline latency or schedule
- key_domain_patterns:
  - AXISPort
  - PipelineDelay
  - get_state
  - get_interface_state
  - resource estimate
- forbidden_assumptions:
  - Do not assume L6 adds no behavior just because comments say algorithm is unchanged.
```

## FixedPointSpec

```text
FixedPointSpec
- spec_id
- signal_or_concept_id
- q_format
- signedness
- total_bits
- integer_bits
- fractional_bits
- scale
- rounding_mode
- overflow_mode
  - wrap
  - saturate
  - truncate
  - unknown
- width_growth_rule
- shift_or_alignment
- source_evidence_ids
- confidence
```

用途：

- 表达 Q1.11、Q3.11、Q6.10 等格式。
- 记录乘法、累加、移位、截断、饱和。
- 支持 L5/L6/RTL 内部位宽差异解释。

## StreamInterfaceSpec

```text
StreamInterfaceSpec
- interface_id
- protocol
  - axis_valid_only
  - axis_valid_ready
  - custom_stream
  - unknown
- data_signal
- valid_signal
- ready_signal
- last_signal
- sideband_signals
- producer
- consumer
- valid_condition
- ready_backpressure_behavior
- packet_boundary_behavior
- source_evidence_ids
- confidence
```

用途：

- 解释 AXIS / valid / ready / last。
- 区分 valid-only stream 和 valid-ready stream。
- 表达 packet boundary、LTS start、frame reset 等语义。

## PipelineTimingSpec

```text
PipelineTimingSpec
- timing_id
- stage_or_module_id
- latency_cycles
- input_cycle
- output_cycle
- register_boundaries
- alignment_requirements
- valid_propagation
- reset_behavior
- clock_domain
- source_evidence_ids
- confidence
```

用途：

- 表达 L3/L4/L6 pipeline stage。
- 解释 PipelineDelay、cycle-accurate step、RTL registers。
- 标注 latency 不确定或 L6/RTL 对齐差异。

## FSMBehaviorSpec

```text
FSMBehaviorSpec
- fsm_id
- owner_view_id
- states
- initial_state
- transitions
- transition_conditions
- outputs_by_state
- reset_behavior
- source_evidence_ids
- confidence
```

用途：

- 表达 L4/L6/RTL 状态机。
- 把 Python 状态变量与 RTL state register 对齐。
- 支持 “state maps_to RTL signal” 的证据约束。

## RTLSignalSpec

```text
RTLSignalSpec
- signal_id
- module_id
- name
- direction
- width
- signedness
- kind
  - port
  - wire
  - reg
  - parameter
  - localparam
- driver
- consumers
- reset_value
- clocked
- bit_slices
- source_evidence_ids
- confidence
```

用途：

- 支持 RTL module/signal/FSM 映射。
- 避免只用信号名推断语义。
- 支持 signal producer/consumer dataflow。

## TestObservation

```text
TestObservation
- observation_id
- test_file
- test_name
- test_type
  - pytest
  - cross_compare
  - cocotb
  - script
- stimulus_summary
- clock_reset_setup
- dut_path
- sample_time_or_cycle
- observed_signal
- asserted_property
- expected_value
- expected_value_source
- coverage_target
- coverage_limitations
- behavior_claim_ids
- source_evidence_ids
- confidence
```

用途：

- 区分测试输入、观测点、断言和覆盖目标。
- 防止把“测试名包含 CFO”误读为“覆盖 CFO 算法语义”。
- 支持 VerificationCoverageGraph。

## SourceLineage

```text
SourceLineageNode
- lineage_id
- source_kind
  - ai_project_template
  - project_local
  - urban_wireless
  - module_project
  - fpga_project_dependency
  - historical_module
  - unknown
- source_root
- module_name
- resolved_path
- package_or_import_name
- content_hash
- local_modification_hint
- evidence_ids
- confidence
```

```text
SourceLineageEdge
- edge_id
- from_lineage_id
- to_lineage_id
- relation_type
  - imports
  - copies
  - vendors
  - references
  - rewrites
  - wraps
  - derives_from
- precedence
- evidence_ids
- confidence
```

用途：

- 追踪 `urban_wireless` 算法包到 L0 本地化，再到 L1-L6/RTL 的演化。
- 区分模板公共模块、项目本地模块和外部 IP。
- 识别本地改写和来源漂移。

## Relation to Semantic Graph

这些领域对象不替代 `ConceptNode` 或 `ImplementationView`，而是作为附加结构绑定到实现视图：

```text
ImplementationView
- fixed_point_specs
- stream_interface_specs
- pipeline_timing_specs
- fsm_behavior_specs
- rtl_signal_specs
- test_observations
- source_lineage_refs
```

这样 Agent 可以同时输出自然语言解释和结构化证据约束。
