# Phase 1a: Single Stage Understanding

本文定义 `fpga_devmind` 第一阶段的第一个可验收切片：单项目、单阶段、证据约束的 Understanding Agent 闭环。

## Objective

P1a 目标：

```text
让 fpga_devmind 针对一个真实 FPGA 项目的一个阶段，完成：
计划 → 查证据 → 形成 claim → 写语义图 → grounding 检查 → 生成解释和 Mermaid 图。
```

P1a 不是完整产品，也不是审计工具。它只证明 `fpga_devmind` 可以作为 Agent 而不是一次性报告生成器工作。

## Target Slice

主样例：

```text
project_root:
  /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm

stage:
  L6_resource_opt

question:
  L6 资源优化阶段实际实现了什么？
```

选择该样例的原因：

- `coarse_sync_glm` 有清晰的 coarse sync 算法语义。
- L6 阶段包含资源优化、定点、stage pipeline 等硬件化语义。
- 该项目的主线可抽象为 S0/S1/S2/S3，适合验证流程图和数据流图。
- P1a 暂不要求完整 L6-to-RTL 映射，但允许把 RTL 作为弱辅助证据或后续 P1b 入口。

Smoke 样例：

```text
project_root:
  /Users/ckstar/Repo/znxt_ofdm/fpga_project_fine_cfo

stage:
  L6_resource_opt
```

使用第二样例的目的不是扩展成“支持所有项目”，而是防止 P1a 过拟合 `coarse_sync_glm` 的 S0/S1/S2/S3 结构。`fine_cfo` 的 L6 使用 streaming correlator、FPD、CFO、FIFO 和 pipeline top 等不同组织方式，适合检验 generic concept inference、trace 和 query 是否仍然 grounded。

## Out of Scope

P1a 不做：

- 自动支持所有 `fpga_project_*`。
- 完整跨阶段追踪。
- 完整 L6-to-RTL 映射。
- cocotb 覆盖解释。
- 交互式 UI。
- 自动审计结论。
- PASS / HOLD。
- finding 主体输出。
- Vivado / synthesis / implementation / bitstream。
- 修改目标项目。

P1a 允许一个确定性的查询壳读取已生成的语义图和 trace index。这属于 Human Interaction Layer 的最小原型，不等同于完整 UI 或 LLM Agent。

## Inputs

```text
TaskRequest
- workflow: UnderstandStage
- project_root: /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm
- stage_id: L6_resource_opt
- user_intent: Explain what the L6 resource optimized stage actually implements.
- focus:
  - main processing flow
  - dataflow
  - fixed-point / Q format
  - resource refinement
  - uncertainties
```

## Evidence Plan

P1a 使用三层证据边界，避免滑入跨阶段、RTL 或验证分析。

```text
mandatory
  必须读取，用于 confirmed claim。

conditional
  只有在 mandatory evidence 无法解释 L6 本身时读取；通常不能单独生成 confirmed claim。

prohibited_for_confirmed
  可以作为 future-entry uncertainty 或后续 P1b/P1c 入口，但不能用于 P1a confirmed claim。
```

### Primary Evidence

Agent 必须优先读取：

```text
<project>/src/python_model/L6_resource_opt/
<project>/config/
```

目标证据：

- L6 顶层文件。
- S0/S1/S2/S3 或等价 stage 类/函数；若不存在该模式，应从 L6 public classes / pipeline classes 中提取 grounded implementation concepts。
- `step()`、`process_block()`、状态变量、接口定义。
- Q 格式、位宽、shift、scale、truncate、saturate。
- resource notes、DSP、LUT、latency、pipeline 信息。
- 项目参数。

### Secondary Evidence

Conditional evidence：

```text
<project>/src/python_model/L5_fixedpoint/
<project>/docs/
```

用途：

- L5 用于理解 L6 相比 fixed-point 阶段的资源化变化，但 P1a 不做完整跨阶段映射。
- docs 用于补充架构说明，但不能单独作为强证据。

### Prohibited for Confirmed Claims

P1a 默认不使用以下证据生成 `confirmed` claim：

```text
<project>/src/verilog_model/rtl/
<project>/tests/
```

用途仅限：

- 生成 future-entry uncertainty。
- 说明 P1b/P1c 后续入口。
- 作为 weak context，不确认 L6 行为。

### External Evidence

必要时可读取：

```text
/Users/ckstar/Repo/znxt_ofdm/ai_project_template/external_modules/
<project>/external_modules/
/Users/ckstar/Repo/znxt_ofdm/urban_wireless/module_projects/
```

用途：

- 解释 QInt、QFormat、AXISPort、PipelineDelay。
- 识别 L0 来源链。
- 解释外部 CORDIC、DSP、LUT 或 shared modules。

