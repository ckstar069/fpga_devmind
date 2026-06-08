"""Tests for P1b schema, artifact contract (T001) and source collector (T002).

These tests validate the structural shape of P1b artifacts,
enforce the mapping claim confidence rules from T005,
and test the read-only source collector.
No external APIs, no target project access, no Vivado.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.p1b_schema import (
    BRIDGE_KIND_CALCULATION_ROLE,
    BRIDGE_KIND_EXPLICIT_SOURCE,
    BRIDGE_KIND_NAMING_ONLY,
    BRIDGE_KIND_UNKNOWN,
    BRIDGE_KIND_VALUES,
    EDGE_TYPE_MAPPING,
    EDGE_TYPE_VALUES,
    MAPPING_CONFIDENCE_VALUES,
    NODE_KIND_CONCEPT,
    NODE_KIND_RTL_MODULE,
    NODE_KIND_RTL_SIGNAL,
    NODE_KIND_STAGE_VIEW,
    NODE_KIND_VALUES,
    P1B_SCHEMA_VERSION,
    ConceptTraceEdge,
    ConceptTraceGraph,
    ConceptTraceIndex,
    ConceptTraceNode,
    MappingClaim,
    RTLEvidenceView,
    StageConceptView,
    STRONG_BRIDGE_KINDS,
)
from fpga_devmind.schema import (
    EvidenceItem,
    GroundingDiagnostic,
    UncertaintyNote,
)
from fpga_devmind.p1b_collectors import (
    SOURCE_COLLECTION_SCHEMA_VERSION,
    SourceCollection,
    collect_p1b_sources,
)
from fpga_devmind.p1b_concept import (
    CONCEPT_COLLECTION_SCHEMA_VERSION,
    ConceptCollection,
    ConceptSubject,
    collect_concept_evidence,
)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


class TestP1bSchemaVersion(unittest.TestCase):

    def test_schema_version_is_semver_string(self):
        self.assertIsInstance(P1B_SCHEMA_VERSION, str)
        self.assertRegex(P1B_SCHEMA_VERSION, r"^\d+\.\d+\.\d+$")

    def test_graph_default_schema_version(self):
        g = ConceptTraceGraph(concept="peak_idx")
        self.assertEqual(g.schema_version, P1B_SCHEMA_VERSION)

    def test_index_default_schema_version(self):
        idx = ConceptTraceIndex(concept="peak_idx")
        self.assertEqual(idx.schema_version, P1B_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Mapping confidence matches P1b plan
# ---------------------------------------------------------------------------


class TestMappingConfidence(unittest.TestCase):

    def test_confidence_values_match_p1b_plan(self):
        expected = ("confirmed", "supported", "inferred", "unknown", "conflicted")
        self.assertEqual(MAPPING_CONFIDENCE_VALUES, expected)

    def test_mapping_claim_rejects_invalid_confidence(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC001",
                confidence="definite",
            )

    def test_mapping_claim_accepts_all_valid_confidences(self):
        """Each confidence value must be constructible with compliant evidence."""
        # confirmed
        mc = MappingClaim(
            claim_id="MC_TEST",
            confidence="confirmed",
            bridge_kind=BRIDGE_KIND_EXPLICIT_SOURCE,
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=["E010"],
            bridge_evidence_ids=["E020"],
        )
        self.assertEqual(mc.confidence, "confirmed")
        # supported
        mc = MappingClaim(
            claim_id="MC_TEST",
            confidence="supported",
            bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=["E010"],
        )
        self.assertEqual(mc.confidence, "supported")
        # inferred
        mc = MappingClaim(
            claim_id="MC_TEST",
            confidence="inferred",
            bridge_kind=BRIDGE_KIND_NAMING_ONLY,
            required_missing_evidence=["RTL module evidence"],
        )
        self.assertEqual(mc.confidence, "inferred")
        # unknown
        mc = MappingClaim(
            claim_id="MC_TEST",
            confidence="unknown",
            required_missing_evidence=["L5/L6 evidence", "RTL evidence"],
        )
        self.assertEqual(mc.confidence, "unknown")
        # conflicted
        mc = MappingClaim(claim_id="MC_TEST", confidence="conflicted")
        self.assertEqual(mc.confidence, "conflicted")

    def test_node_rejects_invalid_confidence(self):
        with self.assertRaises(ValueError):
            _ = ConceptTraceNode(
                node_id="N_BAD",
                label="bad",
                kind=NODE_KIND_STAGE_VIEW,
                confidence="guaranteed",
            )

    def test_edge_rejects_invalid_confidence(self):
        with self.assertRaises(ValueError):
            _ = ConceptTraceEdge(
                edge_id="E_BAD",
                from_node_id="N1",
                to_node_id="N2",
                label="bad",
                edge_type=EDGE_TYPE_MAPPING,
                confidence="certain",
            )

    def test_stage_view_rejects_invalid_confidence(self):
        with self.assertRaises(ValueError):
            _ = StageConceptView(
                view_id="SV_BAD",
                stage_id="L6",
                concept_ref="x",
                file_path="f.py",
                confidence="proven",
            )

    def test_rtl_view_rejects_invalid_confidence(self):
        with self.assertRaises(ValueError):
            _ = RTLEvidenceView(
                view_id="RV_BAD",
                concept_ref="x",
                confidence="absolute",
            )


# ---------------------------------------------------------------------------
# Bridge kind enum
# ---------------------------------------------------------------------------


class TestBridgeKind(unittest.TestCase):

    def test_bridge_kind_values_match_t005(self):
        expected = (
            "explicit_source_bridge",
            "calculation_role",
            "interface_behavior",
            "state_update",
            "pipeline_timing",
            "module_signal_relationship",
            "naming_only",
            "unknown",
        )
        self.assertEqual(BRIDGE_KIND_VALUES, expected)

    def test_mapping_claim_rejects_invalid_bridge_kind(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC001",
                bridge_kind="naming",
            )

    def test_mapping_claim_accepts_all_valid_bridge_kinds(self):
        """All bridge_kind values must be accepted when paired with a
        compliant confidence and evidence configuration."""
        for bk in BRIDGE_KIND_VALUES:
            mc = MappingClaim(
                claim_id="MC_TEST",
                bridge_kind=bk,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
            )
            self.assertEqual(mc.bridge_kind, bk)

    def test_strong_bridge_kinds_includes_explicit_source(self):
        self.assertIn(BRIDGE_KIND_EXPLICIT_SOURCE, STRONG_BRIDGE_KINDS)

    def test_strong_bridge_kinds_excludes_weak_ones(self):
        for weak in (
            BRIDGE_KIND_NAMING_ONLY,
            BRIDGE_KIND_CALCULATION_ROLE,
            BRIDGE_KIND_UNKNOWN,
        ):
            self.assertNotIn(weak, STRONG_BRIDGE_KINDS)


# ---------------------------------------------------------------------------
# MappingClaim evidence fields
# ---------------------------------------------------------------------------


class TestMappingClaimEvidenceFields(unittest.TestCase):

    def test_three_evidence_lists_exist(self):
        mc = MappingClaim(
            claim_id="MC001",
            required_missing_evidence=["both sides missing"],
        )
        self.assertIsInstance(mc.l5_l6_evidence_ids, list)
        self.assertIsInstance(mc.rtl_evidence_ids, list)
        self.assertIsInstance(mc.bridge_evidence_ids, list)

    def test_unknown_confidence_allows_empty_evidence_with_required_missing(self):
        mc = MappingClaim(
            claim_id="MC001",
            confidence="unknown",
            required_missing_evidence=["L5/L6 evidence", "RTL evidence"],
        )
        self.assertEqual(mc.l5_l6_evidence_ids, [])
        self.assertEqual(mc.rtl_evidence_ids, [])
        self.assertEqual(mc.bridge_evidence_ids, [])

    def test_to_dict_merges_evidence_ids(self):
        mc = MappingClaim(
            claim_id="MC001",
            concept_ref="peak_idx",
            l5_l6_evidence_ids=["E001", "E002"],
            rtl_evidence_ids=["E010", "E011"],
            bridge_evidence_ids=["E020"],
            confidence="supported",
            bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
        )
        d = mc.to_dict()
        merged = d["evidence_ids"]
        self.assertIn("E001", merged)
        self.assertIn("E010", merged)
        self.assertIn("E020", merged)

    def test_to_dict_deduplicates_evidence_ids(self):
        mc = MappingClaim(
            claim_id="MC001",
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=["E001"],
            bridge_evidence_ids=["E001"],
        )
        d = mc.to_dict()
        self.assertEqual(d["evidence_ids"].count("E001"), 1)

    def test_required_missing_evidence_field(self):
        mc = MappingClaim(
            claim_id="MC001",
            confidence="inferred",
            required_missing_evidence=["RTL signal evidence"],
        )
        self.assertEqual(mc.required_missing_evidence, ["RTL signal evidence"])

    def test_t005_fields_present(self):
        mc = MappingClaim(
            claim_id="MC001",
            claim_type="mapping_claim",
            statement="peak_idx maps to peak_detector module",
            concept_ref="peak_idx",
            l6_subject_ids=["N001"],
            rtl_subject_ids=["N002"],
            source_plan_step_id="step_3",
            required_missing_evidence=["evidence placeholder"],
        )
        self.assertEqual(mc.claim_type, "mapping_claim")
        self.assertEqual(mc.statement, "peak_idx maps to peak_detector module")
        self.assertEqual(mc.l6_subject_ids, ["N001"])
        self.assertEqual(mc.rtl_subject_ids, ["N002"])
        self.assertEqual(mc.source_plan_step_id, "step_3")


# ---------------------------------------------------------------------------
# Confidence vs evidence rules (from T005) — positive tests
# ---------------------------------------------------------------------------


class TestConfidenceEvidenceRules(unittest.TestCase):

    def test_supported_requires_both_sides(self):
        """supported mapping must have l5_l6_evidence_ids and
        rtl_evidence_ids."""
        mc = MappingClaim(
            claim_id="MC001",
            confidence="supported",
            bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=["E010"],
        )
        self.assertTrue(len(mc.l5_l6_evidence_ids) > 0)
        self.assertTrue(len(mc.rtl_evidence_ids) > 0)

    def test_confirmed_requires_strong_bridge(self):
        """confirmed mapping must have explicit_source_bridge or
        equivalent strong bridge."""
        mc = MappingClaim(
            claim_id="MC001",
            confidence="confirmed",
            bridge_kind=BRIDGE_KIND_EXPLICIT_SOURCE,
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=["E010"],
            bridge_evidence_ids=["E020"],
        )
        self.assertIn(mc.bridge_kind, STRONG_BRIDGE_KINDS)

    def test_naming_only_cannot_be_supported(self):
        """bridge_kind=naming_only cannot be used for supported/confirmed
        confidence. The schema-level validation enforces this."""
        mc = MappingClaim(
            claim_id="MC001",
            bridge_kind=BRIDGE_KIND_NAMING_ONLY,
            confidence="inferred",
            required_missing_evidence=["RTL module evidence"],
        )
        self.assertEqual(mc.bridge_kind, BRIDGE_KIND_NAMING_ONLY)
        self.assertNotEqual(mc.confidence, "supported")
        self.assertNotEqual(mc.confidence, "confirmed")

    def test_unknown_can_lack_one_side_but_needs_required_missing(self):
        """unknown/inferred can lack one-side evidence, but must have
        required_missing_evidence."""
        mc = MappingClaim(
            claim_id="MC001",
            confidence="unknown",
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=[],
            required_missing_evidence=["RTL signal evidence for peak_idx"],
        )
        self.assertEqual(mc.confidence, "unknown")
        self.assertEqual(mc.rtl_evidence_ids, [])
        self.assertTrue(len(mc.required_missing_evidence) > 0)

    def test_inferred_can_lack_one_side_but_needs_required_missing(self):
        mc = MappingClaim(
            claim_id="MC001",
            confidence="inferred",
            bridge_kind=BRIDGE_KIND_NAMING_ONLY,
            l5_l6_evidence_ids=["E001"],
            rtl_evidence_ids=[],
            required_missing_evidence=["RTL module evidence"],
        )
        self.assertEqual(mc.confidence, "inferred")
        self.assertTrue(len(mc.required_missing_evidence) > 0)


# ---------------------------------------------------------------------------
# Schema-level invalid-combination validation (negative tests)
# ---------------------------------------------------------------------------


class TestMappingClaimValidation(unittest.TestCase):
    """Negative tests: MappingClaim.__post_init__ rejects invalid
    confidence / bridge_kind / evidence combinations per T005 rules."""

    # -- rule 1: supported/confirmed require both evidence sides ------

    def test_supported_rejects_empty_l5_l6_evidence(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R1A",
                confidence="supported",
                bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
                rtl_evidence_ids=["E010"],
            )

    def test_supported_rejects_empty_rtl_evidence(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R1B",
                confidence="supported",
                bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
                l5_l6_evidence_ids=["E001"],
            )

    def test_confirmed_rejects_empty_l5_l6_evidence(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R1C",
                confidence="confirmed",
                bridge_kind=BRIDGE_KIND_EXPLICIT_SOURCE,
                rtl_evidence_ids=["E010"],
                bridge_evidence_ids=["E020"],
            )

    def test_confirmed_rejects_empty_rtl_evidence(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R1D",
                confidence="confirmed",
                bridge_kind=BRIDGE_KIND_EXPLICIT_SOURCE,
                l5_l6_evidence_ids=["E001"],
                bridge_evidence_ids=["E020"],
            )

    # -- rule 2: supported/confirmed cannot use weak bridge kinds -----

    def test_supported_rejects_naming_only_bridge(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R2A",
                confidence="supported",
                bridge_kind=BRIDGE_KIND_NAMING_ONLY,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
            )

    def test_supported_rejects_unknown_bridge(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R2B",
                confidence="supported",
                bridge_kind=BRIDGE_KIND_UNKNOWN,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
            )

    def test_confirmed_rejects_naming_only_bridge(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R2C",
                confidence="confirmed",
                bridge_kind=BRIDGE_KIND_NAMING_ONLY,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
                bridge_evidence_ids=["E020"],
            )

    def test_confirmed_rejects_unknown_bridge(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R2D",
                confidence="confirmed",
                bridge_kind=BRIDGE_KIND_UNKNOWN,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
                bridge_evidence_ids=["E020"],
            )

    # -- rule 3: confirmed requires strong bridge + bridge evidence ----

    def test_confirmed_rejects_non_strong_bridge(self):
        """calculation_role is a valid bridge_kind but not in
        STRONG_BRIDGE_KINDS, so it cannot be used with confirmed."""
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R3A",
                confidence="confirmed",
                bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
                bridge_evidence_ids=["E020"],
            )

    def test_confirmed_rejects_empty_bridge_evidence(self):
        """confirmed with explicit_source_bridge still requires
        non-empty bridge_evidence_ids."""
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R3B",
                confidence="confirmed",
                bridge_kind=BRIDGE_KIND_EXPLICIT_SOURCE,
                l5_l6_evidence_ids=["E001"],
                rtl_evidence_ids=["E010"],
            )

    # -- rule 4: unknown/inferred with missing side need explanation ---

    def test_unknown_rejects_missing_required_evidence_when_both_sides_missing(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R4A",
                confidence="unknown",
            )

    def test_unknown_rejects_missing_required_evidence_when_rtl_missing(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R4B",
                confidence="unknown",
                l5_l6_evidence_ids=["E001"],
            )

    def test_inferred_rejects_missing_required_evidence_when_both_sides_missing(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R4C",
                confidence="inferred",
                bridge_kind=BRIDGE_KIND_NAMING_ONLY,
            )

    def test_inferred_rejects_missing_required_evidence_when_l5_l6_missing(self):
        with self.assertRaises(ValueError):
            _ = MappingClaim(
                claim_id="MC_R4D",
                confidence="inferred",
                bridge_kind=BRIDGE_KIND_NAMING_ONLY,
                rtl_evidence_ids=["E010"],
            )

    # -- evidence_ids is derived, not settable via constructor ----------

    def test_evidence_ids_not_settable_via_constructor(self):
        """evidence_ids is init=False; passing it raises TypeError."""
        with self.assertRaises(TypeError):
            _ = MappingClaim(
                claim_id="MC_DERIVED",
                evidence_ids=["E_HACK"],  # pyright: ignore[reportCallIssue]
            )


# ---------------------------------------------------------------------------
# Node kinds and edge types
# ---------------------------------------------------------------------------


class TestNodeKinds(unittest.TestCase):

    def test_node_kinds_defined(self):
        expected = (
            "concept",
            "stage_view",
            "rtl_module",
            "rtl_signal",
            "rtl_always_block",
        )
        self.assertEqual(NODE_KIND_VALUES, expected)

    def test_node_rejects_invalid_kind(self):
        with self.assertRaises(ValueError):
            _ = ConceptTraceNode(node_id="N_BAD", label="bad", kind="invalid")

    def test_valid_stage_view_node(self):
        node = ConceptTraceNode(
            node_id="N001",
            label="peak_idx @ L6",
            kind=NODE_KIND_STAGE_VIEW,
            stage_id="L6_resource_opt",
            file_path="src/L6/model.py",
            symbol_refs=["PeakDetector"],
            evidence_ids=["E001"],
            confidence="supported",
        )
        self.assertEqual(node.kind, NODE_KIND_STAGE_VIEW)

    def test_valid_rtl_module_node(self):
        node = ConceptTraceNode(
            node_id="N002",
            label="peak_detector module",
            kind=NODE_KIND_RTL_MODULE,
            stage_id="RTL",
            file_path="rtl/peak_detector.v",
            evidence_ids=["E010"],
            confidence="inferred",
        )
        self.assertEqual(node.kind, NODE_KIND_RTL_MODULE)

    def test_valid_rtl_signal_node(self):
        node = ConceptTraceNode(
            node_id="N003",
            label="peak_idx wire",
            kind=NODE_KIND_RTL_SIGNAL,
            confidence="inferred",
        )
        self.assertEqual(node.kind, NODE_KIND_RTL_SIGNAL)


class TestEdgeTypes(unittest.TestCase):

    def test_edge_types_defined(self):
        expected = ("mapping", "evolution", "structural")
        self.assertEqual(EDGE_TYPE_VALUES, expected)

    def test_edge_rejects_invalid_type(self):
        with self.assertRaises(ValueError):
            _ = ConceptTraceEdge(
                edge_id="E_BAD",
                from_node_id="N1",
                to_node_id="N2",
                label="bad",
                edge_type="quantum",
            )

    def test_valid_mapping_edge(self):
        edge = ConceptTraceEdge(
            edge_id="E001",
            from_node_id="N_L6",
            to_node_id="N_RTL",
            label="maps to",
            edge_type=EDGE_TYPE_MAPPING,
            confidence="inferred",
            evidence_ids=["E010"],
        )
        self.assertEqual(edge.edge_type, EDGE_TYPE_MAPPING)


# ---------------------------------------------------------------------------
# StageConceptView / RTLEvidenceView
# ---------------------------------------------------------------------------


class TestStageConceptView(unittest.TestCase):

    def test_valid_stage_view(self):
        sv = StageConceptView(
            view_id="SV001",
            stage_id="L6_resource_opt",
            concept_ref="peak_idx",
            file_path="src/python_model/L6_resource_opt/model.py",
            symbol_refs=["peak_idx", "PeakDetector"],
            implementation_kind="method",
            evidence_ids=["E001"],
            confidence="supported",
        )
        self.assertEqual(sv.concept_ref, "peak_idx")
        self.assertEqual(sv.stage_id, "L6_resource_opt")

    def test_default_confidence_is_supported(self):
        sv = StageConceptView(
            view_id="SV002",
            stage_id="L5_fixedpoint",
            concept_ref="metric",
            file_path="src/python_model/L5_fixedpoint/model.py",
        )
        self.assertEqual(sv.confidence, "supported")


class TestRTLEvidenceView(unittest.TestCase):

    def test_valid_rtl_view(self):
        rv = RTLEvidenceView(
            view_id="RV001",
            concept_ref="peak_idx",
            module_name="peak_detector",
            file_path="rtl/peak_detector.v",
            signal_patterns=["peak_idx", "peak_valid"],
            evidence_ids=["E010", "E011"],
            confidence="inferred",
        )
        self.assertEqual(rv.module_name, "peak_detector")
        self.assertEqual(rv.signal_patterns, ["peak_idx", "peak_valid"])

    def test_default_confidence_is_inferred(self):
        rv = RTLEvidenceView(view_id="RV002", concept_ref="peak_idx")
        self.assertEqual(rv.confidence, "inferred")


# ---------------------------------------------------------------------------
# Unknown concept explicit representation
# ---------------------------------------------------------------------------


class TestUnknownConceptRepresentation(unittest.TestCase):

    def test_unknown_concept_trace_graph(self):
        """When a concept cannot be found, the graph must still produce an
        explicit representation with unknown confidence."""
        g = ConceptTraceGraph(
            concept="nonexistent_concept",
            nodes=[
                ConceptTraceNode(
                    node_id="N_UNKNOWN",
                    label="nonexistent_concept (unknown)",
                    kind=NODE_KIND_CONCEPT,
                    confidence="unknown",
                    notes="Concept not found in any stage or RTL.",
                ),
            ],
            mapping_claims=[
                MappingClaim(
                    claim_id="MC_UNKNOWN",
                    concept_ref="nonexistent_concept",
                    confidence="unknown",
                    required_missing_evidence=[
                        "L5/L6 source evidence",
                        "RTL source evidence",
                    ],
                ),
            ],
        )
        self.assertEqual(g.concept, "nonexistent_concept")
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].confidence, "unknown")
        self.assertEqual(len(g.mapping_claims), 1)
        self.assertEqual(g.mapping_claims[0].confidence, "unknown")
        self.assertEqual(
            len(g.mapping_claims[0].required_missing_evidence), 2
        )

    def test_empty_graph_is_valid_for_unknown(self):
        """A completely empty graph with just the concept name is also a
        valid unknown-concept representation."""
        g = ConceptTraceGraph(concept="ghost_signal")
        self.assertEqual(g.concept, "ghost_signal")
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.mapping_claims, [])


# ---------------------------------------------------------------------------
# ConceptTraceGraph serialization
# ---------------------------------------------------------------------------


class TestConceptTraceGraphSerialization(unittest.TestCase):

    def _sample_graph(self) -> ConceptTraceGraph:
        return ConceptTraceGraph(
            concept="peak_idx",
            task_request={"workflow": "p1b-trace-concept"},
            project_profile={"project_id": "coarse_sync_glm"},
            nodes=[
                ConceptTraceNode(
                    node_id="N001",
                    label="peak_idx @ L6",
                    kind=NODE_KIND_STAGE_VIEW,
                    stage_id="L6_resource_opt",
                    evidence_ids=["E001"],
                ),
                ConceptTraceNode(
                    node_id="N002",
                    label="peak_detector module",
                    kind=NODE_KIND_RTL_MODULE,
                    stage_id="RTL",
                    evidence_ids=["E010"],
                ),
            ],
            edges=[
                ConceptTraceEdge(
                    edge_id="E001",
                    from_node_id="N001",
                    to_node_id="N002",
                    label="maps to",
                    edge_type=EDGE_TYPE_MAPPING,
                    evidence_ids=["E001", "E010"],
                    source_claim_ids=["MC001"],
                ),
            ],
            stage_views=[
                StageConceptView(
                    view_id="SV001",
                    stage_id="L6_resource_opt",
                    concept_ref="peak_idx",
                    file_path="src/L6/model.py",
                    evidence_ids=["E001"],
                ),
            ],
            rtl_views=[
                RTLEvidenceView(
                    view_id="RV001",
                    concept_ref="peak_idx",
                    module_name="peak_detector",
                    evidence_ids=["E010"],
                ),
            ],
            mapping_claims=[
                MappingClaim(
                    claim_id="MC001",
                    concept_ref="peak_idx",
                    l6_subject_ids=["N001"],
                    rtl_subject_ids=["N002"],
                    bridge_kind=BRIDGE_KIND_CALCULATION_ROLE,
                    statement="peak_idx calculation maps to peak_detector logic",
                    confidence="supported",
                    l5_l6_evidence_ids=["E001"],
                    rtl_evidence_ids=["E010"],
                    bridge_evidence_ids=["E020"],
                ),
            ],
        )

    def test_to_dict_schema_version(self):
        d = self._sample_graph().to_dict()
        self.assertEqual(d["schema_version"], P1B_SCHEMA_VERSION)

    def test_to_dict_concept(self):
        d = self._sample_graph().to_dict()
        self.assertEqual(d["concept"], "peak_idx")

    def test_to_dict_nodes(self):
        d = self._sample_graph().to_dict()
        self.assertEqual(len(d["nodes"]), 2)
        self.assertEqual(d["nodes"][0]["node_id"], "N001")
        self.assertEqual(d["nodes"][1]["kind"], NODE_KIND_RTL_MODULE)

    def test_to_dict_edges(self):
        d = self._sample_graph().to_dict()
        self.assertEqual(len(d["edges"]), 1)
        self.assertEqual(d["edges"][0]["edge_type"], EDGE_TYPE_MAPPING)

    def test_to_dict_mapping_claims_merge_evidence(self):
        d = self._sample_graph().to_dict()
        mc = d["mapping_claims"][0]
        self.assertEqual(mc["claim_id"], "MC001")
        self.assertEqual(mc["confidence"], "supported")
        self.assertEqual(mc["bridge_kind"], BRIDGE_KIND_CALCULATION_ROLE)
        # evidence_ids should be merged from three source lists
        self.assertIn("E001", mc["evidence_ids"])
        self.assertIn("E010", mc["evidence_ids"])
        self.assertIn("E020", mc["evidence_ids"])
        # Source lists preserved
        self.assertEqual(mc["l5_l6_evidence_ids"], ["E001"])
        self.assertEqual(mc["rtl_evidence_ids"], ["E010"])
        self.assertEqual(mc["bridge_evidence_ids"], ["E020"])

    def test_to_dict_t005_fields(self):
        d = self._sample_graph().to_dict()
        mc = d["mapping_claims"][0]
        self.assertEqual(mc["claim_type"], "mapping_claim")
        self.assertEqual(mc["statement"], "peak_idx calculation maps to peak_detector logic")
        self.assertEqual(mc["l6_subject_ids"], ["N001"])
        self.assertEqual(mc["rtl_subject_ids"], ["N002"])

    def test_json_round_trip(self):
        g = self._sample_graph()
        parsed = json.loads(json.dumps(g.to_dict()))
        self.assertEqual(parsed["concept"], "peak_idx")
        self.assertEqual(parsed["nodes"][0]["node_id"], "N001")
        mc = parsed["mapping_claims"][0]
        self.assertIn("E001", mc["evidence_ids"])
        self.assertIn("E010", mc["evidence_ids"])

    def test_json_with_p1a_evidence_item(self):
        g = ConceptTraceGraph(
            concept="peak_idx",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E001",
                    source_type="python_symbol",
                    file_path="src/L6/model.py",
                    start_line=10,
                    end_line=20,
                    symbol="peak_idx",
                    excerpt_summary="peak index calculation",
                    evidence_strength="strong",
                ),
            ],
        )
        parsed = json.loads(json.dumps(g.to_dict()))
        self.assertEqual(
            parsed["evidence_items"][0]["evidence_id"], "E001"
        )


# ---------------------------------------------------------------------------
# ConceptTraceIndex serialization
# ---------------------------------------------------------------------------


class TestConceptTraceIndexSerialization(unittest.TestCase):

    def _sample_index(self) -> ConceptTraceIndex:
        return ConceptTraceIndex(
            concept="peak_idx",
            claim_index={
                "MC001": {
                    "confidence": "inferred",
                    "l5_l6_evidence_ids": ["E001"],
                    "rtl_evidence_ids": ["E010"],
                    "bridge_kind": BRIDGE_KIND_CALCULATION_ROLE,
                },
            },
            evidence_index={
                "E001": {
                    "source_type": "python_symbol",
                    "claim_ids": ["MC001"],
                },
                "E010": {
                    "source_type": "rtl_signal",
                    "claim_ids": ["MC001"],
                },
            },
            node_index={
                "N001": {"kind": "stage_view", "stage_id": "L6_resource_opt"},
                "N002": {"kind": "rtl_module", "module_name": "peak_detector"},
            },
            edge_index={
                "E001": {
                    "from": "N001",
                    "to": "N002",
                    "edge_type": "mapping",
                },
            },
            cross_references={
                "E001": ["MC001", "N001"],
                "E010": ["MC001", "N002"],
            },
        )

    def test_to_dict_schema_version(self):
        d = self._sample_index().to_dict()
        self.assertEqual(d["schema_version"], P1B_SCHEMA_VERSION)

    def test_to_dict_claim_index(self):
        d = self._sample_index().to_dict()
        self.assertIn("MC001", d["claim_index"])
        self.assertEqual(
            d["claim_index"]["MC001"]["confidence"], "inferred"
        )

    def test_to_dict_evidence_index(self):
        d = self._sample_index().to_dict()
        self.assertIn("E001", d["evidence_index"])
        self.assertIn("E010", d["evidence_index"])

    def test_json_round_trip(self):
        idx = self._sample_index()
        parsed = json.loads(json.dumps(idx.to_dict()))
        self.assertEqual(parsed["concept"], "peak_idx")
        self.assertEqual(len(parsed["claim_index"]), 1)
        self.assertEqual(len(parsed["evidence_index"]), 2)


# ---------------------------------------------------------------------------
# Reuse of P1a types inside ConceptTraceGraph
# ---------------------------------------------------------------------------


class TestConceptTraceGraphReusesP1aTypes(unittest.TestCase):

    def test_evidence_item_in_graph(self):
        g = ConceptTraceGraph(
            concept="peak_idx",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E001",
                    source_type="python_symbol",
                    file_path="model.py",
                    start_line=1,
                    end_line=5,
                    symbol="peak_idx",
                    excerpt_summary="test",
                    evidence_strength="strong",
                ),
            ],
        )
        self.assertIsInstance(g.evidence_items[0], EvidenceItem)

    def test_grounding_diagnostic_in_graph(self):
        g = ConceptTraceGraph(
            concept="peak_idx",
            grounding_diagnostics=[
                GroundingDiagnostic(
                    diagnostic_id="D001",
                    target_claim_id="MC001",
                    target_output_id=None,
                    severity="blocking",
                    issue_type="naming_only_supported_mapping",
                    recommended_action="Downgrade to inferred.",
                    related_evidence_ids=["E001"],
                    message="Mapping depends only on naming similarity.",
                ),
            ],
        )
        self.assertIsInstance(g.grounding_diagnostics[0], GroundingDiagnostic)

    def test_uncertainty_note_in_graph(self):
        g = ConceptTraceGraph(
            concept="peak_idx",
            uncertainty_notes=[
                UncertaintyNote(
                    uncertainty_id="U001",
                    topic="RTL mapping",
                    scope="peak_idx",
                    reason="No RTL module found",
                    current_interpretation="unknown",
                ),
            ],
        )
        self.assertIsInstance(g.uncertainty_notes[0], UncertaintyNote)

    def test_p1a_types_survive_json_round_trip(self):
        g = ConceptTraceGraph(
            concept="peak_idx",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E001",
                    source_type="python_symbol",
                    file_path="f.py",
                    start_line=1,
                    end_line=2,
                    symbol="s",
                    excerpt_summary="ex",
                    evidence_strength="strong",
                ),
            ],
            grounding_diagnostics=[
                GroundingDiagnostic(
                    diagnostic_id="D001",
                    target_claim_id=None,
                    target_output_id=None,
                    severity="non_blocking",
                    issue_type="one_sided_mapping_evidence",
                    recommended_action="Add RTL evidence.",
                ),
            ],
            uncertainty_notes=[
                UncertaintyNote(
                    uncertainty_id="U001",
                    topic="t",
                    scope="s",
                    reason="r",
                    current_interpretation="unknown",
                ),
            ],
        )
        parsed = json.loads(json.dumps(g.to_dict()))
        self.assertEqual(parsed["evidence_items"][0]["evidence_id"], "E001")
        self.assertEqual(
            parsed["grounding_diagnostics"][0]["issue_type"],
            "one_sided_mapping_evidence",
        )
        self.assertEqual(
            parsed["uncertainty_notes"][0]["uncertainty_id"], "U001"
        )


# ---------------------------------------------------------------------------
# P1b source collector (T002)
# ---------------------------------------------------------------------------


class TestP1bSourceCollector(unittest.TestCase):
    """Tests for the read-only P1b source file collector.

    Uses synthetic temp projects for deterministic testing.  The real
    coarse_sync_glm project test is skipped when the target is absent.
    """

    def _make_synthetic_project(self) -> Path:
        """Create a minimal ai_project_template-style project in /tmp."""
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_test_"))
        # L5
        l5 = tmp / "src" / "python_model" / "L5_fixedpoint"
        l5.mkdir(parents=True)
        (l5 / "model.py").write_text("class FixedPointModel:\n    pass\n")
        (l5 / "__init__.py").write_text("")
        # L6
        l6 = tmp / "src" / "python_model" / "L6_resource_opt"
        l6.mkdir(parents=True)
        (l6 / "model.py").write_text("class ResourceModel:\n    pass\n")
        (l6 / "__init__.py").write_text("")
        # RTL
        rtl = tmp / "src" / "verilog_model" / "rtl"
        rtl.mkdir(parents=True)
        (rtl / "top.v").write_text("module top(); endmodule\n")
        (rtl / "sub.v").write_text("module sub(); endmodule\n")
        # Tests
        tests = tmp / "tests"
        tests.mkdir()
        (tests / "test_model.py").write_text("def test_smoke(): pass\n")
        verilog_tests = tests / "verilog"
        verilog_tests.mkdir()
        (verilog_tests / "tb_top.v").write_text("module tb_top; endmodule\n")
        return tmp

    def test_synthetic_project_discovers_all_sections(self):
        tmp = self._make_synthetic_project()
        try:
            result = collect_p1b_sources(tmp, "test_concept")
            self.assertEqual(result.project_id, tmp.name)
            self.assertEqual(result.concept_name, "test_concept")
            # L5: 1 file (model.py, not __init__.py)
            self.assertEqual(len(result.l5_candidate_files), 1)
            self.assertTrue(
                result.l5_candidate_files[0].endswith("model.py")
            )
            # L6: 1 file
            self.assertEqual(len(result.l6_candidate_files), 1)
            # RTL: 2 files
            self.assertEqual(len(result.rtl_candidate_files), 2)
            # Tests: 1 py + 1 v = 2 files
            self.assertEqual(len(result.test_candidate_files), 2)
            # No missing sections
            self.assertEqual(result.missing_sections, [])
            self.assertEqual(result.collection_diagnostics, [])
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_synthetic_project_deterministic_ordering(self):
        tmp = self._make_synthetic_project()
        try:
            r1 = collect_p1b_sources(tmp, "c1")
            r2 = collect_p1b_sources(tmp, "c2")
            self.assertEqual(
                r1.l5_candidate_files, r2.l5_candidate_files
            )
            self.assertEqual(
                r1.rtl_candidate_files, r2.rtl_candidate_files
            )
            self.assertEqual(
                r1.test_candidate_files, r2.test_candidate_files
            )
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_synthetic_project_to_dict_is_json_serializable(self):
        tmp = self._make_synthetic_project()
        try:
            result = collect_p1b_sources(tmp, "test_concept")
            serialized = json.dumps(result.to_dict())
            parsed = json.loads(serialized)
            self.assertEqual(parsed["project_id"], tmp.name)
            self.assertEqual(parsed["concept_name"], "test_concept")
            self.assertIsInstance(parsed["l5_candidate_files"], list)
            self.assertIsInstance(parsed["rtl_candidate_files"], list)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_project_reports_missing_sections(self):
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_empty_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            result = collect_p1b_sources(tmp, "ghost")
            self.assertEqual(result.project_id, tmp.name)
            self.assertEqual(result.l5_candidate_files, [])
            self.assertEqual(result.l6_candidate_files, [])
            self.assertEqual(result.rtl_candidate_files, [])
            self.assertEqual(result.test_candidate_files, [])
            self.assertIn("L5_fixedpoint", result.missing_sections)
            self.assertIn("L6_resource_opt", result.missing_sections)
            self.assertIn("RTL", result.missing_sections)
            self.assertIn("tests", result.missing_sections)
            # Diagnostics should explain each missing section
            sections_in_diag = {
                d["section"] for d in result.collection_diagnostics
            }
            self.assertIn("L5_fixedpoint", sections_in_diag)
            self.assertIn("L6_resource_opt", sections_in_diag)
            self.assertIn("RTL", sections_in_diag)
            self.assertIn("tests", sections_in_diag)

    def test_nonexistent_project_root_raises_value_error(self):
        with self.assertRaises(ValueError):
            collect_p1b_sources(
                Path("/tmp/fpga_devmind_nonexistent__xyz"), "peak_idx"
            )

    def test_file_path_instead_of_directory_raises_value_error(self):
        with tempfile.NamedTemporaryFile(
            prefix="fpga_devmind_notdir_", suffix=".txt"
        ) as f:
            with self.assertRaises(ValueError):
                collect_p1b_sources(Path(f.name), "peak_idx")

    @unittest.skipUnless(
        os.path.isdir(
            "/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
        ),
        "coarse_sync_glm project not available",
    )
    def test_coarse_sync_glm_discovers_known_files(self):
        project = Path(
            "/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
        )
        result = collect_p1b_sources(project, "peak_idx")
        self.assertEqual(result.project_id, "fpga_project_coarse_sync_glm")
        self.assertEqual(result.concept_name, "peak_idx")
        # L6 must have multiple files
        self.assertGreaterEqual(len(result.l6_candidate_files), 3)
        # RTL must have .v files
        self.assertGreaterEqual(len(result.rtl_candidate_files), 5)
        # All RTL paths should end with .v or .vh
        for fp in result.rtl_candidate_files:
            self.assertTrue(
                fp.endswith(".v") or fp.endswith(".sv") or fp.endswith(".vh"),
                "Unexpected RTL file: {}".format(fp),
            )
        # L5 should exist for this project
        self.assertGreaterEqual(len(result.l5_candidate_files), 1)
        # No missing L6 or RTL sections
        self.assertNotIn("L6_resource_opt", result.missing_sections)
        self.assertNotIn("RTL", result.missing_sections)

    def test_schema_version_matches_output_contract(self):
        self.assertEqual(
            SOURCE_COLLECTION_SCHEMA_VERSION, "p1b-source-collection-0.1"
        )
        sc = SourceCollection()
        self.assertEqual(sc.schema_version, SOURCE_COLLECTION_SCHEMA_VERSION)

    def test_init_py_files_excluded(self):
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_initpy_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            l6 = tmp / "src" / "python_model" / "L6_resource_opt"
            l6.mkdir(parents=True)
            (l6 / "__init__.py").write_text("")
            (l6 / "model.py").write_text("pass\n")
            result = collect_p1b_sources(tmp, "test")
            # __init__.py should be excluded
            for fp in result.l6_candidate_files:
                self.assertNotIn("__init__.py", fp)

    def test_pycache_directories_excluded(self):
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_pycache_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            l6 = tmp / "src" / "python_model" / "L6_resource_opt"
            l6.mkdir(parents=True)
            (l6 / "model.py").write_text("pass\n")
            pycache = l6 / "__pycache__"
            pycache.mkdir()
            (pycache / "model.cpython-39.pyc").write_text("")
            result = collect_p1b_sources(tmp, "test")
            for fp in result.l6_candidate_files:
                self.assertNotIn("__pycache__", fp)


# ---------------------------------------------------------------------------
# P1b concept evidence collector (T003)
# ---------------------------------------------------------------------------


class TestP1bConceptCollector(unittest.TestCase):
    """Tests for the P1b concept evidence collector.

    Uses synthetic temp projects with known Python source files for
    deterministic testing.  The real coarse_sync_glm smoke test is
    skipped when the target is absent.
    """

    def _make_concept_project(self) -> tuple[Path, list[str]]:
        """Create a minimal L5/L6 project with known concept occurrences.

        Returns (project_root, candidate_files).
        """
        tmp = Path(tempfile.mkdtemp(prefix="fpga_devmind_concept_"))
        # L5 file with peak_idx as attribute and parameter
        l5 = tmp / "src" / "python_model" / "L5_fixedpoint"
        l5.mkdir(parents=True)
        (l5 / "__init__.py").write_text("")
        l5_code = (
            "class PeakDetector:\n"
            '    """Detect peak index in correlation output."""\n'
            "    def __init__(self):\n"
            "        self.peak_idx = 0\n"
            "\n"
            "    def compute_peak(self, corr_data):\n"
            "        peak_idx = corr_data.argmax()\n"
            "        self.peak_idx = peak_idx\n"
            "        return peak_idx\n"
        )
        (l5 / "detector.py").write_text(l5_code)

        # L6 file with peak_idx in dict and indexing
        l6 = tmp / "src" / "python_model" / "L6_resource_opt"
        l6.mkdir(parents=True)
        (l6 / "__init__.py").write_text("")
        l6_code = (
            "class ResourceModel:\n"
            '    """Resource-optimized peak detector."""\n'
            "    def report(self):\n"
            '        return {"peak_idx": self.peak_idx}\n'
            "\n"
            "def extract_metric(corr_re_0, peak_idx):\n"
            "    value = corr_re_0[peak_idx]\n"
            "    return value\n"
        )
        (l6 / "model.py").write_text(l6_code)

        # Collect candidate file paths (mimics T002 output)
        candidates: list[str] = []
        for p in sorted(l5.rglob("*.py")):
            if p.name != "__init__.py" and "__pycache__" not in p.parts:
                candidates.append(str(p))
        for p in sorted(l6.rglob("*.py")):
            if p.name != "__init__.py" and "__pycache__" not in p.parts:
                candidates.append(str(p))
        return tmp, candidates

    # -- basic structure tests -------------------------------------------

    def test_schema_version_matches_output_contract(self):
        self.assertEqual(
            CONCEPT_COLLECTION_SCHEMA_VERSION,
            "p1b-concept-collection-0.1",
        )
        cc = ConceptCollection()
        self.assertEqual(cc.schema_version, CONCEPT_COLLECTION_SCHEMA_VERSION)

    def test_concept_collection_defaults(self):
        cc = ConceptCollection(concept_name="test")
        self.assertEqual(cc.stage_side, "l5_l6")
        self.assertEqual(cc.evidence_items, [])
        self.assertEqual(cc.candidate_subjects, [])
        self.assertEqual(cc.uncertainty_notes, [])
        self.assertEqual(cc.collection_diagnostics, [])

    def test_to_dict_is_json_serializable(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            serialized = json.dumps(result.to_dict())
            parsed = json.loads(serialized)
            self.assertEqual(parsed["concept_name"], "peak_idx")
            self.assertEqual(parsed["stage_side"], "l5_l6")
            self.assertIsInstance(parsed["evidence_items"], list)
            self.assertIsInstance(parsed["candidate_subjects"], list)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    # -- concept extraction tests ----------------------------------------

    def test_finds_concept_in_classes_and_functions(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            # Should find concept in at least PeakDetector, compute_peak,
            # report, extract_metric
            subject_names = [s.name for s in result.candidate_subjects]
            self.assertIn("PeakDetector", subject_names)
            self.assertIn("compute_peak", subject_names)
            self.assertIn("ResourceModel", subject_names)
            self.assertIn("extract_metric", subject_names)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_evidence_items_have_valid_structure(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            self.assertGreater(len(result.evidence_items), 0)
            for ei in result.evidence_items:
                self.assertIsInstance(ei, EvidenceItem)
                self.assertTrue(ei.evidence_id.startswith("E:p1b_concept:"))
                self.assertEqual(ei.source_type, "concept_occurrence")
                self.assertGreater(ei.start_line, 0)
                self.assertGreaterEqual(ei.end_line, ei.start_line)
                self.assertIn(
                    ei.evidence_strength, ("strong", "medium", "weak")
                )
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_strength_classification(self):
        """Verify strength is classified as expected:
        - attribute (self.peak_idx) → strong
        - parameter (peak_idx) → strong
        - local variable (peak_idx = ...) → medium
        """
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            strengths = {
                ei.symbol: ei.evidence_strength
                for ei in result.evidence_items
            }
            # PeakDetector has self.peak_idx → strong
            self.assertEqual(strengths.get("PeakDetector"), "strong")
            # compute_peak has self.peak_idx assignment inside → strong
            self.assertEqual(strengths.get("compute_peak"), "strong")
            # extract_metric has peak_idx as parameter → strong
            self.assertEqual(strengths.get("extract_metric"), "strong")
            # ResourceModel has self.peak_idx via attribute → strong
            self.assertEqual(strengths.get("ResourceModel"), "strong")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    # -- unknown concept handling ----------------------------------------

    def test_unknown_concept_produces_uncertainty_note(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(
                tmp, "nonexistent_xyz", candidates
            )
            self.assertEqual(len(result.evidence_items), 0)
            self.assertEqual(len(result.candidate_subjects), 0)
            self.assertEqual(len(result.uncertainty_notes), 1)
            note = result.uncertainty_notes[0]
            self.assertIn("nonexistent_xyz", note.uncertainty_id)
            self.assertEqual(note.topic, "concept_not_found")
            self.assertEqual(note.current_interpretation, "unknown")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unknown_concept_produces_diagnostic(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(
                tmp, "ghost_signal", candidates
            )
            self.assertEqual(len(result.collection_diagnostics), 1)
            diag = result.collection_diagnostics[0]
            self.assertEqual(diag["section"], "L5_L6")
            self.assertEqual(diag["severity"], "info")
            self.assertIn("ghost_signal", diag["message"])
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    # -- evidence ID stability -------------------------------------------

    def test_evidence_id_stability(self):
        """Running the same extraction twice produces identical evidence
        IDs (deterministic ordinal-based generation)."""
        tmp, candidates = self._make_concept_project()
        try:
            r1 = collect_concept_evidence(tmp, "peak_idx", candidates)
            r2 = collect_concept_evidence(tmp, "peak_idx", candidates)
            ids1 = [ei.evidence_id for ei in r1.evidence_items]
            ids2 = [ei.evidence_id for ei in r2.evidence_items]
            self.assertEqual(ids1, ids2)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_evidence_id_stability_different_concept(self):
        """Different concept produces different evidence IDs."""
        tmp, candidates = self._make_concept_project()
        try:
            r1 = collect_concept_evidence(tmp, "peak_idx", candidates)
            r2 = collect_concept_evidence(
                tmp, "nonexistent_concept", candidates
            )
            self.assertGreater(len(r1.evidence_items), 0)
            self.assertEqual(len(r2.evidence_items), 0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    # -- candidate subjects structure ------------------------------------

    def test_candidate_subjects_have_correct_kinds(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            subject_kinds = {s.name: s.kind for s in result.candidate_subjects}
            self.assertEqual(subject_kinds.get("PeakDetector"), "class")
            self.assertEqual(subject_kinds.get("compute_peak"), "method")
            self.assertEqual(subject_kinds.get("ResourceModel"), "class")
            self.assertEqual(subject_kinds.get("extract_metric"), "function")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_candidate_subjects_have_evidence_refs(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            for subj in result.candidate_subjects:
                self.assertIsInstance(subj, ConceptSubject)
                self.assertGreater(len(subj.evidence_ids), 0)
                # Each evidence_id referenced in subject must exist
                all_eids = {ei.evidence_id for ei in result.evidence_items}
                for eid in subj.evidence_ids:
                    self.assertIn(eid, all_eids)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_role_hint_classification(self):
        tmp, candidates = self._make_concept_project()
        try:
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            roles = {s.name: s.role_hint for s in result.candidate_subjects}
            # PeakDetector has "detect" in name → calculation
            self.assertEqual(roles.get("PeakDetector"), "calculation")
            # compute_peak has "compute" in name → calculation
            self.assertEqual(roles.get("compute_peak"), "calculation")
            # ResourceModel docstring has "detect" (in "detector") → calculation
            self.assertEqual(roles.get("ResourceModel"), "calculation")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_syntax_error_file_is_skipped_with_diagnostic(self):
        """A file with invalid syntax should not crash the collector.
        Good files in the same batch must still produce evidence."""
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_syntax_err_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            bad_file = tmp / "broken.py"
            bad_file.write_text("def incomplete(\n")  # SyntaxError
            good_file = tmp / "good.py"
            good_file.write_text("peak_idx = 42\n")
            candidates = [str(bad_file), str(good_file)]
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            # Must not raise; good file evidence collected
            self.assertGreater(len(result.evidence_items), 0)
            good_found = any(
                ei.file_path == str(good_file)
                for ei in result.evidence_items
            )
            self.assertTrue(good_found)
            # Diagnostic for the broken file
            diag_paths = [d["file_path"] for d in result.collection_diagnostics]
            self.assertIn(str(bad_file), diag_paths)
            bad_diag = next(
                d for d in result.collection_diagnostics
                if d["file_path"] == str(bad_file)
            )
            self.assertEqual(bad_diag["severity"], "warning")
            self.assertIn("SyntaxError", bad_diag["message"])

    # -- edge cases ------------------------------------------------------

    def test_empty_candidate_files_produces_unknown(self):
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_empty_concept_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            result = collect_concept_evidence(tmp, "peak_idx", [])
            self.assertEqual(len(result.evidence_items), 0)
            self.assertEqual(len(result.uncertainty_notes), 1)

    def test_nonexistent_candidate_files_are_skipped(self):
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_missing_concept_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            result = collect_concept_evidence(
                tmp,
                "peak_idx",
                ["/tmp/nonexistent_file_abc123.py"],
            )
            self.assertEqual(len(result.evidence_items), 0)
            self.assertEqual(len(result.uncertainty_notes), 1)

    def test_init_py_and_pycache_excluded(self):
        with tempfile.TemporaryDirectory(
            prefix="fpga_devmind_excl_"
        ) as tmp_str:
            tmp = Path(tmp_str)
            l6 = tmp / "src" / "python_model" / "L6_resource_opt"
            l6.mkdir(parents=True)
            (l6 / "__init__.py").write_text("peak_idx = 1\n")
            pycache = l6 / "__pycache__"
            pycache.mkdir()
            (pycache / "helper.cpython-39.pyc").write_text("")
            (l6 / "model.py").write_text("peak_idx = 42\n")
            # Collect only non-__init__ files
            candidates = [
                str(l6 / "__init__.py"),
                str(l6 / "model.py"),
            ]
            result = collect_concept_evidence(tmp, "peak_idx", candidates)
            # __init__.py should be excluded
            files = [ei.file_path for ei in result.evidence_items]
            for f in files:
                self.assertNotIn("__init__.py", f)

    # -- real project smoke test -----------------------------------------

    @unittest.skipUnless(
        os.path.isdir(
            "/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
        ),
        "coarse_sync_glm project not available",
    )
    def test_coarse_sync_glm_peak_idx_extraction(self):
        project = Path(
            "/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
        )
        sources = collect_p1b_sources(project, "peak_idx")
        candidates = sources.l5_candidate_files + sources.l6_candidate_files
        result = collect_concept_evidence(project, "peak_idx", candidates)
        self.assertEqual(result.concept_name, "peak_idx")
        # peak_idx must be found in L5/L6
        self.assertGreater(len(result.evidence_items), 0)
        # All evidence must have valid strength
        for ei in result.evidence_items:
            self.assertIn(ei.evidence_strength, ("strong", "medium", "weak"))
        # No uncertainty for a known concept
        self.assertEqual(len(result.uncertainty_notes), 0)


if __name__ == "__main__":
    unittest.main()
