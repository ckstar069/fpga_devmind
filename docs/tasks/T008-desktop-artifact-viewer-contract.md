# T008: Desktop Artifact Viewer Contract

## Objective

Define the contract between the Desktop Agent Shell and the P1a/P1b artifact
bundles.  This is a **contract document**, not GUI code.  T008 establishes
what the desktop viewer must read, validate, display, and how it must behave
when artifact fields are missing, dangling, or marked as unknown.

T008 does **not** implement the viewer.  T009/T010 build the desktop prototype
on top of this contract.

---

## 1. 桌面端定位 (Desktop Positioning)

### What the Desktop Agent Shell Is

- A **Desktop GUI / Agent Shell** running natively on macOS and Linux
  (Windows secondary).
- An **interactive runtime shell** for the FPGA Develop-Understand-Verify
  Agent: read artifact → render → accept user instruction → invoke follow-up
  tools.
- A **viewer and interaction surface**, not a source of semantic truth.  All
  claims, evidence, and mappings originate from the CLI pipeline (P1a/P1b);
  the desktop never invents or modifies them.

### What It Is Not

- **Not a Web GUI.**  No browser, no Electron, no web server.
- **Not a traditional report viewer.**  Static PDF/HTML export is out of scope.
- **Not an IDE.**  No source editing, no synthesis, no bitstream generation.
- **Not an auditor.**  No PASS/HOLD gate, no sign-off workflow.

### Architecture Role

```text
CLI Pipeline (P1a/P1b)          Desktop Agent Shell
├─ generates artifact bundle →  ├─ reads /tmp artifact directory
├─ performs evidence grounding    ├─ renders structured views
├─ produces diagnostics           ├─ accepts user queries
└─ writes to /tmp                 └─ calls CLI tools / spawns agents
       ↑___________________________________________|
```

The desktop shell is the **human-facing side** of the Agent loop.  It does not
replace the CLI; it complements it by providing interactive navigation over
grounded artifacts.

---

## 2. Artifact 输入契约 (Artifact Input Contract)

### 2.1 P1b Concept Trace Artifact Bundle (Primary)

Each `p1b-trace-concept` run produces exactly 6 files in a single directory:

| File | Role | Required |
|---|---|---|
| `concept_trace_graph.json` | **Source of truth.**  Contains `ConceptTraceGraph` with nodes, edges, claims, evidence, diagnostics, uncertainty notes. | Yes |
| `concept_trace_index.json` | **Reverse index.**  `ConceptTraceIndex` with claim_index, evidence_index, node_index, edge_index, cross_references. | Yes |
| `grounding_report.json` | **Grounding diagnostics.**  `GroundingReport` with diagnostics list and summary counts. | Yes |
| `run_metadata.json` | **Run metadata.**  Elapsed time, status, artifact list, concept name, project root path. | Yes |
| `concept_trace.md` | **Rendered Markdown.**  Human-readable summary; derived from graph.  May be regenerated from graph. | Yes |
| `concept_trace.mmd` | **Rendered Mermaid.**  Static `graph TD` diagram text; derived from graph.  May be regenerated from graph. | Yes |

### 2.2 P1a Artifact Bundle (Compatibility)

The desktop shell must also be capable of opening P1a artifact directories:

| File | Role | Required |
|---|---|---|
| `project_graph.json` | `ProjectGraph` with candidate_claims, evidence_items, uncertainty_notes, grounding_diagnostics. | Yes |
| `trace_index.json` | `TraceIndex` with claim_index, evidence_index, node_index, cross_references. | Yes |
| `memory_manifest.json` | Source snapshot hashes for freshness check. | Optional |
| `summary.md` | Human-readable project summary. | Optional |
| `flow.mmd` | Mermaid flow diagram. | Optional |
| `trace.md` | Claim-to-source trace view. | Optional |
| `run_metadata.json` | Run metadata. | Optional |

### 2.3 Artifact Discovery Rules

```text
1. The desktop shell receives an artifact directory path from the user
   (file picker or text input).

2. Default search roots:
   - /tmp/fpga_devmind/
   - /private/tmp/fpga_devmind/
   - tempfile.gettempdir() / fpga_devmind /

3. The shell detects bundle type by file presence:
   - If concept_trace_graph.json exists → P1b bundle
   - Else if project_graph.json exists → P1a bundle
   - Else → unknown / incomplete bundle

4. For incomplete bundles:
   - Produce structured diagnostics (not a crash).
   - List missing required files.
   - Offer to open with degraded view if source-of-truth JSON is present.
```

