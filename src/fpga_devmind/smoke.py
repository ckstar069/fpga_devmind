"""P1a smoke validation over representative read-only sample projects."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .p1a import run_p1a
from .query import check_freshness
from .safety import ensure_safe_output_dir


DEFAULT_SMOKE_OUT = Path("/tmp/fpga_devmind/p1a_smoke")


@dataclass(frozen=True)
class SmokeSample:
    sample_id: str
    project_root: Path
    stage_id: str
    out_dir_name: str


DEFAULT_SAMPLES = [
    SmokeSample(
        sample_id="coarse_sync_glm_l6",
        project_root=Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"),
        stage_id="L6_resource_opt",
        out_dir_name="coarse_sync_glm_l6",
    ),
    SmokeSample(
        sample_id="fine_cfo_l6",
        project_root=Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_fine_cfo"),
        stage_id="L6_resource_opt",
        out_dir_name="fine_cfo_l6",
    ),
]


def run_smoke(out_root: Path = DEFAULT_SMOKE_OUT) -> dict[str, Any]:
    out_root = ensure_safe_output_dir(out_root, "P1a smoke output")
    out_root.mkdir(parents=True, exist_ok=True)
    results = []
    for sample in DEFAULT_SAMPLES:
        sample_out = out_root / sample.out_dir_name
        if not sample.project_root.exists():
            results.append(
                {
                    "sample_id": sample.sample_id,
                    "project_root": str(sample.project_root),
                    "stage_id": sample.stage_id,
                    "artifact_dir": str(sample_out),
                    "status": "skipped",
                    "reason": "project_root_missing",
                    "claims": 0,
                    "evidence_items": 0,
                    "uncertainty_notes": 0,
                    "blocking_diagnostics": 0,
                    "freshness_status": "unknown",
                }
            )
            continue

        try:
            graph = run_p1a(sample.project_root, sample_out)
            blocking = [d for d in graph.grounding_diagnostics if d.severity == "blocking"]
            freshness = check_freshness(sample_out)
            status = "passed" if not blocking and freshness["status"] == "current" else "failed"
            results.append(
                {
                    "sample_id": sample.sample_id,
                    "project_root": str(sample.project_root),
                    "stage_id": sample.stage_id,
                    "artifact_dir": str(sample_out),
                    "status": status,
                    "reason": "ok" if status == "passed" else "blocking_or_stale",
                    "claims": len(graph.candidate_claims),
                    "evidence_items": len(graph.evidence_items),
                    "uncertainty_notes": len(graph.uncertainty_notes),
                    "blocking_diagnostics": len(blocking),
                    "freshness_status": freshness["status"],
                    "source_snapshot_id": freshness.get("source_snapshot_id"),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "sample_id": sample.sample_id,
                    "project_root": str(sample.project_root),
                    "stage_id": sample.stage_id,
                    "artifact_dir": str(sample_out),
                    "status": "failed",
                    "reason": type(exc).__name__,
                    "message": str(exc),
                    "claims": 0,
                    "evidence_items": 0,
                    "uncertainty_notes": 0,
                    "blocking_diagnostics": 1,
                    "freshness_status": "unknown",
                }
            )

    report = {
        "schema_version": "p1a-smoke-0.1",
        "out_root": str(out_root),
        "samples": results,
        "summary": {
            "passed": sum(1 for r in results if r["status"] == "passed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
        },
    }
    (out_root / "smoke_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_root / "smoke_report.md").write_text(render_smoke_report(report), encoding="utf-8")
    return report


def render_smoke_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# P1a Smoke Report",
        "",
        f"Output root: `{report['out_root']}`",
        "",
        "## Summary",
        "",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Skipped: {summary['skipped']}",
        "",
        "## Samples",
        "",
    ]
    for result in report["samples"]:
        lines.append(f"- `{result['sample_id']}`: {result['status']}")
        lines.append(f"  - project: `{result['project_root']}`")
        lines.append(f"  - artifacts: `{result['artifact_dir']}`")
        lines.append(f"  - claims: {result['claims']}")
        lines.append(f"  - evidence_items: {result['evidence_items']}")
        lines.append(f"  - uncertainty_notes: {result.get('uncertainty_notes', 0)}")
        lines.append(f"  - blocking_diagnostics: {result['blocking_diagnostics']}")
        lines.append(f"  - freshness: {result['freshness_status']}")
        if result.get("message"):
            lines.append(f"  - message: {result['message']}")
    return "\n".join(lines) + "\n"


def smoke_exit_code(report: dict[str, Any]) -> int:
    return 1 if report["summary"]["failed"] else 0
