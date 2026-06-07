# T002: P1b Read-Only Source Collector

## Objective

Implement a read-only collector that discovers candidate source files for P1b concept tracing.

It should locate likely L5, L6 and RTL files, but must not infer mappings yet.

## Allowed Files

```text
src/fpga_devmind/tools.py
src/fpga_devmind/safety.py
tests/test_p1b.py
```

Prefer adding:

```text
src/fpga_devmind/p1b_collectors.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected Behavior

Collector input:

```text
project_root
concept_name
```

Collector output:

```text
- project_id
- l5_candidate_files
- l6_candidate_files
- rtl_candidate_files
- test_candidate_files
- missing_sections
- collection_diagnostics
```

## Output Contract

Function-level output should be a structured dict or dataclass equivalent:

```text
{
  "schema_version": "p1b-source-collection-0.1",
  "project_id": str,
  "project_root": str,
  "concept_name": str,
  "l5_candidate_files": [str],
  "l6_candidate_files": [str],
  "rtl_candidate_files": [str],
  "test_candidate_files": [str],
  "missing_sections": [str],
  "collection_diagnostics": [dict]
}
```

## Evidence Rules

File discovery is not a mapping claim. It only identifies where later evidence may be extracted.

## Acceptance

```text
- collector returns deterministic paths for coarse_sync_glm.
- collector returns deterministic paths for fine_cfo when present.
- missing directories are represented as diagnostics, not exceptions unless project root is invalid.
- no generated output is written into target projects.
```

## Tests

Add tests for:

```text
- synthetic project file discovery
- coarse_sync_glm file discovery, skipped cleanly when target project is absent
- nonexistent temp project with missing sections
- safety boundary for output paths if output is added
```

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Review Notes

Do not add ad hoc broad static analysis. Keep this as evidence discovery.
