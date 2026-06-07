# Review Response 0003

This response records how Review 0003 was handled.

## Accepted Findings

### Dataflow Was Not Actually Grounded

Decision: accepted.

Changes:

```text
- Heuristic relation claims are now implementation_order_claim.
- Confidence is inferred, not supported or confirmed.
- Mermaid edges are labeled inferred order.
- Query output now reports inferred implementation order instead of dataflow.
- P1a adds an explicit uncertainty note: implementation order versus dataflow.
```

Rationale:

```text
P1a currently does not trace step/process bodies, producer/consumer variables,
valid/data movement, or call/return flow deeply enough to claim dataflow.
```

### Confirmed Claims Were Too Easy

Decision: accepted.

Changes:

```text
- Stage-level and concept-level implementation claims are now supported.
- Resource refinement claim is supported.
- Class/docstring evidence is no longer enough to create confirmed implementation claims.
```

Rationale:

```text
P1a should preserve evidence anchors without overstating deterministic semantic
confidence. Confirmed claims should wait for claim-type-specific evidence rules.
```

### Visualization Could Pass While Semantically Wrong

Decision: accepted.

Changes:

```text
- Visualization edge label changed to inferred order.
- Pipeline valid propagation is now unknown.
- Inferred order uncertainty is linked to order claims.
```

Rationale:

```text
The graph is still useful as a reading guide, but not as a proven dataflow graph.
```

### Top-Level Pipeline as Flow Tail

Decision: accepted.

Changes:

```text
- Generic concept inference excludes top-level pipeline classes from the main flow when other concrete concepts exist.
- Pipeline top remains discoverable as a main entry candidate, but is not rendered as a downstream processing node.
```

Rationale:

```text
Top-level pipeline classes are often orchestrators/containers, not downstream datapath stages.
```

### Hardcoded Target Device

Decision: accepted.

Changes:

```text
- ResourceEstimateSpec.target_device is no longer hardcoded to xc7z020.
```

## Deferred Items

The following are accepted as real limitations but deferred beyond P1a V0.1:

```text
- Claim-type-specific grounding checker for every claim type.
- Deep call graph / def-use / producer-consumer extraction.
- Signal-specific fixed-point inference.
- Interface-level valid/data movement extraction.
- Imported helper / external module freshness tracking.
- Negative synthetic fixtures for relationship grounding.
```

These are now reflected as known limitations or next-phase work.

## V0.1 Impact

After this response, P1a V0.1 remains a conservative Understanding Layer prototype:

```text
read -> graph -> explain -> trace -> query -> freshness
```

It does not claim proven dataflow or verified behavior. It exposes inferred implementation order with explicit uncertainty.
