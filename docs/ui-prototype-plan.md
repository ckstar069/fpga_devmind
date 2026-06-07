# UI Prototype Plan

`fpga_devmind` should have a graphical interface. The UI is not the semantic source of truth; it is an artifact viewer and interaction surface over ProjectGraph / TraceIndex / ConceptTraceGraph / EvidenceGraph outputs.

## Positioning

The first GUI should support both:

```text
- local Web GUI
- desktop app, with macOS / Linux first and Windows second
```

Both surfaces should share the same artifact loading and view-model contract. The desktop app must not fork semantic logic from the Web GUI.

The first implementation should start with a local Web GUI:

```text
local browser
  -> fpga_devmind UI server or static app
  -> reads generated artifacts under /tmp/fpga_devmind
  -> renders graph / evidence / uncertainty / markdown
```

Then wrap or reuse the same UI for desktop:

```text
desktop app
  -> same artifact loader / view model
  -> same graph / evidence / diagnostics views
  -> local filesystem artifact selection
```

It should not call Vivado, mutate target projects or invent conclusions. All displayed facts must come from structured artifacts and evidence ids.

## Why UI After P1b

P1b produces the first useful user-facing trace artifact:

```text
concept_trace_graph.json
concept_trace_index.json
concept_trace.md
concept_trace.mmd
grounding_report.json
```

These are the right inputs for a GUI. Building the UI before P1b would force the interface to display incomplete or unreliable mapping data.

## First Usable UI

The first GUI should support:

```text
- choose an artifact directory
- show project / stage / concept metadata
- render Mermaid graph
- show claims by confidence
- click claim -> show evidence refs
- click evidence -> show file path and line range
- show grounding diagnostics
- show uncertainty notes
- show raw JSON for debugging
```

The UI should make uncertainty visible. It must not hide inferred / unknown / conflicted status behind polished visuals.

## Non-Goals

The first UI must not implement:

```text
- editing target projects
- running Vivado
- running synthesis / implementation / bitstream
- real provider API calls
- API key configuration
- PASS/HOLD dashboard
- audit finding workflow
- graph editing as source of truth
```

## Suggested Technology

Prefer a small local web app first. The initial implementation can be:

```text
Python stdlib static server + static HTML/JS
```

or, if a frontend stack is intentionally introduced:

```text
Vite + React + TypeScript
```

For desktop, prefer a wrapper around the same Web UI rather than a separate rewritten interface. Candidate approaches:

```text
Tauri
  Preferred for macOS / Linux first if the team is comfortable adding a Rust-based desktop shell.

Electron
  Acceptable if implementation speed and ecosystem matter more than app size.

Native Python desktop shell
  Acceptable only for a minimal artifact browser, but less attractive for rich graph UI.
```

Do not introduce a heavy backend unless the UI needs dynamic file browsing, artifact loading or later Agent interaction.

## Information Architecture

First screen:

```text
Top bar
  artifact directory selector / loaded artifact status

Left pane
  graph sections
  claims
  evidence ids
  uncertainty notes

Center pane
  Mermaid / graph visualization

Right pane
  selected claim / evidence / diagnostic detail

Bottom or secondary tab
  raw JSON / generated markdown preview
```

## Artifact Contract

The UI should support these artifact groups:

```text
P1a:
  project_graph.json
  trace_index.json
  summary.md
  flow.mmd
  trace.md
  grounding diagnostics inside project_graph.json

P1a+:
  project_graph_proposed.json
  trace_index_proposed.json
  graph_write_report.json
  grounding_report.json
  answer.md

P1b:
  concept_trace_graph.json
  concept_trace_index.json
  concept_trace.md
  concept_trace.mmd
  grounding_report.json
```

If an artifact is missing, the UI should show a clear missing-artifact state instead of failing silently.

## Safety Rules

The UI may read:

```text
/tmp/fpga_devmind/**
/private/tmp/fpga_devmind/**
explicit user-selected artifact directories
```

Desktop app file pickers should default to:

```text
/tmp/fpga_devmind
/private/tmp/fpga_devmind
```

The UI must not write into:

```text
/Users/ckstar/Repo/znxt_ofdm/fpga_project_*
any path component beginning with fpga_project_
```

The first UI should be read-only.

## Acceptance

The UI prototype is acceptable when:

```text
- it can open a generated P1a artifact directory
- it can open a generated P1a+ artifact directory
- after P1b exists, it can open a P1b concept trace directory
- the Web GUI and desktop app use the same artifact contract
- Mermaid graph renders nonblank
- selecting a claim shows evidence ids
- selecting evidence shows file path and line range
- grounding diagnostics are visible
- inferred / unknown / conflicted states are visually distinct
- missing artifact states are handled
- no target project files are modified
```

## Review Gate

Before treating the UI as usable, run a UI review focused on:

```text
- whether displayed facts are artifact-grounded
- whether uncertainty is visible
- whether the UI encourages unsupported conclusions
- whether it remains read-only
- whether text and graph layout are usable on desktop
- whether Web and desktop behavior stay consistent
```
