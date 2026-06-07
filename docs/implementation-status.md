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
- Provider-free P1a+ Agent dry-run that writes `agent_trace.json`, `prompt_context.json`, `provider_call.json`, `model_result_normalized.json`, `claim_proposals.json`, `graph_write_proposal.json`, `grounding_report.json` and `answer.md`.
- LLM provider contract helpers that build redacted prompt context and validate model `SemanticReasoningResult` before grounding.
- Noop and fixture semantic provider adapters for testing provider boundaries without external API calls.

Not implemented yet:

- LLM provider integration.
- Prompted semantic claim generation.
- Multi-turn ReAct loop.
- Model-generated CandidateClaims.
- Provider-backed model calls.
- Rich AST def-use / dataflow analysis.
- Proven producer/consumer dataflow extraction.
- High-quality generic flow ordering for every possible L6 architecture.
- Full fixed-point spec extraction.
- Full interface / pipeline / state event extraction.
- Full symbolic resource total evaluation.
- P1b L6-to-RTL mapping.
- P1c verification coverage.
- UI or interactive memory.

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
