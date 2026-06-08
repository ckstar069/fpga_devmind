# Desktop Agent Shell Plan

## Overview

The Desktop Agent Shell is the human-facing interactive layer of the
`fpga_devmind` FPGA Develop-Understand-Verify Agent.  It is a **native desktop
application** (not Web GUI) that reads grounded artifacts produced by the CLI
pipeline and renders them in interactive views.

This document is the **planning-level contract** that bridges the P1b CLI
pipeline and the T009/T010 desktop implementation.  It does not contain
implementation code.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           fpga_devmind Ecosystem                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐      generates      ┌──────────────────────────────┐    │
│   │  CLI Pipeline │  ────────────────→ │  /tmp/fpga_devmind/...       │    │
│   │  (P1a / P1b)  │      artifacts     │  • concept_trace_graph.json  │    │
│   │               │                    │  • concept_trace_index.json  │    │
│   │  run_p1b_     │                    │  • grounding_report.json     │    │
│   │  trace_concept│                    │  • run_metadata.json         │    │
│   │               │                    │  • concept_trace.md          │    │
│   └──────────────┘                    │  • concept_trace.mmd         │    │
│          │                            └──────────────────────────────┘    │
│          │                                        ↑                        │
│          │                            reads (read-only)                     │
│          │                                        │                        │
│          │                            ┌───────────┴──────────────┐         │
│          │                            │   Desktop Agent Shell    │         │
│          │                            │   (T009 / T010)          │         │
│          │                            │                          │         │
│          │                            │  ┌──────────────────┐   │         │
│          │                            │  │ Artifact Loader  │   │         │
│          └────────────────────────────│──│  • validation     │   │         │
│            invokes CLI tools          │  │  • indexing       │   │         │
│                                       │  └──────────────────┘   │         │
│                                       │  ┌──────────────────┐   │         │
│                                       │  │ View Renderer    │   │         │
│                                       │  │  • graph view    │   │         │
│                                       │  │  • evidence      │   │         │
│                                       │  │  • diagnostics   │   │         │
│                                       │  │  • markdown      │   │         │
│                                       │  └──────────────────┘   │         │
│                                       │  ┌──────────────────┐   │         │
│                                       │  │ Agent Panel      │   │         │
│                                       │  │  (T011+)         │   │         │
│                                       │  └──────────────────┘   │         │
│                                       └─────────────────────────┘         │
│                                                                             │
│   Key Principle: The Desktop Shell is a VIEWER and INTERACTION SHELL.       │
│   It does not generate semantic truth.  All claims, evidence, mappings,     │
│   and diagnostics originate from the CLI pipeline.                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Breakdown

| Phase | Scope | Status |
|---|---|---|
| T001–T007 | CLI pipeline: schema, collectors, mapping, grounding, render | ✅ Complete |
| **T008** | **Artifact viewer contract** (this document) | 🔄 In Progress |
| T009 | Desktop app prototype: minimum viable shell | ⏳ Planned |
| T010 | P1b concept trace view: rich interactive graph | ⏳ Planned |
| T011+ | Agent interaction panel: query, tool call, response | ⏳ Future |

---

## Platform Strategy

```text
Primary:   macOS  (current development platform)
Secondary: Linux  (Ubuntu / Debian / Fedora)
Tertiary:  Windows  (after macOS/Linux are stable)
```

不做 Web GUI：不提供 browser-accessible URL，不启动 Web server，不做 Web app。
Electron 默认排除。

The desktop app is a native application.  Preferred approach: a toolkit that
renders its own widgets (PySide6/Qt).  Alternative: a lightweight WebView
within a native wrapper (Tauri) — but only as a **local desktop rendering
layer**, never as a Web GUI.

---

## Technology Stack Candidates

### Candidate A: PySide6 (Python-native)

```text
Pros:
  - Full Python ecosystem; reuse fpga_devmind dataclasses directly.
  - Mature, stable, extensive widget set.
  - No Rust build chain required.
  - LGPL license (PySide6) vs GPL (PyQt); commercial-friendly.

Cons:
  - Larger binary size (~50-100MB with PyInstaller).
  - UI defaults are less modern than web-based alternatives.
  - Packaging complexity on macOS (notarization, signing).
```

### Candidate B: Tauri (Rust + WebView) — Local rendering layer only

```text
Pros:
  - Very small binary (~5-15MB).
  - Secure sandbox model.
  - Native feel on macOS/Linux.
  - Modern UI via standard web technologies rendered inside a local WebView.

Cons:
  - Rust build complexity.
  - WebView is browser-based rendering (security surface), but it is
    **only a local desktop rendering layer** — it does not expose a network
    service, does not provide a browser-accessible URL, and is not a Web GUI.
  - Interfacing with Python dataclasses requires bridge (HTTP/IPC).
```

