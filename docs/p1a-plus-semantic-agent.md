# P1a+: Semantic Agent Layer

本文定义 P1a V0.1 之后的下一步：在现有确定性 evidence shell 外面增加 LLM/ReAct 语义 Agent 层。

P1a+ 的目的不是重写 P1a，也不是把 LLM 接到 `summary.md` 上做润色。P1a+ 要验证：

```text
User question
-> TaskPlan
-> ReAct evidence loop over P1a tools/artifacts
-> CandidateClaims
-> GraphWriteProposal
-> Grounding Checker
-> ProjectGraph / TraceIndex update
-> grounded answer and visualization request
```

## Positioning

P1a V0.1 已经提供：

```text
- read-only evidence extraction
- ProjectGraph artifact
- TraceIndex artifact
- memory freshness manifest
- deterministic query shell
- explicit uncertainty notes
```

P1a+ 在此基础上增加：

```text
- LLM semantic reasoner
- ReAct investigation loop
- structured claim generation
- reflection and confidence downgrade
- user-question-driven graph proposal
```

当前已落地一个 provider-free dry-run 命令：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6
```

它的 mode 是 `deterministic_dry_run_no_llm`，用于验证 artifact 形态，不代表 LLM semantic reasoner 已经接入。

也可以传入本地模型输出 fixture：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --model-result /tmp/fpga_devmind/model_result_fixture.json
```

此时 mode 是 `deterministic_dry_run_with_model_fixture`。fixture 只用于验证 schema、evidence id 和 confidence downgrade，不会被写入 `ProjectGraph`。

当前 dry-run 还会生成 provider contract 相关 artifact：

```text
prompt_context.json
  给未来模型调用使用的 redacted context；不包含 API key、provider secret 或完整环境变量。

model_result_normalized.json
  provider-free 空模型结果的规范化输出；未来真实模型结果也必须先经过同一校验入口。

grounding_report.json
  同时记录 P1a 图谱 diagnostics 和 model_output_diagnostics。
```

P1a+ 仍然不是：

```text
- full multi-agent platform
- automatic developer
- audit / PASS-HOLD tool
- RTL mapping implementation
- verification coverage implementation
```

## Minimal Agent Shape

第一版仍使用单一 orchestrating Agent：

```text
P1aSemanticAgent
  -> TaskPlanner
  -> ToolRouter
  -> SemanticReasoner
  -> GroundingChecker
  -> GraphWriter
  -> ResponseRenderer
```

不急于拆 Planner Agent、Evidence Agent、Critic Agent。拆分只在单 Agent 的上下文、职责或验证成本失控后进行。

## Supported First Workflow

P1a+ 第一批只增强 `UnderstandStage`。

输入：

```text
project_root
stage_id
question
artifact_dir optional
focus optional
```

建议样例：

```text
project: fpga_project_coarse_sync_glm
stage: L6_resource_opt
question: L6 资源优化阶段实际实现了什么？哪些是证据明确的，哪些只是推断？
```

Smoke 样例：

```text
project: fpga_project_fine_cfo
stage: L6_resource_opt
question: 这个 L6 streaming pipeline 的主路径、资源化实现和不确定项是什么？
```

## ReAct Loop

每一轮必须保持结构化记录：

```text
Reason
  Agent 说明下一步要确认的工程语义问题。

Act
  调用只读工具或读取已有 artifact。

Observe
  返回 ToolObservation，包含 evidence ids、候选符号、候选关系、错误和 freshness 状态。

ClaimDelta
  生成或修订 CandidateClaim，不直接写最终答案。

Reflect
  Grounding Checker 检查证据强度、过度推断、冲突和 stale memory。
```

默认限制：

```text
max_iterations: 8
max_claims_per_iteration: 8
confirmed_claim_requires: strong evidence
stale_artifact_action: refresh_or_warn
```

停止条件：

```text
- required_evidence_collected
- no_new_evidence_found
- max_iterations_reached
- blocking_conflict_found
- model_output_invalid_after_retry
```

## Tool Boundary

P1a+ 可调用的工具必须是只读或只写 `/tmp` artifact。

允许：

```text
- run p1a-understand-stage
- read project_graph.json
- read trace_index.json
- run p1a-freshness
- search evidence in target project
- read source snippets
- write proposed graph artifacts under /tmp
```

禁止：

```text
- modify fpga_project_* target projects
- run Vivado
- run synthesis / implementation / bitstream
- write API keys to logs or artifacts
- use model output as evidence without source evidence
```

## LLM Output Contract

LLM 不允许直接输出自由文本作为最终事实。它必须输出结构化中间结果：

```text
SemanticReasoningResult
- request_id
- plan_step_id
- reasoning_summary
- candidate_claims
- proposed_edges
- proposed_uncertainties
- requested_followup_tools
- self_check_notes
```

每个 `candidate_claim` 必须包含：

