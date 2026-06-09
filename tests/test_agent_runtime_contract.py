"""Tests for agent_runtime_contract (T015).

Validates data contracts, JSON round-trip, cross-reference integrity,
and safety boundaries.  No external API, no LLM, no Vivado.
"""

# pyright: reportUnusedCallResult=false

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fpga_devmind.agent_runtime_contract import (
    SCHEMA_VERSION,
    AgentRuntimeTrace,
    Answer,
    GraphWriteProposal,
    Observation,
    ReasoningSummary,
    ToolCallProposal,
    ToolPlan,
    ToolResult,
    UserTask,
    validate_runtime_trace,
    GRAPH_WRITE_DISABLED_REASON,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task() -> UserTask:
    return UserTask(
        task_id="T001",
        question="What is the summary?",
        created_at="2026-06-09T00:00:00Z",
        artifact_bundle_path="/tmp/test_bundle",
        bundle_type="p1b",
        concept="peak_idx",
    )


def _make_observation() -> Observation:
    return Observation(
        observation_id="OBS_001",
        task_id="T001",
        artifact_refs=["concept_trace_graph.json"],
        summary="Loaded P1b bundle",
    )


def _make_reasoning() -> ReasoningSummary:
    return ReasoningSummary(
        reasoning_id="RSN_001",
        task_id="T001",
        mode="deterministic",
        summary="Keyword match to summary intent",
        confidence="supported",
        referenced_observation_ids=["OBS_001"],
    )


def _make_proposal() -> ToolCallProposal:
    return ToolCallProposal(
        proposal_id="PROP_001",
        task_id="T001",
        tool_name="read_artifact",
        params={"artifact": "run_metadata.json"},
        rationale="Read run metadata for summary",
        expected_read_artifacts=["run_metadata.json"],
        allowed_action="read_only_preview",
    )


def _make_plan(proposal: ToolCallProposal | None = None) -> ToolPlan:
    return ToolPlan(
        plan_id="PLAN_001",
        task_id="T001",
        intent="summary",
        steps=[proposal or _make_proposal()],
    )


def _make_result() -> ToolResult:
    return ToolResult(
        result_id="RES_001",
        proposal_id="PROP_001",
        task_id="T001",
        status="not_executed",
        result_summary="Would read run_metadata.json",
    )


def _make_answer() -> Answer:
    return Answer(
        answer_id="ANS_001",
        task_id="T001",
        answer_text="Concept: peak_idx, 2 claims, 2 evidence items",
        confidence="supported",
        referenced_result_ids=["RES_001"],
    )


def _make_gwp() -> GraphWriteProposal:
    return GraphWriteProposal(
        graph_write_id="GWP_001",
        task_id="T001",
        referenced_answer_ids=["ANS_001"],
        blocking_reasons=[GRAPH_WRITE_DISABLED_REASON],
    )


def _make_valid_trace() -> AgentRuntimeTrace:
    return AgentRuntimeTrace(
        task=_make_task(),
        observations=[_make_observation()],
        reasoning=[_make_reasoning()],
        plans=[_make_plan()],
        tool_results=[_make_result()],
        answers=[_make_answer()],
        graph_write_proposals=[_make_gwp()],
    )


# ---------------------------------------------------------------------------
# Happy path & round-trip
# ---------------------------------------------------------------------------


class TestHappyPath(unittest.TestCase):
    """Build a complete trace and verify serialisation."""

    def test_full_trace_to_dict(self):
        trace = _make_valid_trace()
        d = trace.to_dict()
        self.assertEqual(d["schema_version"], SCHEMA_VERSION)
        self.assertEqual(d["task"]["task_id"], "T001")
        self.assertEqual(len(d["observations"]), 1)
        self.assertEqual(len(d["plans"]), 1)
        self.assertEqual(len(d["tool_results"]), 1)
        self.assertEqual(len(d["answers"]), 1)
        self.assertEqual(len(d["graph_write_proposals"]), 1)

    def test_full_trace_json_serializable(self):
        trace = _make_valid_trace()
        text = trace.to_json()
        parsed = json.loads(text)
        self.assertEqual(parsed["task"]["task_id"], "T001")

    def test_json_round_trip(self):
        trace = _make_valid_trace()
        text = trace.to_json()
        restored = AgentRuntimeTrace.from_json(text)
        self.assertEqual(restored.task.task_id, "T001")
        self.assertEqual(restored.schema_version, SCHEMA_VERSION)
        self.assertEqual(len(restored.observations), 1)
        self.assertEqual(len(restored.plans), 1)
        self.assertEqual(restored.plans[0].steps[0].tool_name, "read_artifact")
        self.assertEqual(len(restored.tool_results), 1)
        self.assertEqual(len(restored.answers), 1)
        self.assertEqual(restored.answers[0].answer_text, trace.answers[0].answer_text)
        self.assertEqual(len(restored.graph_write_proposals), 1)

    def test_from_dict_round_trip(self):
        trace = _make_valid_trace()
        d = trace.to_dict()
        restored = AgentRuntimeTrace.from_dict(d)
        self.assertEqual(restored.task.task_id, trace.task.task_id)
        self.assertEqual(restored.task.question, trace.task.question)

    def test_round_trip_preserves_constraints(self):
        trace = _make_valid_trace()
        restored = AgentRuntimeTrace.from_json(trace.to_json())
        for c in ["no_external_api", "no_vivado", "read_only", "no_target_project_mutation"]:
            self.assertIn(c, restored.task.constraints)

    def test_round_trip_preserves_safety_notes(self):
        trace = _make_valid_trace()
        restored = AgentRuntimeTrace.from_json(trace.to_json())
        for note in ["no external LLM", "no Vivado", "no mutation"]:
            found = any(note in n for n in restored.plans[0].safety_notes)
            self.assertTrue(found, f"Safety note containing '{note}' not found")


# ---------------------------------------------------------------------------
# UserTask validation
# ---------------------------------------------------------------------------


class TestUserTask(unittest.TestCase):

    def test_constraints_auto_filled(self):
        task = UserTask(
            task_id="T1", question="q", artifact_bundle_path="/tmp/x"
        )
        for c in ["no_external_api", "no_vivado", "read_only", "no_target_project_mutation"]:
            self.assertIn(c, task.constraints)

    def test_constraints_preserve_existing(self):
        task = UserTask(
            task_id="T1",
            question="q",
            artifact_bundle_path="/tmp/x",
            constraints=["custom_constraint"],
        )
        self.assertIn("custom_constraint", task.constraints)
        self.assertIn("no_external_api", task.constraints)

    def test_empty_task_id_rejected(self):
        with self.assertRaises(ValueError):
            UserTask(task_id="", question="q", artifact_bundle_path="/tmp/x")

    def test_whitespace_task_id_rejected(self):
        with self.assertRaises(ValueError):
            UserTask(task_id="   ", question="q", artifact_bundle_path="/tmp/x")

    def test_empty_question_rejected(self):
        with self.assertRaises(ValueError):
            UserTask(task_id="T1", question="", artifact_bundle_path="/tmp/x")

    def test_empty_bundle_path_rejected(self):
        with self.assertRaises(ValueError):
            UserTask(task_id="T1", question="q", artifact_bundle_path="")

    def test_from_dict_round_trip(self):
        task = _make_task()
        restored = UserTask.from_dict(task.to_dict())
        self.assertEqual(restored.task_id, task.task_id)
        self.assertEqual(restored.question, task.question)
        self.assertEqual(restored.concept, task.concept)


# ---------------------------------------------------------------------------
# Observation validation
# ---------------------------------------------------------------------------


class TestObservation(unittest.TestCase):

    def test_empty_observation_id_rejected(self):
        with self.assertRaises(ValueError):
            Observation(observation_id="", task_id="T1")

    def test_empty_task_id_rejected(self):
        with self.assertRaises(ValueError):
            Observation(observation_id="O1", task_id="")

    def test_from_dict_round_trip(self):
        obs = _make_observation()
        restored = Observation.from_dict(obs.to_dict())
        self.assertEqual(restored.observation_id, obs.observation_id)
        self.assertEqual(restored.artifact_refs, obs.artifact_refs)


# ---------------------------------------------------------------------------
# ReasoningSummary validation
# ---------------------------------------------------------------------------


class TestReasoningSummary(unittest.TestCase):

    def test_bad_mode_rejected(self):
        with self.assertRaises(ValueError):
            ReasoningSummary(
                reasoning_id="R1", task_id="T1", mode="invalid_mode"
            )

    def test_bad_confidence_rejected(self):
        with self.assertRaises(ValueError):
            ReasoningSummary(
                reasoning_id="R1", task_id="T1", confidence="confirmed"
            )

    def test_llm_future_valid(self):
        """llm_future is a legal mode value — no API behaviour triggered."""
        rs = ReasoningSummary(
            reasoning_id="R1",
            task_id="T1",
            mode="llm_future",
            confidence="unknown",
        )
        self.assertEqual(rs.mode, "llm_future")

    def test_deterministic_valid(self):
        rs = ReasoningSummary(
            reasoning_id="R1",
            task_id="T1",
            mode="deterministic",
            confidence="supported",
        )
        self.assertEqual(rs.mode, "deterministic")

    def test_noop_valid(self):
        rs = ReasoningSummary(
            reasoning_id="R1", task_id="T1", mode="noop", confidence="inferred"
        )
        self.assertEqual(rs.mode, "noop")

    def test_from_dict_round_trip(self):
        rs = _make_reasoning()
        restored = ReasoningSummary.from_dict(rs.to_dict())
        self.assertEqual(restored.mode, rs.mode)
        self.assertEqual(restored.confidence, rs.confidence)


# ---------------------------------------------------------------------------
# ToolCallProposal validation
# ---------------------------------------------------------------------------


class TestToolCallProposal(unittest.TestCase):

    def test_bad_allowed_action_rejected(self):
        with self.assertRaises(ValueError):
            ToolCallProposal(
                proposal_id="P1",
                task_id="T1",
                tool_name="exec_shell",
                allowed_action="execute",
            )

    def test_executable_now_rejected(self):
        with self.assertRaises(ValueError):
            ToolCallProposal(
                proposal_id="P1",
                task_id="T1",
                tool_name="exec_shell",
                is_executable_now=True,
            )

    def test_empty_tool_name_rejected(self):
        with self.assertRaises(ValueError):
            ToolCallProposal(
                proposal_id="P1", task_id="T1", tool_name=""
            )

    def test_non_json_params_rejected(self):
        with self.assertRaises(ValueError):
            ToolCallProposal(
                proposal_id="P1",
                task_id="T1",
                tool_name="read",
                params={"key": object()},  # not JSON serializable
            )

    def test_valid_deterministic_query_action(self):
        p = ToolCallProposal(
            proposal_id="P1",
            task_id="T1",
            tool_name="query",
            allowed_action="deterministic_query",
        )
        self.assertEqual(p.allowed_action, "deterministic_query")

    def test_valid_noop_action(self):
        p = ToolCallProposal(
            proposal_id="P1",
            task_id="T1",
            tool_name="noop_tool",
            allowed_action="noop",
        )
        self.assertEqual(p.allowed_action, "noop")

    def test_from_dict_round_trip(self):
        p = _make_proposal()
        restored = ToolCallProposal.from_dict(p.to_dict())
        self.assertEqual(restored.tool_name, p.tool_name)
        self.assertEqual(restored.params, p.params)


# ---------------------------------------------------------------------------
# ToolPlan validation
# ---------------------------------------------------------------------------


class TestToolPlan(unittest.TestCase):

    def test_executable_now_rejected(self):
        with self.assertRaises(ValueError):
            ToolPlan(
                plan_id="PL1",
                task_id="T1",
                is_executable_now=True,
            )

    def test_safety_notes_auto_filled(self):
        plan = ToolPlan(plan_id="PL1", task_id="T1", intent="summary")
        for note in ["no external LLM", "no Vivado", "no mutation"]:
            found = any(note in n for n in plan.safety_notes)
            self.assertTrue(found, f"Safety note '{note}' not found")

    def test_empty_plan_id_rejected(self):
        with self.assertRaises(ValueError):
            ToolPlan(plan_id="", task_id="T1")

    def test_from_dict_round_trip(self):
        plan = _make_plan()
        restored = ToolPlan.from_dict(plan.to_dict())
        self.assertEqual(restored.plan_id, plan.plan_id)
        self.assertEqual(len(restored.steps), 1)
        self.assertEqual(restored.steps[0].tool_name, "read_artifact")


# ---------------------------------------------------------------------------
# ToolResult validation
# ---------------------------------------------------------------------------


class TestToolResult(unittest.TestCase):

    def test_bad_status_rejected(self):
        with self.assertRaises(ValueError):
            ToolResult(
                result_id="R1",
                proposal_id="P1",
                task_id="T1",
                status="running",
            )

    def test_not_executed_valid(self):
        r = ToolResult(
            result_id="R1",
            proposal_id="P1",
            task_id="T1",
            status="not_executed",
        )
        self.assertEqual(r.status, "not_executed")

    def test_simulated_valid(self):
        r = ToolResult(
            result_id="R1",
            proposal_id="P1",
            task_id="T1",
            status="simulated",
        )
        self.assertEqual(r.status, "simulated")

    def test_completed_valid(self):
        """completed is a legal future-state value."""
        r = ToolResult(
            result_id="R1",
            proposal_id="P1",
            task_id="T1",
            status="completed",
        )
        self.assertEqual(r.status, "completed")

    def test_blocked_valid(self):
        r = ToolResult(
            result_id="R1",
            proposal_id="P1",
            task_id="T1",
            status="blocked",
        )
        self.assertEqual(r.status, "blocked")

    def test_from_dict_round_trip(self):
        r = _make_result()
        restored = ToolResult.from_dict(r.to_dict())
        self.assertEqual(restored.result_id, r.result_id)
        self.assertEqual(restored.status, r.status)


# ---------------------------------------------------------------------------
# Answer validation
# ---------------------------------------------------------------------------


class TestAnswer(unittest.TestCase):

    def test_empty_answer_text_rejected(self):
        with self.assertRaises(ValueError):
            Answer(answer_id="A1", task_id="T1", answer_text="")

    def test_whitespace_answer_text_rejected(self):
        with self.assertRaises(ValueError):
            Answer(answer_id="A1", task_id="T1", answer_text="   ")

    def test_bad_confidence_rejected(self):
        with self.assertRaises(ValueError):
            Answer(
                answer_id="A1",
                task_id="T1",
                answer_text="text",
                confidence="high",
            )

    def test_from_dict_round_trip(self):
        a = _make_answer()
        restored = Answer.from_dict(a.to_dict())
        self.assertEqual(restored.answer_text, a.answer_text)
        self.assertEqual(restored.referenced_result_ids, a.referenced_result_ids)


# ---------------------------------------------------------------------------
# GraphWriteProposal validation
# ---------------------------------------------------------------------------


class TestGraphWriteProposal(unittest.TestCase):

    def test_write_allowed_rejected(self):
        with self.assertRaises(ValueError):
            GraphWriteProposal(
                graph_write_id="G1",
                task_id="T1",
                is_write_allowed=True,
                blocking_reasons=[GRAPH_WRITE_DISABLED_REASON],
            )

    def test_missing_blocking_reason_rejected(self):
        with self.assertRaises(ValueError):
            GraphWriteProposal(
                graph_write_id="G1",
                task_id="T1",
                blocking_reasons=["some_other_reason"],
            )

    def test_empty_blocking_reasons_rejected(self):
        with self.assertRaises(ValueError):
            GraphWriteProposal(
                graph_write_id="G1", task_id="T1", blocking_reasons=[]
            )

    def test_valid_with_required_reason(self):
        gwp = _make_gwp()
        self.assertFalse(gwp.is_write_allowed)
        self.assertIn(GRAPH_WRITE_DISABLED_REASON, gwp.blocking_reasons)

    def test_from_dict_round_trip(self):
        gwp = _make_gwp()
        restored = GraphWriteProposal.from_dict(gwp.to_dict())
        self.assertEqual(restored.graph_write_id, gwp.graph_write_id)
        self.assertFalse(restored.is_write_allowed)


# ---------------------------------------------------------------------------
# validate_runtime_trace
# ---------------------------------------------------------------------------


class TestValidateRuntimeTrace(unittest.TestCase):

    def test_clean_trace_no_diagnostics(self):
        trace = _make_valid_trace()
        diags = validate_runtime_trace(trace)
        self.assertEqual(diags, [])

    def test_task_id_mismatch_observation(self):
        trace = _make_valid_trace()
        trace.observations.append(
            Observation(observation_id="OBS_BAD", task_id="WRONG")
        )
        diags = validate_runtime_trace(trace)
        self.assertTrue(len(diags) >= 1)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("OBS_BAD" in m and "WRONG" in m for m in messages)
        )

    def test_task_id_mismatch_reasoning(self):
        trace = _make_valid_trace()
        trace.reasoning.append(
            ReasoningSummary(
                reasoning_id="RSN_BAD", task_id="WRONG"
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("RSN_BAD" in m and "WRONG" in m for m in messages)
        )

    def test_task_id_mismatch_plan(self):
        trace = _make_valid_trace()
        trace.plans.append(
            ToolPlan(plan_id="PLAN_BAD", task_id="WRONG")
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("PLAN_BAD" in m and "WRONG" in m for m in messages)
        )

    def test_task_id_mismatch_result(self):
        trace = _make_valid_trace()
        trace.tool_results.append(
            ToolResult(
                result_id="RES_BAD", proposal_id="P1", task_id="WRONG"
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("RES_BAD" in m and "WRONG" in m for m in messages)
        )

    def test_task_id_mismatch_answer(self):
        trace = _make_valid_trace()
        trace.answers.append(
            Answer(
                answer_id="ANS_BAD",
                task_id="WRONG",
                answer_text="bad",
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("ANS_BAD" in m and "WRONG" in m for m in messages)
        )

    def test_task_id_mismatch_gwp(self):
        trace = _make_valid_trace()
        trace.graph_write_proposals.append(
            GraphWriteProposal(
                graph_write_id="GWP_BAD",
                task_id="WRONG",
                blocking_reasons=[GRAPH_WRITE_DISABLED_REASON],
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("GWP_BAD" in m and "WRONG" in m for m in messages)
        )

    def test_answer_references_nonexistent_result(self):
        trace = _make_valid_trace()
        trace.answers.append(
            Answer(
                answer_id="ANS_002",
                task_id="T001",
                answer_text="extra answer",
                referenced_result_ids=["RES_GHOST"],
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("ANS_002" in m and "RES_GHOST" in m for m in messages)
        )

    def test_gwp_references_nonexistent_answer(self):
        trace = _make_valid_trace()
        trace.graph_write_proposals.append(
            GraphWriteProposal(
                graph_write_id="GWP_002",
                task_id="T001",
                referenced_answer_ids=["ANS_GHOST"],
                blocking_reasons=[GRAPH_WRITE_DISABLED_REASON],
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("GWP_002" in m and "ANS_GHOST" in m for m in messages)
        )

    def test_empty_trace_valid(self):
        """Trace with only a task and no children is valid."""
        trace = AgentRuntimeTrace(task=_make_task())
        diags = validate_runtime_trace(trace)
        self.assertEqual(diags, [])

    # -- T015a: ToolResult.proposal_id existence --

    def test_tool_result_references_nonexistent_proposal(self):
        """ToolResult with a proposal_id not found in any plan step."""
        trace = _make_valid_trace()
        trace.tool_results.append(
            ToolResult(
                result_id="RES_002",
                proposal_id="PROP_GHOST",
                task_id="T001",
                status="not_executed",
            )
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("RES_002" in m and "PROP_GHOST" in m for m in messages),
            "Expected diagnostic about non-existent proposal_id PROP_GHOST",
        )

    def test_valid_trace_no_proposal_id_diagnostics(self):
        """Valid trace should produce zero proposal-id diagnostics."""
        trace = _make_valid_trace()
        diags = validate_runtime_trace(trace)
        proposal_diags = [
            d for d in diags if "proposal_id" in d["message"]
        ]
        self.assertEqual(proposal_diags, [])

    # -- T015a: ToolPlan.steps task_id consistency --

    def test_step_in_plan_has_wrong_task_id(self):
        """A ToolCallProposal inside a plan step with wrong task_id."""
        trace = _make_valid_trace()
        bad_step = ToolCallProposal(
            proposal_id="PROP_BAD",
            task_id="WRONG",
            tool_name="read_artifact",
            allowed_action="read_only_preview",
        )
        trace.plans.append(
            ToolPlan(plan_id="PLAN_002", task_id="T001", steps=[bad_step])
        )
        diags = validate_runtime_trace(trace)
        messages = [d["message"] for d in diags]
        self.assertTrue(
            any("PROP_BAD" in m and "WRONG" in m for m in messages),
            "Expected diagnostic about step task_id mismatch",
        )

    def test_step_in_plan_correct_task_id_no_diagnostic(self):
        """Step with correct task_id produces no step-mismatch diagnostic."""
        trace = _make_valid_trace()
        good_step = ToolCallProposal(
            proposal_id="PROP_002",
            task_id="T001",
            tool_name="query",
            allowed_action="deterministic_query",
        )
        trace.plans.append(
            ToolPlan(plan_id="PLAN_002", task_id="T001", steps=[good_step])
        )
        diags = validate_runtime_trace(trace)
        step_diags = [
            d for d in diags if "ToolCallProposal" in d["message"]
        ]
        self.assertEqual(step_diags, [])


# ---------------------------------------------------------------------------
# T015a: Answer limitations auto-ensure
# ---------------------------------------------------------------------------


class TestAnswerLimitationsAutoEnsure(unittest.TestCase):
    """T015a: Answer auto-ensures no_llm_semantic_reasoning limitation."""

    def test_auto_ensures_default_limitation(self):
        a = Answer(
            answer_id="A1",
            task_id="T001",
            answer_text="some text",
            confidence="supported",
        )
        self.assertIn("no_llm_semantic_reasoning", a.limitations)

    def test_custom_limitations_preserved(self):
        a = Answer(
            answer_id="A1",
            task_id="T001",
            answer_text="some text",
            confidence="supported",
            limitations=["custom_limit"],
        )
        self.assertIn("custom_limit", a.limitations)
        self.assertIn("no_llm_semantic_reasoning", a.limitations)

    def test_round_trip_preserves_limitation(self):
        a = Answer(
            answer_id="A1",
            task_id="T001",
            answer_text="some text",
            confidence="supported",
        )
        restored = Answer.from_dict(a.to_dict())
        self.assertIn("no_llm_semantic_reasoning", restored.limitations)

    def test_explicit_limitation_not_duplicated(self):
        a = Answer(
            answer_id="A1",
            task_id="T001",
            answer_text="some text",
            confidence="supported",
            limitations=["no_llm_semantic_reasoning"],
        )
        count = a.limitations.count("no_llm_semantic_reasoning")
        self.assertEqual(count, 1, "Should not duplicate the limitation")


# ---------------------------------------------------------------------------
# Forbidden imports / boundaries
# ---------------------------------------------------------------------------


class TestSafetyBoundaries(unittest.TestCase):

    def test_no_forbidden_imports(self):
        """Contract module must not import requests, urllib, subprocess, http."""
        import fpga_devmind.agent_runtime_contract as mod

        source = Path(mod.__file__).read_text()
        lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip().startswith("import ")
            or line.strip().startswith("from ")
        ]
        import_text = "\n".join(lines)
        forbidden = ["requests", "urllib", "subprocess", "http.client"]
        for pattern in forbidden:
            self.assertNotIn(
                pattern,
                import_text,
                "Forbidden import '{}' found in contract module".format(
                    pattern
                ),
            )

    def test_no_forbidden_runtime_calls(self):
        """Contract module must not call network or system functions."""
        import fpga_devmind.agent_runtime_contract as mod

        source = Path(mod.__file__).read_text()
        forbidden = [
            "requests.",
            "urllib.",
            "subprocess.",
            "os.system(",
            "os.popen(",
        ]
        for pattern in forbidden:
            self.assertNotIn(
                pattern,
                source,
                "Forbidden call '{}' found in contract module".format(
                    pattern
                ),
            )


if __name__ == "__main__":
    unittest.main()
