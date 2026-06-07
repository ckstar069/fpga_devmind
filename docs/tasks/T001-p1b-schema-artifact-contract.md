# T001: P1b Schema And Artifact Contract

## Objective

Define the first P1b concept trace artifact contract without implementing broad extraction logic.

The contract should make `concept_trace_graph.json` and `concept_trace_index.json` precise enough for later tasks to implement.

## Allowed Files

```text
docs/implementation-plan-p1b.md
docs/phase1-scope.md
docs/phase1a-schema.md
docs/semantic-graph-model.md
src/fpga_devmind/schema.py
tests/test_p1b.py
```

If adding code, prefer a new small module:

```text
src/fpga_devmind/p1b_schema.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not edit target projects.
Do not run Vivado, synthesis, implementation or bitstream.

## Expected Output

Define structured objects or documented dict schema for:

```text
ConceptTraceGraph
ConceptTraceIndex
ConceptTraceNode
ConceptTraceEdge
MappingClaim
RTLEvidenceView
```

## Acceptance

```text
- schema_version values are defined.
- mapping confidence values match P1b plan.
- evidence ids are required for mapping claims.
- unknown concept result has an explicit representation.
- docs and code schema names match.
```

## Tests

Add small tests that validate serialization shape if code is added.

Verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

## Review Notes

Watch for overlarge schema design. P1b is a narrow single-concept trace slice, not a complete graph database.
