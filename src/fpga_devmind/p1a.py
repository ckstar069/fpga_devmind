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
    GroundingDiagnostic,
    ImplementationView,
    ProjectGraph,
    ProjectProfile,
    StageNode,
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

    # Fixed-point and interface/resource claims are conditional.
    q_eids = []
    for event in py_obs.q_operations + py_obs.width_growth_events:
        q_eids.extend(event["evidence_ids"])
    if q_eids:
        claims.append(
            _claim(
                claim_idx,
                "fixed_point_claim",
                "conditional",
                "L6 evidence contains fixed-point/Q-format behavior markers.",
                q_eids,
                confidence="supported",
            )
        )
        claim_idx += 1

    interface_eids = []
    for event in py_obs.interface_events:
        interface_eids.extend(event["evidence_ids"])
    if interface_eids:
        claims.append(
            _claim(
                claim_idx,
                "interface_claim",
                "conditional",
                "L6 evidence contains valid-only stream interface markers.",
                interface_eids,
                confidence="supported",
            )
        )
        claim_idx += 1

    resource_symbols = [s for s in py_obs.symbols if s.role_hint == "resource_estimate"]
    resource_eids = [eid for s in resource_symbols for eid in s.evidence_ids]
    if resource_eids:
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


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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
    for key in ("fixed_point_claim", "interface_claim", "resource_refinement_claim"):
        for claim in claims_by_type.get(key, []):
            lines.append(f"- {claim.statement} [{claim.claim_id}]")
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
    _write_json(out_dir / "project_graph.json", graph.to_dict())
    (out_dir / "summary.md").write_text(_render_summary(graph), encoding="utf-8")
    (out_dir / "flow.mmd").write_text(_render_mermaid(graph), encoding="utf-8")
    _write_json(
        out_dir / "run_metadata.json",
        {
            **graph.run_metadata,
            "output_files": ["project_graph.json", "summary.md", "flow.mmd"],
            "blocking_diagnostics": [
                asdict(d) for d in graph.grounding_diagnostics if d.severity == "blocking"
            ],
        },
    )
    return graph
