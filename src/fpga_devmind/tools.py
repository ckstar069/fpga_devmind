"""Deterministic read-only tools for the P1a slice."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import EvidenceItem


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def evidence_id(tool: str, path: Path, start: int, end: int, ordinal: int) -> str:
    return f"E:{tool}:{file_hash(path)}:{start}-{end}:{ordinal:03d}"


def line_summary(path: Path, start: int, end: int, max_len: int = 180) -> str:
    lines = read_text(path).splitlines()
    snippet = " ".join(line.strip() for line in lines[start - 1:end] if line.strip())
    if len(snippet) > max_len:
        return snippet[: max_len - 3] + "..."
    return snippet


@dataclass
class SymbolInfo:
    name: str
    qualified_name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    docstring: str | None
    role_hint: str
    evidence_ids: list[str]
    methods: list[str] = field(default_factory=list)
    assigns: list[str] = field(default_factory=list)


@dataclass
class PythonStageObservation:
    files: list[str]
    symbols: list[SymbolInfo]
    q_operations: list[dict[str, Any]]
    width_growth_events: list[dict[str, Any]]
    pipeline_events: list[dict[str, Any]]
    interface_events: list[dict[str, Any]]
    dataflow_edges: list[dict[str, Any]]
    evidence_items: list[EvidenceItem]


def scan_project_tree(project_root: Path) -> dict[str, Any]:
    l6_path = project_root / "src" / "python_model" / "L6_resource_opt"
    config_path = project_root / "config"
    return {
        "project_root": str(project_root),
        "name": project_root.name,
        "layout_type": "ai_project_template_stage_layout"
        if (project_root / "src" / "python_model").exists()
        else "unknown",
        "stage_coverage": [
            p.name
            for p in sorted((project_root / "src" / "python_model").glob("L*_*"))
            if p.is_dir()
        ]
        if (project_root / "src" / "python_model").exists()
        else [],
        "l6_path": str(l6_path) if l6_path.exists() else None,
        "config_paths": [str(p) for p in sorted(config_path.glob("*.py"))]
        if config_path.exists()
        else [],
        "optional_context_paths": [
            str(project_root / "src" / "python_model" / "L5_fixedpoint"),
            str(project_root / "docs"),
        ],
    }


def _role_hint(name: str, docstring: str | None) -> str:
    text = f"{name}\n{docstring or ''}".lower()
    if "s0" in text or "autocorr" in text:
        return "stage_s0_autocorr_norm"
    if "s1" in text or "merge" in text:
        return "stage_s1_merge"
    if "s2" in text or "smooth" in text or "peak" in text:
        return "stage_s2_smooth_detect"
    if "s3" in text or "cfo" in text:
        return "stage_s3_cfo"
    if "qformat" in name.lower() or "q(" in text:
        return "fixed_point_support"
    if "axis" in text or "valid" in text:
        return "stream_interface"
    if "resource" in text or "estimate" in text:
        return "resource_estimate"
    if "pipeline" in text:
        return "pipeline_top"
    return "support"


def _class_assigns(node: ast.ClassDef) -> list[str]:
    assigns: list[str] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id == "self":
                        assigns.append(target.attr)
                elif isinstance(target, ast.Name):
                    assigns.append(target.id)
    return sorted(set(assigns))


def _class_methods(node: ast.ClassDef) -> list[str]:
    return [item.name for item in node.body if isinstance(item, ast.FunctionDef)]


def extract_python_stage_patterns(files: list[Path]) -> PythonStageObservation:
    evidence_items: list[EvidenceItem] = []
    symbols: list[SymbolInfo] = []
    q_events: list[dict[str, Any]] = []
    width_events: list[dict[str, Any]] = []
    pipeline_events: list[dict[str, Any]] = []
    interface_events: list[dict[str, Any]] = []
    dataflow_edges: list[dict[str, Any]] = []
    ordinal = 1

    for path in files:
        if path.name.startswith("__") or "__pycache__" in path.parts:
            continue
        source = read_text(path)
        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                continue
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            eid = evidence_id("py_stage", path, start, end, ordinal)
            ordinal += 1
            doc = ast.get_docstring(node)
            role = _role_hint(node.name, doc)
            strength = "strong" if isinstance(node, ast.ClassDef) else "strong"
            evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="source_code",
                    file_path=str(path),
                    start_line=start,
                    end_line=end,
                    symbol=node.name,
                    excerpt_summary=line_summary(path, start, min(end, start + 8)),
                    evidence_strength=strength,
                    snippet_complete=True,
                )
            )
            assigns = _class_assigns(node) if isinstance(node, ast.ClassDef) else []
            methods = _class_methods(node) if isinstance(node, ast.ClassDef) else []
            symbols.append(
                SymbolInfo(
                    name=node.name,
                    qualified_name=node.name,
                    kind="class" if isinstance(node, ast.ClassDef) else "function",
                    file_path=str(path),
                    start_line=start,
                    end_line=end,
                    docstring=doc,
                    role_hint=role,
                    evidence_ids=[eid],
                    methods=methods,
                    assigns=assigns,
                )
            )
            lowered = f"{node.name}\n{doc or ''}".lower()
            if any(marker in lowered for marker in ("q(", "qformat", "q_", "fixed-point")):
                q_events.append({"symbol": node.name, "evidence_ids": [eid], "summary": doc})
            if any(marker in lowered for marker in ("width", "shift", "truncate", "saturate")):
                width_events.append({"symbol": node.name, "evidence_ids": [eid], "summary": doc})
            if any(marker in lowered for marker in ("pipeline", "cycle", "latency", "stage")):
                pipeline_events.append({"symbol": node.name, "evidence_ids": [eid], "summary": doc})
            if any(marker in lowered for marker in ("axis", "valid", "ready", "tlast", "tdata")):
                interface_events.append({"symbol": node.name, "evidence_ids": [eid], "summary": doc})

    # Coarse, deterministic dataflow hints from known stage roles.
    stage_symbols = {s.role_hint: s for s in symbols}
    ordered = [
        "stage_s0_autocorr_norm",
        "stage_s1_merge",
        "stage_s2_smooth_detect",
        "stage_s3_cfo",
    ]
    for src_role, dst_role in zip(ordered, ordered[1:]):
        if src_role in stage_symbols and dst_role in stage_symbols:
            src = stage_symbols[src_role]
            dst = stage_symbols[dst_role]
            dataflow_edges.append(
                {
                    "from_symbol": src.name,
                    "to_symbol": dst.name,
                    "label": "pipeline dataflow",
                    "evidence_ids": src.evidence_ids + dst.evidence_ids,
                }
            )

    return PythonStageObservation(
        files=[str(p) for p in files],
        symbols=symbols,
        q_operations=q_events,
        width_growth_events=width_events,
        pipeline_events=pipeline_events,
        interface_events=interface_events,
        dataflow_edges=dataflow_edges,
        evidence_items=evidence_items,
    )


def extract_parameters(project_root: Path) -> tuple[list[dict[str, Any]], list[EvidenceItem]]:
    parameters_py = project_root / "config" / "parameters.py"
    if not parameters_py.exists():
        return [], []
    tree = ast.parse(read_text(parameters_py))
    params: list[dict[str, Any]] = []
    evidence: list[EvidenceItem] = []
    ordinal = 1
    for class_node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        if class_node.name != "ModuleParameters":
            continue
        for stmt in class_node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                try:
                    value_repr = ast.literal_eval(stmt.value) if stmt.value is not None else None
                except Exception:
                    value_repr = ast.unparse(stmt.value) if stmt.value is not None else None
                start = stmt.lineno
                end = getattr(stmt, "end_lineno", stmt.lineno)
                eid = evidence_id("params", parameters_py, start, end, ordinal)
                ordinal += 1
                params.append(
                    {
                        "name": stmt.target.id,
                        "value_repr": value_repr,
                        "file_path": str(parameters_py),
                        "start_line": start,
                        "end_line": end,
                        "evidence_ids": [eid],
                    }
                )
                evidence.append(
                    EvidenceItem(
                        evidence_id=eid,
                        source_type="config",
                        file_path=str(parameters_py),
                        start_line=start,
                        end_line=end,
                        symbol=stmt.target.id,
                        excerpt_summary=line_summary(parameters_py, start, end),
                        evidence_strength="strong",
                    )
                )
    return params, evidence
