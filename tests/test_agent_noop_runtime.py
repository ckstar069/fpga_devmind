"""Tests for agent_noop_runtime (T016).

Validates the local no-op ReAct dry run: observe -> plan -> propose ->
simulated-result -> answer -> blocked-graph-write trace.

No external API, no LLM, no Vivado.
"""

# pyright: reportUnusedCallResult=false
# pyright: reportUninitializedInstanceVariable=false
# pyright: reportMissingTypeArgument=false

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fpga_devmind.agent_noop_runtime import run_noop_agent_once
from fpga_devmind.agent_runtime_contract import (
    GRAPH_WRITE_DISABLED_REASON,
    SCHEMA_VERSION,
    validate_runtime_trace,
)
from fpga_devmind.cli import main
from fpga_devmind.desktop.artifact_loader import P1B_REQUIRED_ARTIFACTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph() -> dict:
    """Create a synthetic P1b graph with known + unknown claims."""
    return {
        "schema_version": "0.1.0",
        "concept": "peak_idx",
        "nodes": [
            {
                "node_id": "N_CONCEPT_peak_idx",
                "label": "peak_idx",
                "kind": "concept",
                "stage_id": None,
                "file_path": None,
                "symbol_refs": [],
                "evidence_ids": ["E:p1b_concept:path:1:10:1"],
                "confidence": "supported",
                "notes": None,
            },
        ],
        "edges": [],
        "mapping_claims": [
            {
                "claim_id": "MC_peak_idx_001",
                "claim_type": "mapping_claim",
                "statement": "peak_idx maps to peak_detect",
                "concept_ref": "peak_idx",
                "l6_subject_ids": ["class:PeakDetector"],
                "rtl_subject_ids": ["module:peak_detect"],
                "l5_l6_evidence_ids": ["E:p1b_concept:path:1:10:1"],
                "rtl_evidence_ids": ["E:p1b_rtl:path:5:20:1"],
                "bridge_evidence_ids": ["E:p1b_concept:path:1:10:1"],
                "bridge_kind": "explicit_source_bridge",
                "confidence": "supported",
                "required_missing_evidence": [],
                "source_plan_step_id": None,
                "notes": None,
                "evidence_ids": [
                    "E:p1b_concept:path:1:10:1",
                    "E:p1b_rtl:path:5:20:1",
                ],
            },
        ],
        "evidence_items": [
            {
                "evidence_id": "E:p1b_concept:path:1:10:1",
                "source_type": "concept_occurrence",
                "file_path": "/project/l6/peak_detector.py",
                "start_line": 10,
                "end_line": 25,
                "symbol": "PeakDetector",
                "excerpt_summary": "Class PeakDetector",
                "evidence_strength": "strong",
                "snippet_complete": True,
                "reliability_note": None,
            },
        ],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
        "stage_views": [],
        "rtl_views": [],
        "task_request": {},
        "project_profile": {},
        "run_metadata": {},
    }


def _make_grounding() -> dict:
    return {
        "schema_version": "p1b-grounding-report-0.1",
        "diagnostics": [],
        "summary": {
            "mapping_claims": 1,
            "blocking_diagnostics": 0,
            "unsupported_confirmed_mappings": 0,
            "naming_only_supported_mappings": 0,
            "one_sided_mapping_evidence": 0,
        },
    }


def _make_metadata(tmp: Path) -> dict:
    return {
        "schema_version": "p1b-run-metadata-0.1",
        "concept": "peak_idx",
        "project_root": "/tmp/test_project",
        "output_dir": str(tmp),
        "elapsed_seconds": 0.123,
        "status": "ok",
        "blocking_diagnostics": 0,
        "mapping_claims": 1,
        "evidence_items": 1,
        "artifacts": list(P1B_REQUIRED_ARTIFACTS),
    }


