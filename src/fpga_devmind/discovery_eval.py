"""Discovery evaluation against golden benchmark spec (T036/T037).

Compares auto-discovered concepts against a golden benchmark specification
and computes precision/recall metrics for both all candidates and selected top N.

Does not call LLM, does not modify target projects, does not run Vivado.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_discovery import (
    ConceptCandidate,
    DiscoveryResult,
    discover_concepts,
    select_for_trace,
    SELECTABLE_CATEGORIES,
)

EVAL_SCHEMA_VERSION = "discovery-eval-0.2"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SelectedConcept:
    """A concept selected for auto-trace with score info."""
    name: str
    score: int
    category: str
    confidence: str
    semantic_role: str
    selection_reason: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating auto-discovery against a golden spec."""

    # Schema
    schema_version: str = EVAL_SCHEMA_VERSION
    project_id: str = ""
    project_root: str = ""
    golden_spec_path: str = ""
    discovery_version: str = ""
    max_concepts: int = 12

    # Selected concepts (top N for auto-trace)
    selected_concepts: list[str] = field(default_factory=list)
    selected_canonical_concepts: list[str] = field(default_factory=list)
    selected_with_scores: list[dict[str, Any]] = field(default_factory=list)

    # Noise analysis
    rejected_top_terms: list[dict[str, str]] = field(default_factory=list)
    excluded_terms_selected: list[str] = field(default_factory=list)

    # Golden matching (all candidates)
    golden_core_count: int = 0
    golden_secondary_count: int = 0
    matched_core: list[str] = field(default_factory=list)
    missed_core: list[str] = field(default_factory=list)
    matched_secondary: list[str] = field(default_factory=list)
    unexpected_selected: list[str] = field(default_factory=list)

    # Precision/recall (all candidates)
    precision_like: float = 0.0
    recall_like: float = 0.0

    # Precision/recall (selected top N only)
    selected_precision_like: float = 0.0
    selected_recall_like: float = 0.0

    notes: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_discovery(
    project_root: Path,
    golden_spec_path: Path,
    max_concepts: int = 12,
) -> EvalResult:
    """Evaluate auto-discovery against a golden benchmark spec.

    Parameters
    ----------
    project_root : Path
        Root directory of the FPGA project to scan.
    golden_spec_path : Path
        Path to the golden concepts JSON file.
    max_concepts : int
        Maximum number of concepts to select for auto-trace.

    Returns
    -------
    EvalResult
        Evaluation metrics, selected concepts, and per-concept match details.
    """
    spec = _load_golden_spec(golden_spec_path)

    # run auto-discovery
    discovery_result = discover_concepts(project_root)

    # select top N for auto-trace
    selected = select_for_trace(discovery_result, max_n=max_concepts)

    # build lookup of all discovered names (lowercase)
    discovered_names: set[str] = set()
    discovered_aliases: dict[str, list[str]] = {}
    for candidate in discovery_result.candidates:
        norm = candidate.name.lower()
        discovered_names.add(norm)
        cand_aliases = getattr(candidate, "aliases", None) or []
        discovered_aliases[norm] = [a.lower() for a in cand_aliases]

    # extract golden concepts
    core_concepts = spec.get("expected_core_concepts", [])
    secondary_concepts = spec.get("expected_secondary_concepts", [])
    excluded_terms = spec.get("excluded_terms", [])

    # evaluate core concept matching (against all discovered)
    matched_core: list[str] = []
    missed_core: list[str] = []
    details: list[dict[str, Any]] = []

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

    # build golden name set for unexpected detection
    golden_all_names = _build_golden_name_set(core_concepts, secondary_concepts)

    # unexpected selected (all discovered, not in golden)
    unexpected_selected = _find_unexpected(
        discovery_result.candidates, golden_all_names,
    )

    # compute all-candidates precision/recall
    total_core = len(core_concepts)
    matched_count = len(matched_core)
    unexpected_count = len(unexpected_selected)
    precision_denom = matched_count + unexpected_count
    precision_like = matched_count / precision_denom if precision_denom > 0 else 0.0
    recall_like = matched_count / total_core if total_core > 0 else 0.0

    # --- selected top N analysis ---
    selected_names = {c.name.lower() for c in selected}
    selected_canonical = [c.name for c in selected]
    selected_with_scores = [
        {
            "name": c.name,
            "score": c.score_breakdown.total,
            "category": c.category,
            "confidence": c.confidence,
            "semantic_role": c.semantic_role,
            "selection_reason": c.selection_reason,
            "aliases": c.aliases[:5],
        }
        for c in selected
    ]

    # selected precision: how many selected are golden (core or secondary)?
    selected_golden_count = 0
    selected_unexpected: list[str] = []
    for c in selected:
        norm = c.name.lower()
        if norm in golden_all_names:
            selected_golden_count += 1
        elif any(a.lower() in golden_all_names for a in (c.aliases or [])):
            selected_golden_count += 1
        else:
            selected_unexpected.append(c.name)

    sel_prec = selected_golden_count / len(selected) if selected else 0.0

    # selected recall: how many golden core concepts appear in selected?
    selected_core_matched = 0
    for entry in core_concepts:
        name = entry["concept"]
        aliases = entry.get("aliases", [])
        if _is_in_selected(name, aliases, selected):
            selected_core_matched += 1

    sel_recall = selected_core_matched / total_core if total_core > 0 else 0.0

    # excluded terms that leaked into selected
    excluded_names = {e["term"].lower() for e in excluded_terms}
    excluded_leaked = sorted(selected_names & excluded_names)

    # rejected top terms (high score but filtered by category)
    rejected = []
    for c in discovery_result.candidates[:30]:
        if c not in selected and c.category not in SELECTABLE_CATEGORIES:
            rejected.append({
                "name": c.name,
                "score": str(c.score_breakdown.total),
                "category": c.category,
                "reason": "Filtered: category={}".format(c.category),
            })

    notes = []
    if missed_core:
        notes.append("Missed core concepts: {}".format(", ".join(missed_core)))
    if excluded_leaked:
        notes.append("Excluded terms leaked into selected: {}".format(", ".join(excluded_leaked)))

    return EvalResult(
        schema_version=EVAL_SCHEMA_VERSION,
        project_id=spec.get("project_id", project_root.name),
        project_root=str(project_root),
        golden_spec_path=str(golden_spec_path),
        discovery_version=discovery_result.schema_version,
        max_concepts=max_concepts,
        selected_concepts=[c.name for c in selected],
        selected_canonical_concepts=selected_canonical,
        selected_with_scores=selected_with_scores,
        rejected_top_terms=rejected,
        excluded_terms_selected=excluded_leaked,
        golden_core_count=total_core,
        golden_secondary_count=len(secondary_concepts),
        matched_core=matched_core,
        missed_core=missed_core,
        matched_secondary=matched_secondary,
        unexpected_selected=unexpected_selected,
        precision_like=round(precision_like, 4),
        recall_like=round(recall_like, 4),
        selected_precision_like=round(sel_prec, 4),
        selected_recall_like=round(sel_recall, 4),
        notes=notes,
        details=details,
    )


