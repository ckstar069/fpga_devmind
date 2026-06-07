from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.p1a import DEFAULT_PROJECT, run_p1a
from fpga_devmind.query import answer_question


class P1aRunnerTest(unittest.TestCase):
    def test_default_project_generates_grounded_artifacts(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            graph = run_p1a(DEFAULT_PROJECT, out_dir)

            self.assertTrue((out_dir / "project_graph.json").exists())
            self.assertTrue((out_dir / "trace_index.json").exists())
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

            flow_answer = answer_question(out_dir, "L6 实现了什么流程")
            self.assertIn("S0 AutocorrNorm", flow_answer)
            self.assertIn("C001", flow_answer)

            resource_answer = answer_question(out_dir, "资源估计 LUT DSP BRAM 来自哪里")
            self.assertIn("Resource estimates observed", resource_answer)
            self.assertIn("estimate_s0_autocorr", resource_answer)
            self.assertIn("## Evidence", resource_answer)

            claim_answer = answer_question(out_dir, "C001 的证据在哪里")
            self.assertIn("Claim `C001` is `confirmed`", claim_answer)
            self.assertIn("coarse_sync_optimized.py", claim_answer)


if __name__ == "__main__":
    unittest.main()
