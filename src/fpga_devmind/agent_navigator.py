"""Deterministic Agent Navigation Index builder (T041).

Builds a navigation-friendly index from all existing project understanding
artifacts.  No LLM, no external API, read-only on artifacts.

The output ``agent_navigation_index.json`` serves as a first-class artifact
for deterministic Agent Q&A routing, providing:

- entrypoints — top-level entry points for project understanding
- question_routes — intent-to-artifact mappings for common questions
- concept_routes — per-concept navigation data with evidence links
- edge_routes — per-cross-stage-edge navigation data with reasons
- quality_status — golden spec / eval metrics
- limitations — known gaps and warnings
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


NAV_SCHEMA_VERSION = "agent-navigation-index-0.1"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_agent_navigation_index(
    project_root: Path,
    project_graph: dict[str, Any],
    project_index: dict[str, Any],
    semantic_summary: dict[str, Any] | None,
    pipeline_view: dict[str, Any] | None,
    eval_result: dict[str, Any] | None,
    concept_candidates: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build deterministic agent navigation index.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    project_graph : dict
        The project_understanding_graph.json content.
    project_index : dict
        The project_understanding_index.json content.
    semantic_summary : dict | None
        The project_semantic_summary.json content.
    pipeline_view : dict | None
        The semantic_pipeline_view.json content.
    eval_result : dict | None
        The discovery_eval_result.json content.
    concept_candidates : list[dict] | None
        The concept_candidates.json content.

    Returns
    -------
    dict
        Agent navigation index matching schema_version
        ``agent-navigation-index-0.1``.
    """
    project_id = project_graph.get("project_id") or project_root.name or "project"
    concepts = [n for n in project_graph.get("nodes", []) if n.get("kind") == "concept"]
    edges = project_graph.get("edges", [])
    evidence_index = project_index.get("evidence_index", {})
    evidence_chain = project_index.get("evidence_chain", {})

    # ------------------------------------------------------------------
    # 1. Entrypoints
    # ------------------------------------------------------------------
    entrypoints = _build_entrypoints(
        semantic_summary is not None,
        pipeline_view is not None,
        eval_result is not None,
    )

    # ------------------------------------------------------------------
    # 2. Question routes
    # ------------------------------------------------------------------
    question_routes = _build_question_routes()

    # ------------------------------------------------------------------
    # 3. Concept routes
    # ------------------------------------------------------------------
    concept_routes = _build_concept_routes(
        concepts, evidence_chain, evidence_index, semantic_summary
    )

    # ------------------------------------------------------------------
    # 4. Edge routes (cross-stage edges from pipeline view)
    # ------------------------------------------------------------------
    edge_routes = _build_edge_routes(pipeline_view)

    # ------------------------------------------------------------------
    # 5. Quality status
    # ------------------------------------------------------------------
    quality_status = _build_quality_status(eval_result)

    # ------------------------------------------------------------------
    # 6. Limitations
    # ------------------------------------------------------------------
    limitations = _build_limitations(
        semantic_summary, pipeline_view, eval_result, concept_candidates
    )

    # ------------------------------------------------------------------
    # 7. Assemble
    # ------------------------------------------------------------------
    return {
        "schema_version": NAV_SCHEMA_VERSION,
        "project_id": project_id,
        "entrypoints": entrypoints,
        "question_routes": question_routes,
        "concept_routes": concept_routes,
        "edge_routes": edge_routes,
        "quality_status": quality_status,
        "limitations": limitations,
        "source_provenance": {
            "summary_generated_from": _collect_source_artifacts(
                semantic_summary, pipeline_view, eval_result
            ),
            "generation_timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "generator": "fpga_devmind.agent_navigator",
        },
    }


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------


def _build_entrypoints(
    has_semantic_summary: bool,
    has_pipeline_view: bool,
    has_eval: bool,
) -> list[dict[str, Any]]:
    """Build navigation entrypoints based on available artifacts."""
    eps: list[dict[str, Any]] = []

    eps.append({
        "id": "overview",
        "label": "项目整体理解",
        "artifact": "project_semantic_summary.json",
        "available": has_semantic_summary,
        "description": "Top-level purpose, core concepts, evidence quality summary",
    })

    eps.append({
        "id": "pipeline",
        "label": "Pipeline / Dataflow",
        "artifact": "semantic_pipeline_view.json",
        "available": has_pipeline_view,
        "description": "Stage lanes (L5→L6→RTL→Tests), cross-stage edges, inferred relations",
    })

    eps.append({
        "id": "graph",
        "label": "项目理解图",
        "artifact": "project_understanding_graph.json",
        "available": True,
        "description": "Project→Concept→Claim→RTL node graph with edges",
    })

    eps.append({
        "id": "evidence",
        "label": "证据索引",
        "artifact": "project_understanding_index.json",
        "available": True,
        "description": "Per-concept evidence chain, concept index, claim index",
    })

    eps.append({
        "id": "quality",
        "label": "质量评估",
        "artifact": "discovery_eval_result.json",
        "available": has_eval,
        "description": "Golden spec precision/recall, excluded terms, matched/missed concepts",
    })

    return eps


