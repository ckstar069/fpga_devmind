# T010: Desktop P1b Concept Trace View

## Objective

Add a dedicated desktop GUI view for P1b concept trace artifacts after P1b implementation exists.

## Dependency

This task depends on:

```text
T001-T007 P1b implementation
T008 desktop artifact contract
T009 desktop app prototype
```

## Allowed Files

```text
desktop/**
ui/**
src/fpga_devmind/ui*.py
tests/test_ui.py
docs/ui-prototype-plan.md
docs/implementation-status.md
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected View

The P1b view should show:

```text
- selected concept
- L5/L6 evidence side
- RTL evidence side
- mapping claims
- confidence per mapping
- bridge_kind
- required_missing_evidence
- grounding diagnostics
- concept_trace.mmd visualization
```

## Acceptance

```text
- supported / inferred / unknown / conflicted mapping claims are visually distinct.
- naming-only inferred mappings are not presented as confirmed.
- missing RTL side is obvious.
- grounding blocking diagnostics are visible.
- evidence ids and file line ranges are one click away from each claim.
```

## Verification

Use synthetic P1b artifact fixtures when possible. Real project generated artifacts may be used as smoke data, but tests must skip cleanly when absent.