def generate_eval_report(result: EvalResult) -> str:
    """Generate a human-readable markdown evaluation report.

    Parameters
    ----------
    result : EvalResult
        The evaluation result to report on.

    Returns
    -------
    str
        Markdown-formatted evaluation report.
    """
    lines: list[str] = []
    lines.append("# Discovery Evaluation Report")
    lines.append("")
    lines.append("**Project:** {}".format(result.project_id))
    lines.append("**Golden Spec:** {}".format(result.golden_spec_path))
    lines.append("**Discovery Version:** {}".format(result.discovery_version))
    lines.append("**Max Concepts:** {}".format(result.max_concepts))
    lines.append("")

    # Overall metrics
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append("| Golden Core Concepts | {} |".format(result.golden_core_count))
    lines.append("| Golden Secondary Concepts | {} |".format(result.golden_secondary_count))
    lines.append("| Matched Core | {} / {} |".format(len(result.matched_core), result.golden_core_count))
    lines.append("| Matched Secondary | {} / {} |".format(len(result.matched_secondary), result.golden_secondary_count))
    lines.append("| Recall (all candidates) | {:.1%} |".format(result.recall_like))
    lines.append("| Precision (all candidates) | {:.1%} |".format(result.precision_like))
    lines.append("| **Selected Precision (top {})** | **{:.1%}** |".format(result.max_concepts, result.selected_precision_like))
    lines.append("| **Selected Recall (top {})** | **{:.1%}** |".format(result.max_concepts, result.selected_recall_like))
    lines.append("")

    # Missed core
    if result.missed_core:
        lines.append("## Missed Core Concepts")
        lines.append("")
        for mc in result.missed_core:
            lines.append("- {}".format(mc))
        lines.append("")

    # Selected concepts
    lines.append("## Selected Concepts (top {})".format(result.max_concepts))
    lines.append("")
    lines.append("| # | Concept | Score | Category | Confidence | Role |")
    lines.append("|---|---------|-------|----------|------------|------|")
    for i, sc in enumerate(result.selected_with_scores, 1):
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            i, sc["name"], sc["score"], sc["category"], sc["confidence"], sc["semantic_role"]))
    lines.append("")

    # Excluded terms that leaked
    if result.excluded_terms_selected:
        lines.append("## Excluded Terms Leaked into Selected")
        lines.append("")
        for t in result.excluded_terms_selected:
            lines.append("- {}".format(t))
        lines.append("")

    # Notes
    if result.notes:
        lines.append("## Notes")
        lines.append("")
        for note in result.notes:
            lines.append("- {}".format(note))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_golden_spec(path: Path) -> dict[str, Any]:
    """Load and validate a golden concepts JSON file."""
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
) -> dict[str, Any]:
    """Try to match a golden concept against discovered concepts."""
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
    core_concepts: list[dict[str, Any]],
    secondary_concepts: list[dict[str, Any]],
) -> set[str]:
    """Build a set of all golden concept names and aliases (lowercase)."""
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
    """Find discovered concepts not present in the golden spec at all."""
    unexpected: list[str] = []
    for candidate in candidates:
        norm = candidate.name.lower()
        if norm in golden_names:
            continue
        cand_aliases = getattr(candidate, "aliases", None) or []
        if any(a.lower() in golden_names for a in cand_aliases):
            continue
        unexpected.append(candidate.name)
    return unexpected


def _is_in_selected(
    golden_name: str,
    golden_aliases: list[str],
    selected: list[ConceptCandidate],
) -> bool:
    """Check if a golden concept appears in the selected top N."""
    names_to_check = {golden_name.lower()}
    names_to_check.update(a.lower() for a in golden_aliases)

    for c in selected:
        if c.name.lower() in names_to_check:
            return True
        for a in (c.aliases or []):
            if a.lower() in names_to_check:
                return True
        # Also check if selected concept's name/aliases match golden name
        if c.name.lower() == golden_name.lower():
            return True
    return False
