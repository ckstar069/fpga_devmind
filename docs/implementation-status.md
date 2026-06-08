# Implementation Status

## Current State

P1a has a minimal deterministic implementation shell and is currently a V0.1 candidate.

V0.1 candidate means:

```text
- It is usable for read-only L6_resource_opt understanding smoke runs.
- It produces grounded artifacts that later Agent layers can consume.
- It is not yet a full FPGA Agent, LLM/ReAct reasoner, audit tool, or RTL mapper.
```

Implemented:

- CLI entry point: `fpga-devmind p1a-understand-stage`
- CLI entry point: `fpga-devmind p1a-query`
- CLI entry point: `fpga-devmind p1a-freshness`
- CLI entry point: `fpga-devmind p1a-smoke`
- CLI entry point: `fpga-devmind p1a-agent-understand-stage`
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
- Desktop GUI / Agent Shell prototype（桌面端软件，非 Web）。
- Interactive memory.

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
- T009: Desktop app prototype — 最小可运行桌面软件原型，支持 artifact 目录选择、JSON 树浏览、Markdown 渲染、Mermaid 图表展示。macOS/Linux 优先，Windows 其次。
- T010: P1b concept trace view — 在桌面 GUI 中渲染 concept trace graph（节点列表、边列表、claim 详情、grounding diagnostic 高亮）。

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
