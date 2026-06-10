"""Semantic Pipeline View builder (T039/T040).

Builds a lane-based pipeline visualization artifact from project understanding
artifacts.  Each lane corresponds to a design stage (L5, L6, RTL, Tests).
Nodes are placed into their primary lane; edges crossing lanes are extracted
as ``cross_stage_edges`` for pipeline-style rendering.

No LLM, no external API, read-only on target projects.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


PIPELINE_SCHEMA_VERSION = "semantic-pipeline-view-0.1"

_LANE_LABELS: dict[str, str] = {
    "L5_fixedpoint": "L5 Fixed-Point Python Model",
    "L6_resource_opt": "L6 Resource-Optimized Python Model",
    "RTL": "RTL Implementation",
    "tests": "Tests & Verification",
}

_LANE_ORDER = ["L5_fixedpoint", "L6_resource_opt", "RTL", "tests"]


def build_semantic_pipeline_view(
    project_root: Path,
    project_graph: dict[str, Any],
    project_index: dict[str, Any],
    semantic_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build lane-based semantic pipeline view.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    project_graph : dict
        The project_understanding_graph.json content.
    project_index : dict
        The project_understanding_index.json content.
    semantic_summary : dict | None
        Optional project_semantic_summary.json content for enrichment.

    Returns
    -------
    dict
        Semantic pipeline view matching schema_version
        ``semantic-pipeline-view-0.1``.
    """
    project_id = project_graph.get("project_id") or project_root.name or "project"
    nodes = project_graph.get("nodes", [])
    edges = project_graph.get("edges", [])
    evidence_index = project_index.get("evidence_index", {})
    evidence_chain = project_index.get("evidence_chain", {})
    concept_index = project_index.get("concept_index", {})

    # ------------------------------------------------------------------
    # 1. Initialise lanes
    # ------------------------------------------------------------------
    lanes: dict[str, dict[str, Any]] = {
        lane_id: {
            "lane_id": lane_id,
            "label": _LANE_LABELS[lane_id],
            "stage_id": lane_id,
            "nodes": [],
            "edges": [],
        }
        for lane_id in _LANE_ORDER
    }

    # Track which lane each node_id belongs to
    node_lane: dict[str, str] = {}
    node_seen: set[str] = set()

    # ------------------------------------------------------------------
    # 2. Place graph nodes into primary lanes
    # ------------------------------------------------------------------
    for node in nodes:
        nid = node.get("node_id", "")
        kind = node.get("kind", "")
        if not nid:
            continue

        if kind == "project":
            # Project node is not placed in any lane (top-level)
            continue

        if kind == "concept":
            concept = node.get("label", "")
            primary, stages = _determine_concept_lanes(
                concept, evidence_chain, concept_index
            )
            node_lane[nid] = primary
            lanes[primary]["nodes"].append({
                "node_id": nid,
                "label": node.get("label", ""),
                "kind": "concept",
                "confidence": node.get("confidence", "unknown"),
                "stages_present": sorted(stages),
                "primary_stage": primary,
            })
            node_seen.add(nid)
            continue

        if kind.startswith("rtl_"):
            node_lane[nid] = "RTL"
            lanes["RTL"]["nodes"].append({
                "node_id": nid,
                "label": node.get("label", ""),
                "kind": kind,
                "confidence": node.get("confidence", "inferred"),
                "file_path": node.get("file_path", ""),
            })
            node_seen.add(nid)
            continue

        if kind == "mapping_claim":
            node_lane[nid] = "RTL"
            lanes["RTL"]["nodes"].append({
                "node_id": nid,
                "label": node.get("label", ""),
                "kind": "mapping_claim",
                "confidence": node.get("confidence", "unknown"),
                "concept": node.get("concept", ""),
            })
            node_seen.add(nid)
            continue

    # ------------------------------------------------------------------
    # 3. Place evidence items into lanes
    # ------------------------------------------------------------------
    for eid, ev in evidence_index.items():
        if eid in node_seen:
            continue
        fp = ev.get("file_path", "")
        stage = _detect_stage_from_path(fp)
        if stage and stage in lanes:
            node_lane[eid] = stage
            lanes[stage]["nodes"].append({
                "node_id": eid,
                "label": ev.get("symbol", "") or eid,
                "kind": "evidence",
                "stage": stage,
                "source_type": ev.get("source_type", ""),
                "strength": ev.get("strength", ""),
                "file_path": fp,
                "concept": ev.get("concept", ""),
            })
            node_seen.add(eid)

    # ------------------------------------------------------------------
    # 4. Classify edges: lane-internal vs cross-stage
    # ------------------------------------------------------------------
    cross_stage_edges: list[dict[str, Any]] = []

    for edge in edges:
        eid = edge.get("edge_id", "")
        from_id = edge.get("from_node_id", "")
        to_id = edge.get("to_node_id", "")
        from_lane = node_lane.get(from_id)
        to_lane = node_lane.get(to_id)

        if from_lane and to_lane and from_lane != to_lane:
            cross_stage_edges.append({
                "edge_id": eid,
                "from_lane": from_lane,
                "to_lane": to_lane,
                "from_node_id": from_id,
                "to_node_id": to_id,
                "edge_type": edge.get("edge_type", ""),
                "confidence": edge.get("confidence", "unknown"),
                "notes": edge.get("notes", ""),
            })
        elif from_lane and from_lane == to_lane:
            lanes[from_lane]["edges"].append({
                "edge_id": eid,
                "from_node_id": from_id,
                "to_node_id": to_id,
                "edge_type": edge.get("edge_type", ""),
                "confidence": edge.get("confidence", "unknown"),
            })

    # ------------------------------------------------------------------
    # 5. Pipeline summary
    # ------------------------------------------------------------------
    concept_count_per_stage: dict[str, int] = {}
    evidence_count_per_stage: dict[str, int] = {}
    for lane_id in _LANE_ORDER:
        lane_nodes = lanes[lane_id]["nodes"]
        concept_count_per_stage[lane_id] = sum(
            1 for n in lane_nodes if n["kind"] == "concept"
        )
        evidence_count_per_stage[lane_id] = sum(
            1 for n in lane_nodes if n["kind"] == "evidence"
        )

    # Concepts with full pipeline (L5 + L6 + RTL)
    concepts_with_full_pipeline: list[str] = []
    concepts_with_gaps: list[str] = []
    for concept, chain in evidence_chain.items():
        stages = set()
        for ev in chain.get("l5_l6_evidence", []):
            fp = ev.get("file_path", "")
            if "L5_fixedpoint" in fp:
                stages.add("L5_fixedpoint")
            elif "L6_resource_opt" in fp:
                stages.add("L6_resource_opt")
        if chain.get("rtl_evidence"):
            stages.add("RTL")
        if chain.get("test_evidence"):
            stages.add("tests")

        if {"L5_fixedpoint", "L6_resource_opt", "RTL"} <= stages:
            concepts_with_full_pipeline.append(concept)
        elif len(stages) < 2:
            concepts_with_gaps.append(concept)

    # Cross-stage claim / realize edges
    cross_claim_count = sum(
        1 for e in cross_stage_edges
        if e["edge_type"] in ("has_claim", "realizes")
    )

    # ------------------------------------------------------------------
    # 6. Uncertainty flags
    # ------------------------------------------------------------------
    uncertainty_flags: list[dict[str, Any]] = []
    for concept, chain in evidence_chain.items():
        conf_exp = chain.get("confidence_explanation", "")
        if "Low" in conf_exp or "No confidence" in conf_exp:
            uncertainty_flags.append({
                "concept": concept,
                "flag": "low_confidence",
                "reason": conf_exp,
            })
        has_l5l6 = bool(chain.get("l5_l6_evidence"))
        has_rtl = bool(chain.get("rtl_evidence"))
        if not has_l5l6 and not has_rtl:
            uncertainty_flags.append({
                "concept": concept,
                "flag": "no_evidence",
                "reason": "No L5/L6 or RTL evidence found",
            })
        elif not has_l5l6:
            uncertainty_flags.append({
                "concept": concept,
                "flag": "missing_l5_l6",
                "reason": "No L5/L6 evidence",
            })
        elif not has_rtl:
            uncertainty_flags.append({
                "concept": concept,
                "flag": "missing_rtl",
                "reason": "No RTL evidence",
            })

    # ------------------------------------------------------------------
    # 7. Enrich from semantic summary if available
    # ------------------------------------------------------------------
    l5_l6_to_rtl_summary: dict[str, Any] | None = None
    if semantic_summary:
        l5rtl = semantic_summary.get("l5_l6_to_rtl_summary")
        if l5rtl:
            l5_l6_to_rtl_summary = {
                "concepts_with_cross_stage_mapping": l5rtl.get("summary", {}).get(
                    "concepts_with_cross_stage_mapping", 0
                ),
                "concepts_missing_l5_l6": l5rtl.get("summary", {}).get(
                    "concepts_missing_l5_l6", 0
                ),
                "concepts_missing_rtl": l5rtl.get("summary", {}).get(
                    "concepts_missing_rtl", 0
                ),
                "inferred_only_mappings": l5rtl.get("summary", {}).get(
                    "inferred_only_mappings", 0
                ),
            }

    # ------------------------------------------------------------------
    # 8. Assemble result
    # ------------------------------------------------------------------
    return {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "project_id": project_id,
        "lanes": [lanes[lid] for lid in _LANE_ORDER],
        "cross_stage_edges": cross_stage_edges,
        "pipeline_summary": {
            "concept_count_per_stage": concept_count_per_stage,
            "evidence_count_per_stage": evidence_count_per_stage,
            "cross_stage_claim_count": cross_claim_count,
            "dataflow_edge_count": len(cross_stage_edges),
            "concepts_with_full_pipeline": concepts_with_full_pipeline,
            "concepts_with_gaps": concepts_with_gaps,
            "total_nodes": sum(len(l["nodes"]) for l in lanes.values()),
            "total_cross_stage_edges": len(cross_stage_edges),
            "l5_l6_to_rtl_summary": l5_l6_to_rtl_summary,
        },
        "uncertainty_flags": uncertainty_flags,
        "source_provenance": {
            "generated_from": [
                "project_understanding_graph.json",
                "project_understanding_index.json",
            ] + (["project_semantic_summary.json"] if semantic_summary else []),
            "generation_timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "generator": "fpga_devmind.semantic_pipeline_view",
        },
    }


