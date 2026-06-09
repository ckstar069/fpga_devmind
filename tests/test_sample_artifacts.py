"""Tests for sample_artifacts helper (T014).

Validates the artifact bundle discovery function: finds P1b/P1a bundles,
skips non-bundle dirs, handles missing base dirs, sorts by mtime.

No external API, no LLM, no Vivado.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.sample_artifacts import find_recent_artifact_bundles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_p1b_bundle(parent: Path, name: str) -> Path:
    """Create a minimal P1b bundle directory under *parent*."""
    bundle_dir = parent / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "concept_trace_graph.json").write_text(
        json.dumps({"schema_version": "0.1.0", "nodes": []}),
        encoding="utf-8",
    )
    (bundle_dir / "concept_trace_index.json").write_text("{}", encoding="utf-8")
    (bundle_dir / "grounding_report.json").write_text("{}", encoding="utf-8")
    (bundle_dir / "run_metadata.json").write_text("{}", encoding="utf-8")
    (bundle_dir / "concept_trace.md").write_text("# Trace\n", encoding="utf-8")
    (bundle_dir / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return bundle_dir


def _make_p1a_bundle(parent: Path, name: str) -> Path:
    """Create a minimal P1a bundle directory under *parent*."""
    bundle_dir = parent / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "project_graph.json").write_text("{}", encoding="utf-8")
    (bundle_dir / "trace_index.json").write_text("{}", encoding="utf-8")
    return bundle_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindRecentArtifactBundles(unittest.TestCase):

    def test_find_recent_discovers_p1b_bundle(self) -> None:
        """A P1b bundle under a scanned base_dir is discovered."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_test_") as base:
            base_path = Path(base)
            _make_p1b_bundle(base_path, "p1b_peak_idx")
            results = find_recent_artifact_bundles(base_dirs=[base_path])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].bundle_type, "p1b")

    def test_find_recent_nonexistent_base_returns_empty(self) -> None:
        """Non-existent base dirs produce an empty list."""
        results = find_recent_artifact_bundles(
            base_dirs=[Path("/tmp/nonexistent_fpga_devmind_test_dir_xyz")]
        )
        self.assertEqual(results, [])

    def test_find_recent_ignores_non_bundle_dirs(self) -> None:
        """Directories without P1b/P1a marker files are skipped."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_test_") as base:
            base_path = Path(base)
            # A plain directory with no artifact files
            (base_path / "random_dir").mkdir()
            results = find_recent_artifact_bundles(base_dirs=[base_path])
            self.assertEqual(results, [])

    def test_find_recent_sorted_by_mtime(self) -> None:
        """Multiple bundles are sorted newest-first."""
        import time

        with tempfile.TemporaryDirectory(prefix="fpga_devmind_test_") as base:
            base_path = Path(base)
            # Create two bundles with a small mtime gap
            first = _make_p1b_bundle(base_path, "bundle_older")
            time.sleep(0.05)
            second = _make_p1b_bundle(base_path, "bundle_newer")
            results = find_recent_artifact_bundles(base_dirs=[base_path])
            self.assertEqual(len(results), 2)
            # Newest first
            self.assertEqual(results[0].path, second)
            self.assertEqual(results[1].path, first)

    def test_find_recent_discovers_p1a_bundle(self) -> None:
        """A P1a bundle under a scanned base_dir is discovered."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_test_") as base:
            base_path = Path(base)
            _make_p1a_bundle(base_path, "p1a_l6")
            results = find_recent_artifact_bundles(base_dirs=[base_path])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].bundle_type, "p1a")

    def test_find_recent_discovers_agent_runtime_bundle(self) -> None:
        """An agent_runtime bundle is discovered via detect_bundle_type."""
        with tempfile.TemporaryDirectory(prefix="fpga_devmind_test_") as base:
            base_path = Path(base)
            bundle_dir = base_path / "noop_run"
            bundle_dir.mkdir()
            (bundle_dir / "agent_runtime_trace.json").write_text(
                json.dumps({"schema_version": "agent-runtime-contract-0.1"}),
                encoding="utf-8",
            )
            results = find_recent_artifact_bundles(base_dirs=[base_path])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].bundle_type, "agent_runtime")


if __name__ == "__main__":
    unittest.main()
