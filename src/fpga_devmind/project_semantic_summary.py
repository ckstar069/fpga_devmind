"""Project Semantic Summary builder (T038).

Builds a structured semantic understanding of an FPGA project from existing
T037 artifacts (graph, index, candidates, eval) without calling any LLM.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_discovery import ConceptCandidate, DiscoveryResult


def build_semantic_summary(
    project_root: Path,
    project_graph: dict[str, Any],
    project_index: dict[str, Any],
    run_metadata: dict[str, Any],
    candidates: list[ConceptCandidate],
    eval_result: dict[str, Any] | None,
    traced_concepts: list[str] | None = None,
) -> dict[str, Any]:
    """Build deterministic semantic summary from existing artifacts.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    project_graph : dict
        The project_understanding_graph.json content.
    project_index : dict
        The project_understanding_index.json content.
    run_metadata : dict
        The run_metadata.json content.
    candidates : list[ConceptCandidate]
        All discovered concept candidates.
    eval_result : dict | None
        The discovery_eval_result.json content, or None.
    traced_concepts : list[str] | None
        Authoritative canonical concept names (post-golden canonicalisation).
        When provided, ``core_concepts`` is built from this list rather than
        the raw ``is_selected`` flag on candidates.

    Returns
    -------
    dict
        Semantic summary matching schema_version "project-semantic-summary-0.1".
    """
    project_id = project_root.name or "project"

    # --- Top level purpose ---
    golden_core = []
    if eval_result:
        golden_core = eval_result.get("matched_core", []) + eval_result.get("missed_core", [])
    top_purpose = _infer_top_level_purpose(project_id, golden_core, project_graph)

    # --- Pipeline stages ---
    stages = _extract_pipeline_stages(project_graph, project_index)

    # --- Core concepts ---
    core_concepts = _build_core_concepts(
        candidates, project_index, eval_result, traced_concepts
    )

    # --- Implementation modules ---
    impl_modules = _build_implementation_modules(project_graph, project_index)

    # --- Dataflow ---
    dataflow = _build_dataflow_summary(project_graph)

    # --- Evidence quality ---
    ev_quality = _build_evidence_quality_summary(project_index)

    # --- Uncertainty ---
    uncertainty = _build_uncertainty_summary(project_graph, project_index)

    # --- Test coverage ---
    test_cov = _build_test_coverage_summary(project_root, project_index, core_concepts)

    return {
        "schema_version": "project-semantic-summary-0.1",
        "project_id": project_id,
        "project_root": str(project_root),
        "project_kind_hint": _infer_project_kind(project_id, golden_core),
        "top_level_purpose": top_purpose,
        "pipeline_stages": stages,
        "core_concepts": core_concepts,
        "implementation_modules": impl_modules,
        "dataflow_summary": dataflow,
        "evidence_quality_summary": ev_quality,
        "uncertainty_summary": uncertainty,
        "test_coverage_summary": test_cov,
        "source_provenance": {
            "summary_generated_from": [
                "project_understanding_graph.json",
                "project_understanding_index.json",
                "concept_candidates.json",
            ] + (["discovery_eval_result.json"] if eval_result else []),
            "generation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "generator": "fpga_devmind.project_semantic_summary",
        },
    }


# ---------------------------------------------------------------------------
# Top-level purpose
# ---------------------------------------------------------------------------

_PROJECT_PURPOSE_MAP: dict[str, str] = {
    "coarse": "OFDM coarse time and frequency synchronization module",
    "fine_cfo": "Fine carrier frequency offset (CFO) estimation and correction",
    "fft": "Fast Fourier Transform (FFT/DFT) computation engine with butterfly architecture",
    "cordic": "CORDIC iterative rotation/vectoring algorithm implementation",
    "ldpc": "Low-Density Parity-Check (LDPC) encoder/decoder",
    "agc": "Automatic Gain Control (AGC) loop",
    "peak": "Peak detection and index estimation",
    "sync": "Symbol timing and frame synchronization",
}


def _infer_top_level_purpose(
    project_id: str, golden_core: list[str], project_graph: dict[str, Any]
) -> str:
    """Infer project purpose from name, golden concepts, and file structure."""
    pid_lower = project_id.lower()

    # Direct project-name match
    for key, desc in _PROJECT_PURPOSE_MAP.items():
        if key in pid_lower:
            return desc

    # Golden core concept hint
    if golden_core:
        core_lower = " ".join(golden_core).lower()
        if "fft" in core_lower or "butterfly" in core_lower or "twiddle" in core_lower:
            return "FFT/DFT computation engine"
        if "cfo" in core_lower or "frequency" in core_lower:
            return "Carrier frequency offset estimation and correction module"
        if "peak" in core_lower or "sync" in core_lower or "autocorr" in core_lower:
            return "OFDM synchronization and peak detection module"
        if "cordic" in core_lower:
            return "CORDIC algorithm implementation"

    # File structure hint
    nodes = project_graph.get("nodes", [])
    labels = " ".join(n.get("label", "") for n in nodes).lower()
    if "fft" in labels or "butterfly" in labels:
        return "FFT/DFT signal processing module"
    if "cfo" in labels or "cordic" in labels:
        return "Frequency estimation and correction module"
    if "peak" in labels or "sync" in labels:
        return "Synchronization and detection module"

    return "FPGA signal processing module"


def _infer_project_kind(project_id: str, golden_core: list[str]) -> str:
    """Infer broad project kind for categorization."""
    pid = project_id.lower()
    if "fft" in pid:
        return "FFT/DFT engine"
    if "cfo" in pid or "fine" in pid:
        return "Frequency estimation"
    if "sync" in pid or "coarse" in pid:
        return "OFDM synchronization"
    if "cordic" in pid:
        return "CORDIC algorithm"
    if "ldpc" in pid:
        return "Error correction"
    if golden_core:
        gc = " ".join(golden_core).lower()
        if "fft" in gc:
            return "FFT/DFT engine"
        if "cfo" in gc or "freq" in gc:
            return "Frequency estimation"
        if "sync" in gc:
            return "OFDM synchronization"
    return "FPGA DSP module"


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def _extract_pipeline_stages(
    project_graph: dict[str, Any], project_index: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract pipeline stages from file structure and concept mapping."""
    stages: list[dict[str, Any]] = []
    file_index = project_index.get("file_index", {})
    evidence_index = project_index.get("evidence_index", {})

    # Group files by stage directory
    stage_files: dict[str, list[str]] = {}
    for fp in file_index:
        if "L5_fixedpoint" in fp:
            stage_files.setdefault("L5_fixedpoint", []).append(fp)
        elif "L6_resource_opt" in fp:
            stage_files.setdefault("L6_resource_opt", []).append(fp)
        elif "/rtl/" in fp or fp.endswith(".v") or fp.endswith(".sv"):
            stage_files.setdefault("RTL", []).append(fp)
        elif "test" in fp.lower():
            stage_files.setdefault("tests", []).append(fp)

    stage_labels = {
        "L5_fixedpoint": ("L5_fixedpoint", "Fixed-point Python model"),
        "L6_resource_opt": ("L6_resource_opt", "Resource-optimized Python model"),
        "RTL": ("RTL", "Verilog/SystemVerilog implementation"),
        "tests": ("tests", "Testbench and validation"),
    }

    for stage_id, files in stage_files.items():
        sid, label = stage_labels.get(stage_id, (stage_id, stage_id))
        # Find related concepts and RTL modules
        related_concepts = set()
        related_rtl = set()
        evidence_ids = []
        for fp in files:
            for concept in file_index.get(fp, []):
                related_concepts.add(concept)
            for eid, ev in evidence_index.items():
                if ev.get("file_path") == fp:
                    evidence_ids.append(eid)
                    sym = ev.get("symbol", "")
                    if sym:
                        related_rtl.add(sym)

        stages.append({
            "stage_id": sid,
            "label": label,
            "role": f"{len(files)} source files, {len(related_concepts)} related concepts",
            "source_files": sorted(files)[:10],
            "related_concepts": sorted(related_concepts),
            "related_rtl_modules": sorted(related_rtl)[:10],
            "confidence": "supported" if len(files) > 0 else "unknown",
            "evidence_ids": evidence_ids[:20],
        })

    # Sort: L5 -> L6 -> RTL -> tests
    order = {"L5_fixedpoint": 0, "L6_resource_opt": 1, "RTL": 2, "tests": 3}
    stages.sort(key=lambda s: order.get(s["stage_id"], 99))
    return stages


