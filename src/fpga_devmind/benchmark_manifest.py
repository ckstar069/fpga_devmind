"""Benchmark manifest generator for FPGA project directories (T035).

Scans fpga_project_* directories and generates a benchmark manifest
with per-project metadata and auto-discovered concept candidates.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .p1b_discovery import discover_concepts


def generate_benchmark_manifest(
    projects_parent: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    """Scan fpga_project_* directories and generate benchmark manifest.

    Parameters
    ----------
    projects_parent : Path
        Parent directory containing fpga_project_* directories.
    output_dir : Path
        Output directory for the manifest file.

    Returns
    -------
    list[dict[str, Any]]
        List of project manifest entries.
    """
    parent = projects_parent.resolve()
    if not parent.is_dir():
        raise ValueError("Projects parent directory does not exist: {}".format(parent))

    manifest: list[dict[str, Any]] = []

    for entry in sorted(parent.iterdir()):
        if not entry.is_dir():
            continue
        if not entry.name.startswith("fpga_project_"):
            continue

        project_root = entry
        project_id = entry.name

        # Check section existence
        has_L5 = (project_root / "src" / "python_model" / "L5_fixedpoint").is_dir()
        has_L6 = (project_root / "src" / "python_model" / "L6_resource_opt").is_dir()
        has_RTL = (project_root / "src" / "verilog_model" / "rtl").is_dir()
        has_tests = (project_root / "tests").is_dir()

        # Run discovery (best-effort, skip on failure)
        candidates = []
        recommended = []
        discovery_status = "not_run"

        if has_L5 or has_L6 or has_RTL:
            try:
                result = discover_concepts(project_root)
                candidates = [asdict(c) for c in result.candidates]
                recommended = [c.name for c in result.candidates[:12]]
                discovery_status = "ok"
            except Exception as exc:  # noqa: BLE001
                discovery_status = "error: {}".format(exc)

        entry_dict = {
            "project_id": project_id,
            "project_root": str(project_root),
            "has_L5": has_L5,
            "has_L6": has_L6,
            "has_RTL": has_RTL,
            "has_tests": has_tests,
            "candidate_count": len(candidates),
            "recommended_concepts": recommended,
            "discovery_status": discovery_status,
            "bundle_path": "",  # Filled after trace
        }

        manifest.append(entry_dict)

    # Write manifest
    manifest_path = output_dir / "benchmark_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return manifest
