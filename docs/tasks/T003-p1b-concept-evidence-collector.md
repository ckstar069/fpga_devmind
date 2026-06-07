# T003: P1b Concept Evidence Collector

## Objective

Collect L5/L6-side evidence for a selected concept such as `peak_idx`, `metric` or `lts_start`.

This task should not inspect RTL mapping yet.

## Allowed Files

```text
src/fpga_devmind/tools.py
src/fpga_devmind/p1b_collectors.py
tests/test_p1b.py
```

New module allowed:

```text
src/fpga_devmind/p1b_concept.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected Behavior

Input:

```text
project_root
concept_name
candidate_files
```

Output evidence items:

```text
- concept name occurrences
- assignments or references in Python model files
- function/class context
- line ranges
- excerpt summaries
- evidence_strength
```

## Output Contract

Function-level output should be a structured dict or dataclass equivalent:

```text
{
  "schema_version": "p1b-concept-evidence-0.1",
  "concept_name": str,
  "stage_side": "l5_l6",
  "evidence_items": [dict],
  "candidate_subjects": [dict],
  "uncertainty_notes": [dict],
  "collection_diagnostics": [dict]
}
```

Each evidence item must include:

```text
evidence_id
source_type
file_path
start_line
end_line
symbol
excerpt_summary
evidence_strength
```

## Evidence Rules

Naming occurrence alone should usually be `weak`. A concept should become `supported` only when context indicates role, calculation, state update or interface behavior.

## Acceptance

```text
- peak_idx or metric yields at least one L5/L6 evidence item in coarse_sync_glm when source exists.
- unknown concept yields an explicit unknown result and uncertainty note.
- evidence ids are stable for the same source snapshot.
- source snippets are bounded and do not include unrelated large file dumps.
```

## Tests

Add tests for:

```text
- known concept extraction from synthetic fixture
- unknown concept handling
- evidence id stability
- real project smoke extraction, skipped cleanly when target project is absent
```

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Review Notes

Avoid claiming L5-to-L6 equivalence unless both stages contain evidence and a bridge is recorded.
