"""T035: Concept auto-discovery tests.

Tests for p1b_discovery.py, benchmark_manifest.py,
and --concepts auto integration in p1b_project_cli.py.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from fpga_devmind.p1b_discovery import (
    GENERIC_STOP_WORDS,
    DOMAIN_TERMS,
    ConceptCandidate,
    DiscoveryResult,
    discover_concepts,
)


# Use the real project that we know exists
PROJECT_ROOT = Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm")


@pytest.mark.skipif(not PROJECT_ROOT.is_dir(), reason="Project not available")
class TestDiscoverConcepts:
    """Tests for discover_concepts() on a real project."""

    def test_returns_discovery_result(self):
        result = discover_concepts(PROJECT_ROOT)
        assert isinstance(result, DiscoveryResult)
        assert result.project_id == "fpga_project_coarse_sync_glm"
        assert result.project_root == str(PROJECT_ROOT.resolve())

    def test_finds_candidates(self):
        result = discover_concepts(PROJECT_ROOT)
        assert len(result.candidates) > 0

    def test_candidates_have_required_fields(self):
        result = discover_concepts(PROJECT_ROOT)
        for c in result.candidates[:5]:
            assert isinstance(c, ConceptCandidate)
            assert len(c.name) >= 3
            assert c.confidence in ("high", "medium", "low")
            assert len(c.source_sections) >= 1
            assert c.occurrence_count >= 1
            assert c.likely_stage in (
                "L5", "L6", "RTL", "test", "cross_stage", "unknown",
            )

    def test_filters_generic_names(self):
        """Generic stop words should NOT appear in candidates."""
        result = discover_concepts(PROJECT_ROOT)
        candidate_names = {c.name for c in result.candidates}
        for stop_word in ["reset", "clk", "data", "valid", "config", "test",
                          "errors", "signed", "wire", "main", "init"]:
            assert stop_word not in candidate_names, f"Stop word '{stop_word}' found in candidates"

    def test_high_confidence_cross_stage(self):
        """High confidence candidates should appear in multiple sections."""
        result = discover_concepts(PROJECT_ROOT)
        high = [c for c in result.candidates if c.confidence == "high"]
        assert len(high) > 0
        for c in high:
            assert len(c.source_sections) >= 2, f"{c.name} has high confidence but only {c.source_sections}"

    def test_sorted_by_confidence_and_count(self):
        """Candidates should be sorted: high first, then by occurrence count desc."""
        result = discover_concepts(PROJECT_ROOT)
        conf_order = {"high": 0, "medium": 1, "low": 2}
        for i in range(len(result.candidates) - 1):
            a, b = result.candidates[i], result.candidates[i + 1]
            assert conf_order[a.confidence] <= conf_order[b.confidence]
            if a.confidence == b.confidence:
                assert a.occurrence_count >= b.occurrence_count

    def test_domain_terms_not_filtered(self):
        """Domain terms like 'metric', 'energy', 'angle' should survive."""
        result = discover_concepts(PROJECT_ROOT)
        candidate_names = {c.name for c in result.candidates}
        # These should appear because they're in DOMAIN_TERMS or are genuinely significant
        domain_found = candidate_names & DOMAIN_TERMS
        # At least a few domain terms should be found
        assert len(domain_found) > 0, "No domain terms found in candidates"


class TestGenericStopWords:
    """Tests for the stop words set."""

    def test_common_names_filtered(self):
        for name in ["reset", "clk", "data", "valid", "config", "test",
                      "main", "init", "start", "stop", "errors"]:
            assert name in GENERIC_STOP_WORDS

    def test_verilog_keywords_filtered(self):
        for name in ["signed", "wire", "reg", "logic", "always", "module"]:
            assert name in GENERIC_STOP_WORDS

    def test_domain_terms_not_in_stop_words(self):
        """Domain terms should NOT be in stop words."""
        for name in ["cfo", "peak", "sync", "fft", "cordic", "viterbi"]:
            assert name not in GENERIC_STOP_WORDS


class TestAutoTraceIntegration:
    """Test --concepts auto mode integration via p1b_project_cli."""

    @pytest.mark.skipif(not PROJECT_ROOT.is_dir(), reason="Project not available")
    def test_auto_trace_produces_bundle(self):
        from fpga_devmind.p1b_project_cli import run_p1b_trace_project

        with tempfile.TemporaryDirectory(prefix="t035_test_") as tmpdir:
            out_dir = Path(tmpdir)
            metadata = run_p1b_trace_project(
                PROJECT_ROOT,
                ["auto"],
                out_dir,
            )

            assert metadata["status"] == "ok"
            assert metadata.get("discovery_used") is True
            assert metadata.get("discovered_count", 0) > 0
            assert len(metadata["concepts_processed"]) > 0

            # Check that index files exist
            index_path = out_dir / "project_understanding_index.json"
            assert index_path.exists()

            with open(index_path) as f:
                idx = json.load(f)

            # Check evidence_chain exists
            assert "evidence_chain" in idx
            assert len(idx["evidence_chain"]) > 0

            # Check stage counts in concept_index
            for name, info in idx["concept_index"].items():
                assert "l5_count" in info
                assert "l6_count" in info
                assert "test_count" in info


class TestBenchmarkManifest:
    """Test benchmark manifest generation."""

    @pytest.mark.skipif(
        not Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm").is_dir(),
        reason="Projects not available",
    )
    def test_manifest_structure(self):
        from fpga_devmind.benchmark_manifest import generate_benchmark_manifest

        parent = Path("/Users/ckstar/Repo/znxt_ofdm")
        with tempfile.TemporaryDirectory(prefix="t035_bm_") as tmpdir:
            out_dir = Path(tmpdir)
            manifest = generate_benchmark_manifest(parent, out_dir)

            assert len(manifest) >= 3  # At least 3 projects
            for entry in manifest:
                assert "project_id" in entry
                assert entry["project_id"].startswith("fpga_project_")
                assert "has_L5" in entry
                assert "has_L6" in entry
                assert "has_RTL" in entry
                assert "has_tests" in entry
                assert "recommended_concepts" in entry

            # Manifest JSON file should exist
            manifest_file = out_dir / "benchmark_manifest.json"
            assert manifest_file.exists()
            with open(manifest_file) as f:
                data = json.load(f)
            assert len(data) == len(manifest)
