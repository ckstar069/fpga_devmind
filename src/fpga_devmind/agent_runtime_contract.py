"""Agent Runtime Contract for fpga_devmind (T015).

Structured artifact definitions for a future ReAct-like Agent loop.
This module defines data contracts only — no execution, no LLM,
no external API, no Vivado, no project mutation.

Schema version: agent-runtime-contract-0.1

Artifacts:
    UserTask           — user question + context bundle reference
    Observation        — artifact state snapshot at loop start
    ReasoningSummary   — deterministic or future-LLM reasoning
    ToolPlan           — ordered tool-call proposal list
    ToolCallProposal   — single proposed tool invocation
    ToolResult         — output from executing (or simulating) a tool call
    Answer             — final structured answer with referenced IDs
    GraphWriteProposal — proposed graph mutations (blocked by default)
    AgentRuntimeTrace  — top-level container for one loop iteration
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "agent-runtime-contract-0.1"

DEFAULT_SAFETY_CONSTRAINTS: list[str] = [
    "no_external_api",
    "no_vivado",
    "read_only",
    "no_target_project_mutation",
]

DEFAULT_SAFETY_NOTES: list[str] = [
    "no external LLM / API call",
    "no API key loading",
    "no Vivado / synthesis / implementation / bitstream",
    "no mutation to fpga_project_* target projects",
    "this is a contract definition; no tools are executed",
]

VALID_MODES: frozenset[str] = frozenset(
    {"deterministic", "noop", "llm_future"}
)
VALID_CONFIDENCES: frozenset[str] = frozenset(
    {"unknown", "inferred", "supported"}
)
VALID_ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {"read_only_preview", "deterministic_query", "noop"}
)
VALID_TOOL_STATUSES: frozenset[str] = frozenset(
    {"not_executed", "simulated", "completed", "blocked"}
)

GRAPH_WRITE_DISABLED_REASON = "graph_write_disabled_in_current_stage"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_non_empty(
    value: str, field_name: str, context: str = ""
) -> None:
    if not value or not value.strip():
        raise ValueError(
            "{} must be non-empty{}".format(
                field_name,
                " ({})".format(context) if context else "",
            )
        )


def _require_in(
    value: str, allowed: frozenset[str], field_name: str
) -> None:
    if value not in allowed:
        raise ValueError(
            "{} must be one of {}, got '{}'".format(
                field_name, sorted(allowed), value
            )
        )


def _ensure_default_constraints(constraints: list[str]) -> list[str]:
    """Return a copy of *constraints* with all defaults present."""
    result = list(constraints)
    for c in DEFAULT_SAFETY_CONSTRAINTS:
        if c not in result:
            result.append(c)
    return result


def _ensure_default_safety_notes(notes: list[str]) -> list[str]:
    """Return a copy of *notes* with all defaults present."""
    result = list(notes)
    for n in DEFAULT_SAFETY_NOTES:
        if n not in result:
            result.append(n)
    return result


# ---------------------------------------------------------------------------
# 1. UserTask
# ---------------------------------------------------------------------------


@dataclass
class UserTask:
    """User's original question and context bundle reference."""

    task_id: str = ""
    question: str = ""
    created_at: str = ""
    artifact_bundle_path: str = ""
    bundle_type: str = ""
    concept: str | None = None
    constraints: list[str] = field(default_factory=list)
    requested_intent: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.task_id, "task_id")
        _require_non_empty(self.question, "question")
        _require_non_empty(self.artifact_bundle_path, "artifact_bundle_path")
        self.constraints = _ensure_default_constraints(self.constraints)

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "task_id": self.task_id,
            "question": self.question,
            "created_at": self.created_at,
            "artifact_bundle_path": self.artifact_bundle_path,
            "bundle_type": self.bundle_type,
            "concept": self.concept,
            "constraints": list(self.constraints),
            "requested_intent": self.requested_intent,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> UserTask:
        return cls(
            task_id=data.get("task_id", ""),
            question=data.get("question", ""),
            created_at=data.get("created_at", ""),
            artifact_bundle_path=data.get("artifact_bundle_path", ""),
            bundle_type=data.get("bundle_type", ""),
            concept=data.get("concept"),
            constraints=data.get("constraints", []),
            requested_intent=data.get("requested_intent"),
        )


