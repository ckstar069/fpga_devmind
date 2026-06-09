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


@dataclass
class ConceptGraphViewModel:
    """View model for the concept graph visualiser."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    is_loaded: bool = False
    load_error: str | None = None
    filter_state: GraphFilterState = field(default_factory=GraphFilterState)

    def visible_nodes(self) -> list[GraphNode]:
        """Return nodes that pass the current filter."""
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
        return result

    def visible_edges(self) -> list[GraphEdge]:
        """Return edges whose both endpoints are visible."""
        visible_ids = {n.node_id for n in self.visible_nodes()}
        return [
            e for e in self.edges
            if e.from_id in visible_ids and e.to_id in visible_ids
        ]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_concept_graph_view_model(
    bundle: ArtifactBundle,
) -> ConceptGraphViewModel:
    """Build a concept graph view model from a P1b bundle.

    Creates a three-layer graph (Concept → Claim → RTL) by deriving
    virtual claim nodes from mapping_claims when the raw graph only has
    Concept → RTL edges.

    Never raises.
    """
    if not bundle.is_complete:
        return ConceptGraphViewModel(
            is_loaded=False,
            load_error="Bundle incomplete.",
        )

    if bundle.bundle_type != "p1b":
        return ConceptGraphViewModel(
            is_loaded=False,
            load_error="Graph view available for P1b bundles only.",
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
                from_label=node_map.get(fid, fid),
                to_label=node_map.get(tid, tid),
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
                    from_label=node_map.get(concept_node_id, concept_node_id),
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
        if edge.edge_type:
            mid_x = (from_node.x + to_node.x) / 2
            mid_y = (from_node.y + to_node.y) / 2
            label = self.addText(edge.edge_type)
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
                from_label=node_map.get(fid, fid),
                to_label=node_map.get(tid, tid),
                edge_type=raw_edge.get("edge_type", ""),
                confidence=raw_edge.get("confidence", ""),
                claim_refs=[],
            )

    return None
