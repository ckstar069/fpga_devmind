from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.p1a import DEFAULT_PROJECT, run_p1a
from fpga_devmind.query import answer_question, check_freshness
from fpga_devmind.smoke import run_smoke, smoke_exit_code

FINE_CFO_PROJECT = Path("/Users/ckstar/Repo/znxt_ofdm/fpga_project_fine_cfo")


class P1aRunnerTest(unittest.TestCase):
    def test_default_project_generates_grounded_artifacts(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            graph = run_p1a(DEFAULT_PROJECT, out_dir)

            self.assertTrue((out_dir / "project_graph.json").exists())
            self.assertTrue((out_dir / "trace_index.json").exists())
            self.assertTrue((out_dir / "memory_manifest.json").exists())
            self.assertTrue((out_dir / "summary.md").exists())
            self.assertTrue((out_dir / "flow.mmd").exists())
            self.assertTrue((out_dir / "trace.md").exists())

            blocking = [d for d in graph.grounding_diagnostics if d.severity == "blocking"]
            self.assertEqual(blocking, [])
            self.assertGreaterEqual(len(graph.candidate_claims), 5)
            self.assertGreaterEqual(len(graph.evidence_items), 1)
            self.assertGreaterEqual(len(graph.fixed_point_specs), 1)
            self.assertGreaterEqual(len(graph.stream_interface_specs), 1)
            self.assertGreaterEqual(len(graph.pipeline_timing_specs), 1)
            self.assertGreaterEqual(len(graph.resource_estimate_specs), 4)

            trace_index = json.loads((out_dir / "trace_index.json").read_text(encoding="utf-8"))
            self.assertIn("C001", trace_index["claims"])
            self.assertGreaterEqual(len(trace_index["claims"]["C001"]["evidence_refs"]), 1)
            self.assertIn(
                {"output_id": "L6_resource_opt", "output_type": "stage"},
                trace_index["claims"]["C001"]["linked_outputs"],
            )
            self.assertGreaterEqual(len(trace_index["evidence"]), len(graph.evidence_items))

            freshness = check_freshness(out_dir)
            self.assertEqual(freshness["status"], "current")
            self.assertIn("source_snapshot_id", freshness)

            flow_answer = answer_question(out_dir, "L6 实现了什么流程")
            self.assertIn("S0 AutocorrNorm", flow_answer)
            self.assertIn("C001", flow_answer)

            resource_answer = answer_question(out_dir, "资源估计 LUT DSP BRAM 来自哪里")
            self.assertIn("Resource estimates observed", resource_answer)
            self.assertIn("estimate_s0_autocorr", resource_answer)
            self.assertIn("## Evidence", resource_answer)

            claim_answer = answer_question(out_dir, "C001 的证据在哪里")
            self.assertIn("Claim `C001` is `supported`", claim_answer)
            self.assertIn("coarse_sync_optimized.py", claim_answer)

            manifest_path = out_dir / "memory_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_files"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            stale = check_freshness(out_dir)
            self.assertEqual(stale["status"], "stale")
            stale_answer = answer_question(out_dir, "C001 的证据在哪里")
            self.assertIn("Freshness Warning", stale_answer)

    def test_fine_cfo_project_generates_grounded_artifacts(self) -> None:
        if not FINE_CFO_PROJECT.exists():
            self.skipTest(f"target project not found: {FINE_CFO_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            graph = run_p1a(FINE_CFO_PROJECT, out_dir)

            blocking = [d for d in graph.grounding_diagnostics if d.severity == "blocking"]
            self.assertEqual(blocking, [])
            self.assertGreaterEqual(len(graph.concepts), 4)
            self.assertGreaterEqual(len(graph.resource_estimate_specs), 2)

            names = [concept.canonical_name for concept in graph.concepts]
            self.assertIn("Streaming Correlator Opt", names)
            self.assertIn("Streaming FPD Opt", names)
            self.assertIn("Streaming CFO Opt", names)

            answer = answer_question(out_dir, "L6 实现了什么流程")
            self.assertIn("Streaming Correlator Opt", answer)
            self.assertIn("Streaming CFO Opt", answer)
            self.assertIn("## Uncertainties", answer)
            self.assertIn("implementation order versus dataflow", answer)

            uncertainty_answer = answer_question(out_dir, "有哪些不确定")
            self.assertIn("Uncertainties recorded", uncertainty_answer)
            self.assertIn("producer/consumer dataflow", uncertainty_answer)

            resource_answer = answer_question(out_dir, "资源估计 LUT DSP BRAM 来自哪里")
            self.assertIn("estimate_sync", resource_answer)
            self.assertIn("fine_cfo_estimator_resource_est.py", resource_answer)

    def test_smoke_report_runs_available_samples(self) -> None:
        if not DEFAULT_PROJECT.exists() and not FINE_CFO_PROJECT.exists():
            self.skipTest("target smoke projects not found")

        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp)
            report = run_smoke(out_root)

            self.assertTrue((out_root / "smoke_report.json").exists())
            self.assertTrue((out_root / "smoke_report.md").exists())
            self.assertEqual(len(report["samples"]), 2)
            self.assertEqual(report["summary"]["failed"], 0)
            for sample in report["samples"]:
                if sample["status"] == "passed":
                    self.assertGreaterEqual(sample["uncertainty_notes"], 1)
            self.assertEqual(smoke_exit_code(report), 0)


if __name__ == "__main__":
    unittest.main()
