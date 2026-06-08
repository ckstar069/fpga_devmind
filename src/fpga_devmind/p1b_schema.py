"""P1b concept trace schema objects.

These dataclasses define the artifact contract for P1b single-concept
L5/L6-to-RTL trace.  They align with docs/implementation-plan-p1b.md
and docs/tasks/T005-p1b-mapping-claim-builder.md, and reuse P1a types
(EvidenceItem, GroundingDiagnostic, UncertaintyNote) where applicable.

concept_trace_graph.json is the source of truth.
concept_trace.md / concept_trace.mmd are rendered views only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from fpga_devmind.schema import (
    EvidenceItem,
    GroundingDiagnostic,
    UncertaintyNote,
)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

P1B_SCHEMA_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Enum-like constants
# ---------------------------------------------------------------------------

# Mapping confidence values (ordered by decreasing strength).
MAPPING_CONFIDENCE_VALUES = (
    "confirmed",
    "supported",
    "inferred",
    "unknown",
    "conflicted",
)

# Node kinds inside a concept trace graph.
NODE_KIND_CONCEPT = "concept"
NODE_KIND_STAGE_VIEW = "stage_view"
NODE_KIND_RTL_MODULE = "rtl_module"
NODE_KIND_RTL_SIGNAL = "rtl_signal"
NODE_KIND_RTL_ALWAYS_BLOCK = "rtl_always_block"
NODE_KIND_VALUES = (
    NODE_KIND_CONCEPT,
    NODE_KIND_STAGE_VIEW,
    NODE_KIND_RTL_MODULE,
    NODE_KIND_RTL_SIGNAL,
    NODE_KIND_RTL_ALWAYS_BLOCK,
)

# Edge types between trace nodes.
EDGE_TYPE_MAPPING = "mapping"
EDGE_TYPE_EVOLUTION = "evolution"
EDGE_TYPE_STRUCTURAL = "structural"
EDGE_TYPE_VALUES = (
    EDGE_TYPE_MAPPING,
    EDGE_TYPE_EVOLUTION,
    EDGE_TYPE_STRUCTURAL,
)

# Bridge kinds for mapping claims.
# Aligned with docs/tasks/T005-p1b-mapping-claim-builder.md.
BRIDGE_KIND_EXPLICIT_SOURCE = "explicit_source_bridge"
BRIDGE_KIND_CALCULATION_ROLE = "calculation_role"
BRIDGE_KIND_INTERFACE_BEHAVIOR = "interface_behavior"
BRIDGE_KIND_STATE_UPDATE = "state_update"
BRIDGE_KIND_PIPELINE_TIMING = "pipeline_timing"
BRIDGE_KIND_MODULE_SIGNAL = "module_signal_relationship"
BRIDGE_KIND_NAMING_ONLY = "naming_only"
BRIDGE_KIND_UNKNOWN = "unknown"
BRIDGE_KIND_VALUES = (
    BRIDGE_KIND_EXPLICIT_SOURCE,
    BRIDGE_KIND_CALCULATION_ROLE,
    BRIDGE_KIND_INTERFACE_BEHAVIOR,
    BRIDGE_KIND_STATE_UPDATE,
    BRIDGE_KIND_PIPELINE_TIMING,
    BRIDGE_KIND_MODULE_SIGNAL,
    BRIDGE_KIND_NAMING_ONLY,
    BRIDGE_KIND_UNKNOWN,
)

# Bridge kinds strong enough to support "confirmed" confidence.
STRONG_BRIDGE_KINDS = frozenset({BRIDGE_KIND_EXPLICIT_SOURCE})

# Weak bridge kinds that cannot be used with supported/confirmed.
WEAK_BRIDGE_KINDS = frozenset({BRIDGE_KIND_NAMING_ONLY, BRIDGE_KIND_UNKNOWN})


def _validate_field(value: str, allowed: tuple[str, ...], label: str) -> None:
    if value not in allowed:
        raise ValueError(
            f"Invalid {label} '{value}'; expected one of {allowed}"
        )


# ---------------------------------------------------------------------------
# Core P1b types
# ---------------------------------------------------------------------------


@dataclass
class ConceptTraceNode:
    """A node in the P1b concept trace graph.

    Represents the traced concept at a specific stage (L5/L6), an RTL
    object (module/signal/always-block), or the concept itself as an
    abstract anchor.
    """

    node_id: str
    label: str
    kind: str  # one of NODE_KIND_VALUES
    stage_id: str | None = None
    file_path: str | None = None
    symbol_refs: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_field(self.kind, NODE_KIND_VALUES, "node kind")
        _validate_field(self.confidence, MAPPING_CONFIDENCE_VALUES, "confidence")


@dataclass
class ConceptTraceEdge:
    """An edge connecting two ConceptTraceNodes."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    label: str
    edge_type: str  # one of EDGE_TYPE_VALUES
    confidence: str = "inferred"
    evidence_ids: list[str] = field(default_factory=list)
    source_claim_ids: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_field(self.edge_type, EDGE_TYPE_VALUES, "edge type")
        _validate_field(self.confidence, MAPPING_CONFIDENCE_VALUES, "confidence")


