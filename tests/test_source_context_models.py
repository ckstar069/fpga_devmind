"""Tests for source_context_models module (T029).

Pure Python — no PySide6, no file mutation.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.source_context_models import (
    SourceContextViewModel,
    build_source_context_for_evidence,
    _mask_secrets,
    _resolve_line_range,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_project_bundle_with_evidence(tmp: Path) -> Path:
    """Write a project bundle with evidence items that have line ranges."""
    tmp.mkdir(parents=True, exist_ok=True)
    # Write a fake source file.
    src_file = tmp / "src.py"
    lines = ["# line {}\n".format(i) for i in range(1, 101)]
    src_file.write_text("".join(lines), encoding="utf-8")

    graph = {
        "schema_version": "project-understanding-0.1",
        "project_id": "test_project",
        "nodes": [
            {"node_id": "P", "label": "test_project", "kind": "project"},
            {
                "node_id": "C",
                "label": "peak_idx",
                "kind": "concept",
                "confidence": "supported",
            },
            {
                "node_id": "CL",
                "label": "MC_001",
                "kind": "mapping_claim",
                "confidence": "supported",
                "concept": "peak_idx",
                "bridge_kind": "naming_plus_structure",
                "evidence_ids": ["E:p1b_concept:abc:10-20:001"],
            },
            {
                "node_id": "R",
                "label": "rtl_peak",
                "kind": "rtl_module",
                "file_path": str(src_file),
            },
        ],
        "edges": [
            {"edge_id": "E1", "from_node_id": "P", "to_node_id": "C", "edge_type": "contains"},
            {"edge_id": "E2", "from_node_id": "C", "to_node_id": "CL", "edge_type": "has_claim"},
            {"edge_id": "E3", "from_node_id": "CL", "to_node_id": "R", "edge_type": "realizes"},
        ],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }
    index = {
        "schema_version": "project-understanding-0.1",
        "concept_index": {},
        "evidence_index": {
            "E:p1b_concept:abc:10-20:001": {
                "source_type": "concept_occurrence",
                "file_path": str(src_file),
                "symbol": "PeakDetector",
                "strength": "strong",
                "concept": "peak_idx",
            },
            "E:no_lines_X002": {
                "source_type": "concept_occurrence",
                "file_path": str(src_file),
                "symbol": "NoLine",
                "strength": "medium",
                "concept": "peak_idx",
            },
        },
    }
    metadata = {
        "schema_version": "p1b-project-run-metadata-0.1",
        "status": "ok",
        "mapping_claims": 1,
        "evidence_items": 2,
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
    (tmp / "project_understanding.md").write_text("#\n", encoding="utf-8")
    (tmp / "project_understanding.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


def _write_p1b_bundle_with_evidence(tmp: Path) -> Path:
    """Write a P1b bundle with evidence_items containing start_line/end_line."""
    tmp.mkdir(parents=True, exist_ok=True)
    src_file = tmp / "peak.py"
    lines = ["# line {}\n".format(i) for i in range(1, 51)]
    src_file.write_text("".join(lines), encoding="utf-8")

    graph = {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": [
            {
                "node_id": "N1",
                "label": "peak_idx",
                "kind": "stage_view",
                "stage": "L6",
                "evidence_ids": ["EV_0"],
            },
        ],
        "edges": [],
        "mapping_claims": [
            {
                "claim_id": "MC_0",
                "concept": "peak_idx",
                "confidence": "supported",
                "bridge_kind": "naming_plus_structure",
                "evidence_ids": ["EV_0"],
            },
        ],
        "evidence_items": {
            "EV_0": {
                "evidence_id": "EV_0",
                "source_type": "concept_occurrence",
                "file_path": str(src_file),
                "symbol": "PeakDetector",
                "strength": "strong",
                "start_line": 10,
                "end_line": 15,
            },
        },
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }
    (tmp / "concept_trace_graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (tmp / "concept_trace_index.json").write_text(
        json.dumps({"index": {}}), encoding="utf-8"
    )
    (tmp / "agent_understanding.md").write_text("#\n", encoding="utf-8")
    (tmp / "grounding_report.json").write_text(
        json.dumps({"report": []}), encoding="utf-8"
    )
    (tmp / "run_metadata.json").write_text(
        json.dumps({"status": "ok"}), encoding="utf-8"
    )
    (tmp / "concept_trace.md").write_text("#\n", encoding="utf-8")
    (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveLineRange(unittest.TestCase):
    """Line range parsing from evidence_id and metadata."""

    def test_direct_start_end_priority(self) -> None:
        """Direct start_line/end_line fields take priority."""
        meta = {"start_line": 5, "end_line": 10}
        s, e = _resolve_line_range(meta, "E:99-100:X")
        self.assertEqual(s, 5)
        self.assertEqual(e, 10)

    def test_parse_range_from_evidence_id(self) -> None:
        """Range embedded in evidence_id is parsed."""
        meta = {}
        s, e = _resolve_line_range(meta, "E:p1b_concept:abc:399-473:001")
        self.assertEqual(s, 399)
        self.assertEqual(e, 473)

    def test_parse_single_line_from_evidence_id(self) -> None:
        """Single line embedded in evidence_id is parsed."""
        meta = {}
        s, e = _resolve_line_range(meta, "E:abc:47:002")
        self.assertEqual(s, 47)
        self.assertEqual(e, 47)

    def test_no_line_info_returns_zero(self) -> None:
        """No line info returns (0, 0)."""
        meta = {}
        s, e = _resolve_line_range(meta, "E:abc")
        self.assertEqual(s, 0)
        self.assertEqual(e, 0)


class TestMaskSecrets(unittest.TestCase):
    """Secret masking in source code display."""

    def test_api_key_masked(self) -> None:
        """API key value is partially masked."""
        text = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz"'
        result = _mask_secrets(text)
        self.assertIn("***", result)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", result)

    def test_password_masked(self) -> None:
        """Password value is partially masked."""
        text = 'password = "supersecret123"'
        result = _mask_secrets(text)
        self.assertIn("***", result)
        self.assertNotIn("supersecret123", result)

    def test_no_secret_unchanged(self) -> None:
        """Lines without secrets are unchanged."""
        text = "x = 42"
        self.assertEqual(_mask_secrets(text), text)


class TestBuildSourceContextProject(unittest.TestCase):
    """Source context for project bundles."""

    def test_project_evidence_with_line_range(self) -> None:
        """Evidence with line range shows context lines."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_project_bundle_with_evidence(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_source_context_for_evidence(
                bundle, "E:p1b_concept:abc:10-20:001", context_lines=3
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.start_line, 10)
            self.assertEqual(vm.end_line, 20)
            self.assertEqual(vm.symbol, "PeakDetector")
            self.assertEqual(vm.evidence_strength, "strong")
            # Context should include lines around evidence.
            self.assertGreaterEqual(vm.context_start_line, 7)
            self.assertLessEqual(vm.context_end_line, 23)
            # Evidence lines marked.
            ev_lines = [sl for sl in vm.lines if sl.is_evidence_line]
            self.assertGreater(len(ev_lines), 0)

    def test_project_evidence_no_line_range(self) -> None:
        """Evidence without line range shows file start with limitation."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_project_bundle_with_evidence(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_source_context_for_evidence(
                bundle, "E:no_lines_X002", context_lines=3
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.start_line, 0)
            self.assertEqual(vm.end_line, 0)
            self.assertIn("未提供行号", vm.limitations)

    def test_missing_file_returns_error(self) -> None:
        """Missing file returns load_error without crashing."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_project_bundle_with_evidence(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            # Evidence pointing to nonexistent file.
            vm = build_source_context_for_evidence(
                bundle, "E:nonexistent:003", context_lines=3
            )
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)

    def test_max_context_lines_limit(self) -> None:
        """Context is capped at max lines."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_project_bundle_with_evidence(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_source_context_for_evidence(
                bundle, "E:p1b_concept:abc:10-20:001", context_lines=100
            )
            self.assertTrue(vm.is_loaded)
            self.assertLessEqual(len(vm.lines), 80)

    def test_empty_evidence_id(self) -> None:
        """Empty evidence ID returns error."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_project_bundle_with_evidence(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_source_context_for_evidence(bundle, "")
            self.assertFalse(vm.is_loaded)

    def test_incomplete_bundle(self) -> None:
        """Incomplete bundle returns error."""
        bundle = load_bundle(Path("/nonexistent"))
        vm = build_source_context_for_evidence(bundle, "E:X")
        self.assertFalse(vm.is_loaded)


