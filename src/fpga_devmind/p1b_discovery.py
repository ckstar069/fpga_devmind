"""P1b concept auto-discovery engine (T035).

Scans project source files (L5/L6 Python, RTL Verilog, tests) to discover
candidate concept names using AST and regex analysis.

Does not call LLM, does not modify target projects.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_collectors import _discover_py_files, _discover_rtl_files, _discover_test_files

DISCOVERY_SCHEMA_VERSION = "p1b-discovery-0.1"

# Generic names to exclude from concept candidates
GENERIC_STOP_WORDS: frozenset[str] = frozenset({
    "reset", "clk", "clock", "data", "valid", "ready", "enable",
    "input", "output", "init", "start", "stop", "count", "index",
    "result", "tmp", "temp", "val", "value", "bit", "width",
    "main", "test", "setup", "run", "config", "param", "parameter",
    "state", "next", "prev", "curr", "current", "self", "module",
    "write", "read", "addr", "address", "rst", "en", "ack",
    "__init__", "compute", "process", "handle", "callback",
    "get", "set", "put", "add", "remove", "update", "check",
    "new", "old", "buf", "buffer", "vec", "vector", "arr", "array",
    "num", "number", "size", "len", "length", "max", "min",
    "idx", "pos", "neg", "sign", "flag", "status", "err", "error", "errors",
    "assert", "print", "log", "debug", "info", "warn", "error_level",
    "true", "false", "none", "null", "zero", "one",
    "pi", "e", "i", "j", "k", "n", "m", "x", "y", "z",
    "cls", "obj", "item", "element", "key", "name", "type",
    "path", "file", "dir", "dir_path", "base", "root",
    # Additional generic names found in real discovery runs (T035)
    "min_len", "max_pos", "q_total_bits", "re_q", "im_q",
    "total_bits", "bits", "shift", "scale", "offset", "step",
    "sample", "samples", "range", "limit", "threshold_high", "threshold_low",
    "sum", "diff", "prod", "abs", "norm", "mean", "var", "std",
    "tol", "epsilon", "delta", "alpha", "beta", "gamma",
    "arg", "args", "kwargs", "return", "returns",
    # Verilog/RTL keywords and common signal names
    "signed", "wire", "reg", "logic", "always", "assign", "module",
    "input", "output", "inout", "parameter", "localparam",
    "signal", "rng", "acc", "rom", "ram", "fifo", "mux",
    "clk_en", "we", "re", "ce", "cs", "oe",
})

# FPGA/OFDM domain terms to prioritize even if they'd normally be filtered
DOMAIN_TERMS: frozenset[str] = frozenset({
    "cfo", "peak", "sync", "phase", "freq", "angle", "metric",
    "detect", "smooth", "corr", "threshold", "fft", "cordic",
    "crc", "ldpc", "viterbi", "agc", "rotator", "ofdm", "dft",
    "idft", "pilot", "channel", "equalize", "modulate", "demodulate",
    "interpolate", "decimate", "filter", "fir", "iir",
    "quantize", "saturation", "overflow", "underflow",
    "coarse", "fine", "tracking", "acquisition",
    "preamble", "cp", "cyclic", "prefix", "guard",
    "resource", "utilization", "timing", "latency",
    "pipeline", "through", "bypass", "bypass",
    "conjugate", "multiply", "accumulate", "mac",
    "mapper", "demapper", "encoder", "decoder",
    "scrambler", "descrambler", "interleaver",
})


@dataclass
class ConceptCandidate:
    """A discovered concept candidate."""
    name: str
    source_sections: list[str]  # ["L5_fixedpoint", "L6_resource_opt", "RTL", "tests"]
    occurrence_count: int
    confidence: str  # "high" | "medium" | "low"
    reason: str
    representative_files: list[str]
    likely_stage: str  # "L5", "L6", "RTL", "test", "cross_stage", "unknown"


@dataclass
class DiscoveryResult:
    """Result of concept auto-discovery."""
    schema_version: str = DISCOVERY_SCHEMA_VERSION
    project_id: str = ""
    project_root: str = ""
    candidates: list[ConceptCandidate] = field(default_factory=list)
    diagnostics: list[dict[str, str]] = field(default_factory=list)


# RTL regex patterns (from p1b_rtl.py)
_RE_MODULE = re.compile(r"^\s*module\s+(\w+)")
_RE_SIGNAL_DECL = re.compile(r"^\s*(?:input|output|inout|reg|wire|logic)\s+(?:\[\S+?\]\s+)?(\w+)")
_RE_PARAM = re.compile(r"^\s*(?:parameter|localparam)\s+.*?(\w+)\s*=")


def discover_concepts(project_root: Path) -> DiscoveryResult:
    """Scan all source sections for candidate concept names.

    Parameters
    ----------
    project_root : Path
        Root directory of the FPGA project.

    Returns
    -------
    DiscoveryResult
        Sorted list of concept candidates.
    """
    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError("Project root does not exist: {}".format(root))

    result = DiscoveryResult(
        project_id=root.name,
        project_root=str(root),
    )

    # Collect all symbol names from each section
    # name -> {section: count, files: set, ...}
    symbol_map: dict[str, dict[str, Any]] = {}

    # Scan L5
    l5_dir = root / "src" / "python_model" / "L5_fixedpoint"
    l5_files = _discover_py_files(l5_dir)
    _scan_python_files(l5_files, "L5_fixedpoint", symbol_map)

    # Scan L6
    l6_dir = root / "src" / "python_model" / "L6_resource_opt"
    l6_files = _discover_py_files(l6_dir)
    _scan_python_files(l6_files, "L6_resource_opt", symbol_map)

    # Scan RTL
    rtl_dir = root / "src" / "verilog_model" / "rtl"
    rtl_files = _discover_rtl_files(rtl_dir)
    _scan_rtl_files(rtl_files, symbol_map)

    # Scan tests
    test_files = _discover_test_files(root)
    _scan_python_files(test_files, "tests", symbol_map, is_test=True)

    # Build candidates
    for name, info in symbol_map.items():
        sections = list(info["sections"].keys())
        total_count = info["count"]
        files = sorted(info["files"])[:5]  # Keep top 5 representative files

        # Skip generic names
        if _is_generic(name):
            continue

        # Skip very short names (likely abbreviations)
        if len(name) < 3:
            continue

        # Skip names that are just numbers or underscores
        if name.replace("_", "").isdigit():
            continue

        # Compute confidence
        has_l5l6 = bool({"L5_fixedpoint", "L6_resource_opt"} & set(sections))
        has_rtl = "RTL" in sections
        has_test = "tests" in sections

        section_count = len(sections)

        if has_l5l6 and has_rtl:
            confidence = "high"
            reason = "Appears in both L5/L6 and RTL (cross-stage evidence)"
        elif section_count >= 3:
            confidence = "high"
            reason = "Appears in {} source sections".format(section_count)
        elif section_count >= 2 or total_count >= 3:
            confidence = "medium"
            if section_count >= 2:
                reason = "Appears in {} sections with {} occurrences".format(section_count, total_count)
            else:
                reason = "Appears {} times in {}".format(total_count, sections[0] if sections else "?")
        else:
            confidence = "low"
            reason = "Single occurrence in {}".format(sections[0] if sections else "?")

        # Boost domain terms
        if name.lower() in DOMAIN_TERMS and confidence == "low":
            confidence = "medium"
            reason = "FPGA/OFDM domain term: " + reason

        # Determine likely stage
        if has_l5l6 and has_rtl:
            likely_stage = "cross_stage"
        elif has_rtl:
            likely_stage = "RTL"
        elif has_l5l6:
            likely_stage = "L5" if "L5_fixedpoint" in sections else "L6"
        elif has_test:
            likely_stage = "test"
        else:
            likely_stage = "unknown"

        result.candidates.append(ConceptCandidate(
            name=name,
            source_sections=sections,
            occurrence_count=total_count,
            confidence=confidence,
            reason=reason,
            representative_files=files,
            likely_stage=likely_stage,
        ))

    # Sort: high confidence first, then by occurrence count desc
    conf_order = {"high": 0, "medium": 1, "low": 2}
    result.candidates.sort(key=lambda c: (conf_order.get(c.confidence, 3), -c.occurrence_count))

    return result


def _scan_python_files(
    files: list[str],
    section: str,
    symbol_map: dict[str, dict[str, Any]],
    is_test: bool = False,
) -> None:
    """Extract symbol names from Python files using AST."""
    for file_path in files:
        try:
            source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            name = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.ClassDef):
                name = node.name
            elif isinstance(node, ast.Assign):
                # Top-level or in-function assignments
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        name = target.id

            if name is None or _should_skip_name(name, is_test):
                continue

            _add_symbol(name, section, file_path, symbol_map)


def _scan_rtl_files(
    files: list[str],
    symbol_map: dict[str, dict[str, Any]],
) -> None:
    """Extract symbol names from RTL files using regex."""
    for file_path in files:
        try:
            lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        except (UnicodeDecodeError, OSError):
            continue

        for line in lines:
            # Module names
            m = _RE_MODULE.match(line)
            if m:
                _add_symbol(m.group(1), "RTL", file_path, symbol_map)
                continue

            # Signal declarations
            m = _RE_SIGNAL_DECL.match(line)
            if m:
                sig_name = m.group(1)
                # Extract meaningful part of signal name
                parts = sig_name.split("_")
                for part in parts:
                    if len(part) >= 3 and not _is_generic_single(part):
                        _add_symbol(part, "RTL", file_path, symbol_map)
                # Also add full signal name if meaningful
                if len(sig_name) >= 4:
                    _add_symbol(sig_name, "RTL", file_path, symbol_map)
                continue

            # Parameters
            m = _RE_PARAM.match(line)
            if m:
                param_name = m.group(1)
                if len(param_name) >= 3:
                    _add_symbol(param_name, "RTL", file_path, symbol_map)


def _add_symbol(
    name: str,
    section: str,
    file_path: str,
    symbol_map: dict[str, dict[str, Any]],
) -> None:
    """Add a symbol occurrence to the map."""
    # Normalize: strip leading/trailing underscores, lowercase
    normalized = name.strip("_").lower()
    if not normalized or len(normalized) < 2:
        return

    if normalized not in symbol_map:
        symbol_map[normalized] = {
            "sections": {},
            "count": 0,
            "files": set(),
            "original_names": set(),
        }

    entry = symbol_map[normalized]
    entry["sections"][section] = entry["sections"].get(section, 0) + 1
    entry["count"] += 1
    entry["files"].add(file_path)
    entry["original_names"].add(name)


def _is_generic(name: str) -> bool:
    """Check if a name is too generic to be a concept candidate."""
    normalized = name.strip("_").lower()

    # Check stop words
    if normalized in GENERIC_STOP_WORDS:
        return True

    # Check common Python builtins
    if normalized in {"__str__", "__repr__", "__len__", "__init__", "__call__"}:
        return True

    return False


def _is_generic_single(part: str) -> bool:
    """Check if a single underscore-separated part is generic."""
    return part.lower() in GENERIC_STOP_WORDS or len(part) < 3


def _should_skip_name(name: str, is_test: bool) -> bool:
    """Decide if a Python name should be skipped."""
    if name.startswith("__") and name.endswith("__"):
        return True
    if name.startswith("_") and not is_test:
        return True
    return False
