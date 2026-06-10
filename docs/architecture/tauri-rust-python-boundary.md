# Tauri / Rust / Python Boundary Decision

Status: active direction decision
Date: 2026-06-10
Applies to: `fpga_devmind`

## 1. Why this document exists

The project started as a fast Python prototype for FPGA evidence extraction, deterministic graph generation, P1a/P1b CLI workflows, and early desktop experiments. Later the product direction shifted to a Tauri desktop application with a Rust backend and a React/TypeScript UI.

Both histories are visible in the repository today:

- Python owns most legacy analysis and artifact generation logic.
- Earlier desktop shell work used PySide6.
- Newer product work lives under `apps/fpga-devmind-tauri`.
- Rust is already used for the Tauri backend, artifact loading, and provider runtime boundary.
- TypeScript/React is already used for the current product UI.

This is not a failure by itself, but the boundary must be explicit. Future agents must not keep expanding PySide6 or Python UI paths when the product direction is Tauri + React + Rust.

## 2. Decision summary

`fpga_devmind` will use:

```text
Tauri + React/TypeScript
  = primary product UI and user interaction layer

Rust backend
  = desktop backend, local file/runtime boundary, provider runtime, safety-sensitive execution, and future app-owned local services

Python
  = legacy/prototype analysis engine for P1a/P1b/P1c-style FPGA evidence extraction and artifact generation, retained until the semantic workflows are stable enough to justify selective migration

PySide6
  = historical prototype shell only; no new product work should be added there unless explicitly approved for maintenance
```

## 3. Current allowed responsibilities

### 3.1 Tauri + React/TypeScript

Use for:

- primary desktop app UI;
- graph and evidence views;
- Agent Q&A panels;
- project/bundle selection UI;
- request/package preview UI;
- user-facing state and interaction flows;
- visualization planning and rendering surfaces;
- calling Tauri commands through the app boundary.

Do not use for:

- direct external provider calls from the frontend;
- long-running FPGA analysis logic when it belongs in the backend or existing analysis engine;
- persistence of sensitive runtime credentials;
- duplicating Python analysis algorithms just to display results.

### 3.2 Rust backend

Use for:

- Tauri command handlers;
- local file and artifact loading;
- app-owned runtime safety gates;
- provider runtime boundary;
- request/response preview safety handling;
- future process orchestration for calling the Python analysis engine;
- future local service boundary if needed.

Rust should own safety-sensitive operations because it is the app backend boundary.

Do not use Rust as an immediate full rewrite target for all Python analysis modules. Rewriting should be selective and justified by product need, performance, security, or maintainability.

### 3.3 Python analysis engine

Use for now for:

- P1a deterministic stage understanding;
- P1b concept trace pipeline;
- source/evidence collectors;
- schema/artifact writers;
- grounding diagnostics;
- existing CLI workflows;
- legacy tests around analysis behavior.

Python is currently an analysis engine, not the future product UI.

The Tauri app may consume Python-generated artifacts or invoke Python CLI workflows through a controlled backend boundary. This should be treated as integration with a legacy/prototype engine, not as a reason to continue building product UI in Python.

### 3.4 PySide6 legacy shell

PySide6 shell work is historical prototype work. It may remain for reference or regression checks, but:

- do not add new product features to PySide6;
- do not treat PySide6 as the main desktop route;
- do not create new PySide6 pages when a Tauri equivalent is needed;
- only modify it for compatibility or cleanup if explicitly requested.

## 4. Migration policy

Do not attempt a big-bang Python-to-Rust rewrite.

Preferred migration strategy:

1. Keep Python analysis stable while dogfooding real FPGA examples.
2. Use Tauri/Rust to orchestrate artifact loading and user interaction.
3. Add explicit integration contracts between Rust/Tauri and Python-generated artifacts.
4. Migrate small modules only when there is a clear reason:
   - safety boundary;
   - runtime reliability;
   - performance bottleneck;
   - packaging complexity;
   - duplicated logic between Python and Rust/TS;
   - user-facing product need.
5. Preserve existing tests while migrating.
6. Do not rewrite analysis code just for language purity.

## 5. Future integration model

The preferred near-term model is:

```text
Tauri UI
  -> Rust backend command
  -> load existing artifact bundle
  -> optionally run controlled Python analysis CLI
  -> read structured artifacts
  -> display graph/evidence/semantic explanations in React
```

The medium-term model may become:

```text
Tauri UI
  -> Rust backend orchestration
  -> Python analysis engine for evidence/semantic artifacts
  -> LLM semantic layer through gated backend provider runtime
  -> structured claims / evidence / uncertainty
  -> diagrams and explanations in React
```

A later migration may move selected analysis modules to Rust, but only after P1a/P1b/P1c semantic workflows are product-stable.

## 6. What this changes for future tasks

Future tasks must follow these rules:

- New product UI goes to `apps/fpga-devmind-tauri`.
- New backend runtime/safety/provider work goes to Rust under the Tauri app.
- New FPGA analysis algorithm work may remain in Python until a migration decision says otherwise.
- New PySide6 feature work is disallowed by default.
- New documents must describe whether a change touches product UI, Rust backend, Python analysis engine, or legacy shell.
- Web GPT reviews should flag any new task that silently adds product UI in Python or expands PySide6.

## 7. What this does not decide

This document does not decide that all Python must be removed.

This document does not decide that all analysis must be rewritten in Rust.

This document does not decide the final packaging mechanism for Python analysis inside the Tauri app.

This document only fixes the architectural boundary so future work does not drift.

## 8. Relationship to current direction analysis

This boundary complements `docs/current-position-and-drift.md`.

The project's main product risk remains sequencing drift: infrastructure and provider safety layers are ahead of the core semantic understanding loop. This document adds a second drift guard: the product UI and runtime path must converge on Tauri + React + Rust while preserving the existing Python analysis engine until a deliberate migration plan exists.

## 9. Required reading

Before proposing architecture or implementation work, read:

- `PROJECT_CONTEXT.md`;
- `docs/current-position-and-drift.md`;
- `docs/documentation-map.md`;
- this document;
- `docs/implementation-status.md`.