# ---------------------------------------------------------------------------
# 2. Observation
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    """Artifact state snapshot at the start of a loop iteration."""

    observation_id: str = ""
    task_id: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    summary: str = ""
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty(self.observation_id, "observation_id")
        _require_non_empty(self.task_id, "task_id")

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "observation_id": self.observation_id,
            "task_id": self.task_id,
            "artifact_refs": list(self.artifact_refs),
            "summary": self.summary,
            "referenced_claim_ids": list(self.referenced_claim_ids),
            "referenced_evidence_ids": list(self.referenced_evidence_ids),
            "referenced_node_ids": list(self.referenced_node_ids),
            "referenced_diagnostic_ids": list(
                self.referenced_diagnostic_ids
            ),
            "uncertainty_notes": list(self.uncertainty_notes),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> Observation:
        return cls(
            observation_id=data.get("observation_id", ""),
            task_id=data.get("task_id", ""),
            artifact_refs=data.get("artifact_refs", []),
            summary=data.get("summary", ""),
            referenced_claim_ids=data.get("referenced_claim_ids", []),
            referenced_evidence_ids=data.get(
                "referenced_evidence_ids", []
            ),
            referenced_node_ids=data.get("referenced_node_ids", []),
            referenced_diagnostic_ids=data.get(
                "referenced_diagnostic_ids", []
            ),
            uncertainty_notes=data.get("uncertainty_notes", []),
        )


# ---------------------------------------------------------------------------
# 3. ReasoningSummary
# ---------------------------------------------------------------------------


@dataclass
class ReasoningSummary:
    """Reasoning about an observation — deterministic, noop, or future LLM."""

    reasoning_id: str = ""
    task_id: str = ""
    mode: str = "deterministic"
    summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    referenced_observation_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty(self.reasoning_id, "reasoning_id")
        _require_non_empty(self.task_id, "task_id")
        _require_in(self.mode, VALID_MODES, "mode")
        _require_in(self.confidence, VALID_CONFIDENCES, "confidence")

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "reasoning_id": self.reasoning_id,
            "task_id": self.task_id,
            "mode": self.mode,
            "summary": self.summary,
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "confidence": self.confidence,
            "referenced_observation_ids": list(
                self.referenced_observation_ids
            ),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> ReasoningSummary:
        return cls(
            reasoning_id=data.get("reasoning_id", ""),
            task_id=data.get("task_id", ""),
            mode=data.get("mode", "deterministic"),
            summary=data.get("summary", ""),
            assumptions=data.get("assumptions", []),
            unknowns=data.get("unknowns", []),
            confidence=data.get("confidence", "unknown"),
            referenced_observation_ids=data.get(
                "referenced_observation_ids", []
            ),
        )


# ---------------------------------------------------------------------------
# 4. ToolCallProposal
# ---------------------------------------------------------------------------


@dataclass
class ToolCallProposal:
    """Single proposed tool invocation within a plan."""

    proposal_id: str = ""
    task_id: str = ""
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)  # pyright: ignore[reportExplicitAny]
    rationale: str = ""
    expected_read_artifacts: list[str] = field(default_factory=list)
    allowed_action: str = "read_only_preview"
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    is_executable_now: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.proposal_id, "proposal_id")
        _require_non_empty(self.task_id, "task_id")
        _require_non_empty(self.tool_name, "tool_name")
        _require_in(
            self.allowed_action, VALID_ALLOWED_ACTIONS, "allowed_action"
        )
        if self.is_executable_now:
            raise ValueError(
                "is_executable_now must be False in current contract stage"
            )
        # Verify params is JSON serializable.
        try:
            json.dumps(self.params)
        except (TypeError, ValueError) as exc:
            raise ValueError("params must be JSON serializable") from exc

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "proposal_id": self.proposal_id,
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "params": dict(self.params),
            "rationale": self.rationale,
            "expected_read_artifacts": list(self.expected_read_artifacts),
            "allowed_action": self.allowed_action,
            "referenced_claim_ids": list(self.referenced_claim_ids),
            "referenced_evidence_ids": list(self.referenced_evidence_ids),
            "referenced_node_ids": list(self.referenced_node_ids),
            "referenced_diagnostic_ids": list(
                self.referenced_diagnostic_ids
            ),
            "is_executable_now": self.is_executable_now,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> ToolCallProposal:
        return cls(
            proposal_id=data.get("proposal_id", ""),
            task_id=data.get("task_id", ""),
            tool_name=data.get("tool_name", ""),
            params=data.get("params", {}),
            rationale=data.get("rationale", ""),
            expected_read_artifacts=data.get(
                "expected_read_artifacts", []
            ),
            allowed_action=data.get("allowed_action", "read_only_preview"),
            referenced_claim_ids=data.get("referenced_claim_ids", []),
            referenced_evidence_ids=data.get(
                "referenced_evidence_ids", []
            ),
            referenced_node_ids=data.get("referenced_node_ids", []),
            referenced_diagnostic_ids=data.get(
                "referenced_diagnostic_ids", []
            ),
            is_executable_now=data.get("is_executable_now", False),
        )


