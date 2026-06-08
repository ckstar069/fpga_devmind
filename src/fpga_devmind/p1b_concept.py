"""P1b concept evidence collector.

Extracts L5/L6 Python model evidence for a selected concept.
Does not inspect RTL or generate mapping claims.

T003 scope: L5/L6 evidence extraction only.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.schema import EvidenceItem, UncertaintyNote
from fpga_devmind.tools import evidence_id, line_summary, read_text

CONCEPT_COLLECTION_SCHEMA_VERSION = "p1b-concept-collection-0.1"


@dataclass
class ConceptSubject:
    """A Python class, function or module-level scope where the concept
    was found."""

    name: str
    kind: str  # "class" | "function" | "module"
    file_path: str
    start_line: int
    end_line: int
    role_hint: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ConceptCollection:
    """Structured output of the P1b concept evidence collector.

    Aligns with the T003 output contract.
    """

    schema_version: str = CONCEPT_COLLECTION_SCHEMA_VERSION
    concept_name: str = ""
    stage_side: str = "l5_l6"
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    candidate_subjects: list[ConceptSubject] = field(default_factory=list)
    uncertainty_notes: list[UncertaintyNote] = field(default_factory=list)
    collection_diagnostics: list[dict[str, str]] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return asdict(self)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _role_hint(name: str, docstring: str | None) -> str:
    """Classify the semantic role of a Python symbol."""
    text = "{}\n{}".format(name, docstring or "").lower()
    if any(kw in text for kw in ("calc", "compute", "detect", "estimate")):
        return "calculation"
    if any(kw in text for kw in ("update", "state", "track")):
        return "state_update"
    if any(kw in text for kw in ("axis", "valid", "ready", "stream")):
        return "interface"
    if any(kw in text for kw in ("pipeline", "stage", "cycle")):
        return "pipeline"
    if any(kw in text for kw in ("fixed", "qformat", "quantiz")):
        return "fixed_point"
    if any(kw in text for kw in ("config", "param", "setting")):
        return "config"
    if any(kw in text for kw in ("resource", "cost")):
        return "resource"
    return "support"


def _concept_in_lines(
    concept_name: str,
    source_lines: list[str],
    start: int,
    end: int,
) -> bool:
    """Check whether *concept_name* appears in ``source_lines[start-1:end]``."""
    for line in source_lines[start - 1 : end]:
        if concept_name in line:
            return True
    return False


def _classify_strength(
    node: ast.AST,
    concept_name: str,
) -> str:
    """Classify evidence strength for a concept occurrence within a symbol.

    - **strong**: concept appears as a parameter, attribute, or in the
      symbol name itself.
    - **medium**: concept appears as a local variable or index within
      a function/class body.
    - **weak**: fallback (e.g. comment or string-literal only).
    """
    # Symbol name contains the concept → strong
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        if concept_name in node.name:
            return "strong"

    # Parameter name contains the concept → strong
    if isinstance(node, ast.FunctionDef):
        for arg in node.args.args:
            if concept_name in arg.arg:
                return "strong"

    # self.<concept> attribute → strong
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and concept_name in child.attr:
                return "strong"

    # Name node (variable / index) → medium
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == concept_name:
                return "medium"

    return "weak"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_concept_evidence(
    project_root: Path,  # pyright: ignore[reportUnusedParameter]
    concept_name: str,
    candidate_files: list[str],
) -> ConceptCollection:
    """Collect L5/L6 Python model evidence for *concept_name*.

    Parameters
    ----------
    project_root : Path
        Root directory of the target FPGA project.
    concept_name : str
        Name of the concept to search for (e.g. ``"peak_idx"``).
    candidate_files : list[str]
        Absolute paths to L5/L6 candidate Python files (from T002
        :class:`SourceCollection`).

    Returns
    -------
    ConceptCollection
        Evidence items, candidate subjects, uncertainty notes, and
        diagnostics.  Unknown concepts produce an explicit uncertainty
        note and empty evidence.
    """
    collection = ConceptCollection(concept_name=concept_name)
    ordinal = 1

    for file_path_str in candidate_files:
        path = Path(file_path_str)
        if not path.is_file():
            continue
        if path.name.startswith("__") or "__pycache__" in path.parts:
            continue

        try:
            source = read_text(path)
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            collection.collection_diagnostics.append(
                {
                    "section": "L5_L6",
                    "severity": "warning",
                    "file_path": str(path),
                    "message": "{}: {}".format(type(exc).__name__, exc),
                }
            )
            continue
        source_lines = source.splitlines()

        # --- scan top-level classes and functions ---
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                continue

            start = node.lineno
            end = getattr(node, "end_lineno", start)
            if not _concept_in_lines(concept_name, source_lines, start, end):
                continue

            strength = _classify_strength(node, concept_name)
            eid = evidence_id("p1b_concept", path, start, end, ordinal)
            ordinal += 1

            collection.evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="concept_occurrence",
                    file_path=str(path),
                    start_line=start,
                    end_line=end,
                    symbol=node.name,
                    excerpt_summary=line_summary(
                        path, start, min(end, start + 4)
                    ),
                    evidence_strength=strength,
                )
            )

            doc = ast.get_docstring(node)
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            collection.candidate_subjects.append(
                ConceptSubject(
                    name=node.name,
                    kind=kind,
                    file_path=str(path),
                    start_line=start,
                    end_line=end,
                    role_hint=_role_hint(node.name, doc),
                    evidence_ids=[eid],
                )
            )

            # --- recurse into class methods ---
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    if not isinstance(child, ast.FunctionDef):
                        continue
                    m_start = child.lineno
                    m_end = getattr(child, "end_lineno", m_start)
                    if not _concept_in_lines(
                        concept_name, source_lines, m_start, m_end
                    ):
                        continue
                    m_strength = _classify_strength(child, concept_name)
                    m_eid = evidence_id(
                        "p1b_concept", path, m_start, m_end, ordinal
                    )
                    ordinal += 1
                    collection.evidence_items.append(
                        EvidenceItem(
                            evidence_id=m_eid,
                            source_type="concept_occurrence",
                            file_path=str(path),
                            start_line=m_start,
                            end_line=m_end,
                            symbol=child.name,
                            excerpt_summary=line_summary(
                                path, m_start, min(m_end, m_start + 4)
                            ),
                            evidence_strength=m_strength,
                        )
                    )
                    m_doc = ast.get_docstring(child)
                    collection.candidate_subjects.append(
                        ConceptSubject(
                            name=child.name,
                            kind="method",
                            file_path=str(path),
                            start_line=m_start,
                            end_line=m_end,
                            role_hint=_role_hint(child.name, m_doc),
                            evidence_ids=[m_eid],
                        )
                    )

        # --- scan module-level statements outside classes/functions ---
        seen_ranges: set[tuple[int, int]] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                continue
            start = getattr(node, "lineno", 0)
            end = getattr(node, "end_lineno", start)
            if start == 0:
                continue
            if not _concept_in_lines(concept_name, source_lines, start, end):
                continue
            if (start, end) in seen_ranges:
                continue
            seen_ranges.add((start, end))

            eid = evidence_id("p1b_concept", path, start, end, ordinal)
            ordinal += 1

            collection.evidence_items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="concept_occurrence",
                    file_path=str(path),
                    start_line=start,
                    end_line=end,
                    symbol=path.stem,
                    excerpt_summary=line_summary(
                        path, start, min(end, start + 4)
                    ),
                    evidence_strength="weak",
                )
            )

            collection.candidate_subjects.append(
                ConceptSubject(
                    name=path.stem,
                    kind="module",
                    file_path=str(path),
                    start_line=start,
                    end_line=end,
                    role_hint="support",
                    evidence_ids=[eid],
                )
            )

    # --- unknown concept → explicit uncertainty ---
    if not collection.evidence_items:
        collection.uncertainty_notes.append(
            UncertaintyNote(
                uncertainty_id="U_CONCEPT_UNKNOWN_{}".format(concept_name),
                topic="concept_not_found",
                scope="L5_L6",
                reason="Concept '{}' not found in any L5/L6 candidate file".format(
                    concept_name
                ),
                current_interpretation="unknown",
            )
        )
        collection.collection_diagnostics.append(
            {
                "section": "L5_L6",
                "severity": "info",
                "message": "No evidence found for concept '{}' in L5/L6 files".format(
                    concept_name
                ),
            }
        )

    return collection
