"""Tests for desktop view models (T009).

Tests the pure-data view-model layer without PySide6.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.artifact_loader import P1B_REQUIRED_ARTIFACTS, load_bundle
from fpga_devmind.desktop.view_models import (
    JsonTreeNode,
    build_bundle_summary,
    build_json_tree,
    build_markdown_preview,
    build_run_summary,
)


class TestRunSummaryViewModel(unittest.TestCase):

    def _make_bundle(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        metadata = {
            "schema_version": "p1b-run-metadata-0.1",
            "concept": "peak_idx",
            "project_root": "/tmp/test_project",
            "output_dir": str(tmp),
            "elapsed_seconds": 0.456,
            "status": "ok",
            "blocking_diagnostics": 0,
            "mapping_claims": 3,
            "evidence_items": 12,
            "artifacts": list(P1B_REQUIRED_ARTIFACTS),
        }
        (tmp / "concept_trace_graph.json").write_text(
            json.dumps({"schema_version": "0.1.0", "concept": "peak_idx"}),
            encoding="utf-8",
        )
        (tmp / "concept_trace_index.json").write_text("{}")
        (tmp / "grounding_report.json").write_text("{}")
        (tmp / "run_metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        (tmp / "concept_trace.md").write_text("# Trace\n", encoding="utf-8")
        (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
        return tmp

    def test_run_summary_parses_correctly(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_run_summary(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.concept, "peak_idx")
            self.assertEqual(vm.status, "ok")
            self.assertEqual(vm.project_root, "/tmp/test_project")
            self.assertEqual(vm.elapsed_seconds, 0.456)
            self.assertEqual(vm.blocking_diagnostics, 0)
            self.assertEqual(vm.mapping_claims, 3)
            self.assertEqual(vm.evidence_items, 12)
            self.assertEqual(vm.schema_version, "p1b-run-metadata-0.1")
            self.assertEqual(len(vm.artifacts), 6)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_run_summary_for_blocked_status(self):
        tmp = self._make_bundle()
        try:
            # Mutate metadata to blocked status.
            meta_path = tmp / "run_metadata.json"
            meta = json.loads(meta_path.read_text())
            meta["status"] = "blocked"
            meta["blocking_diagnostics"] = 2
            meta_path.write_text(json.dumps(meta), encoding="utf-8")

            bundle = load_bundle(tmp)
            vm = build_run_summary(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.status, "blocked")
            self.assertEqual(vm.blocking_diagnostics, 2)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_run_summary_unknown_concept(self):
        tmp = self._make_bundle()
        try:
            meta_path = tmp / "run_metadata.json"
            meta = json.loads(meta_path.read_text())
            meta["concept"] = "nonexistent_xyz"
            meta["status"] = "ok"
            meta["blocking_diagnostics"] = 0
            meta["mapping_claims"] = 1
            meta["evidence_items"] = 0
            meta_path.write_text(json.dumps(meta), encoding="utf-8")

            bundle = load_bundle(tmp)
            vm = build_run_summary(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.concept, "nonexistent_xyz")
            self.assertEqual(vm.status, "ok")
            self.assertEqual(vm.blocking_diagnostics, 0)
            self.assertEqual(vm.evidence_items, 0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_run_summary_incomplete_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            bundle = load_bundle(p)
            vm = build_run_summary(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)

    def test_run_summary_missing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            (p / "concept_trace_index.json").write_text("{}")
            (p / "grounding_report.json").write_text("{}")
            (p / "concept_trace.md").write_text("")
            (p / "concept_trace.mmd").write_text("")
            bundle = load_bundle(p)
            vm = build_run_summary(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("run_metadata.json", vm.load_error or "")


class TestJsonTreeViewModel(unittest.TestCase):

    def _make_bundle_with_graph(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        graph = {
            "schema_version": "0.1.0",
            "concept": "peak_idx",
            "nodes": [
                {"node_id": "N1", "label": "peak_idx", "kind": "concept"},
            ],
            "edges": [],
        }
        (tmp / "concept_trace_graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        return tmp

    def test_json_tree_loads_graph(self):
        tmp = self._make_bundle_with_graph()
        try:
            bundle = load_bundle(tmp)
            vm = build_json_tree(bundle, "concept_trace_graph.json")
            self.assertTrue(vm.is_loaded)
            self.assertIsNotNone(vm.root)
            root = vm.root
            assert root is not None
            self.assertEqual(vm.title, "concept_trace_graph.json")
            # Root should be a dict with children.
            self.assertEqual(root.value_type, "dict")
            self.assertGreater(len(root.children), 0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_json_tree_handles_missing_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            bundle = load_bundle(p)
            vm = build_json_tree(bundle, "concept_trace_graph.json")
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)

    def test_json_tree_handles_nested_data(self):
        tmp = self._make_bundle_with_graph()
        try:
            bundle = load_bundle(tmp)
            vm = build_json_tree(bundle, "concept_trace_graph.json")
            self.assertIsNotNone(vm.root)
            root = vm.root
            assert root is not None
            # Find the "nodes" child.
            nodes_child = next(
                (c for c in root.children if c.key == "nodes"),
                None,
            )
            self.assertIsNotNone(nodes_child)
            assert nodes_child is not None
            self.assertEqual(nodes_child.value_type, "list")
            self.assertEqual(len(nodes_child.children), 1)
            # First node in list.
            first_node = nodes_child.children[0]
            self.assertEqual(first_node.value_type, "dict")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_json_tree_max_depth_protection(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            # Create deeply nested JSON.
            deep = {}
            current = deep
            for _ in range(60):
                current["child"] = {}
                current = current["child"]
            (tmp / "concept_trace_graph.json").write_text(
                json.dumps(deep), encoding="utf-8"
            )
            bundle = load_bundle(tmp)
            vm = build_json_tree(bundle, "concept_trace_graph.json")
            self.assertTrue(vm.is_loaded)
            # Should not crash even with 60 levels.
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestMarkdownPreviewViewModel(unittest.TestCase):

    def _make_bundle(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        (tmp / "concept_trace_graph.json").write_text("{}")
        (tmp / "concept_trace.md").write_text(
            "# Concept Trace: peak_idx\n\n## Summary\n\n- Status: ok\n",
            encoding="utf-8",
        )
        return tmp

    def test_markdown_preview_loads(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_markdown_preview(bundle, "concept_trace.md")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.title, "concept_trace.md")
            self.assertIn("peak_idx", vm.content)
            self.assertIn("## Summary", vm.content)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_markdown_preview_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            bundle = load_bundle(p)
            vm = build_markdown_preview(bundle, "concept_trace.md")
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)


class TestBundleSummaryViewModel(unittest.TestCase):

    def _make_complete_bundle(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        for name in P1B_REQUIRED_ARTIFACTS:
            (tmp / name).write_text("{}")
        return tmp

    def test_complete_bundle_summary(self):
        tmp = self._make_complete_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_bundle_summary(bundle)
            self.assertEqual(vm.bundle_type, "p1b")
            self.assertTrue(vm.is_complete)
            self.assertEqual(vm.artifact_count, 6)
            self.assertEqual(vm.error_count, 0)
            self.assertEqual(vm.warning_count, 0)
            self.assertEqual(vm.diagnostic_count, 0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_incomplete_bundle_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            bundle = load_bundle(p)
            vm = build_bundle_summary(bundle)
            self.assertEqual(vm.bundle_type, "p1b")
            self.assertFalse(vm.is_complete)
            self.assertGreater(vm.error_count, 0)

    def test_unknown_bundle_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            bundle = load_bundle(p)
            vm = build_bundle_summary(bundle)
            self.assertEqual(vm.bundle_type, "unknown")
            self.assertFalse(vm.is_complete)
            self.assertGreater(vm.diagnostic_count, 0)

    def test_bundle_summary_for_load_error(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            for name in P1B_REQUIRED_ARTIFACTS:
                if name == "run_metadata.json":
                    (tmp / name).write_text("not json")
                else:
                    (tmp / name).write_text("{}")
            bundle = load_bundle(tmp)
            vm = build_bundle_summary(bundle)
            self.assertEqual(vm.bundle_type, "p1b")
            self.assertFalse(vm.is_complete)
            self.assertGreater(vm.error_count, 0)
            self.assertGreater(vm.diagnostic_count, 0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestJsonTreeNode(unittest.TestCase):

    def test_leaf_string_node(self):
        n = JsonTreeNode(key="name", value="peak_idx", value_type="str")
        self.assertEqual(n.key, "name")
        self.assertEqual(n.value, "peak_idx")
        self.assertEqual(n.value_type, "str")
        self.assertEqual(len(n.children), 0)

    def test_dict_node_with_children(self):
        child = JsonTreeNode(key="node_id", value="N1", value_type="str")
        parent = JsonTreeNode(
            key="root", value="1 field(s)", value_type="dict", children=[child]
        )
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(parent.children[0].key, "node_id")


if __name__ == "__main__":
    unittest.main()