class TestBuildSourceContextP1b(unittest.TestCase):
    """Source context for P1b bundles."""

    def test_p1b_evidence_direct_lines(self) -> None:
        """P1b evidence with direct start_line/end_line works."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle_with_evidence(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)
            vm = build_source_context_for_evidence(
                bundle, "EV_0", context_lines=3
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.start_line, 10)
            self.assertEqual(vm.end_line, 15)
            self.assertEqual(vm.symbol, "PeakDetector")
            ev_lines = [sl for sl in vm.lines if sl.is_evidence_line]
            self.assertGreater(len(ev_lines), 0)


class TestSourceLineModel(unittest.TestCase):
    """SourceLine dataclass tests."""

    def test_evidence_line_marked(self) -> None:
        """Evidence lines within start/end range are marked."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_project_bundle_with_evidence(Path(tmp) / "project")
            bundle = load_bundle(bundle_dir)
            vm = build_source_context_for_evidence(
                bundle, "E:p1b_concept:abc:10-20:001", context_lines=0
            )
            for sl in vm.lines:
                if 10 <= sl.line_no <= 20:
                    self.assertTrue(sl.is_evidence_line)
                else:
                    self.assertFalse(sl.is_evidence_line)


class TestSafety(unittest.TestCase):
    """Safety boundary checks."""

    def test_no_forbidden_imports(self) -> None:
        """Module does not import LLM/API/Vivado."""
        import fpga_devmind.desktop.source_context_models as mod

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