# ---------------------------------------------------------------------------
# 5. ToolPlan
# ---------------------------------------------------------------------------


@dataclass
class ToolPlan:
    """Ordered list of tool-call proposals for a single intent."""

    plan_id: str = ""
    task_id: str = ""
    intent: str = ""
    steps: list[ToolCallProposal] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    is_executable_now: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.plan_id, "plan_id")
        _require_non_empty(self.task_id, "task_id")
        if self.is_executable_now:
            raise ValueError(
                "is_executable_now must be False in current contract stage"
            )
        self.safety_notes = _ensure_default_safety_notes(self.safety_notes)

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "intent": self.intent,
            "steps": [s.to_dict() for s in self.steps],
            "safety_notes": list(self.safety_notes),
            "is_executable_now": self.is_executable_now,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> ToolPlan:
        steps = [
            ToolCallProposal.from_dict(s) for s in data.get("steps", [])
        ]
        return cls(
            plan_id=data.get("plan_id", ""),
            task_id=data.get("task_id", ""),
            intent=data.get("intent", ""),
            steps=steps,
            safety_notes=data.get("safety_notes", []),
            is_executable_now=data.get("is_executable_now", False),
        )


# ---------------------------------------------------------------------------
# 6. ToolResult
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """Output from executing (or simulating) a tool call."""

    result_id: str = ""
    proposal_id: str = ""
    task_id: str = ""
    status: str = "not_executed"
    result_summary: str = ""
    output_artifact_refs: list[str] = field(default_factory=list)
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty(self.result_id, "result_id")
        _require_non_empty(self.proposal_id, "proposal_id")
        _require_non_empty(self.task_id, "task_id")
        _require_in(self.status, VALID_TOOL_STATUSES, "status")

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "result_id": self.result_id,
            "proposal_id": self.proposal_id,
            "task_id": self.task_id,
            "status": self.status,
            "result_summary": self.result_summary,
            "output_artifact_refs": list(self.output_artifact_refs),
            "referenced_claim_ids": list(self.referenced_claim_ids),
            "referenced_evidence_ids": list(self.referenced_evidence_ids),
            "referenced_node_ids": list(self.referenced_node_ids),
            "referenced_diagnostic_ids": list(
                self.referenced_diagnostic_ids
            ),
            "blocking_reasons": list(self.blocking_reasons),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> ToolResult:
        return cls(
            result_id=data.get("result_id", ""),
            proposal_id=data.get("proposal_id", ""),
            task_id=data.get("task_id", ""),
            status=data.get("status", "not_executed"),
            result_summary=data.get("result_summary", ""),
            output_artifact_refs=data.get("output_artifact_refs", []),
            referenced_claim_ids=data.get("referenced_claim_ids", []),
            referenced_evidence_ids=data.get(
                "referenced_evidence_ids", []
            ),
            referenced_node_ids=data.get("referenced_node_ids", []),
            referenced_diagnostic_ids=data.get(
                "referenced_diagnostic_ids", []
            ),
            blocking_reasons=data.get("blocking_reasons", []),
        )


# ---------------------------------------------------------------------------
# 7. Answer
# ---------------------------------------------------------------------------


