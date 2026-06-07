"""Grounded query helpers for generated P1a artifacts."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any


def answer_question(artifact_dir: Path, question: str) -> str:
    """Answer a narrow P1a question from ProjectGraph and TraceIndex.

    This is intentionally deterministic. It is the first interaction shell for
    the future Agent runtime, not a semantic replacement for an LLM.
    """

    graph, trace = _load_artifacts(artifact_dir)
    freshness = check_freshness(artifact_dir)
    normalized = question.lower()

    claim_id = _extract_claim_id(question)
    if claim_id:
        return _with_freshness(_answer_claim(trace, claim_id), freshness)

    evidence_id = _extract_evidence_id(question)
    if evidence_id:
        return _with_freshness(_answer_evidence(trace, evidence_id), freshness)

    if _has_any(normalized, ["resource", "lut", "ff", "dsp", "bram", "资源"]):
        return _with_freshness(_answer_resource(graph, trace), freshness)
    if _has_any(normalized, ["fixed", "q(", "q格式", "定点", "位宽", "scale"]):
        return _with_freshness(_answer_fixed_point(graph, trace), freshness)
    if _has_any(normalized, ["interface", "axis", "valid", "ready", "tvalid", "接口"]):
        return _with_freshness(_answer_interface(graph, trace), freshness)
    if _has_any(normalized, ["pipeline", "latency", "cycle", "时序", "延迟", "valid propagation"]):
        return _with_freshness(_answer_pipeline(graph, trace), freshness)
    if _has_any(normalized, ["flow", "dataflow", "stage", "流程", "实现了什么", "主线", "s0", "s1", "s2", "s3"]):
        return _with_freshness(_answer_flow(graph, trace), freshness)

    return _with_freshness(_answer_topics(graph), freshness)


def check_freshness(artifact_dir: Path) -> dict[str, Any]:
    manifest_path = artifact_dir / "memory_manifest.json"
    if not manifest_path.exists():
        return {
            "status": "unknown",
            "reason": "missing_memory_manifest",
            "stale_files": [],
            "missing_files": [],
            "source_snapshot_id": None,
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale_files = []
    missing_files = []
    for source in manifest.get("source_files", []):
        path = Path(source["file_path"])
        if not path.exists():
            missing_files.append(source["file_path"])
            continue
        current_hash = _sha256(path)
        if current_hash != source.get("sha256"):
            stale_files.append(
                {
                    "file_path": source["file_path"],
                    "expected_sha256": source.get("sha256"),
                    "current_sha256": current_hash,
                }
            )
    status = "current"
    reason = "source_snapshot_matches"
    if missing_files or stale_files:
        status = "stale"
        reason = "source_snapshot_changed"
    return {
        "status": status,
        "reason": reason,
        "stale_files": stale_files,
        "missing_files": missing_files,
        "source_snapshot_id": manifest.get("source_snapshot_id"),
        "created_at": manifest.get("created_at"),
    }


def _load_artifacts(artifact_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    graph_path = artifact_dir / "project_graph.json"
    trace_path = artifact_dir / "trace_index.json"
    if not graph_path.exists():
        raise FileNotFoundError(f"missing project graph: {graph_path}")
    if not trace_path.exists():
        raise FileNotFoundError(f"missing trace index: {trace_path}")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    return graph, trace


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _with_freshness(answer: str, freshness: dict[str, Any]) -> str:
    if freshness["status"] == "current":
        return answer
    if freshness["status"] == "unknown":
        warning = (
            "# Freshness Warning\n\n"
            "Artifact freshness is unknown because `memory_manifest.json` is missing. "
            "Treat grounded answers as reusable only after regenerating P1a artifacts.\n\n"
        )
        return warning + answer
    changed = len(freshness.get("stale_files", [])) + len(freshness.get("missing_files", []))
    warning = (
        "# Freshness Warning\n\n"
        f"Artifacts are stale: {changed} source file(s) changed or disappeared since snapshot "
        f"`{freshness.get('source_snapshot_id')}`. Regenerate P1a before using confirmed claims.\n\n"
    )
    return warning + answer


def _extract_claim_id(text: str) -> str | None:
    match = re.search(r"\bC\d{3}\b", text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_evidence_id(text: str) -> str | None:
    match = re.search(r"E:[A-Za-z0-9_]+:[A-Fa-f0-9]+:\d+-\d+:\d{3}", text)
    return match.group(0) if match else None


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _answer_claim(trace: dict[str, Any], claim_id: str) -> str:
    claim = trace["claims"].get(claim_id)
    if claim is None:
        return f"# Query Answer\n\nClaim `{claim_id}` was not found in the trace index.\n"
    lines = [
        "# Query Answer",
        "",
        f"Claim `{claim_id}` is `{claim['confidence']}`.",
        "",
        claim["statement"],
        "",
        "## Linked Outputs",
    ]
    if claim["linked_outputs"]:
        for output in claim["linked_outputs"]:
            lines.append(f"- {output['output_type']} `{output['output_id']}`")
    else:
        lines.append("- No linked output recorded.")
    lines.extend(["", "## Evidence"])
    lines.extend(_format_evidence_refs(claim["evidence_refs"]))
    return "\n".join(lines) + "\n"


def _answer_evidence(trace: dict[str, Any], evidence_id: str) -> str:
    evidence = trace["evidence"].get(evidence_id)
    if evidence is None:
        return f"# Query Answer\n\nEvidence `{evidence_id}` was not found in the trace index.\n"
    lines = [
        "# Query Answer",
        "",
        f"Evidence `{evidence_id}` is from `{evidence['source_type']}`.",
        "",
        f"- Location: `{evidence['file_path']}:{evidence['start_line']}`",
        f"- Symbol: `{evidence['symbol']}`",
        f"- Strength: `{evidence['evidence_strength']}`",
        f"- Summary: {evidence['excerpt_summary']}",
        "",
        "## Supports",
    ]
    claim_ids = evidence.get("supporting_claim_ids", [])
    if claim_ids:
        lines.append(f"- Claims: {', '.join(claim_ids)}")
    else:
        lines.append("- Claims: none")
    outputs = evidence.get("linked_outputs", [])
    if outputs:
        for output in outputs:
            lines.append(f"- {output['output_type']} `{output['output_id']}`")
    else:
        lines.append("- Outputs: none")
    return "\n".join(lines) + "\n"


def _answer_flow(graph: dict[str, Any], trace: dict[str, Any]) -> str:
    lines = [
        "# Query Answer",
        "",
        f"`{graph['stage']['stage_id']}` is represented as:",
        "",
    ]
    for concept in graph["concepts"]:
        claim_ids = _claim_ids_for_subject(trace, concept["concept_id"])
        refs = f" [{', '.join(claim_ids)}]" if claim_ids else ""
        lines.append(f"- {concept['canonical_name']}: {concept['meaning']}{refs}")
    lines.extend(["", "## Evidence"])
    for claim_id, claim in trace["claims"].items():
        if claim_id == "C001" or claim["claim_type"] in {"dataflow_claim", "implementation_order_claim"}:
            lines.append(f"- `{claim_id}`: {claim['statement']}")
    return "\n".join(lines) + "\n"


def _answer_resource(graph: dict[str, Any], trace: dict[str, Any]) -> str:
    lines = ["# Query Answer", "", "Resource estimates observed in P1a:"]
    for spec in graph["resource_estimate_specs"]:
        scale = f", scale={spec['scale_expression']}" if spec.get("scale_expression") else ""
        condition = f", condition={spec['condition']}" if spec.get("condition") else ""
        claim_ids = ", ".join(spec["source_claim_ids"])
        lines.append(
            f"- `{spec['estimate_name']}`: LUT={spec['lut']}, FF={spec['ff']}, "
            f"DSP48={spec['dsp48']}, BRAM18K={spec['bram18k']}{scale}{condition} [{claim_ids}]"
        )
    lines.extend(["", "## Evidence"])
    claim = _first_claim_by_type(trace, "resource_refinement_claim")
    lines.extend(_format_evidence_refs(claim["evidence_refs"] if claim else []))
    return "\n".join(lines) + "\n"


def _answer_fixed_point(graph: dict[str, Any], trace: dict[str, Any]) -> str:
    lines = ["# Query Answer", "", "Fixed-point observations:"]
    for spec in graph["fixed_point_specs"]:
        claim_ids = ", ".join(spec["source_claim_ids"])
        lines.append(
            f"- `{spec['q_format']}` signed={spec['signedness']}, total_bits={spec['total_bits']}, "
            f"integer_bits={spec['integer_bits']}, fractional_bits={spec['fractional_bits']}, "
            f"scale={spec['scale']}, rounding={spec['rounding_mode']}, overflow={spec['overflow_mode']} [{claim_ids}]"
        )
    lines.extend(["", "## Evidence"])
    claim = _first_claim_by_type(trace, "fixed_point_claim")
    lines.extend(_format_evidence_refs(claim["evidence_refs"] if claim else []))
    return "\n".join(lines) + "\n"


def _answer_interface(graph: dict[str, Any], trace: dict[str, Any]) -> str:
    lines = ["# Query Answer", "", "Stream interface observations:"]
    for spec in graph["stream_interface_specs"]:
        claim_ids = ", ".join(spec["source_claim_ids"])
        ready = spec["ready_signal"] or "none"
        last = spec["last_signal"] or "none"
        lines.append(
            f"- protocol={spec['protocol']}, data={spec['data_signal']}, valid={spec['valid_signal']}, "
            f"ready={ready}, last={last}, behavior={spec['ready_backpressure_behavior']} [{claim_ids}]"
        )
    lines.extend(["", "## Evidence"])
    claim = _first_claim_by_type(trace, "interface_claim")
    lines.extend(_format_evidence_refs(claim["evidence_refs"] if claim else []))
    return "\n".join(lines) + "\n"


def _answer_pipeline(graph: dict[str, Any], trace: dict[str, Any]) -> str:
    lines = ["# Query Answer", "", "Pipeline timing observations:"]
    for spec in graph["pipeline_timing_specs"]:
        latency = spec["latency_cycles"] if spec["latency_cycles"] is not None else "unknown"
        claim_ids = ", ".join(spec["source_claim_ids"])
        valid_propagation = spec["valid_propagation"] or "unknown"
        lines.append(
            f"- latency={latency}, register_boundaries={','.join(spec['register_boundaries'])}, "
            f"valid_propagation={valid_propagation} [{claim_ids}]"
        )
    lines.append("")
    lines.append("Exact latency is not confirmed by the deterministic P1a extraction.")
    lines.extend(["", "## Evidence"])
    claim = _first_claim_by_type(trace, "pipeline_timing_claim")
    lines.extend(_format_evidence_refs(claim["evidence_refs"] if claim else []))
    return "\n".join(lines) + "\n"


def _answer_topics(graph: dict[str, Any]) -> str:
    concepts = ", ".join(c["canonical_name"] for c in graph["concepts"])
    return (
        "# Query Answer\n\n"
        "This deterministic P1a query shell can answer grounded questions about:\n\n"
        f"- stage flow: {concepts}\n"
        "- fixed-point/Q format\n"
        "- stream interface\n"
        "- pipeline timing\n"
        "- resource estimates\n"
        "- specific claim ids such as `C001`\n"
        "- specific evidence ids from `trace_index.json`\n"
    )


def _claim_ids_for_subject(trace: dict[str, Any], subject_id: str) -> list[str]:
    return [
        claim_id
        for claim_id, claim in trace["claims"].items()
        if subject_id in claim.get("subject_ids", [])
    ]


def _first_claim_by_type(trace: dict[str, Any], claim_type: str) -> dict[str, Any] | None:
    for claim in trace["claims"].values():
        if claim["claim_type"] == claim_type:
            return claim
    return None


def _format_evidence_refs(evidence_refs: list[dict[str, Any]], limit: int = 6) -> list[str]:
    if not evidence_refs:
        return ["- No evidence refs recorded."]
    lines = []
    for evidence in evidence_refs[:limit]:
        loc = f"{evidence['file_path']}:{evidence['start_line']}"
        lines.append(f"- `{evidence['evidence_id']}` `{loc}` {evidence['excerpt_summary']}")
    if len(evidence_refs) > limit:
        lines.append(f"- ... {len(evidence_refs) - limit} more evidence items")
    return lines
