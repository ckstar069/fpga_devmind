# Current Position and Drift Analysis

This document records the Web GPT review of the project direction after T047/T047.1. It is intended to prevent future sessions or local agents from losing the original product intent.

Status date: 2026-06-10
Current PR context: PR #4, `t047-ephemeral-real-provider-adapter`, after T047.1 safety hardening report. PR #4 is not considered complete until Web GPT reviews the actual diff and the PR is merged.

## 1. Original product intent

`fpga_devmind` is an FPGA Develop-Understand Agent prototype, not a generic static analyzer, report generator, audit dashboard, or JSON artifact viewer.

The core user problem is that AI-assisted FPGA projects grow through many stages, and the user cannot reliably understand what each stage actually implements by reading filenames, tests, or raw code alone. The tool should help the user understand implementation meaning through evidence-grounded explanations and diagrams.

The original useful output should look like what an experienced FPGA engineer would draw and explain after reading the code:

- main processing flow;
- dataflow from inputs to outputs;
- intermediate signals and their meanings;
- module responsibilities;
- key formulas and transformations;
- fixed-point / Q-format / bit-width handling;
- stage-to-stage differences;
- source evidence references;
- explicit uncertainty notes.

## 2. Non-negotiable direction

The project must remain Agent-first:

```text
source evidence
  -> semantic understanding
  -> structured graph / claims / uncertainty
  -> visual explanation
  -> evidence drill-down and follow-up questions
```

Normal software infrastructure is necessary, but it is only infrastructure:

- CLI;
- artifact storage;
- index/cache/config;
- Tauri desktop shell;
- graph rendering;
- provider boundary;
- security gates;
- audit summaries.

These must not replace the semantic Agent kernel.

## 3. Current state summary

The project has made strong progress on infrastructure and safety:

- deterministic project/bundle understanding artifacts;
- graph/evidence/pipeline UI surfaces;
- Agent Q&A shell;
- provider boundary and policy/audit layers;
- dry-run request package;
- approval gate;
- blocked/mock transport;
- egress guard;
- first real provider adapter behind an ephemeral manual send gate.

T047/T047.1 are valuable because they make real LLM usage possible under strict constraints. However, real provider access is not the product goal by itself.

## 4. Main drift risk

The main drift risk is not that the project is going in the wrong direction. The direction is still broadly correct.

The risk is sequencing drift:

```text
implemented quickly:
  UI shell / provider boundary / safety gates / real provider adapter

still incomplete:
  LLM/Agent semantic understanding -> structured claims -> diagrams -> evidence-grounded explanations
```

If the project continues adding provider or UI surface area before closing the semantic loop, it may become a polished LLM wrapper over artifacts rather than an FPGA understanding Agent.

## 5. Current completion estimate

These are engineering estimates, not formal release metrics:

| Area | Approximate state | Notes |
|---|---:|---|
| P1a single-stage deterministic understanding | 85-95% | Mostly usable; quality and edge cases remain. |
| Desktop artifact / graph / evidence viewer | 65-75% | Useful but still needs dogfood-driven UX fixes. |
| Agent Q&A deterministic shell | 60-70% | Works, but not yet a semantic LLM Agent. |
| Real provider safety layer | 70-85% | T047.1 must be reviewed before acceptance. |
| LLM semantic reasoning / structured claims | 20-35% | Provider exists, but semantic output loop is not done. |
| P1b L5/L6-to-RTL concept trace | 40-55% | Foundations exist; original P1b workflow needs closure. |
| P1c verification coverage explanation | 15-25% | Still largely future work. |
| Development Companion Agent | 5-10% | Not a current-stage capability. |
| Review/Audit Agent | 10-20% | Do not make this the main track yet. |

Current-stage useful product completion is approximately 60-70% if the target is: read a project/stage, explain it, draw useful diagrams, cite evidence, and mark uncertainty.

Full Develop-Understand-Verify Agent Platform completion is much lower, roughly 20-30%.

## 6. What counts as “truly usable” next

For the next local dogfood milestone, the tool should answer these questions for real FPGA projects such as `fpga_project_coarse_sync_glm` and `fpga_project_fine_cfo`:

- What does this L5/L6/RTL stage actually implement?
- Where does the data come from, and where does it go?
- What are the key intermediate signals?
- What formulas or transformations are used?
- What Q-format / bit-width / fixed-point handling exists?
- What changed from L5 to L6?
- Which RTL modules/signals correspond to Python concepts?
- Which statements have source evidence?
- Which statements are inferred or unknown?

A version is meaningfully useful only when the answers are grounded in evidence and can be visualized, not merely returned as free-form LLM prose.

## 7. Recommended next sequence after T047.1

Do not continue with provider feature expansion immediately after T047.1.

Recommended sequence:

1. **T048: Real Project Dogfood Against Original Understanding Goals**
   - Use real coarse/fine CFO bundles.
   - Run the original understanding questions.
   - Judge pass / partial / fail against the original success criteria.
   - Produce a dogfood report and a concrete fix list.

2. **T049: Evidence-Grounded LLM Semantic Output Contract**
   - LLM output must become structured data, not only prose.
   - Minimum objects: `Claim[]`, `EvidenceLink[]`, `Uncertainty[]`, `SignalTable[]`, `FormulaNote[]`, `DiagramIntent[]`.
   - Every claim must cite evidence or be explicitly marked inferred/unknown.

3. **T050: Diagram and Explanation Generation from Semantic Claims**
   - Generate user-readable flow/dataflow diagrams from structured semantic output.
   - Render signal tables, formula notes, Q-format notes, module explanations, source evidence, and uncertainty.

4. **T051: P1b Concept Trace Closure**
   - Close the original `p1b-trace-concept` workflow.
   - Produce concept trace graph/index/markdown/mermaid/grounding report for `peak_idx` or `metric`.

5. **T052: P1c Verification Coverage Slice**
   - Explain which semantic nodes are covered by cocotb/tests.
   - Keep this separate from PASS/HOLD audit conclusions.

## 8. What not to do next

Avoid these until the semantic understanding loop is stronger:

- multi-provider key manager;
- streaming provider UI;
- chat history persistence;
- audit finding dashboard;
- PASS/HOLD decision system;
- broad dependency or UI refactors;
- automatic target project mutation;
- replacing structured graph output with Markdown-only summaries.

## 9. Review rule for future agents

Before implementing new tasks, read this document together with:

- `PROJECT_CONTEXT.md`;
- `docs/documentation-map.md`;
- `docs/product-target.md`;
- `docs/roadmap.md`;
- `docs/phase1-scope.md`;
- `docs/implementation-status.md`.

If a proposed task does not move the project toward evidence-grounded FPGA understanding, diagrams, source provenance, uncertainty, or usable project/stage explanations, it should be questioned before implementation.
