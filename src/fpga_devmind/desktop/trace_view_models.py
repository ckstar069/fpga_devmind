"""Trace view models for the Desktop Agent Shell (T010).

Pure data-layer transformations from P1b concept trace artifacts to
view-ready row structures.  No GUI dependency.  Testable independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_graph,
    get_grounding_report,
    get_index,
)


# ---------------------------------------------------------------------------
# Row dataclasses — one per trace entity
# ---------------------------------------------------------------------------


@dataclass
class NodeRow:
    """A single node row in the concept trace table."""

    node_id: str = ""
    label: str = ""
    kind: str = ""
    stage_id: str = ""
    confidence: str = ""
    evidence_count: int = 0
    has_diagnostics: bool = False


@dataclass
class EdgeRow:
    """A single edge row in the concept trace table."""

    edge_id: str = ""
    from_label: str = ""
    to_label: str = ""
    edge_type: str = ""
    confidence: str = ""
    claim_refs: str = ""


@dataclass
class ClaimRow:
    """A single claim row in the concept trace table."""

    claim_id: str = ""
    concept_ref: str = ""
    confidence: str = ""
    bridge_kind: str = ""
    l5_l6_evidence_count: int = 0
    rtl_evidence_count: int = 0
    bridge_evidence_count: int = 0
    required_missing_evidence: str = ""
    diagnostic_count: int = 0


@dataclass
class EvidenceRow:
    """A single evidence row in the concept trace table."""

    evidence_id: str = ""
    source_type: str = ""
    file_path: str = ""
    symbol: str = ""
    evidence_strength: str = ""
    referenced_by_claims: str = ""


@dataclass
class DiagnosticRow:
    """A single diagnostic row in the concept trace table."""

    diagnostic_id: str = ""
    severity: str = ""
    issue_type: str = ""
    target_claim_id: str = ""
    message: str = ""
    recommended_action: str = ""


# ---------------------------------------------------------------------------
# Aggregate view model
# ---------------------------------------------------------------------------


@dataclass
class ConceptTraceViewModel:
    """Aggregated concept trace view model with all row tables."""

    nodes: list[NodeRow] = field(default_factory=list)
    edges: list[EdgeRow] = field(default_factory=list)
    claims: list[ClaimRow] = field(default_factory=list)
    evidence: list[EvidenceRow] = field(default_factory=list)
    diagnostics: list[DiagnosticRow] = field(default_factory=list)
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_concept_trace_view_model(
    bundle: ArtifactBundle,
) -> ConceptTraceViewModel:
    """Build a ConceptTraceViewModel from a loaded P1b bundle.

    Never raises; all errors return a view model with ``is_loaded=False``.
    """
    if not bundle.is_complete:
        errors = [
            d.message for d in bundle.diagnostics if d.severity == "error"
        ]
        return ConceptTraceViewModel(
            is_loaded=False,
            load_error="; ".join(errors) if errors else "Incomplete bundle",
        )

    if bundle.bundle_type != "p1b":
        return ConceptTraceViewModel(
            is_loaded=False,
            load_error="Trace view available for P1b bundles only",
        )

    graph = get_graph(bundle)
    if graph is None:
        return ConceptTraceViewModel(
            is_loaded=False,
            load_error="concept_trace_graph.json not found or invalid",
        )

    index = get_index(bundle) or {}
    grounding = get_grounding_report(bundle) or {}

    # Build lookup tables.
    node_map = _build_node_map(graph)
    all_diagnostics = _deduplicate_diagnostics(graph, grounding)
    claim_diag_counts = _build_claim_diag_counts(all_diagnostics)
    evidence_claim_refs = _build_evidence_claim_refs(index)
    claim_ids_with_diag = set(claim_diag_counts.keys())

    # Build rows.
    nodes = _build_node_rows(graph, index, claim_ids_with_diag)
    edges = _build_edge_rows(graph, node_map)
    claims = _build_claim_rows(graph, claim_diag_counts)
    evidence = _build_evidence_rows(graph, evidence_claim_refs)
    diagnostics = _build_diagnostic_rows_from_list(all_diagnostics)

    return ConceptTraceViewModel(
        nodes=nodes,
        edges=edges,
        claims=claims,
        evidence=evidence,
        diagnostics=diagnostics,
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_node_map(graph: dict[str, Any]) -> dict[str, str]:  # pyright: ignore[reportExplicitAny]
    """Map node_id -> label from graph.nodes."""
    mapping: dict[str, str] = {}
    for node in graph.get("nodes", []):
        nid = node.get("node_id", "")
        label = node.get("label", "")
        if nid:
            mapping[nid] = label
    return mapping


def _deduplicate_diagnostics(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """Merge and de-duplicate diagnostics from graph and grounding report.

    Primary key is ``diagnostic_id``.  If missing, fallback to
    ``(target_claim_id, issue_type, message)``.
    """
    seen: set[str] = set()
    result: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    def _key(diag: dict[str, Any]) -> str:  # pyright: ignore[reportExplicitAny]
        did = diag.get("diagnostic_id")
        if did:
            return str(did)
        return "{}|{}|{}".format(
            diag.get("target_claim_id") or "",
            diag.get("issue_type") or "",
            diag.get("message") or "",
        )

    for diag in graph.get("grounding_diagnostics", []):
        if isinstance(diag, dict):
            k = _key(diag)
            if k not in seen:
                seen.add(k)
                result.append(diag)
    for diag in grounding.get("diagnostics", []):
        if isinstance(diag, dict):
            k = _key(diag)
            if k not in seen:
                seen.add(k)
                result.append(diag)
    return result


def _build_claim_diag_counts(
    all_diagnostics: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
) -> dict[str, int]:
    """Count how many de-duplicated diagnostics target each claim_id."""
    counts: dict[str, int] = {}
    for diag in all_diagnostics:
        target = diag.get("target_claim_id")
        if target:
            counts[target] = counts.get(target, 0) + 1
    return counts


def _build_evidence_claim_refs(
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> dict[str, list[str]]:
    """Map evidence_id -> list of referencing claim_ids from index."""
    refs: dict[str, list[str]] = {}
    evidence_index = index.get("evidence_index", {})
    if isinstance(evidence_index, dict):
        for eid, info in evidence_index.items():
            if isinstance(info, dict):
                claim_ids = info.get("claim_ids", [])
                if isinstance(claim_ids, list):
                    refs[eid] = list(claim_ids)
    return refs


def _build_node_rows(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    claim_ids_with_diag: set[str],
) -> list[NodeRow]:
    """Build NodeRow list from graph.nodes.

    ``has_diagnostics`` is derived conservatively: if any of the node's
    evidence items is referenced by a claim that has diagnostics, the node
    is flagged.  Missing or dangling references default to ``False``.
    """
    rows: list[NodeRow] = []
    evidence_index = index.get("evidence_index", {})
    if not isinstance(evidence_index, dict):
        evidence_index = {}

    for node in graph.get("nodes", []):
        node_id = node.get("node_id", "")
        evidence_ids = node.get("evidence_ids", [])
        evidence_count = (
            len(evidence_ids) if isinstance(evidence_ids, list) else 0
        )
        has_diag = False
        if isinstance(evidence_ids, list):
            for eid in evidence_ids:
                info = evidence_index.get(eid)
                if isinstance(info, dict):
                    cids = info.get("claim_ids", [])
                    if isinstance(cids, list):
                        for cid in cids:
                            if cid in claim_ids_with_diag:
                                has_diag = True
                                break
                if has_diag:
                    break

        rows.append(
            NodeRow(
                node_id=node_id,
                label=node.get("label", ""),
                kind=node.get("kind", ""),
                stage_id=node.get("stage_id") or "",
                confidence=node.get("confidence", ""),
                evidence_count=evidence_count,
                has_diagnostics=has_diag,
            )
        )
    return rows


def _build_edge_rows(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    node_map: dict[str, str],
) -> list[EdgeRow]:
    """Build EdgeRow list from graph.edges."""
    rows: list[EdgeRow] = []
    for edge in graph.get("edges", []):
        from_id = edge.get("from_node_id", "")
        to_id = edge.get("to_node_id", "")
        from_label = node_map.get(from_id)
        if from_label is None:
            from_label = "(unresolved: {})".format(from_id)
        to_label = node_map.get(to_id)
        if to_label is None:
            to_label = "(unresolved: {})".format(to_id)
        claim_ids = edge.get("source_claim_ids", [])
        rows.append(
            EdgeRow(
                edge_id=edge.get("edge_id", ""),
                from_label=from_label,
                to_label=to_label,
                edge_type=edge.get("edge_type", ""),
                confidence=edge.get("confidence", ""),
                claim_refs=", ".join(claim_ids) if isinstance(claim_ids, list) else "",
            )
        )
    return rows


def _build_claim_rows(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    claim_diag_counts: dict[str, int],
) -> list[ClaimRow]:
    """Build ClaimRow list from graph.mapping_claims."""
    rows: list[ClaimRow] = []
    for claim in graph.get("mapping_claims", []):
        claim_id = claim.get("claim_id", "")
        l5 = claim.get("l5_l6_evidence_ids", [])
        rtl = claim.get("rtl_evidence_ids", [])
        bridge = claim.get("bridge_evidence_ids", [])
        missing = claim.get("required_missing_evidence", [])
        rows.append(
            ClaimRow(
                claim_id=claim_id,
                concept_ref=claim.get("concept_ref", ""),
                confidence=claim.get("confidence", ""),
                bridge_kind=claim.get("bridge_kind", ""),
                l5_l6_evidence_count=len(l5) if isinstance(l5, list) else 0,
                rtl_evidence_count=len(rtl) if isinstance(rtl, list) else 0,
                bridge_evidence_count=len(bridge) if isinstance(bridge, list) else 0,
                required_missing_evidence="; ".join(missing) if isinstance(missing, list) else "",
                diagnostic_count=claim_diag_counts.get(claim_id, 0),
            )
        )
    return rows


def _build_evidence_rows(
    graph: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    evidence_claim_refs: dict[str, list[str]],
) -> list[EvidenceRow]:
    """Build EvidenceRow list from graph.evidence_items."""
    rows: list[EvidenceRow] = []
    for item in graph.get("evidence_items", []):
        eid = item.get("evidence_id", "")
        claim_ids = evidence_claim_refs.get(eid, [])
        rows.append(
            EvidenceRow(
                evidence_id=eid,
                source_type=item.get("source_type", ""),
                file_path=item.get("file_path", ""),
                symbol=item.get("symbol") or "",
                evidence_strength=item.get("evidence_strength", ""),
                referenced_by_claims=", ".join(claim_ids) if claim_ids else "",
            )
        )
    return rows


def _build_diagnostic_rows_from_list(
    all_diagnostics: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
) -> list[DiagnosticRow]:
    """Build DiagnosticRow list from de-duplicated diagnostics."""
    rows: list[DiagnosticRow] = []
    for diag in all_diagnostics:
        rows.append(
            DiagnosticRow(
                diagnostic_id=diag.get("diagnostic_id", ""),
                severity=diag.get("severity", ""),
                issue_type=diag.get("issue_type", ""),
                target_claim_id=diag.get("target_claim_id") or "",
                message=diag.get("message") or "",
                recommended_action=diag.get("recommended_action", ""),
            )
        )
    return rows
