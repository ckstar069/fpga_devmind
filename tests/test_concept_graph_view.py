"""Tests for concept_graph_view module (T022/T023).

Pure Python — no PySide6 required for view model tests.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.concept_graph_view import (
    GraphEdge,
    GraphNode,
    build_concept_graph_view_model,
    build_node_detail,
)
from fpga_devmind.desktop.artifact_loader import load_bundle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_p1b_graph() -> dict[str, Any]:
    """Build a P1b concept_trace_graph with multiple node kinds."""
    return {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": [
            {
                "node_id": "N1",
                "label": "peak_idx",
                "kind": "stage_view",
                "stage": "L6",
                "confidence": "supported",
                "evidence_ids": ["EV_0"],
            },
            {
                "node_id": "N2",
                "label": "rtl_peak",
                "kind": "rtl_module",
                "stage": "RTL",
                "confidence": "inferred",
                "evidence_ids": ["EV_1"],
            },
            {
                "node_id": "N3",
                "label": "MC_peak",
                "kind": "claim",
                "stage": "",
                "confidence": "supported",
                "evidence_ids": [],
            },
        ],
        "edges": [
            {
                "edge_id": "E1",
                "from_node_id": "N1",
                "to_node_id": "N3",
                "edge_type": "maps_to",
                "confidence": "supported",
            },
            {
                "edge_id": "E2",
                "from_node_id": "N3",
                "to_node_id": "N2",
                "edge_type": "realizes",
                "confidence": "inferred",
            },
        ],
        "mapping_claims": [],
        "evidence_items": [],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }


def _make_p1b_graph_with_claims() -> dict[str, Any]:
    """Build a P1b graph with mapping_claims for three-layer tests."""
    return {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": [
            {
                "node_id": "N1",
                "label": "peak_idx",
                "kind": "stage_view",
                "stage": "L6",
                "confidence": "supported",
                "evidence_ids": ["EV_0"],
            },
            {
                "node_id": "N2",
                "label": "rtl_peak",
                "kind": "rtl_module",
                "stage": "RTL",
                "confidence": "inferred",
                "evidence_ids": ["EV_1"],
            },
        ],
        "edges": [
            {
                "edge_id": "E1",
                "from_node_id": "N1",
                "to_node_id": "N2",
                "edge_type": "bridge",
                "confidence": "supported",
            }
        ],
        "mapping_claims": [
            {
                "claim_id": "MC_peak_idx_001",
                "concept": "peak_idx",
                "confidence": "supported",
                "bridge_kind": "calculation_role",
                "evidence_ids": ["EV_0", "EV_1"],
                "l5_l6_evidence_ids": ["EV_0"],
                "rtl_evidence_ids": ["EV_1"],
            }
        ],
        "evidence_items": [
            {
                "evidence_id": "EV_0",
                "source_type": "concept_occurrence",
                "evidence_strength": "strong",
                "file_path": "/some/file.py",
                "symbol": "func_a",
            },
            {
                "evidence_id": "EV_1",
                "source_type": "rtl_source",
                "evidence_strength": "medium",
                "file_path": "/some/rtl.v",
                "symbol": "module_a",
            },
        ],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }


def _write_p1b_bundle(tmp: Path, graph: dict[str, Any] | None = None) -> Path:
    """Write a minimal P1b bundle to *tmp*."""
    tmp.mkdir(parents=True, exist_ok=True)
    graph = graph or _make_p1b_graph()
    (tmp / "concept_trace_graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (tmp / "concept_trace_index.json").write_text(
        json.dumps({"claim_index": {}, "evidence_index": {}}),
        encoding="utf-8",
    )
    (tmp / "grounding_report.json").write_text(
        json.dumps(
            {
                "blocking_diagnostics": [],
                "non_blocking_diagnostics": [],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp / "run_metadata.json").write_text(
        json.dumps(
            {
                "concept": "peak_idx",
                "project_root": "/some/project",
                "status": "ok",
                "mapping_claims": 1,
                "evidence_items": 2,
                "blocking_diagnostics": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp / "concept_trace.md").write_text("# Summary\n", encoding="utf-8")
    (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConceptGraphViewModel(unittest.TestCase):
    """Build concept graph view model from bundle."""

    def test_p1b_bundle_loaded(self) -> None:
        """P1b bundle produces loaded graph view model."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertIsNone(vm.load_error)

    def test_nodes_extracted(self) -> None:
        """All nodes are extracted with correct fields."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            node_ids = {n.node_id for n in vm.nodes}
            self.assertEqual(node_ids, {"N1", "N2", "N3"})

    def test_node_fields(self) -> None:
        """Node fields are populated from graph data."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            n1 = next(n for n in vm.nodes if n.node_id == "N1")
            self.assertEqual(n1.label, "peak_idx")
            self.assertEqual(n1.kind, "stage_view")
            self.assertEqual(n1.confidence, "supported")
            self.assertEqual(n1.evidence_count, 1)

    def test_edges_extracted(self) -> None:
        """All edges are extracted with correct fields."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            self.assertEqual(len(vm.edges), 2)
            e1 = next(e for e in vm.edges if e.edge_id == "E1")
            self.assertEqual(e1.from_id, "N1")
            self.assertEqual(e1.to_id, "N3")
            self.assertEqual(e1.edge_type, "maps_to")
            self.assertEqual(e1.confidence, "supported")

    def test_layout_columns(self) -> None:
        """L5/L6 nodes in col 0, bridge/claim in col 1, RTL in col 2."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            n1 = next(n for n in vm.nodes if n.node_id == "N1")
            n2 = next(n for n in vm.nodes if n.node_id == "N2")
            n3 = next(n for n in vm.nodes if n.node_id == "N3")
            # L5/L6 (stage_view) in column 0
            self.assertEqual(n1.x, 40)
            # RTL in column 2
            self.assertEqual(n2.x, 40 + 2 * 240)
            # Claim in column 1
            self.assertEqual(n3.x, 40 + 1 * 240)

    def test_incomplete_bundle(self) -> None:
        """Incomplete bundle returns not loaded."""
        bundle = load_bundle(Path("/nonexistent"))
        vm = build_concept_graph_view_model(bundle)
        self.assertFalse(vm.is_loaded)
        self.assertIsNotNone(vm.load_error)

    def test_non_p1b_bundle(self) -> None:
        """Non-P1b bundle returns type error."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "agent_runtime"
            d.mkdir()
            (d / "agent_runtime_trace.json").write_text(
                json.dumps({"task_id": "t"}), encoding="utf-8"
            )
            bundle = load_bundle(d)
            vm = build_concept_graph_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("P1b", vm.load_error or "")


class TestConceptGraphThreeLayer(unittest.TestCase):
    """Virtual claim nodes create Concept -> Claim -> RTL structure."""

    def test_virtual_claim_node_created(self) -> None:
        """mapping_claims produce virtual claim nodes."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(
                Path(tmp) / "p1b", graph=_make_p1b_graph_with_claims()
            )
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            claim_nodes = [n for n in vm.nodes if n.kind == "claim"]
            self.assertEqual(len(claim_nodes), 1)
            self.assertIn("MC_peak_idx_001", claim_nodes[0].label)

    def test_concept_to_claim_edge(self) -> None:
        """Concept -> Claim edge exists."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(
                Path(tmp) / "p1b", graph=_make_p1b_graph_with_claims()
            )
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            ec_edges = [e for e in vm.edges if e.edge_type == "claims"]
            self.assertEqual(len(ec_edges), 1)
            self.assertTrue(ec_edges[0].from_id.startswith("N"))
            self.assertTrue(ec_edges[0].to_id.startswith("__claim_"))

    def test_claim_to_rtl_edge(self) -> None:
        """Claim -> RTL edge exists."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(
                Path(tmp) / "p1b", graph=_make_p1b_graph_with_claims()
            )
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            cr_edges = [e for e in vm.edges if e.edge_type == "realizes"]
            self.assertEqual(len(cr_edges), 1)
            self.assertTrue(cr_edges[0].from_id.startswith("__claim_"))
            self.assertTrue(cr_edges[0].to_id.startswith("N"))


