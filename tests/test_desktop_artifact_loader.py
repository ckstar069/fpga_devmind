"""Tests for desktop artifact loader (T009).

Tests the pure-data artifact loading layer without PySide6.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.artifact_loader import (
    ArtifactDiagnostic,
    P1B_REQUIRED_ARTIFACTS,
    detect_bundle_type,
    get_graph,
    get_index,
    get_markdown,
    get_mermaid,
    get_project_graph,
    get_run_metadata,
    load_bundle,
    validate_bundle,
)


class TestBundleDetection(unittest.TestCase):

    def test_empty_directory_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_bundle_type(Path(tmp)), "unknown")

    def test_file_instead_of_directory_is_unknown(self):
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            self.assertEqual(detect_bundle_type(Path(f.name)), "unknown")

    def test_p1b_bundle_detected_by_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            self.assertEqual(detect_bundle_type(p), "p1b")

    def test_p1a_bundle_detected_by_project_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "project_graph.json").write_text("{}")
            self.assertEqual(detect_bundle_type(p), "p1a")

    def test_p1b_takes_precedence_over_p1a(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            (p / "project_graph.json").write_text("{}")
            self.assertEqual(detect_bundle_type(p), "p1b")


class TestBundleValidation(unittest.TestCase):

    def test_complete_p1b_bundle_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in P1B_REQUIRED_ARTIFACTS:
                (p / name).write_text("{}")
            diags = validate_bundle(p)
            errors = [d for d in diags if d.severity == "error"]
            self.assertEqual(len(errors), 0)

    def test_incomplete_p1b_bundle_reports_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Only 2 of 6 required files.
            (p / "concept_trace_graph.json").write_text("{}")
            (p / "concept_trace_index.json").write_text("{}")
            diags = validate_bundle(p)
            errors = [d for d in diags if d.severity == "error"]
            self.assertGreater(len(errors), 0)
            missing_names = {d.artifact for d in errors}
            self.assertIn("run_metadata.json", missing_names)

    def test_non_directory_is_error(self):
        with tempfile.NamedTemporaryFile() as f:
            diags = validate_bundle(Path(f.name))
            self.assertEqual(len(diags), 1)
            self.assertEqual(diags[0].severity, "error")

    def test_unknown_bundle_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            diags = validate_bundle(Path(tmp))
            self.assertEqual(len(diags), 1)
            self.assertEqual(diags[0].code, "UNKNOWN_BUNDLE")


class TestBundleLoading(unittest.TestCase):

    def _make_p1b_bundle(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        graph = {
            "schema_version": "0.1.0",
            "concept": "peak_idx",
            "nodes": [],
            "edges": [],
            "mapping_claims": [],
            "evidence_items": [],
            "grounding_diagnostics": [],
            "uncertainty_notes": [],
        }
        index = {
            "schema_version": "0.1.0",
            "concept": "peak_idx",
            "claim_index": {},
            "evidence_index": {},
            "node_index": {},
            "edge_index": {},
            "cross_references": {},
        }
        grounding = {
            "schema_version": "p1b-grounding-report-0.1",
            "diagnostics": [],
            "summary": {
                "mapping_claims": 1,
                "blocking_diagnostics": 0,
            },
        }
        metadata = {
            "schema_version": "p1b-run-metadata-0.1",
            "concept": "peak_idx",
            "project_root": "/tmp/test_project",
            "output_dir": str(tmp),
            "elapsed_seconds": 0.123,
            "status": "ok",
            "blocking_diagnostics": 0,
            "mapping_claims": 1,
            "evidence_items": 10,
            "artifacts": list(P1B_REQUIRED_ARTIFACTS),
        }
        md_text = "# Concept Trace: peak_idx\n\n## Summary\n\n- Status: ok\n"
        mmd_text = "graph TD\n    N1[\"peak_idx\"]\n"

        (tmp / "concept_trace_graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        (tmp / "concept_trace_index.json").write_text(
            json.dumps(index), encoding="utf-8"
        )
        (tmp / "grounding_report.json").write_text(
            json.dumps(grounding), encoding="utf-8"
        )
        (tmp / "run_metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        (tmp / "concept_trace.md").write_text(md_text, encoding="utf-8")
        (tmp / "concept_trace.mmd").write_text(mmd_text, encoding="utf-8")
        return tmp

    def test_load_complete_p1b_bundle(self):
        tmp = self._make_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            self.assertEqual(bundle.bundle_type, "p1b")
            self.assertTrue(bundle.is_complete)
            self.assertEqual(len(bundle.artifacts), 6)
            for name in P1B_REQUIRED_ARTIFACTS:
                self.assertIn(name, bundle.artifacts)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_run_metadata_accessible(self):
        tmp = self._make_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            meta = get_run_metadata(bundle)
            self.assertIsNotNone(meta)
            self.assertEqual(meta["concept"], "peak_idx")  # type: ignore[index]
            self.assertEqual(meta["status"], "ok")  # type: ignore[index]
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_graph_accessible(self):
        tmp = self._make_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            graph = get_graph(bundle)
            self.assertIsNotNone(graph)
            self.assertEqual(graph["concept"], "peak_idx")  # type: ignore[index]
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_index_accessible(self):
        tmp = self._make_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            index = get_index(bundle)
            self.assertIsNotNone(index)
            self.assertEqual(index["concept"], "peak_idx")  # type: ignore[index]
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_markdown_accessible(self):
        tmp = self._make_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            md = get_markdown(bundle)
            self.assertIsNotNone(md)
            self.assertIn("peak_idx", md)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_mermaid_accessible(self):
        tmp = self._make_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            mmd = get_mermaid(bundle)
            self.assertIsNotNone(mmd)
            self.assertIn("graph TD", mmd)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_incomplete_bundle_produces_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Only graph + index.
            (p / "concept_trace_graph.json").write_text("{}")
            (p / "concept_trace_index.json").write_text("{}")
            bundle = load_bundle(p)
            self.assertEqual(bundle.bundle_type, "p1b")
            self.assertFalse(bundle.is_complete)
            errors = [d for d in bundle.diagnostics if d.severity == "error"]
            self.assertGreater(len(errors), 0)

    def test_load_unknown_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = load_bundle(Path(tmp))
            self.assertEqual(bundle.bundle_type, "unknown")
            self.assertFalse(bundle.is_complete)

    def test_json_decode_error_produces_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("not json")
            bundle = load_bundle(p)
            errors = [d for d in bundle.diagnostics if d.code == "LOAD_ERROR"]
            self.assertGreaterEqual(len(errors), 1)

    def test_invalid_json_run_metadata_load_error(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            for name in P1B_REQUIRED_ARTIFACTS:
                if name == "run_metadata.json":
                    (tmp / name).write_text("not json")
                else:
                    (tmp / name).write_text("{}")
            bundle = load_bundle(tmp)
            errors = [d for d in bundle.diagnostics if d.code == "LOAD_ERROR"]
            self.assertGreaterEqual(len(errors), 1)
            self.assertFalse(bundle.is_complete)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_mermaid_decode_error_produces_load_error(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            for name in P1B_REQUIRED_ARTIFACTS:
                if name == "concept_trace.mmd":
                    (tmp / name).write_bytes(b"\xff\xfe invalid utf8")
                else:
                    (tmp / name).write_text("{}" if name.endswith(".json") else "")
            bundle = load_bundle(tmp)
            errors = [d for d in bundle.diagnostics if d.code == "LOAD_ERROR"]
            self.assertGreaterEqual(len(errors), 1)
            self.assertFalse(bundle.is_complete)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_markdown_decode_error_produces_load_error(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            for name in P1B_REQUIRED_ARTIFACTS:
                if name == "concept_trace.md":
                    (tmp / name).write_bytes(b"\xff\xfe invalid utf8")
                else:
                    (tmp / name).write_text("{}" if name.endswith(".json") else "")
            bundle = load_bundle(tmp)
            errors = [d for d in bundle.diagnostics if d.code == "LOAD_ERROR"]
            self.assertGreaterEqual(len(errors), 1)
            self.assertFalse(bundle.is_complete)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_bundle_never_raises(self):
        nonexistent = Path("/nonexistent_path_12345")
        try:
            bundle = load_bundle(nonexistent)
            self.assertFalse(bundle.is_complete)
            errors = [d for d in bundle.diagnostics if d.severity == "error"]
            self.assertGreater(len(errors), 0)
        except Exception:
            self.fail("load_bundle() must never raise")


class TestProjectBundleDetection(unittest.TestCase):
    """Tests for project bundle detection and loading (T024)."""

    def _make_project_bundle(self, tmp: Path) -> Path:
        """Write a minimal project bundle to *tmp* and return the path."""
        tmp.mkdir(parents=True, exist_ok=True)
        graph = {
            "schema_version": "project-understanding-0.1",
            "project_id": "test_project",
            "nodes": [
                {"node_id": "PUG_PROJECT", "label": "test_project", "kind": "project"},
                {"node_id": "PUG_CONCEPT_peak_idx", "label": "peak_idx", "kind": "concept"},
            ],
            "edges": [],
        }
        index = {
            "schema_version": "project-understanding-0.1",
            "concept_index": {"peak_idx": {"status": "ok", "claims": 1}},
        }
        metadata = {
            "schema_version": "p1b-project-run-metadata-0.1",
            "command": "p1b-trace-project",
            "project_root": "/tmp/test_project",
            "concepts_processed": ["peak_idx"],
            "status": "ok",
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

    def test_project_bundle_detected_by_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "project_understanding_graph.json").write_text("{}")
            self.assertEqual(detect_bundle_type(p), "project")

    def test_project_bundle_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(p)
            self.assertEqual(bundle.bundle_type, "project")
            self.assertTrue(bundle.is_complete)
            self.assertIn("project_understanding_graph.json", bundle.artifacts)
            self.assertIn("project_understanding_index.json", bundle.artifacts)
            self.assertIn("run_metadata.json", bundle.artifacts)

    def test_project_graph_accessible(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._make_project_bundle(Path(tmp) / "project")
            bundle = load_bundle(p)
            graph = get_project_graph(bundle)
            self.assertIsNotNone(graph)
            self.assertEqual(graph["project_id"], "test_project")  # type: ignore[index]

    def test_project_takes_precedence_over_p1b(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "project_understanding_graph.json").write_text("{}")
            (p / "concept_trace_graph.json").write_text("{}")
            self.assertEqual(detect_bundle_type(p), "project")

    def test_project_bundle_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "project_understanding_graph.json").write_text("{}")
            bundle = load_bundle(p)
            self.assertEqual(bundle.bundle_type, "project")
            self.assertFalse(bundle.is_complete)


class TestArtifactDiagnostic(unittest.TestCase):

    def test_diagnostic_creation(self):
        d = ArtifactDiagnostic(
            severity="error",
            artifact="run_metadata.json",
            message="Missing",
            code="MISSING_REQUIRED",
        )
        self.assertEqual(d.severity, "error")
        self.assertEqual(d.artifact, "run_metadata.json")
        self.assertEqual(d.code, "MISSING_REQUIRED")


if __name__ == "__main__":
    unittest.main()
