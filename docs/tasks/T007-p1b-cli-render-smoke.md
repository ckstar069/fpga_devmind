# T007: P1b CLI, Rendering And Smoke

## Objective

Expose the P1b concept trace workflow through CLI and write final artifacts under a safe output directory.

This task depends on T006. It must use the real P1b grounding checker and must not emit a stub `grounding_report.json`.

## Allowed Files

```text
src/fpga_devmind/cli.py
src/fpga_devmind/safety.py
src/fpga_devmind/p1b*.py
tests/test_p1b.py
docs/implementation-status.md
docs/p1b-quickstart.md
docs/README.md
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation, bitstream or external provider APIs.

## CLI Shape

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_devmind/p1b_coarse_sync_peak_idx
```

## Required Artifacts

```text
concept_trace_graph.json
concept_trace_index.json
concept_trace.md
concept_trace.mmd
grounding_report.json
run_metadata.json
```

Intermediate function output may remain in memory, but final CLI artifacts must match this list.

## Acceptance

```text
- command writes all required artifacts.
- output paths are guarded by ensure_safe_output_dir().
- unsafe output path containing fpga_project_* raises ValueError.
- command returns nonzero for blocking grounding diagnostics.
- grounding_report.json comes from T006 checker.
- concept_trace.md and concept_trace.mmd are rendered from structured artifacts.
- existing P1a / P1a+ commands still work.
```

## Tests

Add tests for:

```text
- successful primary sample run if target project exists
- unknown concept run
- unsafe output path
- artifact file existence and schema_version
- real-project smoke tests skip cleanly when target projects are absent
```

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli p1b-trace-concept \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --concept peak_idx \
  --out /tmp/fpga_devmind/p1b_coarse_sync_peak_idx
```

## Review Notes

Rendering is secondary. The structured graph and trace artifacts are the source of truth.
