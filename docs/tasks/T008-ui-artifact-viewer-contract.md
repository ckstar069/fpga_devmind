# T008: UI Artifact Viewer Contract

## Objective

Define the first GUI artifact loading contract before building the interface.

The UI must be an artifact viewer, not a new source of semantic truth.

## Allowed Files

```text
docs/ui-prototype-plan.md
docs/README.md
docs/implementation-status.md
```

Optional code contract file:

```text
src/fpga_devmind/ui_contract.py
```

Tests:

```text
tests/test_ui.py
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation or bitstream.

## Expected Contract

Define supported artifact bundles:

```text
p1a_artifacts
p1a_plus_artifacts
p1b_concept_trace_artifacts
```

Each bundle should describe:

```text
- required files
- optional files
- display sections
- missing artifact diagnostics
- graph source file
- trace index source file
- markdown preview source file
```

## Acceptance

```text
- missing files are represented as structured diagnostics.
- UI contract does not read target project source directly.
- UI contract names P1a, P1a+ and P1b artifact files consistently with existing docs.
- tests use synthetic temp artifact directories.
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```