@dataclass
class StageConceptView:
    """View of a concept at a specific Python model stage (L5 or L6)."""

    view_id: str
    stage_id: str
    concept_ref: str
    file_path: str
    symbol_refs: list[str] = field(default_factory=list)
    implementation_kind: str = "unknown"
    explanation: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"

    def __post_init__(self) -> None:
        _validate_field(
            self.confidence, MAPPING_CONFIDENCE_VALUES, "confidence"
        )


@dataclass
class RTLEvidenceView:
    """View of a concept's RTL realization.

    Captures modules, signals, and always-blocks found on the RTL side
    that may correspond to the traced concept.
    """

    view_id: str
    concept_ref: str
    module_name: str | None = None
    file_path: str | None = None
    signal_patterns: list[str] = field(default_factory=list)
    always_block_refs: list[str] = field(default_factory=list)
    instance_refs: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "inferred"
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_field(
            self.confidence, MAPPING_CONFIDENCE_VALUES, "confidence"
        )


@dataclass
class MappingClaim:
    """A claim mapping a concept between L5/L6 and RTL.

    Fields align with docs/tasks/T005-p1b-mapping-claim-builder.md.

    Three separate evidence lists:
      - l5_l6_evidence_ids: evidence from Python model stages.
      - rtl_evidence_ids: evidence from RTL sources.
      - bridge_evidence_ids: evidence supporting the bridge itself.

    evidence_ids is a derived summary field (init=False).  It is
    computed in __post_init__ by merging the three source lists with
    deduplication.  Callers cannot set it directly.

    Confidence rules (from T005):
      confirmed  - only with explicit_source_bridge + bridge evidence.
      supported  - both sides present + non-weak bridge.
      inferred   - naming/structure suggests relation; weak bridge.
      unknown    - one side cannot be found.
      conflicted - multiple incompatible RTL candidates.
    """

    claim_id: str
    claim_type: str = "mapping_claim"
    statement: str = ""
    concept_ref: str = ""
    l6_subject_ids: list[str] = field(default_factory=list)
    rtl_subject_ids: list[str] = field(default_factory=list)
    l5_l6_evidence_ids: list[str] = field(default_factory=list)
    rtl_evidence_ids: list[str] = field(default_factory=list)
    bridge_evidence_ids: list[str] = field(default_factory=list)
    bridge_kind: str = BRIDGE_KIND_UNKNOWN
    confidence: str = "unknown"
    required_missing_evidence: list[str] = field(default_factory=list)
    source_plan_step_id: str | None = None
    notes: str | None = None

    # Derived summary — callers cannot set this directly.
    evidence_ids: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        # --- enum validation ---
        _validate_field(
            self.confidence, MAPPING_CONFIDENCE_VALUES, "confidence"
        )
        _validate_field(
            self.bridge_kind, BRIDGE_KIND_VALUES, "bridge kind"
        )

        # --- rule 1: supported/confirmed require both evidence sides ---
        if self.confidence in ("supported", "confirmed"):
            if not self.l5_l6_evidence_ids:
                raise ValueError(
                    "MappingClaim {}: confidence '{}' requires non-empty l5_l6_evidence_ids".format(self.claim_id, self.confidence)
                )
            if not self.rtl_evidence_ids:
                raise ValueError(
                    "MappingClaim {}: confidence '{}' requires non-empty rtl_evidence_ids".format(self.claim_id, self.confidence)
                )

        # --- rule 2: supported/confirmed cannot use weak bridge kinds ---
        if self.confidence in ("supported", "confirmed"):
            if self.bridge_kind in WEAK_BRIDGE_KINDS:
                raise ValueError(
                    "MappingClaim {}: confidence '{}' cannot use bridge_kind '{}'".format(self.claim_id, self.confidence, self.bridge_kind)
                )

        # --- rule 3: confirmed requires strong bridge + bridge evidence ---
        if self.confidence == "confirmed":
            if self.bridge_kind not in STRONG_BRIDGE_KINDS:
                raise ValueError(
                    "MappingClaim {}: confidence 'confirmed' requires bridge_kind in STRONG_BRIDGE_KINDS, got '{}'".format(self.claim_id, self.bridge_kind)
                )
            if not self.bridge_evidence_ids:
                raise ValueError(
                    "MappingClaim {}: confidence 'confirmed' requires non-empty bridge_evidence_ids".format(self.claim_id)
                )

        # --- rule 4: unknown/inferred with missing side need explanation ---
        if self.confidence in ("unknown", "inferred"):
            has_l5_l6 = bool(self.l5_l6_evidence_ids)
            has_rtl = bool(self.rtl_evidence_ids)
            if not has_l5_l6 or not has_rtl:
                if not self.required_missing_evidence:
                    raise ValueError(
                        "MappingClaim {}: confidence '{}' with missing evidence side requires non-empty required_missing_evidence".format(self.claim_id, self.confidence)
                    )

        # --- compute derived evidence_ids ---
        merged: list[str] = []
        for eid in self.l5_l6_evidence_ids:
            if eid not in merged:
                merged.append(eid)
        for eid in self.rtl_evidence_ids:
            if eid not in merged:
                merged.append(eid)
        for eid in self.bridge_evidence_ids:
            if eid not in merged:
                merged.append(eid)
        self.evidence_ids = merged

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Top-level artifacts
# ---------------------------------------------------------------------------


