"""Tests for desktop agent panel models (T011).

Tests the pure-data deterministic query layer without PySide6.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.agent_panel_models import (
    AgentPanelResponse,
    query_artifact_bundle,
)
from fpga_devmind.desktop.artifact_loader import P1B_REQUIRED_ARTIFACTS, load_bundle


class TestAgentPanelModels(unittest.TestCase):
    """End-to-end tests for query_artifact_bundle."""

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
            vm = query_artifact_bundle(bundle, "summary")
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)

    def test_non_p1b_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Create a random JSON file that does not match P1a or P1b patterns.
            (p / "random_data.json").write_text("{}")
            bundle = load_bundle(p)
            vm = query_artifact_bundle(bundle, "summary")
            self.assertFalse(vm.is_loaded)
            self.assertIn("neither", vm.load_error or "")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def test_summary_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "summary")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "summary")
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("映射声明", vm.answer_text)
            self.assertIn("节点", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_summary_chinese(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "这个 trace 做了什么")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "summary")
            self.assertIn("peak_idx", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def test_claims_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "claims")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "claims")
            self.assertIn("MC_peak_idx_001", vm.answer_text)
            self.assertIn("MC_peak_idx_UNKNOWN", vm.answer_text)
            self.assertIn("supported", vm.answer_text)
            self.assertIn("unknown", vm.answer_text)
            self.assertIn("MC_peak_idx_001", vm.referenced_claim_ids)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_claims_chinese(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "映射")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "claims")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def test_evidence_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "evidence")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "evidence")
            self.assertIn("E:p1b_concept:path:1:10:1", vm.answer_text)
            self.assertIn("E:p1b_rtl:path:5:20:1", vm.answer_text)
            self.assertIn("strong", vm.answer_text)
            self.assertIn("medium", vm.answer_text)
            self.assertEqual(len(vm.referenced_evidence_ids), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_evidence_chinese(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "证据")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "evidence")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def test_diagnostics_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "diagnostics")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "diagnostics")
            self.assertIn("GD_0001", vm.answer_text)
            self.assertIn("blocking", vm.answer_text)
            self.assertIn("MC_peak_idx_UNKNOWN", vm.answer_text)
            self.assertEqual(len(vm.referenced_diagnostic_ids), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_diagnostics_chinese(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "诊断")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "diagnostics")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Unknown / uncertainty
    # ------------------------------------------------------------------

    def test_unknown_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "unknown")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unknown")
            self.assertIn("MC_peak_idx_UNKNOWN", vm.answer_text)
            self.assertIn("missing", vm.answer_text)
            # Unknown should not be presented as error/pass/fail.
            self.assertNotIn("ERROR", vm.answer_text.upper())
            self.assertNotIn("FAIL", vm.answer_text.upper())
            self.assertIn("MC_peak_idx_UNKNOWN", vm.referenced_claim_ids)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unknown_chinese(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "不确定")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unknown")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def test_nodes_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "nodes")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "nodes")
            self.assertIn("N_CONCEPT_peak_idx", vm.answer_text)
            self.assertIn("N_RTL_UNKNOWN", vm.answer_text)
            self.assertEqual(len(vm.referenced_node_ids), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def test_edges_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "edges")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "edges")
            self.assertIn("E_MC_peak_idx_001_unknown", vm.answer_text)
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("RTL_UNKNOWN", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Specific claim ID
    # ------------------------------------------------------------------

    def test_specific_claim_id(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "Tell me about MC_peak_idx_001")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "claim_detail")
            self.assertIn("MC_peak_idx_001", vm.answer_text)
            self.assertIn("supported", vm.answer_text)
            self.assertIn("explicit_source_bridge", vm.answer_text)
            self.assertIn("MC_peak_idx_001", vm.referenced_claim_ids)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_specific_unknown_claim_id(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "What is MC_peak_idx_UNKNOWN?")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "claim_detail")
            self.assertIn("MC_peak_idx_UNKNOWN", vm.answer_text)
            self.assertIn("unknown", vm.answer_text)
            # Unknown confidence should not be an error.
            self.assertNotIn("ERROR", vm.answer_text.upper())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_claim_id(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "MC_nonexistent_999")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "claim_detail")
            self.assertIn("未找到声明", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Specific evidence ID
    # ------------------------------------------------------------------

    def test_specific_evidence_id(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(
                bundle, "Show evidence E:p1b_concept:path:1:10:1"
            )
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "evidence_detail")
            self.assertIn("E:p1b_concept:path:1:10:1", vm.answer_text)
            self.assertIn("PeakDetector", vm.answer_text)
            self.assertIn("strong", vm.answer_text)
            self.assertIn(vm.referenced_evidence_ids[0], "E:p1b_concept:path:1:10:1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_evidence_id(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "E:nonexistent")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "evidence_detail")
            self.assertIn("未找到证据", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Unsupported
    # ------------------------------------------------------------------

    def test_unsupported_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "What is the meaning of life?")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unsupported")
            self.assertIn("not supported", vm.answer_text)
            self.assertIn("External LLM is not enabled", vm.answer_text)
            self.assertIsNotNone(vm.unsupported_reason)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_question(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            # Empty question after strip is caught by the caller (GUI), but
            # the model itself handles it as unsupported since no keywords match.
            vm = query_artifact_bundle(bundle, "   ")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unsupported")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


    # ------------------------------------------------------------------
    # No pass/fail semantics
    # ------------------------------------------------------------------

    def test_no_pass_fail_in_diagnostics_answer(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "diagnostics")
            self.assertTrue(vm.is_loaded)
            # Blocking diagnostic is a warning, not a PASS/HOLD audit result.
            self.assertNotIn("PASS", vm.answer_text.upper())
            self.assertNotIn("HOLD", vm.answer_text.upper())
            self.assertNotIn("FAIL", vm.answer_text.upper())
            self.assertIn("blocking", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_pass_fail_in_unknown_answer(self):
        tmp = self._make_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "unknown")
            self.assertTrue(vm.is_loaded)
            self.assertNotIn("PASS", vm.answer_text.upper())
            self.assertNotIn("HOLD", vm.answer_text.upper())
            self.assertNotIn("FAIL", vm.answer_text.upper())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Diagnostics deduplication (T011a)
    # ------------------------------------------------------------------

    def _make_bundle_with_dup_diags(self) -> Path:
        """Create a P1b bundle where the same diagnostic appears in both
        graph.grounding_diagnostics and grounding_report.diagnostics."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_dedup_"))

        graph = {
            "schema_version": "0.1.0",
            "concept": "dup_test",
            "nodes": [],
            "edges": [],
            "mapping_claims": [
                {
                    "claim_id": "MC_dup_target",
                    "claim_type": "mapping_claim",
                    "statement": "dup",
                    "concept_ref": "dup",
                    "l6_subject_ids": [],
                    "rtl_subject_ids": [],
                    "l5_l6_evidence_ids": [],
                    "rtl_evidence_ids": [],
                    "bridge_evidence_ids": [],
                    "bridge_kind": "unknown",
                    "confidence": "unknown",
                    "required_missing_evidence": [],
                    "source_plan_step_id": None,
                    "notes": None,
                    "evidence_ids": [],
                },
            ],
            "evidence_items": [],
            "grounding_diagnostics": [
                {
                    "diagnostic_id": "GD_0001",
                    "target_claim_id": "MC_dup_target",
                    "target_output_id": None,
                    "severity": "blocking",
                    "issue_type": "mapping_claim_without_evidence",
                    "recommended_action": "Add evidence",
                    "related_evidence_ids": [],
                    "message": "Claim has no evidence",
                },
            ],
            "uncertainty_notes": [],
            "stage_views": [],
            "rtl_views": [],
            "task_request": {},
            "project_profile": {},
            "run_metadata": {},
        }

        # Duplicate diagnostic in grounding_report with same diagnostic_id.
        grounding = {
            "schema_version": "p1b-grounding-report-0.1",
            "diagnostics": [
                {
                    "diagnostic_id": "GD_0001",
                    "target_claim_id": "MC_dup_target",
                    "target_output_id": None,
                    "severity": "blocking",
                    "issue_type": "mapping_claim_without_evidence",
                    "recommended_action": "Add evidence",
                    "related_evidence_ids": [],
                    "message": "Claim has no evidence",
                },
                # Another distinct diagnostic (no id) for fallback-key dedup test.
                {
                    "target_claim_id": "MC_dup_target",
                    "issue_type": "fallback_dup",
                    "message": "Same fallback key",
                },
            ],
            "summary": {
                "mapping_claims": 1,
                "blocking_diagnostics": 2,
            },
        }

        metadata = {
            "schema_version": "p1b-run-metadata-0.1",
            "concept": "dup_test",
            "project_root": "/tmp/test_project",
            "output_dir": str(tmp),
            "elapsed_seconds": 0.001,
            "status": "ok",
            "blocking_diagnostics": 2,
            "mapping_claims": 1,
            "evidence_items": 0,
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

    def test_diagnostics_dedupe_by_diagnostic_id(self):
        tmp = self._make_bundle_with_dup_diags()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "diagnostics")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "diagnostics")
            # GD_0001 appears in both graph and grounding; should show once.
            self.assertEqual(vm.answer_text.count("GD_0001"), 1)
            self.assertEqual(len(vm.referenced_diagnostic_ids), 2)
            # The two distinct diagnostics are GD_0001 and the fallback-key one.
            self.assertIn("GD_0001", vm.referenced_diagnostic_ids)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_claim_detail_deduped_diag_count(self):
        tmp = self._make_bundle_with_dup_diags()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "MC_dup_target")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "claim_detail")
            # GD_0001 duplicated in graph + grounding should count as 1.
            self.assertIn("关联诊断：2 条", vm.answer_text)
            # Should NOT say 3 (1 unique + 2 duplicates).
            self.assertNotIn("关联诊断：3 条", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_diagnostics_dedupe_fallback_key(self):
        tmp = self._make_bundle_with_dup_diags()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "diagnostics")
            self.assertTrue(vm.is_loaded)
            # The fallback-key diagnostic (no diagnostic_id) should appear once.
            self.assertEqual(vm.answer_text.count("fallback_dup"), 1)
            self.assertEqual(vm.answer_text.count("Same fallback key"), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestAgentPanelProjectBundle(unittest.TestCase):
    """Project bundle agent query tests (T024)."""

    def _make_project_bundle(self) -> Path:
        """Create a project bundle."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_proj_"))
        graph = {
            "schema_version": "project-understanding-0.1",
            "project_id": "test_project",
            "nodes": [
                {"node_id": "PUG_PROJECT", "label": "test_project", "kind": "project"},
                {
                    "node_id": "PUG_CONCEPT_peak_idx",
                    "label": "peak_idx",
                    "kind": "concept",
                    "confidence": "supported",
                },
                {
                    "node_id": "PUG_CONCEPT_cfo",
                    "label": "cfo",
                    "kind": "concept",
                    "confidence": "unknown",
                },
                {
                    "node_id": "PUG_CLAIM_peak_idx_MC_001",
                    "label": "MC_001",
                    "kind": "mapping_claim",
                    "confidence": "supported",
                    "concept": "peak_idx",
                },
            ],
            "edges": [
                {
                    "edge_id": "E_SHARED_FILE_peak_idx_cfo",
                    "from_node_id": "PUG_CONCEPT_peak_idx",
                    "to_node_id": "PUG_CONCEPT_cfo",
                    "edge_type": "shares_file",
                    "confidence": "inferred",
                },
                {
                    "edge_id": "E_HAS_CLAIM_peak_idx",
                    "from_node_id": "PUG_CONCEPT_peak_idx",
                    "to_node_id": "PUG_CLAIM_peak_idx_MC_001",
                    "edge_type": "has_claim",
                    "confidence": "supported",
                },
            ],
            "grounding_diagnostics": [],
            "uncertainty_notes": [],
        }
        metadata = {
            "schema_version": "p1b-project-run-metadata-0.1",
            "command": "p1b-trace-project",
            "project_root": "/tmp/test_project",
            "concepts_processed": ["peak_idx", "cfo"],
            "status": "ok",
        }
        (tmp / "project_understanding_graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        (tmp / "project_understanding_index.json").write_text(
            json.dumps({"concept_index": {}}), encoding="utf-8"
        )
        (tmp / "run_metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        (tmp / "project_understanding.md").write_text("# Project\n", encoding="utf-8")
        (tmp / "project_understanding.mmd").write_text("graph TD\n", encoding="utf-8")
        return tmp

    def test_project_summary(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "summary")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "summary")
            self.assertIn("test_project", vm.answer_text)
            self.assertIn("peak_idx", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_concepts(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "有哪些概念")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "concepts")
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("cfo", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_mapped(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "哪些概念有 RTL 映射")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "mapped")
            self.assertIn("peak_idx", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_unknown(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "哪些概念还不确定")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unknown")
            self.assertIn("cfo", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_shared(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "哪些文件被多个概念共享")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "shared")
            self.assertIn("peak_idx", vm.answer_text)
            self.assertIn("cfo", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_graph(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "图画出")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "graph")
            self.assertIn("节点", vm.answer_text)
            self.assertIn("边", vm.answer_text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_unsupported(self):
        tmp = self._make_project_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = query_artifact_bundle(bundle, "What is the meaning of life?")
            self.assertTrue(vm.is_loaded)
            self.assertEqual(vm.response_kind, "unsupported")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