```text
- claim_type
- statement
- subject_ids
- evidence_ids
- confidence
- required_missing_evidence
- generated_from_step
```

如果 LLM 无法给出 evidence id，默认不能高于 `unknown`。如果只基于命名或结构相似，默认不能高于 `inferred`。

当前代码中该契约由 `src/fpga_devmind/llm_contract.py` 表达。它只定义 prompt context 和 response validation，不调用 provider。

最小校验规则：

```text
- SemanticReasoningResult 缺少必填字段会产生 blocking diagnostic。
- candidate_claims 必须是 list。
- 每个 candidate_claim 必须包含 claim_type / statement / subject_ids / evidence_ids / confidence / required_missing_evidence / generated_from_step。
- confidence 必须属于 confirmed / supported / inferred / unknown / conflicted。
- 引用未知 evidence_id 会产生 blocking diagnostic。
- 没有有效 evidence_id 的高置信 claim 会被降级为 unknown。
- confirmed model claim 至少需要一个已知 evidence_id。
- 带 blocking `model_output_diagnostics` 的 fixture 会让 CLI 返回非零退出码。
```

## Grounding Rules

P1a+ 继承 [Evidence Grounding Policy](evidence-grounding-policy.md)，并增加 LLM 专项规则：

```text
1. LLM explanation is not evidence.
2. ToolObservation evidence ids are evidence.
3. Existing ProjectGraph claims are memory, not automatically current truth.
4. Freshness must be checked before reusing existing graph memory.
5. A model can propose semantic links, but Grounding Checker decides confidence.
6. Unsupported confirmed claims are downgraded or rejected.
7. Ambiguous implementation order must stay inferred unless producer/consumer evidence exists.
```

## Artifact Additions

P1a+ 可以在现有 artifact 外新增：

```text
agent_trace.json
  ReAct loop trace with redacted model/tool metadata.

prompt_context.json
  Redacted prompt context and required output schema for future providers.

model_result_normalized.json
  Validated model result after schema and evidence-id checks.

claim_proposals.json
  CandidateClaims before grounding.

graph_write_proposal.json
  Proposed nodes, edges, uncertainties and visualization specs.

grounding_report.json
  Diagnostics and reflection decisions.

answer.md
  Final grounded response generated from accepted graph data.
```

所有新增 artifact 默认写入：

```text
/tmp/fpga_devmind/<run_id>/
```

不得写入 API key、provider secrets、完整 prompt 中的敏感环境变量。

## Prompt Shape

P1a+ prompt 应强调 Agent 角色和证据约束：

```text
You are fpga_devmind's semantic understanding agent.
Your job is to interpret FPGA stage implementation using only provided evidence.
Do not act as an auditor.
Do not emit PASS/HOLD/findings.
Return structured CandidateClaims and requested tool calls.
If evidence is weak, use inferred/unknown and create uncertainty notes.
```

Prompt 里应提供：

```text
- user question
- project/stage scope
- hard safety constraints
- available tools
- current ProjectGraph summary
- TraceIndex excerpts
- freshness status
- required JSON schema
```

Prompt 里不应提供：

```text
- API key
- unrelated repository contents
- target project write permissions
- Vivado or synthesis instructions
```

## Failure Handling

P1a+ 失败时仍应输出结构化状态：

```text
insufficient_evidence
  已读取证据不足，输出 partial claims and uncertainties。

model_output_invalid
  JSON schema invalid，最多重试一次；仍失败则停止。

stale_memory
  不复用旧 graph 作为当前解释，要求刷新或显式警告。

conflicting_evidence
  标注 conflicted claim，不强行合并。

tool_error
  保留 ToolObservation error，说明未完成的 evidence target。
```

## Acceptance

P1a+ 可称为完成，当它能：

```text
1. 对 coarse_sync_glm L6 生成 TaskPlan 和 agent_trace.json。
2. 通过 ReAct loop 读取 P1a artifacts 和必要源码证据。
3. 输出 CandidateClaims，而不是自由文本直接结论。
4. Grounding Checker 能降级 unsupported confirmed claims。
5. answer.md 中每个主要结论能追溯到 claim/evidence ids。
6. query 中能区分 confirmed / supported / inferred / unknown。
7. smoke 覆盖 fine_cfo，且不把 inferred order 说成 proven dataflow。
8. 模型输出契约能拦截缺字段、未知 evidence id 和无证据高置信 claim。
9. 不修改目标项目，不运行 Vivado，不泄露 API key。
```

## Defer

以下推迟到 P1b / P1c 或更后：

```text
- L6-to-RTL semantic mapping
- cocotb coverage interpretation
- multi-agent role split
- user feedback memory persistence
- interactive UI
- review / audit outputs
```

P1a+ 的价值是让 `fpga_devmind` 从确定性 evidence shell 进入真正 Agent 工作方式：计划、查证据、形成结构化语义结论、自检、写图和回答。
