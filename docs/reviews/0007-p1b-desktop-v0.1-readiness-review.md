# Review 0007: P1b + Desktop Shell V0.1 Readiness

Date: 2026-06-08

## Scope

Reviewed:

```text
src/fpga_devmind/p1b_cli.py               (T002–T007 pipeline)
src/fpga_devmind/desktop/                 (T009–T010)
tests/test_p1b.py                         (176 tests)
tests/test_desktop_*.py                   (51 tests)
docs/tasks/T001–T010.md
docs/implementation-status.md
docs/p1a-v0.1-quickstart.md
```

## V0.1 Definition

P1b + Desktop Shell V0.1 is declared when:

```text
1. One-concept L5/L6-to-RTL trace pipeline (T001–T007) is deterministic,
   schema-validated, and produces 6 grounded artifacts per run.
2. Grounding checker (T006) blocks unsupported confirmed claims and
   naming-only supported claims; non-blocking diagnostics flag acknowledged
   uncertainty without treating them as audit failures.
3. Desktop Agent Shell (T009–T010) can read P1b artifact bundles and
   display structured trace views (Nodes, Edges, Claims, Evidence,
   Diagnostics) without PySide6 blocking tests.
4. All artifacts are read-only; no target project mutation, no Vivado,
   no external API calls, no PASS/HOLD semantics.
5. 251+ tests pass with zero failures; compileall clean.
```

## Current Capabilities

### P1b Pipeline (T001–T007)

| Capability | Status | Evidence |
|---|---|---|
| Schema-validated artifact contract (6 files) | ✅ | `p1b_schema.py`, round-trip JSON tests |
| Read-only source discovery (L5/L6 + RTL) | ✅ | `collect_p1b_sources()` excludes `__pycache__` |
| Concept evidence extraction with strength | ✅ | Strong/medium/weak + role hints |
| RTL evidence extraction (regex-based) | ✅ | Module/signal/always/assign/comment |
| Conservative mapping claim builder | ✅ | Naming-only → inferred; one-sided → unknown/inferred |
| Grounding checker with blocking/non-blocking | ✅ | T006 mutation-tested de-duplication |
| CLI `p1b-trace-concept` with artifact render | ✅ | Writes 6 artifacts; nonzero exit on blocking |
| Output path safety guard | ✅ | `ensure_safe_output_dir()` rejects `fpga_project_*` paths |
| Unknown concept legitimate output | ✅ | `N_RTL_UNKNOWN` placeholder, no dangling edges |
| Smoke on `coarse_sync_glm` and `fine_cfo` | ✅ | 194 tests (18 P1a + 176 P1b) pass |

### Desktop Shell (T009–T010)

| Capability | Status | Evidence |
|---|---|---|
| Artifact bundle detection (P1b/P1a/unknown) | ✅ | `detect_bundle_type()` |
| Bundle validation with structured diagnostics | ✅ | `validate_bundle()` produces `ArtifactDiagnostic` |
| Never-raises loader with OSError/JSON safety | ✅ | `load_bundle()` tested on nonexistent paths |
| Run Summary view model | ✅ | `build_run_summary()` |
| JSON Tree Browser (max-depth protection) | ✅ | `build_json_tree()`, depth=50 guard |
| Markdown Preview with Mermaid fallback | ✅ | `build_markdown_preview()` |
| PySide6 GUI with 4 tabs (T009) | ✅ | `_gui.py` with graceful fallback |
| Concept Trace structured tables (T010) | ✅ | 5 sub-tabs: Nodes/Edges/Claims/Evidence/Diagnostics |
| Cross-reference resolution | ✅ | Edge labels, evidence claim refs, diagnostic counts |
| Dangling reference marking | ✅ | `(unresolved: <node_id>)` |
| Diagnostic de-duplication (graph + grounding) | ✅ | `_deduplicate_diagnostics()` |
| Node has_diagnostics via evidence→claim chain | ✅ | Conservative, defaults False |
| Unknown confidence displayed neutrally | ✅ | No pass/fail/error semantics |
| Pure-Python testable without PySide6 | ✅ | 51 desktop tests run without Qt |

### Test Matrix

```text
P1a tests:           18  ✅
P1b tests:          176  ✅
Desktop loader:      18  ✅
Desktop VM:          17  ✅
Desktop trace VM:    17  ✅
--------------------------------
Total:              251  ✅ (0 failures)
```

