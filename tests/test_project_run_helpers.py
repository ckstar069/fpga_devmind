"""Tests for project_run_helpers module (T026).

Pure Python — no PySide6, no pipeline execution.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from fpga_devmind.desktop.project_run_helpers import (
    get_default_concepts,
    get_default_output_dir,
    get_default_project_root,
    parse_concepts,
    validate_run_params,
    format_run_status,
)


class TestParseConcepts(unittest.TestCase):
    """Concept string parsing."""

    def test_comma_separated(self) -> None:
        """Standard comma-separated concepts."""
        result = parse_concepts("peak_idx,cfo,smooth_detect")
        self.assertEqual(result, ["peak_idx", "cfo", "smooth_detect"])

    def test_with_spaces(self) -> None:
        """Spaces around commas are stripped."""
        result = parse_concepts("peak_idx, cfo , smooth_detect")
        self.assertEqual(result, ["peak_idx", "cfo", "smooth_detect"])

    def test_empty_input(self) -> None:
        """Empty string returns empty list."""
        self.assertEqual(parse_concepts(""), [])
        self.assertEqual(parse_concepts("   "), [])

    def test_deduplicates(self) -> None:
        """Duplicate concepts are deduplicated."""
        result = parse_concepts("peak_idx,peak_idx,cfo")
        self.assertEqual(result, ["peak_idx", "cfo"])

    def test_empty_items_ignored(self) -> None:
        """Empty items from trailing commas are ignored."""
        result = parse_concepts("peak_idx,,cfo,")
        self.assertEqual(result, ["peak_idx", "cfo"])


class TestDefaults(unittest.TestCase):
    """Default values."""

    def test_default_concepts(self) -> None:
        """Default concepts string is comma-separated."""
        dc = get_default_concepts()
        self.assertIn("peak_idx", dc)
        self.assertIn("cfo", dc)
        self.assertIn("smooth_detect", dc)

    def test_default_output_dir(self) -> None:
        """Default output dir is under /tmp or /private/tmp."""
        d = get_default_output_dir()
        self.assertTrue(
            str(d).startswith("/tmp") or str(d).startswith("/private/tmp"),
            "Expected temp path, got: {}".format(d),
        )

    def test_default_project_root_exists_or_empty(self) -> None:
        """Default project root either exists or is empty."""
        root = get_default_project_root()
        if root:
            self.assertTrue(root.exists())


class TestValidateRunParams(unittest.TestCase):
    """Run parameter validation."""

    def test_empty_project_root(self) -> None:
        """Empty project root is rejected."""
        err = validate_run_params(Path(""), ["peak_idx"])
        self.assertIsNotNone(err)
        self.assertIn("路径", err or "")

    def test_nonexistent_project(self) -> None:
        """Nonexistent project path is rejected."""
        err = validate_run_params(Path("/nonexistent/path_12345"), ["peak_idx"])
        self.assertIsNotNone(err)
        self.assertIn("不存在", err or "")

    def test_empty_concepts(self) -> None:
        """Empty concepts list is rejected."""
        err = validate_run_params(Path("/tmp"), [])
        self.assertIsNotNone(err)
        self.assertIn("概念", err or "")

    def test_valid_params(self) -> None:
        """Valid parameters return None."""
        err = validate_run_params(Path("/tmp"), ["peak_idx"])
        self.assertIsNone(err)


class TestFormatRunStatus(unittest.TestCase):
    """Status formatting."""

    def test_ok_status(self) -> None:
        """OK run formats cleanly."""
        metadata = {
            "status": "ok",
            "concepts_processed": ["peak_idx"],
            "concepts_failed": [],
            "mapping_claims": 3,
            "evidence_items": 125,
            "elapsed_seconds": 0.063,
            "output_dir": "/tmp/out",
        }
        text = format_run_status(metadata)
        self.assertIn("ok", text)
        self.assertIn("3", text)
        self.assertIn("125", text)
        self.assertIn("0.063", text)
        self.assertIn("/tmp/out", text)

    def test_partial_status(self) -> None:
        """Partial run shows failed concepts."""
        metadata = {
            "status": "partial",
            "concepts_processed": ["peak_idx"],
            "concepts_failed": ["ghost"],
            "mapping_claims": 1,
            "evidence_items": 10,
        }
        text = format_run_status(metadata)
        self.assertIn("partial", text)
        self.assertIn("ghost", text)

    def test_no_elapsed(self) -> None:
        """Missing elapsed_seconds is handled gracefully."""
        metadata = {"status": "ok"}
        text = format_run_status(metadata)
        self.assertIn("ok", text)


class TestSafety(unittest.TestCase):
    """Safety boundary checks."""

    def test_no_forbidden_imports(self) -> None:
        """Module does not import LLM/API/Vivado."""
        import fpga_devmind.desktop.project_run_helpers as mod

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