@dataclass
class Answer:
    """Final structured answer with referenced IDs and confidence."""

    answer_id: str = ""
    task_id: str = ""
    answer_text: str = ""
    confidence: str = "unknown"
    referenced_result_ids: list[str] = field(default_factory=list)
    referenced_claim_ids: list[str] = field(default_factory=list)
    referenced_evidence_ids: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)
    referenced_diagnostic_ids: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty(self.answer_id, "answer_id")
        _require_non_empty(self.task_id, "task_id")
        _require_non_empty(self.answer_text, "answer_text")
        _require_in(self.confidence, VALID_CONFIDENCES, "confidence")
        # Auto-ensure default limitation for deterministic/noop contract stage.
        if "no_llm_semantic_reasoning" not in self.limitations:
            self.limitations = list(self.limitations) + [
                "no_llm_semantic_reasoning"
            ]

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "answer_id": self.answer_id,
            "task_id": self.task_id,
            "answer_text": self.answer_text,
            "confidence": self.confidence,
            "referenced_result_ids": list(self.referenced_result_ids),
            "referenced_claim_ids": list(self.referenced_claim_ids),
            "referenced_evidence_ids": list(self.referenced_evidence_ids),
            "referenced_node_ids": list(self.referenced_node_ids),
            "referenced_diagnostic_ids": list(
                self.referenced_diagnostic_ids
            ),
            "uncertainty_notes": list(self.uncertainty_notes),
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> Answer:
        return cls(
            answer_id=data.get("answer_id", ""),
            task_id=data.get("task_id", ""),
            answer_text=data.get("answer_text", ""),
            confidence=data.get("confidence", "unknown"),
            referenced_result_ids=data.get("referenced_result_ids", []),
            referenced_claim_ids=data.get("referenced_claim_ids", []),
            referenced_evidence_ids=data.get(
                "referenced_evidence_ids", []
            ),
            referenced_node_ids=data.get("referenced_node_ids", []),
            referenced_diagnostic_ids=data.get(
                "referenced_diagnostic_ids", []
            ),
            uncertainty_notes=data.get("uncertainty_notes", []),
            limitations=data.get("limitations", []),
        )


# ---------------------------------------------------------------------------
# 8. GraphWriteProposal
# ---------------------------------------------------------------------------


@dataclass
class GraphWriteProposal:
    """Proposed graph mutations — blocked by default in current stage."""

    graph_write_id: str = ""
    task_id: str = ""
    proposed_nodes: list[dict[str, Any]] = field(default_factory=list)  # pyright: ignore[reportExplicitAny]
    proposed_edges: list[dict[str, Any]] = field(default_factory=list)  # pyright: ignore[reportExplicitAny]
    proposed_claims: list[dict[str, Any]] = field(default_factory=list)  # pyright: ignore[reportExplicitAny]
    referenced_answer_ids: list[str] = field(default_factory=list)
    is_write_allowed: bool = False
    blocking_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty(self.graph_write_id, "graph_write_id")
        _require_non_empty(self.task_id, "task_id")
        if self.is_write_allowed:
            raise ValueError(
                "is_write_allowed must be False in current contract stage"
            )
        if GRAPH_WRITE_DISABLED_REASON not in self.blocking_reasons:
            raise ValueError(
                "blocking_reasons must contain '{}'".format(
                    GRAPH_WRITE_DISABLED_REASON
                )
            )

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "graph_write_id": self.graph_write_id,
            "task_id": self.task_id,
            "proposed_nodes": list(self.proposed_nodes),
            "proposed_edges": list(self.proposed_edges),
            "proposed_claims": list(self.proposed_claims),
            "referenced_answer_ids": list(self.referenced_answer_ids),
            "is_write_allowed": self.is_write_allowed,
            "blocking_reasons": list(self.blocking_reasons),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> GraphWriteProposal:
        return cls(
            graph_write_id=data.get("graph_write_id", ""),
            task_id=data.get("task_id", ""),
            proposed_nodes=data.get("proposed_nodes", []),
            proposed_edges=data.get("proposed_edges", []),
            proposed_claims=data.get("proposed_claims", []),
            referenced_answer_ids=data.get("referenced_answer_ids", []),
            is_write_allowed=data.get("is_write_allowed", False),
            blocking_reasons=data.get("blocking_reasons", []),
        )


# ---------------------------------------------------------------------------
# 9. AgentRuntimeTrace — top-level container
# ---------------------------------------------------------------------------


