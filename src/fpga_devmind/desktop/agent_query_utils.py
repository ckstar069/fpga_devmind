"""Shared query utilities for T011/T012.

Deduplication, keyword matching, and ID extraction helpers used by both
``agent_panel_models`` and ``agent_plan_models``.
"""

from __future__ import annotations

import re
from typing import Any


def has_any(text: str, terms: list[str]) -> bool:
    """Return True if *text* contains any of *terms*."""
    return any(term in text for term in terms)


def deduplicate_diagnostics(
    graph: dict[str, Any] | None,  # pyright: ignore[reportExplicitAny]
    grounding: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """Merge and de-duplicate diagnostics from graph and grounding report.

    Primary key is ``diagnostic_id``.  If missing, fallback to
    ``(target_claim_id, issue_type, message)``.
    """
    seen: set[str] = set()
    result: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]

    def _key(diag: dict[str, Any]) -> str:  # pyright: ignore[reportExplicitAny]
        did = diag.get("diagnostic_id")
        if did:
            return str(did)
        return "{}|{}|{}".format(
            diag.get("target_claim_id") or "",
            diag.get("issue_type") or "",
            diag.get("message") or "",
        )

    for source in (
        (graph or {}).get("grounding_diagnostics", []),
        grounding.get("diagnostics", []),
    ):
        for diag in source:
            if isinstance(diag, dict):
                k = _key(diag)
                if k not in seen:
                    seen.add(k)
                    result.append(diag)
    return result


_CLAIM_ID_RE = re.compile(r"\b(MC_[A-Za-z0-9_]+)\b", re.IGNORECASE)
_EVIDENCE_ID_RE = re.compile(r"\b(E:[A-Za-z0-9_:/-]+)\b", re.IGNORECASE)


def extract_claim_id(text: str) -> str | None:
    """Extract a claim id (``MC_*``) from *text*."""
    m = _CLAIM_ID_RE.search(text)
    return m.group(1) if m else None


def extract_evidence_id(text: str) -> str | None:
    """Extract an evidence id (``E:*``) from *text*."""
    m = _EVIDENCE_ID_RE.search(text)
    return m.group(1) if m else None
