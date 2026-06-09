# Review 0008: Desktop Agent Shell V0.2 Readiness

Date: 2026-06-09

## 1. Verdict

**Desktop Agent Shell V0.2 Candidate: READY WITH LIMITATIONS**

The Desktop Agent Shell has evolved from a passive artifact viewer (V0.1, T009–T010) into a **local deterministic Agent shell prototype** (V0.2, T011–T012a). It can now:

- Accept user questions about the loaded P1a/P1b artifact bundle.
- Route those questions via bilingual keyword matching into 9 deterministic answer types.
- Return structured answers with referenced claim/evidence/node/diagnostic IDs.
- Generate a read-only tool plan preview showing what a future Agent mode would need to read and why.
- Inherit referenced IDs from the answer layer into the plan layer for grounding continuity.
- Display fixed safety notes on every plan, enforcing no-execution, no-LLM, no-mutation boundaries.

**It is not yet a real Agent.** There is no LLM semantic reasoning, no multi-turn memory, no tool execution loop, no autonomous project modification, and no Vivado/synthesis integration. It is the **shell skeleton** that a future ReAct Agent runtime can fill.

---

## 2. Capability Matrix

### T009: Artifact Loader + Desktop GUI Tabs

| Item | Detail |
|---|---|
| **Capability** | Load P1a/P1b artifact bundles from `/tmp` or `/private/tmp`; detect bundle type; validate with structured diagnostics; display in 4 GUI tabs (Run Summary, JSON Tree, Markdown, Diagnostics). |
| **Artifact fields consumed** | All P1b artifacts: `concept_trace_graph.json`, `concept_trace_index.json`, `grounding_report.json`, `run_metadata.json`, `concept_trace.md`, `concept_trace.mmd`. P1a: `project_graph.json`, `trace_index.json`, `run_metadata.json`, etc. |
| **User-visible effect** | User selects artifact directory → app loads bundle → displays summary, tree, markdown, diagnostics. Graceful fallback when PySide6 is missing. |
| **Current limitation** | PySide6 is not a project dependency; user must `pip3 install pyside6` manually. No GUI automation or screenshot tests. |
| **Tests / validation** | 18 loader tests + 17 VM tests = 35 desktop tests. `load_bundle()` tested on nonexistent paths, empty dirs, partial bundles. |

### T010: Concept Trace Structured Table View

| Item | Detail |
|---|---|
| **Capability** | Display P1b concept trace in 5 structured sub-tables: Nodes, Edges, Claims, Evidence, Diagnostics. Cross-reference resolution (edge labels via node map, evidence→claim refs, diagnostic counts). Dangling reference marking. |
| **Artifact fields consumed** | `concept_trace_graph.json`: nodes, edges, mapping_claims, evidence_items, grounding_diagnostics, uncertainty_notes. `concept_trace_index.json`: cross_references. |
| **User-visible effect** | User clicks "Concept Trace" tab → sees 5 sub-tabs with sortable data. Unknown confidence displayed neutrally. Blocking diagnostics shown as warnings, not audit results. |
| **Current limitation** | Table view only; no click-to-navigate popovers, no filtering, no graph layout. Single concept trace per bundle. |
| **Tests / validation** | 17 trace VM tests. Cross-reference, dangling reference, diagnostic dedup tested. |

### T011: Local Deterministic Agent Query Panel

| Item | Detail |
|---|---|
| **Capability** | Agent tab with question input → deterministic rule-based answer. 9 question types: summary, claims, evidence, diagnostics, unknown, nodes, edges, claim_detail (by MC_* ID), evidence_detail (by E:* ID). Bilingual keyword matching (Chinese + English). Returns `AgentPanelResponse` with referenced IDs and uncertainty notes. |
| **Artifact fields consumed** | All P1b artifacts via `artifact_loader` helpers. P1a bundles return limited summary. |
| **User-visible effect** | User types question → answer appears in read-only text box. Unsupported questions get clear fallback message. No external LLM, no API key. |
| **Current limitation** | Keyword-based routing only; no natural language understanding. No multi-turn context. No fuzzy matching. P1a bundles have reduced query surface. |
| **Tests / validation** | 35 dedicated tests in `test_desktop_agent_panel_models.py`. Covers all 9 types + unsupported + incomplete bundle + no PASS/FAIL. |

### T011a: Diagnostics Deduplication Correction

| Item | Detail |
|---|---|
| **Capability** | Diagnostics from `concept_trace_graph.json` (grounding_diagnostics) and `grounding_report.json` (diagnostics) are merged and deduplicated before display. Primary key: `diagnostic_id`. Fallback key: `(target_claim_id, issue_type, message)`. |
| **Artifact fields consumed** | `concept_trace_graph.grounding_diagnostics[]`, `grounding_report.diagnostics[]`. |
| **User-visible effect** | Diagnostics panel and Agent query no longer double-count the same diagnostic. Claim detail answers show correct diagnostic count. |
| **Current limitation** | Dedup key is string-based; structural equivalence beyond these fields is not checked. |
| **Tests / validation** | 3 new dedup-specific tests. Existing diagnostics and claim_detail tests updated to verify corrected counts. |

