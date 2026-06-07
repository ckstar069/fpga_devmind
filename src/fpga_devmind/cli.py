"""Command-line entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from .agent import DEFAULT_AGENT_OUT, run_p1a_semantic_agent_dry_run
from .p1a import DEFAULT_OUT, DEFAULT_PROJECT, run_p1a
from .query import answer_question, check_freshness
from .smoke import DEFAULT_SMOKE_OUT, run_smoke, smoke_exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpga-devmind")
    sub = parser.add_subparsers(dest="command", required=True)

    p1a = sub.add_parser("p1a-understand-stage", help="Run deterministic P1a stage understanding")
    p1a.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    p1a.add_argument("--stage", default="L6_resource_opt")
    p1a.add_argument("--out", type=Path, default=DEFAULT_OUT)

    query = sub.add_parser("p1a-query", help="Query generated P1a graph and trace artifacts")
    query.add_argument("--artifacts", type=Path, default=DEFAULT_OUT)
    query.add_argument("--question", required=True)

    freshness = sub.add_parser("p1a-freshness", help="Check whether generated P1a artifacts are stale")
    freshness.add_argument("--artifacts", type=Path, default=DEFAULT_OUT)

    smoke = sub.add_parser("p1a-smoke", help="Run P1a smoke validation on representative samples")
    smoke.add_argument("--out-root", type=Path, default=DEFAULT_SMOKE_OUT)

    agent = sub.add_parser(
        "p1a-agent-understand-stage",
        help="Run provider-free P1a+ semantic Agent dry-run over P1a artifacts",
    )
    agent.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    agent.add_argument("--stage", default="L6_resource_opt")
    agent.add_argument("--question", required=True)
    agent.add_argument("--out", type=Path, default=DEFAULT_AGENT_OUT)
    agent.add_argument("--artifacts", type=Path)
    agent.add_argument("--model-result", type=Path, help="Optional local SemanticReasoningResult JSON fixture")
    agent.add_argument("--mock-semantic", action="store_true", help="Use built-in mock semantic provider")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "p1a-understand-stage":
        if args.stage != "L6_resource_opt":
            parser.error("P1a currently only supports --stage L6_resource_opt")
        graph = run_p1a(args.project, args.out)
        blocking = [d for d in graph.grounding_diagnostics if d.severity == "blocking"]
        print(f"Wrote P1a artifacts to {args.out}")
        print(f"Claims: {len(graph.candidate_claims)}")
        print(f"Evidence items: {len(graph.evidence_items)}")
        print(f"Blocking diagnostics: {len(blocking)}")
        return 1 if blocking else 0
    if args.command == "p1a-query":
        print(answer_question(args.artifacts, args.question), end="")
        return 0
    if args.command == "p1a-freshness":
        freshness = check_freshness(args.artifacts)
        print(f"Status: {freshness['status']}")
        print(f"Reason: {freshness['reason']}")
        print(f"Source snapshot: {freshness.get('source_snapshot_id') or 'unknown'}")
        for item in freshness.get("stale_files", []):
            print(f"Changed: {item['file_path']}")
        for file_path in freshness.get("missing_files", []):
            print(f"Missing: {file_path}")
        return 1 if freshness["status"] == "stale" else 0
    if args.command == "p1a-smoke":
        report = run_smoke(args.out_root)
        print(f"Wrote P1a smoke artifacts to {args.out_root}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Skipped: {report['summary']['skipped']}")
        for sample in report["samples"]:
            print(
                f"{sample['sample_id']}: {sample['status']} "
                f"claims={sample['claims']} evidence={sample['evidence_items']} "
                f"blocking={sample['blocking_diagnostics']} freshness={sample['freshness_status']}"
            )
        return smoke_exit_code(report)
    if args.command == "p1a-agent-understand-stage":
        result = run_p1a_semantic_agent_dry_run(
            project_root=args.project,
            stage_id=args.stage,
            question=args.question,
            out_dir=args.out,
            artifact_dir=args.artifacts,
            model_result_path=args.model_result,
            use_mock_semantic=args.mock_semantic,
        )
        report = result["grounding_report"]
        print(f"Wrote P1a+ agent dry-run artifacts to {args.out}")
        print(f"P1a artifacts: {result['artifact_dir']}")
        print(f"Mode: {result['agent_trace']['mode']}")
        print(f"Candidate claims: {report['summary']['candidate_claims']}")
        print(f"Blocking diagnostics: {report['summary']['blocking_diagnostics']}")
        print(f"Model output blocking diagnostics: {report['summary']['model_output_blocking_diagnostics']}")
        print(f"Freshness: {report['freshness']['status']}")
        return 1 if report["summary"]["blocking_diagnostics"] or report["summary"]["model_output_blocking_diagnostics"] else 0
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
