# Implementation Status

## Current State

**P1b + Desktop Shell V0.2 is READY WITH LIMITATIONS.** Review 0008 passed on 2026-06-09 with 293/293 tests and zero failures.

V0.2 means:

```text
- P1a: Read-only L6_resource_opt understanding with grounded ProjectGraph and query shell.
- P1b: One-concept L5/L6-to-RTL deterministic trace with 6 schema-validated artifacts.
- Desktop Shell V0.1 (T009–T010): PySide6 artifact viewer with structured trace tables.
- Desktop Shell V0.2 (T011–T012a): Local deterministic Agent query panel + read-only tool
  plan preview. 9 question types, bilingual keyword matching, referenced ID grounding,
  fixed safety notes. No LLM, no execution, no mutation.
- All artifacts are read-only. No target project mutation, no Vivado, no external API,
  no PASS/HOLD, no LLM in pipeline.
- It is a deterministic Agent shell prototype, not yet a real LLM/ReAct Agent.
```

Implemented:

- CLI entry point: `fpga-devmind p1a-understand-stage`
- CLI entry point: `fpga-devmind p1a-query`
- CLI entry point: `fpga-devmind p1a-freshness`
- CLI entry point: `fpga-devmind p1a-smoke`
- CLI entry point: `fpga-devmind p1a-agent-understand-stage`
- CLI entry point: `fpga-devmind desktop-sample-run` (T018)
- P1a dataclass schema objects.
- Read-only project tree scan.
- Read-only L6 Python symbol and evidence extraction.
- Read-only config parameter extraction.
- Deterministic P1a claim generation for L6 resource optimized stages.
- Generic L6 concept inference when the project does not match the coarse-sync S0-S3 pattern.
- Inferred implementation-order edges with explicit uncertainty; proven dataflow is not claimed.
- Basic grounding checks for unsupported confirmed claims and unsupported visualization nodes/edges.
- Structured fixed-point, stream interface, and pipeline timing specs in `project_graph.json`.
- Structured resource estimate specs extracted from L6 `ResourceEstimate(...)` evidence.
- `trace_index.json` and `trace.md` for claim/spec/evidence back-tracing.
- `memory_manifest.json` source snapshot and freshness checking.
- Deterministic query shell over generated ProjectGraph and TraceIndex artifacts.
- Freshness warning in query answers when generated artifacts are stale or unverifiable.
- Artifact writing to `/tmp/fpga_devmind/p1a_coarse_sync_l6`.
- Rendered `project_graph.json`, `trace_index.json`, `memory_manifest.json`, `summary.md`, `flow.mmd`, `trace.md`, `run_metadata.json`.
- Smoke validation on `fpga_project_coarse_sync_glm` and `fpga_project_fine_cfo`.
- P1a V0.1 quickstart for smoke, single-project run, query and freshness.
- Explicit uncertainty notes in generated graph, query output and smoke report.
- External-API-free P1a+ Agent dry-run that writes `agent_trace.json`, `prompt_context.json`, `provider_call.json`, `model_result_normalized.json`, `claim_proposals.json`, `graph_write_proposal.json`, `project_graph_proposed.json`, `trace_index_proposed.json`, `graph_write_report.json`, `grounding_report.json` and `answer.md`.
- LLM provider contract helpers that build redacted prompt context and validate model `SemanticReasoningResult` before grounding.
- Noop and fixture semantic provider adapters for testing provider boundaries without external API calls.
- Built-in mock semantic provider for positive validation / GraphWriter dry-run path without external API calls.
- Output path safety guard for P1a, P1a smoke and P1a+ generated artifacts.
- Model output validation for schema_version, claims, claim types, subject namespaces, requested follow-up tools, proposed edges and proposed uncertainties.
- Global model-output blocking diagnostics block all model claim graph-write proposals.
- Graph write proposal now separates accepted model claims from rejected model claims without mutating ProjectGraph.
- GraphWriter dry-run writes `project_graph_proposed.json`, `trace_index_proposed.json` and `graph_write_report.json` without overwriting source `project_graph.json` or `trace_index.json`.
- Redacted provider configuration drafts for future DeepSeek / GLM / OpenAI adapters, with real API calls disabled by default.
- Disabled external provider route for DeepSeek / GLM / OpenAI that writes blocked provider_call metadata without loading API keys or calling external APIs.
- Explicit `--allow-external-api` gate that currently reaches `external_provider_not_implemented` without loading API keys or calling external APIs.

