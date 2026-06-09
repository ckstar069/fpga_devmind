"""Tests for desktop_sample_run module (T018).

Validates the one-click sample artifact generator that chains
p1b-trace-concept → agent-noop-run.

No external API, no LLM, no Vivado.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop_sample_run import (
    DesktopSampleResult,
    run_desktop_sample,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(
    "/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDesktopSampleHappyPath(unittest.TestCase):
    """End-to-end happy path with the real coarse_sync_glm project."""

    def test_happy_path_creates_both_bundles(self) -> None:
        """Both P1b and agent-runtime bundles are created."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_sample_"
        ) as tmp:
            out = Path(tmp) / "sample"
            result = run_desktop_sample(
                project_root=PROJECT_ROOT,
                concept="peak_idx",
                question="summary",
                out_root=out,
            )
            try:
                self.assertIsInstance(result, DesktopSampleResult)
                # P1b bundle must exist
                self.assertTrue(
                    (result.p1b_dir / "concept_trace_graph.json").is_file(),
                    "P1b bundle missing concept_trace_graph.json",
                )
                # No-op bundle must exist
                self.assertTrue(
                    (
                        result.noop_dir / "agent_runtime_trace.json"
                    ).is_file(),
                    "No-op bundle missing agent_runtime_trace.json",
                )
                self.assertIn(result.status, ("ok", "partial"))
                self.assertTrue(len(result.messages) >= 2)
            finally:
                shutil.rmtree(out, ignore_errors=True)

    def test_p1b_artifacts_are_valid(self) -> None:
        """P1b bundle has valid JSON artifacts."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_sample_"
        ) as tmp:
            out = Path(tmp) / "sample"
            result = run_desktop_sample(
                project_root=PROJECT_ROOT,
                concept="peak_idx",
                question="summary",
                out_root=out,
            )
            try:
                graph_path = result.p1b_dir / "concept_trace_graph.json"
                self.assertTrue(graph_path.is_file())
                data = json.loads(graph_path.read_text(encoding="utf-8"))
                self.assertIn("nodes", data)
                self.assertIn("edges", data)
            finally:
                shutil.rmtree(out, ignore_errors=True)

    def test_noop_trace_is_valid(self) -> None:
        """Agent runtime trace has valid schema."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_sample_"
        ) as tmp:
            out = Path(tmp) / "sample"
            result = run_desktop_sample(
                project_root=PROJECT_ROOT,
                concept="peak_idx",
                question="summary",
                out_root=out,
            )
            try:
                trace_path = result.noop_dir / "agent_runtime_trace.json"
                self.assertTrue(trace_path.is_file())
                data = json.loads(trace_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    data.get("schema_version"),
                    "agent-runtime-contract-0.1",
                )
                self.assertIn("task", data)
                self.assertIn("answers", data)
            finally:
                shutil.rmtree(out, ignore_errors=True)


class TestDesktopSampleEdgeCases(unittest.TestCase):
    """Edge cases for the sample runner."""

    def test_unsafe_output_dir_raises(self) -> None:
        """Output inside fpga_project_* is rejected."""
        with self.assertRaises(ValueError):
            run_desktop_sample(
                project_root=PROJECT_ROOT,
                concept="peak_idx",
                question="summary",
                out_root=PROJECT_ROOT / "output",
            )

    def test_nonexistent_project_returns_error(self) -> None:
        """Non-existent project directory returns error status."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_sample_"
        ) as tmp:
            out = Path(tmp) / "sample"
            result = run_desktop_sample(
                project_root=Path("/nonexistent/project_xyz"),
                concept="peak_idx",
                question="summary",
                out_root=out,
            )
            self.assertEqual(result.status, "error")
            self.assertTrue(len(result.messages) > 0)


class TestDesktopSampleSafety(unittest.TestCase):
    """Safety boundary checks."""

    def test_no_forbidden_imports(self) -> None:
        """Module does not import LLM/API/Vivado modules."""
        import fpga_devmind.desktop_sample_run as mod

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
