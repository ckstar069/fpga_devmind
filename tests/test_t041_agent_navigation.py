"""T041: 本地确定性 Agent 导航层测试."""

import json
import pytest
from pathlib import Path

from fpga_devmind.agent_navigator import (
    build_agent_navigation_index,
    NAV_SCHEMA_VERSION,
    _build_entrypoints,
    _build_question_routes,
    _build_concept_routes,
    _build_edge_routes,
    _build_quality_status,
    _build_limitations,
)


# ─── Unit tests for internal builders ────────────────────────────────

class TestEntrypoints:
    def test_all_entrypoints_with_all_artifacts(self):
        eps = _build_entrypoints(has_semantic_summary=True, has_pipeline_view=True, has_eval=True)
        assert len(eps) == 5
        ids = {e["id"] for e in eps}
        assert ids == {"overview", "pipeline", "graph", "evidence", "quality"}
        for e in eps:
            assert "label" in e
            assert "artifact" in e
            assert "available" in e
            assert "description" in e

    def test_entrypoints_when_artifacts_missing(self):
        eps = _build_entrypoints(has_semantic_summary=False, has_pipeline_view=False, has_eval=False)
        overview = next(e for e in eps if e["id"] == "overview")
        pipeline = next(e for e in eps if e["id"] == "pipeline")
        quality = next(e for e in eps if e["id"] == "quality")
        assert overview["available"] is False
        assert pipeline["available"] is False
        assert quality["available"] is False
        graph = next(e for e in eps if e["id"] == "graph")
        evidence = next(e for e in eps if e["id"] == "evidence")
        assert graph["available"] is True
        assert evidence["available"] is True


class TestQuestionRoutes:
    def test_question_routes_structure(self):
        routes = _build_question_routes()
        assert len(routes) >= 9
        for r in routes:
            assert "intent" in r
            assert "patterns" in r
            assert "primary_artifacts" in r
            assert "fallback_artifacts" in r
            assert isinstance(r["patterns"], list)
            assert len(r["patterns"]) > 0

    def test_navigation_intent_has_agent_index(self):
        routes = _build_question_routes()
        nav_route = next((r for r in routes if r["intent"] == "navigation_help"), None)
        assert nav_route is not None
        assert "agent_navigation_index.json" in nav_route["primary_artifacts"]


class TestConceptRoutes:
    def test_concept_routes_from_fake_concepts(self):
        concepts = [
            {"node_id": "c1", "label": "peak_idx", "confidence": "supported"},
            {"node_id": "c2", "label": "cfo", "confidence": "inferred"},
        ]
        evidence_chain = {
            "peak_idx": {
                "l5_l6_evidence": [
                    {"evidence_id": "ev1", "file_path": "L5/peak.py", "symbol": "PeakDetector"}
                ],
                "rtl_evidence": [
                    {"evidence_id": "ev2", "file_path": "rtl/peak.v", "symbol": "peak_idx"}
                ],
                "test_evidence": [],
                "claims": [{"claim_id": "cl1", "bridge_kind": "calculation_role", "confidence": "supported"}],
            },
            "cfo": {
                "l5_l6_evidence": [],
                "rtl_evidence": [],
                "test_evidence": [],
                "claims": [],
            },
        }
        routes = _build_concept_routes(concepts, evidence_chain, {}, None)
        assert len(routes) == 2

        peak = next(r for r in routes if r["concept"] == "peak_idx")
        assert peak["node_id"] == "c1"
        assert peak["confidence"] == "supported"
        assert peak["has_l5_l6"] is True
        assert peak["has_rtl"] is True
        assert peak["has_test"] is False
        assert "missing_test" in peak["known_gaps"]
        assert "ev1" in peak["evidence_ids"]
        assert "ev2" in peak["evidence_ids"]
        assert "L5/peak.py" in peak["source_files"]

        cfo = next(r for r in routes if r["concept"] == "cfo")
        assert cfo["confidence"] == "inferred"
        assert cfo["has_l5_l6"] is False
        assert "missing_l5_l6" in cfo["known_gaps"]
        assert "missing_rtl" in cfo["known_gaps"]

    def test_concept_routes_with_semantic_summary(self):
        concepts = [{"node_id": "c1", "label": "peak_idx", "confidence": "supported"}]
        evidence_chain = {"peak_idx": {"l5_l6_evidence": [], "rtl_evidence": [], "test_evidence": [], "claims": []}}
        semantic_summary = {
            "l5_l6_to_rtl_summary": {
                "concept_mappings": [
                    {"concept": "peak_idx", "mapping_confidence": "supported", "mapping_reason": "Strong structural link"}
                ]
            }
        }
        routes = _build_concept_routes(concepts, evidence_chain, {}, semantic_summary)
        peak = routes[0]
        assert peak["mapping_confidence"] == "supported"
        assert peak["mapping_reason"] == "Strong structural link"