### Decision

T009 should **prototype one candidate** with the minimum viable views
(Run Summary + JSON tree browser + Markdown preview).  Measure:
- Build time and binary size.
- Startup latency.
- Rendering quality for Markdown and Mermaid.
- Cross-platform packaging effort.

Do not decide now.  The contract (T008) is stack-agnostic.

---

## Artifact Loading Contract

See `docs/tasks/T008-desktop-artifact-viewer-contract.md` for the full
contract.  Summary:

```text
1. The shell opens an artifact directory (user-selected or default /tmp path).
2. Detect bundle type:
     P1b: concept_trace_graph.json present
     P1a: project_graph.json present (fallback)
3. Load required JSON files into memory.
4. Validate schema_version fields; warn on mismatch.
5. Build in-memory index for cross-reference resolution.
6. Handle missing files gracefully (structured diagnostics, not crashes).
7. Never write to the artifact directory.
```

---

## View Inventory

| View | T009 | T010 | Description |
|---|---|---|---|
| Run Summary | ✅ | ✅ | Metadata panel: concept, status, counts |
| JSON Tree Browser | ✅ | ⏳ | Collapsible raw JSON explorer |
| Node List | ⏳ | ✅ | Interactive node table with filtering |
| Edge List | ⏳ | ✅ | Interactive edge table with navigation |
| Evidence Browser | ⏳ | ✅ | Filterable evidence table |
| Mapping Claim Detail | ⏳ | ✅ | Expandable claim cards |
| Grounding Diagnostics | ⏳ | ✅ | Severity-colored diagnostic list |
| Markdown Preview | ✅ | ✅ | Read-only rendered Markdown |
| Mermaid Preview | ✅ | ✅ | Mermaid source + copy button |
| Agent Interaction | ⏳ | ⏳ | Query input + response panel (T011+) |

---

## Constraints

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ HARD CONSTRAINTS                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│ ✗ No Web GUI (no browser-accessible URL, no Web server, no Web app;        │
│   Electron excluded by default)                                            │
│ ✗ No Vivado / synthesis / implementation / bitstream                       │
│ ✗ No modification of fpga_project_* target projects                        │
│ ✗ No API key loading or external LLM calls from the desktop shell          │
│ ✗ No artifact modification (read-only viewer)                              │
│ ✗ No PASS/HOLD audit gate                                                  │
│ ✗ No source code editing                                                   │
├────────────────────────────────────────────────────────────────────────────┤
│ SOFT CONSTRAINTS                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│ ✓ Default artifact root: /tmp or /private/tmp                              │
│ ✓ macOS/Linux first; Windows secondary                                     │
│ ✓ Unknown confidence is normal, not an error                               │
│ ✓ Grounding diagnostics are warnings, not test failures                    │
│ ✓ All semantic truth originates from CLI pipeline                          │
│ ✓ Dangling references are grayed out, not hidden                           │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Desktop toolkit choice locks us into heavy dependency | Medium | High | T009 prototype with one toolkit; evaluate before committing. |
| Mermaid rendering requires WebView or heavy JS runtime | Medium | Medium | Fallback to source display + copy button if rendering is too complex. |
| Cross-platform packaging (macOS notarization) is slow | High | Medium | Start with development-mode execution; package only after T010. |
| Desktop shell drifts from CLI schema changes | Medium | High | Contract (T008) defines schema fields explicitly; update contract first. |
| User expects the desktop to edit claims or run synthesis | Low | High | Clear constraints in UI (read-only badges, disabled edit buttons). |

---

## Next Steps

1. **T008 Completion:** Review this contract; align with team on constraints
   and technology direction.
2. **T009 Kickoff:** Choose one toolkit candidate; build minimum viable
   prototype with Run Summary + JSON Tree Browser + Markdown Preview.
3. **T010 Kickoff:** Build rich concept trace views on top of T009 shell.
4. **T011+ Future:** Agent interaction panel; query input, response rendering,
   tool call display.

---

## Related Documents

- `docs/tasks/T008-desktop-artifact-viewer-contract.md` — Full artifact
  viewer contract with field-level detail.
- `docs/implementation-status.md` — Overall project status.
- `docs/p1a-v0.1-quickstart.md` — CLI quickstart including P1b commands.
- `docs/tasks/T009-desktop-app-prototype.md` — T009 task specification
  (to be written).
- `docs/tasks/T010-desktop-p1b-concept-trace-view.md` — T010 task
  specification (to be written).
