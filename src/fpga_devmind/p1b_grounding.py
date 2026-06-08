"""P1b grounding checker and report generator.

Inspects T005 MappingClaim objects for overclaiming, missing evidence,
and weak-bridge issues.  Produces structured GroundingDiagnostic items
and a summary.  This is NOT a PASS/HOLD auditor — it serves the
understanding layer's traceability and uncertainty annotation.

T006 scope: grounding diagnostics only.
Does not modify claims, does not write files, does not run Vivado.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from fpga_devmind.p1b_mapping import MappingClaimResult
from fpga_devmind.p1b_schema import (
    BRIDGE_KIND_EXPLICIT_SOURCE,
    BRIDGE_KIND_NAMING_ONLY,
    WEAK_BRIDGE_KINDS,
    MappingClaim,
)
from fpga_devmind.schema import GroundingDiagnostic

GROUNDING_REPORT_SCHEMA_VERSION = "p1b-grounding-report-0.1"

# ---------------------------------------------------------------------------
# Output data structures
# ---------------------------------------------------------------------------


@dataclass
class GroundingSummary:
    """Summary counts for the grounding report."""

    mapping_claims: int = 0
    blocking_diagnostics: int = 0
    unsupported_confirmed_mappings: int = 0
    naming_only_supported_mappings: int = 0
    one_sided_mapping_evidence: int = 0


@dataclass
class GroundingReport:
    """Structured output of the P1b grounding checker."""

    schema_version: str = GROUNDING_REPORT_SCHEMA_VERSION
    diagnostics: list[GroundingDiagnostic] = field(default_factory=list)
    summary: GroundingSummary = field(default_factory=GroundingSummary)

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "schema_version": self.schema_version,
            "diagnostics": [asdict(d) for d in self.diagnostics],
            "summary": asdict(self.summary),
        }


# ---------------------------------------------------------------------------
# Internal check helpers
# ---------------------------------------------------------------------------

_ORDINAL_COUNTER = [0]


def _next_diag_id() -> str:
    _ORDINAL_COUNTER[0] += 1
    return "GD_{:04d}".format(_ORDINAL_COUNTER[0])


def _reset_ordinal() -> None:
    _ORDINAL_COUNTER[0] = 0


def _check_unsupported_confirmed(
    claim: MappingClaim,
    diags: list[GroundingDiagnostic],
    summary: GroundingSummary,
) -> None:
    """Blocking: confirmed mapping lacks explicit bridge evidence."""
    if claim.confidence != "confirmed":
        return
    if claim.bridge_kind != BRIDGE_KIND_EXPLICIT_SOURCE:
        summary.unsupported_confirmed_mappings += 1
        summary.blocking_diagnostics += 1
        msg = (
            "Confirmed mapping '{}' lacks explicit_source_bridge "
            "(bridge_kind is '{}')."
        ).format(claim.claim_id, claim.bridge_kind)
        diags.append(
            GroundingDiagnostic(
                diagnostic_id=_next_diag_id(),
                target_claim_id=claim.claim_id,
                target_output_id=None,
                severity="blocking",
                issue_type="unsupported_confirmed_mapping",
                recommended_action=(
                    "Downgrade to supported or inferred; "
                    "add explicit source bridge evidence."
                ),
                related_evidence_ids=claim.evidence_ids,
                message=msg,
            )
        )


def _check_missing_side(
    claim: MappingClaim,
    diags: list[GroundingDiagnostic],
    summary: GroundingSummary,
) -> None:
    """Blocking: supported/confirmed missing L5/L6 or RTL evidence."""
    if claim.confidence not in ("supported", "confirmed"):
        return
    missing: list[str] = []
    if not claim.l5_l6_evidence_ids:
        missing.append("L5/L6")
    if not claim.rtl_evidence_ids:
        missing.append("RTL")
    if not missing:
        return
    summary.blocking_diagnostics += 1
    missing_str = ", ".join(missing)
    action = (
        "Downgrade to unknown/inferred; add "
        "required_missing_evidence for: {}."
    ).format(missing_str)
    msg = (
        "Mapping '{}' (confidence '{}') is missing {} "
        "evidence side(s)."
    ).format(claim.claim_id, claim.confidence, missing_str)
    diags.append(
        GroundingDiagnostic(
            diagnostic_id=_next_diag_id(),
            target_claim_id=claim.claim_id,
            target_output_id=None,
            severity="blocking",
            issue_type="mapping_missing_l6_or_rtl_side",
            recommended_action=action,
            related_evidence_ids=claim.evidence_ids,
            message=msg,
        )
    )


def _check_naming_only_supported(
    claim: MappingClaim,
    diags: list[GroundingDiagnostic],
    summary: GroundingSummary,
) -> None:
    """Blocking: supported mapping with naming-only bridge."""
    if claim.confidence != "supported":
        return
    if claim.bridge_kind != BRIDGE_KIND_NAMING_ONLY:
        return
    summary.naming_only_supported_mappings += 1
    summary.blocking_diagnostics += 1
    msg = (
        "Mapping '{}' has 'supported' confidence but "
        "bridge_kind is 'naming_only'."
    ).format(claim.claim_id)
    diags.append(
        GroundingDiagnostic(
            diagnostic_id=_next_diag_id(),
            target_claim_id=claim.claim_id,
            target_output_id=None,
            severity="blocking",
            issue_type="naming_only_supported_mapping",
            recommended_action=(
                "Downgrade to inferred; naming-only "
                "bridge cannot support 'supported' confidence."
            ),
            related_evidence_ids=claim.evidence_ids,
            message=msg,
        )
    )


def _check_no_evidence(
    claim: MappingClaim,
    diags: list[GroundingDiagnostic],
    summary: GroundingSummary,
) -> None:
    """Blocking: mapping claim has no evidence at all.

    Unknown claims with non-empty required_missing_evidence are
    legitimate unresolved/unknown expressions — not a blocking
    overclaim.  supported/confirmed/inferred with empty evidence_ids
    is always blocking.
    """
    if claim.evidence_ids:
        return
    if claim.confidence == "unknown" and claim.required_missing_evidence:
        return
    summary.blocking_diagnostics += 1
    diags.append(
        GroundingDiagnostic(
            diagnostic_id=_next_diag_id(),
            target_claim_id=claim.claim_id,
            target_output_id=None,
            severity="blocking",
            issue_type="mapping_claim_without_evidence",
            recommended_action="Add evidence or remove claim.",
            related_evidence_ids=[],
            message="Mapping '{}' has no evidence_ids.".format(
                claim.claim_id
            ),
        )
    )


def _check_one_sided(
    claim: MappingClaim,
    diags: list[GroundingDiagnostic],
    summary: GroundingSummary,
) -> None:
    """Non-blocking: one side missing with required_missing_evidence."""
    if claim.confidence not in ("unknown", "inferred"):
        return
    has_l5_l6 = bool(claim.l5_l6_evidence_ids)
    has_rtl = bool(claim.rtl_evidence_ids)
    if has_l5_l6 and has_rtl:
        return
    # Both sides missing → not one_sided; unresolved/unknown
    if not has_l5_l6 and not has_rtl:
        return
    # Exactly one side missing
    if not claim.required_missing_evidence:
        # Should not happen (schema enforces), but defensive check
        return
    summary.one_sided_mapping_evidence += 1
    missing_side = "L5/L6" if not has_l5_l6 else "RTL"
    action = (
        "Gather {} evidence to strengthen mapping."
    ).format(missing_side)
    msg = (
        "Mapping '{}' (confidence '{}') is one-sided: "
        "missing {} evidence. required_missing_evidence provided."
    ).format(claim.claim_id, claim.confidence, missing_side)
    diags.append(
        GroundingDiagnostic(
            diagnostic_id=_next_diag_id(),
            target_claim_id=claim.claim_id,
            target_output_id=None,
            severity="non_blocking",
            issue_type="one_sided_mapping_evidence",
            recommended_action=action,
            related_evidence_ids=claim.evidence_ids,
            message=msg,
        )
    )


def _check_weak_bridge(
    claim: MappingClaim,
    diags: list[GroundingDiagnostic],
    summary: GroundingSummary,  # pyright: ignore[reportUnusedParameter]
) -> None:
    """Non-blocking: bridge kind is too weak for the claimed confidence."""
    if claim.confidence not in ("supported", "confirmed"):
        return
    if claim.bridge_kind not in WEAK_BRIDGE_KINDS:
        return
    msg = (
        "Mapping '{}' uses weak bridge_kind '{}' for "
        "confidence '{}'."
    ).format(claim.claim_id, claim.bridge_kind, claim.confidence)
    diags.append(
        GroundingDiagnostic(
            diagnostic_id=_next_diag_id(),
            target_claim_id=claim.claim_id,
            target_output_id=None,
            severity="non_blocking",
            issue_type="weak_bridge_evidence",
            recommended_action=(
                "Strengthen bridge evidence or downgrade confidence."
            ),
            related_evidence_ids=claim.bridge_evidence_ids,
            message=msg,
        )
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_grounding(
    mapping_result: MappingClaimResult,
) -> GroundingReport:
    """Run grounding checks on a MappingClaimResult.

    Parameters
    ----------
    mapping_result : MappingClaimResult
        Output from T005 ``build_mapping_claims()``.

    Returns
    -------
    GroundingReport
        Structured diagnostics and summary.  Blocking diagnostics
        indicate overclaims that must be fixed; non-blocking indicate
        uncertainty requiring acknowledgment.
    """
    _reset_ordinal()
    report = GroundingReport()
    report.summary.mapping_claims = len(mapping_result.mapping_claims)

    for claim in mapping_result.mapping_claims:
        _check_no_evidence(claim, report.diagnostics, report.summary)
        _check_unsupported_confirmed(
            claim, report.diagnostics, report.summary
        )
        _check_missing_side(claim, report.diagnostics, report.summary)
        _check_naming_only_supported(
            claim, report.diagnostics, report.summary
        )
        _check_one_sided(claim, report.diagnostics, report.summary)
        _check_weak_bridge(claim, report.diagnostics, report.summary)

    return report
