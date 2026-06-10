# Documentation Map

This document is the recommended entry point for understanding `fpga_devmind` documentation. It groups old planning docs, implementation docs, task records, review records, and current direction-control docs.

Read this before starting a new implementation task or a new Web GPT review session.

## 1. First-read documents

Read these in order:

1. [`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)
   - Original user context and product need.
   - Defines the problem: help the user understand what FPGA project stages actually implement.
   - Clarifies that static analysis is only evidence support; LLM/Agent semantic understanding is the core.

2. [`current-position-and-drift.md`](current-position-and-drift.md)
   - Current Web GPT drift analysis after T047/T047.1.
   - Explains what has been built, where the project has drifted, and what should happen next.

3. [`architecture/tauri-rust-python-boundary.md`](architecture/tauri-rust-python-boundary.md)
   - Current technical-stack boundary decision.
   - Defines Tauri/React as primary UI, Rust as backend/safety/runtime boundary, Python as retained analysis engine, and PySide6 as legacy shell.

4. [`product-target.md`](product-target.md)
   - Final product form: desktop FPGA Develop-Understand Agent.
   - Clarifies what the project must not become.

5. [`roadmap.md`](roadmap.md)
   - Long-term phases: Understanding Agent -> Development Companion Agent -> Review/Audit Agent -> Develop-Understand-Verify Platform.

6. [`implementation-status.md`](implementation-status.md)
   - Current accumulated implementation status.
   - Useful for knowing what has already been completed and what remains explicit.

## 2. Direction and architecture documents

These define the product/architecture direction. They should be treated as higher-level guidance than individual task docs.

- [`direction-guardrails.md`](direction-guardrails.md)
  - Short direction constraints.

- [`agent-first-architecture.md`](agent-first-architecture.md)
  - Agent-first architecture and separation between Agent kernel and normal software infrastructure.

- [`agent-runtime.md`](agent-runtime.md)
  - Agent runtime components and task lifecycle.

- [`runtime-contracts.md`](runtime-contracts.md)
  - TaskPlan, ToolObservation, Claim, GroundingDiagnostic, ReflectionDecision, and other executable contracts.

- [`agent-workflows.md`](agent-workflows.md)
  - Core workflows: UnderstandProject, UnderstandStage, TraceConcept, MapL6ToRTL, ExplainVerification.

- [`evidence-grounding-policy.md`](evidence-grounding-policy.md)
  - Evidence strength, confidence rules, mapping rules, and conflict treatment.

- [`domain-semantics.md`](domain-semantics.md)
  - FPGA domain objects: StageContract, FixedPointSpec, StreamInterfaceSpec, PipelineTimingSpec, RTLSignalSpec, TestObservation, SourceLineage.

- [`semantic-graph-model.md`](semantic-graph-model.md)
  - ProjectGraph / StageGraph / ConceptGraph / EvidenceGraph / VisualizationSpec object model.

- [`toolbox.md`](toolbox.md)
  - Future deterministic tools available to the Agent.

- [`tool-contracts.md`](tool-contracts.md)
  - Inputs/outputs/evidence IDs/error modes for deterministic tools.

- [`memory-and-interaction.md`](memory-and-interaction.md)
  - Procedural, semantic, episodic memory and interaction concepts.

- [`architecture/tauri-rust-python-boundary.md`](architecture/tauri-rust-python-boundary.md)
  - Tauri/Rust/Python responsibility boundary and migration policy.

## 3. Phase planning documents

These define the original phased implementation route.

- [`phase1-scope.md`](phase1-scope.md)
  - Phase 1 narrowed into P1a/P1b/P1c.

- [`phase1a-single-stage-understanding.md`](phase1a-single-stage-understanding.md)
  - P1a detailed single-stage understanding spec.

- [`phase1a-schema.md`](phase1a-schema.md)
  - P1a JSON schema and artifact contract.

- [`p1a-implementation-prep.md`](p1a-implementation-prep.md)
  - Implementation prep checklist and slice order.

- [`p1a-v0.1-quickstart.md`](p1a-v0.1-quickstart.md)
  - How to run the P1a V0.1 prototype.

- [`p1a-v0.1-acceptance.md`](p1a-v0.1-acceptance.md)
  - Acceptance criteria and known limitations for P1a V0.1.

- [`p1a-plus-semantic-agent.md`](p1a-plus-semantic-agent.md)
  - P1a+ semantic Agent layer design.

- [`implementation-plan-p1b.md`](implementation-plan-p1b.md)
  - Controlled P1b plan: one-concept L5/L6-to-RTL trace.

- [`ui-prototype-plan.md`](ui-prototype-plan.md)
  - Desktop artifact viewer and Agent interaction shell plan.

## 4. Implementation task records

These docs record task-level implementation details. They are useful as history, but they should not override product direction docs.

### P1b and desktop task cards

- [`tasks/T001-p1b-schema-artifact-contract.md`](tasks/T001-p1b-schema-artifact-contract.md)
- [`tasks/T002-p1b-readonly-source-collector.md`](tasks/T002-p1b-readonly-source-collector.md)
- [`tasks/T003-p1b-concept-evidence-collector.md`](tasks/T003-p1b-concept-evidence-collector.md)
- [`tasks/T004-p1b-rtl-evidence-collector.md`](tasks/T004-p1b-rtl-evidence-collector.md)
- [`tasks/T005-p1b-mapping-claim-builder.md`](tasks/T005-p1b-mapping-claim-builder.md)
- [`tasks/T006-p1b-grounding-report.md`](tasks/T006-p1b-grounding-report.md)
- [`tasks/T007-p1b-cli-render-smoke.md`](tasks/T007-p1b-cli-render-smoke.md)
- [`tasks/T008-desktop-artifact-viewer-contract.md`](tasks/T008-desktop-artifact-viewer-contract.md)
- [`tasks/T009-desktop-app-prototype.md`](tasks/T009-desktop-app-prototype.md)
- [`tasks/T010-desktop-p1b-concept-trace-view.md`](tasks/T010-desktop-p1b-concept-trace-view.md)

### Recent provider / Agent Q&A task records

- [`tasks/T044-llm-context-builder-dry-run.md`](tasks/T044-llm-context-builder-dry-run.md)
- [`tasks/T045-approval-gated-external-runtime.md`](tasks/T045-approval-gated-external-runtime.md)
- [`tasks/T046-external-execution-pipeline.md`](tasks/T046-external-execution-pipeline.md)
- [`tasks/T047-ephemeral-real-provider-adapter.md`](tasks/T047-ephemeral-real-provider-adapter.md)

## 5. Review and response records

These record independent review decisions and should be used when checking whether an implementation is allowed to advance.

- [`review-process.md`](review-process.md)
- [`reviews/0001-agent-architecture-review.md`](reviews/0001-agent-architecture-review.md)
- [`reviews/0002-phase1a-review.md`](reviews/0002-phase1a-review.md)
- [`reviews/0003-p1a-v0.1-review.md`](reviews/0003-p1a-v0.1-review.md)
- [`reviews/0004-p1a-plus-provider-contract-review.md`](reviews/0004-p1a-plus-provider-contract-review.md)
- [`reviews/0005-p1a-plus-graph-write-safety-review.md`](reviews/0005-p1a-plus-graph-write-safety-review.md)
- [`reviews/0006-p1b-handoff-readiness-review.md`](reviews/0006-p1b-handoff-readiness-review.md)
- [`review-response-0001.md`](review-response-0001.md)
- [`review-response-0002.md`](review-response-0002.md)
- [`review-response-0003.md`](review-response-0003.md)
- [`review-response-0004.md`](review-response-0004.md)
- [`review-response-0005.md`](review-response-0005.md)
- [`review-response-0006.md`](review-response-0006.md)

## 6. How to use these docs in future tasks

For implementation tasks:

1. Read `PROJECT_CONTEXT.md`.
2. Read `docs/current-position-and-drift.md`.
3. Read `docs/documentation-map.md`.
4. Read `docs/architecture/tauri-rust-python-boundary.md`.
5. Read `docs/implementation-status.md`.
6. Read only the specific task/design docs relevant to the planned change.
7. Confirm the task still advances evidence-grounded FPGA understanding and respects the Tauri/Rust/Python boundary.

For Web GPT reviews:

1. Prefer actual PR diff/code over Agent reports.
2. Check whether changes preserve the read-only target project boundary.
3. Check whether the task moves toward semantic understanding, evidence, diagrams, uncertainty, or usable FPGA explanations.
4. Challenge tasks that only add UI/provider surface area without improving the understanding loop.
5. Challenge tasks that add new product UI to PySide6 or blur the current Tauri/Rust/Python boundary.

## 7. Current recommended next work

After T047.1 is reviewed and PR #4 is either accepted or fixed again, the next recommended work is not more provider expansion.

The next recommended work is:

```text
T048: Real Project Dogfood Against Original Understanding Goals
```

Purpose:

- use real coarse/fine CFO examples;
- test whether the current system answers the original product questions;
- record pass/partial/fail;
- identify the smallest fixes needed for actual usefulness.

Do not start T049/T050 until T048 dogfood has identified the concrete failure modes.