@dataclass
class AgentRuntimeTrace:
    """Complete trace of one Agent loop iteration."""

    task: UserTask
    schema_version: str = SCHEMA_VERSION
    observations: list[Observation] = field(default_factory=list)
    reasoning: list[ReasoningSummary] = field(default_factory=list)
    plans: list[ToolPlan] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    answers: list[Answer] = field(default_factory=list)
    graph_write_proposals: list[GraphWriteProposal] = field(
        default_factory=list
    )
    runtime_diagnostics: list[dict[str, Any]] = field(default_factory=list)  # pyright: ignore[reportExplicitAny]

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "schema_version": self.schema_version,
            "task": self.task.to_dict(),
            "observations": [o.to_dict() for o in self.observations],
            "reasoning": [r.to_dict() for r in self.reasoning],
            "plans": [p.to_dict() for p in self.plans],
            "tool_results": [tr.to_dict() for tr in self.tool_results],
            "answers": [a.to_dict() for a in self.answers],
            "graph_write_proposals": [
                g.to_dict() for g in self.graph_write_proposals
            ],
            "runtime_diagnostics": list(self.runtime_diagnostics),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> AgentRuntimeTrace:
        task_data = data.get("task", {})
        return cls(
            task=UserTask.from_dict(task_data),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            observations=[
                Observation.from_dict(o)
                for o in data.get("observations", [])
            ],
            reasoning=[
                ReasoningSummary.from_dict(r)
                for r in data.get("reasoning", [])
            ],
            plans=[
                ToolPlan.from_dict(p) for p in data.get("plans", [])
            ],
            tool_results=[
                ToolResult.from_dict(tr)
                for tr in data.get("tool_results", [])
            ],
            answers=[
                Answer.from_dict(a) for a in data.get("answers", [])
            ],
            graph_write_proposals=[
                GraphWriteProposal.from_dict(g)
                for g in data.get("graph_write_proposals", [])
            ],
            runtime_diagnostics=data.get("runtime_diagnostics", []),
        )

    @classmethod
    def from_json(cls, text: str) -> AgentRuntimeTrace:
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Trace-level validation
# ---------------------------------------------------------------------------


def validate_runtime_trace(
    trace: AgentRuntimeTrace,
) -> list[dict[str, str]]:
    """Validate cross-reference integrity of *trace*.

    Returns a list of diagnostic dicts with keys ``severity`` and
    ``message``.  An empty list means no issues found.
    """
    diags: list[dict[str, str]] = []
    task_id = trace.task.task_id

    result_ids = {r.result_id for r in trace.tool_results}
    answer_ids = {a.answer_id for a in trace.answers}

    # Task ID consistency across all children.
    _check_task_id(trace.observations, "observation_id", task_id, diags)
    _check_task_id(trace.reasoning, "reasoning_id", task_id, diags)
    _check_task_id(trace.plans, "plan_id", task_id, diags)
    _check_task_id(trace.tool_results, "result_id", task_id, diags)
    _check_task_id(trace.answers, "answer_id", task_id, diags)
    _check_task_id(
        trace.graph_write_proposals, "graph_write_id", task_id, diags
    )

    # ToolPlan.steps task_id consistency.
    for plan in trace.plans:
        for step in plan.steps:
            if step.task_id != task_id:
                diags.append({
                    "severity": "error",
                    "message": "ToolCallProposal {} has task_id '{}' != '{}'".format(
                        step.proposal_id, step.task_id, task_id
                    ),
                })

    # Collect all proposal IDs from plans.
    proposal_ids: set[str] = set()
    for plan in trace.plans:
        for step in plan.steps:
            proposal_ids.add(step.proposal_id)

    # ToolResult.proposal_id must reference an existing proposal.
    for tr in trace.tool_results:
        if tr.proposal_id not in proposal_ids:
            diags.append({
                "severity": "error",
                "message": "ToolResult {} references non-existent proposal_id '{}'".format(
                    tr.result_id, tr.proposal_id
                ),
            })

    # Answer references existing result IDs.
    for a in trace.answers:
        for rid in a.referenced_result_ids:
            if rid not in result_ids:
                diags.append({
                    "severity": "error",
                    "message": "Answer {} references non-existent result_id '{}'".format(
                        a.answer_id, rid
                    ),
                })

    # Graph write proposals reference existing answer IDs.
    for g in trace.graph_write_proposals:
        for aid in g.referenced_answer_ids:
            if aid not in answer_ids:
                diags.append({
                    "severity": "error",
                    "message": "GraphWriteProposal {} references non-existent answer_id '{}'".format(
                        g.graph_write_id, aid
                    ),
                })

    return diags


def _check_task_id(
    items: list[Any],  # pyright: ignore[reportExplicitAny]
    id_attr: str,
    expected_task_id: str,
    diags: list[dict[str, str]],
) -> None:
    for item in items:
        item_task_id = getattr(item, "task_id", None)
        item_id = getattr(item, id_attr, "?")
        if item_task_id != expected_task_id:
            diags.append({
                "severity": "error",
                "message": "{} {} has task_id '{}' != '{}'".format(
                    type(item).__name__,
                    item_id,
                    item_task_id,
                    expected_task_id,
                ),
            })