@dataclass
class ConceptTraceGraph:
    """Top-level P1b concept trace artifact.

    ``concept_trace_graph.json`` is the source of truth.
    Markdown / Mermaid are rendered views only.
    """

    schema_version: str = P1B_SCHEMA_VERSION
    task_request: dict[str, Any] = field(default_factory=dict)
    project_profile: dict[str, Any] = field(default_factory=dict)
    concept: str = ""
    nodes: list[ConceptTraceNode] = field(default_factory=list)
    edges: list[ConceptTraceEdge] = field(default_factory=list)
    stage_views: list[StageConceptView] = field(default_factory=list)
    rtl_views: list[RTLEvidenceView] = field(default_factory=list)
    mapping_claims: list[MappingClaim] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    uncertainty_notes: list[UncertaintyNote] = field(default_factory=list)
    grounding_diagnostics: list[GroundingDiagnostic] = field(
        default_factory=list
    )
    run_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "task_request": self.task_request,
            "project_profile": self.project_profile,
            "concept": self.concept,
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
            "stage_views": [asdict(sv) for sv in self.stage_views],
            "rtl_views": [asdict(rv) for rv in self.rtl_views],
            "mapping_claims": [mc.to_dict() for mc in self.mapping_claims],
            "evidence_items": [asdict(ei) for ei in self.evidence_items],
            "uncertainty_notes": [asdict(un) for un in self.uncertainty_notes],
            "grounding_diagnostics": [
                asdict(gd) for gd in self.grounding_diagnostics
            ],
            "run_metadata": self.run_metadata,
        }
        return d


@dataclass
class ConceptTraceIndex:
    """Reverse index for P1b concept trace.

    Allows looking up claims by id, evidence by id, and cross-referencing
    claims to their evidence and vice versa.
    """

    schema_version: str = P1B_SCHEMA_VERSION
    concept: str = ""
    claim_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    edge_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    cross_references: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
