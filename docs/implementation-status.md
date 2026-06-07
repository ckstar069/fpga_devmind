# Implementation Status

## Current State

P1a has a minimal deterministic implementation shell.

Implemented:

- CLI entry point: `fpga-devmind p1a-understand-stage`
- CLI entry point: `fpga-devmind p1a-query`
- CLI entry point: `fpga-devmind p1a-freshness`
- CLI entry point: `fpga-devmind p1a-smoke`
- P1a dataclass schema objects.
- Read-only project tree scan.
- Read-only L6 Python symbol and evidence extraction.
- Read-only config parameter extraction.
- Deterministic P1a claim generation for L6 resource optimized stages.
- Generic L6 concept inference when the project does not match the coarse-sync S0-S3 pattern.
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

Not implemented yet:

- LLM provider integration.
- Prompted semantic claim generation.
- Multi-turn ReAct loop.
- Rich AST def-use / dataflow analysis.
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

Supported deterministic query topics:

```text
- stage flow
- fixed-point / Q format
- stream interface
- pipeline timing
- resource estimates
- specific claim ids such as C001
- specific evidence ids from trace_index.json
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Direction Check

This implementation intentionally starts with deterministic evidence and schema plumbing before adding an LLM. This follows [Direction Guardrails](direction-guardrails.md): the first objective is a grounded Agent runtime shell, not a polished report generator.
