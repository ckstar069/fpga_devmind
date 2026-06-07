# Review 0006: P1b Handoff Readiness

Independent review requested after adding the P1b implementation plan, Claude / Kimi handoff document and P1b task cards.

## Scope

Reviewed:

```text
PROJECT_CONTEXT.md
docs/implementation-plan-p1b.md
docs/agent-handoff-claude-kimi.md
docs/tasks/*.md
docs/roadmap.md
docs/implementation-status.md
docs/README.md
docs/phase1-scope.md
docs/review-process.md
```

## Findings

### P2: Grounding Checker / Report Ownership Is Underspecified

The P1b plan required grounding checks and `grounding_report.json`, but no task explicitly owned P1b grounding diagnostics, blocking criteria or report generation.

Risk:

```text
Claude / Kimi could emit a stub grounding_report.json and miss one-sided or overclaimed mappings.
```

Recommendation:

```text
Add an explicit P1b grounding task or assign concrete diagnostic rules to T005 / T006.
```

### P2: Supported Mapping Rules Leave Room For Naming-Based Overclaim

The plan allowed `supported` when both sides had evidence plus a structural or naming bridge, while also saying naming similarity is not evidence.

Risk:

```text
Implementation agents could promote naming-only L6-to-RTL similarities to supported.
```

Recommendation:

```text
Naming-only bridge should always be inferred. Supported requires a non-name bridge such as calculation role, interface behavior, state update, pipeline timing or explicit module/signal relationship.
```

### P2: Secondary Sample Conflicts With P1b Scope

P1b was defined as L5/L6-to-RTL tracing, but the secondary `fine_cfo` sample asked for L1/L4/L6/RTL evolution.

Risk:

```text
Implementation could expand into multi-stage concept evolution before the single-concept L5/L6-to-RTL slice is stable.
```

Recommendation:

```text
Remove L1/L4 from P1b smoke or explicitly defer multi-stage evolution to P1b+.
```

### P3: Task-Card Artifact Expectations Are Uneven

The handoff contract says each task should include expected artifacts, but T002-T005 mostly described behavior rather than output shapes.

Recommendation:

```text
Add per-task output contracts, even when outputs stay in memory before T007 writes final artifacts.
```

### P3: Tests Rely On Local Absolute Target Projects Without Clear Skip / Fallback Rule

Some tasks referenced `coarse_sync_glm` and `fine_cfo` samples without making the synthetic-fixture and skip rules explicit.

Recommendation:

```text
Use synthetic fixtures for unit tests. Real project smoke tests should skip cleanly when target projects are absent.
```

## Overall Conclusion

Not ready for direct Claude / Kimi handoff before the P2 items are tightened. No P1-level direction failure was found: the documents consistently prohibit real providers, Vivado, target project mutation, PASS/HOLD, and broad static-analysis expansion.

The main remaining risk was overclaiming L5/L6-to-RTL mappings because grounding/report ownership and confidence thresholds were not crisp enough.
