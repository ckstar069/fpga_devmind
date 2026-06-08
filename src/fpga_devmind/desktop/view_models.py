"""View models for the Desktop Agent Shell.

Pure data-layer transformations from loaded artifacts to view-ready
structures.  No GUI dependency.  Testable independently of PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    ArtifactDiagnostic,
    get_graph,
    get_grounding_report,
    get_markdown,
    get_mermaid,
    get_run_metadata,
)


# ---------------------------------------------------------------------------
# Run Summary View Model
# ---------------------------------------------------------------------------


@dataclass
class RunSummaryViewModel:
    """View-ready run summary extracted from run_metadata.json."""

    concept: str = ""
    project_root: str = ""
    output_dir: str = ""
    elapsed_seconds: float = 0.0
    status: str = "unknown"
    blocking_diagnostics: int = 0
    mapping_claims: int = 0
    evidence_items: int = 0
    schema_version: str = ""
    artifacts: list[str] = field(default_factory=list)
    is_loaded: bool = False
    load_error: str | None = None


@dataclass
class JsonTreeNode:
    """A single node in a JSON tree view."""

    key: str
    value: str
    value_type: str  # "dict" | "list" | "str" | "int" | "float" | "bool" | "null"
    children: list[JsonTreeNode] = field(default_factory=list)
    depth: int = 0


@dataclass
class JsonTreeViewModel:
    """View-ready JSON tree for structured browsing."""

    title: str = ""
    root: JsonTreeNode | None = None
    is_loaded: bool = False
    load_error: str | None = None


@dataclass
class MarkdownPreviewViewModel:
    """View-ready Markdown preview."""

    title: str = ""
    content: str = ""
    is_loaded: bool = False
    load_error: str | None = None


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def build_run_summary(bundle: ArtifactBundle) -> RunSummaryViewModel:
    """Build a RunSummaryViewModel from a loaded bundle."""
    if not bundle.is_complete:
        errors = [
            d.message
            for d in bundle.diagnostics
            if d.severity == "error"
        ]
        return RunSummaryViewModel(
            is_loaded=False,
            load_error="; ".join(errors) if errors else "Incomplete bundle",
        )

    meta = get_run_metadata(bundle)
    if meta is None:
        return RunSummaryViewModel(
            is_loaded=False,
            load_error="run_metadata.json not found or not valid JSON",
        )

    return RunSummaryViewModel(
        concept=meta.get("concept", ""),
        project_root=meta.get("project_root", ""),
        output_dir=meta.get("output_dir", ""),
        elapsed_seconds=meta.get("elapsed_seconds", 0.0),
        status=meta.get("status", "unknown"),
        blocking_diagnostics=meta.get("blocking_diagnostics", 0),
        mapping_claims=meta.get("mapping_claims", 0),
        evidence_items=meta.get("evidence_items", 0),
        schema_version=meta.get("schema_version", ""),
        artifacts=meta.get("artifacts", []),
        is_loaded=True,
    )


def _build_json_tree(  # noqa: C901
    key: str,
    value: Any,  # pyright: ignore[reportExplicitAny]
    depth: int = 0,
    max_depth: int = 50,
) -> JsonTreeNode:
    """Recursively build a JsonTreeNode from a JSON value."""
    if depth > max_depth:
        return JsonTreeNode(
            key=key,
            value="... (max depth exceeded)",
            value_type="str",
            depth=depth,
        )

    if value is None:
        return JsonTreeNode(
            key=key, value="null", value_type="null", depth=depth
        )

    if isinstance(value, bool):
        return JsonTreeNode(
            key=key,
            value="true" if value else "false",
            value_type="bool",
            depth=depth,
        )

    if isinstance(value, int):
        return JsonTreeNode(
            key=key, value=str(value), value_type="int", depth=depth
        )

    if isinstance(value, float):
        return JsonTreeNode(
            key=key, value=str(value), value_type="float", depth=depth
        )

    if isinstance(value, str):
        # Truncate long strings for tree display.
        display = value[:200] + "..." if len(value) > 200 else value
        return JsonTreeNode(
            key=key, value=display, value_type="str", depth=depth
        )

    if isinstance(value, list):
        children: list[JsonTreeNode] = []
        for i, item in enumerate(value):
            child = _build_json_tree(
                "[{}]".format(i), item, depth + 1, max_depth
            )
            children.append(child)
        summary = "{} item(s)".format(len(value))
        return JsonTreeNode(
            key=key,
            value=summary,
            value_type="list",
            children=children,
            depth=depth,
        )

    if isinstance(value, dict):
        children = []
        for k, v in sorted(value.items()):
            child = _build_json_tree(k, v, depth + 1, max_depth)
            children.append(child)
        summary = "{} field(s)".format(len(value))
        return JsonTreeNode(
            key=key,
            value=summary,
            value_type="dict",
            children=children,
            depth=depth,
        )

    # Fallback for unexpected types.
    return JsonTreeNode(
        key=key,
        value=str(value),
        value_type="str",
        depth=depth,
    )


def build_json_tree(
    bundle: ArtifactBundle,
    artifact_name: str,
) -> JsonTreeViewModel:
    """Build a JsonTreeViewModel for a named JSON artifact."""
    artifact = bundle.artifacts.get(artifact_name)
    if artifact is None:
        return JsonTreeViewModel(
            title=artifact_name,
            is_loaded=False,
            load_error="Artifact not found: {}".format(artifact_name),
        )

    if artifact.content_type != "json":
        return JsonTreeViewModel(
            title=artifact_name,
            is_loaded=False,
            load_error="Not a JSON artifact: {}".format(artifact_name),
        )

    data = artifact.data
    if not isinstance(data, dict):
        return JsonTreeViewModel(
            title=artifact_name,
            is_loaded=False,
            load_error="Invalid JSON structure: {}".format(artifact_name),
        )

    root = _build_json_tree("root", data)
    return JsonTreeViewModel(
        title=artifact_name,
        root=root,
        is_loaded=True,
    )


def build_markdown_preview(
    bundle: ArtifactBundle,
    artifact_name: str = "concept_trace.md",
) -> MarkdownPreviewViewModel:
    """Build a MarkdownPreviewViewModel for a named text artifact."""
    artifact = bundle.artifacts.get(artifact_name)
    if artifact is None:
        return MarkdownPreviewViewModel(
            title=artifact_name,
            is_loaded=False,
            load_error="Artifact not found: {}".format(artifact_name),
        )

    if not isinstance(artifact.data, str):
        return MarkdownPreviewViewModel(
            title=artifact_name,
            is_loaded=False,
            load_error="Not a text artifact: {}".format(artifact_name),
        )

    return MarkdownPreviewViewModel(
        title=artifact_name,
        content=artifact.data,
        is_loaded=True,
    )


# ---------------------------------------------------------------------------
# Bundle summary
# ---------------------------------------------------------------------------


@dataclass
class BundleSummaryViewModel:
    """High-level summary of a loaded artifact bundle."""

    bundle_type: str = "unknown"
    directory: str = ""
    is_complete: bool = False
    diagnostic_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    artifact_count: int = 0
    artifact_names: list[str] = field(default_factory=list)


def build_bundle_summary(bundle: ArtifactBundle) -> BundleSummaryViewModel:
    """Build a BundleSummaryViewModel from a loaded bundle."""
    errors = sum(1 for d in bundle.diagnostics if d.severity == "error")
    warnings = sum(1 for d in bundle.diagnostics if d.severity == "warning")
    return BundleSummaryViewModel(
        bundle_type=bundle.bundle_type,
        directory=str(bundle.directory),
        is_complete=bundle.is_complete,
        diagnostic_count=len(bundle.diagnostics),
        error_count=errors,
        warning_count=warnings,
        artifact_count=len(bundle.artifacts),
        artifact_names=sorted(bundle.artifacts.keys()),
    )
