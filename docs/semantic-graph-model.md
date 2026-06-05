# Semantic Graph Model

本文定义 `fpga_devmind` 的语义记忆草案。它服务 Agent 工作流，而不是替代 Agent。

## 顶层结构

```text
ProjectGraph
- project_profile
- stages
- concepts
- implementation_views
- evidences
- edges
- uncertainties
- visualizations
```

## ProjectProfile

描述 FPGA 项目在生态中的身份和入口。

```text
ProjectProfile
- project_id
- name
- root_path
- project_role
  - algorithm_source
  - fpga_application
  - reusable_ip
  - system_assembly
  - unknown
- layout_type
  - ai_project_template_stage_layout
  - flat_package
  - package_dir_mapping
  - mixed
  - unknown
- stage_coverage
- active_stage_hint
- parameter_sources
- external_sources
- rtl_locations
- test_locations
- confidence
- evidence_ids
```

## StageNode

描述一个阶段的职责、代码入口和实际实现内容。

```text
StageNode
- stage_id
- stage_name
- expected_role
  - prototype
  - structured
  - pipeline
  - cycle_accurate
  - fixed_point
  - resource_optimized
  - rtl
- actual_role_summary
- source_files
- main_entry_candidates
- related_tests
- related_docs
- external_dependencies
- key_concepts
- implementation_style
- confidence
- evidence_ids
- uncertainty_ids
```

`expected_role` 来自 `ai_project_template` 阶段语义；`actual_role_summary` 来自源码理解。两者必须分开，因为 AI agent 生成的阶段代码可能偏离阶段职责。

## ConceptNode

描述工程概念，而不是代码符号。

```text
ConceptNode
- concept_id
- canonical_name
- aliases
- domain_type
  - algorithm_concept
  - signal
  - state
  - module
  - formula
  - data_buffer
  - interface
  - fixed_point_format
  - resource
- meaning
- appears_in_stages
- implementation_views
- upstream_concepts
- downstream_concepts
- confidence
- evidence_ids
```

示例：

```text
canonical_name: lts_start
aliases:
- lts_start
- o_lts_start
- result_lts_start_r
- fpd_lts_start_capture_r
```

## ImplementationView

描述某个概念在某个阶段或文件里的具体实现方式。

```text
ImplementationView
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
  - fsm_state
  - register
  - rtl_module
  - rtl_signal
  - test_observation
- explanation
- inputs
- outputs
- transformations
- timing_behavior
- fixed_point_behavior
- resource_notes
- evidence_ids
- confidence
```

例如 CFO 在 L1 是公式，在 L5 是 Q integer + CORDIC，在 RTL 是多个 module、wire、reg、always block 的组合。它们属于同一工程概念的不同实现视图。

## EvidenceItem

所有结论必须绑定证据。

```text
EvidenceItem
- evidence_id
- source_type
  - source_code
  - rtl
  - test
  - doc
  - config
  - comment
  - report
- file_path
- start_line
- end_line
- symbol
- excerpt_summary
- evidence_strength
  - strong
  - medium
  - weak
- reliability_note
```

证据强度建议：

- `strong`：源码实现、RTL 实现、测试断言、配置值。
- `medium`：设计文档、阶段说明、RTL 头注释。
- `weak`：普通注释、文件名、命名推断、未交叉验证说明。

## GraphEdge

统一表达概念、阶段、实现、证据之间的关系。

```text
GraphEdge
- edge_id
- from_id
- to_id
- relation_type
  - evolves_to
  - implements
  - refines
  - maps_to
  - depends_on
  - produces
  - consumes
  - verifies
  - cites
  - conflicts_with
  - inferred_from
  - covers
  - missing_mapping
  - rtl_refinement
- label
- confidence
- evidence_ids
```

示例：

```text
L5 CFO fixed-point view --refines--> L4 CFO float view
L6 S0 class --maps_to--> RTL s0 module
cocotb assertion --verifies--> RTL o_lts_start behavior
doc dual FIFO section --cites--> L6 FIFO concept
```

## UncertaintyNote

不确定性是一等对象。

```text
UncertaintyNote
- uncertainty_id
- topic
- scope
  - project
  - stage
  - concept
  - implementation_view
  - mapping
- reason
  - missing_evidence
  - conflicting_evidence
  - naming_ambiguity
  - layout_drift
  - comment_code_mismatch
  - inferred_only
- current_interpretation
- needed_evidence
- severity_for_understanding
  - low
  - medium
  - high
```

例如 L6 注释说“算法与 L5 一致”，但代码实际引入资源化 shift / align / divide，应标注为实现细化或注释-代码漂移，而不是简单判断等价或不等价。

## VisualizationSpec

图从语义图生成，不直接从源码生成。

```text
VisualizationSpec
- viz_id
- title
- viz_type
  - stage_evolution
  - algorithm_flow
  - dataflow
  - pipeline_timing
  - fixed_point_path
  - rtl_mapping
  - verification_coverage
  - evidence_trace
- root_nodes
- included_edge_types
- layout_hint
- node_label_policy
- evidence_display_policy
- uncertainty_display_policy
```

第一批重要图：

- Stage Evolution Graph。
- Concept Mapping Graph。
- Dataflow Graph。
- L6-to-RTL Mapping Graph。
- Verification Coverage Graph。
