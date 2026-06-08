"""P1b read-only source collector.

Discovers candidate source files (L5, L6, RTL, test) for P1b
concept tracing.  Does not infer mappings or generate claims.

T002 scope: evidence discovery only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SOURCE_COLLECTION_SCHEMA_VERSION = "p1b-source-collection-0.1"

_PY_IGNORED = {"__init__.py"}
_VERILOG_EXTS = frozenset({".v", ".sv", ".vh"})


@dataclass
class SourceCollection:
    """Structured output of the P1b source collector.

    Identifies where later evidence extraction (T003/T004) may look,
    without making any mapping claims.
    """

    schema_version: str = SOURCE_COLLECTION_SCHEMA_VERSION
    project_id: str = ""
    project_root: str = ""
    concept_name: str = ""
    l5_candidate_files: list[str] = field(default_factory=list)
    l6_candidate_files: list[str] = field(default_factory=list)
    rtl_candidate_files: list[str] = field(default_factory=list)
    test_candidate_files: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    collection_diagnostics: list[dict[str, str]] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _discover_py_files(directory: Path) -> list[str]:
    """Return sorted absolute paths of candidate Python files."""
    if not directory.is_dir():
        return []
    result: list[str] = []
    for p in sorted(directory.rglob("*.py")):
        if p.name in _PY_IGNORED or "__pycache__" in p.parts:
            continue
        result.append(str(p))
    return result


def _discover_rtl_files(directory: Path) -> list[str]:
    """Return sorted absolute paths of candidate Verilog / SystemVerilog
    source files (``.v``, ``.sv``, ``.vh``)."""
    if not directory.is_dir():
        return []
    result: list[str] = []
    for p in sorted(directory.rglob("*")):
        if p.suffix in _VERILOG_EXTS and p.is_file():
            result.append(str(p))
    return result


def _discover_test_files(project_root: Path) -> list[str]:
    """Return sorted absolute paths of candidate test files.

    Discovers both Python tests under ``tests/`` and Verilog
    testbenches under ``tests/verilog/``.
    """
    result: list[str] = []
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return result
    for p in sorted(tests_dir.rglob("*.py")):
        if p.name in _PY_IGNORED or "__pycache__" in p.parts:
            continue
        result.append(str(p))
    for p in sorted(tests_dir.rglob("*")):
        if p.suffix in _VERILOG_EXTS and p.is_file():
            result.append(str(p))
    return result


def collect_p1b_sources(
    project_root: Path,
    concept_name: str,
) -> SourceCollection:
    """Discover candidate source files for P1b concept tracing.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    concept_name : str
        Name of the concept to trace (stored as metadata).

    Returns
    -------
    SourceCollection
        Structured file discovery results with diagnostics for
        missing sections.

    Raises
    ------
    ValueError
        If *project_root* does not exist or is not a directory.
    """
    root = project_root.resolve()

    if not root.exists():
        raise ValueError("Project root does not exist: {}".format(root))
    if not root.is_dir():
        raise ValueError("Project root is not a directory: {}".format(root))

    collection = SourceCollection(
        project_id=root.name,
        project_root=str(root),
        concept_name=concept_name,
    )

    # --- L5 Fixed-point ---
    l5_dir = root / "src" / "python_model" / "L5_fixedpoint"
    l5_files = _discover_py_files(l5_dir)
    collection.l5_candidate_files = l5_files
    if not l5_files:
        collection.missing_sections.append("L5_fixedpoint")
        collection.collection_diagnostics.append({
            "section": "L5_fixedpoint",
            "severity": "info",
            "message": "No L5 fixed-point files found",
        })

    # --- L6 Resource Optimization ---
    l6_dir = root / "src" / "python_model" / "L6_resource_opt"
    l6_files = _discover_py_files(l6_dir)
    collection.l6_candidate_files = l6_files
    if not l6_files:
        collection.missing_sections.append("L6_resource_opt")
        collection.collection_diagnostics.append({
            "section": "L6_resource_opt",
            "severity": "warning",
            "message": "No L6 resource optimization files found",
        })

    # --- RTL Verilog ---
    rtl_dir = root / "src" / "verilog_model" / "rtl"
    rtl_files = _discover_rtl_files(rtl_dir)
    collection.rtl_candidate_files = rtl_files
    if not rtl_files:
        collection.missing_sections.append("RTL")
        collection.collection_diagnostics.append({
            "section": "RTL",
            "severity": "warning",
            "message": "No RTL Verilog files found",
        })

    # --- Tests ---
    test_files = _discover_test_files(root)
    collection.test_candidate_files = test_files
    if not test_files:
        collection.missing_sections.append("tests")
        collection.collection_diagnostics.append({
            "section": "tests",
            "severity": "info",
            "message": "No test files found",
        })

    return collection