class TestGraphFilterState(unittest.TestCase):
    """Graph filtering hides/shows nodes by kind."""

    def test_filter_hides_rtl_modules(self) -> None:
        """Unchecking show_modules hides rtl_module nodes."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            vm.filter_state.show_modules = False
            visible = vm.visible_nodes()
            visible_kinds = {n.kind for n in visible}
            self.assertNotIn("rtl_module", visible_kinds)
            self.assertIn("stage_view", visible_kinds)

    def test_filter_hides_rtl_signals(self) -> None:
        """Unchecking show_signals hides rtl_signal nodes."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            vm.filter_state.show_signals = False
            visible = vm.visible_nodes()
            visible_kinds = {n.kind for n in visible}
            self.assertNotIn("rtl_signal", visible_kinds)

    def test_claim_nodes_always_visible(self) -> None:
        """Claim nodes are always visible regardless of filters."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_concept_graph_view_model(bundle)
            vm.filter_state.show_modules = False
            vm.filter_state.show_signals = False
            vm.filter_state.show_always_assign = False
            visible = vm.visible_nodes()
            visible_kinds = {n.kind for n in visible}
            self.assertIn("claim", visible_kinds)


class TestGraphNodeDetail(unittest.TestCase):
    """Node detail builder from graph data."""

    def test_node_detail_from_raw_node(self) -> None:
        """build_node_detail returns info for raw graph nodes."""
        graph = _make_p1b_graph()
        detail = build_node_detail("N1", graph)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.node_id, "N1")
        self.assertEqual(detail.label, "peak_idx")
        self.assertEqual(detail.kind, "stage_view")
        self.assertEqual(detail.evidence_count, 1)
        self.assertIn("EV_0", detail.evidence_ids)

    def test_node_detail_from_virtual_claim(self) -> None:
        """build_node_detail returns info for virtual claim nodes."""
        graph = _make_p1b_graph_with_claims()
        detail = build_node_detail("__claim_MC_peak_idx_001", graph)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.kind, "claim")
        self.assertEqual(detail.confidence, "supported")
        self.assertEqual(detail.label, "MC_peak_idx_001")

    def test_node_detail_missing_returns_none(self) -> None:
        """build_node_detail returns None for unknown node_id."""
        graph = _make_p1b_graph()
        detail = build_node_detail("NONEXISTENT", graph)
        self.assertIsNone(detail)


class TestGraphDataClasses(unittest.TestCase):
    """GraphNode and GraphEdge defaults."""

    def test_graph_node_defaults(self) -> None:
        """GraphNode has sensible defaults."""
        n = GraphNode()
        self.assertEqual(n.node_id, "")
        self.assertEqual(n.evidence_count, 0)
        self.assertFalse(n.has_diagnostics)

    def test_graph_edge_defaults(self) -> None:
        """GraphEdge has sensible defaults."""
        e = GraphEdge()
        self.assertEqual(e.edge_id, "")
        self.assertEqual(e.confidence, "")


if __name__ == "__main__":
    unittest.main()
