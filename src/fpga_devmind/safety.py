"""Safety guards for filesystem writes."""

from __future__ import annotations

import tempfile
from pathlib import Path


def ensure_safe_output_dir(path: Path, label: str = "output") -> Path:
    """Validate that generated artifacts stay in a temp area.

    fpga_devmind must not write into fpga_project_* target projects. During P1a
    and P1a+ all generated artifacts are expected to live under a temporary
    directory.
    """

    resolved = path.expanduser().resolve(strict=False)
    if any(part.startswith("fpga_project_") for part in resolved.parts):
        raise ValueError(f"{label} path must not be inside an fpga_project_* tree: {resolved}")

    temp_roots = {
        Path("/tmp").resolve(strict=False),
        Path("/private/tmp").resolve(strict=False),
        Path(tempfile.gettempdir()).resolve(strict=False),
    }
    if not any(_is_relative_to(resolved, root) for root in temp_roots):
        allowed = ", ".join(str(root) for root in sorted(temp_roots))
        raise ValueError(f"{label} path must be under a temporary output root ({allowed}): {resolved}")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
