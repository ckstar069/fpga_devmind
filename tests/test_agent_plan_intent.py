"""Tests for Agent Plan Preview intent consistency with Agent Panel (T023).

Verifies that the same Chinese suggested questions produce matching
intents in both agent answers and plan previews.

Pure Python — no PySide6 required.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.agent_panel_models import query_artifact_bundle
from fpga_devmind.desktop.agent_plan_models import build_agent_plan_preview
from fpga_devmind.desktop.artifact_loader import load_bundle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_p1b_graph() -> dict[str, Any]:
    """Build a P1b concept_trace_graph with mapping_claims."""
    return {
        "schema_version": "concept-trace-graph-0.1",
        "concept": "peak_idx",
        "nodes": [
            {
                "node_id": "N1",
                "label": "peak_idx",
                "kind": "stage_view",
                "stage": "L6",
                "confidence": "supported",
                "evidence_ids": ["EV_0"],
            },
            {
                "node_id": "N2",
                "label": "rtl_peak",
                "kind": "rtl_module",
                "stage": "RTL",
                "confidence": "inferred",
                "evidence_ids": ["EV_1"],
            },
        ],
        "edges": [
            {
                "edge_id": "E1",
                "from_node_id": "N1",
                "to_node_id": "N2",
                "edge_type": "bridge",
                "confidence": "supported",
            }
        ],
        "mapping_claims": [
            {
                "claim_id": "MC_peak_idx_001",
                "concept": "peak_idx",
                "confidence": "supported",
                "bridge_kind": "calculation_role",
                "evidence_ids": ["EV_0", "EV_1"],
                "l5_l6_evidence_ids": ["EV_0"],
                "rtl_evidence_ids": ["EV_1"],
            }
        ],
        "evidence_items": [
            {
                "evidence_id": "EV_0",
                "source_type": "concept_occurrence",
                "evidence_strength": "strong",
                "file_path": "/some/file.py",
                "symbol": "func_a",
            },
            {
                "evidence_id": "EV_1",
                "source_type": "rtl_source",
                "evidence_strength": "medium",
                "file_path": "/some/rtl.v",
                "symbol": "module_a",
            },
        ],
        "grounding_diagnostics": [],
        "uncertainty_notes": [],
    }


def _write_p1b_bundle(tmp: Path) -> Path:
    """Write a minimal P1b bundle to *tmp*."""
    tmp.mkdir(parents=True, exist_ok=True)
    graph = _make_p1b_graph()
    (tmp / "concept_trace_graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (tmp / "concept_trace_index.json").write_text(
        json.dumps({"claim_index": {}, "evidence_index": {}}),
        encoding="utf-8",
    )
    (tmp / "grounding_report.json").write_text(
        json.dumps(
            {
                "blocking_diagnostics": [],
                "non_blocking_diagnostics": [],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp / "run_metadata.json").write_text(
        json.dumps(
            {
                "concept": "peak_idx",
                "project_root": "/some/project",
                "status": "ok",
                "mapping_claims": 1,
                "evidence_items": 2,
                "blocking_diagnostics": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp / "concept_trace.md").write_text("# Summary\n", encoding="utf-8")
    (tmp / "concept_trace.mmd").write_text("graph TD\n", encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentPlanIntentConsistency(unittest.TestCase):
    """Plan intent must match agent answer intent for the same question."""

    def _assert_intents_match(self, question: str, expected_kind: str) -> None:
        """Assert both agent answer and plan preview have expected intent."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = _write_p1b_bundle(Path(tmp) / "p1b")
            bundle = load_bundle(bundle_dir)

            agent_resp = query_artifact_bundle(bundle, question)
            plan = build_agent_plan_preview(bundle, question, agent_resp)

            self.assertTrue(
                agent_resp.is_loaded,
                f"Agent not loaded for: {question}",
            )
            self.assertTrue(
                plan.is_loaded,
                f"Plan not loaded for: {question}",
            )
            self.assertEqual(
                agent_resp.response_kind,
                expected_kind,
                f"Agent kind mismatch for: {question}",
            )
            self.assertEqual(
                plan.intent,
                expected_kind,
                f"Plan intent mismatch for: {question}",
            )

    def test_summary_question(self) -> None:
        """'这个概念的整体情况如何？' → summary."""
        self._assert_intents_match("这个概念的整体情况如何？", "summary")

    def test_claims_question(self) -> None:
        """'有哪些映射声明？可信度如何？' → claims."""
        self._assert_intents_match("有哪些映射声明？可信度如何？", "claims")

    def test_evidence_question(self) -> None:
        """'有什么证据支持这些映射？' → evidence."""
        self._assert_intents_match("有什么证据支持这些映射？", "evidence")

    def test_unknown_question(self) -> None:
        """'有哪些不确定或未确认的部分？' → unknown."""
        self._assert_intents_match("有哪些不确定或未确认的部分？", "unknown")

    def test_diagnostics_question(self) -> None:
        """'有哪些诊断信息？' → diagnostics."""
        self._assert_intents_match("有哪些诊断信息？", "diagnostics")

    def test_edges_question(self) -> None:
        """'节点之间的关系是什么？' → edges."""
        self._assert_intents_match("节点之间的关系是什么？", "edges")


if __name__ == "__main__":
    unittest.main()
