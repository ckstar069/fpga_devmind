# Review 0004: P1a+ Provider Contract Readiness

Independent review requested after adding P1a+ dry-run runtime, LLM contract validation, local model-result fixture validation and noop/fixture provider adapters.

## Review Summary

Overall assessment:

```text
No major direction drift was found. P1a+ remains an Understanding Agent shell,
not an audit / PASS-HOLD / finding tool.

The main risk was enforcement: safety and grounding constraints were partly
documented but not yet fully enforced in code.
```

Recommended priority:

```text
Fix before real provider integration:
- guard output paths so generated artifacts cannot be written into target projects
- validate all model-proposed actions, not only candidate claims
- avoid misleading provider safety metadata for future real providers
- keep runtime mode consistent across artifacts
- make schema version part of the provider contract
```

## Findings

### Output Path Was Not Guarded

Severity: P1.

Issue:

```text
P1a+ accepted arbitrary --out and --artifacts paths, then wrote generated
artifacts without checking whether the destination was under /tmp or inside an
fpga_project_* target project.
```

Why it matters:

```text
The project hard constraint says target fpga_project_* projects must remain
read-only. A mistaken command could write fpga_devmind artifacts into a target
project while agent_trace still claimed target_project_modified=false.
```

Suggested change:

```text
Enforce temporary output roots in code and reject paths whose components start
with fpga_project_.
```

### Model Output Validation Only Covered Claims

Severity: P1.

Issue:

```text
SemanticReasoningResult also includes requested_followup_tools, proposed_edges
and proposed_uncertainties, but validation only checked candidate_claims.
```

Why it matters:

```text
A model could request forbidden tools or propose ungrounded edges/uncertainties
with no blocking diagnostics if candidate_claims was empty.
```

Suggested change:

```text
Validate requested tools against an allowlist and validate evidence ids on
proposed_edges / proposed_uncertainties.
```

### Provider Safety Flags Were Too Easy to Reuse Incorrectly

Severity: P2.

Issue:

```text
provider_call.json recorded external_api_called=false, api_key_used=false and
api_key_logged=false in a shared helper.
```

Why it matters:

```text
That is correct for noop/fixture providers, but a future real provider could
reuse the helper and emit false safety metadata.
```

Suggested change:

```text
Limit the helper to offline providers or require real providers to supply their
own call records.
```

### Fixture Mode Had Inconsistent Runtime Mode

Severity: P2.

Issue:

```text
agent_trace and claim_proposals used fixture mode, while graph_write_proposal
and grounding_report still hardcoded deterministic_dry_run_no_llm.
```

Suggested change:

```text
Pass runtime_mode through every P1a+ artifact.
```

### Invalid Model Claims Were Copied Without Explicit Rejection Status

Severity: P2.

Issue:

```text
Invalid normalized model claims appeared in model_candidate_claims, and rejection
could only be inferred indirectly from diagnostics.
```

Suggested change:

```text
Annotate each model claim with validation_status and diagnostic_ids.
```

### Schema Version Was Advertised But Not Checked

Severity: P3.

Issue:

```text
prompt_context advertised required schema_version, but validator did not require
or compare it.
```

Suggested change:

```text
Require schema_version and emit blocking diagnostics on mismatch.
```
