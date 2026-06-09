"""Tests for page_view_models module (T020).

Validates EvidencePageViewModel, UnknownsPageViewModel, OverviewMetrics,
and AgentRuntimePageState builders.

Pure Python — no PySide6, no LLM, no API.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.page_view_models import (
    EvidenceGroup,
    EvidencePageViewModel,
    UnknownsPageViewModel,
    OverviewMetrics,
    AgentRuntimePageState,
    build_evidence_page_view_model,
    build_unknowns_page_view_model,
    build_overview_metrics,
    build_agent_runtime_page_state,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_p1b_graph() -> dict[str, Any]:
    """Build a minimal P1b concept_trace_graph dict."""
    return {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": [
            {"node_id": "N1", "label": "peak_idx", "kind": "stage_view", "stage": "L6"},
            {"node_id": "N2", "label": "rtl_peak", "kind": "rtl_module", "stage": "RTL"},
            {"node_id": "N3", "label": "rtl_always", "kind": "rtl_always_block", "stage": "RTL"},
        ],
        "edges": [],
        "mapping_claims": [
            {
                "claim_id": "MC_0",
                "concept": "peak_idx",
                "confidence": "supported",
                "bridge_kind": "naming_plus_structure",
                "evidence_ids": ["EV_0", "EV_1"],
            },
            {
                "claim_id": "MC_1",
                "concept": "peak_idx",
                "confidence": "unknown",
                "bridge_kind": "naming_only",
                "evidence_ids": [],
                "required_missing_evidence": ["RTL_body_evidence"],
            },
        ],
        "evidence_items": [
            {
                "evidence_id": "EV_0",
                "source_type": "p1b_concept",
                "evidence_strength": "strong",
                "file_path": "/some/file.py",
                "symbol": "func_a",
            },
            {
                "evidence_id": "EV_1",
                "source_type": "p1b_rtl",
                "evidence_strength": "medium",
                "file_path": "/some/rtl.v",
                "symbol": "module_a",
            },
            {
                "evidence_id": "EV_2",
                "source_type": "p1b_concept",
                "evidence_strength": "weak",
                "file_path": "/some/other.py",
                "symbol": "func_b",
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
                "mapping_claims": 2,
                "evidence_items": 3,
                "blocking_diagnostics": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp / "concept_trace.md").write_text("# Summary\n", encoding="utf-8")
    (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


def _write_agent_runtime_bundle(tmp: Path) -> Path:
    """Write a minimal agent_runtime bundle to *tmp*."""
    tmp.mkdir(parents=True, exist_ok=True)
    trace = {
        "schema_version": "agent-runtime-contract-0.1",
        "task": {
            "task_id": "TASK_001",
            "question": "summary",
            "concept": "peak_idx",
            "artifact_bundle_path": "/some/p1b",
            "constraints": [],
        },
        "steps": [
            {"step_id": "S1", "section": "observation"},
            {"step_id": "S2", "section": "plan"},
        ],
        "answers": [
            {"answer_id": "A1", "answer_text": "It is about peak_idx."}
        ],
        "graph_write_proposals": [],
    }
    (tmp / "agent_runtime_trace.json").write_text(
        json.dumps(trace), encoding="utf-8"
    )
    (tmp / "answer.md").write_text("# Answer\n", encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvidencePageViewModel(unittest.TestCase):
    """Evidence page builder tests."""

    def test_p1b_three_groups(self) -> None:
        """P1b bundle produces L5/L6, RTL, and Bridge groups."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.groups), 2)  # L5/L6 and RTL
            titles = [g.title for g in vm.groups]
            self.assertIn("L5/L6 代码证据", titles)
            self.assertIn("RTL 证据", titles)

    def test_p1b_group_counts(self) -> None:
        """Evidence rows are correctly split between groups."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(bundle)
            for g in vm.groups:
                if "L5/L6" in g.title:
                    self.assertEqual(len(g.rows), 2)  # EV_0, EV_2
                elif "RTL" in g.title:
                    self.assertEqual(len(g.rows), 1)  # EV_1

    def test_incomplete_bundle(self) -> None:
        """Incomplete bundle produces is_loaded=False."""
        bundle = load_bundle(Path("/nonexistent"))
        vm = build_evidence_page_view_model(bundle)
        self.assertFalse(vm.is_loaded)
        self.assertIsNotNone(vm.load_error)

    def test_non_p1b_bundle(self) -> None:
        """Non-P1b bundle shows helpful message."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_agent_runtime_bundle(Path(tmp) / "art")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("agent_runtime", vm.load_error or "")