### T012: Read-only Tool Plan Preview

| Item | Detail |
|---|---|
| **Capability** | For every user question, generate a `AgentPlanPreview` showing: intent, ordered `AgentPlanStep` list (step_id, title, rationale, read_artifacts, referenced_*_ids), fixed safety notes, unsupported reason. Steps are marked `is_executable_now=False` and `allowed_action="read_only_preview"`. Inherits referenced IDs from T011 response via duck-typed `getattr`. |
| **Artifact fields consumed** | Same as T011; plan builders read graph/index/grounding metadata to decide which artifacts a future Agent would need. |
| **User-visible effect** | Plan preview appears in a second read-only text box below the answer. Shows what a future Agent would read and why. No execution button, no LLM. |
| **Current limitation** | Plan is static text; not executable. No dynamic plan adjustment based on intermediate results. No tool schema definition. |
| **Tests / validation** | 19 dedicated tests in `test_desktop_agent_plan_models.py`. Covers all 9 intents + unsupported + safety notes + step properties + response inheritance. |

### T012a: Import Cycle / Helper Cleanup

| Item | Detail |
|---|---|
| **Capability** | Shared helpers extracted to `agent_query_utils.py`: `has_any()`, `deduplicate_diagnostics()`, `extract_claim_id()`, `extract_evidence_id()`. `agent_panel_models.py` and `agent_plan_models.py` no longer import each other. `response` param is `Any` with `getattr` duck-typing. |
| **User-visible effect** | No behavioral change; internal architecture improvement. |
| **Current limitation** | `Any` type annotations produce pyright `reportExplicitAny` suppression comments; no formal protocol/interface for the response duck type. |
| **Tests / validation** | All 293 existing tests pass. 0 basedpyright import-cycle errors. Compile check clean. |

---

## 3. Agent Direction Check

### How current capabilities serve a real Agent

| Current Capability | Agent Role |
|---|---|
| **Artifact bundle** (`ArtifactBundle` + `artifact_loader`) | Observation memory: the Agent's starting context is a loaded, validated bundle of structured artifacts. No ad-hoc file reads. |
| **Local deterministic query** (`query_artifact_bundle`) | Tool response: a future Agent can call this as a deterministic "observe" tool to retrieve structured answers with grounded ID references. |
| **Plan preview** (`build_agent_plan_preview`) | Pre-ReAct planning skeleton: shows what an Agent would plan to read before reading it. Provides a structured step list that can be mapped to a real tool dispatch loop. |
| **Referenced IDs** (`referenced_claim_ids`, etc.) | Grounding anchors: every answer and plan step carries the specific artifact IDs it references. A future Agent can use these as provenance links rather than free-text citations. |
| **Safety notes** (`_default_safety_notes()`) | Execution guardrails: every plan step is tagged read-only-preview, no-LLM, no-Vivado, no-mutation. A future Agent runtime must check these before executing any step. |

### What it is NOT yet

```text
- No LLM semantic reasoning or natural language understanding.
- No multi-turn conversation memory or context window management.
- No tool execution loop (observe → plan → act → observe).
- No autonomous project modification.
- No Vivado / synthesis / implementation / bitstream execution.
- No schema-level Desktop Shell contract test.
- No real ReAct-like runtime with observation, reasoning, tool dispatch.
```

The current system is the **deterministic backbone** of a future Agent. The Agent's reasoning layer (LLM or rule-based) would sit above this backbone, using the bundle as context, the query as a tool, the plan as a scaffolding, and the referenced IDs as grounding anchors.

---

## 4. Safety / Boundary Review

All hard constraints remain enforced:

```text
✅ No Web GUI — PySide6 native desktop only.
✅ No browser-accessible URL — no HTTP server.
✅ No Electron — Qt framework only.
✅ No external LLM / API / API key — all query and plan logic is deterministic Python.
✅ No Vivado / synthesis / implementation / bitstream — not invoked, not referenced.
✅ No target project mutation — all reads are from /tmp or /private/tmp artifact bundles.
✅ No PASS / HOLD / finding / audit semantics — diagnostics are overclaim warnings, not audit results.
✅ Default artifact consumption from /tmp or /private/tmp — user must explicitly open a directory.
```

Safety notes are enforced at two levels:

1. **Code level**: `AgentPlanStep.is_executable_now=False` and `allowed_action="read_only_preview"` are hardcoded defaults. No code path sets them to executable.
2. **Display level**: Every plan preview includes the full safety notes list. No execution button exists in the GUI.

---

## 5. Technical Debt / Known Risks