def _detect_stage_from_path(file_path: str) -> str | None:
    """Determine which pipeline stage a file path belongs to."""
    fp = file_path.lower()
    if "l5_fixedpoint" in fp:
        return "L5_fixedpoint"
    if "l6_resource_opt" in fp:
        return "L6_resource_opt"
    if "/rtl/" in fp or fp.endswith(".v") or fp.endswith(".sv"):
        return "RTL"
    if "test" in fp:
        return "tests"
    return None


def _determine_concept_lanes(
    concept: str,
    evidence_chain: dict[str, Any],
    concept_index: dict[str, Any],
) -> tuple[str, set[str]]:
    """Determine primary lane and all present stages for a concept.

    Returns
    -------
    tuple[str, set[str]]
        (primary_lane, all_stages_present)
    """
    stages: set[str] = set()
    chain = evidence_chain.get(concept, {})

    for ev in chain.get("l5_l6_evidence", []):
        fp = ev.get("file_path", "")
        if "L5_fixedpoint" in fp:
            stages.add("L5_fixedpoint")
        elif "L6_resource_opt" in fp:
            stages.add("L6_resource_opt")

    if chain.get("rtl_evidence"):
        stages.add("RTL")
    if chain.get("test_evidence"):
        stages.add("tests")

    # Fallback to concept_index if evidence_chain is empty
    if not stages:
        ci = concept_index.get(concept, {})
        if ci.get("l5_count", 0) > 0:
            stages.add("L5_fixedpoint")
        if ci.get("l6_count", 0) > 0:
            stages.add("L6_resource_opt")
        if ci.get("rtl_objects", 0) > 0:
            stages.add("RTL")
        if ci.get("test_count", 0) > 0:
            stages.add("tests")

    # Determine primary lane: prefer L6 > L5 > RTL > tests
    if "L6_resource_opt" in stages:
        return "L6_resource_opt", stages
    if "L5_fixedpoint" in stages:
        return "L5_fixedpoint", stages
    if "RTL" in stages:
        return "RTL", stages
    if "tests" in stages:
        return "tests", stages
    return "L6_resource_opt", stages
