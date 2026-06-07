"""P1a schema objects.

These dataclasses intentionally mirror docs/phase1a-schema.md and stay
stdlib-only for the first implementation slice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str
    file_path: str
    start_line: int
    end_line: int
    symbol: str | None
    excerpt_summary: str
    evidence_strength: str
    snippet_complete: bool = True
    reliability_note: str | None = None


@dataclass
class CandidateClaim:
    claim_id: str
    claim_type: str
    claim_layer: str
    statement: str
    subject_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    counter_evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    required_missing_evidence: list[str] = field(default_factory=list)
    source_plan_step_id: str | None = None


@dataclass
class GroundingDiagnostic:
    diagnostic_id: str
    target_claim_id: str | None
    target_output_id: str | None
    severity: str
    issue_type: str
    recommended_action: str
    related_evidence_ids: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass
class UncertaintyNote:
    uncertainty_id: str
    topic: str
    scope: str
    reason: str
    current_interpretation: str
    needed_evidence: str | None = None
    source_claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    severity_for_understanding: str = "medium"


@dataclass
class ProjectProfile:
    project_id: str
    name: str
    root_path: str
    layout_type: str
    stage_coverage: list[str]
    l6_path: str | None
    config_paths: list[str]
    optional_context_paths: list[str]
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class StageNode:
    stage_id: str
    stage_name: str
    expected_role: str
    actual_role_summary: str
    source_files: list[str]
    main_entry_candidates: list[str]
    selected_main_entries: list[str]
    key_concept_ids: list[str]
    implementation_style: str
    evidence_ids: list[str]
    uncertainty_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class ConceptNode:
    concept_id: str
    canonical_name: str
    aliases: list[str]
    domain_type: str
    meaning: str
    stage_id: str
    implementation_view_ids: list[str] = field(default_factory=list)
    upstream_concept_ids: list[str] = field(default_factory=list)
    downstream_concept_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class ImplementationView:
    view_id: str
    concept_id: str
    stage_id: str
    file_path: str
    symbol_refs: list[str]
    implementation_kind: str
    explanation: str
    input_concept_ids: list[str] = field(default_factory=list)
    output_concept_ids: list[str] = field(default_factory=list)
    fixed_point_spec_ids: list[str] = field(default_factory=list)
    stream_interface_spec_ids: list[str] = field(default_factory=list)
    pipeline_timing_spec_ids: list[str] = field(default_factory=list)
    resource_estimate_spec_ids: list[str] = field(default_factory=list)
    source_claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class FixedPointSpec:
    spec_id: str
    signal_or_concept_id: str
    q_format: str
    signedness: str
    total_bits: int | None
    integer_bits: int | None
    fractional_bits: int | None
    scale: int | None
    rounding_mode: str | None
    overflow_mode: str | None
    source_claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class StreamInterfaceSpec:
    interface_id: str
    protocol: str
    data_signal: str | None
    valid_signal: str | None
    ready_signal: str | None
    last_signal: str | None
    sideband_signals: list[str] = field(default_factory=list)
    producer: str | None = None
    consumer: str | None = None
    valid_condition: str | None = None
    ready_backpressure_behavior: str | None = None
    packet_boundary_behavior: str | None = None
    source_claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class PipelineTimingSpec:
    timing_id: str
    stage_or_module_id: str
    latency_cycles: int | None
    register_boundaries: list[str] = field(default_factory=list)
    alignment_requirements: list[str] = field(default_factory=list)
    valid_propagation: str | None = None
    reset_behavior: str | None = None
    clock_domain: str | None = None
    source_claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class ResourceEstimateSpec:
    spec_id: str
    stage_or_concept_id: str
    estimate_name: str
    lut: int | str | None
    ff: int | str | None
    dsp48: int | str | None
    bram18k: int | str | None
    scale_expression: str | None = None
    condition: str | None = None
    target_device: str | None = None
    source_claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "supported"


@dataclass
class VizNode:
    node_id: str
    label: str
    kind: str
    source_concept_id: str
    source_claim_ids: list[str]
    evidence_ids: list[str]
    confidence: str


@dataclass
class VizEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    label: str
    source_claim_ids: list[str]
    evidence_ids: list[str]
    confidence: str


@dataclass
class VisualizationSpec:
    viz_id: str
    title: str
    viz_type: str
    nodes: list[VizNode]
    edges: list[VizEdge]
    uncertainty_display_policy: str = "show_unknown_and_inferred"
    evidence_display_policy: str = "node_and_edge_claim_ids"


@dataclass
class TaskRequest:
    request_id: str
    workflow: str
    project_root: str
    stage_id: str
    user_intent: str
    focus: list[str]
    constraints: dict[str, Any]


@dataclass
class ProjectGraph:
    schema_version: str
    task_request: TaskRequest
    project_profile: ProjectProfile
    stage: StageNode
    concepts: list[ConceptNode]
    implementation_views: list[ImplementationView]
    fixed_point_specs: list[FixedPointSpec]
    stream_interface_specs: list[StreamInterfaceSpec]
    pipeline_timing_specs: list[PipelineTimingSpec]
    resource_estimate_specs: list[ResourceEstimateSpec]
    evidence_items: list[EvidenceItem]
    candidate_claims: list[CandidateClaim]
    grounding_diagnostics: list[GroundingDiagnostic]
    uncertainty_notes: list[UncertaintyNote]
    visualization_specs: list[VisualizationSpec]
    run_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