| # | Item | Severity | Notes |
|---|---|---|---|
| 1 | **PySide6 not a project dependency** | Medium | User must manually `pip3 install pyside6`. No `pyproject.toml` or `requirements.txt` entry. Could break on PySide6 major version updates. |
| 2 | **No GUI automation / screenshot tests** | Medium | All GUI testing is manual. No pytest-qt, no screenshot comparison, no accessibility audit. Visual regressions are invisible to CI. |
| 3 | **Single concept trace per bundle** | Medium | Only one concept per P1b run. No batch multi-concept loading or cross-concept view in the desktop shell. |
| 4 | **RTL collector is regex-based** | Medium | Misses complex SystemVerilog constructs (generate blocks, interfaces, packages, classes). Evidence may be incomplete without overclaim. |
| 5 | **JSON dict `Any` warnings remain** | Low | `agent_plan_models.py` and `agent_panel_models.py` use `dict[str, Any]` with `# pyright: ignore[reportExplicitAny]` suppressions. No typed schema for graph JSON contents in the desktop layer. |
| 6 | **No schema-level Desktop Shell contract test** | Low | No test validates that the Desktop Shell's `AgentPanelResponse` / `AgentPlanPreview` dataclass fields match an externally defined contract. Schema evolution could break silently. |
| 7 | **No real LLM / ReAct loop** | Low (by design) | The system is a deterministic shell, not an Agent. But the gap between "plan preview" and "plan execution" is the entire Agent runtime. |
| 8 | **Plan Preview is not execution** | Low (by design) | Plans are read-only text. No tool dispatch, no intermediate result handling, no retry logic. |
| 9 | **P1a / P1b artifact compatibility needs consolidation** | Low | P1a and P1b bundles have different artifact structures. The Desktop Shell handles both but with reduced functionality for P1a. A future unified artifact schema would reduce branching. |
| 10 | **Duck-typed response parameter** | Low | `build_agent_plan_preview()` accepts `Any | None` for `response` and uses `getattr`. No formal protocol or interface. Refactoring could introduce silent attribute misses. |

---

## 6. Next Stage Recommendations

Three candidate directions, ordered by recommended priority:

### T015: Agent Runtime Contract (Recommended First)

Define the structured artifact contract for a ReAct-like Agent loop **without** implementing the loop itself or connecting to a real LLM.

Artifacts to define:

| Artifact | Purpose |
|---|---|
| `UserTask` | User's original question + context bundle reference |
| `Observation` | Snapshot of relevant artifact state at loop start |
| `ReasoningSummary` | Deterministic or LLM-generated reasoning about the observation |
| `ToolPlan` | Ordered list of proposed tool calls with rationale |
| `ToolCallProposal` | Single proposed tool invocation: tool name, params, expected artifact reads |
| `ToolResult` | Output from executing a tool call (deterministic or mocked) |
| `Answer` | Final structured answer with referenced IDs + confidence |
| `GraphWriteProposal` | Proposed mutations to the artifact graph (future, blocked by default) |

This contract defines the **data flow** of a ReAct loop without requiring a real LLM provider. The deterministic query (T011) and plan preview (T012) already produce partial versions of these artifacts.

### T014: Desktop Shell Usability Hardening

Before adding Agent features, stabilize the existing Desktop Shell:

- PySide6 dependency strategy: add to `pyproject.toml` optional dependencies or document version pinning.
- Sample artifact open command: `desktop_app --sample` that opens a built-in test bundle.
- GUI smoke screenshot: manual test doc with expected screenshots for each tab.
- Tab keyboard navigation and focus management.
- Error state display when bundle fails to load (currently silent in some paths).

### T016: Local No-op ReAct Dry Run

Implement a deterministic/noop ReAct loop using the T015 contract:

```
UserTask → Observation (load bundle) → ToolPlan (from T012 plan preview)
  → ToolCallProposal (deterministic, no LLM) → ToolResult (from T011 query)
  → Answer (structured, with referenced IDs)
```

No real LLM. No dangerous tool execution. No external API. The loop runs once (single-turn) and terminates. Its purpose is to validate the artifact contract end-to-end with deterministic data.

**Recommendation: T015 first.** Defining the Agent Runtime Contract before building more UI or implementing a loop ensures that future work has a stable data contract to target. T014 can proceed in parallel if needed. T016 depends on T015.

---

## 7. Test Summary

```text
Total tests:            293  ✅ (0 failures)
  P1a tests:             18
  P1b tests:            176
  Desktop loader:        18
  Desktop VM:            17
  Desktop trace VM:      17
  Agent panel models:    35  (T011 + T011a)
  Agent plan models:     19  (T012)
Compile check:         clean
basedpyright:          0 import-cycle errors
```

---

## Review Conclusion

### Sign-off

```text
Review 0008 author: Claude Opus 4.8
Date: 2026-06-09
Tests: 293/293 pass
Compile: clean
basedpyright: 0 import-cycle errors
Conclusion: V0.2 READY WITH LIMITATIONS
Next recommended: T015 (Agent Runtime Contract)
```