# ---------------------------------------------------------------------------
# Core concepts
# ---------------------------------------------------------------------------


def _build_core_concepts(
    candidates: list[ConceptCandidate],
    project_index: dict[str, Any],
    eval_result: dict[str, Any] | None,
    traced_concepts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build enriched core concept list from candidates.

    When ``traced_concepts`` is provided it is treated as the authoritative
    canonical-name list (post-golden canonicalization).  Each entry is
    resolved against the candidate pool so that metadata such as evidence
    counts can be attached.
    """
    concept_index = project_index.get("concept_index", {})
    evidence_chain = project_index.get("evidence_chain", {})

    # Build golden alias map for canonicalization
    golden_aliases: dict[str, str] = {}
    if eval_result:
        for detail in eval_result.get("details", []):
            sel = detail.get("selected_name", "")
            matched = detail.get("matched_golden_concept", "")
            if sel and matched:
                golden_aliases[sel.lower()] = matched

    # Index candidates by normalised name for O(1) lookup
    cand_by_norm: dict[str, ConceptCandidate] = {}
    for c in candidates:
        cand_by_norm[c.name.lower()] = c
        if c.canonical_name:
            cand_by_norm[c.canonical_name.lower()] = c
        for a in (c.aliases or []):
            cand_by_norm[a.lower()] = c

    # Determine which canonical names to emit
    names_to_emit: list[str] = []
    if traced_concepts:
        names_to_emit = traced_concepts
    else:
        # Fallback: use selected candidates (legacy path)
        names_to_emit = [
            golden_aliases.get(c.name.lower(), c.canonical_name or c.name)
            for c in candidates
            if c.is_selected
        ]
        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for n in names_to_emit:
            if n not in seen:
                seen.add(n)
                deduped.append(n)
        names_to_emit = deduped

    core: list[dict[str, Any]] = []
    for canonical in names_to_emit:
        norm = canonical.lower()
        c = cand_by_norm.get(norm)

        # Resolve concept-index and evidence-chain keys.
        # Prefer the candidate's original name when available so that
        # downstream indexes line up.
        lookup_name = c.name if c else canonical
        ci = concept_index.get(lookup_name, {})
        chain = evidence_chain.get(lookup_name, {})

        if c:
            category = _refine_concept_category(c, golden_aliases)
            aliases = c.aliases
            role = c.semantic_role or "algorithm"
            why = c.selection_reason or f"Score {c.score}, category {c.category}"
        else:
            # Inferred concept with no direct candidate (e.g. golden-only)
            category = "algorithm"
            aliases = []
            role = "algorithm"
            why = "Inferred from golden spec or canonicalization"

        display = _display_name(canonical)

        core.append({
            "canonical_name": canonical,
            "display_name": display,
            "category": category,
            "role_in_project": role,
            "why_selected": why,
            "aliases": aliases,
            "l5_l6_evidence_count": ci.get("l5_count", 0) + ci.get("l6_count", 0),
            "rtl_evidence_count": ci.get("rtl_objects", 0),
            "test_evidence_count": ci.get("test_count", 0),
            "confidence": ci.get("status", "unknown") == "ok" and "supported" or "inferred",
            "limitations": chain.get("missing", []),
        })

    return core


def _refine_concept_category(
    c: ConceptCandidate, golden_aliases: dict[str, str]
) -> str:
    """Refine concept category for display purposes."""
    # Golden-matched core concepts
    if c.name.lower() in golden_aliases:
        return "algorithm"

    # Interface patterns
    if c.name.lower() in {"axis", "axi", "valid", "ready", "data", "addr", "fifo"}:
        return "interface"

    # Parameter patterns
    if c.category == "parameter_like" or re.match(r"^(n_|num_|log2_|pipe_|rom_|denom_|frac_|int_)", c.name):
        return "parameter"

    # Implementation detail
    if c.category in {"generic_variable", "framework_artifact"}:
        return "implementation_detail"

    # Test-only
    if c.category == "test_artifact":
        return "test_only"

    # Default based on cross-stage presence
    if "L5_fixedpoint" in c.source_sections or "L6_resource_opt" in c.source_sections:
        if "RTL" in c.source_sections:
            return "algorithm"
        return "stage"
    if "RTL" in c.source_sections:
        return "algorithm"

    return "unknown"


def _display_name(canonical: str) -> str:
    """Convert canonical name to user-friendly display name."""
    # Specific known mappings
    mapping = {
        "peak_idx": "Peak Index Detection",
        "smooth_detect": "Smooth Detection",
        "autocorr_norm": "Normalized Autocorrelation",
        "merge_stage": "Merge Stage",
        "estimate_s3_cfo": "S3 CFO Estimate",
        "denom_bits": "Denominator Bits",
        "energy_cnt": "Energy Counter",
        "cmpy_dsp48": "Complex Multiply (DSP48)",
        "fine_cfo": "Fine CFO Estimation",
        "first_path": "First Path Detection",
        "fpd": "First Path Detection",
        "lts": "Long Training Symbol",
        "sts": "Short Training Symbol",
        "bit_reverse": "Bit-Reversal Permutation",
        "dft_axis": "DFT Axis",
        "dropped_bit": "Dropped Bit",
        "core_l4": "Core L4",
        "axis_interface": "AXI Stream Interface",
        "rom_addr": "ROM Address",
        "pipeline": "Pipeline Stage",
    }
    if canonical.lower() in mapping:
        return mapping[canonical.lower()]

    # Generic: title-case with underscores as spaces
    return canonical.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Implementation modules
# ---------------------------------------------------------------------------


def _build_implementation_modules(
    project_graph: dict[str, Any], project_index: dict[str, Any]
) -> list[dict[str, Any]]:
    """Aggregate RTL modules with concept and evidence info."""
    nodes = project_graph.get("nodes", [])
    edges = project_graph.get("edges", [])
    rtl_object_index = project_index.get("rtl_object_index", {})
    evidence_index = project_index.get("evidence_index", {})

    modules: list[dict[str, Any]] = []
    for node in nodes:
        kind = node.get("kind", "")
        if not kind.startswith("rtl_"):
            continue

        label = node.get("label", "")
        fp = node.get("file_path", "")
        node_id = node.get("node_id", "")

        # Find concepts that reference this RTL
        concepts = rtl_object_index.get(label, [])

        # Find claims connected to this node
        claims = []
        for edge in edges:
            if edge.get("to_node_id") == node_id and edge.get("edge_type") == "realizes":
                from_id = edge.get("from_node_id", "")
                if "PUG_CLAIM_" in from_id:
                    claims.append(from_id)

        # Count evidence strength
        strong = 0
        medium = 0
        weak = 0
        for eid, ev in evidence_index.items():
            if ev.get("symbol") == label or ev.get("file_path") == fp:
                strength = ev.get("strength", "")
                if strength == "strong":
                    strong += 1
                elif strength == "medium":
                    medium += 1
                else:
                    weak += 1

        modules.append({
            "module_or_file": label or fp,
            "role_hint": _rtl_role_hint(label, fp),
            "concepts_realized": concepts,
            "claims": claims,
            "strong_evidence_count": strong,
            "medium_evidence_count": medium,
            "weak_evidence_count": weak,
            "is_shared_by_multiple_concepts": len(concepts) > 1,
        })

    return modules


def _rtl_role_hint(label: str, file_path: str) -> str:
    """Infer RTL module role from name and path."""
    name = (label or file_path).lower()
    if "test" in name or "tb" in name:
        return "testbench"
    if "top" in name:
        return "top-level wrapper"
    if "ctrl" in name or "control" in name:
        return "control logic"
    if "mem" in name or "rom" in name or "ram" in name:
        return "memory/storage"
    if "arith" in name or "mul" in name or "add" in name:
        return "arithmetic unit"
    return "RTL implementation module"


# ---------------------------------------------------------------------------
# Dataflow summary
# ---------------------------------------------------------------------------


def _build_dataflow_summary(project_graph: dict[str, Any]) -> dict[str, Any]:
    """Build simplified dataflow from project graph."""
    nodes = project_graph.get("nodes", [])
    edges = project_graph.get("edges", [])

    df_nodes = []
    df_edges = []

    for node in nodes:
        kind = node.get("kind", "")
        if kind not in {"project", "concept", "mapping_claim"} and not kind.startswith("rtl_"):
            continue
        df_nodes.append({
            "id": node.get("node_id", ""),
            "label": node.get("label", ""),
            "kind": kind,
        })

    for edge in edges:
        etype = edge.get("edge_type", "")
        conf = edge.get("confidence", "inferred")
        notes = edge.get("notes", "")
        df_edges.append({
            "from": edge.get("from_node_id", ""),
            "to": edge.get("to_node_id", ""),
            "type": etype,
            "confidence": conf,
            "inferred": conf == "inferred" or "inferred" in notes.lower(),
        })

    return {"nodes": df_nodes, "edges": df_edges}


# ---------------------------------------------------------------------------
# Evidence quality
# ---------------------------------------------------------------------------


def _build_evidence_quality_summary(project_index: dict[str, Any]) -> dict[str, int]:
    """Count evidence by quality tier."""
    evidence_index = project_index.get("evidence_index", {})
    strong = 0
    medium = 0
    weak = 0
    inferred = 0

    for ev in evidence_index.values():
        st = ev.get("strength", "")
        src = ev.get("source_type", "")
        if st == "strong":
            strong += 1
        elif st == "medium":
            medium += 1
        elif st == "weak" or src == "naming_match":
            weak += 1
        else:
            inferred += 1

    return {
        "strong_direct": strong,
        "medium_structural": medium,
        "weak_name_only": weak,
        "inferred": inferred,
    }


# ---------------------------------------------------------------------------
# Uncertainty summary
# ---------------------------------------------------------------------------


def _build_uncertainty_summary(
    project_graph: dict[str, Any], project_index: dict[str, Any]
) -> dict[str, Any]:
    """Summarize all uncertainty and weak evidence areas."""
    nodes = project_graph.get("nodes", [])
    edges = project_graph.get("edges", [])
    evidence_chain = project_index.get("evidence_chain", {})

    inferred_claims = []
    weak_only = []
    naming_only = []
    missing_l5l6 = []
    missing_rtl = []
    missing_test = []

    for node in nodes:
        if node.get("kind") == "mapping_claim" and node.get("confidence") == "inferred":
            inferred_claims.append(node.get("label", ""))

    for concept, chain in evidence_chain.items():
        l5 = chain.get("l5_l6_evidence", [])
        rtl = chain.get("rtl_evidence", [])
        test = chain.get("test_evidence", [])

        if not l5:
            missing_l5l6.append(concept)
        if not rtl:
            missing_rtl.append(concept)
        if not test:
            missing_test.append(concept)

        # Check if only weak evidence
        all_ev = l5 + rtl + test
        if all_ev and all(e.get("strength") in ("weak", "") for e in all_ev):
            weak_only.append(concept)

    # Naming-only edges
    for edge in edges:
        if edge.get("edge_type") == "shares_file" or "naming" in edge.get("notes", "").lower():
            naming_only.append(edge.get("edge_id", ""))

    return {
        "inferred_claims": inferred_claims,
        "weak_only_links": weak_only,
        "naming_only_links": naming_only,
        "missing_l5_l6": missing_l5l6,
        "missing_rtl": missing_rtl,
        "missing_test_evidence": missing_test,
    }


# ---------------------------------------------------------------------------
# Test coverage
# ---------------------------------------------------------------------------


def _build_test_coverage_summary(
    project_root: Path,
    project_index: dict[str, Any],
    core_concepts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Scan test files and match against concepts."""
    test_dir = project_root / "tests"
    test_files = []
    if test_dir.is_dir():
        test_files = sorted(
            p for p in test_dir.rglob("*.py")
            if p.is_file() and not p.name.startswith("__")
        )

    # Extract test symbols from test files
    test_symbols: set[str] = set()
    test_asserts: list[str] = []
    for tf in test_files:
        try:
            content = tf.read_text(encoding="utf-8", errors="ignore")
            # Function names
            for m in re.finditer(r"def\s+(test_\w+)", content):
                test_symbols.add(m.group(1))
            # Class names
            for m in re.finditer(r"class\s+(\w+)", content):
                test_symbols.add(m.group(1))
            # Assert strings
            for m in re.finditer(r'assert\s+.*?["\']([^"\']+)["\']', content):
                test_asserts.append(m.group(1))
        except Exception:
            pass

    # Match concepts against test symbols
    per_concept = []
    concepts_with_match = 0
    for cc in core_concepts:
        cname = cc["canonical_name"]
        matched = []
        status = "no_test_files"

        if test_files:
            for sym in test_symbols:
                sym_lower = sym.lower()
                if cname.lower() in sym_lower or any(
                    a.lower() in sym_lower for a in cc.get("aliases", [])
                ):
                    matched.append(sym)
            if matched:
                status = "test_name_match"
                concepts_with_match += 1
            else:
                # Check assert hints
                for assert_str in test_asserts:
                    if cname.lower() in assert_str.lower():
                        status = "test_assert_or_behavior_hint"
                        matched.append(f"assert: {assert_str[:40]}")
                        break
                if status == "no_test_files":
                    status = "test_files_exist_but_no_alias_match"

        per_concept.append({
            "concept": cname,
            "test_files_present": len(test_files) > 0,
            "matched_test_symbols": matched[:10],
            "matched_test_names": [sym for sym in matched if sym.startswith("test_")][:10],
            "test_evidence_status": status,
        })

    return {
        "test_files_present": len(test_files) > 0,
        "total_test_files": len(test_files),
        "concepts_with_test_match": concepts_with_match,
        "concepts_without_test_match": len(core_concepts) - concepts_with_match,
        "per_concept": per_concept,
    }