def _make_synthetic_p1b_bundle() -> Path:
    """Create a complete synthetic P1b artifact bundle in a temp dir."""
    tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_noop_test_"))
    (tmp / "concept_trace_graph.json").write_text(
        json.dumps(_make_graph()), encoding="utf-8"
    )
    (tmp / "concept_trace_index.json").write_text("{}", encoding="utf-8")
    (tmp / "grounding_report.json").write_text(
        json.dumps(_make_grounding()), encoding="utf-8"
    )
    (tmp / "run_metadata.json").write_text(
        json.dumps(_make_metadata(tmp)), encoding="utf-8"
    )
    (tmp / "concept_trace.md").write_text("# Trace\n", encoding="utf-8")
    (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


def _make_incomplete_bundle() -> Path:
    """Create an incomplete bundle (only graph file)."""
    tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_noop_incomp_"))
    (tmp / "concept_trace_graph.json").write_text("{}", encoding="utf-8")
    return tmp


def _make_safe_out() -> Path:
    """Create a safe output directory under /tmp."""
    return Path(tempfile.mkdtemp(prefix="fpga_devmind_noop_out_"))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestNoopAgentHappyPath(unittest.TestCase):
    """Core happy-path assertions for the no-op agent trace."""

    def setUp(self) -> None:
        self.bundle_dir = _make_synthetic_p1b_bundle()
        self.out_dir = _make_safe_out()
        self.result = run_noop_agent_once(
            artifact_dir=self.bundle_dir,
            question="summary",
            out_dir=self.out_dir,
        )

    def test_happy_path_writes_trace(self) -> None:
        trace_path = Path(self.result.artifact_path)
        self.assertTrue(trace_path.exists())
        data = json.loads(trace_path.read_text(encoding="utf-8"))
        self.assertIn("task", data)

    def test_trace_schema_version(self) -> None:
        self.assertEqual(self.result.trace.schema_version, SCHEMA_VERSION)

    def test_validate_no_diagnostics(self) -> None:
        diags = validate_runtime_trace(self.result.trace)
        self.assertEqual(diags, [])

    def test_user_task_has_safety_constraints(self) -> None:
        constraints = self.result.trace.task.constraints
        for c in ["no_external_api", "no_vivado", "read_only", "no_target_project_mutation"]:
            self.assertIn(c, constraints)

    def test_observation_artifact_refs_populated(self) -> None:
        obs = self.result.trace.observations
        self.assertEqual(len(obs), 1)
        self.assertTrue(len(obs[0].artifact_refs) > 0)

    def test_tool_plan_not_executable(self) -> None:
        self.assertFalse(self.result.trace.plans[0].is_executable_now)

    def test_all_proposals_not_executable(self) -> None:
        for plan in self.result.trace.plans:
            for step in plan.steps:
                self.assertFalse(step.is_executable_now)

    def test_tool_result_status_simulated(self) -> None:
        for tr in self.result.trace.tool_results:
            self.assertEqual(tr.status, "simulated")

    def test_answer_has_no_llm_limitation(self) -> None:
        self.assertIn(
            "no_llm_semantic_reasoning",
            self.result.trace.answers[0].limitations,
        )

    def test_graph_write_blocked(self) -> None:
        gwp = self.result.trace.graph_write_proposals[0]
        self.assertFalse(gwp.is_write_allowed)
        self.assertIn(GRAPH_WRITE_DISABLED_REASON, gwp.blocking_reasons)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestNoopAgentEdgeCases(unittest.TestCase):

    def test_unsupported_question_unknown_confidence(self) -> None:
        bundle_dir = _make_synthetic_p1b_bundle()
        out_dir = _make_safe_out()
        result = run_noop_agent_once(
            artifact_dir=bundle_dir,
            question="xyzzy foo bar unrecognized question",
            out_dir=out_dir,
        )
        self.assertEqual(result.trace.answers[0].confidence, "unknown")

    def test_incomplete_bundle_load_error(self) -> None:
        bundle_dir = _make_incomplete_bundle()
        out_dir = _make_safe_out()
        result = run_noop_agent_once(
            artifact_dir=bundle_dir,
            question="summary",
            out_dir=out_dir,
        )
        self.assertEqual(result.status, "load_error")
        self.assertTrue(len(result.trace.runtime_diagnostics) > 0)
        self.assertTrue(len(result.diagnostics) > 0)

    def test_unsafe_output_dir_raises(self) -> None:
        bundle_dir = _make_synthetic_p1b_bundle()
        with self.assertRaises(ValueError):
            run_noop_agent_once(
                artifact_dir=bundle_dir,
                question="summary",
                out_dir=Path("/tmp/fpga_project_test/output"),
            )

    def test_validation_diagnostics_propagate_to_blocked(self) -> None:
        """When validate_runtime_trace returns errors, status=blocked
        and runtime_diagnostics is populated in the trace and JSON."""
        bundle_dir = _make_synthetic_p1b_bundle()
        out_dir = _make_safe_out()
        fake_diag = [{"severity": "error", "message": "cross-ref broken"}]
        with patch(
            "fpga_devmind.agent_noop_runtime.validate_runtime_trace",
            return_value=fake_diag,
        ):
            result = run_noop_agent_once(
                artifact_dir=bundle_dir,
                question="summary",
                out_dir=out_dir,
            )
        self.assertEqual(result.status, "blocked")
        self.assertTrue(len(result.diagnostics) > 0)
        self.assertTrue(len(result.trace.runtime_diagnostics) > 0)
        # Verify the written JSON also contains runtime_diagnostics
        trace_data = json.loads(
            Path(result.artifact_path).read_text(encoding="utf-8")
        )
        self.assertTrue(len(trace_data.get("runtime_diagnostics", [])) > 0)


# ---------------------------------------------------------------------------
# Safety boundaries
# ---------------------------------------------------------------------------


class TestNoopAgentSafety(unittest.TestCase):

    def test_no_forbidden_imports(self) -> None:
        import fpga_devmind.agent_noop_runtime as mod

        source = Path(mod.__file__).read_text()
        lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip().startswith("import ")
            or line.strip().startswith("from ")
        ]
        import_text = "\n".join(lines)
        forbidden = ["requests", "urllib", "subprocess", "http.client"]
        for pattern in forbidden:
            self.assertNotIn(
                pattern,
                import_text,
                "Forbidden import '{}' found".format(pattern),
            )

    def test_no_forbidden_runtime_calls(self) -> None:
        import fpga_devmind.agent_noop_runtime as mod

        source = Path(mod.__file__).read_text()
        forbidden = [
            "requests.",
            "urllib.",
            "subprocess.",
            "os.system(",
            "os.popen(",
        ]
        for pattern in forbidden:
            self.assertNotIn(
                pattern,
                source,
                "Forbidden call '{}' found".format(pattern),
            )

    def test_no_target_project_mutation(self) -> None:
        """Artifact dir under fpga_project_* should not be written to."""
        with tempfile.TemporaryDirectory(prefix="fpga_project_test_") as proj:
            proj_dir = Path(proj)
            # Create minimal bundle inside fpga_project_*
            (proj_dir / "concept_trace_graph.json").write_text("{}")
            files_before = set(proj_dir.iterdir())

            out_dir = _make_safe_out()
            run_noop_agent_once(
                artifact_dir=proj_dir,
                question="summary",
                out_dir=out_dir,
            )
            files_after = set(proj_dir.iterdir())
            self.assertEqual(files_before, files_after)


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestNoopAgentCLI(unittest.TestCase):

    def test_cli_happy_path(self) -> None:
        bundle_dir = _make_synthetic_p1b_bundle()
        out_dir = _make_safe_out()
        exit_code = main([
            "agent-noop-run",
            "--artifact-dir", str(bundle_dir),
            "--question", "summary",
            "--out", str(out_dir),
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue((out_dir / "agent_runtime_trace.json").exists())

    def test_cli_unsafe_output_nonzero(self) -> None:
        bundle_dir = _make_synthetic_p1b_bundle()
        # Use a path inside fpga_project_* — ValueError → SystemExit(2)
        with self.assertRaises(SystemExit) as ctx:
            main([
                "agent-noop-run",
                "--artifact-dir", str(bundle_dir),
                "--question", "summary",
                "--out", "/tmp/fpga_project_test/output",
            ])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_cli_blocked_returns_nonzero(self) -> None:
        bundle_dir = _make_synthetic_p1b_bundle()
        out_dir = _make_safe_out()
        exit_code = main([
            "agent-noop-run",
            "--artifact-dir", str(bundle_dir),
            "--question", "xyzzy unrecognized",
            "--out", str(out_dir),
        ])
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
