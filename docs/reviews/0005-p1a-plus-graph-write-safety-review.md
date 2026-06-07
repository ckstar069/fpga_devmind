# Review 0005: P1a+ Graph Write Safety

Independent read-only review requested after adding external provider disabled routes, the explicit external API gate, mock semantic provider and GraphWriter dry-run.

## Scope

Reviewed:

```text
src/fpga_devmind/agent.py
src/fpga_devmind/providers.py
src/fpga_devmind/provider_config.py
src/fpga_devmind/llm_contract.py
src/fpga_devmind/graph_writer.py
src/fpga_devmind/cli.py
src/fpga_devmind/safety.py
tests/test_p1a.py
docs/p1a-plus-semantic-agent.md
docs/p1a-v0.1-quickstart.md
docs/implementation-status.md
docs/review-response-0004.md
```

The reviewer also ran:

```bash
PYTHONPATH=src python3 -m unittest tests/test_p1a.py
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/review_gate_run \
  --mock-semantic
```

## Direction Check

No direction drift was found toward:

```text
- PASS/HOLD
- audit findings
- Vivado execution
- synthesis / implementation / bitstream
- target project mutation
- API key logging
```

The main remaining risk was provider-readiness: invalid model outputs could still influence proposed graph artifacts.

## Findings

### P1: Globally Invalid Model Outputs Can Still Write Accepted Claims

`run_p1a_semantic_agent_dry_run()` validated provider output and produced blocking `model_output_diagnostics`, but `_build_graph_write_proposal()` still built proposed graph writes from normalized claims even when the whole model response had blocking diagnostics not tied to a single claim.

Examples:

```text
- schema mismatch
- missing top-level fields
- forbidden follow-up tools
- invalid proposed_edges
- invalid proposed_uncertainties
```

Because claim validation only rejected claim-targeted diagnostics, a valid-looking claim inside a globally invalid ReAct response could remain `accepted_for_grounding` and be appended to `project_graph_proposed.json`.

Recommendation:

```text
If any blocking model diagnostic exists, set model_claims_to_create=[] or mark all model claims rejected until retry succeeds.
```

### P2: Accepted Model Claims Are Not Validated Against Graph Schema / Domain

The LLM contract required claim fields by presence, but did not validate:

```text
- claim_type
- subject_ids shape / namespace
- required_missing_evidence shape
- counter_evidence_ids shape
- whether subject references are compatible with known graph namespaces
```

Recommendation:

```text
Define allowed P1a+ claim types and subject id namespaces. Reject or quarantine schema-invalid claims before GraphWriter dry-run.
```

### P2: Proposed Graph Is Not Trace / Query Complete

`project_graph_proposed.json` appends model claims, but there is no companion proposed trace index or evidence reverse-index update.

Recommendation:

```text
Either generate trace_index_proposed.json in a later slice or explicitly mark project_graph_proposed.json as not trace/query complete.
```

### P3: Provider Call Safety Metadata Is Easy To Misuse Later

The helper for noop / fixture / mock provider call records hardcoded:

```text
external_api_called=false
api_key_used=false
api_key_logged=false
```

Current use was safe, but a future real provider could accidentally reuse the helper and under-report API/key behavior.

Recommendation:

```text
Rename the helper to make the offline-only scope explicit, and require real-provider records to set safety fields explicitly.
```

## Outcome

Accepted. See [Review response 0005](../review-response-0005.md).
