# T011: UI Desktop App Packaging

## Objective

Package the fpga_devmind GUI as a desktop application while reusing the Web GUI artifact contract and view model.

Priority:

```text
1. macOS
2. Linux
3. Windows
```

## Dependencies

This task depends on:

```text
T008 UI artifact viewer contract
T009 UI local web prototype
T010 UI P1b concept trace view, if P1b-specific desktop view is required
```

## Allowed Files

```text
ui/**
web/**
desktop/**
src/fpga_devmind/ui*.py
tests/test_ui.py
docs/ui-prototype-plan.md
docs/implementation-status.md
```

## Forbidden Files

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
```

Do not modify target projects. Do not run Vivado, synthesis, implementation, bitstream or external provider APIs.

## Preferred Approach

Use a desktop shell around the same UI:

```text
Web GUI code
  -> shared artifact loader / view model
  -> desktop shell
```

Candidate shells:

```text
Tauri
  Preferred if acceptable, especially for macOS / Linux.

Electron
  Acceptable fallback if Tauri integration cost is too high.
```

Do not rewrite the UI as a separate desktop-only app unless a review explicitly accepts the maintenance cost.

## Required Desktop Features

```text
- choose artifact directory from filesystem
- default browse location: /tmp/fpga_devmind or /private/tmp/fpga_devmind
- render the same graph view as Web GUI
- show claims / evidence / diagnostics / uncertainty
- read-only behavior
- no target project mutation
```

## Acceptance

```text
- macOS desktop app can open a synthetic artifact directory.
- Linux desktop app path is documented, even if packaging is verified later.
- Windows is documented as secondary and may be deferred.
- desktop app uses the same artifact contract as Web GUI.
- missing artifact states match Web GUI behavior.
- no API keys or environment dumps appear in app logs.
```

## Verification

At minimum:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```

If a desktop toolchain is added, document:

```text
- install prerequisites
- dev command
- package command
- tested OS
```
