"""Project-level multi-concept trace CLI (T024).

Chains multiple p1b-trace-concept runs and aggregates them into a
project-level understanding graph.

Does not call LLM, does not modify target projects, does not run Vivado.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_cli import run_p1b_trace_concept
from fpga_devmind.safety import ensure_safe_output_dir


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

PROJECT_SCHEMA_VERSION = "project-understanding-0.1"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_p1b_trace_project(
    project_root: Path,
    concepts: list[str],
    out_dir: Path,
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Run project-level concept trace for multiple concepts.

    For each concept, runs the full P1b pipeline in a temporary directory,
    then aggregates all results into a project understanding graph.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    concepts : list[str]
        List of concept names to trace (e.g. ``["peak_idx", "cfo"]``).
    out_dir : Path
        Output directory for project artifacts (must be a safe temp path).

    Returns
    -------
    dict[str, Any]
        Run metadata including status and artifact paths.

    Raises
    ------
    ValueError
        If *out_dir* is not a safe temp path, or if *concepts* is empty.
    """
    if not concepts:
        raise ValueError("At least one concept must be specified (--concepts).")

    safe_out = ensure_safe_output_dir(out_dir, label="project trace output")
    safe_out.mkdir(parents=True, exist_ok=True)
    t_start = time.monotonic()

    # Run per-concept traces in temp dirs, collecting results.
    concept_results: list[_ConceptTraceResult] = []
    diagnostics: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    for concept in concepts:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                metadata = run_p1b_trace_concept(project_root, concept, tmp_path)
                graph_path = tmp_path / "concept_trace_graph.json"
                index_path = tmp_path / "concept_trace_index.json"
                grounding_path = tmp_path / "grounding_report.json"

                graph: dict[str, Any] | None = None  # pyright: ignore[reportExplicitAny]
                if graph_path.is_file():
                    graph = json.loads(graph_path.read_text(encoding="utf-8"))

                index: dict[str, Any] | None = None  # pyright: ignore[reportExplicitAny]
                if index_path.is_file():
                    index = json.loads(index_path.read_text(encoding="utf-8"))

                grounding: dict[str, Any] | None = None  # pyright: ignore[reportExplicitAny]
                if grounding_path.is_file():
                    grounding = json.loads(grounding_path.read_text(encoding="utf-8"))

                concept_results.append(
                    _ConceptTraceResult(
                        concept=concept,
                        metadata=metadata,
                        graph=graph,
                        index=index,
                        grounding=grounding,
                        status=metadata.get("status", "ok"),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                diagnostics.append(
                    {
                        "severity": "error",
                        "concept": concept,
                        "message": str(exc),
                        "code": "CONCEPT_TRACE_FAILED",
                    }
                )
                concept_results.append(
                    _ConceptTraceResult(
                        concept=concept,
                        metadata={},
                        graph=None,
                        index=None,
                        grounding=None,
                        status="failed",
                    )
                )

    # Build project-level artifacts.
    project_graph = _build_project_graph(project_root, concept_results)
    project_index = _build_project_index(project_root, concept_results)
    project_md = _render_project_markdown(project_root, concept_results, diagnostics)

    # Write artifacts.
    _write_json(safe_out / "project_understanding_graph.json", project_graph)
    _write_json(safe_out / "project_understanding_index.json", project_index)
    _ = (safe_out / "project_understanding.md").write_text(
        project_md, encoding="utf-8"
    )

    # Mermaid fallback.
    mmd = _render_project_mermaid(project_graph)
    _ = (safe_out / "project_understanding.mmd").write_text(mmd, encoding="utf-8")

    # Metadata.
    elapsed = time.monotonic() - t_start
    total_claims = sum(
        len(r.graph.get("mapping_claims", [])) if r.graph else 0
        for r in concept_results
    )
    total_evidence = sum(
        len(r.graph.get("evidence_items", [])) if r.graph else 0
        for r in concept_results
    )
    failed_concepts = [r.concept for r in concept_results if r.status != "ok"]

    metadata: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "schema_version": "p1b-project-run-metadata-0.1",
        "command": "p1b-trace-project",
        "project_root": str(project_root),
        "output_dir": str(safe_out),
        "concepts_requested": concepts,
        "concepts_processed": [r.concept for r in concept_results],
        "concepts_failed": failed_concepts,
        "elapsed_seconds": round(elapsed, 3),
        "status": "ok" if not failed_concepts else "partial",
        "mapping_claims": total_claims,
        "evidence_items": total_evidence,
        "diagnostics": len(diagnostics),
        "artifacts": [
            "project_understanding_graph.json",
            "project_understanding_index.json",
            "project_understanding.md",
            "project_understanding.mmd",
            "run_metadata.json",
        ],
    }
    _write_json(safe_out / "run_metadata.json", metadata)

    return metadata


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------


class _ConceptTraceResult:
    """Result of a single concept trace (in-memory)."""

    def __init__(
        self,
        concept: str,
        metadata: dict[str, Any],  # pyright: ignore[reportExplicitAny]
        graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
        index: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
        grounding: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
        status: str,
    ) -> None:
        self.concept = concept
        self.metadata = metadata
        self.graph = graph
        self.index = index
        self.grounding = grounding
        self.status = status


# ---------------------------------------------------------------------------
# Project graph builder
# ---------------------------------------------------------------------------


def _build_project_graph(
    project_root: Path,
    results: list[_ConceptTraceResult],
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Build project understanding graph from per-concept traces."""
    nodes: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    edges: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    # Project node.
    project_id = project_root.name or "project"
    nodes.append(
        {
            "node_id": "PUG_PROJECT",
            "label": project_id,
            "kind": "project",
            "stage": "",
            "confidence": "supported",
        }
    )

    # Track deduplicated RTL objects across concepts.
    rtl_node_map: dict[tuple[str, str, str], str] = {}  # (file_path, name, object_type) -> node_id

    for result in results:
        concept = result.concept
        graph = result.graph
        if graph is None:
            # Unknown placeholder node.
            cnode_id = _concept_node_id(concept)
            nodes.append(
                {
                    "node_id": cnode_id,
                    "label": concept,
                    "kind": "concept",
                    "stage": "",
                    "confidence": "unknown",
                    "notes": "Concept trace failed or produced no graph.",
                }
            )
            edges.append(
                {
                    "edge_id": "E_PROJECT_{}".format(concept),
                    "from_node_id": "PUG_PROJECT",
                    "to_node_id": cnode_id,
                    "edge_type": "contains",
                    "confidence": "unknown",
                }
            )
            continue

        cnode_id = _concept_node_id(concept)
        concept_conf = _concept_confidence(graph)

        # Concept node.
        nodes.append(
            {
                "node_id": cnode_id,
                "label": concept,
                "kind": "concept",
                "stage": "",
                "confidence": concept_conf,
            }
        )

        # Project -> Concept edge.
        edges.append(
            {
                "edge_id": "E_PROJECT_{}".format(concept),
                "from_node_id": "PUG_PROJECT",
                "to_node_id": cnode_id,
                "edge_type": "contains",
                "confidence": concept_conf,
            }
        )

        # Claim nodes and Concept -> Claim edges.
        for claim in graph.get("mapping_claims", []):
            cid = claim.get("claim_id", "")
            if not cid:
                continue
            claim_node_id = "PUG_CLAIM_{}_{}".format(concept, cid)
            claim_conf = claim.get("confidence", "unknown")
            nodes.append(
                {
                    "node_id": claim_node_id,
                    "label": cid,
                    "kind": "mapping_claim",
                    "stage": "",
                    "confidence": claim_conf,
                    "concept": concept,
                }
            )
            edges.append(
                {
                    "edge_id": "E_{}_{}".format(cnode_id, claim_node_id),
                    "from_node_id": cnode_id,
                    "to_node_id": claim_node_id,
                    "edge_type": "has_claim",
                    "confidence": claim_conf,
                }
            )

            # Claim -> RTL edges (deduplicate RTL objects).
            for rtl_node in graph.get("nodes", []):
                if rtl_node.get("kind", "").startswith("rtl_"):
                    rtl_key = _rtl_key(rtl_node)
                    if rtl_key in rtl_node_map:
                        rtl_id = rtl_node_map[rtl_key]
                    else:
                        rtl_id = "PUG_RTL_{}_{}".format(
                            concept, rtl_node.get("node_id", "")
                        )
                        rtl_node_map[rtl_key] = rtl_id
                        nodes.append(
                            {
                                "node_id": rtl_id,
                                "label": rtl_node.get("label", ""),
                                "kind": rtl_node.get("kind", "rtl_module"),
                                "stage": "RTL",
                                "file_path": rtl_node.get("file_path", ""),
                                "confidence": rtl_node.get("confidence", "inferred"),
                            }
                        )
                    edges.append(
                        {
                            "edge_id": "E_{}_{}".format(claim_node_id, rtl_id),
                            "from_node_id": claim_node_id,
                            "to_node_id": rtl_id,
                            "edge_type": "realizes",
                            "confidence": claim_conf,
                        }
                    )

    # Structural edges: shared files and shared RTL objects between concepts.
    shared_edges = _build_shared_edges(results, rtl_node_map)
    edges.extend(shared_edges)

    # Collect all diagnostics and uncertainty notes.
    all_diagnostics: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    all_uncertainty: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for result in results:
        if result.graph:
            for d in result.graph.get("grounding_diagnostics", []):
                if isinstance(d, dict):
                    d = dict(d)
                    d["concept"] = result.concept
                    all_diagnostics.append(d)
            for u in result.graph.get("uncertainty_notes", []):
                if isinstance(u, dict):
                    u = dict(u)
                    u["concept"] = result.concept
                    all_uncertainty.append(u)

    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_id": project_id,
        "project_root": str(project_root),
        "concepts": [r.concept for r in results],
        "nodes": nodes,
        "edges": edges,
        "grounding_diagnostics": all_diagnostics,
        "uncertainty_notes": all_uncertainty,
    }


def _build_project_index(
    project_root: Path,
    results: list[_ConceptTraceResult],
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Build project understanding index from per-concept traces."""
    concept_index: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
    claim_index: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
    evidence_index: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
    node_index: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
    file_index: dict[str, list[str]] = {}
    rtl_object_index: dict[str, list[str]] = {}

    for result in results:
        concept = result.concept
        graph = result.graph
        if graph is None:
            concept_index[concept] = {"status": "failed"}
            continue

        claims_count = len(graph.get("mapping_claims", []))
        evidence_count = len(graph.get("evidence_items", []))
        rtl_count = sum(
            1 for n in graph.get("nodes", []) if n.get("kind", "").startswith("rtl_")
        )

        concept_index[concept] = {
            "status": "ok",
            "claims": claims_count,
            "evidence": evidence_count,
            "rtl_objects": rtl_count,
        }

        # Claim index.
        for claim in graph.get("mapping_claims", []):
            cid = claim.get("claim_id", "")
            if cid:
                scoped_id = "PUG_CLAIM_{}_{}".format(concept, cid)
                claim_index[scoped_id] = {
                    "concept": concept,
                    "confidence": claim.get("confidence", ""),
                    "bridge_kind": claim.get("bridge_kind", ""),
                }

        # Evidence index.
        for item in graph.get("evidence_items", []):
            eid = item.get("evidence_id", "")
            if eid:
                evidence_index[eid] = {
                    "concept": concept,
                    "source_type": item.get("source_type", ""),
                    "file_path": item.get("file_path", ""),
                    "symbol": item.get("symbol", ""),
                    "strength": item.get("evidence_strength", ""),
                }
                fp = item.get("file_path", "")
                if fp:
                    file_index.setdefault(fp, []).append(concept)

        # Node index.
        for node in graph.get("nodes", []):
            nid = node.get("node_id", "")
            if nid:
                node_index[nid] = {
                    "concept": concept,
                    "kind": node.get("kind", ""),
                    "file_path": node.get("file_path", ""),
                }
                if node.get("kind", "").startswith("rtl_"):
                    name = node.get("label", "")
                    rtl_object_index.setdefault(name, []).append(concept)

    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_id": project_root.name or "project",
        "concept_index": concept_index,
        "claim_index": claim_index,
        "evidence_index": evidence_index,
        "node_index": node_index,
        "file_index": file_index,
        "rtl_object_index": rtl_object_index,
    }


# ---------------------------------------------------------------------------
# Structural shared edges
# ---------------------------------------------------------------------------


def _build_shared_edges(
    results: list[_ConceptTraceResult],
    rtl_node_map: dict[tuple[str, str, str], str],
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """Build inferred structural edges between concepts.

    These edges are based on shared files, shared RTL objects, or shared
    L5/L6 files. They are explicitly marked as ``inferred`` and
    ``structural`` to avoid semantic over-claiming.
    """
    edges: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    # Map file_path -> list of concepts that reference it.
    file_to_concepts: dict[str, set[str]] = {}
    rtl_to_concepts: dict[tuple[str, str, str], set[str]] = {}

    for result in results:
        concept = result.concept
        graph = result.graph
        if graph is None:
            continue

        for node in graph.get("nodes", []):
            fp = node.get("file_path", "")
            kind = node.get("kind", "")
            if fp:
                file_to_concepts.setdefault(fp, set()).add(concept)
            if kind.startswith("rtl_"):
                rtl_key = _rtl_key(node)
                rtl_to_concepts.setdefault(rtl_key, set()).add(concept)

    # Shared file edges.
    seen_file_pairs: set[str] = set()
    for fp, concepts in file_to_concepts.items():
        if len(concepts) > 1:
            concept_list = sorted(concepts)
            for i in range(len(concept_list)):
                for j in range(i + 1, len(concept_list)):
                    c1 = concept_list[i]
                    c2 = concept_list[j]
                    pair_key = "{}|{}".format(c1, c2)
                    if pair_key in seen_file_pairs:
                        continue
                    seen_file_pairs.add(pair_key)
                    edges.append(
                        {
                            "edge_id": "E_SHARED_FILE_{}_{}".format(c1, c2),
                            "from_node_id": _concept_node_id(c1),
                            "to_node_id": _concept_node_id(c2),
                            "edge_type": "shares_file",
                            "confidence": "inferred",
                            "notes": "Both concepts reference file: {}".format(
                                Path(fp).name
                            ),
                        }
                    )

    # Shared RTL object edges.
    seen_rtl_pairs: set[str] = set()
    for rtl_key, concepts in rtl_to_concepts.items():  # type: ignore[reportArgumentType]
        if len(concepts) > 1:
            concept_list = sorted(concepts)
            for i in range(len(concept_list)):
                for j in range(i + 1, len(concept_list)):
                    c1 = concept_list[i]
                    c2 = concept_list[j]
                    pair_key = "{}|{}".format(c1, c2)
                    if pair_key in seen_rtl_pairs:
                        continue
                    seen_rtl_pairs.add(pair_key)
                    edges.append(
                        {
                            "edge_id": "E_SHARED_RTL_{}_{}".format(c1, c2),
                            "from_node_id": _concept_node_id(c1),
                            "to_node_id": _concept_node_id(c2),
                            "edge_type": "shares_rtl_object",
                            "confidence": "inferred",
                            "notes": "Both concepts reference RTL object: {}".format(
                                rtl_key[1]  # name
                            ),
                        }
                    )

    return edges


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_project_markdown(
    project_root: Path,
    results: list[_ConceptTraceResult],
    diagnostics: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
) -> str:
    """Render project understanding as Markdown."""
    lines: list[str] = []
    lines.append("# Project Understanding: {}".format(project_root.name or "project"))
    lines.append("")

    # Summary.
    lines.append("## Summary")
    lines.append("")
    total_concepts = len(results)
    ok_concepts = [r for r in results if r.status == "ok"]
    failed_concepts = [r for r in results if r.status != "ok"]
    total_claims = sum(
        len(r.graph.get("mapping_claims", [])) if r.graph else 0
        for r in results
    )
    total_evidence = sum(
        len(r.graph.get("evidence_items", [])) if r.graph else 0
        for r in results
    )

    lines.append("- Project: {}".format(project_root))
    lines.append("- Concepts traced: {}".format(total_concepts))
    lines.append("- Successful traces: {}".format(len(ok_concepts)))
    if failed_concepts:
        lines.append(
            "- Failed traces: {}".format(
                ", ".join(r.concept for r in failed_concepts)
            )
        )
    lines.append("- Total mapping claims: {}".format(total_claims))
    lines.append("- Total evidence items: {}".format(total_evidence))
    if diagnostics:
        lines.append("- Diagnostics: {}".format(len(diagnostics)))
    lines.append("")

    # Per-concept summary.
    if ok_concepts:
        lines.append("## Concepts")
        lines.append("")
        for result in ok_concepts:
            concept = result.concept
            graph = result.graph
            if graph is None:
                continue
            claims = graph.get("mapping_claims", [])
            evidence = graph.get("evidence_items", [])
            lines.append("### {}".format(concept))
            lines.append("")
            lines.append("- Claims: {}".format(len(claims)))
            lines.append("- Evidence: {}".format(len(evidence)))
            conf_counts: dict[str, int] = {}
            for c in claims:
                conf = c.get("confidence", "unknown")
                conf_counts[conf] = conf_counts.get(conf, 0) + 1
            for conf in sorted(conf_counts):
                lines.append("  - {}: {}".format(conf, conf_counts[conf]))
            lines.append("")

    # Shared RTL / files.
    shared_rtl: dict[str, list[str]] = {}
    shared_files: dict[str, list[str]] = {}
    for result in ok_concepts:
        concept = result.concept
        graph = result.graph
        if graph is None:
            continue
        for node in graph.get("nodes", []):
            fp = node.get("file_path", "")
            if fp:
                shared_files.setdefault(fp, []).append(concept)
            if node.get("kind", "").startswith("rtl_"):
                name = node.get("label", "")
                shared_rtl.setdefault(name, []).append(concept)

    multi_concept_rtl = {
        k: v for k, v in shared_rtl.items() if len(v) > 1
    }
    multi_concept_files = {
        k: v for k, v in shared_files.items() if len(v) > 1
    }

    if multi_concept_rtl or multi_concept_files:
        lines.append("## Shared Resources")
        lines.append("")
        if multi_concept_rtl:
            lines.append("### RTL Objects referenced by multiple concepts")
            lines.append("")
            for name, concepts in multi_concept_rtl.items():
                lines.append(
                    "- {}: {}".format(name, ", ".join(sorted(concepts)))
                )
            lines.append("")
        if multi_concept_files:
            lines.append("### Files referenced by multiple concepts")
            lines.append("")
            for fp, concepts in multi_concept_files.items():
                lines.append(
                    "- {}: {}".format(Path(fp).name, ", ".join(sorted(concepts)))
                )
            lines.append("")

    # Unknowns / limitations.
    lines.append("## Uncertainties and Limitations")
    lines.append("")
    has_unknowns = False
    for result in ok_concepts:
        graph = result.graph
        if graph is None:
            continue
        for note in graph.get("uncertainty_notes", []):
            reason = note.get("reason", "")
            if reason:
                has_unknowns = True
                lines.append(
                    "- **{}**: {}".format(result.concept, reason)
                )
    if not has_unknowns:
        lines.append("No explicit uncertainty notes recorded.")
    lines.append("")

    # Diagnostics.
    if diagnostics:
        lines.append("## Diagnostics")
        lines.append("")
        for d in diagnostics:
            lines.append(
                "- [{}] {}: {}".format(
                    d.get("severity", "info"),
                    d.get("concept", "project"),
                    d.get("message", ""),
                )
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mermaid rendering
# ---------------------------------------------------------------------------


def _render_project_mermaid(graph: dict[str, Any]) -> str:  # pyright: ignore[reportExplicitAny]
    """Render project understanding as Mermaid diagram."""
    lines: list[str] = ["graph TD"]
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    for node in nodes:
        safe_id = _sanitize_mermaid_id(node.get("node_id", ""))
        label = node.get("label", "")
        kind = node.get("kind", "")
        lines.append('    {}["{} ({})"]'.format(safe_id, label, kind))

    lines.append("")

    for edge in edges:
        safe_from = _sanitize_mermaid_id(edge.get("from_node_id", ""))
        safe_to = _sanitize_mermaid_id(edge.get("to_node_id", ""))
        etype = edge.get("edge_type", "")
        conf = edge.get("confidence", "")
        lines.append(
            '    {} -->|"{} ({})"| {}'.format(safe_from, etype, conf, safe_to)
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _concept_node_id(concept: str) -> str:
    """Generate a project-scoped concept node ID."""
    return "PUG_CONCEPT_{}".format(concept)


def _rtl_key(node: dict[str, Any]) -> tuple[str, str, str]:  # pyright: ignore[reportExplicitAny]
    """Generate a deduplication key for an RTL node."""
    fp = node.get("file_path", "")
    label = node.get("label", "")
    kind = node.get("kind", "")
    return (fp, label, kind)


def _concept_confidence(graph: dict[str, Any]) -> str:  # pyright: ignore[reportExplicitAny]
    """Derive overall concept confidence from graph claims."""
    claims = graph.get("mapping_claims", [])
    if not claims:
        return "unknown"
    confidences = [c.get("confidence", "unknown") for c in claims]
    if "supported" in confidences:
        return "supported"
    if "inferred" in confidences:
        return "inferred"
    return "unknown"


def _sanitize_mermaid_id(node_id: str) -> str:
    """Sanitize a node ID for Mermaid syntax."""
    return (
        node_id.replace(":", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
    """Write a dict as pretty-printed JSON."""
    _ = path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
