# T004: P1b RTL Evidence Collector

## Objective

Collect RTL-side evidence for candidate modules, signals and state elements related to a selected concept.

This task should not make final L6-to-RTL mapping claims.

## Allowed Files

```text
src/fpga_devmind/p1b_collectors.py
src/fpga_devmind/tools.py
tests/test_p1b.py
```

New module allowed:

```text
src/fpga_devmind/p1b_rtl.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected Behavior

For `.v`, `.sv` or related RTL files, extract bounded evidence for:

```text
- module declarations
- signal declarations
- always blocks or assign statements containing concept-like names
- FSM state names when clearly present
- line ranges and excerpt summaries
```

## Evidence Rules

RTL evidence establishes that an RTL object exists and where it appears. It does not by itself prove that it maps to an L5/L6 concept.

## Output Contract

Function-level output should be a structured dict or dataclass equivalent:

```text
{
  "schema_version": "p1b-rtl-evidence-0.1",
  "concept_name": str,
  "rtl_candidate_files": [str],
  "rtl_views": [dict],
  "evidence_items": [dict],
  "collection_diagnostics": [dict]
}
```

Each RTL view should include:

```text
rtl_object_id
object_type: module | signal | state | assignment | always_block
name
file_path
evidence_ids
confidence
```

## Acceptance

```text
- collector handles missing RTL directory gracefully.
- collector finds candidate RTL symbols by exact and normalized name matching.
- evidence item line ranges are bounded.
- no target project files are modified.
```

## Tests

Add synthetic temp RTL fixtures in tests. Do not edit target projects. Real project smoke tests must skip cleanly when target projects are absent.

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Review Notes

Do not implement a full Verilog parser unless there is a clear dependency already available. A conservative line/regex collector is acceptable if claims remain weak or inferred.