P1a 只做必要引用，不做完整 SourceLineageGraph。

## Agent Plan

最小 TaskPlan：

```text
1. scan_project_tree
   确认项目布局、L6 目录、config、docs、tests、RTL 是否存在。

2. extract_python_stage_patterns on L6
   提取 L6 class/function/step/state/Q format/resource/pipeline 候选。

3. extract_parameters
   读取配置参数和 Q 格式上下文。

4. optional query_template_rules
   查询 L6 StageContract 和相关 procedural memory。

5. optional inspect L5/docs
   仅在解释 L6 resource refinement 需要上下文时读取。

6. generate CandidateClaims
   形成 implementation_claim、resource_refinement claim、uncertainty_claim。

7. run check_evidence_coverage
   检查 claim 是否满足 evidence 规则。

8. reflection loop
   对 GroundingDiagnostic 执行 collect_more_evidence / downgrade_confidence / create_uncertainty / stop_insufficient_evidence。

9. recheck claims
   只有 unsupported_confirmed_claim_count = 0 且无 blocking diagnostic 才进入写图。

10. write GraphWriteProposal
   写 StageNode、ConceptNode、ImplementationView、EvidenceItem、UncertaintyNote、VisualizationSpec。

11. render summary.md and flow.mmd
   从图谱生成解释和 Mermaid。

12. answer p1a-query
   从 ProjectGraph 和 TraceIndex 回答阶段流程、资源估计、定点、接口、时序、claim/evidence drill-down。
```

每轮 ReAct 必须记录：

```text
- plan_step
- tool_observation
- claim_delta
- grounding_diagnostics
- reflection_decision
```

## Required Claims

P1a claim 分为 mandatory、conditional、prohibited 三层。

### Mandatory Claims

必须尝试生成：

```text
stage_purpose_claim
  L6 阶段整体实现目的。

main_flow_claims
  主处理路径的阶段或模块节点。

dataflow_claims
  输入、中间数据、输出之间的主要流向。

uncertainty_claims
  证据不足、注释与代码不完全一致、主入口不明确等。
```

### Conditional Claims

仅当 L6 evidence 中实际出现对应内容时生成；没有出现时输出 `unknown` 或 `not_observed_in_p1a_evidence`，不视为验收失败。

```text
fixed_point_claims
  Q 格式、位宽、定点运算、缩放或截断。


resource_refinement_claims
  DSP、LUT、reciprocal、pipeline、资源复用或延迟相关细化。

interface_claims
  L6 输入输出接口和 valid / ready / data / state 行为。
```

### Prohibited Claims

P1a 不生成：

```text
rtl_mapping_claim
verification_coverage_claim
cross_stage_equivalence_claim
```

## Claim Confidence Requirements

使用 [Runtime Contracts](runtime-contracts.md) 中的 claim rules。

P1a 额外约束：

```text
implementation_claim
  confirmed 需要 L6 source_code strong evidence。

fixed_point_claim
  confirmed 需要明确 Q format、位宽或运算证据。

resource_refinement_claim
  confirmed 需要 L6 executable source_code、配置参数、资源估算表达式或结构化 resource table。
  仅 doc/comment/resource note 最多 supported。

dataflow_claim
  confirmed 需要 producer/consumer 或函数输入输出证据。

interface_claim
  confirmed 需要 port/state/interface symbol evidence。

uncertainty_claim
  可以来自 missing_evidence、ambiguous_main_path、comment_code_mismatch。
```

禁止：

```text
- 只有文件名就 confirmed。
- 只有注释就 confirmed。
- 只有 L5 或 RTL 证据就确认 L6 行为。
- 把 L6 和 RTL 自动说成等价。
- 用 RTL/tests 证据生成 P1a confirmed claim。
```

## P1a Coarse Sync Domain Checklist

Agent 应检查以下 coarse sync L6 候选语义，并为每项输出 `confirmed`、`supported`、`inferred`、`unknown` 或 `not_observed_in_p1a_evidence`。

```text
expected_stage_concepts
- S0 autocorrelation / normalization candidate
- S1 merge candidate
- S2 smooth / peak detect candidate
- S3 CFO candidate

expected_algorithm_concepts
- metric
- peak_idx
- cfo
- autocorrelation
- normalization
- smoothing / moving average
- detection threshold

fixed_point_markers
- Q format
- signedness
- width growth
- shift / alignment
- truncate / saturate

resource_refinement_markers
- DSP / multiplier reuse
- LUT
- reciprocal / divide approximation
- pipeline latency
- resource estimate

interface_timing_markers
- valid propagation
- state exposure
- step() cycle behavior
- reset behavior
- producer / consumer alignment
```