### P1b (T001–T007) — One-concept L5/L6-to-RTL trace pipeline

- P1b artifact schema (T001): `ConceptTraceGraph`, `ConceptTraceIndex`, `ConceptTraceNode`, `ConceptTraceEdge`, `MappingClaim`, `StageConceptView`, `RTLEvidenceView` with strict validation (confidence, bridge_kind, node_kind, edge_type enums) and JSON round-trip.
- Read-only source collector (T002): `collect_p1b_sources()` discovers L5/L6 Python, RTL Verilog/SystemVerilog and test candidate files from project tree. Produces `SourceCollection` with deterministic ordering, `__init__.py` / `__pycache__` exclusion and missing-section diagnostics.
- Concept evidence collector (T003): `collect_concept_evidence()` extracts L5/L6 class/function/method occurrences with strength classification (strong/medium/weak), role hints (calculation, state_update, interface, pipeline) and deterministic `evidence_id` generation. Handles syntax errors gracefully.
- RTL evidence collector (T004): `collect_rtl_evidence()` scans modules, always blocks, assigns, signals, parameters and comments via regex-based line matching. Distinguishes name-match vs body-match vs comment-only. Produces `RTLEvidenceCollection` with `RTLObjectView`.
- Conservative mapping claim builder (T005): `build_mapping_claims()` bridges T003/T004 evidence into `MappingClaim` with deterministic bridge_kind classification, confidence downgrade rules (naming_only → inferred, one-sided → unknown/inferred, both sides + non-weak bridge → supported). Never produces `confirmed` in first implementation. Propagates upstream uncertainty.
- Grounding checker (T006): `check_grounding()` inspects mapping claims for blocking overclaims (unsupported confirmed, naming_only supported, missing evidence side, zero evidence) and non-blocking diagnostics (one-sided evidence, weak bridge). Defense-in-depth checks via mutation tests.
- CLI pipeline / render / smoke (T007): `p1b-trace-concept` command chains T002–T006, builds `ConceptTraceGraph` and `ConceptTraceIndex`, renders `concept_trace.md` and `concept_trace.mmd`, and writes 6 artifacts. Output path guarded by `ensure_safe_output_dir()`. Returns nonzero exit code for blocking diagnostics. 194 tests (18 P1a + 176 P1b) pass.
- Desktop app prototype (T009): PySide6-based minimum viable shell with artifact directory picker, Run Summary view, JSON Tree Browser, Markdown Preview, and Diagnostics tab. Graceful fallback when PySide6 is missing. Artifact loader (`desktop/artifact_loader.py`) and view models (`desktop/view_models.py`) are pure Python and testable without GUI. 229 tests (194 P1a/P1b + 35 desktop) pass.
- Local Agent Interaction Panel (T011): Deterministic rule-based query panel inside the Desktop Shell Agent tab. No external LLM, no API key, no Web server. Supports bilingual keyword routing for summary, claims, evidence, diagnostics, unknown, nodes, edges, and specific claim/evidence ID lookups. Returns `AgentPanelResponse` with referenced IDs, uncertainty notes, and unsupported fallback. Pure Python view model (`desktop/agent_panel_models.py`) with 35 dedicated tests. 274 tests total pass.
- Agent Tool Plan Preview (T012): Read-only tool/action plan preview in the Agent tab. For every user question, shows what artifacts a future Agent mode would read and why. No execution, no LLM, no API. Inherits referenced IDs from T011 response. 9 intent types covered with fixed safety notes. Pure Python view model (`desktop/agent_plan_models.py`) with 19 dedicated tests. 293 tests total pass.
- Agent Runtime Contract (T015): Structured artifact definitions for a future ReAct-like Agent loop. 9 dataclasses (UserTask, Observation, ReasoningSummary, ToolPlan, ToolCallProposal, ToolResult, Answer, GraphWriteProposal, AgentRuntimeTrace) with validation, JSON round-trip, and cross-reference integrity checking. Schema version `agent-runtime-contract-0.1`. No execution, no LLM, no API. Pure Python contract module (`agent_runtime_contract.py`) with 60 dedicated tests. 353 tests total pass.
  - T015a: Strengthened cross-reference validation — ToolPlan.steps task_id check, ToolResult.proposal_id existence check, Answer limitations auto-ensure `no_llm_semantic_reasoning`. 68 dedicated tests. 361 tests total pass.
