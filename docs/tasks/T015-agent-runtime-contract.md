# T015: Agent Runtime Contract

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Define the structured artifact contract for a future ReAct-like Agent loop **before** implementing the loop itself. The contract specifies what data flows between observe → plan → propose → answer stages, enabling T016 (Local No-op ReAct Dry Run) to build on a stable data foundation.

## Why T015 Is the Next Step

Review 0008 (Desktop Agent Shell V0.2 Readiness) recommended T015 as the highest-priority next step because:

1. **Data contract first**: Before writing any loop logic, define what artifacts the loop produces and consumes. This prevents ad-hoc data structures that are hard to validate.
2. **T011/T012 are proto-contracts**: The Agent Panel (T011) already produces structured answers with referenced IDs, and the Plan Preview (T012) already produces structured step lists. T015 formalizes these into a runtime artifact contract.
3. **Enables T016**: The no-op ReAct dry run needs data structures to populate. Without a contract, T016 would invent its own ad-hoc formats.
4. **No LLM required**: The contract defines `mode=deterministic|noop|llm_future`. Real LLM is a future plug-in point, not a current dependency.

## Artifact Roles

| Artifact | Role in Agent Loop |
|---|---|
| `UserTask` | User's original question + artifact bundle reference. Entry point of the loop. |
| `Observation` | Snapshot of artifact state at loop start. The Agent's "what do I know?" phase. |
| `ReasoningSummary` | Reasoning about the observation. Mode can be deterministic, noop, or future LLM. |
| `ToolPlan` | Ordered list of tool-call proposals. Maps to T012's `AgentPlanPreview`. |
| `ToolCallProposal` | Single proposed tool invocation. Maps to T012's `AgentPlanStep`. |
| `ToolResult` | Output from executing (or simulating) a tool call. Maps to T011's `AgentPanelResponse`. |
| `Answer` | Final structured answer with referenced IDs. Maps to T011's answer output. |
| `GraphWriteProposal` | Proposed graph mutations — blocked by default. Future write capability placeholder. |
| `AgentRuntimeTrace` | Top-level container for one complete loop iteration. JSON serializable. |

## Relationship to T011/T012

| T011/T012 Concept | T015 Contract |
|---|---|
| `ArtifactBundle` + `artifact_loader` | `Observation.artifact_refs` |
| `AgentPanelResponse.answer_text` | `Answer.answer_text` |
| `AgentPanelResponse.referenced_*_ids` | `Answer.referenced_*_ids` |
| `AgentPanelResponse.response_kind` | `ToolPlan.intent` |
| `AgentPlanPreview.steps` | `ToolPlan.steps` (list of `ToolCallProposal`) |
| `AgentPlanStep.allowed_action` | `ToolCallProposal.allowed_action` |
| `AgentPlanStep.is_executable_now=False` | `ToolCallProposal.is_executable_now=False` |
| `AgentPlanPreview.safety_notes` | `ToolPlan.safety_notes` |
| T011 query function | `ToolResult` (deterministic query result) |

## Data Structure Summary

Schema version: `agent-runtime-contract-0.1`

All dataclasses provide:
- `to_dict()` → JSON-serializable dict
- `from_dict(data)` → reconstruct from dict (runs validation)
- `__post_init__()` validation for required fields and enum constraints

### Key Validation Rules

- `UserTask.constraints`: auto-ensures `no_external_api`, `no_vivado`, `read_only`, `no_target_project_mutation`
- `ToolPlan.is_executable_now`: must be `False`
- `ToolCallProposal.is_executable_now`: must be `False`
- `ToolCallProposal.allowed_action`: must be `read_only_preview`, `deterministic_query`, or `noop`
- `ToolCallProposal.params`: must be JSON serializable
- `ToolResult.status`: must be `not_executed`, `simulated`, `completed`, or `blocked`
- `ReasoningSummary.mode`: must be `deterministic`, `noop`, or `llm_future`
- `Answer.answer_text`: must be non-empty
- `Answer.limitations`: auto-ensures `no_llm_semantic_reasoning`
- `GraphWriteProposal.is_write_allowed`: must be `False`
- `GraphWriteProposal.blocking_reasons`: must contain `graph_write_disabled_in_current_stage`
- `validate_runtime_trace()`: cross-references task_id consistency, result_id existence, answer_id existence
- `validate_runtime_trace()`: checks ToolPlan.steps task_id matches trace.task.task_id (T015a)
- `validate_runtime_trace()`: checks ToolResult.proposal_id references an existing ToolCallProposal in plan steps (T015a)

### Safety Constants

```python
DEFAULT_SAFETY_CONSTRAINTS = [
    "no_external_api", "no_vivado", "read_only", "no_target_project_mutation"
]
DEFAULT_SAFETY_NOTES = [
    "no external LLM / API call",
    "no API key loading",
    "no Vivado / synthesis / implementation / bitstream",
    "no mutation to fpga_project_* target projects",
    "this is a contract definition; no tools are executed",
]
```

## What T015 Does NOT Implement

```text
- No real LLM semantic reasoning.
- No external API calls.
- No ReAct loop execution.
- No tool dispatch.
- No graph writes.
- No Vivado / synthesis / implementation / bitstream.
- No API key loading.
- No target project mutation.
- No PASS / HOLD / finding / audit semantics.
```

## How T016 Will Use This Contract

T016 (Local No-op ReAct Dry Run) will:

1. Accept a `UserTask` (question + artifact bundle path).
2. Build an `Observation` by loading the artifact bundle.
3. Create a `ReasoningSummary` with `mode=deterministic` (keyword matching).
4. Build a `ToolPlan` from the T012 plan preview logic.
5. Populate `ToolResult` entries with `status=simulated` from T011 query.
6. Compose an `Answer` from the T011 answer text + referenced IDs.
7. Create a `GraphWriteProposal` with `is_write_allowed=False`.
8. Assemble everything into an `AgentRuntimeTrace`.
9. Run `validate_runtime_trace()` to verify cross-reference integrity.
10. Serialize to JSON.

No LLM, no external API, no tool execution. The loop runs exactly once (single-turn).

## Files

```text
src/fpga_devmind/agent_runtime_contract.py   — 9 dataclasses + validate_runtime_trace()
tests/test_agent_runtime_contract.py         — 68 tests
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_agent_runtime_contract -v
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src basedpyright src/fpga_devmind/agent_runtime_contract.py tests/test_agent_runtime_contract.py
```

## Boundaries

```text
- Only defines data contracts and validation.
- No code execution beyond dataclass construction.
- No imports of requests, urllib, subprocess, http.
- No API key references.
- No Vivado / synthesis / implementation / bitstream.
- No mutation to fpga_project_*.
- No PASS / HOLD / finding / audit semantics.
```
