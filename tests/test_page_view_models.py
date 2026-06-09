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
    PlanToolsPageState,
    build_evidence_page_view_model,
    build_unknowns_page_view_model,
    build_overview_metrics,
    build_agent_runtime_page_state,
    build_plan_tools_page_state,
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


def _write_project_bundle(tmp: Path) -> Path:
    """Write a minimal project bundle to *tmp*."""
    tmp.mkdir(parents=True, exist_ok=True)
    graph = {
        "schema_version": "project-understanding-0.1",
        "project_id": "test_project",
        "nodes": [
            {"node_id": "PUG_PROJECT", "label": "test_project", "kind": "project"},
            {
                "node_id": "PUG_CONCEPT_peak_idx",
                "label": "peak_idx",
                "kind": "concept",
                "confidence": "supported",
            },
            {
                "node_id": "PUG_CLAIM_peak_idx_MC_001",
                "label": "MC_001",
                "kind": "mapping_claim",
                "confidence": "supported",
                "concept": "peak_idx",
                "bridge_kind": "naming_plus_structure",
            },
            {
                "node_id": "PUG_RTL_peak_idx_N1",
                "label": "peak_detect",
                "kind": "rtl_module",
                "file_path": "/rtl/top.v",
            },
            {
                "node_id": "PUG_RTL_peak_sig",
                "label": "peak_signal",
                "kind": "rtl_signal",
                "file_path": "/rtl/top.v",
            },
        ],
        "edges": [
            {
                "edge_id": "E_PROJECT_peak_idx",
                "from_node_id": "PUG_PROJECT",
                "to_node_id": "PUG_CONCEPT_peak_idx",
                "edge_type": "contains",
            },
            {
                "edge_id": "E_peak_idx_claim",
                "from_node_id": "PUG_CONCEPT_peak_idx",
                "to_node_id": "PUG_CLAIM_peak_idx_MC_001",
                "edge_type": "has_claim",
            },
            {
                "edge_id": "E_realizes_1",
                "from_node_id": "PUG_CLAIM_peak_idx_MC_001",
                "to_node_id": "PUG_RTL_peak_idx_N1",
                "edge_type": "realizes",
            },
            {
                "edge_id": "E_realizes_2",
                "from_node_id": "PUG_CLAIM_peak_idx_MC_001",
                "to_node_id": "PUG_RTL_peak_sig",
                "edge_type": "realizes",
            },
        ],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }
    index = {
        "schema_version": "project-understanding-0.1",
        "concept_index": {"peak_idx": {"status": "ok", "claims": 1}},
        "evidence_index": {
            "EV_1": {
                "source_type": "concept_occurrence",
                "concept": "peak_idx",
                "file_path": "/src/peak.py",
                "symbol": "PeakDetector",
                "strength": "strong",
            }
        },
    }
    metadata = {
        "schema_version": "p1b-project-run-metadata-0.1",
        "command": "p1b-trace-project",
        "project_root": "/tmp/test_project",
        "concepts_processed": ["peak_idx"],
        "status": "ok",
        "mapping_claims": 1,
        "evidence_items": 1,
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

    def test_project_evidence_filter_by_concept(self) -> None:
        """Filtering by concept node shows only claims for that concept."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(
                bundle, selected_node_id="PUG_CONCEPT_peak_idx"
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.groups), 1)
            self.assertIn("peak_idx", vm.groups[0].title)

    def test_project_evidence_filter_by_claim(self) -> None:
        """Filtering by claim node shows only that claim."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(
                bundle, selected_node_id="PUG_CLAIM_peak_idx_MC_001"
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.groups), 1)
            self.assertIn("MC_001", vm.groups[0].title)

    def test_project_evidence_filter_by_rtl(self) -> None:
        """Filtering by RTL node shows claims realizing to it."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(
                bundle, selected_node_id="PUG_RTL_peak_idx_N1"
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.groups), 1)
            self.assertIn("MC_001", vm.groups[0].title)

    def test_project_evidence_filter_no_match(self) -> None:
        """Filtering by unrelated node returns empty groups."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_ev_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(
                bundle, selected_node_id="NONEXISTENT"
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.groups), 1)
            self.assertEqual(len(vm.groups[0].rows), 0)


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


