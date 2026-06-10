"""T039/T040 Pipeline View validation tests.

Validates:
- semantic_pipeline_view.json schema and generation
- Lane structure (L5, L6, RTL, Tests)
- Cross-stage edges
- Metadata integration (semantic_pipeline_view_status)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fpga_devmind.p1b_project_cli import run_p1b_trace_project
from fpga_devmind.semantic_pipeline_view import build_semantic_pipeline_view


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_synthetic_fpga_project(base: Path) -> Path:
    """Create a minimal synthetic FPGA project for pipeline view testing."""
    proj = base / "fpga_project_pipeline_test"

    # L5 fixed-point Python model
    l5 = proj / "src" / "python_model" / "L5_fixedpoint"
    l5.mkdir(parents=True)
    (l5 / "test_l5.py").write_text(
        "def compute_peak_idx(signal):\n"
        "    return max(range(len(signal)), key=lambda i: signal[i])\n"
        "\n"
        "class PeakDetector:\n"
        "    pass\n",
        encoding="utf-8",
    )

    # L6 resource-optimized Python model
    l6 = proj / "src" / "python_model" / "L6_resource_opt"
    l6.mkdir(parents=True)
    (l6 / "test_l6.py").write_text(
        "def optimized_peak_idx(signal, window):\n"
        "    return compute_peak_idx(signal[:window])\n"
        "\n"
        "class PeakDetectorOpt:\n"
        "    pass\n",
        encoding="utf-8",
    )

    # RTL Verilog model
    rtl = proj / "src" / "verilog_model" / "rtl"
    rtl.mkdir(parents=True)
    (rtl / "peak_detector.v").write_text(
        "module peak_detector (\n"
        "    input clk,\n"
        "    input [15:0] signal_in,\n"
        "    output [7:0] peak_idx_out\n"
        ");\n"
        "    assign peak_idx_out = 8'd0;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    # Tests
    tests = proj / "tests"
    tests.mkdir(parents=True)
    (tests / "test_peak.py").write_text(
        "def test_peak_idx():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    return proj


# ---------------------------------------------------------------------------
# Unit tests for build_semantic_pipeline_view
# ---------------------------------------------------------------------------


def test_build_semantic_pipeline_view_schema() -> None:
    """Direct unit test for build_semantic_pipeline_view with synthetic data."""
    project_root = Path("/tmp/fpga_devmind/test_pipeline_project")
    project_root.mkdir(parents=True, exist_ok=True)

    # Minimal project graph
    project_graph = {
        "schema_version": "project-understanding-0.1",
        "project_id": "test_project",
        "nodes": [
            {"node_id": "PUG_PROJECT", "label": "test_project", "kind": "project", "stage": "", "confidence": "supported"},
            {"node_id": "PUG_CONCEPT_peak_idx", "label": "peak_idx", "kind": "concept", "stage": "", "confidence": "supported"},
            {"node_id": "PUG_CLAIM_peak_idx_C001", "label": "C001", "kind": "mapping_claim", "stage": "", "confidence": "supported", "concept": "peak_idx"},
            {"node_id": "PUG_RTL_peak_detector", "label": "peak_detector", "kind": "rtl_module", "stage": "RTL", "confidence": "supported", "file_path": "rtl/peak_detector.v"},
        ],
        "edges": [
            {"edge_id": "E_PROJECT_peak_idx", "from_node_id": "PUG_PROJECT", "to_node_id": "PUG_CONCEPT_peak_idx", "edge_type": "contains", "confidence": "supported"},
            {"edge_id": "E_peak_idx_C001", "from_node_id": "PUG_CONCEPT_peak_idx", "to_node_id": "PUG_CLAIM_peak_idx_C001", "edge_type": "has_claim", "confidence": "supported"},
            {"edge_id": "E_C001_RTL", "from_node_id": "PUG_CLAIM_peak_idx_C001", "to_node_id": "PUG_RTL_peak_detector", "edge_type": "realizes", "confidence": "supported"},
        ],
    }

    # Minimal project index with evidence chain
    project_index = {
        "schema_version": "project-understanding-0.1",
        "project_id": "test_project",
        "concept_index": {
            "peak_idx": {"status": "ok", "claims": 1, "evidence": 2, "rtl_objects": 1, "l5_count": 1, "l6_count": 1, "test_count": 1},
        },
        "claim_index": {},
        "evidence_index": {
            "E_L5_001": {"concept": "peak_idx", "source_type": "concept_occurrence", "file_path": "src/python_model/L5_fixedpoint/test_l5.py", "symbol": "compute_peak_idx", "strength": "strong"},
            "E_L6_001": {"concept": "peak_idx", "source_type": "concept_occurrence", "file_path": "src/python_model/L6_resource_opt/test_l6.py", "symbol": "optimized_peak_idx", "strength": "strong"},
            "E_RTL_001": {"concept": "peak_idx", "source_type": "rtl_source", "file_path": "src/verilog_model/rtl/peak_detector.v", "symbol": "peak_detector", "strength": "medium"},
            "E_TEST_001": {"concept": "peak_idx", "source_type": "test_evidence", "file_path": "tests/test_peak.py", "symbol": "test_peak_idx", "strength": "medium"},
        },
        "evidence_chain": {
            "peak_idx": {
                "l5_l6_evidence": [
                    {"evidence_id": "E_L5_001", "file_path": "src/python_model/L5_fixedpoint/test_l5.py", "symbol": "compute_peak_idx", "strength": "strong"},
                    {"evidence_id": "E_L6_001", "file_path": "src/python_model/L6_resource_opt/test_l6.py", "symbol": "optimized_peak_idx", "strength": "strong"},
                ],
                "claims": [{"claim_id": "C001", "bridge_kind": "calculation_role", "confidence": "supported"}],
                "rtl_evidence": [{"evidence_id": "E_RTL_001", "file_path": "src/verilog_model/rtl/peak_detector.v", "symbol": "peak_detector", "strength": "medium"}],
                "test_evidence": [{"evidence_id": "E_TEST_001", "file_path": "tests/test_peak.py", "symbol": "test_peak_idx", "strength": "medium"}],
                "missing": [],
                "confidence_explanation": "High confidence: found in L5/L6 (2 refs), RTL (1 ref), tests (1 ref) with 1 claim — cross-stage evidence",
            },
        },
    }

    result = build_semantic_pipeline_view(project_root, project_graph, project_index)

    # Schema check
    assert result["schema_version"] == "semantic-pipeline-view-0.1"
    assert result["project_id"] == "test_project"

    # Lanes check
    lanes = result["lanes"]
    assert len(lanes) == 4
    lane_ids = [l["lane_id"] for l in lanes]
    assert lane_ids == ["L5_fixedpoint", "L6_resource_opt", "RTL", "tests"]

    # L5 lane should have evidence node
    l5_lane = lanes[0]
    assert any(n["kind"] == "evidence" for n in l5_lane["nodes"])

    # L6 lane should have concept node (primary lane for peak_idx)
    l6_lane = lanes[1]
    assert any(n["kind"] == "concept" and n["label"] == "peak_idx" for n in l6_lane["nodes"])

    # RTL lane should have rtl_module and mapping_claim
    rtl_lane = lanes[2]
    assert any(n["kind"] == "rtl_module" for n in rtl_lane["nodes"])
    assert any(n["kind"] == "mapping_claim" for n in rtl_lane["nodes"])

    # Tests lane should have evidence
    tests_lane = lanes[3]
    assert any(n["kind"] == "evidence" for n in tests_lane["nodes"])

    # Cross-stage edges check
    cross_edges = result["cross_stage_edges"]
    assert len(cross_edges) >= 1
    # Concept -> claim should be cross-stage (L6 to RTL)
    concept_to_claim = [e for e in cross_edges if e["edge_type"] == "has_claim"]
    assert len(concept_to_claim) >= 1

    # Pipeline summary
    summary = result["pipeline_summary"]
    assert summary["concept_count_per_stage"]["L6_resource_opt"] >= 1
    assert summary["cross_stage_claim_count"] >= 1
    assert summary["concepts_with_full_pipeline"] == ["peak_idx"]

    # Uncertainty flags
    assert len(result["uncertainty_flags"]) == 0  # peak_idx has full evidence

    # Source provenance
    assert "semantic_pipeline_view" in result["source_provenance"]["generator"]


# ---------------------------------------------------------------------------
# Integration tests via run_p1b_trace_project
# ---------------------------------------------------------------------------


def test_pipeline_view_cli_integration(tmp_path: Path) -> None:
    """Integration test: run project trace and verify pipeline view artifact."""
    proj = _make_synthetic_fpga_project(tmp_path)
    out_dir = tmp_path / "bundle_out"

    metadata = run_p1b_trace_project(
        project_root=proj,
        concepts=["auto"],
        out_dir=out_dir,
        max_concepts=8,
    )

    # Metadata fields
    assert metadata.get("semantic_pipeline_view_status") == "ok", (
        f"semantic_pipeline_view_status must be ok, got {metadata.get('semantic_pipeline_view_status')}"
    )
    assert "semantic_pipeline_view_error" not in metadata or not metadata["semantic_pipeline_view_error"]
    assert "semantic_pipeline_view.json" in metadata.get("artifacts", [])

    # File exists
    pv_path = out_dir / "semantic_pipeline_view.json"
    assert pv_path.is_file(), "semantic_pipeline_view.json must be generated"

    # Schema validation
    pv = _load_json(pv_path)
    assert pv["schema_version"] == "semantic-pipeline-view-0.1"
    assert "lanes" in pv
    assert "cross_stage_edges" in pv
    assert "pipeline_summary" in pv
    assert "uncertainty_flags" in pv

    # Lanes structure
    lanes = pv["lanes"]
    assert len(lanes) == 4
    for lane in lanes:
        assert "lane_id" in lane
        assert "label" in lane
        assert "nodes" in lane
        assert "edges" in lane
        assert isinstance(lane["nodes"], list)
        assert isinstance(lane["edges"], list)

    # Pipeline summary structure
    ps = pv["pipeline_summary"]
    assert "concept_count_per_stage" in ps
    assert "evidence_count_per_stage" in ps
    assert "cross_stage_claim_count" in ps
    assert "dataflow_edge_count" in ps
    assert "concepts_with_full_pipeline" in ps
    assert "concepts_with_gaps" in ps
    assert "total_nodes" in ps
    assert "total_cross_stage_edges" in ps

    # Index should reference pipeline_view_path
    idx = _load_json(out_dir / "project_understanding_index.json")
    assert idx.get("semantic_pipeline_view_path") == "semantic_pipeline_view.json"


# ---------------------------------------------------------------------------
# Reproducibility test (same as T038 pattern)
# ---------------------------------------------------------------------------


def test_reproducible_pipeline_view_generation(tmp_path: Path) -> None:
    """Verify pipeline view is deterministic across runs on same project."""
    proj = _make_synthetic_fpga_project(tmp_path)
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    meta1 = run_p1b_trace_project(project_root=proj, concepts=["auto"], out_dir=out1, max_concepts=8)
    meta2 = run_p1b_trace_project(project_root=proj, concepts=["auto"], out_dir=out2, max_concepts=8)

    assert meta1["semantic_pipeline_view_status"] == "ok"
    assert meta2["semantic_pipeline_view_status"] == "ok"

    pv1 = _load_json(out1 / "semantic_pipeline_view.json")
    pv2 = _load_json(out2 / "semantic_pipeline_view.json")

    # Deterministic: lane counts should match
    assert len(pv1["lanes"]) == len(pv2["lanes"])
    for i, (l1, l2) in enumerate(zip(pv1["lanes"], pv2["lanes"])):
        assert l1["lane_id"] == l2["lane_id"]
        assert len(l1["nodes"]) == len(l2["nodes"])
        assert len(l1["edges"]) == len(l2["edges"])
