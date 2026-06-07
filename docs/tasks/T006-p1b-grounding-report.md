# T006: P1b Grounding Checker And Report

## Objective

Implement P1b grounding diagnostics and write `grounding_report.json` from structured concept trace graph data.

This task prevents overclaimed L5/L6-to-RTL mappings from reaching the CLI as acceptable results.

## Allowed Files

```text
src/fpga_devmind/p1b_schema.py
src/fpga_devmind/p1b_mapping.py
tests/test_p1b.py
docs/implementation-plan-p1b.md
```

New module allowed:

```text
src/fpga_devmind/p1b_grounding.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected Output Contract

Function-level output:

```text
{
  "schema_version": "p1b-grounding-report-0.1",
  "diagnostics": [...],
  "summary": {
    "mapping_claims": int,
    "blocking_diagnostics": int,
    "unsupported_confirmed_mappings": int,
    "naming_only_supported_mappings": int,
    "one_sided_mapping_evidence": int
  }
}
```

Diagnostic fields:

```text
diagnostic_id
target_claim_id
severity
issue_type
recommended_action
related_evidence_ids
message
```

## Blocking Diagnostics

```text
unsupported_confirmed_mapping
  confirmed mapping lacks explicit bridge evidence.

mapping_missing_l6_or_rtl_side
  supported/confirmed mapping lacks either L5/L6 evidence or RTL evidence.

naming_only_supported_mapping
  supported mapping depends only on naming similarity or file proximity.

mapping_claim_without_evidence
  mapping claim has no evidence ids.
```

## Non-Blocking Diagnostics

```text
one_sided_mapping_evidence
  one side is missing and claim is unknown or inferred with required_missing_evidence.

multiple_candidate_rtl_objects
  several RTL candidates remain plausible.

weak_bridge_evidence
  bridge is too weak for supported.
```

## Acceptance

```text
- confirmed mapping without explicit bridge produces blocking diagnostic.
- supported mapping with naming-only bridge produces blocking diagnostic.
- supported/confirmed mapping missing either L5/L6 or RTL evidence produces blocking diagnostic.
- unknown/inferred one-sided mapping produces non-blocking diagnostic when required_missing_evidence is present.
- grounding report is generated from structured graph data, not Markdown.
```

## Tests

Use synthetic fixtures for unit tests.

Add tests for:

```text
- unsupported confirmed mapping
- naming-only supported mapping
- missing RTL side
- acceptable inferred one-sided unknown result
- clean supported mapping with non-name bridge
```

Real project smoke tests are not required for this task. If added, they must skip cleanly when target projects are absent.

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Review Notes

This task is required before T007 CLI work. Do not let T007 emit a stub `grounding_report.json`.
