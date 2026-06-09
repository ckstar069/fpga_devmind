"""Artifact loader for the Desktop Agent Shell.

Reads P1a/P1b artifact bundles from a directory, validates completeness,
produces structured diagnostics for missing files, and loads JSON/Markdown
content into memory.

Does not write to artifact directories.  Does not read fpga_project_*
source trees.  Does not run Vivado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# P1b artifact contract (from T008)
# ---------------------------------------------------------------------------

P1B_REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "concept_trace_graph.json",
    "concept_trace_index.json",
    "grounding_report.json",
    "run_metadata.json",
    "concept_trace.md",
    "concept_trace.mmd",
)

P1B_OPTIONAL_ARTIFACTS: tuple[str, ...] = ()  # reserved for future expansion

PROJECT_REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "project_understanding_graph.json",
    "project_understanding_index.json",
    "run_metadata.json",
    "project_understanding.md",
)

PROJECT_OPTIONAL_ARTIFACTS: tuple[str, ...] = (
    "project_understanding.mmd",
)

P1A_REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "project_graph.json",
    "trace_index.json",
)

P1A_OPTIONAL_ARTIFACTS: tuple[str, ...] = (
    "memory_manifest.json",
    "summary.md",
    "flow.mmd",
    "trace.md",
    "run_metadata.json",
)

AGENT_RUNTIME_REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "agent_runtime_trace.json",
)

AGENT_RUNTIME_OPTIONAL_ARTIFACTS: tuple[str, ...] = (
    "answer.md",
)


# ---------------------------------------------------------------------------
# Diagnostic types
# ---------------------------------------------------------------------------


@dataclass
class ArtifactDiagnostic:
    """A diagnostic about an artifact bundle."""

    severity: str  # "error" | "warning" | "info"
    artifact: str | None  # artifact filename, or None for bundle-level
    message: str
    code: str | None = None  # diagnostic code for filtering


# ---------------------------------------------------------------------------
# Bundle detection
# ---------------------------------------------------------------------------


def detect_bundle_type(path: Path) -> str:
    """Detect whether *path* is a P1b, P1a, agent_runtime, project, or unknown bundle.

    Returns one of ``"agent_runtime"``, ``"p1b"``, ``"p1a"``, ``"project"``, ``"unknown"``.
    """
    if not path.is_dir():
        return "unknown"

    files = {p.name for p in path.iterdir() if p.is_file()}

    # Agent runtime detection: agent_runtime_trace.json is unique.
    if "agent_runtime_trace.json" in files:
        return "agent_runtime"

    # Project-level detection: project_understanding_graph.json is the source of truth.
    if "project_understanding_graph.json" in files:
        return "project"

    # P1b detection: concept_trace_graph.json is the source of truth.
    if "concept_trace_graph.json" in files:
        return "p1b"

    # P1a fallback detection.
    if "project_graph.json" in files:
        return "p1a"

    return "unknown"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_bundle(
    path: Path,
    bundle_type: str | None = None,
) -> list[ArtifactDiagnostic]:
    """Validate an artifact bundle and return diagnostics.

    Parameters
    ----------
    path : Path
        Artifact directory.
    bundle_type : str | None
        Pre-detected bundle type.  If None, ``detect_bundle_type()`` is
        called.

    Returns
    -------
    list[ArtifactDiagnostic]
        Diagnostics for missing or unexpected files.  Empty list means
        the bundle is complete.
    """
    diagnostics: list[ArtifactDiagnostic] = []

    if not path.is_dir():
        diagnostics.append(
            ArtifactDiagnostic(
                severity="error",
                artifact=None,
                message="Path is not a directory: {}".format(path),
                code="NOT_A_DIRECTORY",
            )
        )
        return diagnostics

    if bundle_type is None:
        bundle_type = detect_bundle_type(path)

    if bundle_type == "unknown":
        diagnostics.append(
            ArtifactDiagnostic(
                severity="error",
                artifact=None,
                message=(
                    "Unknown artifact bundle: neither "
                    "project_understanding_graph.json (project) nor "
                    "concept_trace_graph.json (P1b) nor "
                    "project_graph.json (P1a) found."
                ),
                code="UNKNOWN_BUNDLE",
            )
        )
        return diagnostics

    files = {p.name for p in path.iterdir() if p.is_file()}

    if bundle_type == "project":
        required = PROJECT_REQUIRED_ARTIFACTS
        for name in required:
            if name not in files:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Required project artifact missing: {}".format(
                            name
                        ),
                        code="MISSING_REQUIRED",
                    )
                )

    elif bundle_type == "p1b":
        required = P1B_REQUIRED_ARTIFACTS
        for name in required:
            if name not in files:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Required P1b artifact missing: {}".format(
                            name
                        ),
                        code="MISSING_REQUIRED",
                    )
                )

    elif bundle_type == "agent_runtime":
        for name in AGENT_RUNTIME_REQUIRED_ARTIFACTS:
            if name not in files:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message=(
                            "Required agent_runtime artifact missing: {}"
                        ).format(name),
                        code="MISSING_REQUIRED",
                    )
                )
        for name in AGENT_RUNTIME_OPTIONAL_ARTIFACTS:
            if name not in files:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="info",
                        artifact=name,
                        message=(
                            "Optional agent_runtime artifact missing: {}"
                        ).format(name),
                        code="MISSING_OPTIONAL",
                    )
                )

    elif bundle_type == "p1a":
        required = P1A_REQUIRED_ARTIFACTS
        for name in required:
            if name not in files:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Required P1a artifact missing: {}".format(
                            name
                        ),
                        code="MISSING_REQUIRED",
                    )
                )
        optional = P1A_OPTIONAL_ARTIFACTS
        for name in optional:
            if name not in files:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="warning",
                        artifact=name,
                        message="Optional P1a artifact missing: {}".format(
                            name
                        ),
                        code="MISSING_OPTIONAL",
                    )
                )

    return diagnostics


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


@dataclass
class LoadedArtifact:
    """A single loaded artifact."""

    name: str
    file_path: Path
    content_type: str  # "json" | "markdown" | "mermaid" | "unknown"
    data: dict[str, Any] | str  # parsed dict for JSON, raw str for text


@dataclass
class ArtifactBundle:
    """A loaded artifact bundle with metadata and diagnostics."""

    bundle_type: str  # "p1b" | "p1a" | "agent_runtime" | "project" | "unknown"
    directory: Path
    artifacts: dict[str, LoadedArtifact] = field(default_factory=dict)
    diagnostics: list[ArtifactDiagnostic] = field(default_factory=list)
    is_complete: bool = False


def load_bundle(path: Path) -> ArtifactBundle:
    """Load an artifact bundle from *path*.

    Parameters
    ----------
    path : Path
        Artifact directory.

    Returns
    -------
    ArtifactBundle
        Loaded bundle with artifacts and diagnostics.  Never raises;
        all errors become diagnostics.
    """
    diagnostics: list[ArtifactDiagnostic] = []
    try:
        bundle_type = detect_bundle_type(path)
        diagnostics = validate_bundle(path, bundle_type)
    except OSError as exc:
        diagnostics.append(
            ArtifactDiagnostic(
                severity="error",
                artifact=None,
                message="Failed to inspect bundle directory: {}".format(exc),
                code="LOAD_ERROR",
            )
        )
        return ArtifactBundle(
            bundle_type="unknown",
            directory=path,
            diagnostics=diagnostics,
            is_complete=False,
        )

    is_complete = not any(
        d.severity == "error" for d in diagnostics
    )

    bundle = ArtifactBundle(
        bundle_type=bundle_type,
        directory=path,
        diagnostics=diagnostics,
        is_complete=is_complete,
    )

    if bundle_type == "unknown":
        return bundle

    # Determine which files to load.
    if bundle_type == "p1b":
        files_to_load = list(P1B_REQUIRED_ARTIFACTS)
    elif bundle_type == "project":
        files_to_load = list(PROJECT_REQUIRED_ARTIFACTS)
        files_to_load.extend(PROJECT_OPTIONAL_ARTIFACTS)
    elif bundle_type == "agent_runtime":
        files_to_load = list(AGENT_RUNTIME_REQUIRED_ARTIFACTS)
        files_to_load.extend(AGENT_RUNTIME_OPTIONAL_ARTIFACTS)
    else:
        files_to_load = list(P1A_REQUIRED_ARTIFACTS)
        files_to_load.extend(P1A_OPTIONAL_ARTIFACTS)

    for name in files_to_load:
        file_path = path / name
        if not file_path.is_file():
            continue

        # Determine content type from extension.
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            content_type = "json"
            try:
                data: dict[str, Any] | str = json.loads(
                    file_path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError) as exc:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Failed to load {}: {}".format(name, exc),
                        code="LOAD_ERROR",
                    )
                )
                continue
        elif suffix == ".md":
            content_type = "markdown"
            try:
                data = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Failed to load {}: {}".format(name, exc),
                        code="LOAD_ERROR",
                    )
                )
                continue
        elif suffix == ".mmd":
            content_type = "mermaid"
            try:
                data = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Failed to load {}: {}".format(name, exc),
                        code="LOAD_ERROR",
                    )
                )
                continue
        else:
            content_type = "unknown"
            try:
                data = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                diagnostics.append(
                    ArtifactDiagnostic(
                        severity="error",
                        artifact=name,
                        message="Failed to load {}: {}".format(name, exc),
                        code="LOAD_ERROR",
                    )
                )
                continue

        bundle.artifacts[name] = LoadedArtifact(
            name=name,
            file_path=file_path,
            content_type=content_type,
            data=data,
        )

    # Re-evaluate is_complete after loading artifacts; any error-level
    # diagnostic must mark the bundle as incomplete.
    bundle.is_complete = not any(
        d.severity == "error" for d in diagnostics
    )
    return bundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_run_metadata(bundle: ArtifactBundle) -> dict[str, Any] | None:
    """Return run_metadata dict from a loaded bundle, or None."""
    artifact = bundle.artifacts.get("run_metadata.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None


def get_agent_runtime_trace(bundle: ArtifactBundle) -> dict[str, Any] | None:
    """Return agent_runtime_trace.json dict from a bundle, or None."""
    if bundle.bundle_type != "agent_runtime":
        return None
    artifact = bundle.artifacts.get("agent_runtime_trace.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None


def get_graph(bundle: ArtifactBundle) -> dict[str, Any] | None:
    """Return concept_trace_graph dict from a P1b bundle, or None."""
    if bundle.bundle_type != "p1b":
        return None
    artifact = bundle.artifacts.get("concept_trace_graph.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None


def get_index(bundle: ArtifactBundle) -> dict[str, Any] | None:
    """Return concept_trace_index dict from a P1b bundle, or None."""
    if bundle.bundle_type != "p1b":
        return None
    artifact = bundle.artifacts.get("concept_trace_index.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None


def get_grounding_report(bundle: ArtifactBundle) -> dict[str, Any] | None:
    """Return grounding_report dict from a P1b bundle, or None."""
    if bundle.bundle_type != "p1b":
        return None
    artifact = bundle.artifacts.get("grounding_report.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None


def get_markdown(bundle: ArtifactBundle) -> str | None:
    """Return concept_trace.md text from a P1b bundle, or None."""
    if bundle.bundle_type != "p1b":
        return None
    artifact = bundle.artifacts.get("concept_trace.md")
    if artifact is None:
        return None
    if isinstance(artifact.data, str):
        return artifact.data
    return None


def get_mermaid(bundle: ArtifactBundle) -> str | None:
    """Return concept_trace.mmd text from a P1b bundle, or None."""
    if bundle.bundle_type != "p1b":
        return None
    artifact = bundle.artifacts.get("concept_trace.mmd")
    if artifact is None:
        return None
    if isinstance(artifact.data, str):
        return artifact.data
    return None


def get_project_graph(bundle: ArtifactBundle) -> dict[str, Any] | None:  # pyright: ignore[reportExplicitAny]
    """Return project_understanding_graph dict from a project bundle, or None."""
    if bundle.bundle_type != "project":
        return None
    artifact = bundle.artifacts.get("project_understanding_graph.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None


def get_project_index(bundle: ArtifactBundle) -> dict[str, Any] | None:  # pyright: ignore[reportExplicitAny]
    """Return project_understanding_index dict from a project bundle, or None."""
    if bundle.bundle_type != "project":
        return None
    artifact = bundle.artifacts.get("project_understanding_index.json")
    if artifact is None:
        return None
    if isinstance(artifact.data, dict):
        return artifact.data
    return None
