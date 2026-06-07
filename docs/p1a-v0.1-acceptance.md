# P1a V0.1 Acceptance

本文定义 P1a V0.1 的可用标准。它只评价当前 Understanding Layer 原型，不代表完整 FPGA Agent 已完成。

## Version Meaning

P1a V0.1 可称为可试用版本，当且仅当它能稳定完成：

```text
read L6 evidence
-> build grounded ProjectGraph
-> build TraceIndex
-> render summary and Mermaid flow
-> answer deterministic grounded queries
-> check memory freshness
-> run smoke validation on two representative samples
```

它仍然不是：

```text
- full Agent runtime
- LLM/ReAct semantic reasoner
- L6-to-RTL mapper
- verification coverage explainer
- audit / PASS-HOLD / finding tool
```

## Acceptance Checklist

### Direction

```text
[x] Uses fpga_devmind naming.
[x] Keeps short-term focus on read / graph / explain / trace.
[x] Does not emit PASS/HOLD or audit findings.
[x] Treats static analysis as evidence extraction, not final semantic authority.
[x] Has completed independent V0.1 review and response.
```

### Safety

```text
[x] Does not modify fpga_project_* target projects.
[x] Does not run Vivado.
[x] Does not run synthesis / implementation / bitstream.
[x] Writes default generated artifacts under /tmp/fpga_devmind.
[x] Does not require or log API keys.
```

### Artifacts

```text
[x] project_graph.json generated.
[x] trace_index.json generated.
[x] memory_manifest.json generated.
[x] summary.md generated from graph data.
[x] flow.mmd generated from VisualizationSpec.
[x] trace.md generated from TraceIndex.
[x] run_metadata.json generated.
```

### Grounding

```text
[x] Main concepts have evidence ids.
[x] Visualization nodes have claim and evidence links.
[x] Visualization edges have claim and evidence links.
[x] Confirmed claims require evidence.
[x] Class/docstring-backed implementation claims are downgraded to supported.
[x] Heuristic relation edges are labeled inferred order, not dataflow.
[x] Blocking diagnostics cause non-zero p1a-understand-stage exit.
[x] Query answers are derived from ProjectGraph and TraceIndex.
[x] Stale memory produces explicit Freshness Warning.
```

### Smoke Samples

Current smoke command:

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-smoke \
  --out-root /tmp/fpga_devmind/p1a_smoke
```

Required result:

```text
[x] fpga_project_coarse_sync_glm / L6_resource_opt passes.
[x] fpga_project_fine_cfo / L6_resource_opt passes.
[x] failed = 0.
[x] blocking_diagnostics = 0 for both samples.
[x] freshness = current for both samples.
```

### Query

Required query types:

```text
[x] stage flow.
[x] fixed-point / Q format.
[x] stream interface.
[x] pipeline timing.
[x] resource estimates.
[x] claim id drill-down.
[x] evidence id drill-down.
```

## Known Limitations

These do not block P1a V0.1, but must stay explicit:

```text
- Generic flow ordering is heuristic and may be wrong for unfamiliar L6 architectures.
- P1a main-flow edges are inferred implementation order, not proven dataflow.
- Claim-type-specific grounding checks are incomplete.
- Resource estimates preserve symbolic expressions instead of evaluating full totals.
- Fixed-point extraction is shallow and partly parameter-driven.
- Interface extraction is shallow and assumes common AXIS naming.
- Pipeline timing reports unknown latency unless directly extracted.
- Query is deterministic keyword routing, not LLM natural-language understanding.
- No user feedback memory is implemented yet.
- No cross-stage concept trace is implemented yet.
- No L6-to-RTL evidence mapping is implemented yet.
```

## V0.1 Decision Rule

P1a V0.1 can be tagged when:

```text
1. p1a-smoke passes with failed = 0.
2. unittest and compileall pass.
3. Independent V0.1 review has no unresolved high-severity blocker.
4. Any accepted review fixes are committed.
5. docs/p1a-v0.1-quickstart.md and this acceptance checklist match the current CLI.
```

## Suggested Next Phase

After P1a V0.1:

```text
P1a+:
  Add LLM/ReAct semantic claim generation around the deterministic evidence shell.

P1b:
  Trace one concept from L5/L6 to RTL with explicit mapping evidence.

P1c:
  Explain verification coverage against semantic nodes.
```