### 2.4 Security & Isolation Rules

```text
- The shell reads artifacts only; it never writes into the artifact directory.
- The shell never reads source code from fpga_project_* directly.
- The shell never loads API keys or calls external LLM providers.
- The shell never runs Vivado, synthesis, implementation, or bitstream generation.
- The shell treats artifact paths as read-only references.
```

---

## 3. 视图规划 (View Planning)

The desktop shell provides the following views.  Each view maps to specific
JSON artifact fields.

### 3.1 Run Summary View

**Purpose:** Overview of a single trace run.

**Data Source:** `run_metadata.json`

**Display Fields:**

```text
schema_version       # "p1b-run-metadata-0.1"
concept              # Traced concept name
project_root         # Original project path (display only, not navigable)
output_dir           # Artifact directory path
elapsed_seconds      # Wall-clock time
status               # "ok" | "blocked"
blocking_diagnostics # Count
mapping_claims       # Count
evidence_items       # Count
artifacts            # List of artifact filenames
```

**Visual Cues:**
- `status == "blocked"` → red/orange header banner with blocking diagnostic count.
- `status == "ok"` → green/blue header.

### 3.2 Concept Trace Graph View

**Purpose:** Interactive navigation of the concept trace graph.

**Data Source:** `concept_trace_graph.json`

**Sub-views:**

#### Node List

```text
Fields per node:
  node_id, label, kind, stage_id, file_path, confidence, notes

Grouping:
  - By kind: concept → stage_view → rtl_module → rtl_signal → rtl_always_block
  - By stage_id: L5_L6 → RTL
```

#### Edge List

```text
Fields per edge:
  edge_id, from_node_id, to_node_id, label, edge_type, confidence

Cross-reference:
  - Click from_node_id → jump to Node List filtered to that node.
  - Click to_node_id   → jump to Node List filtered to that node.
```

#### Graph Integrity Check

```text
Rule: Every from_node_id and to_node_id in edges must exist in nodes.
If dangling reference found:
  - Display as "Unresolved reference: {node_id}".
  - Do not crash; render edge in gray/strikethrough.
```

### 3.3 Evidence Browser View

**Purpose:** Browse all evidence items with filtering and cross-reference.

**Data Source:** `concept_trace_graph.json` → `evidence_items`

**Display Fields per EvidenceItem:**

```text
evidence_id      # E.g. "E:p1b_concept:/tmp/...:1:10:1"
source_type      # "concept_occurrence" | "rtl_source"
file_path        # Source file path
start_line       # 1-based
end_line         # 1-based (inclusive)
symbol           # Detected symbol name
excerpt_summary  # Human-readable summary
evidence_strength # "strong" | "medium" | "weak"
```

**Filtering:**
- By source_type (L5/L6 vs RTL).
- By evidence_strength.
- By symbol substring search.

**Cross-reference:**
- Click evidence_id → show all claims and nodes that reference it.
  Use `concept_trace_index.json` → `evidence_index[eid].claim_ids` and
  `cross_references[eid]`.

### 3.4 Mapping Claim Detail View

**Purpose:** Inspect individual mapping claims with full evidence context.

**Data Source:** `concept_trace_graph.json` → `mapping_claims`

**Display Fields per MappingClaim:**

```text
claim_id                   # E.g. "MC_peak_idx_001"
concept_ref                # Target concept
statement                  # Human-readable mapping description
confidence                 # confirmed | supported | inferred | unknown | conflicted
bridge_kind                # explicit_source_bridge | calculation_role | ...
l5_l6_evidence_ids         # Evidence from Python stages
rtl_evidence_ids           # Evidence from RTL sources
bridge_evidence_ids        # Evidence supporting the bridge
required_missing_evidence  # List of missing evidence descriptions
l6_subject_ids             # Subject identifiers on L5/L6 side
rtl_subject_ids            # Subject identifiers on RTL side
```

**Visual Cues by Confidence:**

