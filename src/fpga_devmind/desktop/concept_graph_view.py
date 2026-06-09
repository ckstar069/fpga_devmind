"""Concept graph visualiser using PySide6 QGraphicsView/QGraphicsScene (T022).

No Web/Mermaid renderer.  Deterministic layout: three columns
(L5/L6 → mapping → RTL) with fixed spacing.

This module is imported only when PySide6 is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_graph,
    get_project_graph,
)


# ---------------------------------------------------------------------------
# Colours by node kind
# ---------------------------------------------------------------------------

_COLOURS: dict[str, tuple[int, int, int]] = {
    "stage_view": (59, 130, 246),      # blue
    "concept": (59, 130, 246),
    "rtl_module": (34, 197, 94),       # green
    "rtl_always_block": (34, 197, 94),
    "rtl_signal": (250, 204, 21),      # yellow
    "rtl_assign": (250, 204, 21),
    "claim": (168, 85, 247),           # purple
    "bridge": (168, 85, 247),
    "unknown": (239, 68, 68),          # red
    "rtl_aggregate": (20, 184, 166),   # teal
}

_EDGE_CONFIDENCE: dict[str, QtCore.Qt.PenStyle] = {
    "supported": QtCore.Qt.PenStyle.SolidLine,
    "inferred": QtCore.Qt.PenStyle.DashLine,
    "unknown": QtCore.Qt.PenStyle.DotLine,
    "confirmed": QtCore.Qt.PenStyle.SolidLine,
}


# ---------------------------------------------------------------------------
# Graph item dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A node in the concept graph."""

    node_id: str = ""
    label: str = ""
    kind: str = ""
    stage: str = ""
    confidence: str = ""
    evidence_count: int = 0
    has_diagnostics: bool = False
    x: float = 0.0
    y: float = 0.0


@dataclass
class GraphEdge:
    """An edge in the concept graph."""

    edge_id: str = ""
    from_id: str = ""
    to_id: str = ""
    from_label: str = ""
    to_label: str = ""
    edge_type: str = ""
    confidence: str = ""
    evidence_count: int = 0  # aggregated from N raw edges (T025)


@dataclass
class GraphNodeDetail:
    """Detailed info for a selected graph node."""

    node_id: str = ""
    label: str = ""
    kind: str = ""
    stage: str = ""
    confidence: str = ""
    evidence_count: int = 0
    evidence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    has_diagnostics: bool = False
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class GraphEdgeDetail:
    """Detailed info for a selected graph edge."""

    edge_id: str = ""
    from_label: str = ""
    to_label: str = ""
    edge_type: str = ""
    confidence: str = ""
    claim_refs: list[str] = field(default_factory=list)


@dataclass
class GraphFilterState:
    """Filter state for the concept graph."""

    show_modules: bool = True
    show_signals: bool = True
    show_always_assign: bool = True
    show_weak_evidence: bool = True


class ProjectGraphDisplayMode:
    """Display modes for project-level concept graphs (T025/T031)."""

    SUMMARY = "summary"
    RTL_OVERVIEW = "rtl_overview"
    EVIDENCE_DETAIL = "evidence_detail"


