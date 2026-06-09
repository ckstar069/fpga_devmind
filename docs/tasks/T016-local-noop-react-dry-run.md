# T016: Local No-op ReAct Dry Run

## Status: ✅ Completed

Date: 2026-06-09

## Purpose

Implement the first contract-backed local Agent dry run. T016 chains T011 (deterministic query), T012 (plan preview), and T015/T015a (runtime contract) into a single observe → plan → propose → simulated-result → answer → blocked-graph-write trace.

This is **not** a real ReAct/LLM Agent. It is a deterministic, no-op runtime that proves the contract data flow works end-to-end.

## Why T016

1. **First end-to-end contract validation**: T015 defined 9 dataclasses but never populated them from real subsystems. T016 proves the contract is usable.
2. **Bridges T011/T012/T015**: Each was tested in isolation. T016 integrates them.
3. **Enables future GUI trace viewer**: The `agent_runtime_trace.json` output is the artifact that a future T017 Desktop Agent Trace Viewer would render.
4. **No LLM required**: The loop runs entirely with deterministic keyword matching and simulated tool results.

## Dependencies

- T011: `query_artifact_bundle(bundle, question)` → `AgentPanelResponse`
- T012: `build_agent_plan_preview(bundle, question, response)` → `AgentPlanPreview`
- T015/T015a: 9 dataclasses + `validate_runtime_trace()` + `SCHEMA_VERSION`

## Public API

```python
@dataclass
class NoopAgentRunResult:
    trace: AgentRuntimeTrace
    output_dir: str
    artifact_path: str          # agent_runtime_trace.json path
    diagnostics: list[dict[str, str]]
    status: str                 # "ok" | "blocked" | "load_error"

def run_noop_agent_once(
    artifact_dir: Path,
    question: str,
    out_dir: Path,
) -> NoopAgentRunResult
```

## Behavior Flow

1. `ensure_safe_output_dir(out_dir)` — reject fpga_project_* paths
2. `load_bundle(artifact_dir)` — load P1a or P1b bundle
3. Incomplete bundle → minimal trace with `status="load_error"`
4. Create `UserTask` with deterministic task_id (`noop-{sha256[:12]}`)
5. Create `Observation` from bundle artifact list
6. Call `query_artifact_bundle()` (T011) → response
7. Call `build_agent_plan_preview()` (T012) → preview
8. Create `ReasoningSummary` — mode="deterministic", confidence mapped
9. Map preview steps → `ToolPlan` + `ToolCallProposal` entries
10. Create `ToolResult` entries with status="simulated"
11. Create `Answer` from response (auto-ensures `no_llm_semantic_reasoning`)
12. Create `GraphWriteProposal` — blocked by default
13. Assemble `AgentRuntimeTrace`
14. `validate_runtime_trace()` — cross-reference integrity
14a. If diagnostics non-empty, propagate into `trace.runtime_diagnostics` and set status="blocked"
15. Write `agent_runtime_trace.json`
16. Write `answer.md`
17. Return `NoopAgentRunResult`

## CLI

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli agent-noop-run \
  --artifact-dir /tmp/fpga_devmind/p1b_peak_idx \
  --question "summary" \
  --out /tmp/fpga_devmind/noop_run
```

Output:
- `agent_runtime_trace.json` — full contract-backed trace
- `answer.md` — human-readable answer

Console output includes: trace path, status, task_id, confidence, diagnostics count, graph write blocked.

Exit codes: 0 = ok, nonzero = blocked/load_error/invalid args.

No `--external-provider`, no `--allow-external-api` flags.

## Confidence Mapping

| response_kind | Answer.confidence |
|---|---|
| "unsupported" | "unknown" |
| "unknown" | "unknown" |
| all others | "inferred" |

## Files

```text
src/fpga_devmind/agent_noop_runtime.py    — core runtime module
tests/test_agent_noop_runtime.py          — 19 tests
src/fpga_devmind/cli.py                   — agent-noop-run subcommand
```

## Tests (19)

- **TestNoopAgentHappyPath** (10): trace writes, schema version, validate clean, safety constraints, observation refs, plan not executable, proposals not executable, results simulated, answer limitation, graph write blocked
- **TestNoopAgentEdgeCases** (3): unsupported question → unknown confidence, incomplete bundle → load_error, unsafe path → ValueError
- **TestNoopAgentSafety** (3): no forbidden imports, no forbidden runtime calls, no target project mutation
- **TestNoopAgentCLI** (3): happy path exits 0, unsafe output exits nonzero, blocked exits nonzero

## Boundaries

```text
- No real LLM semantic reasoning.
- No external API calls.
- No API key loading.
- No Vivado / synthesis / implementation / bitstream.
- No mutation to fpga_project_* target projects.
- No graph writes (only proposals, all blocked).
- No PASS / HOLD / finding / audit semantics.
- Output only to /tmp or /private/tmp.
- Only consumes existing P1a/P1b artifact bundles.
```

## Next Steps

- T014 (optional): Desktop Shell usability hardening
- T017 (future): Desktop Agent Trace Viewer — render `agent_runtime_trace.json` in GUI
- T018 (future): Real LLM provider integration (after T016 proves the contract)

## T016a: Propagate runtime validation diagnostics

`validate_runtime_trace()` diagnostics are now propagated into `trace.runtime_diagnostics` and cause `status="blocked"` when non-empty. The `agent_runtime_trace.json` written to disk includes these diagnostics. This ensures that any cross-reference integrity violations detected by the contract validator are visible in the output trace and cause the run to be reported as blocked.