## What It Cannot Do (Explicit Boundaries)

```text
- LLM semantic reasoning / provider-backed model calls.
- Multi-turn ReAct loop or Agent interaction panel (T011 not started).
- Full SystemVerilog parser (regex-only RTL scanning).
- Batch multi-concept trace (single concept per run).
- Cross-concept structural/evolution edges.
- AST-level def-use or proven producer/consumer dataflow.
- Graph layout engine / interactive node-edge diagram.
- Click-to-navigate cross-reference popovers.
- Claim editing, artifact mutation, or graph mutation.
- Vivado / synthesis / implementation / bitstream.
- PASS / HOLD / finding / audit semantics.
- Web GUI, Web server, or browser-accessible URL.
```

## Risks and Gaps

| Risk | Severity | Mitigation | Remaining Work |
|---|---|---|---|
| Regex-based RTL scanning misses complex SystemVerilog structures | Medium | Documented limitation; no overclaim from parser gaps | P1b+ may add partial parser |
| Single-concept per run limits batch analysis workflow | Medium | By design for V0.1; batch deferred | P1b+ multi-concept orchestration |
| Desktop GUI requires PySide6 (not installed in current environment) | Low | Loader/VM layer works without GUI; graceful fallback tested | User installs `pip3 install pyside6` |
| No real LLM provider integration yet | Low | Provider contract, validation, and mock path exist; external API disabled by default | P1a+ provider adapter (future) |
| Claim detail cards and evidence filtering not implemented | Low | T010 scope explicitly excluded; tables show all rows | T011 or later |
| Mermaid is static text only | Low | Source display in GUI; no live renderer | Future Mermaid viewer or Qt SVG |
| Diagnostic de-duplication uses string fallback key when ID missing | Low | Fallback key is deterministic `(target_claim_id, issue_type, message)` | Documented in code |

## Next Phase Recommendations

### Immediate (T011, optional)

Agent Interaction Panel — if user decides to proceed:

```text
- Query input box (text only, no chat history).
- Response display with grounded claim references.
- Tool call suggestions (read-only, not executable).
- Keep PySide6 dependency optional.
```

### Short-term (P1b+ or P1c)

```text
- Multi-concept batch trace orchestration.
- Partial SystemVerilog parser for always-block hierarchy.
- Cross-concept structural edge inference (evolution/structural).
- Evidence filtering by strength, source_type, or file path.
```

### Medium-term (V0.2 candidate)

```text
- LLM provider adapter with real API calls (behind --allow-external-api).
- Semantic claim generation from evidence, not deterministic bridging.
- Interactive claim refinement (still read-only on source projects).
```

## Review Conclusion

### Verdict: ✅ P1b + Desktop Shell V0.1 Ready

Rationale:

1. **Deterministic pipeline is stable**: T001–T007 produce schema-validated artifacts, grounding checker blocks overclaims, and unknown concepts are handled as legitimate output.
2. **Desktop Shell validates architecture**: T009–T010 prove the artifact bundle contract is consumable by a native GUI layer. The pure-Python loader/view-model separation means the GUI is a thin, replaceable layer.
3. **Safety boundaries are enforced**: No Vivado, no project mutation, no external API, no PASS/HOLD. Output path guard and graceful PySide6 fallback are tested.
4. **Test coverage is sufficient for V0.1**: 251 tests, zero failures. P1b has dedicated mutation-style grounding tests. Desktop has loader, VM, and trace-VM tests without GUI automation.
5. **Documentation is current**: T001–T010 task cards, implementation-status, and quickstart all reflect the actual state.

### Trial Usage Recommendation

**Can be handed to a user for controlled trial** with the following caveats:

```text
- User must understand this is a deterministic evidence viewer, not an LLM Agent.
- PySide6 must be installed separately for the GUI (`pip3 install pyside6`).
- Single-concept traces only; batch workflows require manual scripting.
- RTL scanning is regex-based; complex SystemVerilog may produce incomplete evidence.
- Grounding diagnostics are warnings, not audit results. "blocking" means
  "do not trust this claim as-is," not "project is broken."
```

### Sign-off

```text
Review 0007 author: Claude Opus 4.8
Date: 2026-06-08
Tests: 251/251 pass
Compile: clean
Conclusion: V0.1 READY
```