class TestEdgeRoutes:
    def test_edge_routes_from_pipeline_view(self):
        pv = {
            "cross_stage_edges": [
                {
                    "edge_id": "e1",
                    "edge_type": "stage_flow",
                    "from_lane": "L5",
                    "to_lane": "RTL",
                    "from_node_id": "n1",
                    "to_node_id": "n2",
                    "confidence": "supported",
                    "reason": "Same concept",
                    "evidence_ids": ["ev1"],
                    "source_files": ["L5/peak.py"],
                }
            ]
        }
        routes = _build_edge_routes(pv)
        assert len(routes) == 1
        assert routes[0]["edge_id"] == "e1"
        assert routes[0]["from_lane"] == "L5"
        assert routes[0]["to_lane"] == "RTL"
        assert routes[0]["confidence"] == "supported"
        assert routes[0]["evidence_ids"] == ["ev1"]

    def test_edge_routes_when_no_pipeline_view(self):
        routes = _build_edge_routes(None)
        assert routes == []


class TestQualityStatus:
    def test_quality_with_eval(self):
        eval_result = {
            "selected_precision_like": 0.75,
            "selected_recall_like": 0.80,
            "excluded_terms_selected": ["term1"],
            "matched_core": ["a", "b"],
            "missed_core": ["c"],
            "matched_secondary": ["d"],
        }
        qs = _build_quality_status(eval_result)
        assert qs["golden_spec_used"] is True
        assert qs["selected_precision_like"] == 0.75
        assert qs["selected_recall_like"] == 0.80
        assert qs["excluded_terms_selected"] == ["term1"]
        assert qs["matched_core_count"] == 2
        assert qs["missed_core_count"] == 1
        assert qs["matched_secondary_count"] == 1

    def test_quality_without_eval(self):
        qs = _build_quality_status(None)
        assert qs["golden_spec_used"] is False
        assert qs["selected_precision_like"] == 0.0
        assert qs["selected_recall_like"] == 0.0
        assert qs["excluded_terms_selected"] == []


class TestLimitations:
    def test_limitations_with_gaps(self):
        semantic_summary = {
            "uncertainty_summary": {
                "naming_only_links": ["a", "b"],
                "missing_rtl": ["c"],
            }
        }
        pipeline_view = {
            "pipeline_summary": {"concepts_with_gaps": ["g1", "g2"]}
        }
        eval_result = {"excluded_terms_selected": ["x"]}
        lims = _build_limitations(semantic_summary, pipeline_view, eval_result, None)
        categories = {l["category"] for l in lims}
        assert "quality_warning" in categories
        assert "inference_quality" in categories
        assert "coverage_gap" in categories

    def test_limitations_when_missing_artifacts(self):
        lims = _build_limitations(None, None, None, None)
        items = {l["item"] for l in lims}
        assert "semantic_summary" in items
        assert "pipeline_view" in items
        assert "eval_result" in items


# ─── Integration: build_agent_navigation_index ───────────────────────

