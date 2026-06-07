# T009: UI Local Web Prototype

## Objective

Build the first read-only graphical interface for browsing generated fpga_devmind artifacts.

This task should start only after T008 defines the artifact loading contract.

This task builds the Web GUI first. Desktop packaging is covered by T011.

## Allowed Files

```text
src/fpga_devmind/ui*.py
ui/**
web/**
tests/test_ui.py
docs/ui-prototype-plan.md
docs/implementation-status.md
```

Use whichever UI folder convention is chosen, but keep it documented.

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation, bitstream or external provider APIs.

## First Screen

The first screen should show the actual artifact browsing experience:

```text
- artifact directory input
- load status
- graph visualization pane
- claim/evidence list
- selected detail pane
- grounding diagnostics
- uncertainty notes
```

No marketing landing page.

## Visual Requirements

```text
- render Mermaid or equivalent graph from artifact data
- make inferred / unknown / conflicted visually distinct
- evidence ids must be visible near claims
- selected evidence shows file path and line range
- missing artifact state is explicit
- dense, utilitarian layout suitable for engineering review
```

## Acceptance

```text
- UI can open synthetic P1a artifact fixture.
- UI can open synthetic P1a+ artifact fixture.
- UI can render a nonblank graph.
- clicking/selecting a claim shows evidence refs.
- clicking/selecting evidence shows source location metadata.
- UI remains read-only.
- UI code exposes or documents a reusable artifact view model for the desktop app.
```

## Verification

Use automated browser/screenshot checks if a frontend stack is introduced.

Required:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

If a dev server is used, document the local URL.
