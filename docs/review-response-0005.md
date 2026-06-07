# Review Response 0005

This response records the fixes made after Review 0005: P1a+ Graph Write Safety.

## P1: Globally Invalid Model Output Can Still Write Claims

Status: fixed.

Changes:

```text
src/fpga_devmind/llm_contract.py
src/fpga_devmind/agent.py
tests/test_p1a.py
```

Behavior now:

```text
- Any blocking diagnostic without target_claim_id is attached to every model claim.
- Any model claim touched by a global blocking diagnostic is marked rejected.
- graph_write_proposal.json records graph_write_blocked=true when any blocking model diagnostic exists.
- graph_write_proposal.json records blocking_model_diagnostic_ids.
- model_claims_to_create=[] when graph_write_blocked=true.
- project_graph_proposed.json receives no model claim additions in globally invalid model-result runs.
```

Added regression coverage:

```text
test_p1a_plus_agent_blocks_all_graph_writes_when_model_result_is_globally_invalid
```

The regression fixture contains a valid-looking evidence-backed claim plus a forbidden follow-up tool. The expected result is nonzero model-output diagnostics and no graph additions.

## P2: Model Claim Schema / Domain Validation

Status: fixed for the first P1a+ contract slice.

Changes:

```text
src/fpga_devmind/llm_contract.py
tests/test_p1a.py
docs/p1a-plus-semantic-agent.md
docs/p1a-v0.1-quickstart.md
docs/implementation-status.md
```

The validator now rejects model claims that violate:

```text
- allowed claim_type set
- subject_ids list shape
- subject namespace allowlist
- required_missing_evidence list shape
- counter_evidence_ids list shape
- counter_evidence_ids known evidence constraint
```

Allowed subject namespace prefixes:

```text
N
C
stage:
concept:
module:
signal:
formula:
state:
test:
```

Added regression coverage:

```text
test_llm_contract_rejects_schema_invalid_model_claims
```

## P2: Proposed Graph Is Not Trace / Query Complete

Status: documented and deferred.

Current dry-run keeps `project_graph_proposed.json` as a proposal artifact, not a reusable semantic memory artifact. Documentation now explicitly says it is not trace/query complete until a future `trace_index_proposed.json` slice exists.

Deferred next slice:

```text
GraphWriter should generate trace_index_proposed.json or another explicit EvidenceGraph reverse-index proposal.
```

## P3: Provider Call Safety Metadata

Status: fixed.

Changes:

```text
src/fpga_devmind/providers.py
```

The helper was renamed:

```text
_offline_call_record -> _offline_only_call_record
```

This makes the helper's scope explicit for noop / fixture / mock / disabled stub routes. Future real provider adapters should build call records through a separate path that sets API/key safety fields explicitly.

## Verification

Commands:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_review_fix \
  --mock-semantic
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_review_disabled \
  --external-provider deepseek
```

Results:

```text
- 18 tests passed.
- compileall passed.
- mock_semantic route produced zero model-output blocking diagnostics.
- disabled external provider route returned nonzero through model-output blocking diagnostics and still made no external API call.
```