- Local No-op ReAct Dry Run (T016): Deterministic single-turn Agent runtime that chains T011 (query) + T012 (plan preview) + T015 (runtime contract) into one observe→plan→propose→simulated-result→answer→blocked-graph-write trace. No LLM, no API, no execution. CLI entry point: `agent-noop-run`. Outputs `agent_runtime_trace.json` + `answer.md`. 19 dedicated tests. 380 tests total pass.
  - T016a: Propagate runtime validation diagnostics — `validate_runtime_trace()` errors now propagated into `trace.runtime_diagnostics` and cause `status="blocked"`. 20 dedicated tests. 381 total.
- Desktop Shell Usability Hardening (T014): PySide6 optional dependency in `pyproject.toml` (`.[desktop]`), sample artifact discovery helper (`find_recent_artifact_bundles()`), `--recent` CLI flag, GUI load-state clarity improvements (Diagnostics/Concept Trace/Plan Preview empty states), manual GUI smoke test docs. 387 tests total pass.
- Desktop Agent Runtime Trace Viewer (T017): GUI recognizes, loads, and displays `agent_runtime_trace.json` from T016's `agent-noop-run`. New Agent Runtime tab with summary form, steps timeline table, and runtime diagnostics table. Pure viewer — no Agent execution, no LLM. View model (`desktop/agent_trace_view_models.py`) with 8 section types (task/observation/reasoning/plan/proposal/result/answer/graph_write). Graph write status uses "blocked"/"allowed", never PASS/HOLD. T016 no-op always generates "blocked"; "allowed" display is forward-compatible only, does not enable graph mutation. 14 new tests (13 view model + 1 sample artifacts). 401 tests total pass.
- Desktop GUI First-Run Smoke and Usability Hardening (T018): New `desktop-sample-run` CLI subcommand chains `p1b-trace-concept` → `agent-noop-run` into one invocation with sensible defaults. New `desktop_sample_run.py` module with `DesktopSampleResult` dataclass. Updated smoke-test docs with Quick Start section and Current GUI Capabilities declaration. Updated quickstart with one-click trial command. 6 new tests. No LLM, no API, no Vivado, no fpga_project_* mutation, no graph write execution, no PASS/HOLD/finding/audit.
- Desktop Agent Shell UX Pivot (T019): Transformed the first screen and core interaction from artifact/debug viewer to user-understandable FPGA Agent tool. New `overview_models.py` with `OverviewViewModel`, `SuggestedQuestion`, `EvidenceStrengthSummary`, `MappingConfidenceSummary`, `build_overview_view_model()`, `format_concept_trace_summary()`. 8 GUI changes: Overview first screen, Concept Understanding with natural-language summary, Agent tab with Chinese suggestions, Developer tab (demoted JSON Tree), Agent Runtime conditional visibility, window title update, improved empty/help states. 15 new tests. Tab order: Overview → Concept Understanding → Agent → Markdown → Diagnostics → Developer → Agent Runtime. No LLM, no API, no Vivado, no fpga_project_* mutation, no graph write execution, no PASS/HOLD/finding/audit.
- AgentScope-style Desktop Product Shell (T020): Complete GUI重构 from PySide6 tab widget to AgentScope-style product shell with left navigation sidebar, main workspace, and card-based overview. New `product_shell.py` with MainWindow, 12 pages, dark sidebar navigation (#1e1e2e), top bar with project info, QStackedWidget content area. New pages: 概览 (product homepage with metrics cards), 概念追踪, 证据 (grouped by L5/L6/RTL/Bridge), 不确定项 (limitations + why-not-confirmed), Agent 问答 (dominant entry), Agent Runtime (conditional with guidance for P1b), 计划与工具, 开发者区 (Raw Data/Markdown/Diagnostics), 设置. New `page_view_models.py` with `EvidencePageViewModel`, `UnknownsPageViewModel`, `OverviewMetrics`, `AgentRuntimePageState`, and builders. `_gui.py` rewritten as thin wrapper. 15 new tests. 437 tests total pass. Window title: "FPGA DevMind".
- Product Shell Static Cleanup and Plan/Tools Activation (T020a): Fixed 26 basedpyright errors in T020 files (Qt enum access, Optional layout items, QWidget dynamic attributes, uninitialized instance variables, unused imports). Activated Plan/Tools page: now syncs with Agent QA plan preview, shows guidance when empty. Added `PlanToolsPageState` dataclass and builder. 3 new tests. 440 tests total pass. 0 basedpyright errors.

Not implemented yet:

- LLM provider integration.
- Prompted semantic claim generation.
- Multi-turn ReAct loop.
- Model-generated CandidateClaims.
- Provider-backed model calls.
- Runtime API key loading.
- Rich AST def-use / dataflow analysis.
- Proven producer/consumer dataflow extraction.
- High-quality generic flow ordering for every possible L6 architecture.
- Full fixed-point spec extraction.
- Full interface / pipeline / state event extraction.
- Full symbolic resource total evaluation.
- P1c verification coverage.
- Desktop GUI / Agent Shell prototype（桌面端软件，非 Web）。T009–T012a 已完成从 artifact viewer 到本地确定性 Agent shell 原型的演进。详见 `docs/reviews/0007-p1b-desktop-v0.1-readiness-review.md`（V0.1）和 `docs/reviews/0008-desktop-agent-shell-v0.2-readiness-review.md`（V0.2）。
- Interactive memory.
- Agent Runtime Contract（T015 ✅）：ReAct-like loop 的结构化 artifact 定义已完成。详见 `docs/tasks/T015-agent-runtime-contract.md`。

### P1b Current Limitations

```text
- Deterministic evidence extraction only (no LLM in pipeline).
- Regex-based RTL scanning; no full SystemVerilog parser.
- Single-concept trace per run (no batch multi-concept).
- No interactive graph editing or claim mutation.
- Mermaid render is static text; no live diagram viewer.
- No cross-concept structural edges (evolution / structural).
- No AST-level def-use or proven dataflow.
```

## P1b Commands

Run one-concept trace:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_devmind/p1b_peak_idx
```

Unknown concept (legitimate unresolved output):

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept nonexistent_xyz \
  --out /tmp/fpga_devmind/p1b_unknown
```

Unsafe path is rejected:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_project_test/output
# → error: path must not be inside an fpga_project_* tree
```

## P1b Artifacts

Each run writes 6 artifacts to the output directory:

```text
concept_trace_graph.json    # ConceptTraceGraph: nodes, edges, claims, evidence, diagnostics
concept_trace_index.json    # ConceptTraceIndex: claim/evidence/node/edge/cross-ref indexes
concept_trace.md            # Human-readable Markdown summary
concept_trace.mmd           # Mermaid diagram (static text)
grounding_report.json       # T006 grounding diagnostics + summary
run_metadata.json           # Elapsed time, status, artifact list
```

## Next Phase: Desktop GUI / Agent Shell (T008–T010)

P1b 结构化 artifact 就绪后，下一阶段推进桌面端 Agent Shell / Desktop GUI：

- T008: Desktop artifact viewer contract — 定义桌面 GUI 如何读取 P1a/P1b artifact 并渲染交互视图。已完成：详见 `docs/tasks/T008-desktop-artifact-viewer-contract.md` 和 `docs/desktop-agent-shell-plan.md`。
- **T009: Desktop app prototype ✅** — 最小可运行桌面软件原型，支持 artifact 目录选择、JSON 树浏览、Markdown 预览与 Mermaid source 展示。macOS/Linux 优先，Windows 其次。详见 `docs/tasks/T009-desktop-app-prototype.md`。
- **T010: P1b concept trace view ✅** — 在桌面 GUI 中以结构化表格展示 concept trace：Nodes、Edges、Claims、Evidence、Diagnostics 五个子表。支持 cross-reference 解析、dangling reference 标记、unknown confidence 正常展示。详见 `docs/tasks/T010-desktop-p1b-concept-trace-view.md`。非图布局引擎，非 Agent chat。
- **T011: Local Agent Interaction Panel ✅** — 桌面 Agent Tab，支持用户输入确定性问题，基于当前已加载的 P1a/P1b artifact bundle 做本地规则化查询并返回答案。不调用外部 LLM，不加载 API key。支持 summary、claims、evidence、diagnostics、unknown、nodes、edges、claim_detail、evidence_detail 共 9 类问题类型，中英双语关键词匹配。详见 `docs/tasks/T011-desktop-local-agent-panel.md`。
- **T012: Agent Tool Plan Preview ✅** — 在 Agent Tab 中增加只读工具计划预览。用户提问后，除返回答案外，还展示“未来 Agent 模式需要读取哪些 artifact、为什么需要这些证据”的 plan preview。不执行工具，不调用 LLM，不提供执行按钮。9 类 intent 全覆盖，固定 safety notes。详见 `docs/tasks/T012-agent-tool-plan-preview.md`。

方向约束：
```text
- 不做 Web GUI。
- 桌面端是 Agent runtime shell：读取 /tmp 或 /private/tmp 下的 artifact → 渲染 → 接受用户指令 → 调用后续工具。
- 桌面端本身不运行 Vivado / synthesis / implementation / bitstream。
- 桌面端不修改 fpga_project_* 目标项目。
```

Ready for controlled implementation planning:

- P1b one-concept L5/L6-to-RTL trace.
- Claude / Kimi implementation handoff using task cards under `docs/tasks/`.
- Desktop GUI prototype planning after P1b structured artifacts are available.
- Review gate before marking P1b complete.

## Current Command

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --out /tmp/fpga_devmind/p1a_coarse_sync_l6
```

Second smoke sample:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_fine_cfo \
  --stage L6_resource_opt \
  --out /tmp/fpga_devmind/p1a_fine_cfo_l6
```

Query generated artifacts:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-query \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6 \
  --question "L6 实现了什么流程"
```

Check whether generated artifacts are stale:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-freshness \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6
```

Run P1a smoke validation:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-smoke \
  --out-root /tmp/fpga_devmind/p1a_smoke
```

Run P1a+ Agent dry-run:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6
```

Validate a local model output fixture without calling a provider:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --model-result /tmp/fpga_devmind/model_result_fixture.json
```

Supported deterministic query topics:

```text
- stage flow
- fixed-point / Q format
- stream interface
- pipeline timing
- resource estimates
- specific claim ids such as C001
- specific evidence ids from trace_index.json
- uncertainty / known limitations
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Direction Check

This implementation intentionally starts with deterministic evidence and schema plumbing before adding an LLM. This follows [Direction Guardrails](direction-guardrails.md): the first objective is a grounded Agent runtime shell, not a polished report generator.
