from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fpga_devmind.agent import run_p1a_semantic_agent_dry_run
from fpga_devmind.llm_contract import validate_semantic_reasoning_result
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

    def test_p1a_plus_agent_dry_run_writes_runtime_artifacts(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            result = run_p1a_semantic_agent_dry_run(
                project_root=DEFAULT_PROJECT,
                stage_id="L6_resource_opt",
                question="L6 实现了什么流程",
                out_dir=out_dir,
            )

            self.assertTrue((out_dir / "agent_trace.json").exists())
            self.assertTrue((out_dir / "prompt_context.json").exists())
            self.assertTrue((out_dir / "provider_call.json").exists())
            self.assertTrue((out_dir / "model_result_normalized.json").exists())
            self.assertTrue((out_dir / "claim_proposals.json").exists())
            self.assertTrue((out_dir / "graph_write_proposal.json").exists())
            self.assertTrue((out_dir / "project_graph_proposed.json").exists())
            self.assertTrue((out_dir / "graph_write_report.json").exists())
            self.assertTrue((out_dir / "grounding_report.json").exists())
            self.assertTrue((out_dir / "answer.md").exists())

            trace = json.loads((out_dir / "agent_trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["mode"], "deterministic_dry_run_no_llm")
            self.assertEqual(trace["provider_id"], "noop")
            self.assertFalse(trace["safety"]["api_key_used"])
            self.assertFalse(trace["safety"]["vivado_run"])
            self.assertGreaterEqual(len(trace["events"]), 2)

            provider_call = json.loads((out_dir / "provider_call.json").read_text(encoding="utf-8"))
            self.assertEqual(provider_call["provider_id"], "noop")
            self.assertFalse(provider_call["external_api_called"])
            self.assertFalse(provider_call["api_key_used"])
            self.assertFalse(provider_call["api_key_logged"])

            grounding = result["grounding_report"]
            self.assertEqual(grounding["freshness"]["status"], "current")
            self.assertEqual(grounding["summary"]["blocking_diagnostics"], 0)
            self.assertEqual(grounding["summary"]["model_output_blocking_diagnostics"], 0)
            self.assertGreaterEqual(grounding["summary"]["candidate_claims"], 5)

            prompt_context = json.loads((out_dir / "prompt_context.json").read_text(encoding="utf-8"))
            self.assertFalse(prompt_context["redaction_policy"]["api_keys_included"])
            self.assertFalse(prompt_context["redaction_policy"]["provider_secrets_included"])
            self.assertIn("known_evidence_ids", prompt_context)
            self.assertEqual(prompt_context["task"]["request_id"], "p1a-fpga_project_coarse_sync_glm-l6")

            normalized = json.loads((out_dir / "model_result_normalized.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized["request_id"], prompt_context["task"]["request_id"])

            answer = (out_dir / "answer.md").read_text(encoding="utf-8")
            self.assertIn("deterministic_dry_run_no_llm", answer)
            self.assertIn("## Grounded Answer", answer)
            self.assertIn("S0 AutocorrNorm", answer)

    def test_p1a_plus_agent_validates_model_result_fixture(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "agent"
            fixture_path = Path(tmp) / "model_result.json"
            fixture = {
                "schema_version": "p1a-plus-semantic-result-0.1",
                "request_id": "fixture-001",
                "plan_step_id": "S002",
                "reasoning_summary": "Synthetic fixture for model validation.",
                "candidate_claims": [
                    {
                        "claim_type": "implementation_claim",
                        "statement": "The stage has proven producer consumer dataflow.",
                        "subject_ids": ["N001"],
                        "evidence_ids": ["E:not-known"],
                        "confidence": "confirmed",
                        "required_missing_evidence": [],
                        "generated_from_step": "S002",
                    }
                ],
                "proposed_edges": [],
                "proposed_uncertainties": [],
                "requested_followup_tools": [],
                "self_check_notes": [],
            }
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            result = run_p1a_semantic_agent_dry_run(
                project_root=DEFAULT_PROJECT,
                stage_id="L6_resource_opt",
                question="L6 实现了什么流程",
                out_dir=out_dir,
                model_result_path=fixture_path,
            )

            trace = json.loads((out_dir / "agent_trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["mode"], "deterministic_dry_run_with_model_fixture")
            self.assertEqual(trace["provider_id"], "fixture")
            self.assertEqual(trace["model_result_source"], str(fixture_path))

            provider_call = json.loads((out_dir / "provider_call.json").read_text(encoding="utf-8"))
            self.assertEqual(provider_call["provider_id"], "fixture")
            self.assertEqual(provider_call["source"], str(fixture_path))
            self.assertFalse(provider_call["external_api_called"])

            normalized = json.loads((out_dir / "model_result_normalized.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized["candidate_claims"][0]["confidence"], "unknown")
            self.assertEqual(normalized["candidate_claims"][0]["evidence_ids"], [])

            grounding = result["grounding_report"]
            self.assertEqual(grounding["mode"], "deterministic_dry_run_with_model_fixture")
            self.assertGreaterEqual(grounding["summary"]["model_output_blocking_diagnostics"], 1)
            self.assertTrue(any(d["issue_type"] == "unknown_evidence_id" for d in grounding["model_output_diagnostics"]))

            graph_write = json.loads((out_dir / "graph_write_proposal.json").read_text(encoding="utf-8"))
            self.assertEqual(graph_write["mode"], "deterministic_dry_run_with_model_fixture")
            proposals = json.loads((out_dir / "claim_proposals.json").read_text(encoding="utf-8"))
            self.assertEqual(proposals["model_claim_summary"]["rejected"], 1)
            self.assertEqual(proposals["model_candidate_claims"][0]["validation_status"], "rejected")

    def test_p1a_plus_agent_proposes_valid_model_claims_for_graph_write(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "agent"
            artifact_dir = Path(tmp) / "artifacts"
            graph = run_p1a(DEFAULT_PROJECT, artifact_dir)
            evidence_id = graph.evidence_items[0].evidence_id
            fixture_path = Path(tmp) / "model_result.json"
            fixture = {
                "schema_version": "p1a-plus-semantic-result-0.1",
                "request_id": "fixture-accepted",
                "plan_step_id": "S002",
                "reasoning_summary": "Synthetic accepted fixture.",
                "candidate_claims": [
                    {
                        "claim_type": "implementation_claim",
                        "statement": "The model proposes a grounded semantic reading of the first observed evidence item.",
                        "subject_ids": ["N001"],
                        "evidence_ids": [evidence_id],
                        "confidence": "supported",
                        "required_missing_evidence": [],
                        "generated_from_step": "S002",
                    }
                ],
                "proposed_edges": [],
                "proposed_uncertainties": [],
                "requested_followup_tools": [],
                "self_check_notes": [],
            }
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            result = run_p1a_semantic_agent_dry_run(
                project_root=DEFAULT_PROJECT,
                stage_id="L6_resource_opt",
                question="L6 实现了什么流程",
                out_dir=out_dir,
                artifact_dir=artifact_dir,
                model_result_path=fixture_path,
            )

            self.assertEqual(result["grounding_report"]["summary"]["model_output_blocking_diagnostics"], 0)
            graph_write = json.loads((out_dir / "graph_write_proposal.json").read_text(encoding="utf-8"))
            self.assertEqual(len(graph_write["model_claims_to_create"]), 1)
            self.assertEqual(graph_write["rejected_model_claim_ids"], [])
            self.assertEqual(graph_write["model_claims_to_create"][0]["validation_status"], "accepted_for_grounding")
            graph_write_report = json.loads((out_dir / "graph_write_report.json").read_text(encoding="utf-8"))
            self.assertEqual(graph_write_report["claims_added"], ["M001"])
            self.assertFalse(graph_write_report["project_graph_mutated"])

            original_graph = json.loads((artifact_dir / "project_graph.json").read_text(encoding="utf-8"))
            proposed_graph = json.loads((out_dir / "project_graph_proposed.json").read_text(encoding="utf-8"))
            self.assertEqual(len(original_graph["candidate_claims"]), len(graph.candidate_claims))
            self.assertEqual(len(proposed_graph["candidate_claims"]), len(graph.candidate_claims) + 1)
            self.assertEqual(proposed_graph["candidate_claims"][-1]["claim_layer"], "p1a_plus_model_proposal")

    def test_p1a_plus_agent_mock_semantic_provider_generates_proposed_graph_claim(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "agent"
            result = run_p1a_semantic_agent_dry_run(
                project_root=DEFAULT_PROJECT,
                stage_id="L6_resource_opt",
                question="L6 实现了什么流程",
                out_dir=out_dir,
                use_mock_semantic=True,
            )

            self.assertEqual(result["agent_trace"]["mode"], "deterministic_dry_run_with_mock_semantic")
            self.assertEqual(result["agent_trace"]["provider_id"], "mock_semantic")
            self.assertEqual(result["grounding_report"]["summary"]["model_output_blocking_diagnostics"], 0)

            provider_call = json.loads((out_dir / "provider_call.json").read_text(encoding="utf-8"))
            self.assertEqual(provider_call["provider_id"], "mock_semantic")
            self.assertFalse(provider_call["external_api_called"])

            graph_write = json.loads((out_dir / "graph_write_proposal.json").read_text(encoding="utf-8"))
            self.assertEqual(len(graph_write["model_claims_to_create"]), 1)
            self.assertEqual(graph_write["model_claims_to_create"][0]["claim_id"], "M001")

            report = json.loads((out_dir / "graph_write_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["claims_added"], ["M001"])

    def test_p1a_plus_agent_rejects_unsafe_output_path(self) -> None:
        if not DEFAULT_PROJECT.exists():
            self.skipTest(f"target project not found: {DEFAULT_PROJECT}")

        unsafe_out = Path("/tmp/fpga_project_bad/devmind_out")
        with self.assertRaisesRegex(ValueError, "fpga_project_"):
            run_p1a_semantic_agent_dry_run(
                project_root=DEFAULT_PROJECT,
                stage_id="L6_resource_opt",
                question="L6 实现了什么流程",
                out_dir=unsafe_out,
            )

    def test_llm_contract_downgrades_unsupported_model_claims(self) -> None:
        result = {
            "schema_version": "p1a-plus-semantic-result-0.1",
            "request_id": "req-001",
            "plan_step_id": "S002",
            "reasoning_summary": "Synthetic model result for validation.",
            "candidate_claims": [
                {
                    "claim_type": "implementation_claim",
                    "statement": "The stage has proven producer consumer dataflow.",
                    "subject_ids": ["N001"],
                    "evidence_ids": ["E:missing"],
                    "confidence": "confirmed",
                    "required_missing_evidence": [],
                    "generated_from_step": "S002",
                },
                {
                    "claim_type": "implementation_claim",
                    "statement": "The stage has an implementation concept.",
                    "subject_ids": ["N001"],
                    "evidence_ids": ["E:known"],
                    "confidence": "supported",
                    "required_missing_evidence": [],
                    "generated_from_step": "S002",
                },
            ],
            "proposed_edges": [],
            "proposed_uncertainties": [],
            "requested_followup_tools": [],
            "self_check_notes": [],
        }

        normalized, diagnostics = validate_semantic_reasoning_result(result, {"E:known"})

        self.assertEqual(normalized["candidate_claims"][0]["confidence"], "unknown")
        self.assertEqual(normalized["candidate_claims"][0]["evidence_ids"], [])
        self.assertEqual(normalized["candidate_claims"][1]["confidence"], "supported")
        self.assertTrue(any(d["issue_type"] == "unknown_evidence_id" for d in diagnostics))
        self.assertTrue(any(d["issue_type"] == "model_claim_without_evidence" for d in diagnostics))

    def test_llm_contract_blocks_forbidden_tools_and_ungrounded_outputs(self) -> None:
        result = {
            "schema_version": "p1a-plus-semantic-result-0.1",
            "request_id": "req-002",
            "plan_step_id": "S002",
            "reasoning_summary": "Synthetic model result for output validation.",
            "candidate_claims": [],
            "proposed_edges": [
                {
                    "edge_id": "ME001",
                    "from_node_id": "N001",
                    "to_node_id": "N002",
                    "evidence_ids": ["E:missing-edge"],
                }
            ],
            "proposed_uncertainties": [
                {
                    "uncertainty_id": "MU001",
                    "topic": "dataflow",
                    "evidence_ids": ["E:missing-uncertainty"],
                }
            ],
            "requested_followup_tools": [{"tool_name": "vivado"}],
            "self_check_notes": [],
        }

        normalized, diagnostics = validate_semantic_reasoning_result(result, {"E:known"})

        self.assertEqual(normalized["requested_followup_tools"], [])
        self.assertEqual(normalized["proposed_edges"][0]["evidence_ids"], [])
        self.assertEqual(normalized["proposed_uncertainties"][0]["evidence_ids"], [])
        issue_types = {d["issue_type"] for d in diagnostics}
        self.assertIn("forbidden_followup_tool", issue_types)
        self.assertIn("proposed_edges_unknown_evidence_id", issue_types)
        self.assertIn("proposed_uncertainties_unknown_evidence_id", issue_types)

    def test_llm_contract_requires_schema_version(self) -> None:
        result = {
            "request_id": "req-003",
            "plan_step_id": "S002",
            "reasoning_summary": "Missing schema version.",
            "candidate_claims": [],
            "proposed_edges": [],
            "proposed_uncertainties": [],
            "requested_followup_tools": [],
            "self_check_notes": [],
        }

        _normalized, diagnostics = validate_semantic_reasoning_result(result, set())

        self.assertTrue(any(d["issue_type"] == "model_output_missing_fields" for d in diagnostics))
        self.assertTrue(any(d["issue_type"] == "model_output_schema_version_mismatch" for d in diagnostics))


if __name__ == "__main__":
    unittest.main()
