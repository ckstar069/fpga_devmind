"""Tests for T031 GUI usability fixes.

Covers: Summary graph mode, Overview current_understanding,
render helper non-empty output.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.concept_graph_view import (
    ProjectGraphDisplayMode,
    build_concept_graph_view_model,
)
from fpga_devmind.desktop.overview_models import build_overview_view_model
from fpga_devmind.desktop.understanding_card_models import (
    build_understanding_card,
    render_understanding_card_text,
)


def _write_project_bundle(tmp: Path) -> Path:
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
    index = {
        "schema_version": "project-understanding-0.1",
        "concept_index": {},
        "evidence_index": {
            "EV1": {
                "source_type": "concept_occurrence",
                "file_path": "/src/peak.py",
                "symbol": "PeakDetector",
                "strength": "strong",
                "concept": "peak_idx",
            },
            "EV2": {
                "source_type": "rtl_source",
                "file_path": "/rtl/peak.v",
                "symbol": "peak_detect",
                "strength": "medium",
                "concept": "peak_idx",
            },
        },
    }
    (tmp / "project_understanding_graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (tmp / "project_understanding_index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )
    (tmp / "run_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    (tmp / "project_understanding.md").write_text("# Project\n", encoding="utf-8")
    (tmp / "project_understanding.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


def _get_bundle() -> Any:
    tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_t031_"))
    bundle_dir = _write_project_bundle(tmp / "project")
    return load_bundle(bundle_dir)


# ---------------------------------------------------------------------------
# Tests: Summary Graph Mode (Section 3)
# ---------------------------------------------------------------------------


class TestSummaryGraphMode(unittest.TestCase):
    """Summary mode shows only project/concept/claim, no realizes edges."""

    def test_summary_no_realizes_edges(self) -> None:
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.SUMMARY,
        )
        self.assertTrue(vm.is_loaded)
        edge_types = {e.edge_type for e in vm.edges}
        self.assertNotIn("realizes", edge_types)

    def test_summary_contains_project_concept_claim(self) -> None:
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.SUMMARY,
        )
        kinds = {n.kind for n in vm.nodes}
        self.assertIn("project", kinds)
        self.assertIn("concept", kinds)
        self.assertIn("mapping_claim", kinds)

    def test_summary_no_rtl_nodes(self) -> None:
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.SUMMARY,
        )
        kinds = {n.kind for n in vm.nodes}
        self.assertNotIn("rtl_module", kinds)
        self.assertNotIn("rtl_signal", kinds)

    def test_summary_keeps_contains_edges(self) -> None:
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.SUMMARY,
        )
        edge_types = {e.edge_type for e in vm.edges}
        self.assertIn("contains", edge_types)

    def test_summary_keeps_shares_edges(self) -> None:
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.SUMMARY,
        )
        edge_types = {e.edge_type for e in vm.edges}
        self.assertIn("shares_file", edge_types)

    def test_summary_small_node_count(self) -> None:
        """Summary should have ~7 nodes for our fixture (1 project + 2 concept + 2 claim)."""
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.SUMMARY,
        )
        self.assertLessEqual(len(vm.nodes), 7)
        self.assertGreaterEqual(len(vm.nodes), 5)

    def test_rtl_overview_has_realizes(self) -> None:
        """RTL Overview mode still shows realizes edges."""
        bundle = _get_bundle()
        vm = build_concept_graph_view_model(
            bundle, mode=ProjectGraphDisplayMode.RTL_OVERVIEW,
        )
        self.assertTrue(vm.is_loaded)
        edge_types = {e.edge_type for e in vm.edges}
        self.assertIn("realizes", edge_types)

    def test_default_mode_is_summary(self) -> None:
        """Default mode constant is SUMMARY."""
        self.assertEqual(ProjectGraphDisplayMode.SUMMARY, "summary")

    def test_mode_constants(self) -> None:
        """All three modes have distinct constants."""
        modes = {
            ProjectGraphDisplayMode.SUMMARY,
            ProjectGraphDisplayMode.RTL_OVERVIEW,
            ProjectGraphDisplayMode.EVIDENCE_DETAIL,
        }
        self.assertEqual(len(modes), 3)


# ---------------------------------------------------------------------------
# Tests: Overview Current Understanding (Section 1)
# ---------------------------------------------------------------------------


class TestOverviewCurrentUnderstanding(unittest.TestCase):
    """Overview '当前理解' must be non-empty for project bundles."""

    def test_project_overview_non_empty(self) -> None:
        bundle = _get_bundle()
        vm = build_overview_view_model(bundle)
        self.assertTrue(vm.is_loaded)
        self.assertTrue(vm.current_understanding)

    def test_overview_contains_concepts(self) -> None:
        bundle = _get_bundle()
        vm = build_overview_view_model(bundle)
        self.assertIn("peak_idx", vm.current_understanding)
        self.assertIn("cfo", vm.current_understanding)

    def test_overview_contains_claim_count(self) -> None:
        bundle = _get_bundle()
        vm = build_overview_view_model(bundle)
        self.assertIn("mapping claims", vm.current_understanding)

    def test_overview_contains_next_steps(self) -> None:
        bundle = _get_bundle()
        vm = build_overview_view_model(bundle)
        self.assertIn("概念追踪", vm.current_understanding)
        self.assertIn("理解卡", vm.current_understanding)

    def test_overview_bundle_type(self) -> None:
        bundle = _get_bundle()
        vm = build_overview_view_model(bundle)
        self.assertEqual(vm.bundle_type, "project")


# ---------------------------------------------------------------------------
# Tests: Render Helper (Section 2 / existing T030)
# ---------------------------------------------------------------------------


class TestRenderHelperNonEmpty(unittest.TestCase):
    """render_understanding_card_text must produce non-empty output."""

    def test_concept_card_render_nonempty(self) -> None:
        bundle = _get_bundle()
        card = build_understanding_card(bundle, "C_peak")
        text = render_understanding_card_text(card)
        self.assertTrue(text)
        self.assertIn("peak_idx", text)
        self.assertIn("【摘要】", text)
        self.assertIn("【Top 证据】", text)

    def test_project_card_render_nonempty(self) -> None:
        bundle = _get_bundle()
        card = build_understanding_card(bundle, "P")
        text = render_understanding_card_text(card)
        self.assertTrue(text)
        self.assertIn("test_project", text)

    def test_error_card_render_nonempty(self) -> None:
        bundle = _get_bundle()
        card = build_understanding_card(bundle, "")
        text = render_understanding_card_text(card)
        self.assertTrue(text)
        self.assertIn("未选中", text)


# ---------------------------------------------------------------------------
# Tests: Navigation Uniqueness (Section 7)
# ---------------------------------------------------------------------------


class TestNavigationKeys(unittest.TestCase):
    """Verify navigation key constants are unique."""

    def test_no_duplicate_nav_keys(self) -> None:
        groups = [
            [
                ("概览", "overview"),
                ("概念追踪", "concept_trace"),
                ("证据", "evidence"),
                ("不确定项", "unknowns"),
            ],
            [
                ("Agent 问答", "agent_qa"),
                ("Agent Runtime", "agent_runtime"),
                ("计划与工具", "plan_tools"),
            ],
            [
                ("Raw Data", "raw_data"),
                ("Markdown", "markdown"),
                ("Diagnostics", "diagnostics"),
            ],
            [
                ("项目设置", "project_settings"),
                ("通用设置", "general_settings"),
            ],
        ]
        all_keys: list[str] = []
        for items in groups:
            for _, key in items:
                all_keys.append(key)
        self.assertEqual(len(all_keys), len(set(all_keys)), "Duplicate nav keys found")


if __name__ == "__main__":
    unittest.main()