class TestProjectEvidencePageViewModel(unittest.TestCase):
    """Project bundle evidence page tests — claim-centric grouping (T025)."""

    def test_project_evidence_groups_by_claim(self) -> None:
        """Project bundle groups evidence rows by mapping claim."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_proj_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.groups), 1)
            self.assertIn("Claim:", vm.groups[0].title)
            self.assertIn("MC_001", vm.groups[0].title)

    def test_claim_group_has_counts(self) -> None:
        """Claim group description shows L5/L6 and RTL evidence counts."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_proj_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            group = vm.groups[0]
            self.assertIn("L5/L6=1", group.description)
            self.assertIn("RTL=2", group.description)
            self.assertIn("bridge=naming_plus_structure", group.description)

    def test_evidence_row_mapping_correct(self) -> None:
        """Evidence rows map to the correct claim group with RTL + L5/L6 rows."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_proj_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_evidence_page_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            rows = vm.groups[0].rows
            # L5/L6 row from evidence_index.
            l5_l6 = [r for r in rows if r.source_type == "concept_occurrence"]
            self.assertEqual(len(l5_l6), 1)
            self.assertEqual(l5_l6[0].evidence_id, "EV_1")
            self.assertEqual(l5_l6[0].symbol, "PeakDetector")
            # RTL rows from realizes edges.
            rtl = [r for r in rows if r.source_type.startswith("rtl_")]
            self.assertEqual(len(rtl), 2)
            rtl_ids = {r.evidence_id for r in rtl}
            self.assertIn("PUG_RTL_peak_idx_N1", rtl_ids)
            self.assertIn("PUG_RTL_peak_sig", rtl_ids)


class TestProjectOverviewMetrics(unittest.TestCase):
    """Project bundle overview metrics tests."""

    def test_project_metrics(self) -> None:
        """Project bundle produces correct metric counts."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_proj_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            m = build_overview_metrics(bundle)
            self.assertTrue(m.is_loaded)
            self.assertEqual(m.mapping_claims, 1)
            self.assertEqual(m.rtl_objects, 2)
            self.assertEqual(m.unknowns, 0)


class TestProjectUnknownsPageViewModel(unittest.TestCase):
    """Project bundle unknowns page tests."""

    def test_project_unknowns_loaded(self) -> None:
        """Project bundle unknowns page loads successfully."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_proj_") as tmp:
            bundle_dir = _write_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_unknowns_page_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertIn("confirmed", vm.why_not_confirmed)


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


class TestPlanToolsPageState(unittest.TestCase):
    """Plan & Tools page state tests."""

    def test_empty_plan(self) -> None:
        """Empty plan preview text shows guidance message."""
        state = build_plan_tools_page_state("")
        self.assertFalse(state.has_plan)
        self.assertIn("Agent 问答页", state.display_text)

    def test_plan_present(self) -> None:
        """Non-empty plan preview text is passed through."""
        plan_text = "Intent: summary\n\n[S1] Read concept_trace_graph.json"
        state = build_plan_tools_page_state(plan_text)
        self.assertTrue(state.has_plan)
        self.assertEqual(state.display_text, plan_text)

    def test_plan_format(self) -> None:
        """Plan preview text contains expected sections."""
        plan_text = (
            "Intent: evidence\n"
            "\n"
            "[S1] Read concept_trace_graph.json\n"
            "[S2] Read concept_trace_index.json\n"
            "\n"
            "Safety Notes:\n"
            "  - No LLM semantic reasoning"
        )
        state = build_plan_tools_page_state(plan_text)
        self.assertTrue(state.has_plan)
        self.assertIn("Safety Notes", state.display_text)


if __name__ == "__main__":
    unittest.main()