def _build_question_routes() -> list[dict[str, Any]]:
    """Build deterministic question-to-artifact routes."""
    return [
        {
            "intent": "project_overview",
            "patterns": ["整体实现", "项目目的", "这个项目做什么", "概述"],
            "primary_artifacts": ["project_semantic_summary.json"],
            "fallback_artifacts": ["project_understanding_graph.json"],
        },
        {
            "intent": "pipeline_stages",
            "patterns": ["pipeline", "阶段", "stage", "dataflow", "数据流"],
            "primary_artifacts": ["semantic_pipeline_view.json"],
            "fallback_artifacts": ["project_semantic_summary.json"],
        },
        {
            "intent": "concept_mapping",
            "patterns": ["映射", "对应", "怎么实现", "L5到RTL"],
            "primary_artifacts": ["project_understanding_graph.json", "project_understanding_index.json"],
            "fallback_artifacts": ["semantic_pipeline_view.json"],
        },
        {
            "intent": "missing_evidence",
            "patterns": ["缺失", "missing", "缺少", "没有"],
            "primary_artifacts": ["semantic_pipeline_view.json", "project_understanding_index.json"],
            "fallback_artifacts": ["project_semantic_summary.json"],
        },
        {
            "intent": "quality_metrics",
            "patterns": ["精确率", "召回率", "precision", "recall", "golden", "评估"],
            "primary_artifacts": ["discovery_eval_result.json"],
            "fallback_artifacts": [],
        },
        {
            "intent": "noise_concepts",
            "patterns": ["噪声", "噪声概念", "假阳性", "unexpected", "filtered"],
            "primary_artifacts": ["discovery_eval_result.json", "concept_candidates.json"],
            "fallback_artifacts": [],
        },
        {
            "intent": "navigation_help",
            "patterns": ["从哪里开始", "推荐", "先看", "下一步", "点哪里"],
            "primary_artifacts": ["agent_navigation_index.json"],
            "fallback_artifacts": ["project_semantic_summary.json"],
        },
        {
            "intent": "edge_evidence",
            "patterns": ["这条边", "为什么存在", "edge", "证据"],
            "primary_artifacts": ["semantic_pipeline_view.json"],
            "fallback_artifacts": ["project_understanding_index.json"],
        },
        {
            "intent": "confidence_distribution",
            "patterns": ["supported", "inferred", "置信度", "哪些结论是"],
            "primary_artifacts": ["project_understanding_graph.json", "project_semantic_summary.json"],
            "fallback_artifacts": ["semantic_pipeline_view.json"],
        },
    ]


