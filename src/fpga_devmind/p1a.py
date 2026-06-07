"""P1a single-stage understanding runner."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .schema import (
    CandidateClaim,
    ConceptNode,
    FixedPointSpec,
    GroundingDiagnostic,
    ImplementationView,
    PipelineTimingSpec,
    ProjectGraph,
    ProjectProfile,
    ResourceEstimateSpec,
    StageNode,
    StreamInterfaceSpec,
    TaskRequest,
    UncertaintyNote,
    VisualizationSpec,
    VizEdge,
    VizNode,
)
from .tools import extract_parameters, extract_python_stage_patterns, scan_project_tree


DEFAULT_PROJECT = Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm")
DEFAULT_OUT = Path("/tmp/fpga_devmind/p1a_coarse_sync_l6")


def _claim(
    idx: int,
    claim_type: str,
    layer: str,
    statement: str,
    evidence_ids: Iterable[str],
    confidence: str = "supported",
    subjects: Iterable[str] = (),
) -> CandidateClaim:
    return CandidateClaim(
        claim_id=f"C{idx:03d}",
        claim_type=claim_type,
        claim_layer=layer,
        statement=statement,
        subject_ids=list(subjects),
        evidence_ids=list(dict.fromkeys(evidence_ids)),
        confidence=confidence,
        source_plan_step_id="p1a_claim_builder",
    )


def _concept(idx: int, name: str, domain_type: str, meaning: str, evidence_ids: list[str]) -> ConceptNode:
    return ConceptNode(
        concept_id=f"N{idx:03d}",
        canonical_name=name,
        aliases=[name],
        domain_type=domain_type,
        meaning=meaning,
        stage_id="L6_resource_opt",
        evidence_ids=evidence_ids,
        confidence="supported" if evidence_ids else "unknown",
    )


def _diagnose_claims(claims: list[CandidateClaim], evidence_strength: dict[str, str]) -> list[GroundingDiagnostic]:
    diagnostics: list[GroundingDiagnostic] = []
    did = 1
    for claim in claims:
        if claim.confidence == "confirmed" and not claim.evidence_ids:
            diagnostics.append(
                GroundingDiagnostic(
                    diagnostic_id=f"D{did:03d}",
                    target_claim_id=claim.claim_id,
                    target_output_id=None,
                    severity="blocking",
                    issue_type="unsupported_confirmed_claim",
                    recommended_action="downgrade_confidence",
                    message="Confirmed claim has no evidence ids.",
                )
            )
            did += 1
        if claim.confidence == "confirmed":
            strengths = {evidence_strength.get(eid, "weak") for eid in claim.evidence_ids}
            if "strong" not in strengths:
                diagnostics.append(
                    GroundingDiagnostic(
                        diagnostic_id=f"D{did:03d}",
                        target_claim_id=claim.claim_id,
                        target_output_id=None,
                        severity="blocking",
                        issue_type="unsupported_confirmed_claim",
                        recommended_action="downgrade_confidence",
                        related_evidence_ids=claim.evidence_ids,
                        message="Confirmed claim needs at least one strong evidence item.",
                    )
                )
                did += 1
        if claim.confidence == "confirmed" and claim.claim_layer == "prohibited":
            diagnostics.append(
                GroundingDiagnostic(
                    diagnostic_id=f"D{did:03d}",
                    target_claim_id=claim.claim_id,
                    target_output_id=None,
                    severity="blocking",
                    issue_type="prohibited_claim_source",
                    recommended_action="downgrade_confidence",
                    related_evidence_ids=claim.evidence_ids,
                )
            )
            did += 1
    return diagnostics


def _build_graph(project_root: Path, out_dir: Path) -> ProjectGraph:
    tree = scan_project_tree(project_root)
    l6_path = Path(tree["l6_path"]) if tree["l6_path"] else None
    if l6_path is None:
        raise FileNotFoundError("L6_resource_opt path not found")
    l6_files = sorted(p for p in l6_path.glob("*.py") if p.name != "__init__.py")
    py_obs = extract_python_stage_patterns(l6_files)
    params, param_evidence = extract_parameters(project_root)
    param_by_name = {p["name"]: p for p in params}
    evidence_items = py_obs.evidence_items + param_evidence
    evidence_strength = {e.evidence_id: e.evidence_strength for e in evidence_items}

    role_to_symbol = {s.role_hint: s for s in py_obs.symbols}
    stage_roles = [
        ("stage_s0_autocorr_norm", "S0 AutocorrNorm", "autocorrelation and normalization"),
        ("stage_s1_merge", "S1 Merge", "multi-delay metric merge"),
        ("stage_s2_smooth_detect", "S2 SmoothDetect", "smoothing and peak detection"),
        ("stage_s3_cfo", "S3 CFO", "CFO estimation"),
    ]

    concepts: list[ConceptNode] = []
    views: list[ImplementationView] = []
    claims: list[CandidateClaim] = []

    stage_eids = []
    for role, _label, _meaning in stage_roles:
        if role in role_to_symbol:
            stage_eids.extend(role_to_symbol[role].evidence_ids)

    claims.append(
        _claim(
            1,
            "implementation_claim",
            "mandatory",
            "L6_resource_opt implements a four-stage coarse synchronization pipeline when S0/S1/S2/S3 stage classes are present.",
            stage_eids,
            confidence="confirmed" if len(stage_eids) >= 4 else "supported",
        )
    )

    idx = 1
    claim_idx = 2
    for role, label, meaning in stage_roles:
        symbol = role_to_symbol.get(role)
        eids = symbol.evidence_ids if symbol else []
        concept = _concept(idx, label, "algorithm_concept", meaning, eids)
        concepts.append(concept)
        if symbol:
            views.append(
                ImplementationView(
                    view_id=f"V{idx:03d}",
                    concept_id=concept.concept_id,
                    stage_id="L6_resource_opt",
                    file_path=symbol.file_path,
                    symbol_refs=[symbol.name],
                    implementation_kind="pipeline_stage",
                    explanation=f"{label} is represented by {symbol.name}.",
                    source_claim_ids=[f"C{claim_idx:03d}"],
                    evidence_ids=eids,
                    confidence="confirmed",
                )
            )
            claims.append(
                _claim(
                    claim_idx,
                    "implementation_claim",
                    "mandatory",
                    f"{label} is implemented by {symbol.name}.",
                    eids,
                    confidence="confirmed",
                    subjects=[concept.concept_id],
                )
            )
        else:
            claims.append(
                _claim(
                    claim_idx,
                    "uncertainty_claim",
                    "mandatory",
                    f"{label} was not observed in L6 evidence.",
                    [],
                    confidence="unknown",
                    subjects=[concept.concept_id],
                )
            )
        claim_idx += 1
        idx += 1

    # Dataflow claims from deterministic stage order.
    dataflow_claim_ids_by_pair: dict[tuple[str, str], list[str]] = {}
    for edge in py_obs.dataflow_edges:
        claim_id = f"C{claim_idx:03d}"
        claims.append(
            _claim(
                claim_idx,
                "dataflow_claim",
                "mandatory",
                f"{edge['from_symbol']} feeds {edge['to_symbol']} in the coarse S0-S3 pipeline order.",
                edge["evidence_ids"],
                confidence="supported",
            )
        )
        dataflow_claim_ids_by_pair[(edge["from_symbol"], edge["to_symbol"])] = [claim_id]
        claim_idx += 1

    fixed_point_specs: list[FixedPointSpec] = []
    stream_interface_specs: list[StreamInterfaceSpec] = []
    pipeline_timing_specs: list[PipelineTimingSpec] = []
    resource_estimate_specs: list[ResourceEstimateSpec] = []

    # Fixed-point and interface/resource claims are conditional.
    q_eids = []
    for event in py_obs.q_operations + py_obs.width_growth_events:
        q_eids.extend(event["evidence_ids"])
    for name in ("q_int_bits", "q_frac_bits", "data_width", "rounding_mode", "saturation"):
        if name in param_by_name:
            q_eids.extend(param_by_name[name]["evidence_ids"])
    if q_eids:
        q_int_bits = _param_int(param_by_name, "q_int_bits")
        q_frac_bits = _param_int(param_by_name, "q_frac_bits")
        total_bits = q_int_bits + q_frac_bits if q_int_bits is not None and q_frac_bits is not None else _param_int(param_by_name, "data_width")
        scale = 1 << q_frac_bits if q_frac_bits is not None else None
        claims.append(
            _claim(
                claim_idx,
                "fixed_point_claim",
                "conditional",
                f"L6 evidence contains fixed-point/Q-format behavior markers ({_q_format(q_int_bits, q_frac_bits)}).",
                q_eids,
                confidence="supported",
            )
        )
        fixed_point_specs.append(
            FixedPointSpec(
                spec_id="FP001",
                signal_or_concept_id="stage:L6_resource_opt",
                q_format=_q_format(q_int_bits, q_frac_bits),
                signedness="signed",
                total_bits=total_bits,
                integer_bits=q_int_bits,
                fractional_bits=q_frac_bits,
                scale=scale,
                rounding_mode=str(param_by_name.get("rounding_mode", {}).get("value_repr", "unknown")),
                overflow_mode="saturate" if param_by_name.get("saturation", {}).get("value_repr") is True else "unknown",
                source_claim_ids=[f"C{claim_idx:03d}"],
                evidence_ids=list(dict.fromkeys(q_eids)),
                confidence="supported",
            )
        )
        claim_idx += 1

    interface_eids = []
    for event in py_obs.interface_events:
        interface_eids.extend(event["evidence_ids"])
    for name in ("interface_type", "axis_data_width", "axis_has_tlast"):
        if name in param_by_name:
            interface_eids.extend(param_by_name[name]["evidence_ids"])
    if interface_eids:
        protocol = str(param_by_name.get("interface_type", {}).get("value_repr", "unknown"))
        claims.append(
            _claim(
                claim_idx,
                "interface_claim",
                "conditional",
                f"L6 evidence contains {protocol} stream interface markers.",
                interface_eids,
                confidence="supported",
            )
        )
        stream_interface_specs.append(
            StreamInterfaceSpec(
                interface_id="IF001",
                protocol=protocol,
                data_signal="tdata",
                valid_signal="tvalid",
                ready_signal=None if protocol == "axis_valid_only" else "tready",
                last_signal="tlast" if param_by_name.get("axis_has_tlast", {}).get("value_repr") is True else None,
                producer="s_axis",
                consumer="m_axis",
                valid_condition="AxisValidOnly.transfer() returns tvalid",
                ready_backpressure_behavior="no backpressure" if protocol == "axis_valid_only" else "unknown",
                packet_boundary_behavior="tlast present" if param_by_name.get("axis_has_tlast", {}).get("value_repr") is True else "unknown",
                source_claim_ids=[f"C{claim_idx:03d}"],
                evidence_ids=list(dict.fromkeys(interface_eids)),
                confidence="supported",
            )
        )
        claim_idx += 1

    pipeline_eids = []
    for event in py_obs.pipeline_events:
        pipeline_eids.extend(event["evidence_ids"])
    if pipeline_eids:
        claims.append(
            _claim(
                claim_idx,
                "pipeline_timing_claim",
                "conditional",
                "L6 evidence contains pipeline/cycle behavior markers; exact latency is not confirmed by P1a deterministic extraction.",
                pipeline_eids,
                confidence="supported",
            )
        )
        pipeline_timing_specs.append(
            PipelineTimingSpec(
                timing_id="PT001",
                stage_or_module_id="L6_resource_opt",
                latency_cycles=None,
                register_boundaries=["S0", "S1", "S2", "S3"],
                valid_propagation="_s0_out_valid -> _s1_out_valid -> _s2_out_valid -> _s3_out_valid",
                reset_behavior="stage reset methods and AxisValidOnly.reset",
                clock_domain="modeled by step() calls",
                source_claim_ids=[f"C{claim_idx:03d}"],
                evidence_ids=list(dict.fromkeys(pipeline_eids)),
                confidence="supported",
            )
        )
        claim_idx += 1

    resource_symbols = [
        s
        for s in py_obs.symbols
        if s.role_hint == "resource_estimate"
        and (
            "resource" in s.name.lower()
            or "estimate" in s.name.lower()
            or Path(s.file_path).name.endswith("_resource_est.py")
        )
    ]
    resource_eids = [eid for s in resource_symbols for eid in s.evidence_ids]
    for estimate in py_obs.resource_estimates:
        resource_eids.extend(estimate["evidence_ids"])
    if resource_eids:
        resource_claim_id = f"C{claim_idx:03d}"
        claims.append(
            _claim(
                claim_idx,
                "resource_refinement_claim",
                "conditional",
                "L6 includes a resource estimation model for LUT/FF/DSP/BRAM usage.",
                resource_eids,
                confidence="confirmed",
            )
        )
        claim_idx += 1
        method_to_concept = {
            "estimate_s0_autocorr": "N001",
            "estimate_s1_merge": "N002",
            "estimate_s2_smooth_detect": "N003",
            "estimate_s3_cfo": "N004",
        }
        stage_estimates = [
            e
            for e in py_obs.resource_estimates
            if e["method_name"] in method_to_concept and e["estimate_kind"] in {"stage_return", "stage_return_scaled"}
        ]
        for spec_idx, estimate in enumerate(stage_estimates, start=1):
            resource_estimate_specs.append(
                ResourceEstimateSpec(
                    spec_id=f"RE{spec_idx:03d}",
                    stage_or_concept_id=method_to_concept[estimate["method_name"]],
                    estimate_name=estimate["method_name"],
                    lut=estimate.get("lut"),
                    ff=estimate.get("ff"),
                    dsp48=estimate.get("dsp"),
                    bram18k=estimate.get("bram"),
                    scale_expression=estimate.get("scale_expression"),
                    condition=estimate.get("condition"),
                    target_device="xc7z020",
                    source_claim_ids=[resource_claim_id],
                    evidence_ids=estimate["evidence_ids"],
                    confidence="supported",
                )
            )

    for view in views:
        view.resource_estimate_spec_ids = [
            spec.spec_id for spec in resource_estimate_specs if spec.stage_or_concept_id == view.concept_id
        ]

    uncertainties: list[UncertaintyNote] = []
    if not resource_eids:
        uncertainties.append(
            UncertaintyNote(
                uncertainty_id="U001",
                topic="resource refinement",
                scope="stage",
                reason="not_observed_in_p1a_evidence",
                current_interpretation="No structured resource estimate was found in mandatory L6 evidence.",
                needed_evidence="ResourceEstimate class or resource table in L6.",
            )
        )

    profile = ProjectProfile(
        project_id=project_root.name,
        name=tree["name"],
        root_path=str(project_root),
        layout_type=tree["layout_type"],
        stage_coverage=tree["stage_coverage"],
        l6_path=tree["l6_path"],
        config_paths=tree["config_paths"],
        optional_context_paths=tree["optional_context_paths"],
        evidence_ids=[],
        confidence="supported",
    )
    stage = StageNode(
        stage_id="L6_resource_opt",
        stage_name="L6 Resource Optimization",
        expected_role="resource_optimized",
        actual_role_summary="Deterministic extractor found L6 stage classes and resource/fixed-point/interface markers.",
        source_files=[str(p) for p in l6_files],
        main_entry_candidates=[s.name for s in py_obs.symbols if s.role_hint in {"pipeline_top", *[r for r, _, _ in stage_roles]}],
        selected_main_entries=[s.name for s in py_obs.symbols if s.name == "CoarseSyncPipelineL6"],
        key_concept_ids=[c.concept_id for c in concepts],
        implementation_style="fixed_point_resource_pipeline",
        evidence_ids=stage_eids,
        uncertainty_ids=[u.uncertainty_id for u in uncertainties],
        confidence="supported",
    )

    viz_nodes: list[VizNode] = []
    for concept in concepts:
        viz_nodes.append(
            VizNode(
                node_id=concept.concept_id,
                label=concept.canonical_name,
                kind="stage",
                source_concept_id=concept.concept_id,
                source_claim_ids=[
                    claim.claim_id
                    for claim in claims
                    if concept.concept_id in claim.subject_ids
                ],
                evidence_ids=concept.evidence_ids,
                confidence=concept.confidence,
            )
        )
    viz_edges: list[VizEdge] = []
    symbol_by_concept = {
        view.concept_id: view.symbol_refs[0]
        for view in views
        if view.symbol_refs
    }
    for i in range(len(viz_nodes) - 1):
        from_symbol = symbol_by_concept.get(viz_nodes[i].source_concept_id, "")
        to_symbol = symbol_by_concept.get(viz_nodes[i + 1].source_concept_id, "")
        edge_claims = dataflow_claim_ids_by_pair.get((from_symbol, to_symbol), [])
        viz_edges.append(
            VizEdge(
                edge_id=f"VE{i+1:03d}",
                from_node_id=viz_nodes[i].node_id,
                to_node_id=viz_nodes[i + 1].node_id,
                label="dataflow",
                source_claim_ids=edge_claims,
                evidence_ids=list(dict.fromkeys(viz_nodes[i].evidence_ids + viz_nodes[i + 1].evidence_ids)),
                confidence="supported",
            )
        )
    visualizations = [
        VisualizationSpec(
            viz_id="Z001",
            title="coarse_sync_glm L6 stage flow",
            viz_type="stage_flow",
            nodes=viz_nodes,
            edges=viz_edges,
        )
    ]

    diagnostics = _diagnose_claims(claims, evidence_strength)
    diagnostics.extend(_diagnose_visualization(visualizations))

    task = TaskRequest(
        request_id="p1a-coarse-sync-l6",
        workflow="UnderstandStage",
        project_root=str(project_root),
        stage_id="L6_resource_opt",
        user_intent="Explain what the L6 resource optimized stage actually implements.",
        focus=["main processing flow", "dataflow", "fixed-point", "resource refinement", "uncertainties"],
        constraints={
            "read_only_target": True,
            "forbid_rtl_confirmed_claims": True,
            "forbid_test_confirmed_claims": True,
            "forbid_vivado": True,
            "output_root": str(out_dir),
        },
    )
    return ProjectGraph(
        schema_version="p1a-0.1",
        task_request=task,
        project_profile=profile,
        stage=stage,
        concepts=concepts,
        implementation_views=views,
        fixed_point_specs=fixed_point_specs,
        stream_interface_specs=stream_interface_specs,
        pipeline_timing_specs=pipeline_timing_specs,
        resource_estimate_specs=resource_estimate_specs,
        evidence_items=evidence_items,
        candidate_claims=claims,
        grounding_diagnostics=diagnostics,
        uncertainty_notes=uncertainties,
        visualization_specs=visualizations,
        run_metadata={
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "deterministic_p1a_no_llm",
            "parameters_count": len(params),
            "source_files_read": [str(p) for p in l6_files] + [str(project_root / "config" / "parameters.py")],
        },
    )


def _diagnose_visualization(viz_specs: list[VisualizationSpec]) -> list[GroundingDiagnostic]:
    diagnostics: list[GroundingDiagnostic] = []
    did = 100
    for viz in viz_specs:
        for node in viz.nodes:
            if not node.source_claim_ids or not node.evidence_ids:
                diagnostics.append(
                    GroundingDiagnostic(
                        diagnostic_id=f"D{did:03d}",
                        target_claim_id=None,
                        target_output_id=node.node_id,
                        severity="blocking",
                        issue_type="unsupported_visual_node",
                        recommended_action="attach_claim_or_remove_node",
                        related_evidence_ids=node.evidence_ids,
                    )
                )
                did += 1
        for edge in viz.edges:
            if not edge.source_claim_ids or not edge.evidence_ids:
                diagnostics.append(
                    GroundingDiagnostic(
                        diagnostic_id=f"D{did:03d}",
                        target_claim_id=None,
                        target_output_id=edge.edge_id,
                        severity="blocking",
                        issue_type="unsupported_visual_edge",
                        recommended_action="attach_claim_or_remove_edge",
                        related_evidence_ids=edge.evidence_ids,
                    )
                )
                did += 1
    return diagnostics


def _param_int(param_by_name: dict[str, dict], name: str) -> int | None:
    value = param_by_name.get(name, {}).get("value_repr")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _q_format(q_int_bits: int | None, q_frac_bits: int | None) -> str:
    if q_int_bits is None or q_frac_bits is None:
        return "unknown"
    return f"Q({q_int_bits},{q_frac_bits})"


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _evidence_lookup(graph: ProjectGraph) -> dict[str, dict]:
    return {item.evidence_id: asdict(item) for item in graph.evidence_items}


def _build_trace_index(graph: ProjectGraph) -> dict:
    evidence_by_id = _evidence_lookup(graph)
    outputs_by_claim: dict[str, list[dict]] = {}
    outputs_by_evidence: dict[str, list[dict]] = {}

    def attach(output_id: str, output_type: str, source_claim_ids: list[str], evidence_ids: list[str]) -> None:
        output_ref = {"output_id": output_id, "output_type": output_type}
        for claim_id in source_claim_ids:
            if output_ref not in outputs_by_claim.setdefault(claim_id, []):
                outputs_by_claim[claim_id].append(output_ref)
        for evidence_id in evidence_ids:
            if output_ref not in outputs_by_evidence.setdefault(evidence_id, []):
                outputs_by_evidence[evidence_id].append(output_ref)

    stage_claim_ids = [
        claim.claim_id
        for claim in graph.candidate_claims
        if claim.claim_type == "implementation_claim" and not claim.subject_ids
    ]
    attach(graph.stage.stage_id, "stage", stage_claim_ids, graph.stage.evidence_ids)
    for concept in graph.concepts:
        source_claim_ids = [
            claim.claim_id for claim in graph.candidate_claims if concept.concept_id in claim.subject_ids
        ]
        attach(concept.concept_id, "concept", source_claim_ids, concept.evidence_ids)
    for view in graph.implementation_views:
        attach(view.view_id, "implementation_view", view.source_claim_ids, view.evidence_ids)
    for spec in graph.fixed_point_specs:
        attach(spec.spec_id, "fixed_point_spec", spec.source_claim_ids, spec.evidence_ids)
    for spec in graph.stream_interface_specs:
        attach(spec.interface_id, "stream_interface_spec", spec.source_claim_ids, spec.evidence_ids)
    for spec in graph.pipeline_timing_specs:
        attach(spec.timing_id, "pipeline_timing_spec", spec.source_claim_ids, spec.evidence_ids)
    for spec in graph.resource_estimate_specs:
        attach(spec.spec_id, "resource_estimate_spec", spec.source_claim_ids, spec.evidence_ids)
    for viz in graph.visualization_specs:
        for node in viz.nodes:
            attach(node.node_id, "visualization_node", node.source_claim_ids, node.evidence_ids)
        for edge in viz.edges:
            attach(edge.edge_id, "visualization_edge", edge.source_claim_ids, edge.evidence_ids)

    claims = {}
    for claim in graph.candidate_claims:
        claims[claim.claim_id] = {
            "claim_type": claim.claim_type,
            "claim_layer": claim.claim_layer,
            "confidence": claim.confidence,
            "statement": claim.statement,
            "subject_ids": claim.subject_ids,
            "evidence_ids": claim.evidence_ids,
            "evidence_refs": [
                evidence_by_id[eid] for eid in claim.evidence_ids if eid in evidence_by_id
            ],
            "linked_outputs": outputs_by_claim.get(claim.claim_id, []),
        }

    evidence = {}
    for evidence_id, item in evidence_by_id.items():
        evidence[evidence_id] = {
            **item,
            "supporting_claim_ids": [
                claim.claim_id for claim in graph.candidate_claims if evidence_id in claim.evidence_ids
            ],
            "linked_outputs": outputs_by_evidence.get(evidence_id, []),
        }

    return {
        "schema_version": "trace-0.1",
        "project_id": graph.project_profile.project_id,
        "stage_id": graph.stage.stage_id,
        "claims": claims,
        "evidence": evidence,
        "diagnostics": [asdict(d) for d in graph.grounding_diagnostics],
    }


def _render_trace_markdown(trace_index: dict) -> str:
    lines = [
        "# P1a Evidence Trace",
        "",
        f"Project: {trace_index['project_id']}",
        f"Stage: {trace_index['stage_id']}",
        "",
        "## Claims",
    ]
    for claim_id, claim in trace_index["claims"].items():
        lines.append(f"- {claim_id} ({claim['claim_type']}, {claim['confidence']}): {claim['statement']}")
        for evidence in claim["evidence_refs"][:4]:
            loc = f"{evidence['file_path']}:{evidence['start_line']}"
            lines.append(f"  - {evidence['evidence_id']} {loc} {evidence['excerpt_summary']}")
        if len(claim["evidence_refs"]) > 4:
            lines.append(f"  - ... {len(claim['evidence_refs']) - 4} more evidence items")
    lines.extend(["", "## Evidence With Multiple Uses"])
    reused = [
        (evidence_id, evidence)
        for evidence_id, evidence in trace_index["evidence"].items()
        if len(evidence["supporting_claim_ids"]) > 1 or len(evidence["linked_outputs"]) > 1
    ]
    if not reused:
        lines.append("- No reused evidence detected.")
    for evidence_id, evidence in reused:
        claims = ",".join(evidence["supporting_claim_ids"]) or "no-claim"
        outputs = ",".join(f"{ref['output_type']}:{ref['output_id']}" for ref in evidence["linked_outputs"]) or "no-output"
        loc = f"{evidence['file_path']}:{evidence['start_line']}"
        lines.append(f"- {evidence_id} {loc}: claims={claims}; outputs={outputs}")
    return "\n".join(lines) + "\n"


def _render_summary(graph: ProjectGraph) -> str:
    claims_by_type: dict[str, list[CandidateClaim]] = {}
    for claim in graph.candidate_claims:
        claims_by_type.setdefault(claim.claim_type, []).append(claim)

    def claim_refs(claims: list[CandidateClaim]) -> str:
        return ", ".join(c.claim_id for c in claims) or "no-claim"

    lines = [
        "# P1a Coarse Sync L6 Understanding",
        "",
        "## Stage Purpose",
        f"{graph.stage.actual_role_summary} [{claim_refs(claims_by_type.get('implementation_claim', [])[:1])}]",
        "",
        "## Main Flow",
    ]
    for concept in graph.concepts:
        refs = [
            c.claim_id
            for c in graph.candidate_claims
            if concept.concept_id in c.subject_ids
        ]
        lines.append(f"- {concept.canonical_name}: {concept.meaning} [{', '.join(refs) or 'no-claim'}]")
    lines.extend(["", "## Conditional Findings"])
    for key in ("fixed_point_claim", "interface_claim", "pipeline_timing_claim", "resource_refinement_claim"):
        for claim in claims_by_type.get(key, []):
            lines.append(f"- {claim.statement} [{claim.claim_id}]")
    if graph.fixed_point_specs:
        spec = graph.fixed_point_specs[0]
        lines.append(
            f"- Fixed-point spec: {spec.q_format}, total_bits={spec.total_bits}, scale={spec.scale} [{','.join(spec.source_claim_ids)}]"
        )
    if graph.stream_interface_specs:
        spec = graph.stream_interface_specs[0]
        lines.append(
            f"- Stream interface: {spec.protocol}, valid={spec.valid_signal}, ready={spec.ready_signal or 'none'} [{','.join(spec.source_claim_ids)}]"
        )
    if graph.pipeline_timing_specs:
        spec = graph.pipeline_timing_specs[0]
        latency = spec.latency_cycles if spec.latency_cycles is not None else "unknown"
        lines.append(
            f"- Pipeline timing: latency={latency}, valid propagation={spec.valid_propagation} [{','.join(spec.source_claim_ids)}]"
        )
    if graph.resource_estimate_specs:
        lines.append("- Resource estimates:")
        for spec in graph.resource_estimate_specs:
            scale = f", scale={spec.scale_expression}" if spec.scale_expression else ""
            condition = f", condition={spec.condition}" if spec.condition else ""
            lines.append(
                f"  - {spec.estimate_name}: LUT={spec.lut}, FF={spec.ff}, DSP48={spec.dsp48}, BRAM18K={spec.bram18k}{scale}{condition} [{','.join(spec.source_claim_ids)}]"
            )
    lines.extend(["", "## Uncertainties"])
    if graph.uncertainty_notes:
        for uncertainty in graph.uncertainty_notes:
            lines.append(f"- {uncertainty.topic}: {uncertainty.current_interpretation} [{uncertainty.uncertainty_id}]")
    else:
        lines.append("- No mandatory uncertainty was generated by the deterministic P1a runner.")
    lines.extend(["", "## Grounding Diagnostics"])
    blocking = [d for d in graph.grounding_diagnostics if d.severity == "blocking"]
    if blocking:
        for diag in blocking:
            lines.append(f"- {diag.issue_type}: {diag.message or diag.recommended_action} [{diag.diagnostic_id}]")
    else:
        lines.append("- No blocking diagnostics.")
    return "\n".join(lines) + "\n"


def _render_mermaid(graph: ProjectGraph) -> str:
    viz = graph.visualization_specs[0]
    lines = ["flowchart LR"]
    for node in viz.nodes:
        label = f"{node.label}\\n{','.join(node.source_claim_ids) or 'no-claim'}"
        lines.append(f'  {node.node_id}["{label}"]')
    for edge in viz.edges:
        label = f"{edge.label} {','.join(edge.source_claim_ids[:2])}"
        lines.append(f"  {edge.from_node_id} -->|{label}| {edge.to_node_id}")
    return "\n".join(lines) + "\n"


def run_p1a(project_root: Path = DEFAULT_PROJECT, out_dir: Path = DEFAULT_OUT) -> ProjectGraph:
    project_root = project_root.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    graph = _build_graph(project_root, out_dir)
    trace_index = _build_trace_index(graph)
    _write_json(out_dir / "project_graph.json", graph.to_dict())
    _write_json(out_dir / "trace_index.json", trace_index)
    (out_dir / "summary.md").write_text(_render_summary(graph), encoding="utf-8")
    (out_dir / "flow.mmd").write_text(_render_mermaid(graph), encoding="utf-8")
    (out_dir / "trace.md").write_text(_render_trace_markdown(trace_index), encoding="utf-8")
    _write_json(
        out_dir / "run_metadata.json",
        {
            **graph.run_metadata,
            "output_files": ["project_graph.json", "trace_index.json", "summary.md", "flow.mmd", "trace.md"],
            "blocking_diagnostics": [
                asdict(d) for d in graph.grounding_diagnostics if d.severity == "blocking"
            ],
        },
    )
    return graph
