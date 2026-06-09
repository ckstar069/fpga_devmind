"""Desktop sample artifact generator (T018).

Chains p1b-trace-concept → agent-noop-run into a single command so users
can generate loadable artifacts for the Desktop Shell with one invocation.

No LLM, no API, no Vivado, no fpga_project_* mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .agent_noop_runtime import run_noop_agent_once
from .p1b_cli import run_p1b_trace_concept
from .safety import ensure_safe_output_dir


DEFAULT_SAMPLE_PROJECT = Path(
    "/Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm"
)
DEFAULT_SAMPLE_CONCEPT = "peak_idx"
DEFAULT_SAMPLE_QUESTION = "summary"
DEFAULT_SAMPLE_OUT = Path("/tmp/fpga_devmind/desktop_sample")


@dataclass
class DesktopSampleResult:
    """Result from the desktop sample run."""

    p1b_dir: Path
    noop_dir: Path
    p1b_status: str
    noop_status: str
    status: str  # "ok" | "partial" | "error"
    messages: list[str] = field(default_factory=list)


def run_desktop_sample(
    project_root: Path = DEFAULT_SAMPLE_PROJECT,
    concept: str = DEFAULT_SAMPLE_CONCEPT,
    question: str = DEFAULT_SAMPLE_QUESTION,
    out_root: Path = DEFAULT_SAMPLE_OUT,
) -> DesktopSampleResult:
    """Generate sample artifacts for the Desktop Shell.

    Chains:
    1. ``p1b-trace-concept`` → P1b artifact bundle
    2. ``agent-noop-run`` → agent runtime trace

    Both outputs are placed under *out_root* and can be loaded by
    ``desktop_app --artifact-dir`` or ``desktop_app --recent``.
    """
    messages: list[str] = []
    safe_root = ensure_safe_output_dir(out_root, label="desktop sample")

    # --- Step 1: P1b concept trace ---
    p1b_dir = safe_root / "p1b"
    try:
        metadata = run_p1b_trace_concept(project_root, concept, p1b_dir)
        p1b_status = metadata.get("status", "unknown")
        messages.append(
            "P1b trace: concept={}, status={}, claims={}".format(
                metadata.get("concept", concept),
                p1b_status,
                metadata.get("mapping_claims", 0),
            )
        )
    except (ValueError, OSError) as exc:
        return DesktopSampleResult(
            p1b_dir=p1b_dir,
            noop_dir=safe_root / "noop_run",
            p1b_status="error",
            noop_status="skipped",
            status="error",
            messages=["P1b trace failed: {}".format(exc)],
        )

    # --- Step 2: No-op agent run ---
    noop_dir = safe_root / "noop_run"
    try:
        result = run_noop_agent_once(
            artifact_dir=p1b_dir,
            question=question,
            out_dir=noop_dir,
        )
        noop_status = result.status
        messages.append(
            "No-op run: task={}, status={}, diagnostics={}".format(
                result.trace.task.task_id,
                noop_status,
                len(result.diagnostics),
            )
        )
    except (ValueError, OSError) as exc:
        return DesktopSampleResult(
            p1b_dir=p1b_dir,
            noop_dir=noop_dir,
            p1b_status=p1b_status,
            noop_status="error",
            status="partial",
            messages=messages + ["No-op run failed: {}".format(exc)],
        )

    overall = "ok" if p1b_status != "blocked" and noop_status == "ok" else "partial"

    return DesktopSampleResult(
        p1b_dir=p1b_dir,
        noop_dir=noop_dir,
        p1b_status=p1b_status,
        noop_status=noop_status,
        status=overall,
        messages=messages,
    )