class TestBuildAgentNavigationIndex:
    def test_full_index_structure(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        project_graph = {
            "project_id": "test_project",
            "nodes": [
                {"node_id": "c1", "kind": "concept", "label": "peak_idx", "confidence": "supported"},
            ],
            "edges": [],
        }
        project_index = {
            "evidence_index": {},
            "evidence_chain": {
                "peak_idx": {
                    "l5_l6_evidence": [],
                    "rtl_evidence": [],
                    "test_evidence": [],
                    "claims": [],
                }
            },
        }
        semantic_summary = {
            "l5_l6_to_rtl_summary": {"concept_mappings": []},
            "uncertainty_summary": {},
        }
        pipeline_view = {
            "cross_stage_edges": [],
            "pipeline_summary": {},
        }
        eval_result = {
            "selected_precision_like": 1.0,
            "selected_recall_like": 1.0,
            "excluded_terms_selected": [],
            "matched_core": ["peak_idx"],
            "missed_core": [],
            "matched_secondary": [],
        }

        nav = build_agent_navigation_index(
            project_root=project_root,
            project_graph=project_graph,
            project_index=project_index,
            semantic_summary=semantic_summary,
            pipeline_view=pipeline_view,
            eval_result=eval_result,
            concept_candidates=None,
        )

        assert nav["schema_version"] == NAV_SCHEMA_VERSION
        assert nav["project_id"] == "test_project"
        assert len(nav["entrypoints"]) == 5
        assert len(nav["question_routes"]) >= 9
        assert len(nav["concept_routes"]) == 1
        assert nav["concept_routes"][0]["concept"] == "peak_idx"
        assert nav["quality_status"]["golden_spec_used"] is True
        assert nav["quality_status"]["selected_precision_like"] == 1.0
        assert "source_provenance" in nav
        assert "summary_generated_from" in nav["source_provenance"]
        assert "generation_timestamp" in nav["source_provenance"]

    def test_index_without_optional_artifacts(self, tmp_path):
        project_root = tmp_path / "minimal"
        project_root.mkdir()

        project_graph = {
            "project_id": "minimal",
            "nodes": [],
            "edges": [],
        }
        project_index = {"evidence_index": {}, "evidence_chain": {}}

        nav = build_agent_navigation_index(
            project_root=project_root,
            project_graph=project_graph,
            project_index=project_index,
            semantic_summary=None,
            pipeline_view=None,
            eval_result=None,
            concept_candidates=None,
        )

        assert nav["schema_version"] == NAV_SCHEMA_VERSION
        assert nav["project_id"] == "minimal"
        assert len(nav["entrypoints"]) == 5
        # overview, pipeline, quality should be unavailable
        unavailable = [e for e in nav["entrypoints"] if not e["available"]]
        assert len(unavailable) == 3
        assert nav["quality_status"]["golden_spec_used"] is False
        assert len(nav["edge_routes"]) == 0
        assert len(nav["concept_routes"]) == 0


# ─── Real project bundle validation ──────────────────────────────────

FPGA_ROOT = Path("/Users/ckstar/Repo/znxt_ofdm")
T041_BUNDLES = [
    ("coarse", Path("/tmp/fpga_devmind/t041_coarse_agent")),
    ("fine_cfo", Path("/tmp/fpga_devmind/t041_fine_cfo_agent")),
    ("fft", Path("/tmp/fpga_devmind/t041_fft_agent")),
]


def _require_bundle(name, bundle_dir):
    if not bundle_dir.exists():
        pytest.skip(f"T041 real bundle '{name}' not found at {bundle_dir}; run generation command first")


class TestT041RealBundles:
    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_agent_navigation_index_exists(self, name, bundle_dir):
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        assert nav_path.exists(), f"{name}: agent_navigation_index.json missing"

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_navigation_index_schema(self, name, bundle_dir):
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        assert nav["schema_version"] == NAV_SCHEMA_VERSION
        assert "project_id" in nav
        assert "entrypoints" in nav
        assert "question_routes" in nav
        assert "concept_routes" in nav
        assert "edge_routes" in nav
        assert "quality_status" in nav
        assert "limitations" in nav
        assert "source_provenance" in nav

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_entrypoints_have_graph_and_evidence(self, name, bundle_dir):
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        graph_ep = next((e for e in nav["entrypoints"] if e["id"] == "graph"), None)
        evidence_ep = next((e for e in nav["entrypoints"] if e["id"] == "evidence"), None)
        assert graph_ep is not None and graph_ep["available"] is True
        assert evidence_ep is not None and evidence_ep["available"] is True

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_quality_status_has_golden_spec(self, name, bundle_dir):
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        qs = nav["quality_status"]
        assert qs["golden_spec_used"] is True
        assert 0.0 <= qs["selected_precision_like"] <= 1.0
        assert 0.0 <= qs["selected_recall_like"] <= 1.0
        assert "excluded_terms_selected" in qs
        assert "matched_core_count" in qs
        assert "missed_core_count" in qs

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_concept_routes_non_empty(self, name, bundle_dir):
        """Concept routes should be non-empty and have valid structure."""
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        assert len(nav["concept_routes"]) > 0, f"{name}: should have concept routes"
        for r in nav["concept_routes"]:
            assert "concept" in r
            assert "node_id" in r
            assert "confidence" in r
            assert "known_gaps" in r
            assert "evidence_ids" in r
            assert "has_l5_l6" in r
            assert "has_rtl" in r
            assert "has_test" in r

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_pipeline_view_has_cross_stage_edges(self, name, bundle_dir):
        """Pipeline view should have cross-stage edges that map to edge routes."""
        _require_bundle(name, bundle_dir)
        pv_path = bundle_dir / "semantic_pipeline_view.json"
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(pv_path) as f:
            pv = json.load(f)
        with open(nav_path) as f:
            nav = json.load(f)

        pv_edges = pv.get("cross_stage_edges", [])
        nav_edges = nav["edge_routes"]
        # Each pipeline view edge should have a corresponding route
        assert len(nav_edges) == len(pv_edges), \
            f"{name}: edge_routes ({len(nav_edges)}) should match pipeline edges ({len(pv_edges)})"

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_all_edge_routes_have_evidence(self, name, bundle_dir):
        """Edge routes should have evidence_ids and source_files arrays."""
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        for edge in nav["edge_routes"]:
            assert "evidence_ids" in edge
            assert "source_files" in edge
            assert "reason" in edge
            assert "confidence" in edge

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_limitations_non_empty(self, name, bundle_dir):
        """Should have at least one limitation documented."""
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        assert len(nav["limitations"]) > 0, f"{name}: should document limitations"

    @pytest.mark.parametrize("name,bundle_dir", T041_BUNDLES)
    def test_question_routes_cover_navigation(self, name, bundle_dir):
        """Should have navigation_help intent."""
        _require_bundle(name, bundle_dir)
        nav_path = bundle_dir / "agent_navigation_index.json"
        with open(nav_path) as f:
            nav = json.load(f)
        intents = {r["intent"] for r in nav["question_routes"]}
        assert "navigation_help" in intents
        assert "edge_evidence" in intents
        assert "quality_metrics" in intents
