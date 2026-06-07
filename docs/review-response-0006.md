# Review Response 0006

This response records the fixes made after Review 0006: P1b Handoff Readiness.

## P2: Grounding Checker / Report Ownership

Status: fixed.

Changes:

```text
docs/implementation-plan-p1b.md
docs/tasks/T006-p1b-grounding-report.md
docs/tasks/T007-p1b-cli-render-smoke.md
```

The implementation plan now defines P1b grounding diagnostic shape, blocking diagnostics, non-blocking diagnostics and ownership:

```text
T006 implements P1b grounding report generation.
T007 CLI returns nonzero when grounding_report.json contains any blocking diagnostic.
```

Added explicit T006 task:

```text
T006: P1b Grounding Checker And Report
```

T007 now depends on T006 and must not emit a stub `grounding_report.json`.

## P2: Supported Mapping Overclaim

Status: fixed.

Changes:

```text
docs/implementation-plan-p1b.md
docs/phase1-scope.md
docs/tasks/T005-p1b-mapping-claim-builder.md
docs/tasks/T006-p1b-grounding-report.md
```

Rules now state:

```text
- naming-only bridge is always inferred, never supported.
- supported requires a non-name bridge.
- confirmed should normally be avoided in first implementation.
- supported mapping with bridge_kind=naming_only is blocking.
```

Allowed non-name bridge examples:

```text
calculation_role
interface_behavior
state_update
pipeline_timing
module_signal_relationship
explicit_source_bridge
```

## P2: Secondary Sample Scope Conflict

Status: fixed.

Changes:

```text
docs/implementation-plan-p1b.md
docs/phase1-scope.md
```

The `fine_cfo` secondary sample now asks only:

```text
lts_start 在 L6/RTL 中有哪些可追踪证据？
```

Full L1/L4/L6/RTL evolution is explicitly deferred to P1b+ or a later multi-stage TraceConcept slice.

## P3: Uneven Task Output Contracts

Status: fixed.

Changes:

```text
docs/tasks/T002-p1b-readonly-source-collector.md
docs/tasks/T003-p1b-concept-evidence-collector.md
docs/tasks/T004-p1b-rtl-evidence-collector.md
docs/tasks/T005-p1b-mapping-claim-builder.md
docs/tasks/T006-p1b-grounding-report.md
docs/tasks/T007-p1b-cli-render-smoke.md
```

Each task now has an output contract or final artifact contract. Intermediate tasks may keep outputs in memory, but their dict/dataclass shapes are explicit.

## P3: Test Skip / Fixture Rule

Status: fixed.

Changes:

```text
docs/agent-handoff-claude-kimi.md
docs/tasks/*.md
```

Rules now state:

```text
- Unit tests should use synthetic fixtures when possible.
- P1b behavior tests should go in tests/test_p1b.py.
- Real project smoke tests must skip cleanly when target projects are absent.
```

## Verification

Commands:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

Results:

```text
18 tests passed.
compileall passed.
```
