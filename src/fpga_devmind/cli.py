"""Command-line entry points."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .agent import DEFAULT_AGENT_OUT, run_p1a_semantic_agent_dry_run
from .desktop_sample_run import (
    DEFAULT_SAMPLE_CONCEPT,
    DEFAULT_SAMPLE_OUT,
    DEFAULT_SAMPLE_PROJECT,
    DEFAULT_SAMPLE_QUESTION,
)
from .p1a import DEFAULT_OUT, DEFAULT_PROJECT, run_p1a
from .provider_config import DEFAULT_PROVIDER_CONFIG_OUT, write_provider_config_draft
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
        help="Run external-API-free P1a+ semantic Agent dry-run over P1a artifacts",
    )
    agent.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    agent.add_argument("--stage", default="L6_resource_opt")
    agent.add_argument("--question", required=True)
    agent.add_argument("--out", type=Path, default=DEFAULT_AGENT_OUT)
    agent.add_argument("--artifacts", type=Path)
    agent.add_argument("--model-result", type=Path, help="Optional local SemanticReasoningResult JSON fixture")
    agent.add_argument("--mock-semantic", action="store_true", help="Use built-in mock semantic provider")
    agent.add_argument(
        "--external-provider",
        choices=["deepseek", "glm", "openai"],
        help="Select a future real provider; currently disabled and never calls external APIs",
    )
    agent.add_argument(
        "--allow-external-api",
        action="store_true",
        help="Acknowledge external provider intent; current adapters still do not call APIs",
    )

    provider_config = sub.add_parser(
        "provider-config-draft",
        help="Write a redacted provider configuration draft without calling external APIs",
    )
    provider_config.add_argument("--provider", choices=["deepseek", "glm", "openai"], required=True)
    provider_config.add_argument("--out", type=Path, default=DEFAULT_PROVIDER_CONFIG_OUT)

    p1b = sub.add_parser(
        "p1b-trace-concept",
        help="Run P1b concept trace pipeline (T002-T006) and write artifacts",
    )
    p1b.add_argument("--project", type=Path, required=True)
    p1b.add_argument("--concept", required=True)
    p1b.add_argument("--out", type=Path, required=True)

    p1b_project = sub.add_parser(
        "p1b-trace-project",
        help="Run project-level multi-concept trace (T024)",
    )
    p1b_project.add_argument("--project", type=Path, required=True)
    p1b_project.add_argument(
        "--concepts",
        required=True,
        help="Comma-separated concept names, or 'auto' for auto-discovery (T035)",
    )
    p1b_project.add_argument("--out", type=Path, required=True)

    p1b_discover = sub.add_parser(
        "p1b-discover-concepts",
        help="Auto-discover candidate concepts from project sources (T035)",
    )
    p1b_discover.add_argument("--project", type=Path, required=True)
    p1b_discover.add_argument("--out", type=Path, required=True)
    p1b_discover.add_argument("--top", type=int, default=12, help="Return top N candidates")

    p1b_benchmark = sub.add_parser(
        "p1b-benchmark-manifest",
        help="Generate benchmark manifest for all fpga_project_* directories (T035)",
    )
    p1b_benchmark.add_argument("--projects-parent", type=Path, required=True)
    p1b_benchmark.add_argument("--out", type=Path, required=True)

    p1b_eval = sub.add_parser(
        "p1b-evaluate-discovery",
        help="Evaluate auto-discovery against golden benchmark spec (T036)",
    )
    p1b_eval.add_argument("--project", type=Path, required=True)
    p1b_eval.add_argument("--golden-spec", type=Path, required=True)
    p1b_eval.add_argument("--out", type=Path, required=True)

    noop = sub.add_parser(
        "agent-noop-run",
        help="Run local no-op ReAct dry run over a P1a/P1b artifact bundle",
    )
    noop.add_argument("--artifact-dir", type=Path, required=True)
    noop.add_argument("--question", required=True)
    noop.add_argument("--out", type=Path, required=True)

    sample = sub.add_parser(
        "desktop-sample-run",
        help="Generate sample artifacts for Desktop Shell (P1b + agent-runtime)",
    )
    sample.add_argument("--project", type=Path, default=DEFAULT_SAMPLE_PROJECT)
    sample.add_argument("--concept", default=DEFAULT_SAMPLE_CONCEPT)
    sample.add_argument("--question", default=DEFAULT_SAMPLE_QUESTION)
    sample.add_argument("--out", type=Path, default=DEFAULT_SAMPLE_OUT)

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
            external_provider=args.external_provider,
            allow_external_api=args.allow_external_api,
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
    if args.command == "provider-config-draft":
        result = write_provider_config_draft(args.provider, args.out)
        draft = result["draft"]
        print(f"Wrote provider config draft to {result['path']}")
        print(f"Provider: {draft['provider_id']}")
        print(f"Adapter status: {draft['adapter_status']}")
        print(f"Enabled by default: {draft['enabled_by_default']}")
        print(f"API key value included: {draft['api_key_value_included']}")
        return 0
    if args.command == "p1b-trace-concept":
        from .p1b_cli import run_p1b_trace_concept as _run_p1b

        try:
            metadata = _run_p1b(args.project, args.concept, args.out)
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        print(f"Wrote P1b trace artifacts to {metadata['output_dir']}")
        print(f"Concept: {metadata['concept']}")
        print(f"Status: {metadata['status']}")
        print(f"Mapping claims: {metadata['mapping_claims']}")
        print(f"Evidence items: {metadata['evidence_items']}")
        print(f"Blocking diagnostics: {metadata['blocking_diagnostics']}")
        print(f"Elapsed: {metadata['elapsed_seconds']}s")
        return 1 if metadata["status"] == "blocked" else 0
    if args.command == "p1b-trace-project":
        from .p1b_project_cli import run_p1b_trace_project as _run_project

        concepts = [c.strip() for c in args.concepts.split(",") if c.strip()]
        try:
            metadata = _run_project(args.project, concepts, args.out)
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        print(f"Wrote project trace artifacts to {metadata['output_dir']}")
        print(f"Concepts: {', '.join(metadata['concepts_processed'])}")
        print(f"Status: {metadata['status']}")
        if metadata.get("concepts_failed"):
            print(f"Failed: {', '.join(metadata['concepts_failed'])}")
        print(f"Mapping claims: {metadata['mapping_claims']}")
        print(f"Evidence items: {metadata['evidence_items']}")
        print(f"Elapsed: {metadata['elapsed_seconds']}s")
        return 1 if metadata["status"] == "partial" else 0
    if args.command == "p1b-discover-concepts":
        from .p1b_discovery import discover_concepts
        from .safety import ensure_safe_output_dir

        safe_out = ensure_safe_output_dir(args.out, label="discovery output")
        safe_out.mkdir(parents=True, exist_ok=True)

        result = discover_concepts(args.project)

        # Write candidates JSON
        candidates_json = safe_out / "concept_candidates.json"
        candidates_json.write_text(
            json.dumps([asdict(c) for c in result.candidates[:args.top]], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Print summary
        print("Project: {}".format(result.project_id))
        print("Candidates found: {}".format(len(result.candidates)))
        print("Top {} candidates:".format(args.top))
        for c in result.candidates[:args.top]:
            print("  {} ({}): {} occurrences, {} [{}]".format(
                c.name, c.confidence, c.occurrence_count,
                ", ".join(c.source_sections), c.reason,
            ))
        print("Output: {}".format(candidates_json))
        return 0

    if args.command == "p1b-benchmark-manifest":
        from .benchmark_manifest import generate_benchmark_manifest
        from .safety import ensure_safe_output_dir

        safe_out = ensure_safe_output_dir(args.out, label="benchmark output")
        safe_out.mkdir(parents=True, exist_ok=True)

        manifest = generate_benchmark_manifest(args.projects_parent, safe_out)

        print("Benchmark manifest generated: {} projects".format(len(manifest)))
        for entry in manifest:
            print("  {}: L5={} L6={} RTL={} Tests={} | {} candidates".format(
                entry["project_id"],
                entry["has_L5"], entry["has_L6"], entry["has_RTL"], entry["has_tests"],
                len(entry.get("recommended_concepts", [])),
            ))
        return 0
    if args.command == "p1b-evaluate-discovery":
        from .discovery_eval import evaluate_discovery
        from .safety import ensure_safe_output_dir

        safe_out = ensure_safe_output_dir(args.out, label="evaluation output")
        safe_out.mkdir(parents=True, exist_ok=True)

        result = evaluate_discovery(args.project, args.golden_spec)

        # Write result JSON
        result_json = safe_out / "discovery_eval_result.json"
        result_json.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Print summary
        print("Project: {}".format(result.project_id))
        print("Golden core concepts: {}".format(result.golden_core_count))
        print("Golden secondary concepts: {}".format(result.golden_secondary_count))
        print("Matched core: {} / {}".format(len(result.matched_core), result.golden_core_count))
        if result.missed_core:
            print("Missed core: {}".format(", ".join(result.missed_core)))
        print("Matched secondary: {} / {}".format(len(result.matched_secondary), result.golden_secondary_count))
        if result.unexpected_selected:
            print("Unexpected selected: {}".format(", ".join(result.unexpected_selected)))
        print("Precision-like: {:.2%}".format(result.precision_like))
        print("Recall-like: {:.2%}".format(result.recall_like))
        print("Output: {}".format(result_json))
        return 0

    if args.command == "agent-noop-run":
        from .agent_noop_runtime import run_noop_agent_once

        try:
            result = run_noop_agent_once(
                artifact_dir=args.artifact_dir,
                question=args.question,
                out_dir=args.out,
            )
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        print("Wrote no-op agent trace to {}".format(result.output_dir))
        print("Trace: {}".format(result.artifact_path))
        print("Status: {}".format(result.status))
        print("Task: {}".format(result.trace.task.task_id))
        print("Confidence: {}".format(
            result.trace.answers[0].confidence
            if result.trace.answers else "n/a"
        ))
        print("Diagnostics: {}".format(len(result.diagnostics)))
        print("Graph write: blocked")
        return 1 if result.status != "ok" else 0
    if args.command == "desktop-sample-run":
        from .desktop_sample_run import run_desktop_sample

        try:
            result = run_desktop_sample(
                project_root=args.project,
                concept=args.concept,
                question=args.question,
                out_root=args.out,
            )
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        for msg in result.messages:
            print(msg)
        print("")
        print("P1b bundle:   {}".format(result.p1b_dir))
        print("No-op bundle: {}".format(result.noop_dir))
        print("")
        print("Open in Desktop Shell:")
        print("  PYTHONPATH=src python3 -m fpga_devmind.desktop_app --recent")
        print(
            "  PYTHONPATH=src python3 -m fpga_devmind.desktop_app "
            "--artifact-dir {}".format(result.p1b_dir)
        )
        return 1 if result.status == "error" else 0
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
