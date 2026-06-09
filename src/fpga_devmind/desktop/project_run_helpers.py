"""Pure Python helpers for the desktop project run workflow (T026).

No PySide6 dependency.  Deterministic, testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_CONCEPTS = "peak_idx,cfo,smooth_detect"

# Detect macOS /private/tmp prefix and adapt
if Path("/private/tmp").exists():
    _DEFAULT_OUTPUT_DIR = Path("/private/tmp/fpga_devmind/gui_project_run")
else:
    _DEFAULT_OUTPUT_DIR = Path("/tmp/fpga_devmind/gui_project_run")

_DEFAULT_PROJECT_ROOT = Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm")


# ---------------------------------------------------------------------------
# Concepts parsing
# ---------------------------------------------------------------------------


def parse_concepts(text: str) -> list[str]:
    """Parse a comma-separated concept string into a deduplicated list.

    Empty items and whitespace are stripped.  Returns empty list when
    *text* is empty or contains only whitespace.
    """
    if not text or not text.strip():
        return []
    parts = [p.strip() for p in text.split(",")]
    seen: set[str] = set()
    result: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def get_default_project_root() -> Path:
    """Return the default FPGA project root if it exists, else empty path."""
    if _DEFAULT_PROJECT_ROOT.exists():
        return _DEFAULT_PROJECT_ROOT
    return Path("")


def get_default_concepts() -> str:
    """Return the default comma-separated concepts string."""
    return _DEFAULT_CONCEPTS


def get_default_output_dir() -> Path:
    """Return the default output directory for GUI project runs."""
    return _DEFAULT_OUTPUT_DIR


def validate_run_params(project_root: Path, concepts: list[str]) -> str | None:
    """Validate project run parameters.

    Returns an error message string if invalid, or *None* if valid.
    """
    if not project_root or not str(project_root).strip() or str(project_root).strip() == ".":
        return "项目路径不能为空。"
    if not project_root.exists():
        return "项目路径不存在：{}".format(project_root)
    if not concepts:
        return "概念列表不能为空。请输入至少一个 concept。"
    return None


def format_run_status(metadata: dict[str, Any]) -> str:
    """Format run metadata into a human-readable status string."""
    lines: list[str] = []
    status = metadata.get("status", "unknown")
    lines.append("状态：{}".format(status))

    processed = metadata.get("concepts_processed", [])
    failed = metadata.get("concepts_failed", [])
    lines.append("概念：{} 个处理".format(len(processed)))
    if failed:
        lines.append("  失败：{}".format(", ".join(failed)))

    lines.append("Mapping claims：{}".format(metadata.get("mapping_claims", 0)))
    lines.append("Evidence items：{}".format(metadata.get("evidence_items", 0)))

    elapsed = metadata.get("elapsed_seconds")
    if elapsed is not None:
        lines.append("耗时：{:.3f} 秒".format(elapsed))

    out_dir = metadata.get("output_dir", "")
    if out_dir:
        lines.append("输出目录：{}".format(out_dir))

    return "\n".join(lines)
