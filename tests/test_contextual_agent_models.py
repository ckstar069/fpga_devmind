"""Tests for contextual_agent_models module (T027).

Pure Python — no PySide6, no pipeline execution.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.contextual_agent_models import query_selected_node


def _make_project_bundle(tmp: Path) -> Path:
    """Write a minimal project bundle to *tmp*."""
    tmp.mkdir(parents=True, exist_ok=True)
    graph = {
        "schema_version": "project-understanding-0.1",
        "project_id": "test_project",
        "nodes": [
            {"node_id": "P", "label": "test_project", "kind": "project"},
            {
                "node_id": "C_peak",
                "label": "peak_idx",
                "kind": "concept",
                "confidence": "supported",
            },
            {
                "node_id": "C_cfo",
                "label": "cfo",
                "kind": "concept",
                "confidence": "unknown",
            },
            {
                "node_id": "CL_peak",
                "label": "MC_peak_001",
                "kind": "mapping_claim",
                "confidence": "supported",
                "concept": "peak_idx",
                "bridge_kind": "naming_plus_structure",
                "evidence_ids": ["EV1", "EV2"],
            },
            {
                "node_id": "CL_cfo",
                "label": "MC_cfo_001",
                "kind": "mapping_claim",
                "confidence": "inferred",
                "concept": "cfo",
                "bridge_kind": "naming_only",
                "required_missing_evidence": ["RTL_body_evidence"],
            },
            {
                "node_id": "RTL_peak",
                "label": "peak_detect",
                "kind": "rtl_module",
                "file_path": "/rtl/peak.v",
            },
            {
                "node_id": "RTL_sig",
                "label": "peak_signal",
                "kind": "rtl_signal",
                "file_path": "/rtl/peak.v",
            },
        ],
        "edges": [
            {"edge_id": "E1", "from_node_id": "P", "to_node_id": "C_peak", "edge_type": "contains"},
            {"edge_id": "E2", "from_node_id": "P", "to_node_id": "C_cfo", "edge_type": "contains"},
            {"edge_id": "E3", "from_node_id": "C_peak", "to_node_id": "CL_peak", "edge_type": "has_claim"},
            {"edge_id": "E4", "from_node_id": "C_cfo", "to_node_id": "CL_cfo", "edge_type": "has_claim"},
            {"edge_id": "E5", "from_node_id": "CL_peak", "to_node_id": "RTL_peak", "edge_type": "realizes"},
            {"edge_id": "E6", "from_node_id": "CL_peak", "to_node_id": "RTL_sig", "edge_type": "realizes"},
            {"edge_id": "E7", "from_node_id": "C_peak", "to_node_id": "C_cfo", "edge_type": "shares_file", "confidence": "inferred"},
        ],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }
    metadata = {
        "schema_version": "p1b-project-run-metadata-0.1",
        "command": "p1b-trace-project",
        "project_root": "/tmp/test_project",
        "concepts_processed": ["peak_idx", "cfo"],
        "status": "ok",
        "mapping_claims": 2,
        "evidence_items": 2,
    }
    (tmp / "project_understanding_graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (tmp / "project_understanding_index.json").write_text(
        json.dumps({"concept_index": {}, "evidence_index": {}}),
        encoding="utf-8",
    )
    (tmp / "run_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    (tmp / "project_understanding.md").write_text("# Project\n", encoding="utf-8")
    (tmp / "project_understanding.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


class TestContextualAgentModels(unittest.TestCase):
    """Contextual node query tests."""

    def test_project_node(self) -> None:
        """Project node answer contains concept/claim/RTL counts."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "P", "project", "test_project", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("test_project", vm.answer_text)
            self.assertIn("概念", vm.answer_text)
            self.assertIn("Mapping claims", vm.answer_text)

    def test_concept_node(self) -> None:
        """Concept node answer contains related claims and RTL targets."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "C_peak", "concept", "peak_idx", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("MC_peak_001", vm.answer_text)
            self.assertIn("peak_detect", vm.answer_text)
            self.assertIn("supported", vm.answer_text)

    def test_concept_node_shares_file(self) -> None:
        """Concept node answer mentions shared edges."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "C_peak", "concept", "peak_idx", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("cfo", vm.answer_text)

    def test_mapping_claim_node(self) -> None:
        """Claim node answer contains confidence, bridge, realizes RTL."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "CL_peak", "mapping_claim", "MC_peak_001", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("MC_peak_001", vm.answer_text)
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("supported", vm.answer_text)
            self.assertIn("naming_plus_structure", vm.answer_text)
            self.assertIn("peak_detect", vm.answer_text)
            self.assertEqual(vm.referenced_claim_ids, ["MC_peak_001"])

    def test_claim_node_unknown(self) -> None:
        """Unknown claim lists missing evidence."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "CL_cfo", "mapping_claim", "MC_cfo_001", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("inferred", vm.answer_text)
            self.assertIn("RTL_body_evidence", vm.answer_text)

    def test_rtl_module_node(self) -> None:
        """RTL node answer contains related concepts and claims."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "RTL_peak", "rtl_module", "peak_detect", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("peak_detect", vm.answer_text)
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("MC_peak_001", vm.answer_text)

    def test_rtl_node_no_claims(self) -> None:
        """RTL signal node with no direct claims is handled."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "RTL_sig", "rtl_signal", "peak_signal", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("peak_signal", vm.answer_text)

    def test_unknown_node_id(self) -> None:
        """Unknown selected node id returns error without crashing."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "NONEXISTENT", "concept", "ghost", "解释当前节点"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("ghost", vm.answer_text)

    def test_empty_node_id(self) -> None:
        """Empty node id returns helpful error."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "", "", "", "解释当前节点"
            )
            self.assertFalse(vm.is_loaded)
            self.assertIn("未选中", vm.load_error or "")

    def test_non_project_bundle(self) -> None:
        """Non-project bundle returns type error."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            p = Path(tmp) / "art"
            p.mkdir()
            (p / "agent_runtime_trace.json").write_text(
                json.dumps({"task_id": "t"}), encoding="utf-8"
            )
            bundle = load_bundle(p)
            vm = query_selected_node(
                bundle, "X", "concept", "x", "解释当前节点"
            )
            self.assertFalse(vm.is_loaded)
            self.assertIn("project", vm.load_error or "")

    def test_contextual_answer_contains_node_label(self) -> None:
        """Answer always mentions the selected node label."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ctx_") as tmp:
            bundle_dir = _make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = query_selected_node(
                bundle, "C_peak", "concept", "peak_idx", "它为什么重要？"
            )
            self.assertTrue(vm.is_loaded)
            self.assertIn("peak_idx", vm.answer_text)


class TestSafety(unittest.TestCase):
    """Safety boundary checks."""

    def test_no_forbidden_imports(self) -> None:
        """Module does not import LLM/API/Vivado."""
        import fpga_devmind.desktop.contextual_agent_models as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        forbidden = ["openai", "anthropic", "requests", "vivado", "subprocess"]
        for word in forbidden:
            self.assertNotIn(
                word,
                source,
                "Forbidden import/keyword '{}' found".format(word),
            )


if __name__ == "__main__":
    unittest.main()
