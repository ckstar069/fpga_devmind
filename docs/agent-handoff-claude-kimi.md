# Agent Handoff: Claude + Kimi Implementation

This document is the implementation handoff for external coding agents. It is written to keep implementation agents inside the fpga_devmind direction and prevent scope drift.

## Project Direction

`fpga_devmind` is an FPGA development-understanding Agent prototype. Its near-term job is:

```text
read -> graph -> explain -> trace -> query -> freshness
```

It is not:

```text
- a traditional static analyzer
- an audit checker
- a PASS/HOLD tool
- a report generator
- a Vivado automation tool
```

The long-term target is integration with `ai_project_template` into a Develop-Understand-Verify Agent.

## Implementation Principle

Use deterministic tools to collect evidence and enforce constraints. Use Agent/LLM semantics only through structured contracts.

Do not replace structured artifacts with free-form Markdown. Markdown is a rendered view only.

## Hard Constraints

Implementation agents must obey:

```text
- Do not modify any fpga_project_* target project.
- Do not run Vivado.
- Do not run synthesis / implementation / bitstream.
- Do not read, print, log or commit API key values.
- Do not add API key values to generated artifacts.
- Generated outputs default to /tmp or /private/tmp.
- Do not write generated artifacts into any path component beginning with fpga_project_.
- Do not make PASS/HOLD or finding-list outputs the product surface.
```

## Current Safe Commands

Use these for verification:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-smoke \
  --out-root /tmp/fpga_devmind/p1a_smoke
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-agent-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --question "L6 实现了什么流程" \
  --out /tmp/fpga_devmind/p1a_agent_l6 \
  --mock-semantic
```

Do not run external provider commands unless the assigned task explicitly covers provider disabled routes. Even then, current adapters must not call external APIs.

## Existing Core Files

Implementation agents should read before editing:

```text
PROJECT_CONTEXT.md
docs/direction-guardrails.md
docs/implementation-status.md
docs/implementation-plan-p1b.md
docs/p1a-plus-semantic-agent.md
src/fpga_devmind/cli.py
src/fpga_devmind/p1a.py
src/fpga_devmind/agent.py
src/fpga_devmind/graph_writer.py
src/fpga_devmind/llm_contract.py
src/fpga_devmind/safety.py
tests/test_p1a.py
tests/test_p1b.py
```

## Coding Rules

Prefer narrow changes:

```text
- Add small modules over large rewrites.
- Keep P1a / P1a+ behavior stable.
- Preserve JSON artifact compatibility unless the task explicitly changes the schema.
- Add tests with every behavior change.
- Put new P1b behavior tests in `tests/test_p1b.py` unless a task explicitly edits existing P1a behavior.
- Use structured parsers or AST where practical.
- Mark weak relationships as inferred or unknown.
- Keep comments sparse and useful.
```

Do not:

```text
- remove safety checks
- bypass validate_semantic_reasoning_result()
- mutate source project files
- introduce environment variable dumps
- turn summaries into source of truth
- silently downgrade stale artifact warnings
```

## Task Card Contract

Each implementation task should include:

```text
- objective
- allowed files
- forbidden files
- expected artifacts
- acceptance tests
- verification commands
- review notes
```

Agents should not expand beyond the task card. If a broader refactor seems useful, write it as a follow-up proposal instead.

Unit tests should use synthetic fixtures when possible. Tests that depend on `/Users/ckstar/Repo/znxt_ofdm/fpga_project_*` must skip cleanly when the target project is absent.

## GUI Direction

The final complete product should be a desktop Agent app, with macOS / Linux first and Windows second. Web GUI is not part of the current implementation route. GUI work is covered by:

```text
docs/ui-prototype-plan.md
docs/tasks/T008-desktop-artifact-viewer-contract.md
docs/tasks/T009-desktop-app-prototype.md
docs/tasks/T010-desktop-p1b-concept-trace-view.md
```

Do not start GUI work before the assigned task says so. The GUI target is desktop-only, macOS / Linux first and Windows second. Do not implement a Web GUI task. The first desktop GUI may be a read-only artifact viewer over generated JSON / Markdown / Mermaid artifacts, but the long-term desktop app must become the Human Interaction Layer for the Agent. It must not become the semantic source of truth, and it must not run Vivado, mutate target projects or call external provider APIs unless a later explicit workflow safely allows it.

## Review Requirement

After each meaningful slice:

```text
1. Run tests.
2. Run compileall.
3. Summarize generated artifacts.
4. Record any deferred risks.
5. Ask for or trigger Review Agent when the slice changes graph, evidence, provider, or grounding behavior.
```

The user should not be expected to catch low-level FPGA / Agent architecture issues manually.
