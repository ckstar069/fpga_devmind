"""Tests for overview_models module (T019).

Validates the OverviewViewModel builder, evidence/confidence summaries,
suggested questions, and format_concept_trace_summary formatter.

Pure Python — no PySide6, no LLM, no API.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    load_bundle,
)
from fpga_devmind.desktop.overview_models import (
    EvidenceStrengthSummary,
    MappingConfidenceSummary,
    OverviewViewModel,
    SuggestedQuestion,
    build_overview_view_model,
    format_concept_trace_summary,
    _increment_strength,
    _increment_confidence,
    _format_confidence_summary,
    _translate_confidence,
)
from fpga_devmind.desktop.trace_view_models import (
    ConceptTraceViewModel,
    ClaimRow,
    EvidenceRow,
    NodeRow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_p1b_graph(
    *,
    nodes: int = 2,
    evidence_items: int = 4,
    mapping_claims: int = 1,
) -> dict[str, Any]:
    """Build a minimal P1b concept_trace_graph dict for testing."""
    ns: list[dict[str, Any]] = []
    for i in range(nodes):
        ns.append(
            {
                "node_id": "N_{}".format(i),
                "label": "node_{}".format(i),
                "kind": ["stage_view", "rtl_module"][i % 2],
                "stage": "L6_resource_opt" if i % 2 == 0 else "RTL",
            }
        )

    evs: list[dict[str, Any]] = []
    for i in range(evidence_items):
        is_concept = i < evidence_items // 2
        evs.append(
            {
                "evidence_id": "EV_{}".format(i),
                "source_type": "p1b_concept" if is_concept else "p1b_rtl",
                "evidence_strength": ["strong", "medium", "weak", "unknown"][
                    i % 4
                ],
                "file_path": "/some/file_{}.py".format(i),
                "symbol": "sym_{}".format(i),
            }
        )

    claims: list[dict[str, Any]] = []
    for i in range(mapping_claims):
        claims.append(
            {
                "claim_id": "MC_{}".format(i),
                "concept": "peak_idx",
                "confidence": ["supported", "inferred", "unknown"][i % 3],
                "bridge_kind": "naming_plus_structure",
                "evidence_ids": ["EV_0", "EV_1"],
            }
        )

    return {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": ns,
        "edges": [],
        "mapping_claims": claims,
        "evidence_items": evs,
        "grounding_diagnostics": [],
        "uncertainty_notes": [
            {"note_id": "UN_0", "reason": "RTL 命名匹配但不唯一"}
        ],
    }


def _make_run_metadata() -> dict[str, Any]:
    return {
        "concept": "peak_idx",
        "project_root": "/some/project",
        "status": "ok",
        "mapping_claims": 1,
        "evidence_items": 4,
        "blocking_diagnostics": 0,
        "elapsed_seconds": 0.5,
    }


def _make_agent_runtime_trace() -> dict[str, Any]:
    return {
        "schema_version": "agent-runtime-contract-0.1",
        "task": {
            "task_id": "TASK_001",
            "question": "summary",
            "concept": "peak_idx",
            "artifact_bundle_path": "/some/p1b",
            "constraints": ["no_llm", "no_graph_write"],
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


def _write_p1b_bundle(tmp: Path) -> Path:
    """Write a minimal P1b bundle to *tmp* and return the path."""
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
        json.dumps(_make_run_metadata()), encoding="utf-8"
    )
    (tmp / "concept_trace.md").write_text("# Summary\n", encoding="utf-8")
    (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


def _write_agent_runtime_bundle(tmp: Path) -> Path:
    """Write a minimal agent_runtime bundle to *tmp* and return the path."""
    tmp.mkdir(parents=True, exist_ok=True)
    trace = _make_agent_runtime_trace()
    (tmp / "agent_runtime_trace.json").write_text(
        json.dumps(trace), encoding="utf-8"
    )
    (tmp / "answer.md").write_text("# Answer\n", encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildOverviewP1b(unittest.TestCase):
    """P1b bundle → OverviewViewModel."""

    def test_p1b_complete_bundle_loaded(self) -> None:
        """Complete P1b bundle produces is_loaded=True."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.bundle_type, "p1b")
            self.assertIsNone(vm.load_error)

    def test_p1b_current_understanding_contains_concept(self) -> None:
        """current_understanding mentions the concept name."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            self.assertIn("peak_idx", vm.current_understanding)

    def test_p1b_evidence_strength_counts(self) -> None:
        """L5/L6 and RTL evidence are correctly split and counted."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            total_l5 = vm.l5_l6_evidence_summary.total
            total_rtl = vm.rtl_evidence_summary.total
            self.assertEqual(total_l5 + total_rtl, 4)
            self.assertEqual(total_l5, 2)
            self.assertEqual(total_rtl, 2)

    def test_p1b_mapping_confidence(self) -> None:
        """Mapping confidence counts are correct."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            self.assertEqual(vm.mapping_confidence.total, 1)
            # First claim has confidence "supported" (index 0 % 3)
            self.assertEqual(vm.mapping_confidence.supported, 1)

    def test_p1b_suggested_questions(self) -> None:
        """P1b bundle provides 6 Chinese suggested questions."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            self.assertEqual(len(vm.suggested_questions), 6)
            for q in vm.suggested_questions:
                self.assertIsInstance(q, SuggestedQuestion)
                self.assertTrue(len(q.text) > 0)

    def test_p1b_unknown_limitations(self) -> None:
        """Uncertainty notes are collected into unknown_limitations."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            self.assertTrue(len(vm.unknown_limitations) >= 1)
            self.assertTrue(
                any(
                    "RTL" in lim or "不唯一" in lim
                    for lim in vm.unknown_limitations
                )
            )


class TestBuildOverviewAgentRuntime(unittest.TestCase):
    """Agent runtime bundle → OverviewViewModel."""

    def test_agent_runtime_overview(self) -> None:
        """Agent runtime bundle produces correct overview."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            bundle_dir = _write_agent_runtime_bundle(
                Path(tmp) / "agent"
            )
            bundle = load_bundle(bundle_dir)
            vm = build_overview_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.bundle_type, "agent_runtime")
            self.assertIn("TASK_001", vm.current_understanding)
            self.assertIn("summary", vm.current_understanding)
            self.assertEqual(len(vm.suggested_questions), 3)


