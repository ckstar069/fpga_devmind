"""Discovery evaluation against golden benchmark spec (T036).

Compares auto-discovered concepts against a golden benchmark specification
and computes precision/recall-like metrics.

Does not call LLM, does not modify target projects, does not run Vivado.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_discovery import ConceptCandidate, discover_concepts


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Result of evaluating auto-discovery against a golden spec."""

    project_id: str
    golden_core_count: int
    golden_secondary_count: int
    matched_core: list[str]  # names of matched core concepts
    missed_core: list[str]  # names of missed core concepts
    matched_secondary: list[str]
    unexpected_selected: list[str]
    precision_like: float  # 0.0 - 1.0
    recall_like: float  # 0.0 - 1.0
    details: list[dict[str, Any]] = field(default_factory=list)  # pyright: ignore[reportExplicitAny]

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_discovery(
    project_root: Path,
    golden_spec_path: Path,
) -> EvalResult:
    """Evaluate auto-discovery against a golden benchmark spec.

    Parameters
    ----------
    project_root : Path
        Root directory of the FPGA project to scan.
    golden_spec_path : Path
        Path to the golden concepts JSON file.

    Returns
    -------
    EvalResult
        Evaluation metrics and per-concept match details.

    Raises
    ------
    FileNotFoundError
        If the golden spec file does not exist.
    ValueError
        If the golden spec has an unexpected schema.
    """
    spec = _load_golden_spec(golden_spec_path)

    # run auto-discovery
    discovery_result = discover_concepts(project_root)

    # build lookup of discovered names (lowercase)
    discovered_names: set[str] = set()
    discovered_aliases: dict[str, list[str]] = {}
    for candidate in discovery_result.candidates:
        norm = candidate.name.lower()
        discovered_names.add(norm)
        # V2 discovery provides aliases on each candidate
        cand_aliases = getattr(candidate, "aliases", None) or []
        discovered_aliases[norm] = [a.lower() for a in cand_aliases]

    # extract golden concepts
    core_concepts = spec.get("expected_core_concepts", [])
    secondary_concepts = spec.get("expected_secondary_concepts", [])

    # evaluate core concept matching
    matched_core: list[str] = []
    missed_core: list[str] = []
    details: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    for entry in core_concepts:
        name = entry["concept"]
        aliases = entry.get("aliases", [])
        match_info = _match_concept(name, aliases, discovered_names, discovered_aliases)
        detail = {
            "golden_concept": name,
            "category": "core",
            "match_type": match_info["match_type"],
            "matched_to": match_info["matched_to"],
        }
        details.append(detail)

        if match_info["matched"]:
            matched_core.append(name)
        else:
            missed_core.append(name)

    # evaluate secondary concept matching
    matched_secondary: list[str] = []
    for entry in secondary_concepts:
        name = entry["concept"]
        aliases = entry.get("aliases", [])
        match_info = _match_concept(name, aliases, discovered_names, discovered_aliases)
        detail = {
            "golden_concept": name,
            "category": "secondary",
            "match_type": match_info["match_type"],
            "matched_to": match_info["matched_to"],
        }
        details.append(detail)

        if match_info["matched"]:
            matched_secondary.append(name)

    # find unexpected selected (discovered but not in golden spec at all)
    golden_all_names = _build_golden_name_set(core_concepts, secondary_concepts)
    unexpected_selected = _find_unexpected(
        discovery_result.candidates, golden_all_names,
    )

    # compute metrics
    total_core = len(core_concepts)
    matched_count = len(matched_core)
    unexpected_count = len(unexpected_selected)

    precision_denom = matched_count + unexpected_count
    precision_like = matched_count / precision_denom if precision_denom > 0 else 0.0
    recall_like = matched_count / total_core if total_core > 0 else 0.0

    return EvalResult(
        project_id=spec.get("project_id", project_root.name),
        golden_core_count=total_core,
        golden_secondary_count=len(secondary_concepts),
        matched_core=matched_core,
        missed_core=missed_core,
        matched_secondary=matched_secondary,
        unexpected_selected=unexpected_selected,
        precision_like=round(precision_like, 4),
        recall_like=round(recall_like, 4),
        details=details,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_golden_spec(path: Path) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Load and validate a golden concepts JSON file.

    Parameters
    ----------
    path : Path
        Path to the golden spec JSON.

    Returns
    -------
    dict[str, Any]
        Parsed golden spec.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the schema version is unexpected.
    """
    if not path.is_file():
        raise FileNotFoundError("Golden spec not found: {}".format(path))

    spec = json.loads(path.read_text(encoding="utf-8"))

    version = spec.get("schema_version", "")
    if not version.startswith("golden-concepts-"):
        raise ValueError(
            "Unexpected schema_version in golden spec: {} (expected golden-concepts-*)".format(
                version
            )
        )

    return spec


def _match_concept(
    name: str,
    aliases: list[str],
    discovered_names: set[str],
    discovered_aliases: dict[str, list[str]],
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Try to match a golden concept against discovered concepts.

    Matching logic (in order):
    1. Exact match (case-insensitive)
    2. Golden alias matches any discovered concept name
    3. Discovered concept aliases contain the golden concept name

    Parameters
    ----------
    name : str
        Golden concept name.
    aliases : list[str]
        Aliases from the golden spec.
    discovered_names : set[str]
        Normalized names of discovered concepts.
    discovered_aliases : dict[str, list[str]]
        Aliases of discovered concepts (populated from V2 discovery).

    Returns
    -------
    dict[str, Any]
        Match result with keys: matched, match_type, matched_to.
    """
    norm_name = name.lower()

    # 1. exact match
    if norm_name in discovered_names:
        return {"matched": True, "match_type": "exact", "matched_to": norm_name}

    # 2. golden alias matches discovered name
    for alias in aliases:
        norm_alias = alias.lower()
        if norm_alias in discovered_names:
            return {"matched": True, "match_type": "alias_to_name", "matched_to": norm_alias}

    # 3. discovered alias contains golden name
    for disc_name, disc_alias_list in discovered_aliases.items():
        for disc_alias in disc_alias_list:
            if disc_alias.lower() == norm_name:
                return {"matched": True, "match_type": "name_to_discovered_alias", "matched_to": disc_name}

    return {"matched": False, "match_type": "none", "matched_to": ""}


def _build_golden_name_set(
    core_concepts: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
    secondary_concepts: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
) -> set[str]:
    """Build a set of all golden concept names and aliases (lowercase).

    Parameters
    ----------
    core_concepts : list[dict]
        Core concept entries from the golden spec.
    secondary_concepts : list[dict]
        Secondary concept entries from the golden spec.

    Returns
    -------
    set[str]
        Normalized set of all golden concept names and aliases.
    """
    names: set[str] = set()
    for entry in core_concepts + secondary_concepts:
        names.add(entry["concept"].lower())
        for alias in entry.get("aliases", []):
            names.add(alias.lower())
    return names


def _find_unexpected(
    candidates: list[ConceptCandidate],
    golden_names: set[str],
) -> list[str]:
    """Find discovered concepts not present in the golden spec at all.

    A discovered concept is considered unexpected if neither its name nor any
    of its aliases appear in the golden concept name/alias set.

    Parameters
    ----------
    candidates : list[ConceptCandidate]
        Discovered concept candidates.
    golden_names : set[str]
        All golden concept names and aliases (lowercase).

    Returns
    -------
    list[str]
        Names of unexpected discovered concepts.
    """
    unexpected: list[str] = []
    for candidate in candidates:
        norm = candidate.name.lower()
        if norm in golden_names:
            continue
        # Check if any discovered alias is in golden names
        cand_aliases = getattr(candidate, "aliases", None) or []
        if any(a.lower() in golden_names for a in cand_aliases):
            continue
        unexpected.append(candidate.name)
    return unexpected
