# T005: P1b Mapping Claim Builder

## Objective

Build conservative mapping claims from L5/L6 evidence and RTL evidence.

This task turns collected evidence into structured `mapping_claims`, `uncertainty_notes` and visualization edges.

## Allowed Files

```text
src/fpga_devmind/p1b_concept.py
src/fpga_devmind/p1b_rtl.py
src/fpga_devmind/p1b_schema.py
tests/test_p1b.py
```

New module allowed:

```text
src/fpga_devmind/p1b_mapping.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected Behavior

Mapping claim fields:

```text
claim_id
claim_type: mapping_claim
statement
l6_subject_ids
rtl_subject_ids
evidence_ids
l5_l6_evidence_ids
rtl_evidence_ids
bridge_evidence_ids
bridge_kind
confidence
required_missing_evidence
source_plan_step_id
```

## Output Contract

Function-level output should be a structured dict or dataclass equivalent:

```text
{
  "schema_version": "p1b-mapping-claims-0.1",
  "mapping_claims": [dict],
  "uncertainty_notes": [dict],
  "visualization_edges": [dict],
  "mapping_diagnostics": [dict]
}
```

`bridge_kind` must be one of:

```text
explicit_source_bridge
calculation_role
interface_behavior
state_update
pipeline_timing
module_signal_relationship
naming_only
unknown
```

## Confidence Rules

```text
confirmed
  Avoid in first implementation unless explicit source bridge exists.

supported
  Use only when both L6 and RTL evidence exist and a non-name bridge is recorded.
  Acceptable bridge examples include calculation role, interface behavior, state
  update, pipeline timing or explicit module/signal relationship.

inferred
  Use when naming/structure suggests a relation but bridge evidence is weak.
  Naming-only bridge is always inferred, never supported.

unknown
  Use when one side cannot be found.

conflicted
  Use when multiple incompatible RTL candidates appear.
```

## Acceptance

```text
- unsupported confirmed mapping claim count is 0.
- every concrete mapping claim has at least one L5/L6 evidence id and at least one RTL evidence id.
- weak bridge records required_missing_evidence.
- unknown concept produces unknown claim or uncertainty instead of false mapping.
- one-sided evidence produces unknown/inferred result with required_missing_evidence, not supported/confirmed mapping.
- supported mapping with naming-only bridge is forbidden and should be caught by T006 grounding.
```

## Tests

Add tests for:

```text
- supported mapping with both sides present
- inferred mapping with naming only
- unknown mapping when RTL side missing
- no confirmed claim without explicit bridge
- no supported claim with bridge_kind=naming_only
```

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Review Notes

This is the highest-risk P1b task. It must be reviewed for overclaiming.
