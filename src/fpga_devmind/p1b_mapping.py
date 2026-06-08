"""P1b mapping claim builder.

Builds conservative MappingClaim objects from T003 (L5/L6 concept
evidence) and T004 (RTL evidence) collections.  Does NOT perform
free-form explanation, LLM inference, or code modification.

T005 scope: mapping claim generation only.
Strict rules:
  - naming_only / comment-only evidence → never upgraded to supported.
  - no dual-side evidence → unknown/inferred + required_missing_evidence.
  - confirmed requires explicit_source_bridge + bridge evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from fpga_devmind.p1b_concept import ConceptCollection
from fpga_devmind.p1b_rtl import RTLEvidenceCollection
from fpga_devmind.p1b_schema import (
    BRIDGE_KIND_CALCULATION_ROLE,
    BRIDGE_KIND_INTERFACE_BEHAVIOR,
    BRIDGE_KIND_MODULE_SIGNAL,
    BRIDGE_KIND_NAMING_ONLY,
    BRIDGE_KIND_PIPELINE_TIMING,
    BRIDGE_KIND_STATE_UPDATE,
    BRIDGE_KIND_UNKNOWN,
    WEAK_BRIDGE_KINDS,
    MappingClaim,
)
from fpga_devmind.schema import EvidenceItem, UncertaintyNote

MAPPING_CLAIMS_SCHEMA_VERSION = "p1b-mapping-claims-0.1"

# ---------------------------------------------------------------------------
# Output data structures
# ---------------------------------------------------------------------------


@dataclass
class VisualizationEdge:
    """A lightweight edge for rendering concept-trace visualizations."""

    edge_id: str
    from_label: str
    to_label: str
    edge_type: str  # "mapping" | "evolution" | "structural"
    confidence: str = "inferred"
    claim_ref: str | None = None


@dataclass
class MappingClaimResult:
    """Structured output of the P1b mapping claim builder."""

    schema_version: str = MAPPING_CLAIMS_SCHEMA_VERSION
    concept_name: str = ""
    mapping_claims: list[MappingClaim] = field(default_factory=list)
    uncertainty_notes: list[UncertaintyNote] = field(
        default_factory=list
    )
    visualization_edges: list[VisualizationEdge] = field(
        default_factory=list
    )
    mapping_diagnostics: list[dict[str, str]] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "schema_version": self.schema_version,
            "concept_name": self.concept_name,
            "mapping_claims": [mc.to_dict() for mc in self.mapping_claims],
            "uncertainty_notes": [asdict(un) for un in self.uncertainty_notes],
            "visualization_edges": [asdict(ve) for ve in self.visualization_edges],
            "mapping_diagnostics": self.mapping_diagnostics,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_strong_evidence_ids(items: list[EvidenceItem]) -> list[str]:
    """Return evidence_ids with strong or medium strength."""
    return [
        item.evidence_id
        for item in items
        if item.evidence_strength in ("strong", "medium")
    ]


def _has_non_weak_evidence(items: list[EvidenceItem]) -> bool:
    """Return True if any evidence item has strong or medium strength."""
    return any(
        item.evidence_strength in ("strong", "medium") for item in items
    )


def _classify_bridge_kind(
    concept: ConceptCollection,
    rtl: RTLEvidenceCollection,
) -> str:
    """Determine bridge_kind based on evidence role hints and RTL types.

    Uses deterministic heuristics only — no LLM.
    """
    # Gather role hints from concept subjects
    role_hints: set[str] = set()
    for subj in concept.candidate_subjects:
        role_hints.add(subj.role_hint)

    # Gather RTL object types present
    rtl_types: set[str] = set()
    for view in rtl.rtl_views:
        rtl_types.add(view.object_type)

    # Check if any non-weak evidence exists on both sides
    l5_l6_strong = _has_non_weak_evidence(concept.evidence_items)
    rtl_strong = _has_non_weak_evidence(rtl.evidence_items)

    # --- role-based bridge classification ---
    if "calculation" in role_hints and "always_block" in rtl_types:
        if l5_l6_strong and rtl_strong:
            return BRIDGE_KIND_CALCULATION_ROLE

    if "state_update" in role_hints and "always_block" in rtl_types:
        if l5_l6_strong and rtl_strong:
            return BRIDGE_KIND_STATE_UPDATE

    if "interface" in role_hints and (
        "signal" in rtl_types or "module" in rtl_types
    ):
        if l5_l6_strong and rtl_strong:
            return BRIDGE_KIND_INTERFACE_BEHAVIOR

    if "pipeline" in role_hints and "always_block" in rtl_types:
        if l5_l6_strong and rtl_strong:
            return BRIDGE_KIND_PIPELINE_TIMING

    if "module" in rtl_types and "signal" in rtl_types:
        if l5_l6_strong and rtl_strong:
            return BRIDGE_KIND_MODULE_SIGNAL

    # If both sides have strong/medium evidence but no specific role match
    if l5_l6_strong and rtl_strong:
        return BRIDGE_KIND_NAMING_ONLY

    # Default: unknown
    return BRIDGE_KIND_UNKNOWN


def _determine_confidence(
    bridge_kind: str,
    l5_l6_evidence_ids: list[str],
    rtl_evidence_ids: list[str],
    all_l5_l6_items: list[EvidenceItem],
    all_rtl_items: list[EvidenceItem],
) -> str:
    """Determine mapping confidence conservatively.

    Rules:
      - No confirmed without explicit_source_bridge (avoid in first impl).
      - supported requires both sides + non-weak bridge.
      - inferred for naming-only or one-sided evidence.
      - unknown when one side is missing.
    """
    has_l5_l6 = bool(l5_l6_evidence_ids)
    has_rtl = bool(rtl_evidence_ids)

    if not has_l5_l6 and not has_rtl:
        return "unknown"

    if not has_l5_l6 or not has_rtl:
        # One side missing — always unknown or inferred
        # If the present side has strong evidence, use inferred;
        # otherwise unknown.
        if has_l5_l6 and _has_non_weak_evidence(all_l5_l6_items):
            return "inferred"
        if has_rtl and _has_non_weak_evidence(all_rtl_items):
            return "inferred"
        return "unknown"

    # Both sides present
    if bridge_kind in WEAK_BRIDGE_KINDS:
        # Weak bridge → always inferred, never supported
        return "inferred"

    # Non-weak bridge with both sides → supported
    return "supported"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_mapping_claims(
    concept_collection: ConceptCollection,
    rtl_collection: RTLEvidenceCollection,
) -> MappingClaimResult:
    """Build mapping claims from concept and RTL evidence collections.

    Parameters
    ----------
    concept_collection : ConceptCollection
        Output from T003 ``collect_concept_evidence()``.
    rtl_collection : RTLEvidenceCollection
        Output from T004 ``collect_rtl_evidence()``.

    Returns
    -------
    MappingClaimResult
        Conservative mapping claims, uncertainty notes, visualization
        edges, and diagnostics.  Never overclaims.
    """
    concept_name = concept_collection.concept_name
    result = MappingClaimResult(concept_name=concept_name)

    # Propagate uncertainty notes from upstream collectors
    result.uncertainty_notes.extend(concept_collection.uncertainty_notes)
    result.uncertainty_notes.extend(rtl_collection.uncertainty_notes)

    # --- classify evidence ---
    l5_l6_evidence_ids = [
        ei.evidence_id for ei in concept_collection.evidence_items
    ]
    rtl_evidence_ids = [
        ei.evidence_id for ei in rtl_collection.evidence_items
    ]

    l5_l6_subject_ids = [
        "{}:{}".format(subj.kind, subj.name)
        for subj in concept_collection.candidate_subjects
    ]
    rtl_subject_ids = [
        "{}:{}".format(view.object_type, view.name)
        for view in rtl_collection.rtl_views
    ]

    has_l5_l6 = bool(l5_l6_evidence_ids)
    has_rtl = bool(rtl_evidence_ids)

    # --- no evidence at all → unknown claim ---
    if not has_l5_l6 and not has_rtl:
        claim = MappingClaim(
            claim_id="MC_{}_UNKNOWN".format(concept_name),
            concept_ref=concept_name,
            confidence="unknown",
            required_missing_evidence=[
                "L5/L6 source evidence for '{}'".format(concept_name),
                "RTL source evidence for '{}'".format(concept_name),
            ],
        )
        result.mapping_claims.append(claim)
        result.mapping_diagnostics.append(
            {
                "section": "mapping",
                "severity": "info",
                "message": "No L5/L6 or RTL evidence found for '{}'; "
                "produced unknown claim".format(concept_name),
            }
        )
        return result

    # --- determine bridge kind ---
    bridge_kind = _classify_bridge_kind(
        concept_collection, rtl_collection
    )

    # --- determine confidence ---
    confidence = _determine_confidence(
        bridge_kind,
        l5_l6_evidence_ids,
        rtl_evidence_ids,
        concept_collection.evidence_items,
        rtl_collection.evidence_items,
    )

    # --- build required_missing_evidence if one side absent ---
    required_missing: list[str] = []
    if not has_l5_l6:
        required_missing.append(
            "L5/L6 source evidence for '{}'".format(concept_name)
        )
    if not has_rtl:
        required_missing.append(
            "RTL source evidence for '{}'".format(concept_name)
        )

    # --- build bridge_evidence_ids ---
    # For non-unknown bridge kinds, include the evidence that
    # participated in the bridge classification.  These are the
    # strong/medium evidence ids from both sides, deduplicated.
    bridge_evidence_ids: list[str] = []
    if bridge_kind != BRIDGE_KIND_UNKNOWN:
        seen: set[str] = set()
        for eid in _collect_strong_evidence_ids(concept_collection.evidence_items):
            if eid not in seen:
                bridge_evidence_ids.append(eid)
                seen.add(eid)
        for eid in _collect_strong_evidence_ids(rtl_collection.evidence_items):
            if eid not in seen:
                bridge_evidence_ids.append(eid)
                seen.add(eid)

    # --- build statement ---
    l5_l6_desc = "{} L5/L6 subject(s)".format(
        len(l5_l6_subject_ids)
    ) if has_l5_l6 else "no L5/L6 evidence"
    rtl_desc = "{} RTL view(s)".format(
        len(rtl_subject_ids)
    ) if has_rtl else "no RTL evidence"
    statement = (
        "Concept '{}' maps from [{}] to [{}] "
        "via {} bridge (confidence: {})".format(
            concept_name, l5_l6_desc, rtl_desc,
            bridge_kind, confidence,
        )
    )

    # --- construct the claim ---
    claim = MappingClaim(
        claim_id="MC_{}_001".format(concept_name),
        concept_ref=concept_name,
        statement=statement,
        l6_subject_ids=l5_l6_subject_ids,
        rtl_subject_ids=rtl_subject_ids,
        l5_l6_evidence_ids=l5_l6_evidence_ids,
        rtl_evidence_ids=rtl_evidence_ids,
        bridge_evidence_ids=bridge_evidence_ids,
        bridge_kind=bridge_kind,
        confidence=confidence,
        required_missing_evidence=required_missing,
    )
    result.mapping_claims.append(claim)

    # --- visualization edge ---
    if has_l5_l6 and has_rtl:
        edge = VisualizationEdge(
            edge_id="VE_{}_001".format(concept_name),
            from_label="{} @ L5/L6".format(concept_name),
            to_label="{} @ RTL".format(concept_name),
            edge_type="mapping",
            confidence=confidence,
            claim_ref=claim.claim_id,
        )
        result.visualization_edges.append(edge)

    # --- diagnostic for weak-only evidence ---
    l5_l6_strong_ids = _collect_strong_evidence_ids(
        concept_collection.evidence_items
    )
    rtl_strong_ids = _collect_strong_evidence_ids(
        rtl_collection.evidence_items
    )
    if has_l5_l6 and not l5_l6_strong_ids:
        result.mapping_diagnostics.append(
            {
                "section": "mapping",
                "severity": "info",
                "message": "L5/L6 evidence for '{}' is weak-only; "
                "bridge downgraded to inferred/unknown".format(
                    concept_name
                ),
            }
        )
    if has_rtl and not rtl_strong_ids:
        result.mapping_diagnostics.append(
            {
                "section": "mapping",
                "severity": "info",
                "message": "RTL evidence for '{}' is weak-only; "
                "bridge downgraded to inferred/unknown".format(
                    concept_name
                ),
            }
        )

    return result