class TestBuildOverviewEdgeCases(unittest.TestCase):
    """Edge cases for build_overview_view_model."""

    def test_incomplete_bundle_not_loaded(self) -> None:
        """Incomplete bundle produces is_loaded=False with error."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_ov_"
        ) as tmp:
            # Empty dir = unknown/incomplete
            bundle = load_bundle(Path(tmp) / "empty")
            vm = build_overview_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)

    def test_unknown_bundle_graceful(self) -> None:
        """Unknown bundle type with is_complete=True degrades gracefully."""
        bundle = ArtifactBundle(
            bundle_type="unknown",
            directory=Path("/tmp/unknown"),
            artifacts={},
            diagnostics=[],
            is_complete=True,  # bypass the incomplete check
        )
        vm = build_overview_view_model(bundle)
        self.assertFalse(vm.is_loaded)
        self.assertIn("Unknown", vm.load_error or "")


class TestFormatConceptTraceSummary(unittest.TestCase):
    """format_concept_trace_summary() three-section output."""

    def test_three_section_output(self) -> None:
        """Summary contains L5/L6, Mapping claims, and RTL sections."""
        vm = ConceptTraceViewModel(
            is_loaded=True,
            nodes=[
                NodeRow(
                    node_id="N1",
                    label="test",
                    kind="stage_view",
                    stage_id="L6",
                    confidence="supported",
                    evidence_count=1,
                    has_diagnostics=False,
                )
            ],
            edges=[],
            claims=[
                ClaimRow(
                    claim_id="MC_0",
                    concept_ref="peak_idx",
                    confidence="supported",
                    bridge_kind="naming_plus_structure",
                    l5_l6_evidence_count=1,
                    rtl_evidence_count=1,
                    bridge_evidence_count=2,
                    required_missing_evidence="",
                    diagnostic_count=0,
                )
            ],
            evidence=[
                EvidenceRow(
                    evidence_id="EV_0",
                    source_type="p1b_concept",
                    file_path="/some/file.py",
                    symbol="func_a",
                    evidence_strength="strong",
                    referenced_by_claims="MC_0",
                ),
                EvidenceRow(
                    evidence_id="EV_1",
                    source_type="p1b_rtl",
                    file_path="/some/rtl.v",
                    symbol="module_a",
                    evidence_strength="medium",
                    referenced_by_claims="MC_0",
                ),
            ],
            diagnostics=[],
        )
        result = format_concept_trace_summary(vm)
        self.assertIn("L5/L6", result)
        self.assertIn("映射声明", result)
        self.assertIn("RTL", result)
        self.assertIn("func_a", result)
        self.assertIn("module_a", result)

    def test_not_loaded_returns_error(self) -> None:
        """Not-loaded VM returns error text."""
        vm = ConceptTraceViewModel(
            is_loaded=False,
            load_error="Missing graph",
        )
        result = format_concept_trace_summary(vm)
        self.assertIn("Missing graph", result)


class TestHelperFunctions(unittest.TestCase):
    """Unit tests for helper functions."""

    def test_increment_strength(self) -> None:
        """_increment_strength updates correct counters."""
        ev = EvidenceStrengthSummary()
        _increment_strength(ev, "strong")
        _increment_strength(ev, "strong")
        _increment_strength(ev, "medium")
        _increment_strength(ev, "unknown")
        self.assertEqual(ev.strong, 2)
        self.assertEqual(ev.medium, 1)
        self.assertEqual(ev.unknown, 1)
        self.assertEqual(ev.total, 4)

    def test_increment_confidence(self) -> None:
        """_increment_confidence updates correct counters."""
        mc = MappingConfidenceSummary()
        _increment_confidence(mc, "supported")
        _increment_confidence(mc, "inferred")
        self.assertEqual(mc.supported, 1)
        self.assertEqual(mc.inferred, 1)
        self.assertEqual(mc.total, 2)

    def test_format_confidence_summary(self) -> None:
        """_format_confidence_summary produces readable string."""
        mc = MappingConfidenceSummary(supported=2, inferred=1, total=3)
        result = _format_confidence_summary(mc)
        self.assertIn("2 supported", result)
        self.assertIn("1 inferred", result)

    def test_translate_confidence(self) -> None:
        """_translate_confidence translates all known labels."""
        self.assertEqual(_translate_confidence("supported"), "有支持")
        self.assertEqual(_translate_confidence("inferred"), "推断")
        self.assertEqual(_translate_confidence("unknown"), "未知")
        self.assertEqual(_translate_confidence("confirmed"), "已确认")
        self.assertEqual(_translate_confidence("custom"), "custom")


if __name__ == "__main__":
    unittest.main()
