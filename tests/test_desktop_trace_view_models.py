"""Tests for desktop trace view models (T010).

Tests the pure-data trace view-model layer without PySide6.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.desktop.artifact_loader import P1B_REQUIRED_ARTIFACTS, load_bundle
from fpga_devmind.desktop.trace_view_models import (
    build_concept_trace_view_model,
)


class TestConceptTraceViewModel(unittest.TestCase):
    """End-to-end tests for build_concept_trace_view_model."""

    def _make_complete_p1b_bundle(self) -> Path:
        """Create a complete P1b bundle with realistic trace data."""
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
                    "node_id": "N_RTL_module_peak_detect",
                    "label": "peak_detect",
                    "kind": "rtl_module",
                    "stage_id": "RTL",
                    "file_path": "/project/rtl/peak_detect.v",
                    "symbol_refs": ["module:peak_detect"],
                    "evidence_ids": ["E:p1b_rtl:path:5:20:1"],
                    "confidence": "supported",
                    "notes": None,
                },
                {
                    "node_id": "N_RTL_signal_peak_valid",
                    "label": "peak_valid",
                    "kind": "rtl_signal",
                    "stage_id": "RTL",
                    "file_path": "/project/rtl/peak_detect.v",
                    "symbol_refs": ["signal:peak_valid"],
                    "evidence_ids": ["E:p1b_rtl:path:7:15:2"],
                    "confidence": "supported",
                    "notes": None,
                },
            ],
            "edges": [
                {
                    "edge_id": "E_MC_peak_idx_001_peak_detect",
                    "from_node_id": "N_CONCEPT_peak_idx",
                    "to_node_id": "N_RTL_module_peak_detect",
                    "label": "maps to",
                    "edge_type": "mapping",
                    "confidence": "supported",
                    "evidence_ids": ["E:p1b_concept:path:1:10:1", "E:p1b_rtl:path:5:20:1"],
                    "source_claim_ids": ["MC_peak_idx_001"],
                    "notes": None,
                },
                {
                    "edge_id": "E_MC_peak_idx_001_peak_valid",
                    "from_node_id": "N_CONCEPT_peak_idx",
                    "to_node_id": "N_RTL_signal_peak_valid",
                    "label": "maps to",
                    "edge_type": "mapping",
                    "confidence": "inferred",
                    "evidence_ids": ["E:p1b_rtl:path:7:15:2"],
                    "source_claim_ids": ["MC_peak_idx_001"],
                    "notes": None,
                },
                {
                    "edge_id": "E_dangling",
                    "from_node_id": "N_CONCEPT_peak_idx",
                    "to_node_id": "N_NONEXISTENT",
                    "label": "maps to",
                    "edge_type": "mapping",
                    "confidence": "unknown",
                    "evidence_ids": [],
                    "source_claim_ids": [],
                    "notes": None,
                },
            ],
            "mapping_claims": [
                {
                    "claim_id": "MC_peak_idx_001",
                    "claim_type": "mapping_claim",
                    "statement": "peak_idx maps to peak_detect module",
                    "concept_ref": "peak_idx",
                    "l6_subject_ids": ["class:PeakDetector"],
                    "rtl_subject_ids": ["module:peak_detect"],
                    "l5_l6_evidence_ids": ["E:p1b_concept:path:1:10:1"],
                    "rtl_evidence_ids": ["E:p1b_rtl:path:5:20:1", "E:p1b_rtl:path:7:15:2"],
                    "bridge_evidence_ids": ["E:p1b_concept:path:1:10:1"],
                    "bridge_kind": "explicit_source_bridge",
                    "confidence": "supported",
                    "required_missing_evidence": [],
                    "source_plan_step_id": None,
                    "notes": None,
                    "evidence_ids": [
                        "E:p1b_concept:path:1:10:1",
                        "E:p1b_rtl:path:5:20:1",
                        "E:p1b_rtl:path:7:15:2",
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
                    "excerpt_summary": "Class PeakDetector implements peak_idx",
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
                {
                    "evidence_id": "E:p1b_rtl:path:7:15:2",
                    "source_type": "rtl_source",
                    "file_path": "/project/rtl/peak_detect.v",
                    "start_line": 7,
                    "end_line": 15,
                    "symbol": "peak_valid",
                    "excerpt_summary": "Signal peak_valid",
                    "evidence_strength": "weak",
                    "snippet_complete": True,
                    "reliability_note": None,
                },
            ],
            "grounding_diagnostics": [
                {
                    "diagnostic_id": "GD_0001",
                    "target_claim_id": "MC_peak_idx_UNKNOWN",
                    "target_output_id": None,
                    "severity": "non_blocking",
                    "issue_type": "one_sided_mapping_evidence",
                    "recommended_action": "Review claim evidence",
                    "related_evidence_ids": [],
                    "message": "Claim has one-sided evidence",
                },
            ],
            "uncertainty_notes": [],
            "stage_views": [],
            "rtl_views": [],
            "task_request": {},
            "project_profile": {},
            "run_metadata": {},
        }

        index = {
            "schema_version": "0.1.0",
            "concept": "peak_idx",
            "claim_index": {
                "MC_peak_idx_001": {
                    "confidence": "supported",
                    "l5_l6_evidence_ids": ["E:p1b_concept:path:1:10:1"],
                    "rtl_evidence_ids": [
                        "E:p1b_rtl:path:5:20:1",
                        "E:p1b_rtl:path:7:15:2",
                    ],
                    "bridge_kind": "explicit_source_bridge",
                },
            },
            "evidence_index": {
                "E:p1b_concept:path:1:10:1": {
                    "source_type": "concept_occurrence",
                    "claim_ids": ["MC_peak_idx_001"],
                },
                "E:p1b_rtl:path:5:20:1": {
                    "source_type": "rtl_source",
                    "claim_ids": ["MC_peak_idx_001"],
                },
                "E:p1b_rtl:path:7:15:2": {
                    "source_type": "rtl_source",
                    "claim_ids": ["MC_peak_idx_001"],
                },
            },
            "node_index": {
                "N_CONCEPT_peak_idx": {
                    "kind": "concept",
                },
                "N_RTL_module_peak_detect": {
                    "kind": "rtl_module",
                    "stage_id": "RTL",
                    "file_path": "/project/rtl/peak_detect.v",
                },
            },
            "edge_index": {
                "E_MC_peak_idx_001_peak_detect": {
                    "from": "N_CONCEPT_peak_idx",
                    "to": "N_RTL_module_peak_detect",
                    "edge_type": "mapping",
                },
            },
            "cross_references": {},
        }

        grounding = {
            "schema_version": "p1b-grounding-report-0.1",
            "diagnostics": [
                {
                    "diagnostic_id": "GD_0002",
                    "target_claim_id": "MC_peak_idx_UNKNOWN",
                    "target_output_id": None,
                    "severity": "blocking",
                    "issue_type": "mapping_claim_without_evidence",
                    "recommended_action": "Add evidence",
                    "related_evidence_ids": [],
                    "message": "Claim has no evidence",
                },
            ],
            "summary": {
                "mapping_claims": 2,
                "blocking_diagnostics": 1,
                "unsupported_confirmed_mappings": 0,
                "naming_only_supported_mappings": 0,
                "one_sided_mapping_evidence": 1,
            },
        }

        metadata = {
            "schema_version": "p1b-run-metadata-0.1",
            "concept": "peak_idx",
            "project_root": "/tmp/test_project",
            "output_dir": str(tmp),
            "elapsed_seconds": 0.456,
            "status": "ok",
            "blocking_diagnostics": 1,
            "mapping_claims": 2,
            "evidence_items": 3,
            "artifacts": list(P1B_REQUIRED_ARTIFACTS),
        }

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
        (tmp / "concept_trace.md").write_text("# Trace\n", encoding="utf-8")
        (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
        return tmp

    # ------------------------------------------------------------------
    # Load state
    # ------------------------------------------------------------------

    def test_trace_vm_loads_complete_p1b(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertIsNone(vm.load_error)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_non_p1b_bundle_shows_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "project_graph.json").write_text("{}")
            (p / "trace_index.json").write_text("{}")
            bundle = load_bundle(p)
            vm = build_concept_trace_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("P1b bundles only", vm.load_error or "")

    def test_incomplete_bundle_load_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "concept_trace_graph.json").write_text("{}")
            bundle = load_bundle(p)
            vm = build_concept_trace_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIsNotNone(vm.load_error)

    # ------------------------------------------------------------------
    # Node rows
    # ------------------------------------------------------------------

    def test_nodes_parsed_from_graph(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.nodes), 3)
            node_ids = {n.node_id for n in vm.nodes}
            self.assertIn("N_CONCEPT_peak_idx", node_ids)
            self.assertIn("N_RTL_module_peak_detect", node_ids)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_node_evidence_count(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            concept_node = next(
                (n for n in vm.nodes if n.node_id == "N_CONCEPT_peak_idx"),
                None,
            )
            self.assertIsNotNone(concept_node)
            self.assertEqual(concept_node.evidence_count, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_node_has_diagnostics(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            # The unknown claim has 2 diagnostics (1 graph + 1 grounding).
            # Node diagnostics are keyed by node_id, but our test data has
            # diagnostics targeting claims.  has_diagnostics on nodes uses
            # node_id lookup, so nodes should not have diagnostics here.
            for node in vm.nodes:
                self.assertFalse(node.has_diagnostics)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Edge rows
    # ------------------------------------------------------------------

    def test_edges_with_resolved_labels(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.edges), 3)
            edge = next(
                (
                    e
                    for e in vm.edges
                    if e.edge_id == "E_MC_peak_idx_001_peak_detect"
                ),
                None,
            )
            self.assertIsNotNone(edge)
            self.assertEqual(edge.from_label, "peak_idx")
            self.assertEqual(edge.to_label, "peak_detect")
            self.assertEqual(edge.edge_type, "mapping")
            self.assertEqual(edge.confidence, "supported")
            self.assertIn("MC_peak_idx_001", edge.claim_refs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_dangling_edge_endpoint_marked_unresolved(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            edge = next(
                (e for e in vm.edges if e.edge_id == "E_dangling"),
                None,
            )
            self.assertIsNotNone(edge)
            self.assertIn("unresolved", edge.to_label)
            self.assertIn("N_NONEXISTENT", edge.to_label)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Claim rows
    # ------------------------------------------------------------------

    def test_claims_with_evidence_counts(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.claims), 2)
            claim = next(
                (c for c in vm.claims if c.claim_id == "MC_peak_idx_001"),
                None,
            )
            self.assertIsNotNone(claim)
            self.assertEqual(claim.concept_ref, "peak_idx")
            self.assertEqual(claim.confidence, "supported")
            self.assertEqual(claim.bridge_kind, "explicit_source_bridge")
            self.assertEqual(claim.l5_l6_evidence_count, 1)
            self.assertEqual(claim.rtl_evidence_count, 2)
            self.assertEqual(claim.bridge_evidence_count, 1)
            self.assertEqual(claim.required_missing_evidence, "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unknown_claim_counts(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            claim = next(
                (
                    c
                    for c in vm.claims
                    if c.claim_id == "MC_peak_idx_UNKNOWN"
                ),
                None,
            )
            self.assertIsNotNone(claim)
            self.assertEqual(claim.confidence, "unknown")
            self.assertEqual(claim.bridge_kind, "unknown")
            self.assertIn("L5/L6 source evidence", claim.required_missing_evidence)
            self.assertEqual(claim.diagnostic_count, 2)  # graph + grounding
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Evidence rows
    # ------------------------------------------------------------------

    def test_evidence_referenced_by_claims(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.evidence), 3)
            ev = next(
                (
                    e
                    for e in vm.evidence
                    if e.evidence_id == "E:p1b_concept:path:1:10:1"
                ),
                None,
            )
            self.assertIsNotNone(ev)
            self.assertEqual(ev.source_type, "concept_occurrence")
            self.assertIn("MC_peak_idx_001", ev.referenced_by_claims)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Diagnostic rows
    # ------------------------------------------------------------------

    def test_diagnostics_linked_to_claims(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.diagnostics), 2)
            diag = next(
                (d for d in vm.diagnostics if d.diagnostic_id == "GD_0001"),
                None,
            )
            self.assertIsNotNone(diag)
            self.assertEqual(diag.severity, "non_blocking")
            self.assertEqual(diag.target_claim_id, "MC_peak_idx_UNKNOWN")
            self.assertIn("one_sided", diag.issue_type)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_diagnostics_from_grounding_report(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            diag = next(
                (d for d in vm.diagnostics if d.diagnostic_id == "GD_0002"),
                None,
            )
            self.assertIsNotNone(diag)
            self.assertEqual(diag.severity, "blocking")
            self.assertEqual(diag.target_claim_id, "MC_peak_idx_UNKNOWN")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Unknown confidence semantics
    # ------------------------------------------------------------------

    def test_unknown_confidence_not_error(self):
        tmp = self._make_complete_p1b_bundle()
        try:
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            claim = next(
                (
                    c
                    for c in vm.claims
                    if c.confidence == "unknown"
                ),
                None,
            )
            self.assertIsNotNone(claim)
            # Unknown confidence should be a normal row, not treated as error.
            self.assertEqual(claim.confidence, "unknown")
            self.assertNotEqual(claim.bridge_kind, "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Empty graph
    # ------------------------------------------------------------------

    def test_empty_graph_loads_empty_rows(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            graph = {
                "schema_version": "0.1.0",
                "concept": "test_empty",
                "nodes": [],
                "edges": [],
                "mapping_claims": [],
                "evidence_items": [],
                "grounding_diagnostics": [],
                "uncertainty_notes": [],
            }
            for name in P1B_REQUIRED_ARTIFACTS:
                if name == "concept_trace_graph.json":
                    (tmp / name).write_text(json.dumps(graph), encoding="utf-8")
                else:
                    (tmp / name).write_text("{}" if name.endswith(".json") else "")
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertTrue(vm.is_loaded)
            self.assertEqual(len(vm.nodes), 0)
            self.assertEqual(len(vm.edges), 0)
            self.assertEqual(len(vm.claims), 0)
            self.assertEqual(len(vm.evidence), 0)
            self.assertEqual(len(vm.diagnostics), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Missing graph file
    # ------------------------------------------------------------------

    def test_missing_graph_returns_load_error(self):
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_p1b_"))
        try:
            for name in P1B_REQUIRED_ARTIFACTS:
                if name != "concept_trace_graph.json":
                    (tmp / name).write_text("{}" if name.endswith(".json") else "")
            bundle = load_bundle(tmp)
            vm = build_concept_trace_view_model(bundle)
            self.assertFalse(vm.is_loaded)
            self.assertIn("graph", vm.load_error or "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
