# Review Response 0004

This response records how Review 0004 was handled.

## Accepted Findings

### Output Path Was Not Guarded

Decision: accepted.

Changes:

```text
- Added src/fpga_devmind/safety.py.
- P1a run_p1a now validates output paths before writing artifacts.
- P1a smoke validates out_root before writing smoke reports.
- P1a+ validates both --out and --artifacts before writing.
- Paths under fpga_project_* are rejected.
- Generated artifact paths must be under a temporary output root.
- Added negative test for unsafe fpga_project_* output path.
```

Rationale:

```text
The read-only target-project constraint must be enforced in code, not only in
docs or agent_trace metadata.
```

### Model Output Validation Only Covered Claims

Decision: accepted.

Changes:

```text
- requested_followup_tools is now validated against a safe tool allowlist.
- proposed_edges evidence_ids are validated against known evidence ids.
- proposed_uncertainties evidence_ids are validated against known evidence ids.
- Forbidden or unknown tool requests produce blocking diagnostics.
- Unknown evidence ids in proposed edges/uncertainties produce blocking diagnostics.
- Added tests for forbidden Vivado-like tool request and ungrounded model outputs.
```

Rationale:

```text
Future ReAct outputs include actions and graph proposals, not just claims. The
contract gate must cover the full SemanticReasoningResult surface.
```

### Provider Safety Flags Were Too Easy to Reuse Incorrectly

Decision: accepted.

Changes:

```text
- Renamed the provider call-record helper to an offline-scoped helper.
- Review 0005 later tightened the name to _offline_only_call_record.
- The helper is now explicitly scoped to noop / fixture / mock / disabled stub providers.
- Docs state that real providers must implement the same interface but must not
  bypass validation or reuse offline-only metadata incorrectly.
```

Rationale:

```text
The current providers do not call external APIs or use API keys. Future real
providers need explicit safety accounting instead of inheriting offline flags.
```

### Fixture Mode Had Inconsistent Runtime Mode

Decision: accepted.

Changes:

```text
- graph_write_proposal.json now records the selected runtime mode.
- grounding_report.json now records the selected runtime mode.
- Tests assert fixture mode consistency across artifacts.
```

### Invalid Model Claims Were Copied Without Explicit Rejection Status

Decision: accepted.

Changes:

```text
- Model claims now receive validation_status.
- Model claims now receive diagnostic_ids.
- claim_proposals.json includes model_claim_summary.
- Tests assert rejected fixture claims are marked rejected.
```

Rationale:

```text
Future graph-writer code should not need to infer rejection status from a
separate diagnostic list.
```

### Schema Version Was Advertised But Not Checked

Decision: accepted.

Changes:

```text
- schema_version is now required in SemanticReasoningResult.
- Validator compares it to p1a-plus-semantic-result-0.1.
- Mismatches produce blocking diagnostics.
- Tests cover missing schema_version.
```

## Deferred Items

The following remain future work:

```text
- Real provider adapters for DeepSeek / GLM / OpenAI or other configured models.
- Provider-specific API key loading with redaction tests.
- Full endpoint validation for proposed_edges beyond evidence id checks.
- Tool execution loop for safe requested_followup_tools.
- Writing accepted model claims into graph_write_proposal.
```

## Impact

P1a+ remains external-API-free, and its model boundary is now stricter:

```text
provider result
-> schema/version check
-> safe tool allowlist
-> evidence id validation for claims, edges and uncertainties
-> confidence downgrade / rejection status
-> grounding_report diagnostics
```

This keeps the next real provider step aligned with the Agent-first direction while preserving read-only target-project safety.
