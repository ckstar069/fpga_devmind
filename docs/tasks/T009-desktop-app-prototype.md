# T009: Desktop App Prototype

## Objective

Build the first read-only desktop graphical interface for browsing generated fpga_devmind artifacts.

This task should start only after T008 defines the artifact loading contract. It must not implement a Web GUI.

Priority:

```text
1. macOS
2. Linux
3. Windows
```

## Allowed Files

```text
desktop/**
ui/**
src/fpga_devmind/ui*.py
tests/test_ui.py
docs/ui-prototype-plan.md
docs/implementation-status.md
```

Use whichever desktop folder convention is chosen, but keep it documented.

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation, bitstream or external provider APIs.

## First Screen

The first screen should show the actual desktop artifact browsing experience:

```text
- workspace / artifact directory picker
- load status and freshness status
- graph visualization pane
- claim/evidence list
- selected detail pane
- grounding diagnostics
- uncertainty notes
- Agent trace / raw JSON tab
```

No marketing landing page.

## Visual Requirements

```text
- render graph from artifact data
- make inferred / unknown / conflicted visually distinct
- evidence ids must be visible near claims
- selected evidence shows file path and line range
- missing artifact state is explicit
- dense, utilitarian layout suitable for engineering review
```

## Acceptance

```text
- macOS desktop app can open a synthetic artifact directory.
- Linux dev-mode path is documented.
- Windows is documented as secondary and may be deferred.
- desktop app can open synthetic P1a artifact fixture.
- desktop app can open synthetic P1a+ artifact fixture.
- graph renders nonblank.
- selecting a claim shows evidence refs.
- selecting evidence shows source location metadata.
- desktop app remains read-only.
```

## Verification

Use automated screenshot checks if a desktop/frontend stack is introduced.

Required:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

If a desktop toolchain is used, document the dev command and tested OS.
