"""Tests for concept_graph_view module (T022).

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
    }


def _write_p1b_bundle(tmp: Path) -> Path:
    """Write a minimal P1b bundle to *tmp*."""
    tmp.mkdir(parents=True, exist_ok=True)
    graph = _make_p1b_graph()
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
                "mapping_claims": 0,
                "evidence_items": 0,
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
