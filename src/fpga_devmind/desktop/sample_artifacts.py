"""Sample artifact discovery helper for the Desktop Agent Shell (T014).

Scans known temp directories for P1a/P1b artifact bundles produced by
previous CLI runs.  Read-only: does not create, modify, or delete files.

Typical usage::

    from fpga_devmind.desktop.sample_artifacts import find_recent_artifact_bundles

    bundles = find_recent_artifact_bundles()
    if bundles:
        print("Most recent:", bundles[0].path)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifact_loader import detect_bundle_type


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class ArtifactBundleInfo:
    """Information about a discovered artifact bundle."""

    path: Path
    bundle_type: str  # "p1b" | "p1a" | "unknown"
    mtime: float  # os.stat().st_mtime


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASE_DIRS: list[Path] = [
    Path("/tmp/fpga_devmind"),
    Path("/private/tmp/fpga_devmind"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_recent_artifact_bundles(
    base_dirs: list[Path] | None = None,
) -> list[ArtifactBundleInfo]:
    """Discover artifact bundles under *base_dirs*, sorted newest-first.

    Parameters
    ----------
    base_dirs :
        Directories to scan.  Defaults to ``/tmp/fpga_devmind`` and
        ``/private/tmp/fpga_devmind``.  Non-existent or unreadable
        directories are silently skipped.

    Returns
    -------
    list[ArtifactBundleInfo]
        Bundles sorted by modification time (newest first).
    """
    dirs = base_dirs if base_dirs is not None else _DEFAULT_BASE_DIRS
    results: list[ArtifactBundleInfo] = []

    for base in dirs:
        if not base.is_dir():
            continue
        try:
            entries = list(base.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            btype = detect_bundle_type(entry)
            if btype == "unknown":
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            results.append(
                ArtifactBundleInfo(path=entry, bundle_type=btype, mtime=mtime)
            )

    results.sort(key=lambda info: info.mtime, reverse=True)
    return results
