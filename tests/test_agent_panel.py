"""Tests for agent_panel_models module (T021).

Validates deterministic local Agent query produces non-empty answers
for common question types.

Pure Python — no PySide6, no LLM, no API.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.agent_panel_models import (
    AgentPanelResponse,
    query_artifact_bundle,
)
from fpga_devmind.desktop.artifact_loader import load_bundle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_p1b_graph() -> dict[str, Any]:
    """Build a minimal P1b concept_trace_graph dict."""
    return {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": [
            {
                "node_id": "N1",
                "label": "peak_idx",
                "kind": "stage_view",
                "stage": "L6",
            },
            {
                "node_id": "N2",
                "label": "rtl_peak",
                "kind": "rtl_module",
                "stage": "RTL",
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
        "grounding_diagnostics": [
            {"severity": "warning", "message": "One-sided evidence"}
        ],
        "uncertainty_notes": [
            {"note_id": "UN_0", "reason": "RTL 命名匹配但不唯一"}
        ],
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


class TestAgentQuerySummary(unittest.TestCase):
    """Agent query for summary question."""

    def test_summary_answer_not_empty(self) -> None:
        """Summary question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "概况")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)
            self.assertIn("peak_idx", vm.answer_text)


class TestAgentQueryClaims(unittest.TestCase):
    """Agent query for claims question."""

    def test_claims_answer_not_empty(self) -> None:
        """Claims question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "映射")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)
            self.assertIn("MC_peak_idx_001", vm.answer_text)


class TestAgentQueryEvidence(unittest.TestCase):
    """Agent query for evidence question."""

    def test_evidence_answer_not_empty(self) -> None:
        """Evidence question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "证据")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)
            self.assertIn("EV_0", vm.answer_text)


class TestAgentQueryDiagnostics(unittest.TestCase):
    """Agent query for diagnostics question."""

    def test_diagnostics_answer_not_empty(self) -> None:
        """Diagnostics question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "诊断")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)


class TestAgentQueryNodes(unittest.TestCase):
    """Agent query for nodes question."""

    def test_nodes_answer_not_empty(self) -> None:
        """Nodes question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "节点")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)
            self.assertIn("N1", vm.answer_text)


class TestAgentQueryEdges(unittest.TestCase):
    """Agent query for edges question."""

    def test_edges_answer_not_empty(self) -> None:
        """Edges question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "边")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)


class TestAgentQueryUnknown(unittest.TestCase):
    """Agent query for unknown/uncertainty question."""

    def test_unknown_answer_not_empty(self) -> None:
        """Unknown question produces non-empty answer."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "不确定")
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.answer_text) > 0)


class TestAgentQueryNoBundle(unittest.TestCase):
    """Agent query without bundle."""

    def test_no_bundle_shows_error(self) -> None:
        """Query without bundle returns helpful error."""
        bundle = load_bundle(Path("/nonexistent"))
        vm = query_artifact_bundle(bundle, "概况")
        self.assertFalse(vm.is_loaded)
        self.assertIsNotNone(vm.load_error)


class TestAgentQueryUnsupported(unittest.TestCase):
    """Agent query for unsupported question."""

    def test_unsupported_question(self) -> None:
        """Unsupported question returns fallback."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "xyz_not_supported_123")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unsupported")
            self.assertIn("not supported", vm.answer_text.lower())


class TestAgentQueryEvidenceSourceTypes(unittest.TestCase):
    """Agent evidence query with concept_occurrence / rtl_source."""

    def test_evidence_with_new_source_types(self) -> None:
        """Evidence items with concept_occurrence / rtl_source are found."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_agent_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = query_artifact_bundle(bundle, "证据")
            self.assertTrue(vm.is_loaded)
            self.assertIn("EV_0", vm.answer_text)
            self.assertIn("EV_1", vm.answer_text)
            self.assertIn("concept_occurrence", vm.answer_text)
            self.assertIn("rtl_source", vm.answer_text)


if __name__ == "__main__":
    unittest.main()
