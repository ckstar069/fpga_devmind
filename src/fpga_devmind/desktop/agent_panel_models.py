"""Agent interaction panel models for the Desktop Agent Shell (T011).

Deterministic, rule-based artifact query.  No LLM, no external API,
no API key.  Pure Python; testable without PySide6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_graph,
    get_grounding_report,
    get_index,
    get_run_metadata,
)

if TYPE_CHECKING:
    from fpga_devmind.desktop.agent_plan_models import AgentPlanPreview


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentPanelResponse:
    """Response from a deterministic local artifact query."""

    question: str = ""
    answer_text: str = ""
    response_kind: str = "unsupported"  # "summary" | "claims" | "evidence" |
    # "diagnostics" | "unknown" | "nodes" | "edges" | "claim_detail" |
    # "evidence_detail" | "unsupported"
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None
    plan_preview: "AgentPlanPreview | None" = None
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def query_artifact_bundle(
    bundle: ArtifactBundle,
    question: str,
) -> AgentPanelResponse:
    """Answer a question about *bundle* using deterministic rules.

    Never raises; all errors return ``is_loaded=False``.
    """
    if not bundle.is_complete:
        errors = [
            d.message for d in bundle.diagnostics if d.severity == "error"
        ]
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="; ".join(errors) if errors else "Incomplete bundle",
        )

    if bundle.bundle_type not in ("p1b", "p1a"):
        return AgentPanelResponse(
            question=question,
            is_loaded=False,
            load_error="Agent query available for P1a/P1b bundles only",
        )

    graph = get_graph(bundle)
    index = get_index(bundle) or {}
    grounding = get_grounding_report(bundle) or {}
    meta = get_run_metadata(bundle) or {}

    normalized = question.strip().lower()

    # Specific ID lookups first (use original question to preserve case).
    claim_match = _extract_claim_id(question)
    if claim_match:
        return _answer_claim_detail(
            normalized, graph, claim_match, index, grounding
        )

    evidence_match = _extract_evidence_id(question)
    if evidence_match:
        return _answer_evidence_detail(normalized, graph, evidence_match)

    # Keyword-based routing.
    if _has_any(normalized, ["summary", "概况", "做了什么", "overview", "about"]):
        return _answer_summary(normalized, graph, meta, grounding)

    if _has_any(
        normalized, ["claims", "mapping", "映射", "claim", "mapping claims"]
    ):
        return _answer_claims(normalized, graph)

    if _has_any(normalized, ["evidence", "证据", "proof"]):
        return _answer_evidence(normalized, graph)

    if _has_any(
        normalized, ["diagnostics", "grounding", "诊断", "checker"]
    ):
        return _answer_diagnostics(normalized, graph, grounding)

    if _has_any(
        normalized, ["unknown", "不确定", "uncertainty", "unsure"]
    ):
        return _answer_unknown(normalized, graph)

    if _has_any(normalized, ["nodes", "node", "节点"]):
        return _answer_nodes(normalized, graph)

    if _has_any(normalized, ["edges", "edge", "边"]):
        return _answer_edges(normalized, graph)

    # Fallback.
    return AgentPanelResponse(
        question=question,
        response_kind="unsupported",
        answer_text=(
            "This question is not supported by the local deterministic query.\n"
            "Supported topics: summary, claims, evidence, diagnostics, "
            "unknown/uncertainty, nodes, edges, or a specific claim_id / "
            "evidence_id.\n"
            "External LLM is not enabled in T011."
        ),
        unsupported_reason="question_type_not_recognized",
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_any(text: str, terms: list[str]) -> bool:
    """Return True if *text* contains any of *terms*."""
    return any(term in text for term in terms)


def _deduplicate_diagnostics(
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
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

    for source in (
        (graph or {}).get("grounding_diagnostics", []),
        grounding.get("diagnostics", []),
    ):
        for diag in source:
            if isinstance(diag, dict):
                k = _key(diag)
                if k not in seen:
                    seen.add(k)
                    result.append(diag)
    return result


_CLAIM_ID_RE = re.compile(r"\b(MC_[A-Za-z0-9_]+)\b", re.IGNORECASE)
_EVIDENCE_ID_RE = re.compile(r"\b(E:[A-Za-z0-9_:/-]+)\b", re.IGNORECASE)


def _extract_claim_id(text: str) -> str | None:
    m = _CLAIM_ID_RE.search(text)
    return m.group(1) if m else None


def _extract_evidence_id(text: str) -> str | None:
    m = _EVIDENCE_ID_RE.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Answer builders — P1b aware, fall back gracefully when graph is None
# ---------------------------------------------------------------------------


def _answer_summary(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    meta: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    concept = meta.get("concept", "")
    status = meta.get("status", "unknown")
    claims = meta.get("mapping_claims", 0)
    evidence = meta.get("evidence_items", 0)
    blocking = meta.get("blocking_diagnostics", 0)
    elapsed = meta.get("elapsed_seconds", 0.0)

    lines = [
        "## Summary",
        "",
        "- Concept: {}".format(concept),
        "- Status: {}".format(status),
        "- Mapping claims: {}".format(claims),
        "- Evidence items: {}".format(evidence),
        "- Blocking diagnostics: {}".format(blocking),
        "- Elapsed: {:.3f}s".format(elapsed),
    ]

    if graph:
        nodes = len(graph.get("nodes", []))
        edges = len(graph.get("edges", []))
        lines.extend([
            "- Nodes: {}".format(nodes),
            "- Edges: {}".format(edges),
        ])

    summary_diag = grounding.get("summary", {})
    if isinstance(summary_diag, dict):
        for key, value in summary_diag.items():
            lines.append("- {}: {}".format(key, value))

    return AgentPanelResponse(
        question=question,
        response_kind="summary",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_claims(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="claims",
            answer_text="No concept trace graph available.",
            is_loaded=True,
        )

    claims = graph.get("mapping_claims", [])
    if not claims:
        return AgentPanelResponse(
            question=question,
            response_kind="claims",
            answer_text="No mapping claims found.",
            is_loaded=True,
        )

    lines = ["## Mapping Claims", ""]
    claim_ids: list[str] = []
    for claim in claims:
        cid = claim.get("claim_id", "")
        claim_ids.append(cid)
        conf = claim.get("confidence", "unknown")
        bridge = claim.get("bridge_kind", "unknown")
        lines.append(
            "- {} | confidence: {} | bridge: {}".format(cid, conf, bridge)
        )

    return AgentPanelResponse(
        question=question,
        response_kind="claims",
        answer_text="\n".join(lines),
        referenced_claim_ids=claim_ids,
        is_loaded=True,
    )


def _answer_evidence(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence",
            answer_text="No concept trace graph available.",
            is_loaded=True,
        )

    items = graph.get("evidence_items", [])
    if not items:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence",
            answer_text="No evidence items found.",
            is_loaded=True,
        )

    lines = ["## Evidence Items", ""]
    eids: list[str] = []
    for item in items[:20]:
        eid = item.get("evidence_id", "")
        eids.append(eid)
        src = item.get("source_type", "")
        sym = item.get("symbol") or ""
        strength = item.get("evidence_strength", "")
        lines.append(
            "- {} | source: {} | symbol: {} | strength: {}".format(
                eid, src, sym, strength
            )
        )
    if len(items) > 20:
        lines.append("\n... and {} more".format(len(items) - 20))

    return AgentPanelResponse(
        question=question,
        response_kind="evidence",
        answer_text="\n".join(lines),
        referenced_evidence_ids=eids,
        is_loaded=True,
    )


def _answer_diagnostics(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    diags = _deduplicate_diagnostics(graph, grounding)

    if not diags:
        return AgentPanelResponse(
            question=question,
            response_kind="diagnostics",
            answer_text="No diagnostics found.",
            is_loaded=True,
        )

    lines = ["## Diagnostics", ""]
    diag_ids: list[str] = []
    for diag in diags:
        did = diag.get("diagnostic_id", "")
        diag_ids.append(did)
        severity = diag.get("severity", "")
        issue = diag.get("issue_type", "")
        target = diag.get("target_claim_id") or ""
        msg = diag.get("message") or ""
        lines.append(
            "- {} | severity: {} | issue: {} | target: {} | {}".format(
                did, severity, issue, target, msg
            )
        )

    return AgentPanelResponse(
        question=question,
        response_kind="diagnostics",
        answer_text="\n".join(lines),
        referenced_diagnostic_ids=diag_ids,
        is_loaded=True,
    )


def _answer_unknown(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="unknown",
            answer_text="No concept trace graph available.",
            is_loaded=True,
        )

    notes = graph.get("uncertainty_notes", [])
    claims = graph.get("mapping_claims", [])
    unknown_claims = [c for c in claims if c.get("confidence") == "unknown"]

    lines = ["## Unknown / Uncertainty", ""]

    if unknown_claims:
        lines.append("### Claims with unknown confidence")
        for claim in unknown_claims:
            cid = claim.get("claim_id", "")
            missing = claim.get("required_missing_evidence", [])
            lines.append(
                "- {} | missing: {}".format(
                    cid,
                    "; ".join(missing) if isinstance(missing, list) else "",
                )
            )
        lines.append("")

    if notes:
        lines.append("### Uncertainty notes")
        for note in notes:
            topic = note.get("topic", "")
            reason = note.get("reason", "")
            lines.append("- {} | {}".format(topic, reason))
    else:
        lines.append("No explicit uncertainty notes recorded.")

    return AgentPanelResponse(
        question=question,
        response_kind="unknown",
        answer_text="\n".join(lines),
        referenced_claim_ids=[c.get("claim_id", "") for c in unknown_claims],
        uncertainty_notes=[n.get("reason", "") for n in notes],
        is_loaded=True,
    )


def _answer_nodes(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="nodes",
            answer_text="No concept trace graph available.",
            is_loaded=True,
        )

    nodes = graph.get("nodes", [])
    lines = ["## Nodes ({})".format(len(nodes)), ""]
    nids: list[str] = []
    for node in nodes:
        nid = node.get("node_id", "")
        nids.append(nid)
        label = node.get("label", "")
        kind = node.get("kind", "")
        conf = node.get("confidence", "")
        lines.append(
            "- {} | label: {} | kind: {} | confidence: {}".format(
                nid, label, kind, conf
            )
        )

    return AgentPanelResponse(
        question=question,
        response_kind="nodes",
        answer_text="\n".join(lines),
        referenced_node_ids=nids,
        is_loaded=True,
    )


def _answer_edges(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="edges",
            answer_text="No concept trace graph available.",
            is_loaded=True,
        )

    edges = graph.get("edges", [])
    node_map = _build_node_map(graph)
    lines = ["## Edges ({})".format(len(edges)), ""]
    for edge in edges:
        eid = edge.get("edge_id", "")
        fid = edge.get("from_node_id", "")
        tid = edge.get("to_node_id", "")
        fl = node_map.get(fid, fid)
        tl = node_map.get(tid, tid)
        et = edge.get("edge_type", "")
        conf = edge.get("confidence", "")
        lines.append(
            "- {} | {} -> {} | type: {} | confidence: {}".format(
                eid, fl, tl, et, conf
            )
        )

    return AgentPanelResponse(
        question=question,
        response_kind="edges",
        answer_text="\n".join(lines),
        is_loaded=True,
    )


def _answer_claim_detail(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    claim_id: str,
    index: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="claim_detail",
            answer_text="No concept trace graph available.",
            referenced_claim_ids=[claim_id],
            is_loaded=True,
        )

    claims = graph.get("mapping_claims", [])
    claim = next((c for c in claims if c.get("claim_id") == claim_id), None)
    if claim is None:
        return AgentPanelResponse(
            question=question,
            response_kind="claim_detail",
            answer_text="Claim {} not found.".format(claim_id),
            referenced_claim_ids=[claim_id],
            is_loaded=True,
        )

    lines = ["## Claim: {}".format(claim_id), ""]
    lines.append("- concept_ref: {}".format(claim.get("concept_ref", "")))
    lines.append("- confidence: {}".format(claim.get("confidence", "")))
    lines.append("- bridge_kind: {}".format(claim.get("bridge_kind", "")))
    lines.append(
        "- statement: {}".format(claim.get("statement", "(none)"))
    )

    l5 = claim.get("l5_l6_evidence_ids", [])
    rtl = claim.get("rtl_evidence_ids", [])
    bridge = claim.get("bridge_evidence_ids", [])
    lines.append("- L5/L6 evidence: {}".format(len(l5) if isinstance(l5, list) else 0))
    lines.append("- RTL evidence: {}".format(len(rtl) if isinstance(rtl, list) else 0))
    lines.append("- Bridge evidence: {}".format(len(bridge) if isinstance(bridge, list) else 0))

    missing = claim.get("required_missing_evidence", [])
    if missing and isinstance(missing, list):
        lines.append("- Missing evidence: {}".format("; ".join(missing)))

    # Count diagnostics targeting this claim (deduplicated).
    all_diags = _deduplicate_diagnostics(graph, grounding)
    diag_count = sum(
        1 for d in all_diags if d.get("target_claim_id") == claim_id
    )
    if diag_count:
        lines.append("- Diagnostics: {}".format(diag_count))

    return AgentPanelResponse(
        question=question,
        response_kind="claim_detail",
        answer_text="\n".join(lines),
        referenced_claim_ids=[claim_id],
        referenced_evidence_ids=list(claim.get("evidence_ids", [])),
        is_loaded=True,
    )


def _answer_evidence_detail(
    question: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    evidence_id: str,
) -> AgentPanelResponse:
    if graph is None:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence_detail",
            answer_text="No concept trace graph available.",
            referenced_evidence_ids=[evidence_id],
            is_loaded=True,
        )

    items = graph.get("evidence_items", [])
    item = next(
        (i for i in items if i.get("evidence_id") == evidence_id), None
    )
    if item is None:
        return AgentPanelResponse(
            question=question,
            response_kind="evidence_detail",
            answer_text="Evidence {} not found.".format(evidence_id),
            referenced_evidence_ids=[evidence_id],
            is_loaded=True,
        )

    lines = ["## Evidence: {}".format(evidence_id), ""]
    lines.append("- source_type: {}".format(item.get("source_type", "")))
    lines.append("- file_path: {}".format(item.get("file_path", "")))
    lines.append(
        "- lines: {}-{}".format(
            item.get("start_line", ""), item.get("end_line", "")
        )
    )
    lines.append("- symbol: {}".format(item.get("symbol") or "(none)"))
    lines.append(
        "- strength: {}".format(item.get("evidence_strength", ""))
    )
    lines.append(
        "- summary: {}".format(item.get("excerpt_summary", ""))
    )

    return AgentPanelResponse(
        question=question,
        response_kind="evidence_detail",
        answer_text="\n".join(lines),
        referenced_evidence_ids=[evidence_id],
        is_loaded=True,
    )


def _build_node_map(graph: dict[str, Any]) -> dict[str, str]:  # pyright: ignore[reportExplicitAny]
    """Map node_id -> label from graph.nodes."""
    mapping: dict[str, str] = {}
    for node in graph.get("nodes", []):
        nid = node.get("node_id", "")
        label = node.get("label", "")
        if nid:
            mapping[nid] = label
    return mapping
