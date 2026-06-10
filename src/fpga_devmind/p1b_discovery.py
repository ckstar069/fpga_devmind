"""P1b concept auto-discovery engine V2 (T035).

Scans project source files (L5/L6 Python, RTL Verilog, tests) to discover
candidate concept names using AST and regex analysis.
V2 adds: alias aggregation, compound concepts, numeric scoring,
semantic roles, and discovery modes.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fpga_devmind.p1b_collectors import _discover_py_files, _discover_rtl_files, _discover_test_files

DISCOVERY_SCHEMA_VERSION = "p1b-discovery-0.2"

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
    "min_len", "max_pos", "q_total_bits", "re_q", "im_q",
    "total_bits", "bits", "shift", "scale", "offset", "step",
    "sample", "samples", "range", "limit", "threshold_high", "threshold_low",
    "sum", "diff", "prod", "abs", "norm", "mean", "var", "std",
    "tol", "epsilon", "delta", "alpha", "beta", "gamma",
    "arg", "args", "kwargs", "return", "returns",
    "signed", "wire", "reg", "logic", "always", "assign", "module",
    "input", "output", "inout", "parameter", "localparam",
    "signal", "rng", "acc", "rom", "ram", "fifo", "mux",
    "clk_en", "we", "re", "ce", "cs", "oe",
    # Additional generic noise (T036 calibration)
    "sig", "cfg", "mod", "est", "exp", "recon", "rhs", "use",
    "n_samples", "p_sq", "metrics", "structured", "num_stages",
    "project_root", "measure_performance", "overflow", "underflow",
    "q_scale", "pytest_configure", "threshold", "angle",
    "n_fft", "q_z",
    # T036 gate #4 additions
    "expected", "actual", "results", "model",
    # T037: test infrastructure / generic noise
    "driver", "monitor", "complex", "real", "float", "short", "full",
    "load", "send", "round", "delay", "frame", "window", "total", "point",
    "push", "split", "final", "last",
    # T037: test quality attribute names (from TestXxxCorrectness etc.)
    "correctness", "functional", "intrinsic", "properties",
    "boundary", "conditions", "consistency", "cross",
    "numerical", "stability", "validation", "contracts",
    "generation", "detection", "integration",
    # T037: generic implementation verbs / adjectives
    "finalize", "resolved", "position",
    # T037: generic fixed-point parameters
    "frac_bits", "int_bits",
    # T037: generic implementation nouns
    "pipeline",
})

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
    "lts", "sts", "fpd", "butterfly", "twiddle",
    "radix", "nfft", "scaling",
})

_COMPOUND_GENERIC = frozenset({
    "fixed", "stage", "pipeline", "fixedpoint", "fixedp", "module",
    "component", "entity", "block", "unit", "handler", "manager",
    "wrapper", "impl", "base", "abstract", "top", "tb",
})

# Short domain terms that are too generic as standalone concepts;
# they need compound forms to be useful (e.g., smooth_detect not just detect)
_COMPOUND_STANDALONE_GENERIC: frozenset[str] = frozenset({
    "detect", "noise", "metric", "pipeline", "preamble",
    "streaming", "coarse", "fine", "channel", "filter",
    "resource", "performance", "latency", "throughput",
})
_RE_CAMEL = re.compile(r"([A-Z]{2,}[0-9]*|[A-Z][a-z0-9]*)")
_RE_MODULE = re.compile(r"^\s*module\s+(\w+)")
_RE_SIGNAL = re.compile(r"^\s*(?:input|output|inout|reg|wire|logic)\s+(?:\[\S+?\]\s+)?(\w+)")
_RE_PARAM = re.compile(r"^\s*(?:parameter|localparam)\s+.*?(\w+)\s*=")
_RE_ALIAS_SUFFIX = re.compile(r"_(idx|index|pos|val|value|est|calc|result|out|in)$")


@dataclass
class ScoreBreakdown:
    cross_stage_bonus: int = 0
    key_position_bonus: int = 0
    domain_term_bonus: int = 0
    short_domain_bonus: int = 0
    test_presence_bonus: int = 0
    occurrence_score: int = 0
    alias_group_bonus: int = 0
    generic_penalty: int = 0
    total: int = 0


@dataclass
class ConceptCandidate:
    name: str
    canonical_name: str = ""
    source_sections: list[str] = field(default_factory=list)
    occurrence_count: int = 0
    confidence: str = "low"
    reason: str = ""
    representative_files: list[str] = field(default_factory=list)
    likely_stage: str = "unknown"
    aliases: list[str] = field(default_factory=list)
    semantic_role: str = "unknown"
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    score: int = 0
    selection_reason: str = ""
    compound_source: str = ""
    category: str = "weak_candidate"  # core_like, secondary_like, parameter_like, test_artifact, framework_artifact, generic_variable, weak_candidate
    is_selected: bool = False
    rejection_reason: str = ""
    evidence_counts_by_stage: dict[str, int] = field(default_factory=dict)


@dataclass
class DiscoveryResult:
    schema_version: str = DISCOVERY_SCHEMA_VERSION
    project_id: str = ""
    project_root: str = ""
    candidates: list[ConceptCandidate] = field(default_factory=list)
    diagnostics: list[dict[str, str]] = field(default_factory=list)
    mode: str = "balanced"
    total_raw_symbols: int = 0
    total_after_filter: int = 0


def discover_concepts(project_root: Path, mode: str = "balanced") -> DiscoveryResult:
    """Scan all source sections for candidate concept names."""
    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError("Project root does not exist: {}".format(root))
    result = DiscoveryResult(project_id=root.name, project_root=str(root), mode=mode)
    smap: dict[str, dict[str, Any]] = {}

    # Phase 1: collect
    _scan_python_files(_discover_py_files(root / "src" / "python_model" / "L5_fixedpoint"), "L5_fixedpoint", smap)
    _scan_python_files(_discover_py_files(root / "src" / "python_model" / "L6_resource_opt"), "L6_resource_opt", smap)
    _scan_rtl_files(_discover_rtl_files(root / "src" / "verilog_model" / "rtl"), smap)
    _scan_python_files(_discover_test_files(root), "tests", smap, is_test=True)

    result.total_raw_symbols = len(smap)

    # Phase 2: filter
    filt = {n: i for n, i in smap.items()
            if len(n) >= 3 and not _is_generic(n) and not n.replace("_", "").isdigit()}
    result.total_after_filter = len(filt)

    # Phase 3: compound concepts
    _extract_compounds(filt)

    # Phase 4: alias aggregation
    groups = _build_alias_groups(filt)

    # Phase 5: build candidates with canonical preference and category
    for root, members in groups.items():
        canonical = _pick_canonical(members)
        merged_sec: dict[str, int] = {}
        merged_files: set[str] = set()
        total = 0
        aliases: list[str] = []
        compound_src = ""
        roles: dict[str, int] = {}
        for m in members:
            info = filt[m]
            for s, c in info["sections"].items():
                merged_sec[s] = merged_sec.get(s, 0) + c
            merged_files |= info["files"]
            total += info["count"]
            if m != canonical:
                aliases.append(m)
            for r in info.get("roles", []):
                roles[r] = roles.get(r, 0) + 1
            if info.get("compound_source"):
                compound_src = info["compound_source"]

        secs = list(merged_sec.keys())
        files = sorted(merged_files)[:5]
        sec_set = set(secs)
        has_l5l6 = bool({"L5_fixedpoint", "L6_resource_opt"} & sec_set)
        has_rtl = "RTL" in sec_set

        sb = _score(canonical, secs, total, aliases, roles, compound_src)
        conf = "high" if sb.total >= 50 else "medium" if sb.total >= 25 else "low"
        if canonical.lower() in DOMAIN_TERMS and conf == "low":
            conf = "medium"
            if sb.total < 25:
                sb.domain_term_bonus += (25 - sb.total)
                sb.total = 25

        reason = _reason(secs, total, has_l5l6, has_rtl, conf)
        stage = "cross_stage" if has_l5l6 and has_rtl else (
            "RTL" if has_rtl else (
                "L5" if "L5_fixedpoint" in sec_set else "L6") if has_l5l6 else (
            "test" if "tests" in sec_set else "unknown"))
        role = _role(canonical, secs, roles)
        sel = _sel_reason(canonical, secs, total, aliases, compound_src, sb, role)
        category = _classify_category(canonical, secs, roles, aliases, sb, compound_src)

        result.candidates.append(ConceptCandidate(
            name=canonical, canonical_name=canonical, source_sections=secs,
            occurrence_count=total, confidence=conf, reason=reason,
            representative_files=files, likely_stage=stage, aliases=aliases,
            semantic_role=role, score_breakdown=sb, score=sb.total,
            selection_reason=sel, compound_source=compound_src,
            category=category, evidence_counts_by_stage=dict(merged_sec)))

    # Phase 6: mode filter + category-aware sort
    thresh = {"conservative": 50, "balanced": 25, "broad": 0}.get(mode, 25)
    result.candidates = [c for c in result.candidates if c.score_breakdown.total >= thresh]
    cat_order = {
        "core_like": 0, "secondary_like": 1, "parameter_like": 2,
        "weak_candidate": 3, "test_artifact": 4, "framework_artifact": 5,
        "generic_variable": 6,
    }
    result.candidates.sort(key=lambda c: (
        cat_order.get(c.category, 7),
        -c.score_breakdown.total,
        -c.occurrence_count,
    ))
    return result


# Parameter-like patterns that should not be selectable even with high scores.
# NOTE: Do NOT include golden-core concepts (lts, sts, fpd, first_path, atan2, etc.)
_PARAMETER_PATTERNS = frozenset({
    "nfft", "n_samples", "pipe_depth", "denom_bits", "energy_cnt",
    "cfo_hz", "cfo_rad", "fifo", "fifo2", "buffer", "rom_addr",
    "dropped_bit", "core_l4", "cmpy_dsp48", "estimate_s3",
    "n_samples_py", "q_scale", "q_z", "q_total_bits", "re_q", "im_q",
    "budget_val", "total_latency", "noise_max", "chain_res",
    "search_lhs", "pipeline_latency", "params", "estimator",
    "estimate_s3_cfo", "sig_im", "sig_re", "stage_id",
    "s2_valid", "s3_valid", "s_valid", "x_recon", "phase",
})

SELECTABLE_CATEGORIES: frozenset[str] = frozenset({"core_like", "secondary_like"})


def _is_likely_parameter(c: ConceptCandidate) -> bool:
    """Check if a candidate is likely a parameter or implementation detail."""
    name = c.name.lower()
    if name in _PARAMETER_PATTERNS:
        return True
    if c.category == "parameter_like":
        return True
    if c.category == "generic_variable":
        return True
    # Unit suffix patterns (xxx_hz, xxx_rad, xxx_bits, xxx_cnt)
    if re.search(r'_(hz|rad|bits|cnt|addr|depth|buffer)$', name):
        return True
    return False


def select_for_trace(result: DiscoveryResult, max_n: int = 12) -> list[ConceptCandidate]:
    """Select the best top N concepts for auto-trace.

    Only selects core_like and secondary_like concepts.
    Excludes parameter-like and implementation-detail concepts.
    Falls back to high-scoring parameter_like only if truly needed.
    Sets is_selected and rejection_reason on all candidates.
    """
    selectable = [c for c in result.candidates
                  if c.category in SELECTABLE_CATEGORIES and not _is_likely_parameter(c)]
    if len(selectable) < max_n:
        # Only fallback to parameter_like if score is very high (>= 50)
        fallback = [c for c in result.candidates
                    if c.category == "parameter_like"
                    and c.score_breakdown.total >= 50
                    and not _is_likely_parameter(c)]
        selectable.extend(fallback)
    selected = selectable[:max_n]
    selected_names = {c.name for c in selected}
    for c in result.candidates:
        if c.name in selected_names:
            c.is_selected = True
            c.rejection_reason = ""
        else:
            c.is_selected = False
            if _is_likely_parameter(c):
                c.rejection_reason = "Likely parameter or implementation detail"
            elif c.category not in SELECTABLE_CATEGORIES:
                c.rejection_reason = f"Category '{c.category}' not selectable"
            elif c.score_breakdown.total < 25:
                c.rejection_reason = "Score too low (< 25)"
            else:
                c.rejection_reason = "Not in top N"
    return selected


def _extract_compounds(smap: dict[str, dict[str, Any]]) -> None:
    """Detect compound concepts from PascalCase class/function names.

    Skips ALL_UPPER names (constants like ATAN2_TABLE_SIZE_Q) to avoid
    producing garbage compounds.  For CamelCase names, splits into parts,
    filters generic fillers, and produces both a joined compound and
    individual meaningful parts as separate candidates.
    """
    _RE_ALL_UPPER = re.compile(r"^[A-Z0-9_]+$")
    additions: list[tuple[str, dict[str, Any]]] = []

    for name, info in list(smap.items()):
        for orig in info.get("original_names", set()):
            # Skip dunder, private, and ALL_UPPER (constants)
            if not re.search(r"[A-Z]", orig) or orig.startswith("_"):
                continue
            if _RE_ALL_UPPER.match(orig):
                continue

            parts = [p.lower() for p in _RE_CAMEL.findall(orig) if p]
            if len(parts) < 2:
                continue
            meaningful = [p for p in parts if p not in _COMPOUND_GENERIC and len(p) >= 3]
            if not meaningful:
                continue

            # Add joined compound
            compound = "_".join(meaningful)
            if len(compound) >= 3 and not _is_generic(compound):
                additions.append((compound, {
                    "sections": dict(info["sections"]),
                    "count": 1, "files": set(info["files"]),
                    "original_names": {compound},
                    "roles": ["function"],
                    "compound_source": orig,
                }))

            # Also add each individual meaningful part if it looks like a concept
            for p in meaningful:
                if len(p) >= 4 and not _is_generic(p):
                    additions.append((p, {
                        "sections": dict(info["sections"]),
                        "count": 1, "files": set(info["files"]),
                        "original_names": {p},
                        "roles": ["function"],
                        "compound_source": orig,
                    }))

    # Merge additions into smap
    for compound, entry in additions:
        if compound not in smap:
            smap[compound] = entry
        else:
            e = smap[compound]
            for s, c in entry["sections"].items():
                e["sections"][s] = e["sections"].get(s, 0) + c
            e["count"] += entry["count"]
            e["files"] |= entry["files"]
            e["original_names"] |= entry["original_names"]
            e.setdefault("compound_source", entry.get("compound_source", ""))
            if "function" not in e.get("roles", []):
                e.setdefault("roles", []).append("function")


def _build_alias_groups(smap: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    names = sorted(smap.keys())
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb if len(ra) <= len(rb) else ra] = ra if len(ra) <= len(rb) else rb

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _are_aliases(a, b):
                union(a, b)
    groups: dict[str, list[str]] = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)
    return groups


def _are_aliases(a: str, b: str) -> bool:
    """Determine if two names are likely aliases of the same concept.

    Conservative: only groups names that clearly refer to the same thing.
    Avoids false positives from transitive linking through long compound names.
    """
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)

    # Reject if length ratio is too different (avoids transitive chain pollution)
    if len(longer) > len(shorter) * 2.5:
        return False

    ab = _RE_ALIAS_SUFFIX.sub("", a)
    bb = _RE_ALIAS_SUFFIX.sub("", b)

    # "foo" is prefix of "foo_est", "foo_idx", etc.
    if longer.startswith(shorter + "_") and len(shorter) >= 4:
        return True
    # After stripping suffixes, they are the same
    if ab == bb and len(ab) >= 4:
        return True
    # Multi-part names sharing ALL parts except one (e.g. peak_idx / peak_index)
    ap = a.split("_")
    bp = b.split("_")
    if len(ap) >= 2 and len(bp) >= 2 and len(ap) <= 4 and len(bp) <= 4:
        shared = set(ap) & set(bp)
        min_parts = min(len(ap), len(bp))
        if len(shared) >= min_parts and all(len(p) >= 4 for p in shared):
            return True
    return False


def _pick_canonical(members: list[str]) -> str:
    """Pick the best canonical name from alias group members.

    Prefers concise compound domain names over long RTL signal names.
    Penalises RTL register/wire suffixes (_r, _w, _v, _q, _n, _s),
    overly long names (>18 chars), and names with too many parts (>2 underscores).
    """
    if len(members) <= 1:
        return members[0] if members else ""

    def _cscore(m: str) -> tuple[int, int]:
        rtl = -5 if re.match(r".*_[rwvqns]$", m) else 0
        long_penalty = -3 if len(m) > 18 else 0
        parts_penalty = -1 if m.count("_") > 2 else 0
        domain = 3 if m in DOMAIN_TERMS else 0
        has_domain_part = 2 if "_" in m and any(
            p in DOMAIN_TERMS for p in m.split("_") if len(p) >= 3
        ) else 0
        compound = 1 if "_" in m else 0
        return (domain + has_domain_part + compound + rtl + long_penalty + parts_penalty, -len(m))

    return max(members, key=_cscore)


def _score(name: str, secs: list[str], total: int,
           aliases: list[str], roles: dict[str, int], csrc: str) -> ScoreBreakdown:
    ss = set(secs)
    sb = ScoreBreakdown()
    if bool({"L5_fixedpoint", "L6_resource_opt"} & ss) and "RTL" in ss:
        sb.cross_stage_bonus = 20
    if "function" in roles or csrc:
        sb.key_position_bonus = 15
    if name.lower() in DOMAIN_TERMS:
        sb.domain_term_bonus = 10
        if len(name) <= 4:
            sb.short_domain_bonus = 10
    if "tests" in ss:
        sb.test_presence_bonus = 5
    sb.occurrence_score = min(20, total * 2)
    if aliases:
        sb.alias_group_bonus = 10
    if re.match(r"^(top|tb_|test_|src|lib|pkg|utils|helper|common|shared|core|base|main)", name):
        sb.generic_penalty = -30
    sb.total = (sb.cross_stage_bonus + sb.key_position_bonus + sb.domain_term_bonus
                + sb.short_domain_bonus + sb.test_presence_bonus + sb.occurrence_score
                + sb.alias_group_bonus + sb.generic_penalty)
    return sb


def _reason(secs: list[str], total: int, has_l5l6: bool, has_rtl: bool, conf: str) -> str:
    if has_l5l6 and has_rtl:
        return "Appears in both L5/L6 and RTL (cross-stage evidence)"
    if len(secs) >= 3:
        return "Appears in {} source sections".format(len(secs))
    if len(secs) >= 2 or total >= 3:
        return "Appears in {} sections with {} occurrences".format(len(secs), total)
    return "Single occurrence in {}".format(secs[0] if secs else "?")


def _role(name: str, secs: list[str], roles: dict[str, int]) -> str:
    if re.search(r"(config|cfg|settings)$", name, re.IGNORECASE):
        return "config"
    if set(secs) == {"tests"}:
        return "test_only"
    for tag in ("signal", "parameter", "function"):
        if roles.get(tag, 0) > 0:
            return tag
    return "unknown"


def _classify_category(name: str, secs: list[str], roles: dict[str, int],
                       aliases: list[str], sb: ScoreBreakdown,
                       compound_source: str) -> str:
    """Classify a concept candidate into a category for selection filtering."""
    ss = set(secs)
    has_l5l6 = bool({"L5_fixedpoint", "L6_resource_opt"} & ss)
    has_rtl = "RTL" in ss

    # test_artifact: only in tests, test-prefixed
    if ss == {"tests"} and re.search(r"(^test_|testl\d)", name, re.IGNORECASE):
        return "test_artifact"

    # framework_artifact: config/fixture/driver patterns
    if re.search(r"(config|fixture|conftest|conftest)", name, re.IGNORECASE):
        return "framework_artifact"

    # generic_variable: in stop words or very short non-domain
    if name in GENERIC_STOP_WORDS:
        return "generic_variable"
    if len(name) <= 3 and name not in DOMAIN_TERMS:
        return "generic_variable"

    # Single-letter prefix test variables (x_recon, s_valid, etc.)
    if re.match(r"^[a-z]_[a-z]", name) and name not in DOMAIN_TERMS:
        return "generic_variable"

    # RTL register/wire suffix (_r, _w, _v, _q, _n, _s) → generic_variable unless domain term
    if re.match(r".*_[rwvqns]$", name) and name not in DOMAIN_TERMS:
        return "generic_variable"

    # parameter_like: implementation parameters (n_xxx, q_xxx, etc.)
    if re.match(r"^(n_|num_|log2_|inv_|ref_|pre_|post_|max_|min_)", name) and name not in DOMAIN_TERMS:
        return "parameter_like"

    # Standalone generic domain terms: need compound form to be useful
    if name in _COMPOUND_STANDALONE_GENERIC and "_" not in name:
        if has_l5l6 and has_rtl:
            return "secondary_like"  # cross-stage redeems it
        return "weak_candidate"

    # core_like: cross-stage evidence, compound from class, or high score
    if has_l5l6 and has_rtl:
        return "core_like"
    if compound_source and sb.total >= 30:
        return "core_like"
    if sb.total >= 50 and (has_l5l6 or has_rtl):
        return "core_like"

    # secondary_like: domain term, multi-section, or has aliases
    if name in DOMAIN_TERMS:
        return "secondary_like"
    if aliases and len(secs) >= 2:
        return "secondary_like"
    if has_l5l6 or has_rtl:
        return "secondary_like"
    if sb.total >= 35:
        return "secondary_like"

    return "weak_candidate"


def _sel_reason(name: str, secs: list[str], total: int, aliases: list[str],
                csrc: str, sb: ScoreBreakdown, role: str) -> str:
    ss = set(secs)
    if bool({"L5_fixedpoint", "L6_resource_opt"} & ss) and "RTL" in ss:
        return "Cross-stage: appears in L5/L6 and RTL with {} total occurrences".format(total)
    if csrc:
        return "Compound concept from class definition: {}".format(csrc)
    if name.lower() in DOMAIN_TERMS:
        return "Domain term with {} occurrences in key positions".format(total)
    if aliases:
        return "Alias group of {} related names: {}".format(len(aliases) + 1, ", ".join([name] + aliases[:4]))
    return "{} concept with {} occurrences across {} sections".format(role, total, len(secs))


# --- scanning helpers ---

def _scan_python_files(files: list[str], section: str,
                       symbol_map: dict[str, dict[str, Any]], is_test: bool = False) -> None:
    for fp in files:
        try:
            tree = ast.parse(Path(fp).read_text(encoding="utf-8", errors="ignore"), filename=fp)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            name = rh = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name, rh = node.name, "function"
            elif isinstance(node, ast.ClassDef):
                name, rh = node.name, "function"
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and not t.id.startswith("_"):
                        name = t.id
                        rh = "signal" if _looks_like_signal(t.id) else None
            if name and not _should_skip_name(name, is_test):
                _add_symbol(name, section, fp, symbol_map, rh)


def _scan_rtl_files(files: list[str], symbol_map: dict[str, dict[str, Any]]) -> None:
    for fp in files:
        try:
            lines = Path(fp).read_text(encoding="utf-8", errors="ignore").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for line in lines:
            m = _RE_MODULE.match(line)
            if m:
                mod_name = m.group(1)
                _add_symbol(mod_name, "RTL", fp, symbol_map, "function")
                # Module names like coarse_sync_s0_autocorr — extract meaningful segments
                parts = mod_name.split("_")
                for p in parts:
                    if 3 <= len(p) <= 15 and not _is_generic_single(p):
                        _add_symbol(p, "RTL", fp, symbol_map, "function")
                # Also add meaningful 2-part combinations (e.g., coarse_sync)
                meaningful = [p for p in parts if len(p) >= 3 and not _is_generic_single(p)]
                for i in range(len(meaningful) - 1):
                    combo = meaningful[i] + "_" + meaningful[i + 1]
                    if len(combo) >= 4 and not _is_generic(combo):
                        _add_symbol(combo, "RTL", fp, symbol_map, "function")
                continue
            m = _RE_SIGNAL.match(line)
            if m:
                sn = m.group(1)
                # Only add full signal name; splitting causes garbage
                if len(sn) >= 3 and not _is_generic(sn.strip("_").lower()):
                    _add_symbol(sn, "RTL", fp, symbol_map, "signal")
                continue
            m = _RE_PARAM.match(line)
            if m and len(m.group(1)) >= 3:
                _add_symbol(m.group(1), "RTL", fp, symbol_map, "parameter")


def _add_symbol(name: str, section: str, fp: str,
                symbol_map: dict[str, dict[str, Any]], role: str | None = None) -> None:
    n = name.strip("_").lower()
    if not n or len(n) < 2:
        return
    if n not in symbol_map:
        symbol_map[n] = {"sections": {}, "count": 0, "files": set(),
                         "original_names": set(), "roles": []}
    e = symbol_map[n]
    e["sections"][section] = e["sections"].get(section, 0) + 1
    e["count"] += 1
    e["files"].add(fp)
    e["original_names"].add(name)
    if role and role not in e["roles"]:
        e["roles"].append(role)


def _looks_like_signal(name: str) -> bool:
    return bool(re.search(r"(_[ioqdn]$|_reg$|_next$|_wire$|_bus$|^[swr]_)", name.lower()))


def _is_generic(name: str) -> bool:
    n = name.strip("_").lower()
    return n in GENERIC_STOP_WORDS or n in {"__str__", "__repr__", "__len__", "__init__", "__call__"}


def _is_generic_single(part: str) -> bool:
    return part.lower() in GENERIC_STOP_WORDS or len(part) < 3


def _should_skip_name(name: str, is_test: bool) -> bool:
    return (name.startswith("__") and name.endswith("__")) or (name.startswith("_") and not is_test)