def _build_concept_routes(
    concepts: list[dict[str, Any]],
    evidence_chain: dict[str, Any],
    evidence_index: dict[str, Any],
    semantic_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Build per-concept navigation routes."""
    routes: list[dict[str, Any]] = []

    # Build mapping from semantic_summary if available
    summary_mappings: dict[str, dict[str, Any]] = {}
    if semantic_summary:
        for m in semantic_summary.get("l5_l6_to_rtl_summary", {}).get("concept_mappings", []):
            summary_mappings[m.get("concept", "")] = m

    for c in concepts:
        label = c.get("label", "")
        chain = evidence_chain.get(label, {})

        # Collect evidence IDs
        ev_ids: list[str] = []
        for ev in chain.get("l5_l6_evidence", []):
            eid = ev.get("evidence_id", "")
            if eid:
                ev_ids.append(eid)
        for ev in chain.get("rtl_evidence", []):
            eid = ev.get("evidence_id", "")
            if eid:
                ev_ids.append(eid)
        for ev in chain.get("test_evidence", []):
            eid = ev.get("evidence_id", "")
            if eid:
                ev_ids.append(eid)

        # Collect source files
        src_files: list[str] = []
        for ev in chain.get("l5_l6_evidence", []):
            fp = ev.get("file_path", "")
            if fp and fp not in src_files:
                src_files.append(fp)
        for ev in chain.get("rtl_evidence", []):
            fp = ev.get("file_path", "")
            if fp and fp not in src_files:
                src_files.append(fp)

        # Confidence from chain or concept node
        confidence = c.get("confidence", "unknown")
        if chain.get("confidence_explanation"):
            if "High" in chain["confidence_explanation"]:
                confidence = "supported"
            elif "Low" in chain["confidence_explanation"]:
                confidence = "inferred"

        # Known gaps
        gaps: list[str] = []
        if not chain.get("l5_l6_evidence"):
            gaps.append("missing_l5_l6")
        if not chain.get("rtl_evidence"):
            gaps.append("missing_rtl")
        if not chain.get("test_evidence"):
            gaps.append("missing_test")

        # Semantic summary enrichment
        mapping = summary_mappings.get(label)
        mapping_confidence = mapping.get("mapping_confidence", confidence) if mapping else confidence
        mapping_reason = mapping.get("mapping_reason", "") if mapping else ""

        routes.append({
            "concept": label,
            "node_id": c.get("node_id", ""),
            "confidence": confidence,
            "mapping_confidence": mapping_confidence,
            "mapping_reason": mapping_reason,
            "evidence_ids": ev_ids,
            "source_files": src_files,
            "known_gaps": gaps,
            "has_l5_l6": bool(chain.get("l5_l6_evidence")),
            "has_rtl": bool(chain.get("rtl_evidence")),
            "has_test": bool(chain.get("test_evidence")),
            "claims": [cl.get("claim_id", "") for cl in chain.get("claims", [])],
        })

    return routes


def _build_edge_routes(
    pipeline_view: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Build per-edge navigation routes from pipeline view cross-stage edges."""
    if not pipeline_view:
        return []

    routes: list[dict[str, Any]] = []
    for e in pipeline_view.get("cross_stage_edges", []):
        routes.append({
            "edge_id": e.get("edge_id", ""),
            "edge_type": e.get("edge_type", ""),
            "from_lane": e.get("from_lane", ""),
            "to_lane": e.get("to_lane", ""),
            "from_node_id": e.get("from_node_id", ""),
            "to_node_id": e.get("to_node_id", ""),
            "confidence": e.get("confidence", "unknown"),
            "reason": e.get("reason", ""),
            "evidence_ids": e.get("evidence_ids", []),
            "source_files": e.get("source_files", []),
        })
    return routes


def _build_quality_status(
    eval_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build quality status from eval result."""
    if not eval_result:
        return {
            "golden_spec_used": False,
            "selected_precision_like": 0.0,
            "selected_recall_like": 0.0,
            "excluded_terms_selected": [],
            "matched_core_count": 0,
            "missed_core_count": 0,
            "matched_secondary_count": 0,
        }

    return {
        "golden_spec_used": True,
        "selected_precision_like": eval_result.get("selected_precision_like", 0.0),
        "selected_recall_like": eval_result.get("selected_recall_like", 0.0),
        "excluded_terms_selected": eval_result.get("excluded_terms_selected", []),
        "matched_core_count": len(eval_result.get("matched_core", [])),
        "missed_core_count": len(eval_result.get("missed_core", [])),
        "matched_secondary_count": len(eval_result.get("matched_secondary", [])),
    }


def _build_limitations(
    semantic_summary: dict[str, Any] | None,
    pipeline_view: dict[str, Any] | None,
    eval_result: dict[str, Any] | None,
    concept_candidates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Build known limitations list."""
    lims: list[dict[str, Any]] = []

    if not semantic_summary:
        lims.append({
            "category": "missing_artifact",
            "item": "semantic_summary",
            "reason": "No semantic summary available — navigation limited to raw graph/index.",
        })

    if not pipeline_view:
        lims.append({
            "category": "missing_artifact",
            "item": "pipeline_view",
            "reason": "No pipeline view available — cross-stage navigation unavailable.",
        })

    if not eval_result:
        lims.append({
            "category": "missing_artifact",
            "item": "eval_result",
            "reason": "No golden spec evaluation — quality metrics unavailable.",
        })
    elif eval_result.get("excluded_terms_selected"):
        terms = eval_result["excluded_terms_selected"]
        lims.append({
            "category": "quality_warning",
            "item": "excluded_terms_in_selected",
            "reason": f"{len(terms)} excluded/generic terms leaked into selected concepts: {terms}",
        })

    if semantic_summary:
        unc = semantic_summary.get("uncertainty_summary", {})
        if unc.get("naming_only_links"):
            lims.append({
                "category": "inference_quality",
                "item": "naming_only_mappings",
                "reason": f"{len(unc['naming_only_links'])} concepts mapped by naming only (weak evidence).",
            })
        if unc.get("missing_rtl"):
            lims.append({
                "category": "coverage_gap",
                "item": "missing_rtl",
                "reason": f"{len(unc['missing_rtl'])} concepts lack RTL evidence.",
            })

    if pipeline_view:
        ps = pipeline_view.get("pipeline_summary", {})
        if ps.get("concepts_with_gaps"):
            lims.append({
                "category": "coverage_gap",
                "item": "pipeline_gaps",
                "reason": f"{len(ps['concepts_with_gaps'])} concepts have incomplete cross-stage evidence.",
            })

    return lims


def _collect_source_artifacts(
    semantic_summary: dict[str, Any] | None,
    pipeline_view: dict[str, Any] | None,
    eval_result: dict[str, Any] | None,
) -> list[str]:
    """List source artifact files used to build this index."""
    sources = [
        "project_understanding_graph.json",
        "project_understanding_index.json",
    ]
    if semantic_summary:
        sources.append("project_semantic_summary.json")
    if pipeline_view:
        sources.append("semantic_pipeline_view.json")
    if eval_result:
        sources.append("discovery_eval_result.json")
    return sources
