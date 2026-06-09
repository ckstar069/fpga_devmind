"""Tests for agent trace view models (T017).

Tests the pure-data Agent Runtime Trace view-model layer without PySide6.

No external API, no LLM, no Vivado.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.agent_trace_view_models import (
    build_agent_runtime_trace_view_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_full_agent_runtime_trace() -> dict:
    """Build a realistic agent_runtime_trace.json dict."""
    return {
        "schema_version": "agent-runtime-contract-0.1",
        "task": {
            "task_id": "TASK_001",
            "question": "What is the peak_idx concept?",
            "bundle_type": "p1b",
            "concept": "peak_idx",
            "constraints": ["read_only", "no_llm"],
        },
        "observations": [
            {
                "observation_id": "OBS_001",
                "summary": "Loaded concept_trace_graph.json",
                "artifact_refs": ["concept_trace_graph.json"],
            },
            {
                "observation_id": "OBS_002",
                "summary": "Loaded grounding_report.json",
                "artifact_refs": ["grounding_report.json"],
            },
        ],
        "reasoning": [
            {
                "reasoning_id": "RSN_001",
                "confidence": "supported",
                "summary": "Concept peak_idx has 2 mapping claims",
                "referenced_observation_ids": ["OBS_001"],
            },
        ],
        "plans": [
            {
                "plan_id": "PLAN_001",
                "intent": "summarize_concept",
                "steps": [
                    {
                        "proposal_id": "PROP_001",
                        "allowed_action": "read_artifact",
                        "rationale": "Read trace graph for summary",
                        "expected_read_artifacts": [
                            "concept_trace_graph.json"
                        ],
                    },
                    {
                        "proposal_id": "PROP_002",
                        "allowed_action": "read_artifact",
                        "rationale": "Read grounding report",
                        "expected_read_artifacts": [
                            "grounding_report.json"
                        ],
                    },
                ],
            },
        ],
        "tool_results": [
            {
                "result_id": "TR_001",
                "status": "simulated",
                "result_summary": "Trace graph loaded successfully",
            },
        ],
        "answers": [
            {
                "answer_id": "ANS_001",
                "confidence": "supported",
                "answer_text": "peak_idx maps to peak_detect module and peak_valid signal",
                "limitations": ["no_llm_semantic_reasoning"],
            },
        ],
        "graph_write_proposals": [
            {
                "graph_write_id": "GW_001",
                "is_write_allowed": False,
                "blocking_reasons": ["no_llm_semantic_reasoning"],
                "referenced_answer_ids": ["ANS_001"],
            },
        ],
        "runtime_diagnostics": [
            {
                "severity": "info",
                "message": "Agent dry-run completed successfully",
            },
        ],
    }


def _make_agent_runtime_bundle(
    trace: dict | None = None,
    include_answer_md: bool = True,
) -> Path:
    """Create a minimal agent_runtime bundle directory."""
    tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_art_"))
    if trace is None:
        trace = _make_full_agent_runtime_trace()
    (tmp / "agent_runtime_trace.json").write_text(
        json.dumps(trace), encoding="utf-8"
    )
    if include_answer_md:
        (tmp / "answer.md").write_text(
            "# Answer\n\npeak_idx maps to peak_detect.", encoding="utf-8"
        )
    return tmp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentRuntimeTraceViewModel(unittest.TestCase):
    """End-to-end tests for build_agent_runtime_trace_view_model."""

    def test_detect_agent_runtime_bundle_type(self) -> None:
        """agent_runtime_trace.json is detected as agent_runtime bundle."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            self.assertEqual(bundle.bundle_type, "agent_runtime")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_bundle_with_trace_and_answer(self) -> None:
        """Bundle with trace + answer.md loads completely."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            self.assertTrue(bundle.is_complete)
            self.assertIn("agent_runtime_trace.json", bundle.artifacts)
            self.assertIn("answer.md", bundle.artifacts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_invalid_json_yields_load_diagnostic(self) -> None:
        """Malformed JSON in trace produces a load error diagnostic."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_art_"))
        try:
            (tmp / "agent_runtime_trace.json").write_text(
                "{bad json!!}", encoding="utf-8"
            )
            bundle = load_bundle(tmp)
            self.assertEqual(bundle.bundle_type, "agent_runtime")
            # The bundle should have error diagnostics for the bad JSON.
            error_diags = [
                d
                for d in bundle.diagnostics
                if d.severity == "error"
            ]
            self.assertTrue(len(error_diags) > 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_view_model_happy_path(self) -> None:
        """Full trace produces is_loaded=True with all sections."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertIsNone(vm.load_error)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_summary_counts_correct(self) -> None:
        """Summary rows include correct counts for all sections."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            summary_fields = {r.field: r.value for r in vm.summary_rows}
            self.assertEqual(summary_fields["Schema Version"], "agent-runtime-contract-0.1")
            self.assertEqual(summary_fields["Task ID"], "TASK_001")
            self.assertEqual(summary_fields["Question"], "What is the peak_idx concept?")
            self.assertEqual(summary_fields["Observations"], "2")
            self.assertEqual(summary_fields["Reasoning"], "1")
            self.assertEqual(summary_fields["Plans"], "1")
            self.assertEqual(summary_fields["Tool Results"], "1")
            self.assertEqual(summary_fields["Answers"], "1")
            self.assertEqual(summary_fields["Graph Write Proposals"], "1")
            self.assertEqual(summary_fields["Runtime Diagnostics"], "1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_step_rows_include_all_sections(self) -> None:
        """Step rows cover task, observation, reasoning, plan, proposal,
        result, answer, and graph_write sections."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            sections = {r.section for r in vm.step_rows}
            self.assertIn("task", sections)
            self.assertIn("observation", sections)
            self.assertIn("reasoning", sections)
            self.assertIn("plan", sections)
            self.assertIn("proposal", sections)
            self.assertIn("result", sections)
            self.assertIn("answer", sections)
            self.assertIn("graph_write", sections)
            # 1 task + 2 obs + 1 reasoning + 1 plan + 2 proposals + 1 result
            # + 1 answer + 1 graph_write = 10
            self.assertEqual(len(vm.step_rows), 10)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_runtime_diagnostics_displayed(self) -> None:
        """Runtime diagnostics appear as diagnostic rows."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.diagnostic_rows), 1)
            self.assertEqual(vm.diagnostic_rows[0].severity, "info")
            self.assertIn(
                "dry-run completed", vm.diagnostic_rows[0].message
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_graph_write_shows_blocked_never_pass_hold(self) -> None:
        """Graph write status uses blocked/allowed, never PASS/HOLD."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            gw_rows = [
                r for r in vm.step_rows if r.section == "graph_write"
            ]
            self.assertEqual(len(gw_rows), 1)
            self.assertEqual(gw_rows[0].status, "blocked")
            # Ensure no PASS/HOLD anywhere.
            for row in vm.step_rows:
                self.assertNotIn("PASS", row.status)
                self.assertNotIn("HOLD", row.status)
                self.assertNotIn("pass", row.status)
                self.assertNotIn("hold", row.status)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_non_agent_runtime_bundle_returns_not_loaded(self) -> None:
        """A P1b bundle returns is_loaded=False with error message."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_art_"))
        try:
            # Create a P1b bundle (no agent_runtime_trace.json)
            (tmp / "concept_trace_graph.json").write_text("{}", encoding="utf-8")
            (tmp / "concept_trace_index.json").write_text("{}", encoding="utf-8")
            (tmp / "grounding_report.json").write_text("{}", encoding="utf-8")
            (tmp / "run_metadata.json").write_text("{}", encoding="utf-8")
            (tmp / "concept_trace.md").write_text("# Trace\n", encoding="utf-8")
            (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("agent runtime", vm.load_error or "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_trace_json_returns_load_error(self) -> None:
        """An agent_runtime bundle missing the trace JSON returns error."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_art_"))
        try:
            # Only answer.md, no agent_runtime_trace.json
            # This would be detected as "unknown" since no marker file
            # But we can test the view model directly with a manually-built
            # bundle that has the right type but missing trace.
            from fpga_devmind.desktop.artifact_loader import ArtifactBundle
            bundle = ArtifactBundle(
                bundle_type="agent_runtime",
                directory=tmp,
            )
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("not found", vm.load_error or "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_answer_limitations_shown_in_summary(self) -> None:
        """Answer limitations appear in summary rows."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            summary_fields = {r.field: r.value for r in vm.summary_rows}
            self.assertIn("Answer Limitations", summary_fields)
            self.assertIn(
                "no_llm_semantic_reasoning",
                summary_fields["Answer Limitations"],
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_graph_write_allowed_shows_allowed(self) -> None:
        """An allowed graph write shows status 'allowed'."""
        trace = _make_full_agent_runtime_trace()
        trace["graph_write_proposals"][0]["is_write_allowed"] = True
        trace["graph_write_proposals"][0]["blocking_reasons"] = []
        tmp = _make_agent_runtime_bundle(trace=trace)
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            gw_rows = [
                r for r in vm.step_rows if r.section == "graph_write"
            ]
            self.assertEqual(len(gw_rows), 1)
            self.assertEqual(gw_rows[0].status, "allowed")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_constraints_shown_in_summary(self) -> None:
        """Task constraints appear in summary rows."""
        tmp = _make_agent_runtime_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_agent_runtime_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            summary_fields = {r.field: r.value for r in vm.summary_rows}
            self.assertIn("Constraints", summary_fields)
            self.assertIn("read_only", summary_fields["Constraints"])
            self.assertIn("no_llm", summary_fields["Constraints"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
