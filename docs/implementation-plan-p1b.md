# P1b Implementation Plan

P1b is the first controlled coding phase after the P1a / P1a+ understanding shell. Its goal is not to expand fpga_devmind into a broad static analyzer. Its goal is to add one narrow, evidence-grounded concept trace workflow that can follow a selected concept from L5/L6 into RTL and produce graph artifacts with explicit uncertainty.

## Current Baseline

P1a / P1a+ already provide:

```text
- deterministic L6 evidence extraction
- ProjectGraph / TraceIndex / MemoryManifest
- deterministic query and freshness checks
- external-API-free P1a+ Agent dry-run
- provider contract and model result validation
- GraphWriter dry-run
- project_graph_proposed.json
- trace_index_proposed.json
```

P1b should build on these artifacts. It should not replace them.

## P1b Goal

Answer one question:

```text
How does one selected concept in a generated FPGA project map from L5/L6 into RTL, and which parts are evidence-backed, inferred, or unknown?
```

Primary sample:

```text
project: /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm
concept: peak_idx
question: 这个概念如何从 L5/L6 映射到 RTL？哪些 RTL 细节是资源化细化？
```

Fallback concept for the same project:

```text
metric
```

Secondary smoke sample:

```text
project: /Users/ckstar/Repo/znxt_ofdm/fpga_project_fine_cfo
concept: lts_start
question: lts_start 在 L6/RTL 中有哪些可追踪证据？
```

Full L1/L4/L6/RTL concept evolution for `fine_cfo` is deferred to P1b+ or a later multi-stage concept trace slice. P1b implementation tasks should only collect L5/L6/RTL evidence.

## Non-Goals

P1b must not implement:

```text
- real LLM provider calls
- API key loading
- Vivado / synthesis / implementation / bitstream
- target project mutation
- broad whole-project RTL dataflow extraction
- PASS/HOLD or audit finding output
- UI
- automatic code modification feedback to ai_project_template
```

## Required Workflow

The P1b workflow should be a new controlled slice:

```text
p1b-trace-concept
  -> profile target project layout
  -> collect L5/L6 evidence for selected concept
  -> collect RTL evidence for candidate modules/signals
  -> propose mapping claims
  -> run grounding checks
  -> write ConceptTraceGraph / EvidenceGraph-style artifacts
  -> answer with evidence ids and uncertainty
```

The workflow can be deterministic first. LLM/ReAct integration should remain behind the existing P1a+ provider contract until a later task explicitly enables a real provider.

## Proposed Artifacts

Default output:

```text
/tmp/fpga_devmind/p1b_<project>_<concept>/
```

Required files:

```text
concept_trace_graph.json
concept_trace_index.json
concept_trace.md
concept_trace.mmd
grounding_report.json
run_metadata.json
```

Optional, if implemented through P1a+ proposal flow:

```text
project_graph_proposed.json
trace_index_proposed.json
graph_write_proposal.json
graph_write_report.json
```

## Minimal Schema

`concept_trace_graph.json` should include:

```text
schema_version
task_request
project_profile
concept
stage_views
rtl_views
mapping_claims
evidence_items
uncertainty_notes
visualization_specs
grounding_diagnostics
run_metadata
```

The first implementation may keep this as plain dicts before adding dataclasses, but it must remain structured JSON and must not become a Markdown report as the primary artifact.

## Mapping Claim Rules

Mapping claims must use confidence conservatively:

```text
confirmed
  Only when there is explicit source evidence connecting L5/L6 concept and RTL object.
  The first implementation should normally avoid confirmed mapping claims.

supported
  When there is source evidence on both sides plus a non-name bridge such as
  calculation role, interface behavior, state update, pipeline timing, or an
  explicit module/signal relationship.

inferred
  When the bridge is based mainly on naming, nearby code structure, or expected template convention.
  Naming-only bridges are always inferred, never supported.

unknown
  When the concept or RTL object cannot be located with enough evidence.

conflicted
  When multiple incompatible mappings are plausible from evidence.
```

For P1b, most L6-to-RTL mappings are expected to be `supported` or `inferred`, not `confirmed`.

## Evidence Rules

Every mapping claim must include:

```text
- at least one L5 or L6 evidence id when discussing Python/model-side meaning
- at least one RTL evidence id when discussing RTL-side implementation
- required_missing_evidence when either side is weak
```

If either side is missing, the workflow should emit an `unknown` mapping claim or uncertainty note instead of pretending a full L5/L6-to-RTL mapping exists.

LLM output, file names, naming similarity and template conventions are not evidence by themselves.

## P1b Grounding Diagnostics

P1b must produce `grounding_report.json` from structured graph data, not from rendered Markdown.

Diagnostic shape:

```text
diagnostic_id
target_claim_id
severity: blocking | non_blocking
issue_type
recommended_action
related_evidence_ids
message
```

Blocking diagnostics:

```text
unsupported_confirmed_mapping
  A confirmed mapping claim lacks explicit bridge evidence.

mapping_missing_l6_or_rtl_side
  A concrete supported/confirmed mapping claim lacks either L5/L6 evidence or RTL evidence.

naming_only_supported_mapping
  A supported mapping depends only on naming similarity or file proximity.

mapping_claim_without_evidence
  A mapping claim has no evidence ids.

unsafe_output_path
  Generated output path is not under a temp root or contains fpga_project_*.
```

Non-blocking diagnostics:

```text
one_sided_mapping_evidence
  One side exists but the other side is missing; emit unknown or inferred with required_missing_evidence.

multiple_candidate_rtl_objects
  Several RTL candidates exist; emit conflicted or inferred unless disambiguated.

weak_bridge_evidence
  Bridge exists but is not strong enough for supported.
```

Ownership:

```text
T006 implements P1b grounding report generation.
T007 CLI returns nonzero when grounding_report.json contains any blocking diagnostic.
```

## CLI Shape

Recommended first CLI:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_devmind/p1b_coarse_sync_peak_idx
```

The command should return nonzero only for blocking grounding diagnostics or safety violations.

## Implementation Slices

Recommended order:

```text
T001: P1b schema and artifact contract
T002: read-only project layout and source collector
T003: concept evidence collector
T004: RTL evidence collector
T005: deterministic mapping claim builder
T006: grounding checker and report
T007: CLI, rendering and smoke tests
```

Do not start multiple slices if their write scopes overlap.

## Acceptance

P1b is acceptable when:

```text
- p1b-trace-concept runs on the primary sample without modifying the target project.
- generated artifacts are under /tmp or /private/tmp.
- concept_trace_graph.json contains at least one mapping claim or a clear unknown result.
- every mapping claim has evidence ids and confidence.
- no unsupported confirmed mapping claim exists.
- concept_trace_index.json can reverse-index claims and evidence.
- concept_trace.mmd shows L5/L6/RTL nodes with confidence labels.
- grounding_report.json is generated from structured graph data.
- CLI returns nonzero when blocking grounding diagnostics exist.
- tests cover success, unknown concept and unsafe output path.
- all existing P1a / P1a+ tests still pass.
```

## Review Gate

Before handing implementation back to the user, run a Review Agent focused on:

```text
- direction drift
- evidence grounding
- RTL mapping overclaim
- target project mutation
- generated artifact completeness
```

P1b should not be marked complete until Review Agent findings are either fixed or explicitly deferred in docs.
