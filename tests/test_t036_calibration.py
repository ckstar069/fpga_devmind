"""T036: Semantic calibration + golden benchmark tests.

Tests for:
- Golden benchmark spec loading and validation
- Discovery V2 fields (aliases, selection_reason, score_breakdown, semantic_role)
- Discovery evaluation against golden specs
- Quality gates for 3 real projects
- Evidence chain V2 fields
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fpga_devmind.discovery_eval import (
    EvalResult,
    _build_golden_name_set,
    _load_golden_spec,
    _match_concept,
    evaluate_discovery,
)
from fpga_devmind.p1b_discovery import (
    DiscoveryResult,
    ScoreBreakdown,
    discover_concepts,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BENCH_DIR = Path(__file__).resolve().parent.parent / "docs" / "benchmarks"
PROJECTS_PARENT = Path("/Users/ckstar/Repo/znxt_ofdm")

COARSE_ROOT = PROJECTS_PARENT / "fpga_project_coarse_sync_glm"
FINE_ROOT = PROJECTS_PARENT / "fpga_project_fine_cfo"
FFT_ROOT = PROJECTS_PARENT / "fpga_project_fft"

COARSE_SPEC = BENCH_DIR / "coarse_sync_glm-golden-concepts.json"
FINE_SPEC = BENCH_DIR / "fine_cfo-golden-concepts.json"
FFT_SPEC = BENCH_DIR / "fft-golden-concepts.json"

REAL_PROJECTS_AVAILABLE = COARSE_ROOT.is_dir() and FINE_ROOT.is_dir() and FFT_ROOT.is_dir()

skip_no_projects = pytest.mark.skipif(
    not REAL_PROJECTS_AVAILABLE,
    reason="Real FPGA projects not available",
)

# Quality gate forbidden terms (must NOT appear in top 12)
GATE4_FORBIDDEN = {"cfg", "model", "pytestmark", "expected", "actual", "results"}


# ===========================================================================
# Golden benchmark specs
# ===========================================================================


class TestGoldenSpecLoading:
    """Golden benchmark spec loading and validation."""

    def test_coarse_spec_loads(self):
        spec = _load_golden_spec(COARSE_SPEC)
        assert spec["schema_version"].startswith("golden-concepts-")
        assert spec["project_id"] == "fpga_project_coarse_sync_glm"
        assert len(spec["expected_core_concepts"]) >= 6

    def test_fine_spec_loads(self):
        spec = _load_golden_spec(FINE_SPEC)
        assert spec["project_id"] == "fpga_project_fine_cfo"
        assert len(spec["expected_core_concepts"]) >= 4

    def test_fft_spec_loads(self):
        spec = _load_golden_spec(FFT_SPEC)
        assert spec["project_id"] == "fpga_project_fft"
        assert len(spec["expected_core_concepts"]) >= 4

    def test_invalid_spec_raises(self, tmp_path: Path):
        bad_spec = tmp_path / "bad.json"
        bad_spec.write_text('{"schema_version": "invalid"}')
        with pytest.raises(ValueError, match="Unexpected schema_version"):
            _load_golden_spec(bad_spec)

    def test_missing_spec_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            _load_golden_spec(tmp_path / "nonexistent.json")

    def test_each_core_has_required_fields(self):
        for spec_path in [COARSE_SPEC, FINE_SPEC, FFT_SPEC]:
            spec = _load_golden_spec(spec_path)
            for entry in spec["expected_core_concepts"]:
                assert "concept" in entry, f"Missing 'concept' in {spec_path}"
                assert "aliases" in entry, f"Missing 'aliases' for {entry.get('concept')}"
                assert "why_core" in entry, f"Missing 'why_core' for {entry.get('concept')}"
                assert "semantic_role" in entry, f"Missing 'semantic_role' for {entry.get('concept')}"


# ===========================================================================
# Discovery V2 fields
# ===========================================================================


@skip_no_projects
class TestDiscoveryV2Fields:
    """Verify V2 fields on ConceptCandidate after discovery."""

    @pytest.fixture()
    def coarse_result(self) -> DiscoveryResult:
        return discover_concepts(COARSE_ROOT)

    def test_candidates_have_aliases(self, coarse_result: DiscoveryResult):
        """At least some candidates should have alias groups."""
        with_aliases = [c for c in coarse_result.candidates if c.aliases]
        assert len(with_aliases) > 0, "No candidates have aliases"

    def test_candidates_have_score_breakdown(self, coarse_result: DiscoveryResult):
        """Every candidate must have a ScoreBreakdown."""
        for c in coarse_result.candidates[:20]:
            assert isinstance(c.score_breakdown, ScoreBreakdown), (
                f"{c.name} missing ScoreBreakdown"
            )
            assert c.score_breakdown.total >= 0

    def test_candidates_have_selection_reason(self, coarse_result: DiscoveryResult):
        """Every candidate must have a non-empty selection_reason."""
        for c in coarse_result.candidates[:20]:
            assert c.selection_reason, f"{c.name} missing selection_reason"

    def test_candidates_have_semantic_role(self, coarse_result: DiscoveryResult):
        """Every candidate must have a valid semantic_role."""
        valid_roles = {"function", "signal", "parameter", "test_only", "config", "generic", "unknown"}
        for c in coarse_result.candidates[:20]:
            assert c.semantic_role in valid_roles, (
                f"{c.name} has invalid semantic_role: {c.semantic_role}"
            )

    def test_discovery_result_has_mode(self, coarse_result: DiscoveryResult):
        """DiscoveryResult must have a mode field."""
        assert coarse_result.mode in ("conservative", "balanced", "broad")

    def test_discovery_result_has_counts(self, coarse_result: DiscoveryResult):
        """DiscoveryResult must have raw symbol counts."""
        assert coarse_result.total_raw_symbols > 0
        assert coarse_result.total_after_filter > 0
        assert coarse_result.total_after_filter <= coarse_result.total_raw_symbols


# ===========================================================================
# Concept matching logic
# ===========================================================================


class TestConceptMatching:
    """Unit tests for _match_concept matching logic."""

    def test_exact_match(self):
        discovered = {"autocorr", "peak_idx", "sync"}
        result = _match_concept("autocorr", [], discovered, {})
        assert result["matched"] is True
        assert result["match_type"] == "exact"

    def test_alias_to_name_match(self):
        discovered = {"smooth"}
        result = _match_concept("smooth_detect", ["smooth"], discovered, {})
        assert result["matched"] is True
        assert result["match_type"] == "alias_to_name"

    def test_name_to_discovered_alias_match(self):
        discovered_aliases = {"smooth": ["smooth_detect", "smooth_detection"]}
        result = _match_concept("smooth_detect", [], set(), discovered_aliases)
        assert result["matched"] is True
        assert result["match_type"] == "name_to_discovered_alias"

    def test_no_match(self):
        discovered = {"autocorr"}
        result = _match_concept("cordic", [], discovered, {})
        assert result["matched"] is False
        assert result["match_type"] == "none"

    def test_case_insensitive_match(self):
        discovered = {"cfo"}
        result = _match_concept("CFO", [], discovered, {})
        assert result["matched"] is True


class TestGoldenNameSet:
    """Test _build_golden_name_set helper."""

    def test_builds_name_set(self):
        core = [{"concept": "fft", "aliases": ["FFT", "fft_core"]}]
        secondary = [{"concept": "sine", "aliases": ["sin"]}]
        names = _build_golden_name_set(core, secondary)
        assert "fft" in names
        assert "fft_core" in names
        assert "sine" in names
        assert "sin" in names

    def test_empty_secondary(self):
        core = [{"concept": "cfo", "aliases": []}]
        names = _build_golden_name_set(core, [])
        assert "cfo" in names


# ===========================================================================
# Quality gates on real projects
# ===========================================================================


@skip_no_projects
class TestQualityGates:
    """Verify quality gates from T036 specification."""

    def _eval(self, project_root: Path, spec_path: Path) -> EvalResult:
        return evaluate_discovery(project_root, spec_path)

    # Gate 1: coarse_sync_glm must include peak_idx/cfo/smooth_detect or aliases
    def test_gate1_coarse_core_concepts(self):
        result = self._eval(COARSE_ROOT, COARSE_SPEC)
        matched = set(result.matched_core)
        required_any = {"peak_idx", "cfo", "smooth_detect"}
        # Check via golden spec aliases
        spec = _load_golden_spec(COARSE_SPEC)
        for entry in spec["expected_core_concepts"]:
            if entry["concept"] in required_any:
                assert entry["concept"] in matched or any(
                    a in matched for a in entry.get("aliases", [])
                ), f"Gate 1: missing {entry['concept']} (or alias) from coarse_sync_glm"

    # Gate 2: fine_cfo must include cfo/fine_cfo/phase/frequency/lts related concepts
    def test_gate2_fine_cfo_core_concepts(self):
        result = self._eval(FINE_ROOT, FINE_SPEC)
        matched = set(result.matched_core)
        # fine_cfo (concept name in spec) matched via alias "cfo"; lts must also match
        assert "fine_cfo" in matched or "cfo" in matched, (
            f"Gate 2: neither fine_cfo nor cfo in matched: {matched}"
        )
        assert "lts" in matched, f"Gate 2: lts missing from fine_cfo, got {matched}"

    # Gate 3: fft must include at least 3 of fft/twiddle/butterfly/stage/core
    def test_gate3_fft_core_concepts(self):
        result = self._eval(FFT_ROOT, FFT_SPEC)
        matched = set(result.matched_core)
        required = {"fft", "twiddle", "butterfly", "stage", "dft"}
        found = required & matched
        assert len(found) >= 3, (
            f"Gate 3: only found {found} of required {required} in fft"
        )

    # Gate 4: forbidden terms must not appear in top 12
    def test_gate4_no_forbidden_in_top12(self):
        for proj_root in [COARSE_ROOT, FINE_ROOT, FFT_ROOT]:
            result = discover_concepts(proj_root)
            top12_names = {c.name.lower() for c in result.candidates[:12]}
            violations = GATE4_FORBIDDEN & top12_names
            assert not violations, (
                f"Gate 4: {proj_root.name} top 12 contains forbidden: {violations}"
            )

    # Gate 5: every selected concept has selection_reason
    def test_gate5_selection_reasons(self):
        for proj_root in [COARSE_ROOT, FINE_ROOT, FFT_ROOT]:
            result = discover_concepts(proj_root)
            for c in result.candidates[:12]:
                assert c.selection_reason, (
                    f"Gate 5: {c.name} in {proj_root.name} missing selection_reason"
                )

    # Recall: 100% core recall for all 3 projects
    def test_all_core_concepts_recalled(self):
        for proj_root, spec_path in [
            (COARSE_ROOT, COARSE_SPEC),
            (FINE_ROOT, FINE_SPEC),
            (FFT_ROOT, FFT_SPEC),
        ]:
            result = self._eval(proj_root, spec_path)
            assert len(result.matched_core) == result.golden_core_count, (
                f"{proj_root.name}: missed core concepts: {result.missed_core}"
            )


# ===========================================================================
# EvalResult serialization
# ===========================================================================


class TestEvalResultSerialization:
    """Test EvalResult to_dict round-trip."""

    def test_to_dict(self):
        r = EvalResult(
            project_id="test_proj",
            golden_core_count=3,
            golden_secondary_count=1,
            matched_core=["a", "b"],
            missed_core=["c"],
            matched_secondary=["d"],
            unexpected_selected=["x"],
            precision_like=0.5,
            recall_like=0.6667,
        )
        d = r.to_dict()
        assert d["project_id"] == "test_proj"
        assert d["matched_core"] == ["a", "b"]
        assert d["missed_core"] == ["c"]
        assert d["precision_like"] == 0.5

        # Round-trip through JSON
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["matched_core"] == ["a", "b"]