| Confidence | Color | Icon | Meaning |
|---|---|---|---|
| confirmed | Green bold | ✓ | Strong claim with explicit bridge evidence. |
| supported | Blue | ○ | Both sides present, non-weak bridge. |
| inferred | Yellow/amber | ~ | Naming or structural suggestion; may be wrong. |
| unknown | Gray | ? | One side missing; unresolved. |
| conflicted | Red | ✗ | Multiple incompatible candidates. |

**Rule:** `unknown` confidence is **not an error**.  It is a legitimate
expression of uncertainty.  The viewer must not show red error styling for
`unknown` claims.

### 3.5 Grounding Diagnostics View

**Purpose:** Show blocking and non-blocking diagnostics with severity
visualization.

**Data Source:** `grounding_report.json` → `diagnostics`

**Display Fields per GroundingDiagnostic:**

```text
diagnostic_id       # E.g. "GD_0001"
target_claim_id     # Claim this diagnostic refers to (may be null)
severity            # "blocking" | "non_blocking"
issue_type          # E.g. "unsupported_confirmed_mapping"
message             # Human-readable explanation
recommended_action  # Suggested fix
cross-reference:
  related_evidence_ids  # Evidence involved
```

**Visual Cues by Severity:**

| Severity | Color | Meaning | Action Required |
|---|---|---|---|
| blocking | Red/Orange | Overclaim detected; claim should not be trusted. | Downgrade or add evidence. |
| non_blocking | Yellow | Uncertainty acknowledged; claim is acceptable but weak. | Gather more evidence. |

**Rule:** The viewer must **not** present diagnostics as a PASS/HOLD audit.
Blocking diagnostics are "overclaim warnings," not "failed tests."  The user
may still choose to act on them or not.

### 3.6 Markdown / Mermaid Preview View

**Purpose:** Render pre-generated human-readable views.

**Data Sources:**
- `concept_trace.md` → Markdown preview (with syntax highlighting for code blocks).
- `concept_trace.mmd` → Mermaid diagram text (rendered via embedded Mermaid
  renderer or displayed as source with "Copy" button).

**Behavior:**
- These are **read-only rendered views**; the viewer does not regenerate them.
- If files are missing, show "Rendered view not available; regenerate from CLI."

### 3.7 Future: Agent Interaction Panel (T011+)

**Placeholder contract:**

```text
- Accept natural-language user queries about the current trace.
- Display query history.
- Show tool calls spawned by the Agent (e.g. "Re-run trace with concept X").
- Render Agent responses with embedded references to claims/evidence/diagnostics.
- All Agent reasoning happens in the CLI/backend; the desktop panel is pure UI.
```

---

## 4. 数据契约 (Data Contract)

### 4.1 Cross-Reference Resolution

The desktop shell resolves cross-references using `concept_trace_index.json`:

```text
evidence_id → claims:
  index.evidence_index[eid].claim_ids

evidence_id → nodes:
  index.cross_references[eid]  (includes claim_id + node_ids)

claim_id → evidence:
  index.claim_index[cid].l5_l6_evidence_ids
  index.claim_index[cid].rtl_evidence_ids

node_id → node info:
  index.node_index[nid]  # {kind, stage_id?, file_path?}

edge_id → edge info:
  index.edge_index[eid]  # {from, to, edge_type}
```

### 4.2 Dangling Reference Handling

```text
Rule: When a reference target is missing, the viewer must:
  1. Display the reference ID as plain text (not a hyperlink).
  2. Append "(unresolved)" or "(missing)" label.
  3. Gray out the reference; do not crash or hide it.
  4. Log a silent diagnostic (optional) for debugging.

Example: A claim references evidence_id "E_OLD" that no longer exists.
  → Display: "E_OLD (unresolved)"
```

### 4.3 Confidence Display Rules

| Confidence | Viewer Treatment |
|---|---|
| confirmed | Strong visual weight; green accent. |
| supported | Normal weight; blue accent. |
| inferred | Dimmed/italic; yellow/amber accent; tooltip: "Inferred from naming or structural similarity." |
| unknown | Gray; tooltip: "One side of evidence is missing; unresolved." |
| conflicted | Red accent; tooltip: "Multiple incompatible candidates detected." |

### 4.4 Diagnostic Display Rules

