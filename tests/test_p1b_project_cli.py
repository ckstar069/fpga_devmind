"""Tests for project-level multi-concept trace CLI (T024).

Tests the pure-data graph builders and renderers without running the full
per-concept P1b pipeline (which would require a real FPGA project).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_project_cli import (
    _ConceptTraceResult,
    _build_project_graph,
    _build_project_index,
    _build_shared_edges,
    _concept_confidence,
    _concept_node_id,
    _render_project_markdown,
    _render_project_mermaid,
    _rtl_key,
    run_p1b_trace_project,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_concept_result(
    concept: str,
    claims: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    uncertainty_notes: list[dict[str, Any]] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
    status: str = "ok",
) -> _ConceptTraceResult:
    """Build a mock concept trace result."""
    graph: dict[str, Any] | None = {
        "schema_version": "concept-trace-graph-0.1",
        "concept": concept,
        "nodes": nodes or [],
        "edges": [],
        "mapping_claims": claims or [],
        "evidence_items": evidence or [],
        "grounding_diagnostics": diagnostics or [],
        "uncertainty_notes": uncertainty_notes or [],
    }
    return _ConceptTraceResult(
        concept=concept,
        metadata={"status": status, "concept": concept},
        graph=graph,
        index={},
        grounding={},
        status=status,
    )


def _make_rtl_node(
    node_id: str,
    label: str,
    kind: str = "rtl_module",
    file_path: str = "/project/rtl/top.v",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "label": label,
        "kind": kind,
        "stage": "RTL",
        "file_path": file_path,
        "confidence": "inferred",
    }


# ---------------------------------------------------------------------------
# Project graph builder
# ---------------------------------------------------------------------------


class TestBuildProjectGraph(unittest.TestCase):
    """Tests for _build_project_graph."""

    def test_empty_concepts_still_has_project_node(self):
        """Even with no concepts, a project node exists."""
        project_root = Path("/tmp/test_project")
        graph = _build_project_graph(project_root, [])
        self.assertEqual(graph["schema_version"], "project-understanding-0.1")
        self.assertEqual(graph["project_id"], "test_project")
        project_nodes = [n for n in graph["nodes"] if n["kind"] == "project"]
        self.assertEqual(len(project_nodes), 1)
        self.assertEqual(project_nodes[0]["node_id"], "PUG_PROJECT")

    def test_single_concept_nodes_and_edges(self):
        """One concept produces project->concept->claim->rtl chain."""
        result = _make_concept_result(
            "peak_idx",
            claims=[
                {
                    "claim_id": "MC_001",
                    "confidence": "supported",
                    "bridge_kind": "naming_plus_structure",
                }
            ],
            nodes=[_make_rtl_node("N1", "peak_detect")],
        )
        graph = _build_project_graph(Path("/project"), [result])

        # Project node.
        self.assertEqual(len([n for n in graph["nodes"] if n["kind"] == "project"]), 1)
        # Concept node.
        concept_nodes = [n for n in graph["nodes"] if n["kind"] == "concept"]
        self.assertEqual(len(concept_nodes), 1)
        self.assertEqual(concept_nodes[0]["node_id"], "PUG_CONCEPT_peak_idx")
        # Claim node.
        claim_nodes = [n for n in graph["nodes"] if n["kind"] == "mapping_claim"]
        self.assertEqual(len(claim_nodes), 1)
        self.assertEqual(claim_nodes[0]["node_id"], "PUG_CLAIM_peak_idx_MC_001")
        # RTL node.
        rtl_nodes = [n for n in graph["nodes"] if n["kind"].startswith("rtl_")]
        self.assertEqual(len(rtl_nodes), 1)

        # Edges.
        edge_types = {e["edge_type"] for e in graph["edges"]}
        self.assertIn("contains", edge_types)
        self.assertIn("has_claim", edge_types)
        self.assertIn("realizes", edge_types)

    def test_failed_concept_produces_unknown_node(self):
        """A failed concept trace produces an unknown-confidence concept node."""
        result = _ConceptTraceResult(
            concept="failed_concept",
            metadata={},
            graph=None,
            index=None,
            grounding=None,
            status="failed",
        )
        graph = _build_project_graph(Path("/project"), [result])
        concept_nodes = [n for n in graph["nodes"] if n["kind"] == "concept"]
        self.assertEqual(len(concept_nodes), 1)
        self.assertEqual(concept_nodes[0]["confidence"], "unknown")
        self.assertIn("notes", concept_nodes[0])

    def test_multi_concept_multiple_nodes(self):
        """Multiple concepts produce multiple concept nodes."""
        r1 = _make_concept_result("peak_idx", claims=[], nodes=[])
        r2 = _make_concept_result("cfo", claims=[], nodes=[])
        graph = _build_project_graph(Path("/project"), [r1, r2])
        concept_nodes = [n for n in graph["nodes"] if n["kind"] == "concept"]
        self.assertEqual(len(concept_nodes), 2)
        ids = {n["node_id"] for n in concept_nodes}
        self.assertEqual(ids, {"PUG_CONCEPT_peak_idx", "PUG_CONCEPT_cfo"})

    def test_rtl_deduplication(self):
        """RTL objects with same (file, label, kind) are deduplicated."""
        rtl = _make_rtl_node("N1", "shared_module", file_path="/rtl/top.v")
        r1 = _make_concept_result(
            "peak_idx",
            claims=[{"claim_id": "MC_1", "confidence": "inferred"}],
            nodes=[rtl],
        )
        r2 = _make_concept_result(
            "cfo",
            claims=[{"claim_id": "MC_1", "confidence": "inferred"}],
            nodes=[rtl],
        )
        graph = _build_project_graph(Path("/project"), [r1, r2])
        rtl_nodes = [n for n in graph["nodes"] if n["kind"].startswith("rtl_")]
        self.assertEqual(len(rtl_nodes), 1)
        # Both claims should have edges to the same RTL node.
        realize_edges = [e for e in graph["edges"] if e["edge_type"] == "realizes"]
        self.assertEqual(len(realize_edges), 2)
        to_ids = {e["to_node_id"] for e in realize_edges}
        self.assertEqual(len(to_ids), 1)

    def test_no_dangling_edges(self):
        """Every edge references nodes that exist in the graph."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[{"claim_id": "MC_1", "confidence": "supported"}],
            nodes=[_make_rtl_node("N1", "mod")],
        )
        graph = _build_project_graph(Path("/project"), [r1])
        node_ids = {n["node_id"] for n in graph["nodes"]}
        for edge in graph["edges"]:
            self.assertIn(
                edge["from_node_id"],
                node_ids,
                "Edge from_node_id {} not in nodes".format(edge["from_node_id"]),
            )
            self.assertIn(
                edge["to_node_id"],
                node_ids,
                "Edge to_node_id {} not in nodes".format(edge["to_node_id"]),
            )

    def test_diagnostics_and_uncertainty_aggregated(self):
        """Grounding diagnostics and uncertainty notes are collected."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[],
            diagnostics=[{"diagnostic_id": "D1", "message": "m1"}],
            uncertainty_notes=[{"reason": "u1"}],
        )
        graph = _build_project_graph(Path("/project"), [r1])
        self.assertEqual(len(graph["grounding_diagnostics"]), 1)
        self.assertEqual(graph["grounding_diagnostics"][0].get("concept"), "peak_idx")
        self.assertEqual(len(graph["uncertainty_notes"]), 1)
        self.assertEqual(graph["uncertainty_notes"][0].get("concept"), "peak_idx")

    def test_concept_confidence_from_claims(self):
        """Concept confidence is derived from claim confidences."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[
                {"claim_id": "MC_1", "confidence": "inferred"},
                {"claim_id": "MC_2", "confidence": "unknown"},
            ],
        )
        graph = _build_project_graph(Path("/project"), [r1])
        concept = [n for n in graph["nodes"] if n["kind"] == "concept"][0]
        self.assertEqual(concept["confidence"], "inferred")

    def test_concept_confidence_supported_wins(self):
        """If any claim is supported, concept confidence is supported."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[
                {"claim_id": "MC_1", "confidence": "supported"},
                {"claim_id": "MC_2", "confidence": "inferred"},
            ],
        )
        graph = _build_project_graph(Path("/project"), [r1])
        concept = [n for n in graph["nodes"] if n["kind"] == "concept"][0]
        self.assertEqual(concept["confidence"], "supported")


# ---------------------------------------------------------------------------
# Shared edges
# ---------------------------------------------------------------------------


class TestBuildSharedEdges(unittest.TestCase):
    """Tests for _build_shared_edges."""

    def test_no_shared_files_no_edges(self):
        """Concepts referencing different files produce no shared edges."""
        r1 = _make_concept_result(
            "peak_idx",
            nodes=[_make_rtl_node("N1", "mod", file_path="/a.v")],
        )
        r2 = _make_concept_result(
            "cfo",
            nodes=[_make_rtl_node("N2", "mod2", file_path="/b.v")],
        )
        edges = _build_shared_edges([r1, r2], {})
        self.assertEqual(len(edges), 0)

    def test_shared_file_edge(self):
        """Two concepts referencing the same file produce a shares_file edge."""
        # Use a non-RTL node to test only file sharing.
        node = {"node_id": "N1", "label": "doc", "kind": "document", "file_path": "/shared.v"}
        r1 = _make_concept_result("peak_idx", nodes=[node])
        r2 = _make_concept_result("cfo", nodes=[node])
        edges = _build_shared_edges([r1, r2], {})
        file_edges = [e for e in edges if e["edge_type"] == "shares_file"]
        self.assertEqual(len(file_edges), 1)
        self.assertEqual(file_edges[0]["confidence"], "inferred")

    def test_shared_rtl_object_edge(self):
        """Two concepts referencing the same RTL object produce shares_rtl_object."""
        rtl = _make_rtl_node("N1", "shared_mod")
        r1 = _make_concept_result("peak_idx", nodes=[rtl])
        r2 = _make_concept_result("cfo", nodes=[rtl])
        edges = _build_shared_edges([r1, r2], {})
        # Should have both shares_file and shares_rtl_object edges.
        file_edges = [e for e in edges if e["edge_type"] == "shares_file"]
        rtl_edges = [e for e in edges if e["edge_type"] == "shares_rtl_object"]
        self.assertEqual(len(file_edges), 1)
        self.assertEqual(len(rtl_edges), 1)

    def test_shared_edges_not_duplicated(self):
        """Same concept pair should not produce duplicate edges."""
        rtl1 = _make_rtl_node("N1", "mod", file_path="/a.v")
        rtl2 = _make_rtl_node("N2", "mod", file_path="/b.v")
        r1 = _make_concept_result("peak_idx", nodes=[rtl1, rtl2])
        r2 = _make_concept_result("cfo", nodes=[rtl1, rtl2])
        edges = _build_shared_edges([r1, r2], {})
        # Only one shares_file edge between peak_idx and cfo.
        file_edges = [e for e in edges if e["edge_type"] == "shares_file"]
        self.assertEqual(len(file_edges), 1)

    def test_failed_concept_ignored(self):
        """Failed concepts (graph=None) do not produce shared edges."""
        rtl = _make_rtl_node("N1", "mod")
        r1 = _make_concept_result("peak_idx", nodes=[rtl])
        r2 = _ConceptTraceResult(
            concept="cfo",
            metadata={},
            graph=None,
            index=None,
            grounding=None,
            status="failed",
        )
        edges = _build_shared_edges([r1, r2], {})
        self.assertEqual(len(edges), 0)


# ---------------------------------------------------------------------------
# Project index builder
# ---------------------------------------------------------------------------


class TestBuildProjectIndex(unittest.TestCase):
    """Tests for _build_project_index."""

    def test_index_has_concept_counts(self):
        """Concept index contains claim/evidence/rtl counts."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[{"claim_id": "MC_1"}],
            evidence=[{"evidence_id": "EV_1"}],
            nodes=[_make_rtl_node("N1", "mod")],
        )
        index = _build_project_index(Path("/project"), [r1])
        self.assertEqual(index["concept_index"]["peak_idx"]["claims"], 1)
        self.assertEqual(index["concept_index"]["peak_idx"]["evidence"], 1)
        self.assertEqual(index["concept_index"]["peak_idx"]["rtl_objects"], 1)
        self.assertEqual(index["concept_index"]["peak_idx"]["status"], "ok")

    def test_failed_concept_in_index(self):
        """Failed concepts appear in index with failed status."""
        r1 = _ConceptTraceResult(
            concept="failed",
            metadata={},
            graph=None,
            index=None,
            grounding=None,
            status="failed",
        )
        index = _build_project_index(Path("/project"), [r1])
        self.assertEqual(index["concept_index"]["failed"]["status"], "failed")

    def test_claim_index_scoped_ids(self):
        """Claim index uses project-scoped IDs."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[
                {
                    "claim_id": "MC_1",
                    "confidence": "supported",
                    "bridge_kind": "naming",
                }
            ],
        )
        index = _build_project_index(Path("/project"), [r1])
        scoped_id = "PUG_CLAIM_peak_idx_MC_1"
        self.assertIn(scoped_id, index["claim_index"])
        self.assertEqual(index["claim_index"][scoped_id]["concept"], "peak_idx")

    def test_file_index_maps_paths_to_concepts(self):
        """File index maps file paths to concepts that reference them."""
        r1 = _make_concept_result(
            "peak_idx",
            evidence=[{"evidence_id": "EV_1", "file_path": "/shared.v"}],
        )
        r2 = _make_concept_result(
            "cfo",
            evidence=[{"evidence_id": "EV_2", "file_path": "/shared.v"}],
        )
        index = _build_project_index(Path("/project"), [r1, r2])
        self.assertIn("/shared.v", index["file_index"])
        self.assertEqual(set(index["file_index"]["/shared.v"]), {"peak_idx", "cfo"})

    def test_rtl_object_index(self):
        """RTL object index maps RTL names to concepts."""
        r1 = _make_concept_result(
            "peak_idx",
            nodes=[_make_rtl_node("N1", "shared_mod")],
        )
        r2 = _make_concept_result(
            "cfo",
            nodes=[_make_rtl_node("N2", "shared_mod")],
        )
        index = _build_project_index(Path("/project"), [r1, r2])
        self.assertIn("shared_mod", index["rtl_object_index"])
        self.assertEqual(set(index["rtl_object_index"]["shared_mod"]), {"peak_idx", "cfo"})


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


class TestRenderProjectMarkdown(unittest.TestCase):
    """Tests for _render_project_markdown."""

    def test_contains_project_name(self):
        """Markdown contains the project name."""
        r1 = _make_concept_result("peak_idx", claims=[], evidence=[])
        md = _render_project_markdown(Path("/projects/my_fpga"), [r1], [])
        self.assertIn("my_fpga", md)
        self.assertIn("# Project Understanding", md)

    def test_counts_summary(self):
        """Markdown summary section contains counts."""
        r1 = _make_concept_result(
            "peak_idx",
            claims=[{"claim_id": "MC_1"}],
            evidence=[{"evidence_id": "EV_1"}],
        )
        md = _render_project_markdown(Path("/project"), [r1], [])
        self.assertIn("Concepts traced: 1", md)
        self.assertIn("Total mapping claims: 1", md)
        self.assertIn("Total evidence items: 1", md)

    def test_failed_concepts_listed(self):
        """Failed concepts appear in the summary."""
        r1 = _make_concept_result("ok_concept", status="ok")
        r2 = _ConceptTraceResult(
            "bad_concept", {}, None, None, None, "failed"
        )
        md = _render_project_markdown(Path("/project"), [r1, r2], [])
        self.assertIn("Failed traces", md)
        self.assertIn("bad_concept", md)

    def test_shared_resources_section(self):
        """Shared RTL objects appear in dedicated section."""
        rtl = _make_rtl_node("N1", "shared_mod")
        r1 = _make_concept_result("peak_idx", nodes=[rtl])
        r2 = _make_concept_result("cfo", nodes=[rtl])
        md = _render_project_markdown(Path("/project"), [r1, r2], [])
        self.assertIn("Shared Resources", md)
        self.assertIn("shared_mod", md)
        self.assertIn("peak_idx", md)
        self.assertIn("cfo", md)

    def test_uncertainties_section(self):
        """Uncertainty notes appear in uncertainties section."""
        r1 = _make_concept_result(
            "peak_idx",
            uncertainty_notes=[{"reason": "RTL missing"}],
        )
        md = _render_project_markdown(Path("/project"), [r1], [])
        self.assertIn("Uncertainties and Limitations", md)
        self.assertIn("RTL missing", md)

    def test_diagnostics_section(self):
        """Diagnostics appear in diagnostics section."""
        diag = {"severity": "error", "concept": "peak_idx", "message": "failed"}
        md = _render_project_markdown(Path("/project"), [], [diag])
        self.assertIn("Diagnostics", md)
        self.assertIn("failed", md)


class TestRenderProjectMermaid(unittest.TestCase):
    """Tests for _render_project_mermaid."""

    def test_basic_mermaid_structure(self):
        """Mermaid output starts with graph TD and contains nodes/edges."""
        graph = {
            "nodes": [
                {"node_id": "PUG_PROJECT", "label": "my_fpga", "kind": "project"},
                {"node_id": "PUG_CONCEPT_peak_idx", "label": "peak_idx", "kind": "concept"},
            ],
            "edges": [
                {
                    "from_node_id": "PUG_PROJECT",
                    "to_node_id": "PUG_CONCEPT_peak_idx",
                    "edge_type": "contains",
                    "confidence": "supported",
                }
            ],
        }
        mmd = _render_project_mermaid(graph)
        self.assertTrue(mmd.startswith("graph TD"))
        self.assertIn("PUG_PROJECT", mmd)
        self.assertIn("peak_idx", mmd)
        self.assertIn("contains", mmd)

    def test_sanitizes_node_ids(self):
        """Special characters in node IDs are sanitized."""
        graph = {
            "nodes": [
                {"node_id": "node:with-chars.v", "label": "test", "kind": "concept"},
            ],
            "edges": [],
        }
        mmd = _render_project_mermaid(graph)
        self.assertNotIn(":", mmd)
        self.assertIn("node_with_chars_v", mmd)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    """Tests for small helper functions."""

    def test_concept_node_id(self):
        self.assertEqual(_concept_node_id("peak_idx"), "PUG_CONCEPT_peak_idx")

    def test_rtl_key(self):
        node = {"file_path": "/a.v", "label": "mod", "kind": "rtl_module"}
        self.assertEqual(_rtl_key(node), ("/a.v", "mod", "rtl_module"))

    def test_concept_confidence_unknown_when_empty(self):
        self.assertEqual(_concept_confidence({"mapping_claims": []}), "unknown")

    def test_concept_confidence_from_list(self):
        self.assertEqual(
            _concept_confidence(
                {"mapping_claims": [{"confidence": "inferred"}]}
            ),
            "inferred",
        )
        self.assertEqual(
            _concept_confidence(
                {"mapping_claims": [{"confidence": "supported"}]}
            ),
            "supported",
        )


# ---------------------------------------------------------------------------
# Integration: run_p1b_trace_project
# ---------------------------------------------------------------------------


class TestRunP1bTraceProject(unittest.TestCase):
    """Integration tests for the full project trace CLI."""

    def test_empty_concepts_raises(self):
        """Empty concepts list raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                run_p1b_trace_project(
                    Path("/nonexistent_project"), [], Path(tmp)
                )
            self.assertIn("At least one concept", str(ctx.exception))

    def test_creates_artifacts(self):
        """Running with valid project creates expected artifacts."""
        # Use the sample project from the repo if it exists.
        sample_project = Path(__file__).parent.parent / "sample_projects" / "ofdm_tx"
        if not sample_project.is_dir():
            self.skipTest("Sample project not available")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            metadata = run_p1b_trace_project(
                sample_project,
                ["peak_idx"],
                out_dir,
            )
            self.assertIn("project_understanding_graph.json", metadata["artifacts"])
            self.assertIn("project_understanding_index.json", metadata["artifacts"])
            self.assertIn("project_understanding.md", metadata["artifacts"])
            self.assertIn("run_metadata.json", metadata["artifacts"])
            self.assertTrue((out_dir / "project_understanding_graph.json").is_file())
            self.assertTrue((out_dir / "project_understanding_index.json").is_file())
            self.assertTrue((out_dir / "project_understanding.md").is_file())
            self.assertTrue((out_dir / "run_metadata.json").is_file())

            # Validate graph JSON structure.
            graph = json.loads(
                (out_dir / "project_understanding_graph.json").read_text()
            )
            self.assertEqual(graph["schema_version"], "project-understanding-0.1")
            self.assertIn("nodes", graph)
            self.assertIn("edges", graph)
            self.assertIn("PUG_PROJECT", {n["node_id"] for n in graph["nodes"]})

    def test_metadata_fields(self):
        """Metadata contains expected fields."""
        sample_project = Path(__file__).parent.parent / "sample_projects" / "ofdm_tx"
        if not sample_project.is_dir():
            self.skipTest("Sample project not available")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            metadata = run_p1b_trace_project(
                sample_project,
                ["peak_idx"],
                out_dir,
            )
            self.assertEqual(metadata["command"], "p1b-trace-project")
            self.assertIn("peak_idx", metadata["concepts_requested"])
            self.assertIn("peak_idx", metadata["concepts_processed"])
            self.assertIn("elapsed_seconds", metadata)
            self.assertIn("status", metadata)
            self.assertIn("mapping_claims", metadata)
            self.assertIn("evidence_items", metadata)

    def test_error_isolation(self):
        """One failing concept does not crash the whole project trace."""
        sample_project = Path(__file__).parent.parent / "sample_projects" / "ofdm_tx"
        if not sample_project.is_dir():
            self.skipTest("Sample project not available")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            # Use one valid concept and one that likely doesn't exist.
            metadata = run_p1b_trace_project(
                sample_project,
                ["peak_idx", "__nonexistent_concept_999__"],
                out_dir,
            )
            # Should complete with partial status.
            self.assertEqual(metadata["status"], "partial")
            self.assertIn("__nonexistent_concept_999__", metadata["concepts_failed"])
            # Artifacts should still be created.
            self.assertTrue((out_dir / "project_understanding_graph.json").is_file())


if __name__ == "__main__":
    unittest.main()
