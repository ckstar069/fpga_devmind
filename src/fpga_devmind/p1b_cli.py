"""P1b CLI runner: chains T002-T006 and writes final artifacts.

Exposes ``run_p1b_trace_concept()`` which drives the full pipeline:
  source discovery → concept evidence → RTL evidence → mapping claims
  → grounding check → graph/index/render → artifact write.

T007 scope: CLI pipeline, rendering, and smoke testing.
Does not call LLM, does not modify target projects, does not run Vivado.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_collectors import SourceCollection, collect_p1b_sources
from fpga_devmind.p1b_concept import (
    ConceptCollection,
    collect_concept_evidence,
)
from fpga_devmind.p1b_grounding import GroundingReport, check_grounding
from fpga_devmind.p1b_mapping import MappingClaimResult, build_mapping_claims
from fpga_devmind.p1b_rtl import RTLEvidenceCollection, collect_rtl_evidence
from fpga_devmind.p1b_schema import (
    ConceptTraceEdge,
    ConceptTraceGraph,
    ConceptTraceIndex,
    ConceptTraceNode,
    EDGE_TYPE_MAPPING,
    NODE_KIND_CONCEPT,
    NODE_KIND_RTL_ALWAYS_BLOCK,
    NODE_KIND_RTL_MODULE,
    NODE_KIND_RTL_SIGNAL,
    NODE_KIND_STAGE_VIEW,
)
from fpga_devmind.safety import ensure_safe_output_dir

# Map RTL object_type → ConceptTraceNode kind constant.
_RTL_TYPE_TO_NODE_KIND: dict[str, str] = {
    "module": NODE_KIND_RTL_MODULE,
    "signal": NODE_KIND_RTL_SIGNAL,
    "always_block": NODE_KIND_RTL_ALWAYS_BLOCK,
}


def run_p1b_trace_concept(
    project_root: Path,
    concept_name: str,
    out_dir: Path,
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Run the full P1b concept trace pipeline.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    concept_name : str
        Name of the concept to trace (e.g. ``"peak_idx"``).
    out_dir : Path
        Output directory for artifacts (must be a safe temp path).

    Returns
    -------
    dict[str, Any]
        Run metadata including status and artifact paths.

    Raises
    ------
    ValueError
        If *out_dir* is not a safe temp path.
    """
    safe_out = ensure_safe_output_dir(out_dir, label="P1b trace output")
    safe_out.mkdir(parents=True, exist_ok=True)
    t_start = time.monotonic()

    # --- T002: source discovery ---
    sources = collect_p1b_sources(project_root, concept_name)

    # --- T003: L5/L6 concept evidence ---
    concept_candidates = (
        sources.l5_candidate_files + sources.l6_candidate_files
    )
    concept_collection = collect_concept_evidence(
        project_root, concept_name, concept_candidates
    )

    # --- T004: RTL evidence ---
    rtl_collection = collect_rtl_evidence(
        concept_name, sources.rtl_candidate_files
    )

    # --- T005: mapping claims ---
    mapping_result = build_mapping_claims(concept_collection, rtl_collection)

    # --- T006: grounding check ---
    grounding_report = check_grounding(mapping_result)

    # --- Build graph ---
    graph = _build_graph(
        concept_name, sources, concept_collection,
        rtl_collection, mapping_result, grounding_report,
    )

    # --- Build index ---
    index = _build_index(concept_name, graph)

    # --- Write artifacts ---
    _write_json(safe_out / "concept_trace_graph.json", graph.to_dict())
    _write_json(safe_out / "concept_trace_index.json", index.to_dict())
    _write_json(safe_out / "grounding_report.json", grounding_report.to_dict())

    # --- Render markdown ---
    md = _render_markdown(
        concept_name, graph, mapping_result, grounding_report
    )
    _ = (safe_out / "concept_trace.md").write_text(
        md, encoding="utf-8"
    )

    # --- Render mermaid ---
    mmd = _render_mermaid(graph)
    _ = (safe_out / "concept_trace.mmd").write_text(
        mmd, encoding="utf-8"
    )

    # --- Run metadata ---
    elapsed = time.monotonic() - t_start
    blocking = [
        d for d in grounding_report.diagnostics
        if d.severity == "blocking"
    ]
    metadata: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "schema_version": "p1b-run-metadata-0.1",
        "concept": concept_name,
        "project_root": str(project_root),
        "output_dir": str(safe_out),
        "elapsed_seconds": round(elapsed, 3),
        "status": "blocked" if blocking else "ok",
        "blocking_diagnostics": len(blocking),
        "mapping_claims": len(mapping_result.mapping_claims),
        "evidence_items": (
            len(concept_collection.evidence_items)
            + len(rtl_collection.evidence_items)
        ),
        "artifacts": [
            "concept_trace_graph.json",
            "concept_trace_index.json",
            "concept_trace.md",
            "concept_trace.mmd",
            "grounding_report.json",
            "run_metadata.json",
        ],
    }
    _write_json(safe_out / "run_metadata.json", metadata)

    return metadata


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _build_graph(
    concept_name: str,
    sources: SourceCollection,
    concept_collection: ConceptCollection,
    rtl_collection: RTLEvidenceCollection,
    mapping_result: MappingClaimResult,
    grounding_report: GroundingReport,
) -> ConceptTraceGraph:
    """Build ConceptTraceGraph from pipeline outputs."""
    graph = ConceptTraceGraph(
        concept=concept_name,
        task_request={"workflow": "p1b-trace-concept"},
        project_profile={
            "project_id": sources.project_id,
            "concept_name": concept_name,
        },
    )

    # --- Concept-level L5/L6 node (always present) ---
    concept_node_id = "N_CONCEPT_{}".format(concept_name)
    l56_eids = [
        ei.evidence_id for ei in concept_collection.evidence_items
    ]
    if concept_collection.evidence_items:
        graph.nodes.append(
            ConceptTraceNode(
                node_id=concept_node_id,
                label="{} @ L5/L6".format(concept_name),
                kind=NODE_KIND_STAGE_VIEW,
                stage_id="L5_L6",
                evidence_ids=l56_eids,
                confidence="supported",
            )
        )
    else:
        graph.nodes.append(
            ConceptTraceNode(
                node_id=concept_node_id,
                label="{} (unknown)".format(concept_name),
                kind=NODE_KIND_CONCEPT,
                confidence="unknown",
                notes="Concept not found in L5/L6 sources.",
            )
        )

    # --- RTL object nodes ---
    rtl_node_map: dict[str, str] = {}  # subject_id → node_id
    for view in rtl_collection.rtl_views:
        kind = _RTL_TYPE_TO_NODE_KIND.get(
            view.object_type, NODE_KIND_RTL_MODULE
        )
        node_id = "N_{}".format(view.rtl_object_id)
        subj_id = "{}:{}".format(view.object_type, view.name)
        rtl_node_map[subj_id] = node_id
        graph.nodes.append(
            ConceptTraceNode(
                node_id=node_id,
                label="{} ({})".format(view.name, view.object_type),
                kind=kind,
                stage_id="RTL",
                file_path=view.file_path,
                evidence_ids=view.evidence_ids,
                confidence=view.confidence,
            )
        )

    # --- Mapping edges (ensure all endpoints exist as nodes) ---
    _needs_rtl_unknown = False
    for claim in mapping_result.mapping_claims:
        if claim.rtl_subject_ids:
            for rtl_sid in claim.rtl_subject_ids:
                to_node = rtl_node_map.get(rtl_sid, "N_RTL_UNKNOWN")
                if to_node == "N_RTL_UNKNOWN":
                    _needs_rtl_unknown = True
                safe_sid = rtl_sid.replace(":", "_")
                graph.edges.append(
                    ConceptTraceEdge(
                        edge_id="E_{}_{}".format(
                            claim.claim_id, safe_sid
                        ),
                        from_node_id=concept_node_id,
                        to_node_id=to_node,
                        label="{} ({})".format(
                            claim.bridge_kind, claim.confidence
                        ),
                        edge_type=EDGE_TYPE_MAPPING,
                        confidence=claim.confidence,
                        evidence_ids=claim.evidence_ids,
                        source_claim_ids=[claim.claim_id],
                    )
                )
        else:
            _needs_rtl_unknown = True
            graph.edges.append(
                ConceptTraceEdge(
                    edge_id="E_{}_none".format(claim.claim_id),
                    from_node_id=concept_node_id,
                    to_node_id="N_RTL_UNKNOWN",
                    label="{} ({})".format(
                        claim.bridge_kind, claim.confidence
                    ),
                    edge_type=EDGE_TYPE_MAPPING,
                    confidence=claim.confidence,
                    evidence_ids=claim.evidence_ids,
                    source_claim_ids=[claim.claim_id],
                )
            )

    if _needs_rtl_unknown:
        graph.nodes.append(
            ConceptTraceNode(
                node_id="N_RTL_UNKNOWN",
                label="RTL realization unknown",
                kind=NODE_KIND_CONCEPT,
                stage_id="RTL",
                confidence="unknown",
                notes="RTL side missing or unresolved.",
            )
        )

    # --- Evidence items ---
    graph.evidence_items.extend(concept_collection.evidence_items)
    graph.evidence_items.extend(rtl_collection.evidence_items)

    # --- Mapping claims ---
    graph.mapping_claims.extend(mapping_result.mapping_claims)

    # --- Grounding diagnostics ---
    graph.grounding_diagnostics.extend(grounding_report.diagnostics)

    # --- Uncertainty notes ---
    graph.uncertainty_notes.extend(mapping_result.uncertainty_notes)

    return graph


# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------


def _build_index(
    concept_name: str,
    graph: ConceptTraceGraph,
) -> ConceptTraceIndex:
    """Build ConceptTraceIndex from a populated ConceptTraceGraph."""
    index = ConceptTraceIndex(concept=concept_name)

    # --- Claim index ---
    for claim in graph.mapping_claims:
        index.claim_index[claim.claim_id] = {
            "confidence": claim.confidence,
            "l5_l6_evidence_ids": claim.l5_l6_evidence_ids,
            "rtl_evidence_ids": claim.rtl_evidence_ids,
            "bridge_kind": claim.bridge_kind,
        }

    # --- Evidence index ---
    ev_to_claims: dict[str, list[str]] = {}
    for claim in graph.mapping_claims:
        for eid in claim.evidence_ids:
            ev_to_claims.setdefault(eid, []).append(claim.claim_id)
    for ei in graph.evidence_items:
        index.evidence_index[ei.evidence_id] = {
            "source_type": ei.source_type,
            "claim_ids": ev_to_claims.get(ei.evidence_id, []),
        }

    # --- Node index ---
    for node in graph.nodes:
        entry = {"kind": node.kind}
        if node.stage_id:
            entry["stage_id"] = node.stage_id
        if node.file_path:
            entry["file_path"] = node.file_path
        index.node_index[node.node_id] = entry

    # --- Edge index ---
    for edge in graph.edges:
        index.edge_index[edge.edge_id] = {
            "from": edge.from_node_id,
            "to": edge.to_node_id,
            "edge_type": edge.edge_type,
        }

    # --- Cross references ---
    for claim in graph.mapping_claims:
        for eid in claim.evidence_ids:
            refs: list[str] = [claim.claim_id]
            for node in graph.nodes:
                if eid in node.evidence_ids:
                    refs.append(node.node_id)
            index.cross_references[eid] = refs

    return index


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_markdown(
    concept_name: str,
    graph: ConceptTraceGraph,
    mapping_result: MappingClaimResult,  # pyright: ignore[reportUnusedParameter]
    grounding_report: GroundingReport,
) -> str:
    """Render concept trace as Markdown."""
    lines: list[str] = []
    lines.append("# Concept Trace: {}".format(concept_name))
    lines.append("")

    # --- Summary ---
    lines.append("## Summary")
    lines.append("")
    lines.append("- Concept: {}".format(concept_name))
    claims_by_conf: dict[str, int] = {}
    for c in graph.mapping_claims:
        claims_by_conf[c.confidence] = (
            claims_by_conf.get(c.confidence, 0) + 1
        )
    lines.append(
        "- Mapping claims: {}".format(len(graph.mapping_claims))
    )
    for conf in sorted(claims_by_conf):
        lines.append(
            "  - {}: {}".format(conf, claims_by_conf[conf])
        )
    blocking = [
        d for d in grounding_report.diagnostics
        if d.severity == "blocking"
    ]
    lines.append(
        "- Blocking diagnostics: {}".format(len(blocking))
    )
    lines.append(
        "- Evidence items: {}".format(len(graph.evidence_items))
    )
    lines.append("")

    # --- L5/L6 Evidence ---
    l56_items = [
        ei for ei in graph.evidence_items
        if ei.source_type == "concept_occurrence"
    ]
    if l56_items:
        lines.append("## L5/L6 Evidence")
        lines.append("")
        lines.append("| ID | File | Symbol | Strength |")
        lines.append("|----|------|--------|----------|")
        for ei in l56_items:
            short_file = Path(ei.file_path).name
            lines.append(
                "| {} | {} | {} | {} |".format(
                    ei.evidence_id, short_file,
                    ei.symbol or "-", ei.evidence_strength,
                )
            )
        lines.append("")

    # --- RTL Evidence ---
    rtl_items = [
        ei for ei in graph.evidence_items
        if ei.source_type == "rtl_source"
    ]
    if rtl_items:
        lines.append("## RTL Evidence")
        lines.append("")
        lines.append("| ID | File | Symbol | Strength |")
        lines.append("|----|------|--------|----------|")
        for ei in rtl_items:
            short_file = Path(ei.file_path).name
            lines.append(
                "| {} | {} | {} | {} |".format(
                    ei.evidence_id, short_file,
                    ei.symbol or "-", ei.evidence_strength,
                )
            )
        lines.append("")

    # --- Mapping Claims ---
    if graph.mapping_claims:
        lines.append("## Mapping Claims")
        lines.append("")
        for claim in graph.mapping_claims:
            lines.append(
                "### {} ({})".format(claim.claim_id, claim.confidence)
            )
            lines.append("")
            lines.append(
                "- Bridge: {}".format(claim.bridge_kind)
            )
            if claim.statement:
                lines.append(
                    "- Statement: {}".format(claim.statement)
                )
            if claim.l5_l6_evidence_ids:
                lines.append(
                    "- L5/L6 evidence: {}".format(
                        ", ".join(claim.l5_l6_evidence_ids)
                    )
                )
            if claim.rtl_evidence_ids:
                lines.append(
                    "- RTL evidence: {}".format(
                        ", ".join(claim.rtl_evidence_ids)
                    )
                )
            lines.append("")

    # --- Grounding Diagnostics ---
    lines.append("## Grounding Diagnostics")
    lines.append("")
    if grounding_report.diagnostics:
        for d in grounding_report.diagnostics:
            lines.append(
                "- **{}** [{}]: {}".format(
                    d.issue_type, d.severity, d.message or ""
                )
            )
            if d.recommended_action:
                lines.append(
                    "  - Action: {}".format(d.recommended_action)
                )
    else:
        lines.append("None.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mermaid rendering
# ---------------------------------------------------------------------------


def _sanitize_mermaid_id(node_id: str) -> str:
    """Sanitize a node ID for Mermaid syntax (no colons / hyphens / dots)."""
    return (
        node_id.replace(":", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def _render_mermaid(graph: ConceptTraceGraph) -> str:
    """Render concept trace as Mermaid diagram."""
    lines: list[str] = ["graph TD"]

    for node in graph.nodes:
        safe_id = _sanitize_mermaid_id(node.node_id)
        lines.append('    {}["{}"]'.format(safe_id, node.label))

    lines.append("")

    for edge in graph.edges:
        safe_from = _sanitize_mermaid_id(edge.from_node_id)
        safe_to = _sanitize_mermaid_id(edge.to_node_id)
        lines.append(
            '    {} -->|"{}"| {}'.format(
                safe_from, edge.label, safe_to
            )
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
    """Write a dict as pretty-printed JSON."""
    _ = path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