| Severity | Viewer Treatment |
|---|---|
| blocking | Red/Orange highlight on the affected claim. Expandable detail panel. |
| non_blocking | Yellow highlight. Collapsed by default; expandable. |

**Important:** The viewer must not compute a "PASS/FAIL" score from
diagnostics.  Each diagnostic is an independent observation.

---

## 5. 桌面端约束 (Desktop Constraints)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  HARD CONSTRAINTS (must be enforced by T009/T010 implementation)        │
├─────────────────────────────────────────────────────────────────────────┤
│  ✗ No Web GUI (no browser, no Electron, no web server)                  │
│  ✗ No Vivado / synthesis / implementation / bitstream                   │
│  ✗ No modification of fpga_project_* target projects                    │
│  ✗ No API key loading or external LLM provider calls                    │
│  ✗ No artifact modification (read-only)                                 │
│  ✗ No PASS/HOLD audit gate                                              │
│  ✗ No source code editing                                               │
├─────────────────────────────────────────────────────────────────────────┤
│  SOFT CONSTRAINTS (direction, not enforced)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  ✓ Default artifact root: /tmp or /private/tmp                          │
│  ✓ macOS/Linux first; Windows secondary                                 │
│  ✓ Unknown confidence is normal, not an error                           │
│  ✓ Grounding diagnostics are warnings, not test failures                │
│  ✓ All semantic truth originates from CLI pipeline, not desktop         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. T009 / T010 后续实现建议

### T009: Desktop App Prototype

**Scope:** Minimum viable desktop shell that can open an artifact directory
and display the 7 views above in a tabbed or sidebar layout.

**Suggested Technology Stack (1-2 candidates):**

1. **Tauri + WebView (Rust + frontend framework)**
   - Pros: Small binary, native feel, good macOS/Linux support, secure
     sandbox, WebView for rendering Markdown/Mermaid without full Electron.
   - Cons: Rust build complexity; WebView is still browser-based rendering
     (but not a Web GUI in the traditional sense since it's a native app
     wrapper).

2. **PyQt / PySide6 (Python-native)**
   - Pros: Full Python ecosystem, tight integration with existing
     fpga_devmind code, no JS/WebView needed, mature on all platforms.
   - Cons: Larger binary size, LGPL licensing considerations for PyQt
     (PySide6 is LGPL-friendly), less modern UI defaults.

**Decision criteria for T009:**
- If the team prefers staying in Python → PySide6.
- If binary size and security sandbox are critical → Tauri.
- Do not decide now; T009 should prototype one and measure.

**T009 Minimum Views:**
- File picker for artifact directory.
- Run Summary panel.
- JSON tree browser (collapsible) for graph/index/diagnostics.
- Markdown preview (read-only).
- Mermaid source display with copy button.

### T010: P1b Concept Trace View

**Scope:** Rich interactive view of the concept trace graph, replacing the
plain JSON tree browser.

**Features:**
- Node list with kind-based icons and confidence color coding.
- Edge list with bidirectional navigation.
- Evidence browser with filtering and cross-reference popovers.
- Mapping claim detail with expandable evidence sections.
- Grounding diagnostics overlaid on claims (red/yellow badges).
- Click-to-navigate: claim → evidence, evidence → nodes, node → edges.

**Data Flow:**
```text
concept_trace_graph.json ─┬─→ Node List
                          ├─→ Edge List
                          ├─→ Evidence Browser
                          ├─→ Claim Detail
                          └─→ Diagnostic Overlay

concept_trace_index.json ─┬─→ Cross-reference resolution
                          └─→ Click-to-jump

grounding_report.json ────→ Diagnostic List + Claim Badges
```

---

## Acceptance

- [ ] Contract covers all 6 required artifact files with field-level detail.
- [ ] Contract defines dangling reference handling.
- [ ] Contract defines unknown confidence treatment (not error).
- [ ] Contract defines diagnostic visualization (not PASS/HOLD).
- [ ] Contract names P1a and P1b artifact files consistently with existing docs.
- [ ] T009/T010 scope is clearly separated; no code is written in T008.
- [ ] Desktop constraints table is present and unambiguous.

## Verification

```bash
# No code changes; verify docs compile and tests still pass.
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
```