class TestUnknownsPageViewModel(unittest.TestCase):
    """Unknowns page builder tests."""

    def test_p1b_limitations(self) -> None:
        """P1b bundle extracts limitations from unknown claims."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_un_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_unknowns_page_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertTrue(len(vm.limitations) > 0)
            self.assertTrue(
                any("MC_1" in lim for lim in vm.limitations)
            )

    def test_p1b_uncertainty_notes(self) -> None:
        """P1b bundle extracts uncertainty notes."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_un_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_unknowns_page_view_model(bundle)
            self.assertTrue(len(vm.uncertainty_notes) > 0)
            self.assertTrue(
                any("不唯一" in note for note in vm.uncertainty_notes)
            )

    def test_p1b_why_not_confirmed(self) -> None:
        """Why-not-confirmed explanation is present."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_un_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_unknowns_page_view_model(bundle)
            self.assertIn("confirmed", vm.why_not_confirmed)
            self.assertIn("人工 review", vm.why_not_confirmed)

    def test_non_p1b_bundle(self) -> None:
        """Non-P1b bundle shows helpful message."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_un_") as tmp:
            bundle_dir = _write_agent_runtime_bundle(Path(tmp) / "art")
            bundle = load_bundle(bundle_dir)
            vm = build_unknowns_page_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("agent_runtime", vm.load_error or "")


class TestOverviewMetrics(unittest.TestCase):
    """Overview metrics builder tests."""

    def test_p1b_metrics(self) -> None:
        """P1b bundle produces correct metric counts."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_met_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            m = build_overview_metrics(bundle)
            self.assertTrue(m.is_loaded)
            self.assertEqual(m.mapping_claims, 2)
            self.assertEqual(m.evidence_items, 3)
            self.assertEqual(m.rtl_objects, 2)  # rtl_module + rtl_always_block
            self.assertEqual(m.unknowns, 1)

    def test_agent_runtime_metrics(self) -> None:
        """Agent runtime bundle produces metrics from trace."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_met_") as tmp:
            bundle_dir = _write_agent_runtime_bundle(Path(tmp) / "art")
            bundle = load_bundle(bundle_dir)
            m = build_overview_metrics(bundle)
            self.assertTrue(m.is_loaded)
            self.assertEqual(m.mapping_claims, 1)  # 1 answer
            self.assertEqual(m.evidence_items, 2)  # 2 steps

    def test_incomplete_bundle(self) -> None:
        """Incomplete bundle produces is_loaded=False."""
        bundle = load_bundle(Path("/nonexistent"))
        m = build_overview_metrics(bundle)
        self.assertFalse(m.is_loaded)


class TestAgentRuntimePageState(unittest.TestCase):
    """Agent Runtime page state tests."""

    def test_p1b_bundle_not_visible(self) -> None:
        """P1b bundle makes Agent Runtime page not visible with message."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_art_") as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            state = build_agent_runtime_page_state(bundle)
            self.assertFalse(state.is_visible)
            self.assertIn("p1b", state.message)
            self.assertIn("desktop-sample-run", state.message)

    def test_agent_runtime_bundle_visible(self) -> None:
        """Agent runtime bundle makes page visible and loaded."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_art_") as tmp:
            bundle_dir = _write_agent_runtime_bundle(Path(tmp) / "art")
            bundle = load_bundle(bundle_dir)
            state = build_agent_runtime_page_state(bundle)
            self.assertTrue(state.is_visible)
            self.assertTrue(state.is_loaded)
            self.assertTrue(state.has_trace)

    def test_no_bundle(self) -> None:
        """No bundle shows prompt message."""
        from fpga_devmind.desktop.artifact_loader import ArtifactBundle
        empty = ArtifactBundle(
            bundle_type="unknown",
            directory=Path("/tmp"),
            is_complete=False,
        )
        state = build_agent_runtime_page_state(empty)
        self.assertFalse(state.is_visible)
        self.assertIn("加载", state.message)


class TestSafety(unittest.TestCase):
    """Safety boundary checks."""

    def test_no_forbidden_imports(self) -> None:
        """Module does not import LLM/API/Vivado modules."""
        import fpga_devmind.desktop.page_view_models as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        forbidden = [
            "openai",
            "anthropic",
            "requests",
            "vivado",
            "subprocess",
        ]
        for word in forbidden:
            self.assertNotIn(
                word,
                source,
                "Forbidden import/keyword '{}' found".format(word),
            )


if __name__ == "__main__":
    unittest.main()