@dataclass
class ConceptGraphViewModel:
    """View model for the concept graph visualiser."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    is_loaded: bool = False
    load_error: str | None = None
    filter_state: GraphFilterState = field(default_factory=GraphFilterState)
    mode: str = ProjectGraphDisplayMode.SUMMARY
    raw_node_count: int = 0
    hidden_node_count: int = 0
    aggregated_edge_count: int = 0
    selected_node_id: str = ""
    focus_enabled: bool = False
    focus_depth: int = 2

    def visible_nodes(self) -> list[GraphNode]:
        """Return nodes that pass the current filter and focus."""
        result: list[GraphNode] = []
        for node in self.nodes:
            kind = node.kind
            if kind in ("stage_view", "concept", "claim", "bridge"):
                result.append(node)
                continue
            if kind == "rtl_module":
                if self.filter_state.show_modules:
                    result.append(node)
                continue
            if kind == "rtl_signal":
                if self.filter_state.show_signals:
                    result.append(node)
                continue
            if kind in ("rtl_always_block", "rtl_assign"):
                if self.filter_state.show_always_assign:
                    result.append(node)
                continue
            if kind.startswith("rtl"):
                # catch-all for other rtl kinds
                if self.filter_state.show_modules:
                    result.append(node)
                continue
            result.append(node)

        if self.focus_enabled and self.selected_node_id:
            focused = self._focused_node_ids()
            result = [n for n in result if n.node_id in focused]

        return result

    def visible_edges(self) -> list[GraphEdge]:
        """Return edges whose both endpoints are visible."""
        visible_ids = {n.node_id for n in self.visible_nodes()}
        return [
            e for e in self.edges
            if e.from_id in visible_ids and e.to_id in visible_ids
        ]

    def _focused_node_ids(self) -> set[str]:
        """Compute node IDs within focus_depth of selected_node_id."""
        if not self.selected_node_id:
            return {n.node_id for n in self.nodes}

        # Build adjacency: node_id -> set of neighbor node_ids.
        adj: dict[str, set[str]] = {}
        for e in self.edges:
            src = e.from_id
            dst = e.to_id
            adj.setdefault(src, set()).add(dst)
            adj.setdefault(dst, set()).add(src)

        focused: set[str] = {self.selected_node_id}
        frontier: set[str] = {self.selected_node_id}

        for _ in range(self.focus_depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for neighbor in adj.get(nid, set()):
                    if neighbor not in focused:
                        focused.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        return focused


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_concept_graph_view_model(
    bundle: ArtifactBundle,
    mode: str = ProjectGraphDisplayMode.SUMMARY,
) -> ConceptGraphViewModel:
    """Build a concept graph view model from a P1b or project bundle.

    Creates a three-layer graph (Concept → Claim → RTL) by deriving
    virtual claim nodes from mapping_claims when the raw graph only has
    Concept → RTL edges.

    For project bundles, *mode* controls whether to show the aggregated
    Overview Graph (default) or the raw Evidence Detail Graph.

    Never raises.
    """
    if not bundle.is_complete:
        return ConceptGraphViewModel(
            is_loaded=False,
            load_error="Bundle incomplete.",
        )

    if bundle.bundle_type == "project":
        return _build_project_graph_vm(bundle, mode=mode)

    if bundle.bundle_type != "p1b":
        return ConceptGraphViewModel(
            is_loaded=False,
            load_error="Graph view available for P1b/project bundles only.",
        )

    graph = get_graph(bundle)
    if graph is None:
        return ConceptGraphViewModel(
            is_loaded=False,
            load_error="concept_trace_graph.json not found.",
        )

    node_map: dict[str, str] = {}
    for raw_node in graph.get("nodes", []):
        nid: str = raw_node.get("node_id", "")
        label: str = raw_node.get("label", nid)
        if nid:
            node_map[nid] = label

    # Build raw nodes.
    nodes: list[GraphNode] = []
    node_id_to_evidence_ids: dict[str, list[str]] = {}
    for raw_node in graph.get("nodes", []):
        nid = raw_node.get("node_id", "")
        evidence_ids = raw_node.get("evidence_ids", [])
        evidence_ids_list = evidence_ids if isinstance(evidence_ids, list) else []
        node_id_to_evidence_ids[nid] = evidence_ids_list
        evidence_count = len(evidence_ids_list)
        nodes.append(
            GraphNode(
                node_id=nid,
                label=raw_node.get("label", ""),
                kind=raw_node.get("kind", ""),
                stage=raw_node.get("stage", ""),
                confidence=raw_node.get("confidence", ""),
                evidence_count=evidence_count,
                has_diagnostics=raw_node.get("has_diagnostics", False),
            )
        )

    # Build raw edges.
    raw_edges: list[GraphEdge] = []
    for raw_edge in graph.get("edges", []):
        fid: str = raw_edge.get("from_node_id", "")
        tid: str = raw_edge.get("to_node_id", "")
        raw_edges.append(
            GraphEdge(
                edge_id=raw_edge.get("edge_id", ""),
                from_id=fid,
                to_id=tid,
                from_label=node_map.get(fid, fid) or "",
                to_label=node_map.get(tid, tid) or "",
                edge_type=raw_edge.get("edge_type", ""),
                confidence=raw_edge.get("confidence", ""),
            )
        )

    # Identify L5/L6 concept nodes and RTL nodes.
    l5_l6_ids = {
        n.node_id for n in nodes
        if n.kind in ("stage_view", "concept")
        or n.kind.startswith("l5") or n.kind.startswith("l6")
    }
    rtl_ids = {n.node_id for n in nodes if n.kind.startswith("rtl")}

    # Derive virtual claim nodes from mapping_claims for three-layer structure.
    claim_nodes: list[GraphNode] = []
    claim_edges: list[GraphEdge] = []
    claim_id_counter = 0

    # Build a map from claim_id to its evidence_ids for node enrichment.
    claim_evidence_map: dict[str, list[str]] = {}

    for claim in graph.get("mapping_claims", []):
        cid: str = claim.get("claim_id", "")
        if not cid:
            continue
        cnode_id = "__claim_{}".format(cid)
        conf = claim.get("confidence", "")
        bridge = claim.get("bridge_kind", "")
        label = cid if len(cid) <= 20 else cid[:17] + "..."

        # Collect evidence IDs from the claim.
        ev_ids: list[str] = []
        for key in ("evidence_ids", "l5_l6_evidence_ids", "rtl_evidence_ids", "bridge_evidence_ids"):
            vals = claim.get(key, [])
            if isinstance(vals, list):
                ev_ids.extend(vals)
        ev_ids = list(dict.fromkeys(ev_ids))  # deduplicate while preserving order
        claim_evidence_map[cid] = ev_ids

        claim_nodes.append(
            GraphNode(
                node_id=cnode_id,
                label=label,
                kind="claim",
                stage="",
                confidence=conf,
                evidence_count=len(ev_ids),
                has_diagnostics=False,
            )
        )
        claim_id_counter += 1

        # Find concept ref for the claim and create Concept → Claim edge.
        concept_ref: str = claim.get("concept", "") or claim.get("concept_ref", "")
        concept_node_id: str | None = None
        # Try to match concept_ref to an L5/L6 node label.
        if concept_ref:
            for n in nodes:
                if n.node_id in l5_l6_ids and n.label == concept_ref:
                    concept_node_id = n.node_id
                    break
            # Fallback: match by node_id prefix.
            if concept_node_id is None:
                for n in nodes:
                    if n.node_id in l5_l6_ids and concept_ref in n.label:
                        concept_node_id = n.node_id
                        break
        # Fallback: use first L5/L6 node.
        if concept_node_id is None and l5_l6_ids:
            concept_node_id = sorted(l5_l6_ids)[0]

        if concept_node_id is not None:
            claim_edges.append(
                GraphEdge(
                    edge_id="__ec_{}".format(cid),
                    from_id=concept_node_id,
                    to_id=cnode_id,
                    from_label=node_map.get(concept_node_id, concept_node_id) or "",
                    to_label=label,
                    edge_type="claims",
                    confidence=conf,
                )
            )

        # Find RTL evidence for this claim and create Claim → RTL edges.
        rtl_ev = claim.get("rtl_evidence_ids", [])
        rtl_ev_list = rtl_ev if isinstance(rtl_ev, list) else []
        # Also look at evidence_ids that point to RTL nodes.
        all_claim_ev = ev_ids
        for ev_id in all_claim_ev:
            # Find which node(s) reference this evidence.
            for n in nodes:
                if n.node_id in rtl_ids and ev_id in node_id_to_evidence_ids.get(n.node_id, []):
                    claim_edges.append(
                        GraphEdge(
                            edge_id="__cr_{}_{}".format(cid, n.node_id),
                            from_id=cnode_id,
                            to_id=n.node_id,
                            from_label=label,
                            to_label=node_map.get(n.node_id, n.node_id),
                            edge_type="realizes",
                            confidence=conf,
                        )
                    )

    # If we successfully built claim nodes and edges, use them.
    # Otherwise fall back to raw edges.
    if claim_nodes and claim_edges:
        nodes.extend(claim_nodes)
        edges = claim_edges
    else:
        edges = raw_edges

    # Simple three-column layout
    _layout_nodes(nodes)

    return ConceptGraphViewModel(
        nodes=nodes,
        edges=edges,
        is_loaded=True,
    )


def _build_project_graph_vm(
    bundle: ArtifactBundle,
    mode: str = ProjectGraphDisplayMode.SUMMARY,
) -> ConceptGraphViewModel:
    """Build a graph view model from a project-level understanding bundle.

    *mode*:
      - SUMMARY (default): only project → concepts → claims.
        No claim → RTL realizes edges.  Clean high-level view.
      - RTL_OVERVIEW: aggregate rtl_signal/always/assign/comment under their
        parent rtl_module/file nodes; show realizes edges.
      - EVIDENCE_DETAIL: show every raw node/edge.
    """
    graph = get_project_graph(bundle)
    if graph is None:
        return ConceptGraphViewModel(
            is_loaded=False,
            load_error="project_understanding_graph.json not found.",
        )

    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    # Always build the raw flat graph first.
    node_map: dict[str, str] = {}
    for raw_node in raw_nodes:
        nid = raw_node.get("node_id", "")
        label = raw_node.get("label", nid)
        if nid:
            node_map[nid] = label

    all_nodes: list[GraphNode] = []
    for raw_node in raw_nodes:
        nid = raw_node.get("node_id", "")
        evidence_ids = raw_node.get("evidence_ids", [])
        evidence_count = len(evidence_ids) if isinstance(evidence_ids, list) else 0
        all_nodes.append(
            GraphNode(
                node_id=nid,
                label=raw_node.get("label", ""),
                kind=raw_node.get("kind", ""),
                stage=raw_node.get("stage", ""),
                confidence=raw_node.get("confidence", ""),
                evidence_count=evidence_count,
                has_diagnostics=raw_node.get("has_diagnostics", False),
            )
        )

    all_edges: list[GraphEdge] = []
    node_ids = {n.node_id for n in all_nodes}
    dangling: list[str] = []
    for raw_edge in raw_edges:
        fid = raw_edge.get("from_node_id", "")
        tid = raw_edge.get("to_node_id", "")
        if fid not in node_ids or tid not in node_ids:
            dangling.append(raw_edge.get("edge_id", ""))
            continue
        all_edges.append(
            GraphEdge(
                edge_id=raw_edge.get("edge_id", ""),
                from_id=fid,
                to_id=tid,
                from_label=node_map.get(fid, fid) or "",
                to_label=node_map.get(tid, tid) or "",
                edge_type=raw_edge.get("edge_type", ""),
                confidence=raw_edge.get("confidence", ""),
            )
        )

    if mode == ProjectGraphDisplayMode.EVIDENCE_DETAIL:
        _layout_project_nodes(all_nodes)
        vm = ConceptGraphViewModel(
            nodes=all_nodes,
            edges=all_edges,
            is_loaded=True,
            mode=mode,
            raw_node_count=len(all_nodes),
            hidden_node_count=0,
            aggregated_edge_count=0,
        )
        if dangling:
            vm.load_error = "忽略 {} 条 dangling edge".format(len(dangling))
        return vm

    # ---------------------------------------------------------------
    # SUMMARY mode: project → concepts → claims only (T031)
    # ---------------------------------------------------------------
    if mode == ProjectGraphDisplayMode.SUMMARY:
        summary_kinds = {"project", "concept", "mapping_claim"}
        summary_nodes = [n for n in all_nodes if n.kind in summary_kinds]
        summary_node_ids = {n.node_id for n in summary_nodes}
        # Keep contains, has_claim, shares_file/shared_rtl_object edges.
        # Exclude realizes edges entirely.
        skip_edge_types = {"realizes"}
        summary_edges: list[GraphEdge] = []
        for e in all_edges:
            if e.edge_type in skip_edge_types:
                continue
            if e.from_id in summary_node_ids and e.to_id in summary_node_ids:
                summary_edges.append(e)
        # Use 3-column layout for summary (no RTL column).
        _layout_summary_nodes(summary_nodes)
        return ConceptGraphViewModel(
            nodes=summary_nodes,
            edges=summary_edges,
            is_loaded=True,
            mode=mode,
            raw_node_count=len(all_nodes),
            hidden_node_count=len(all_nodes) - len(summary_nodes),
            aggregated_edge_count=len(summary_edges),
        )

    # ---------------------------------------------------------------
    # RTL_OVERVIEW mode: aggregate fine-grained RTL nodes
    # ---------------------------------------------------------------
    hidden_kinds = {
        "rtl_signal",
        "rtl_always_block",
        "rtl_assign",
        "rtl_comment",
        "comment",
    }

    # Determine which nodes are hidden.
    hidden_node_ids: set[str] = set()
    for n in all_nodes:
        if n.kind in hidden_kinds or "comment" in n.kind:
            hidden_node_ids.add(n.node_id)
        elif n.confidence == "weak" and n.kind.startswith("rtl"):
            hidden_node_ids.add(n.node_id)

    # Build parent lookup for hidden nodes:
    #   1. contains edge from rtl_module -> hidden node
    #   2. file_path grouping (hidden node with same file_path as visible rtl_module)
    parent_of: dict[str, str] = {}

    # Step 1: direct contains edges.
    for e in all_edges:
        if e.edge_type == "contains":
            if e.to_id in hidden_node_ids:
                parent_of[e.to_id] = e.from_id

    # Step 2: file_path grouping for remaining hidden nodes.
    # Find visible rtl_module nodes and their file_paths.
    visible_rtl_modules: dict[str, str] = {}  # node_id -> file_path
    raw_node_by_id: dict[str, dict[str, Any]] = {}
    for raw_node in raw_nodes:
        nid = raw_node.get("node_id", "")
        if nid:
            raw_node_by_id[nid] = raw_node
        kind = raw_node.get("kind", "")
        if kind == "rtl_module" and nid not in hidden_node_ids:
            fp = raw_node.get("file_path", "")
            if fp:
                visible_rtl_modules[nid] = fp

    for hid in hidden_node_ids:
        if hid in parent_of:
            continue
        hidden_raw = raw_node_by_id.get(hid, {})
        h_fp = hidden_raw.get("file_path", "")
        # Try to match by file_path to a visible rtl_module.
        matched = False
        if h_fp:
            for vid, vfp in visible_rtl_modules.items():
                if vfp == h_fp:
                    parent_of[hid] = vid
                    matched = True
                    break
        # Fallback: create an aggregate node for unclassified hidden nodes.
        if not matched:
            agg_id = "__agg_unclassified_{}".format(hid)
            parent_of[hid] = agg_id

    # Create aggregate nodes for unclassified hidden nodes.
    # Group unclassified hidden nodes by their aggregate ID.
    unclassified_groups: dict[str, list[str]] = {}
    for hid, pid in parent_of.items():
        if pid.startswith("__agg_"):
            unclassified_groups.setdefault(pid, []).append(hid)

    # Build final visible node list.
    visible_nodes: list[GraphNode] = []
    for n in all_nodes:
        if n.node_id not in hidden_node_ids:
            visible_nodes.append(n)

    # Add aggregate nodes for unclassified groups.
    for agg_id, hids in unclassified_groups.items():
        # Use basename of first hidden node's file_path as label.
        first_fp = raw_node_by_id.get(hids[0], {}).get("file_path", "")
        label = first_fp.split("/")[-1] if first_fp else "未分类"
        total_ev: list[str] = []
        for h in hids:
            ev = raw_node_by_id.get(h, {}).get("evidence_ids", [])
            if isinstance(ev, list):
                total_ev.extend(ev)
        total_ev_count = len(total_ev)
        visible_nodes.append(
            GraphNode(
                node_id=agg_id,
                label=label,
                kind="rtl_aggregate",
                stage="RTL",
                confidence="inferred",
                evidence_count=total_ev_count,
                has_diagnostics=False,
            )
        )

    # Build visible edges with aggregation.
    visible_node_ids = {n.node_id for n in visible_nodes}
    edge_key_counts: dict[tuple[str, str, str], int] = {}
    for e in all_edges:
        src = e.from_id
        dst = e.to_id
        etype = e.edge_type

        # Skip contains edges from module to hidden (module is now aggregate parent).
        if etype == "contains" and dst in hidden_node_ids:
            continue

        # Remap hidden endpoints to their aggregate parent.
        if src in hidden_node_ids:
            src = parent_of.get(src, src)
        if dst in hidden_node_ids:
            dst = parent_of.get(dst, dst)

        # Skip if both endpoints ended up the same.
        if src == dst:
            continue

        # Skip if any endpoint is not visible.
        if src not in visible_node_ids or dst not in visible_node_ids:
            continue

        key = (src, dst, etype)
        edge_key_counts[key] = edge_key_counts.get(key, 0) + 1

    visible_edges: list[GraphEdge] = []
    for (src, dst, etype), count in edge_key_counts.items():
        visible_edges.append(
            GraphEdge(
                edge_id="__agg_{}_{}_{}".format(src, dst, etype),
                from_id=src,
                to_id=dst,
                from_label=node_map.get(src, src) or "",
                to_label=node_map.get(dst, dst) or "",
                edge_type=etype,
                confidence="inferred" if etype in ("shares_file", "shares_rtl_object") else "supported",
                evidence_count=count,
            )
        )

    _layout_project_nodes(visible_nodes)

    vm = ConceptGraphViewModel(
        nodes=visible_nodes,
        edges=visible_edges,
        is_loaded=True,
        mode=mode,
        raw_node_count=len(all_nodes),
        hidden_node_count=len(hidden_node_ids),
        aggregated_edge_count=len(visible_edges),
    )
    if dangling:
        vm.load_error = "忽略 {} 条 dangling edge".format(len(dangling))
    return vm


def _layout_summary_nodes(nodes: list[GraphNode]) -> None:
    """Assign (x, y) positions for the Summary 3-column layout.

    Columns: project(0) → concept(1) → mapping_claim(2).
    No RTL column — keeps the graph clean and readable.
    """
    project: list[GraphNode] = []
    concepts: list[GraphNode] = []
    claims: list[GraphNode] = []

    for node in nodes:
        kind = node.kind
        if kind == "project":
            project.append(node)
        elif kind == "concept":
            concepts.append(node)
        elif kind in ("mapping_claim", "claim"):
            claims.append(node)

    col_width = 240
    row_height = 60
    margin = 40

    def _place_column(column: list[GraphNode], col_idx: int) -> None:
        x = margin + col_idx * col_width
        for i, node in enumerate(column):
            node.x = x
            node.y = margin + i * row_height

    _place_column(project, 0)
    _place_column(concepts, 1)
    _place_column(claims, 2)


def _layout_project_nodes(nodes: list[GraphNode]) -> None:
    """Assign (x, y) positions using a four-column layout.

    Columns: project(0) → concept(1) → mapping_claim(2) → rtl(3).
    """
    project: list[GraphNode] = []
    concepts: list[GraphNode] = []
    claims: list[GraphNode] = []
    rtl: list[GraphNode] = []
    other: list[GraphNode] = []

    for node in nodes:
        kind = node.kind
        if kind == "project":
            project.append(node)
        elif kind == "concept":
            concepts.append(node)
        elif kind in ("mapping_claim", "claim"):
            claims.append(node)
        elif kind.startswith("rtl") or kind == "rtl_aggregate":
            rtl.append(node)
        else:
            other.append(node)

    col_width = 240
    row_height = 60
    margin = 40

    def _place_column(column: list[GraphNode], col_idx: int) -> None:
        x = margin + col_idx * col_width
        for i, node in enumerate(column):
            node.x = x
            node.y = margin + i * row_height

    _place_column(project, 0)
    _place_column(concepts, 1)
    _place_column(claims, 2)
    _place_column(rtl, 3)
    _place_column(other, 1)


def _layout_nodes(nodes: list[GraphNode]) -> None:
    """Assign (x, y) positions using a simple three-column layout."""
    l5_l6: list[GraphNode] = []
    rtl: list[GraphNode] = []
    bridge: list[GraphNode] = []
    other: list[GraphNode] = []

    for node in nodes:
        kind = node.kind
        if kind in ("stage_view", "concept") or kind.startswith("l5") or kind.startswith("l6"):
            l5_l6.append(node)
        elif kind.startswith("rtl"):
            rtl.append(node)
        elif kind in ("claim", "bridge"):
            bridge.append(node)
        else:
            other.append(node)

    col_width = 240
    row_height = 60
    margin = 40

    def _place_column(column: list[GraphNode], col_idx: int) -> None:
        x = margin + col_idx * col_width
        for i, node in enumerate(column):
            node.x = x
            node.y = margin + i * row_height

    _place_column(l5_l6, 0)
    _place_column(bridge, 1)
    _place_column(rtl, 2)
    _place_column(other, 1)


# ---------------------------------------------------------------------------
# QGraphicsScene builder
# ---------------------------------------------------------------------------


class ConceptGraphScene(QtWidgets.QGraphicsScene):
    """QGraphicsScene that renders a ConceptGraphViewModel."""

    node_clicked = QtCore.Signal(GraphNode)
    """Emitted when a node is clicked."""

    def __init__(self) -> None:
        super().__init__()
        self._vm: ConceptGraphViewModel | None = None
        self._node_items: dict[str, QtWidgets.QGraphicsItem] = {}

    def set_view_model(self, vm: ConceptGraphViewModel) -> None:
        """Render the given view model respecting filters."""
        self.clear()
        self._node_items.clear()
        self._vm = vm

        if not vm.is_loaded:
            text = self.addText(vm.load_error or "无法加载图数据")
            text.setDefaultTextColor(QtGui.QColor(150, 150, 150))
            return

        visible_nodes = vm.visible_nodes()
        visible_edges = vm.visible_edges()

        # Draw edges first (behind nodes)
        for edge in visible_edges:
            self._add_edge(edge)

        # Draw nodes
        for node in visible_nodes:
            self._add_node(node)

        # Set scene rect
        if visible_nodes:
            max_x = max(n.x for n in visible_nodes) + 120
            max_y = max(n.y for n in visible_nodes) + 80
            self.setSceneRect(0, 0, max(max_x, 800), max(max_y, 400))

    def _add_node(self, node: GraphNode) -> None:
        """Add a node ellipse with label."""
        size = 80
        x = node.x - size / 2
        y = node.y - size / 2

        ellipse = QtWidgets.QGraphicsEllipseItem(x, y, size, size)
        r, g, b = _COLOURS.get(node.kind, (150, 150, 150))
        brush = QtGui.QBrush(QtGui.QColor(r, g, b))
        ellipse.setBrush(brush)
        pen = QtGui.QPen(QtGui.QColor(60, 60, 60))
        pen.setWidth(2)
        ellipse.setPen(pen)
        ellipse.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        # Store node data on the item for click handling
        ellipse.setData(0, node.node_id)
        ellipse.setAcceptHoverEvents(True)

        self.addItem(ellipse)
        self._node_items[node.node_id] = ellipse

        # Label
        label_text = node.label if len(node.label) <= 14 else node.label[:11] + "..."
        text = self.addText(label_text)
        text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(9)
        text.setFont(font)
        text.setPos(node.x - text.boundingRect().width() / 2, node.y - 10)

        # Kind label below
        kind_text = self.addText(node.kind)
        kind_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
        kind_font = QtGui.QFont()
        kind_font.setPointSize(7)
        kind_text.setFont(kind_font)
        kind_text.setPos(node.x - kind_text.boundingRect().width() / 2, node.y + 12)

        # Confidence badge
        if node.confidence:
            conf_colour = {
                "supported": "#22c55e",
                "inferred": "#f59e0b",
                "unknown": "#ef4444",
                "confirmed": "#3b82f6",
            }.get(node.confidence, "#999999")
            conf_text = self.addText(node.confidence)
            conf_text.setDefaultTextColor(QtGui.QColor(conf_colour))
            conf_font = QtGui.QFont()
            conf_font.setPointSize(7)
            conf_text.setFont(conf_font)
            conf_text.setPos(node.x - conf_text.boundingRect().width() / 2, node.y + 28)

        # Click handler via event filter or override
        ellipse.mousePressEvent = lambda _evt, n=node: self.node_clicked.emit(n)

    def _add_edge(self, edge: GraphEdge) -> None:
        """Add a line between two nodes."""
        from_node = next((n for n in (self._vm.nodes if self._vm else []) if n.node_id == edge.from_id), None)
        to_node = next((n for n in (self._vm.nodes if self._vm else []) if n.node_id == edge.to_id), None)

        if from_node is None or to_node is None:
            return

        line = QtWidgets.QGraphicsLineItem(
            from_node.x, from_node.y, to_node.x, to_node.y
        )
        pen = QtGui.QPen(QtGui.QColor(120, 120, 120))
        pen.setWidth(1)
        pen.setStyle(
            _EDGE_CONFIDENCE.get(edge.confidence, QtCore.Qt.PenStyle.SolidLine)
        )
        line.setPen(pen)
        line.setZValue(-1)
        self.addItem(line)

        # Edge label
        label_text = edge.edge_type
        if edge.evidence_count > 1:
            label_text += " · {}".format(edge.evidence_count)
        if label_text:
            mid_x = (from_node.x + to_node.x) / 2
            mid_y = (from_node.y + to_node.y) / 2
            label = self.addText(label_text)
            label.setDefaultTextColor(QtGui.QColor(100, 100, 100))
            label_font = QtGui.QFont()
            label_font.setPointSize(7)
            label.setFont(label_font)
            label.setPos(mid_x - label.boundingRect().width() / 2, mid_y - 10)


# ---------------------------------------------------------------------------
# Detail builders
# ---------------------------------------------------------------------------


def build_node_detail(
    node_id: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> GraphNodeDetail | None:
    """Build a GraphNodeDetail from graph data for the given node_id."""
    if graph is None:
        return None

    for raw_node in graph.get("nodes", []):
        if raw_node.get("node_id") == node_id:
            evidence_ids = raw_node.get("evidence_ids", [])
            ev_list = evidence_ids if isinstance(evidence_ids, list) else []
            return GraphNodeDetail(
                node_id=node_id,
                label=raw_node.get("label", ""),
                kind=raw_node.get("kind", ""),
                stage=raw_node.get("stage", ""),
                confidence=raw_node.get("confidence", ""),
                evidence_count=len(ev_list),
                evidence_ids=ev_list,
                claim_ids=[],
                has_diagnostics=raw_node.get("has_diagnostics", False),
                diagnostics=[],
            )

    # Check if this is a virtual claim node.
    if node_id.startswith("__claim_"):
        claim_id = node_id[8:]
        for claim in graph.get("mapping_claims", []):
            if claim.get("claim_id") == claim_id:
                ev_ids: list[str] = []
                for key in (
                    "evidence_ids",
                    "l5_l6_evidence_ids",
                    "rtl_evidence_ids",
                    "bridge_evidence_ids",
                ):
                    vals = claim.get(key, [])
                    if isinstance(vals, list):
                        ev_ids.extend(vals)
                ev_ids = list(dict.fromkeys(ev_ids))  # deduplicate while preserving order
                return GraphNodeDetail(
                    node_id=node_id,
                    label=claim_id,
                    kind="claim",
                    stage="",
                    confidence=claim.get("confidence", ""),
                    evidence_count=len(ev_ids),
                    evidence_ids=ev_ids,
                    claim_ids=[claim_id],
                    has_diagnostics=False,
                    diagnostics=[],
                )

    # Aggregate node: build detail from raw graph children.
    if node_id.startswith("__agg_"):
        # Find hidden nodes whose parent is this aggregate.
        children: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
        for raw_node in graph.get("nodes", []):
            nid = raw_node.get("node_id", "")
            if not nid:
                continue
            # Heuristic: if the aggregate ID contains the hidden node ID.
            if nid in node_id or node_id.endswith(nid):
                children.append(raw_node)
        if not children:
            # Fallback: search by file_path match.
            pass
        total_ev: list[str] = []
        for c in children:
            ev = c.get("evidence_ids", [])
            if isinstance(ev, list):
                total_ev.extend(ev)
        return GraphNodeDetail(
            node_id=node_id,
            label="聚合节点",
            kind="rtl_aggregate",
            stage="RTL",
            confidence="inferred",
            evidence_count=len(total_ev),
            evidence_ids=total_ev,
            claim_ids=[],
            has_diagnostics=False,
            diagnostics=[],
        )

    return None


def build_edge_detail(
    edge_id: str,
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
) -> GraphEdgeDetail | None:
    """Build a GraphEdgeDetail from graph data for the given edge_id."""
    if graph is None:
        return None

    node_map = {}
    for raw_node in graph.get("nodes", []):
        nid = raw_node.get("node_id", "")
        label = raw_node.get("label", "")
        if nid:
            node_map[nid] = label

    for raw_edge in graph.get("edges", []):
        if raw_edge.get("edge_id") == edge_id:
            fid = raw_edge.get("from_node_id", "")
            tid = raw_edge.get("to_node_id", "")
            return GraphEdgeDetail(
                edge_id=edge_id,
                from_label=node_map.get(fid, fid) or "",
                to_label=node_map.get(tid, tid) or "",
                edge_type=raw_edge.get("edge_type", ""),
                confidence=raw_edge.get("confidence", ""),
                claim_refs=[],
            )

    # Aggregated edge: parse from synthetic edge_id __agg_{src}_{dst}_{etype}.
    if edge_id.startswith("__agg_"):
        rest = edge_id[6:]  # strip "__agg_"
        parts = rest.rsplit("_", 2)
        if len(parts) == 3:
            src, dst, etype = parts
            return GraphEdgeDetail(
                edge_id=edge_id,
                from_label=node_map.get(src, src) or "",
                to_label=node_map.get(dst, dst) or "",
                edge_type=etype,
                confidence="inferred" if etype in ("shares_file", "shares_rtl_object") else "supported",
                claim_refs=[],
            )

    return None
