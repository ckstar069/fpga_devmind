"""Tests for desktop agent plan preview models (T012).

Tests the pure-data read-only plan preview layer without PySide6.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.agent_panel_models import query_artifact_bundle
from fpga_devmind.desktop.agent_plan_models import build_agent_plan_preview
from fpga_devmind.desktop.artifact_loader import P1B_REQUIRED_ARTIFACTS, load_bundle


class TestAgentPlanModels(unittest.TestCase):
    """End-to-end tests for build_agent_plan_preview."""

    def _make_bundle(self) -> Path:
        """Create a P1b bundle with a mix of known and unknown claims."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))

        graph = {
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
                {
                    "node_id": "N_RTL_UNKNOWN",
                    "label": "RTL_UNKNOWN",
                    "kind": "concept",
                    "stage_id": "RTL",
                    "file_path": None,
                    "symbol_refs": [],
                    "evidence_ids": [],
                    "confidence": "unknown",
                    "notes": "RTL side missing",
                },
            ],
            "edges": [
                {
                    "edge_id": "E_MC_peak_idx_001_unknown",
                    "from_node_id": "N_CONCEPT_peak_idx",
                    "to_node_id": "N_RTL_UNKNOWN",
                    "label": "maps to",
                    "edge_type": "mapping",
                    "confidence": "unknown",
                    "evidence_ids": [],
                    "source_claim_ids": ["MC_peak_idx_UNKNOWN"],
                    "notes": None,
                },
            ],
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
                {
                    "claim_id": "MC_peak_idx_UNKNOWN",
                    "claim_type": "mapping_claim",
                    "statement": "",
                    "concept_ref": "peak_idx",
                    "l6_subject_ids": [],
                    "rtl_subject_ids": [],
                    "l5_l6_evidence_ids": [],
                    "rtl_evidence_ids": [],
                    "bridge_evidence_ids": [],
                    "bridge_kind": "unknown",
                    "confidence": "unknown",
                    "required_missing_evidence": [
                        "L5/L6 source evidence",
                        "RTL source evidence",
                    ],
                    "source_plan_step_id": None,
                    "notes": None,
                    "evidence_ids": [],
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
                {
                    "evidence_id": "E:p1b_rtl:path:5:20:1",
                    "source_type": "rtl_source",
                    "file_path": "/project/rtl/peak_detect.v",
                    "start_line": 5,
                    "end_line": 20,
                    "symbol": "peak_detect",
                    "excerpt_summary": "Module peak_detect",
                    "evidence_strength": "medium",
                    "snippet_complete": True,
                    "reliability_note": None,
                },
            ],
            "grounding_diagnostics": [
                {
                    "diagnostic_id": "GD_0001",
                    "target_claim_id": "MC_peak_idx_UNKNOWN",
                    "target_output_id": None,
                    "severity": "blocking",
                    "issue_type": "mapping_claim_without_evidence",
                    "recommended_action": "Add evidence",
                    "related_evidence_ids": [],
                    "message": "Claim has no evidence",
                },
            ],
            "uncertainty_notes": [
                {
                    "uncertainty_id": "U_001",
                    "topic": "rtl_missing",
                    "scope": "RTL",
                    "reason": "RTL side not found for peak_idx",
                    "current_interpretation": "Placeholder node used",
                    "needed_evidence": None,
                    "source_claim_ids": ["MC_peak_idx_UNKNOWN"],
                    "evidence_ids": [],
                    "severity_for_understanding": "medium",
                },
            ],
            "stage_views": [],
            "rtl_views": [],
            "task_request": {},
            "project_profile": {},
            "run_metadata": {},
        }

        grounding = {
            "schema_version": "p1b-grounding-report-0.1",
            "diagnostics": [],
            "summary": {
                "mapping_claims": 2,
                "blocking_diagnostics": 1,
                "unsupported_confirmed_mappings": 0,
                "naming_only_supported_mappings": 0,
                "one_sided_mapping_evidence": 0,
            },
        }

        metadata = {
            "schema_version": "p1b-run-metadata-0.1",
            "concept": "peak_idx",
            "project_root": "/tmp/test_project",
            "output_dir": str(tmp),
            "elapsed_seconds": 0.123,
            "status": "ok",
            "blocking_diagnostics": 1,
            "mapping_claims": 2,
            "evidence_items": 2,
            "artifacts": list(P1B_REQUIRED_ARTIFACTS),
        }

        (tmp / "concept_trace_graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        (tmp / "concept_trace_index.json").write_text("{}", encoding="utf-8")
        (tmp / "grounding_report.json").write_text(
            json.dumps(grounding), encoding="utf-8"
        )
        (tmp / "run_metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        (tmp / "concept_trace.md").write_text("# Trace\n", encoding="utf-8")
        (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
        return tmp

    # ------------------------------------------------------------------
    # Load state
    # ------------------------------------------------------------------

    def test_incomplete_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            bundle = load_bundle(p)
            plan = build_agent_plan_preview(bundle, "summary")
            self.assertFalse(plan.is_loaded)
            self.assertIsNotNone(plan.load_error)

    def test_non_p1b_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "random_data.json").write_text("{}")
            bundle = load_bundle(p)
            plan = build_agent_plan_preview(bundle, "summary")
            self.assertFalse(plan.is_loaded)
            self.assertIn("neither", plan.load_error or "")

    # ------------------------------------------------------------------
    # Intent coverage
    # ------------------------------------------------------------------

    def test_summary_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            plan = build_agent_plan_preview(bundle, "summary")
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "summary")
            self.assertEqual(len(plan.steps), 3)
            self.assertIn("run_metadata.json", plan.steps[0].read_artifacts)
            self.assertIn("concept_trace_graph.json", plan.steps[1].read_artifacts)
            self.assertIn("grounding_report.json", plan.steps[2].read_artifacts)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_claims_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "claims")
            plan = build_agent_plan_preview(bundle, "claims", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "claims")
            self.assertTrue(plan.steps)
            # Steps should inherit referenced IDs from response.
            self.assertTrue(plan.steps[0].referenced_claim_ids)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_evidence_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "evidence")
            plan = build_agent_plan_preview(bundle, "evidence", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "evidence")
            self.assertTrue(plan.steps)
            self.assertTrue(plan.steps[0].referenced_evidence_ids)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_diagnostics_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "diagnostics")
            plan = build_agent_plan_preview(bundle, "diagnostics", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "diagnostics")
            self.assertTrue(plan.steps)
            # Should contain dedup step because diagnostics exist.
            dedup_steps = [s for s in plan.steps if "deduplicate" in s.title.lower()]
            self.assertTrue(dedup_steps)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unknown_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "unknown")
            plan = build_agent_plan_preview(bundle, "unknown", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "unknown")
            self.assertTrue(plan.steps)
            # Should have inspect_missing step because unknown claims exist.
            missing_steps = [s for s in plan.steps if "missing" in s.title.lower()]
            self.assertTrue(missing_steps)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_nodes_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "nodes")
            plan = build_agent_plan_preview(bundle, "nodes", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "nodes")
            self.assertTrue(plan.steps)
            self.assertTrue(plan.steps[0].referenced_node_ids)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_edges_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "edges")
            plan = build_agent_plan_preview(bundle, "edges", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "edges")
            self.assertTrue(plan.steps)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_claim_detail_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "MC_peak_idx_001")
            plan = build_agent_plan_preview(bundle, "MC_peak_idx_001", response)
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "claim_detail")
            self.assertTrue(plan.steps)
            # Should inherit claim ID from response.
            self.assertIn("MC_peak_idx_001", plan.steps[0].referenced_claim_ids)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_evidence_detail_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(
                bundle, "E:p1b_concept:path:1:10:1"
            )
            plan = build_agent_plan_preview(
                bundle, "E:p1b_concept:path:1:10:1", response
            )
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "evidence_detail")
            self.assertTrue(plan.steps)
            self.assertIn(
                "E:p1b_concept:path:1:10:1",
                plan.steps[0].referenced_evidence_ids,
            )
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Unsupported
    # ------------------------------------------------------------------

    def test_unsupported_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            plan = build_agent_plan_preview(
                bundle, "What is the meaning of life?"
            )
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "unsupported")
            # Unsupported must not generate executable steps.
            self.assertEqual(len(plan.steps), 0)
            self.assertTrue(plan.safety_notes)
            self.assertIsNotNone(plan.unsupported_reason)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_question_plan(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            plan = build_agent_plan_preview(bundle, "   ")
            self.assertTrue(plan.is_loaded)
            self.assertEqual(plan.intent, "unsupported")
            self.assertEqual(len(plan.steps), 0)
            self.assertTrue(plan.safety_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Safety notes always present
    # ------------------------------------------------------------------

    def test_safety_notes_always_present(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            for q in [
                "summary",
                "claims",
                "evidence",
                "diagnostics",
                "unknown",
                "nodes",
                "edges",
                "MC_peak_idx_001",
                "E:p1b_concept:path:1:10:1",
                "nonsense",
            ]:
                with self.subTest(question=q):
                    plan = build_agent_plan_preview(bundle, q)
                    self.assertTrue(
                        plan.safety_notes,
                        f"Safety notes missing for question: {q}",
                    )
                    self.assertIn(
                        "read-only",
                        " ".join(plan.safety_notes).lower(),
                    )
                    self.assertIn(
                        "no external llm",
                        " ".join(plan.safety_notes).lower(),
                    )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Step properties
    # ------------------------------------------------------------------

    def test_step_is_not_executable(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            plan = build_agent_plan_preview(bundle, "summary")
            for step in plan.steps:
                self.assertFalse(
                    step.is_executable_now,
                    f"Step {step.step_id} should not be executable",
                )
                self.assertEqual(step.allowed_action, "read_only_preview")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_plan_with_response_inheritance(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            response = query_artifact_bundle(bundle, "claims")
            plan = build_agent_plan_preview(bundle, "claims", response)
            # At least one step should have inherited claim IDs.
            found = False
            for step in plan.steps:
                if step.referenced_claim_ids:
                    found = True
                    break
            self.assertTrue(found, "No step inherited referenced claim IDs")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