Checklist 项不能直接成为事实。每项都必须通过 L6 evidence 生成 claim，或输出 unknown。

## Graph Output Contract

P1a 必须生成：

```text
ProjectProfile
  最小项目画像。

StageNode
  L6_resource_opt 的 expected_role 与 actual_role_summary。

ConceptNode[]
  至少包含主流程概念、输入输出概念、固定点/资源化关键概念。

ImplementationView[]
  每个主流程概念在 L6 中的实现视图。

FixedPointSpec[]
  如果 L6 中存在 Q format 或定点运算。

PipelineTimingSpec[]
  如果 L6 中存在 stage latency、PipelineDelay 或 cycle behavior。

StreamInterfaceSpec[]
  如果 L6 中存在 AXIS 或 valid/ready/valid-only 接口。

EvidenceItem[]
  所有主要 claim 的证据锚点。

CandidateClaim[]
  Agent 推理中间结论。

GroundingDiagnostic[]
  自检结果。

UncertaintyNote[]
  不确定项。

VisualizationSpec[]
  至少包含 stage_flow 或 dataflow。
```

P1a 可以暂不生成：

```text
Full Concept Evolution Graph
Full L6-to-RTL Mapping Graph
Full VerificationCoverageGraph
```

## Visual Output

P1a 至少生成两类展示：

```text
summary.md
  自然语言解释：
  - L6 阶段目的
  - 主处理流程
  - 输入输出和中间数据
  - 定点 / Q 格式 / 位宽
  - 资源化细节
  - 证据引用
  - 不确定项

flow.mmd
  Mermaid flowchart：
  - 输入节点
  - S0/S1/S2/S3 或实际主流程节点
  - 关键中间数据
  - 输出节点
  - resource refinement 节点可用虚线或标注
```

图形要求：

- 主路径节点不能孤立。
- 节点标签表达工程含义，不是纯函数名。
- 不确定节点或推断节点应显式标记。
- 图不追求覆盖所有代码。
- VisualizationSpec 的每个 node / edge 必须绑定 `source_claim_ids` 和 `evidence_ids`。
- `summary.md` 每个主要段落必须引用 claim ids。
- Grounding checker 必须检查 `unsupported_visual_node`、`unsupported_visual_edge`、`unsupported_summary_statement`。

## Failure Handling

### main path ambiguous

处理：

```text
- 生成 UncertaintyNote。
- 输出多个 main_entry_candidates。
- 不强行选唯一主路径。
```

### insufficient evidence

处理：

```text
- 降级 claim confidence。
- 生成 missing_evidence uncertainty。
- 输出需要的证据类型。
```

### comment-code mismatch

处理：

```text
- 标注 conflicting_evidence 或 comment_code_mismatch。
- 不把注释作为最终事实。
```

### grounding checker blocking

处理：

```text
- 如果可通过本地文件查证，回到 collecting_evidence。
- 如果已达到 max_iterations，downgrade_and_write。
- confirmed claim 不允许带 blocking diagnostic 输出。
```

## Acceptance Criteria

P1a 通过条件：

```text
1. 生成 summary.md 和 flow.mmd。
2. 至少 80% 主要 claim 有 evidence_ids。
3. unsupported_confirmed_claim_count = 0。
4. 所有 confirmed claim 符合 claim_type 证据组合规则。
5. 至少一个 VisualizationSpec 被生成。
6. main path 必须有。
7. auxiliary / resource refinement 必须区分；如果 L6 evidence 中未出现，输出 unknown 或 not_observed_in_p1a_evidence。
8. fixed-point / interface / pipeline 按证据存在情况输出 confirmed / supported / inferred / unknown。
9. summary.md 和 flow.mmd 不得包含未绑定 claim/evidence 的主要结论。
10. 不确定项不为空时必须显式输出；证据不足时不得强行确定。
11. 不修改目标 fpga_project_coarse_sync_glm。
12. 不运行 Vivado / synthesis / implementation / bitstream。
```

建议人工抽样检查：

```text
- 主流程节点是否真实来自 L6。
- Q 格式或资源化说明是否有证据。
- Mermaid 图是否能帮助用户理解该阶段。
- 是否存在明显胡编或过度确定。
```

## Implementation Readiness

进入 P1a 实现前，还需要：

```text
1. 选定 graph artifact 输出位置，默认 /tmp/fpga_devmind/p1a_coarse_sync_l6。
2. 明确模型 provider 配置方式，但不写入 API key。
3. 按 phase1a-schema.md 实现 JSON schema 或 Pydantic schema。
4. 确定是否先用 CLI 触发 Agent session。
```

这些属于实现准备，不在本文继续展开。
