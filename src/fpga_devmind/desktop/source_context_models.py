"""Source context viewer for evidence items (T029).

Pure Python — no PySide6.  Read-only file access.  No LLM / API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.desktop.artifact_loader import (
    ArtifactBundle,
    get_graph,
    get_project_graph,
    get_project_index,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONTEXT_LINES = 80
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*(.+)", re.IGNORECASE),
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*(.+)", re.IGNORECASE),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(bearer\s+[a-zA-Z0-9_\-]{20,})", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# View models
# ---------------------------------------------------------------------------


@dataclass
class SourceLine:
    """A single line of source code with metadata."""

    line_no: int = 0
    text: str = ""
    is_evidence_line: bool = False


@dataclass
class SourceContextViewModel:
    """View model for source context around an evidence item."""

    is_loaded: bool = False
    load_error: str | None = None
    evidence_id: str = ""
    file_path: str = ""
    source_type: str = ""
    symbol: str = ""
    evidence_strength: str = ""
    start_line: int = 0
    end_line: int = 0
    context_start_line: int = 0
    context_end_line: int = 0
    lines: list[SourceLine] = field(default_factory=list)
    why_this_matters: str = ""
    limitations: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_source_context_for_evidence(
    bundle: ArtifactBundle,
    evidence_id: str,
    context_lines: int = 5,
) -> SourceContextViewModel:
    """Build source context for *evidence_id* in *bundle*.

    Reads the source file referenced by the evidence item and returns
    the surrounding context lines.  Never modifies files.
    """
    if not bundle.is_complete:
        return _error_vm(evidence_id, "Bundle incomplete.")

    if not evidence_id:
        return _error_vm(evidence_id, "Evidence ID is empty.")

    # 1. Find evidence metadata.
    meta = _find_evidence_metadata(bundle, evidence_id)
    if meta is None:
        return _error_vm(evidence_id, "Evidence '{}' not found in bundle.".format(evidence_id))

    file_path = meta.get("file_path", "")
    if not file_path:
        return _error_vm(
            evidence_id,
            "Evidence '{}' does not reference a file path.".format(evidence_id),
        )

    source_type = meta.get("source_type", "")
    symbol = meta.get("symbol", "")
    strength = meta.get("strength", "unknown")

    # 2. Resolve line range.
    start_line, end_line = _resolve_line_range(meta, evidence_id)

    # 3. Read file.
    path = Path(file_path)
    if not path.exists():
        # Try relative to bundle directory.
        alt_path = bundle.directory / file_path.lstrip("/")
        if alt_path.exists():
            path = alt_path
        else:
            return SourceContextViewModel(
                is_loaded=False,
                load_error="File not found: {}".format(file_path),
                evidence_id=evidence_id,
                file_path=file_path,
                source_type=source_type,
                symbol=symbol,
                evidence_strength=strength,
                start_line=start_line,
                end_line=end_line,
                why_this_matters=_why_this_matters(source_type, symbol, strength),
                limitations="Artifact 包含文件路径但文件当前不可访问。",
            )

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return _error_vm(evidence_id, "无法读取文件 {}: {}".format(file_path, exc))

    total_lines = len(raw_lines)

    # 4. Determine context range.
    if start_line > 0 and end_line >= start_line:
        ctx_start = max(1, start_line - context_lines)
        ctx_end = min(total_lines, end_line + context_lines)
    elif start_line > 0:
        ctx_start = max(1, start_line - context_lines)
        ctx_end = min(total_lines, start_line + context_lines)
    else:
        # No line numbers — show first few lines as fallback.
        ctx_start = 1
        ctx_end = min(total_lines, 10)

    # Enforce max context.
    if ctx_end - ctx_start + 1 > _MAX_CONTEXT_LINES:
        ctx_end = ctx_start + _MAX_CONTEXT_LINES - 1

    # 5. Build SourceLine list.
    lines: list[SourceLine] = []
    for i in range(ctx_start, ctx_end + 1):
        idx = i - 1  # 0-based
        if idx < 0 or idx >= total_lines:
            continue
        text = raw_lines[idx]
        text = _mask_secrets(text)
        is_ev = start_line > 0 and start_line <= i <= end_line
        lines.append(SourceLine(line_no=i, text=text, is_evidence_line=is_ev))

    limitations = ""
    if start_line == 0:
        limitations = "Artifact 当前未提供行号/范围信息，仅显示文件开头。"
    elif ctx_end - ctx_start + 1 >= _MAX_CONTEXT_LINES:
        limitations = "上下文行数已达上限 ({} 行)，未显示完整范围。".format(_MAX_CONTEXT_LINES)

    return SourceContextViewModel(
        is_loaded=True,
        evidence_id=evidence_id,
        file_path=str(path),
        source_type=source_type,
        symbol=symbol,
        evidence_strength=strength,
        start_line=start_line,
        end_line=end_line,
        context_start_line=ctx_start,
        context_end_line=ctx_end,
        lines=lines,
        why_this_matters=_why_this_matters(source_type, symbol, strength),
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error_vm(evidence_id: str, message: str) -> SourceContextViewModel:
    return SourceContextViewModel(
        is_loaded=False,
        load_error=message,
        evidence_id=evidence_id,
    )


def _find_evidence_metadata(
    bundle: ArtifactBundle, evidence_id: str
) -> dict[str, Any] | None:
    """Return evidence metadata dict or None."""
    if bundle.bundle_type == "project":
        idx = get_project_index(bundle) or {}
        ev_index = idx.get("evidence_index", {})
        if isinstance(ev_index, dict):
            item = ev_index.get(evidence_id)
            if isinstance(item, dict):
                return item
        # Also check rtl nodes in graph (fallback for RTL evidence rows).
        graph = get_project_graph(bundle)
        if graph:
            for n in graph.get("nodes", []):
                if n.get("node_id") == evidence_id:
                    return {
                        "file_path": n.get("file_path", ""),
                        "symbol": n.get("label", ""),
                        "source_type": n.get("kind", "rtl"),
                        "strength": n.get("confidence", "inferred"),
                    }
        return None

    if bundle.bundle_type == "p1b":
        graph = get_graph(bundle)
        if graph:
            ev_items = graph.get("evidence_items", {})
            if isinstance(ev_items, dict):
                item = ev_items.get(evidence_id)
                if isinstance(item, dict):
                    return item
        return None

    return None


def _resolve_line_range(meta: dict[str, Any], evidence_id: str) -> tuple[int, int]:
    """Return (start_line, end_line).  0 means unknown."""
    # Direct fields take priority.
    s = meta.get("start_line")
    e = meta.get("end_line")
    if isinstance(s, int) and s > 0:
        start = s
        end = e if isinstance(e, int) and e >= start else start
        return start, end

    # Parse from evidence_id like :399-473: or :408-412:
    m = re.search(r":(\d+)-(\d+):", evidence_id)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Single line pattern like :47:
    m = re.search(r":(\d+)(?::|$)", evidence_id)
    if m:
        line = int(m.group(1))
        return line, line

    return 0, 0


def _mask_secrets(text: str) -> str:
    """Mask potential secrets in source code display."""
    for pat in _SECRET_PATTERNS:
        match = pat.search(text)
        if match:
            full = match.group(0)
            secret = match.group(2) if len(match.groups()) >= 2 else match.group(1)
            if secret and len(secret) > 4:
                masked = secret[:2] + "***"
                text = text.replace(secret, masked, 1)
    return text


def _why_this_matters(source_type: str, symbol: str, strength: str) -> str:
    """Generate a short explanation of why this evidence matters."""
    parts: list[str] = []
    if "rtl" in source_type.lower():
        parts.append("这是 RTL 侧证据")
    elif "concept" in source_type.lower() or "l5" in source_type.lower() or "l6" in source_type.lower():
        parts.append("这是 L5/L6 概念侧证据")
    else:
        parts.append("这是桥接/映射证据")

    if symbol:
        parts.append("，符号 '{}'".format(symbol))

    if strength == "strong":
        parts.append("。强度为 strong，可直接支撑 mapping claim。")
    elif strength == "medium":
        parts.append("。强度为 medium，需要额外上下文确认。")
    elif strength == "weak":
        parts.append("。强度为 weak，仅供参考。")
    else:
        parts.append("。")

    return "".join(parts)
