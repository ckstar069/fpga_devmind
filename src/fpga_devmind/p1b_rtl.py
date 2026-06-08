"""P1b RTL evidence collector.

Extracts RTL-side evidence for candidate modules, signals and state
elements related to a selected concept.  Uses conservative line/regex
matching — no full Verilog parser.

T004 scope: RTL evidence extraction only.
Does not generate MappingClaims or L5/L6-to-RTL mapping conclusions.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.schema import EvidenceItem, UncertaintyNote
from fpga_devmind.tools import evidence_id, line_summary, read_text

RTL_EVIDENCE_SCHEMA_VERSION = "p1b-rtl-evidence-0.1"

# Verilog / SystemVerilog file extensions.
_VERILOG_EXTS = frozenset({".v", ".sv", ".vh"})

# ---------------------------------------------------------------------------
# Regex patterns (conservative line-level matching)
# ---------------------------------------------------------------------------

# module <name> ... (
_RE_MODULE = re.compile(r"^\s*module\s+(\w+)")
# endmodule
_RE_ENDMODULE = re.compile(r"^\s*endmodule\b")
# input/output/inout/reg/wire/logic declarations
_RE_SIGNAL_DECL = re.compile(
    r"^\s*(?:input|output|inout|reg|wire|logic)\s+"
)
# always @(
_RE_ALWAYS = re.compile(r"^\s*always\s*@")
# assign <signal> = ...
_RE_ASSIGN = re.compile(r"^\s*assign\s+(\w+)")
# parameter / localparam
_RE_PARAM = re.compile(
    r"^\s*(?:parameter|localparam)\s+.*?(\w+)\s*="
)


def _normalize(name: str) -> str:
    """Normalize a concept name for loose matching.

    Strips leading/trailing underscores and lowercases.
    """
    return name.strip("_").lower()


def _name_matches(concept: str, identifier: str) -> bool:
    """Check whether *identifier* matches *concept* (exact or normalized
    substring)."""
    if concept == identifier:
        return True
    nc = _normalize(concept)
    ni = _normalize(identifier)
    if not nc or not ni:
        return False
    return nc in ni or ni in nc


def _find_module_range(
    lines: list[str], start_idx: int
) -> int | None:
    """Find the endmodule line for a module starting at *start_idx*.

    Returns the 1-based line number of ``endmodule``, or None.
    """
    for i in range(start_idx, len(lines)):
        if _RE_ENDMODULE.search(lines[i]):
            return i + 1  # 1-based
    return None


def _block_end(
    lines: list[str], start_idx: int, max_lines: int = 200
) -> int:
    """Estimate the end of a block (always/assign) starting at
    *start_idx*.  Looks for begin/end balance, capped at *max_lines*."""
    depth = 0
    for i in range(start_idx, min(start_idx + max_lines, len(lines))):
        depth += len(re.findall(r"\bbegin\b", lines[i]))
        depth -= len(re.findall(r"\bend\b", lines[i]))
        if depth <= 0 and i > start_idx:
            return i + 1  # 1-based
    return min(start_idx + max_lines, len(lines))


# ---------------------------------------------------------------------------
# Output data structures
# ---------------------------------------------------------------------------


@dataclass
class RTLObjectView:
    """An RTL object found during evidence collection."""

    rtl_object_id: str
    object_type: str  # module|signal|always_block|assign|parameter|comment
    name: str
    file_path: str
    start_line: int
    end_line: int
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "inferred"


@dataclass
class RTLEvidenceCollection:
    """Structured output of the P1b RTL evidence collector."""

    schema_version: str = RTL_EVIDENCE_SCHEMA_VERSION
    concept_name: str = ""
    rtl_candidate_files: list[str] = field(default_factory=list)
    rtl_views: list[RTLObjectView] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    uncertainty_notes: list[UncertaintyNote] = field(
        default_factory=list
    )
    collection_diagnostics: list[dict[str, str]] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return asdict(self)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_evidence(
    path: Path,
    start: int,
    end: int,
    symbol: str,
    ordinal: int,
    strength: str,
) -> tuple[EvidenceItem, str]:
    """Create an EvidenceItem and return (item, evidence_id)."""
    eid = evidence_id("p1b_rtl", path, start, end, ordinal)
    ei = EvidenceItem(
        evidence_id=eid,
        source_type="rtl_source",
        file_path=str(path),
        start_line=start,
        end_line=end,
        symbol=symbol,
        excerpt_summary=line_summary(path, start, min(end, start + 4)),
        evidence_strength=strength,
    )
    return ei, eid


def _add_view(
    collection: RTLEvidenceCollection,
    object_type: str,
    name: str,
    path: Path,
    start: int,
    end: int,
    eid: str,
    confidence: str = "inferred",
) -> None:
    """Append an RTLObjectView to the collection."""
    obj_id = "RTL_{}_{}_{}".format(object_type, path.stem, start)
    collection.rtl_views.append(
        RTLObjectView(
            rtl_object_id=obj_id,
            object_type=object_type,
            name=name,
            file_path=str(path),
            start_line=start,
            end_line=end,
            evidence_ids=[eid],
            confidence=confidence,
        )
    )


def _is_comment_only(line: str) -> bool:
    """Return True if the line is a pure comment (stripped starts with //)."""
    return line.strip().startswith("//")


def _concept_in_line(line: str, concept: str, norm_concept: str) -> bool:
    """Check if a line contains the concept name (exact or normalized)."""
    if concept in line:
        return True
    return norm_concept in _normalize(line)


# ---------------------------------------------------------------------------
# Internal scanners
# ---------------------------------------------------------------------------


def _scan_modules(
    lines: list[str],
    path: Path,
    concept: str,
    norm_concept: str,
    collection: RTLEvidenceCollection,
    start_ordinal: int,
) -> None:
    """Scan for module declarations related to the concept."""
    ordinal = start_ordinal
    for i, line in enumerate(lines):
        m = _RE_MODULE.search(line)
        if m is None:
            continue
        mod_name = m.group(1)
        name_match = _name_matches(concept, mod_name)
        end_line = _find_module_range(lines, i)
        if end_line is None:
            end_line = len(lines)

        if not name_match:
            # Check if concept appears in module body, excluding pure
            # comment lines.  Comment-only references should only produce
            # evidence via _scan_comments(), not module-level claims.
            body_has_concept = any(
                _concept_in_line(lines[j], concept, norm_concept)
                for j in range(i, min(end_line, len(lines)))
                if not _is_comment_only(lines[j])
            )
            if not body_has_concept:
                continue

        strength = "strong" if name_match else "medium"
        start = i + 1  # 1-based
        ei, eid = _make_evidence(
            path, start, end_line, mod_name, ordinal, strength
        )
        ordinal += 1
        collection.evidence_items.append(ei)
        _add_view(
            collection, "module", mod_name, path, start, end_line, eid
        )


def _scan_always_blocks(
    lines: list[str],
    path: Path,
    concept: str,
    norm_concept: str,
    collection: RTLEvidenceCollection,
    start_ordinal: int,
) -> None:
    """Scan for always blocks containing the concept name."""
    ordinal = start_ordinal
    for i, line in enumerate(lines):
        if not _RE_ALWAYS.search(line):
            continue
        start = i + 1
        end = _block_end(lines, i)
        # Exclude pure comment lines — comment-only references should
        # only produce evidence via _scan_comments(), not always_block
        # claims.
        has_concept = any(
            _concept_in_line(lines[j], concept, norm_concept)
            for j in range(i, min(end, len(lines)))
            if not _is_comment_only(lines[j])
        )
        if not has_concept:
            continue

        ei, eid = _make_evidence(
            path, start, end, "always_{}".format(start), ordinal, "medium"
        )
        ordinal += 1
        collection.evidence_items.append(ei)
        _add_view(
            collection, "always_block",
            "always_{}".format(start), path, start, end, eid,
        )


def _scan_assigns(
    lines: list[str],
    path: Path,
    concept: str,
    norm_concept: str,
    collection: RTLEvidenceCollection,
    start_ordinal: int,
) -> None:
    """Scan for assign statements containing the concept name."""
    ordinal = start_ordinal
    for i, line in enumerate(lines):
        m = _RE_ASSIGN.search(line)
        if m is None:
            continue
        sig_name = m.group(1)
        if not _concept_in_line(line, concept, norm_concept):
            continue

        start = i + 1
        end = start  # single-line
        strength = "strong" if _name_matches(concept, sig_name) else "medium"
        ei, eid = _make_evidence(
            path, start, end, sig_name, ordinal, strength
        )
        ordinal += 1
        collection.evidence_items.append(ei)
        _add_view(collection, "assign", sig_name, path, start, end, eid)


def _scan_signals(
    lines: list[str],
    path: Path,
    concept: str,
    norm_concept: str,
    collection: RTLEvidenceCollection,
    start_ordinal: int,
) -> None:
    """Scan for signal declarations (input/output/reg/wire) related to
    the concept."""
    ordinal = start_ordinal
    for i, line in enumerate(lines):
        if not _RE_SIGNAL_DECL.search(line):
            continue
        if not _concept_in_line(line, concept, norm_concept):
            continue

        tokens = re.findall(r"(\w+)", line)
        matched_tokens = [
            t for t in tokens  # pyright: ignore[reportAny]
            if _name_matches(concept, t)  # pyright: ignore[reportAny]
        ]
        if not matched_tokens:
            continue

        start = i + 1
        end = start
        for sig_name in matched_tokens:  # pyright: ignore[reportAny]
            strength = "strong" if concept == sig_name else "medium"
            ei, eid = _make_evidence(
                path, start, end, sig_name, ordinal, strength  # pyright: ignore[reportAny]
            )
            ordinal += 1
            collection.evidence_items.append(ei)
            _add_view(
                collection, "signal", sig_name,  # pyright: ignore[reportAny]
                path, start, end, eid
            )


def _scan_params(
    lines: list[str],
    path: Path,
    concept: str,
    norm_concept: str,
    collection: RTLEvidenceCollection,
    start_ordinal: int,
) -> None:
    """Scan for parameter/localparam declarations related to the concept."""
    ordinal = start_ordinal
    for i, line in enumerate(lines):
        m = _RE_PARAM.search(line)
        if m is None:
            continue
        if not _concept_in_line(line, concept, norm_concept):
            continue

        param_name = m.group(1)
        start = i + 1
        end = start
        ei, eid = _make_evidence(
            path, start, end, param_name, ordinal, "medium"
        )
        ordinal += 1
        collection.evidence_items.append(ei)
        _add_view(
            collection, "parameter", param_name, path, start, end, eid
        )


def _scan_comments(
    lines: list[str],
    path: Path,
    concept: str,
    norm_concept: str,
    collection: RTLEvidenceCollection,
    start_ordinal: int,
) -> None:
    """Scan for comments explicitly referencing the concept."""
    ordinal = start_ordinal
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("//"):
            continue
        if not _concept_in_line(stripped, concept, norm_concept):
            continue

        start = i + 1
        end = start
        ei, eid = _make_evidence(
            path, start, end, "comment_{}".format(start), ordinal, "weak"
        )
        ordinal += 1
        collection.evidence_items.append(ei)
        _add_view(
            collection, "comment",
            "comment_{}".format(start), path, start, end, eid,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_rtl_evidence(
    concept_name: str,
    candidate_files: list[str],
) -> RTLEvidenceCollection:
    """Collect RTL-side evidence for *concept_name*.

    Parameters
    ----------
    concept_name : str
        Name of the concept to search for (e.g. ``"peak_idx"``).
    candidate_files : list[str]
        Absolute paths to RTL candidate files (from T002
        :class:`SourceCollection`).

    Returns
    -------
    RTLEvidenceCollection
        RTL views, evidence items, uncertainty notes and diagnostics.
    """
    collection = RTLEvidenceCollection(
        concept_name=concept_name,
        rtl_candidate_files=list(candidate_files),
    )
    ordinal = 1
    norm_concept = _normalize(concept_name)

    for file_path_str in candidate_files:
        path = Path(file_path_str)
        if not path.is_file():
            continue
        if path.suffix not in _VERILOG_EXTS:
            continue

        try:
            source = read_text(path)
        except OSError as exc:
            collection.collection_diagnostics.append(
                {
                    "section": "RTL",
                    "severity": "warning",
                    "file_path": str(path),
                    "message": "{}: {}".format(type(exc).__name__, exc),
                }
            )
            continue

        lines = source.splitlines()

        # --- module declarations ---
        _scan_modules(
            lines, path, concept_name, norm_concept,
            collection, ordinal,
        )
        ordinal = len(collection.evidence_items) + 1

        # --- always blocks ---
        _scan_always_blocks(
            lines, path, concept_name, norm_concept,
            collection, ordinal,
        )
        ordinal = len(collection.evidence_items) + 1

        # --- assign statements ---
        _scan_assigns(
            lines, path, concept_name, norm_concept,
            collection, ordinal,
        )
        ordinal = len(collection.evidence_items) + 1

        # --- signal declarations ---
        _scan_signals(
            lines, path, concept_name, norm_concept,
            collection, ordinal,
        )
        ordinal = len(collection.evidence_items) + 1

        # --- parameters ---
        _scan_params(
            lines, path, concept_name, norm_concept,
            collection, ordinal,
        )
        ordinal = len(collection.evidence_items) + 1

        # --- comments referencing concept ---
        _scan_comments(
            lines, path, concept_name, norm_concept,
            collection, ordinal,
        )
        ordinal = len(collection.evidence_items) + 1

    # --- unknown concept -> explicit uncertainty ---
    if not collection.evidence_items:
        collection.uncertainty_notes.append(
            UncertaintyNote(
                uncertainty_id="U_RTL_UNKNOWN_{}".format(concept_name),
                topic="concept_not_found_in_rtl",
                scope="RTL",
                reason="Concept '{}' not found in any RTL candidate file".format(
                    concept_name
                ),
                current_interpretation="unknown",
            )
        )
        collection.collection_diagnostics.append(
            {
                "section": "RTL",
                "severity": "info",
                "message": "No RTL evidence found for concept '{}'".format(
                    concept_name
                ),
            }
        )

    return collection
