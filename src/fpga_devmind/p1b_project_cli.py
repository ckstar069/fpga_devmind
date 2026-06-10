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
    golden_spec: Path | None = None,
    discovery_mode: str = "auto",
    max_concepts: int = 12,
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
        Use ``["auto"]`` for auto-discovery.
    out_dir : Path
        Output directory for project artifacts (must be a safe temp path).
    golden_spec : Path | None
        Optional golden benchmark spec for guided auto-trace (T037).
        When provided with auto-discovery, prioritizes golden-matched concepts.
    discovery_mode : str
        Discovery mode: "auto" (default), "conservative", "balanced", "broad".
    max_concepts : int
        Maximum number of concepts to select for auto-trace (default 12).

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

    # --- Auto-discovery (T035) ---
    discovery_metadata: dict[str, Any] = {}
    eval_result_dict: dict[str, Any] | None = None
    discovery_result_for_candidates = None
    if len(concepts) == 1 and concepts[0] == "auto":
        from .p1b_discovery import discover_concepts, select_for_trace

        discovery_result = discover_concepts(project_root)
        discovery_result_for_candidates = discovery_result

        # When golden-spec provided, use select_for_trace and eval
        if golden_spec and golden_spec.is_file():
            from .discovery_eval import evaluate_discovery, generate_eval_report

            selected = select_for_trace(discovery_result, max_n=max_concepts)
            concepts = [c.name for c in selected]

            # T038: Golden-aware canonicalization and filtering
            concepts = _canonicalize_with_golden(concepts, golden_spec)

            # Run evaluation for metrics
            eval_result = evaluate_discovery(project_root, golden_spec, max_concepts=max_concepts)
            eval_result_dict = eval_result.to_dict()

            # Write eval artifacts
            safe_out = ensure_safe_output_dir(out_dir, label="project trace output")
            safe_out.mkdir(parents=True, exist_ok=True)
            eval_json = safe_out / "discovery_eval_result.json"
            eval_json.write_text(
                json.dumps(eval_result_dict, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            eval_report = safe_out / "discovery_eval_report.md"
            eval_report.write_text(
                generate_eval_report(eval_result) + "\n",
                encoding="utf-8",
            )

            # Write concept candidates (T038: all candidates with new fields)
            candidates_json = safe_out / "concept_candidates.json"
            candidates_json.write_text(
                json.dumps(
                    [_candidate_to_dict(c) for c in discovery_result.candidates],
                    indent=2, ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )
        else:
            # Standard auto-discovery without golden spec
            selected = select_for_trace(discovery_result, max_n=max_concepts)
            concepts = [c.name for c in selected]

        discovery_metadata = {
            "discovery_used": True,
            "discovery_mode": discovery_mode,
            "discovered_count": len(discovery_result.candidates),
            "discovered_concepts": [c.name for c in discovery_result.candidates],
            "selected_concepts": concepts,
            "skipped_count": max(0, len(discovery_result.candidates) - max_concepts),
            "golden_spec_used": golden_spec is not None and golden_spec.is_file(),
        }
        if eval_result_dict:
            discovery_metadata["eval_metrics"] = {
                "selected_precision_like": eval_result_dict.get("selected_precision_like"),
                "selected_recall_like": eval_result_dict.get("selected_recall_like"),
            }
        if not concepts:
            raise ValueError("Auto-discovery found no concept candidates.")
    else:
        discovery_metadata = {"discovery_used": False}

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
        "project_id": project_root.name or "project",
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
    metadata.update(discovery_metadata)
    # T038: ensure selected_canonical_concepts and selected_concept_count
    if metadata.get("selected_concepts"):
        metadata["selected_canonical_concepts"] = metadata["selected_concepts"]
        metadata["selected_concept_count"] = len(metadata["selected_concepts"])

    # T038: Write concept candidates (all paths)
    if discovery_result_for_candidates is not None:
        candidates_json = safe_out / "concept_candidates.json"
        candidates_json.write_text(
            json.dumps(
                [_candidate_to_dict(c) for c in discovery_result_for_candidates.candidates],
                indent=2, ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    # T038: Generate and write project semantic summary
    semantic_summary_status = "ok"
    semantic_summary_error = ""
    try:
        from .project_semantic_summary import build_semantic_summary

        semantic_summary = build_semantic_summary(
            project_root,
            project_graph,
            project_index,
            metadata,
            discovery_result_for_candidates.candidates if discovery_result_for_candidates else [],
            eval_result_dict,
            traced_concepts=metadata.get("concepts_processed"),
        )
        _write_json(safe_out / "project_semantic_summary.json", semantic_summary)
        metadata["artifacts"].append("project_semantic_summary.json")
        # Add semantic_summary_path to index for cross-reference
        project_index["semantic_summary_path"] = "project_semantic_summary.json"
        _write_json(safe_out / "project_understanding_index.json", project_index)
        semantic_summary_status = "ok"
    except Exception as exc:
        semantic_summary_status = "failed"
        semantic_summary_error = str(exc)
        diagnostics.append(
            {
                "severity": "warning",
                "concept": "project",
                "message": f"Semantic summary generation failed: {exc}",
                "code": "SEMANTIC_SUMMARY_FAILED",
            }
        )
        # If semantic summary fails, downgrade overall status from ok to partial
        if metadata.get("status") == "ok":
            metadata["status"] = "partial"

    metadata["semantic_summary_status"] = semantic_summary_status
    if semantic_summary_error:
        metadata["semantic_summary_error"] = semantic_summary_error

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

        # Stage-categorized evidence counts (T035)
        l5_count = 0
        l6_count = 0
        test_count = 0
        for ei in graph.get("evidence_items", []):
            fp = ei.get("file_path", "")
            if "L5_fixedpoint" in fp:
                l5_count += 1
            elif "L6_resource_opt" in fp:
                l6_count += 1
            elif "test" in fp.lower() or fp.startswith(str(project_root / "tests")):
                test_count += 1

        concept_index[concept].update({
            "l5_count": l5_count,
            "l6_count": l6_count,
            "test_count": test_count,
        })

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

    # Build evidence chains per concept (T035)
    evidence_chain: dict[str, dict[str, Any]] = {}
    # Check if project has test files at all (for V2.1 status classification)
    project_test_dir = project_root / "tests"
    project_has_tests = project_test_dir.is_dir() and any(
        f.suffix in (".py", ".v", ".sv") for f in project_test_dir.rglob("*") if f.is_file()
    )
    for result in results:
        concept = result.concept
        graph = result.graph
        if graph is None:
            continue

        chain: dict[str, Any] = {
            "l5_l6_evidence": [],
            "claims": [],
            "rtl_evidence": [],
            "test_evidence": [],
            "missing": [],
            # V2.1: test evidence status fields (T037)
            "test_evidence_status": "no_test_files",
            "test_files_scanned": 0,
            "matched_test_symbols": [],
            "missing_reason": "",
        }

        test_file_count = 0
        matched_symbols: list[str] = []

        for ei in graph.get("evidence_items", []):
            entry = {
                "evidence_id": ei.get("evidence_id", ""),
                "file_path": ei.get("file_path", ""),
                "symbol": ei.get("symbol", ""),
                "strength": ei.get("evidence_strength", ""),
            }
            fp = ei.get("file_path", "")
            if "L5_fixedpoint" in fp or "L6_resource_opt" in fp:
                chain["l5_l6_evidence"].append(entry)
            elif "test" in fp.lower():
                test_file_count += 1
                sym = ei.get("symbol", "")
                if sym and sym.lower() != concept.lower() and concept.lower() in sym.lower():
                    matched_symbols.append(sym)
                elif sym and concept.lower() == sym.lower():
                    matched_symbols.append(sym)
                chain["test_evidence"].append(entry)
            else:
                chain["rtl_evidence"].append(entry)

        # V2.1: classify test evidence status
        chain["test_files_scanned"] = test_file_count
        chain["matched_test_symbols"] = matched_symbols[:10]
        if test_file_count > 0 and matched_symbols:
            chain["test_evidence_status"] = "test_evidence_found"
            chain["missing_reason"] = ""
        elif project_has_tests and test_file_count == 0:
            chain["test_evidence_status"] = "test_extraction_not_supported"
            chain["missing_reason"] = "Project has test files but concept trace does not scan tests"
        elif test_file_count > 0 and not matched_symbols:
            chain["test_evidence_status"] = "test_files_exist_but_no_alias_match"
            chain["missing_reason"] = "Test files exist but no symbol matching concept found"
        else:
            chain["test_evidence_status"] = "no_test_files"
            chain["missing_reason"] = "No test files found for this concept"

        for claim in graph.get("mapping_claims", []):
            chain["claims"].append({
                "claim_id": claim.get("claim_id", ""),
                "bridge_kind": claim.get("bridge_kind", ""),
                "confidence": claim.get("confidence", ""),
            })

        # Missing evidence indicators
        if not chain["l5_l6_evidence"]:
            chain["missing"].append("L5/L6 evidence")
        if not chain["rtl_evidence"]:
            chain["missing"].append("RTL evidence")
        if not chain["test_evidence"]:
            chain["missing"].append("test evidence")

        # V2 additions: aliases, selection_reason, confidence_explanation,
        # why_core_or_secondary
        chain["aliases"] = []
        chain["selection_reason"] = ""
        chain["confidence_explanation"] = _build_confidence_explanation(chain)
        chain["why_core_or_secondary"] = _classify_core_or_secondary(chain)

        evidence_chain[concept] = chain

    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_id": project_root.name or "project",
        "concept_index": concept_index,
        "claim_index": claim_index,
        "evidence_index": evidence_index,
        "node_index": node_index,
        "file_index": file_index,
        "rtl_object_index": rtl_object_index,
        "evidence_chain": evidence_chain,
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


def _build_confidence_explanation(chain: dict[str, Any]) -> str:  # pyright: ignore[reportExplicitAny]
    """Build a human-readable confidence explanation from evidence chain data.

    Parameters
    ----------
    chain : dict[str, Any]
        Evidence chain dictionary with l5_l6_evidence, rtl_evidence, test_evidence.

    Returns
    -------
    str
        Human-readable confidence explanation string.
    """
    l5l6_count = len(chain.get("l5_l6_evidence", []))
    rtl_count = len(chain.get("rtl_evidence", []))
    test_count = len(chain.get("test_evidence", []))
    claim_count = len(chain.get("claims", []))
    missing = chain.get("missing", [])

    parts: list[str] = []

    if l5l6_count > 0:
        parts.append("L5/L6 ({} ref{})".format(l5l6_count, "s" if l5l6_count != 1 else ""))
    if rtl_count > 0:
        parts.append("RTL ({} ref{})".format(rtl_count, "s" if rtl_count != 1 else ""))
    if test_count > 0:
        parts.append("tests ({} ref{})".format(test_count, "s" if test_count != 1 else ""))

    if not parts:
        return "No confidence: no evidence found"

    total_refs = l5l6_count + rtl_count + test_count
    cross_stage = (l5l6_count > 0 and rtl_count > 0)

    if cross_stage and total_refs >= 4:
        level = "High"
    elif cross_stage:
        level = "High"
    elif total_refs >= 3:
        level = "Medium"
    elif total_refs == 1:
        level = "Low"
    else:
        level = "Medium"

    explanation = "{} confidence: found in {}".format(level, ", ".join(parts))
    if claim_count > 0:
        explanation += " with {} claim{}".format(claim_count, "s" if claim_count != 1 else "")
    if missing:
        explanation += " — missing: {}".format(", ".join(missing))
    if cross_stage:
        explanation += " — cross-stage evidence"

    return explanation


def _classify_core_or_secondary(chain: dict[str, Any]) -> str:  # pyright: ignore[reportExplicitAny]
    """Classify a concept as core or secondary based on evidence chain data.

    A concept is "core" if it has cross-stage evidence (L5/L6 + RTL) or
    high total occurrence count. Otherwise it is "secondary".

    Parameters
    ----------
    chain : dict[str, Any]
        Evidence chain dictionary.

    Returns
    -------
    str
        Classification string: "core: <reason>" or "secondary: <reason>".
    """
    l5l6_count = len(chain.get("l5_l6_evidence", []))
    rtl_count = len(chain.get("rtl_evidence", []))
    test_count = len(chain.get("test_evidence", []))
    total = l5l6_count + rtl_count + test_count

    has_cross_stage = l5l6_count > 0 and rtl_count > 0
    has_high_count = total >= 4

    if has_cross_stage:
        return "core: cross-stage evidence (L5/L6 + RTL)"
    if has_high_count:
        return "core: high occurrence count ({} refs)".format(total)
    if l5l6_count > 0 and rtl_count == 0:
        return "secondary: domain term found in L5/L6 only"
    if rtl_count > 0 and l5l6_count == 0:
        return "secondary: RTL-only evidence"
    if test_count > 0 and l5l6_count == 0 and rtl_count == 0:
        return "secondary: test-only evidence"
    return "secondary: limited evidence"


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


def _canonicalize_with_golden(concepts: list[str], golden_spec: Path) -> list[str]:
    """Canonicalize selected concepts using golden spec aliases and filter excluded terms."""
    try:
        spec = json.loads(golden_spec.read_text(encoding="utf-8"))
    except Exception:
        return concepts

    # Build alias -> canonical mapping from golden spec
    alias_to_canonical: dict[str, str] = {}
    for gc in spec.get("expected_core_concepts", []) + spec.get("expected_secondary_concepts", []):
        canonical = gc.get("concept", "")
        if canonical:
            alias_to_canonical[canonical.lower()] = canonical
            for alias in gc.get("aliases", []):
                alias_to_canonical[alias.lower()] = canonical

    # Build excluded terms set
    excluded = {item.get("term", "").lower() for item in spec.get("excluded_terms", [])}

    result: list[str] = []
    seen: set[str] = set()
    for c in concepts:
        # Skip excluded terms
        if c.lower() in excluded:
            continue
        # Canonicalize via golden alias map
        canonical = alias_to_canonical.get(c.lower(), c)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    return result


def _candidate_to_dict(c) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Serialize a ConceptCandidate to dict with all T038 fields."""
    return {
        "name": c.name,
        "canonical_name": c.canonical_name,
        "aliases": c.aliases,
        "source_sections": c.source_sections,
        "occurrence_count": c.occurrence_count,
        "confidence": c.confidence,
        "reason": c.reason,
        "representative_files": c.representative_files,
        "likely_stage": c.likely_stage,
        "semantic_role": c.semantic_role,
        "score": c.score,
        "score_breakdown": {
            "cross_stage_bonus": c.score_breakdown.cross_stage_bonus,
            "key_position_bonus": c.score_breakdown.key_position_bonus,
            "domain_term_bonus": c.score_breakdown.domain_term_bonus,
            "short_domain_bonus": c.score_breakdown.short_domain_bonus,
            "test_presence_bonus": c.score_breakdown.test_presence_bonus,
            "occurrence_score": c.score_breakdown.occurrence_score,
            "alias_group_bonus": c.score_breakdown.alias_group_bonus,
            "generic_penalty": c.score_breakdown.generic_penalty,
            "total": c.score_breakdown.total,
        },
        "selection_reason": c.selection_reason,
        "compound_source": c.compound_source,
        "category": c.category,
        "is_selected": c.is_selected,
        "rejection_reason": c.rejection_reason,
        "evidence_counts_by_stage": c.evidence_counts_by_stage,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
    """Write a dict as pretty-printed JSON."""
    _ = path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
