"""Command-line entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from .p1a import DEFAULT_OUT, DEFAULT_PROJECT, run_p1a


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpga-devmind")
    sub = parser.add_subparsers(dest="command", required=True)

    p1a = sub.add_parser("p1a-understand-stage", help="Run deterministic P1a stage understanding")
    p1a.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    p1a.add_argument("--stage", default="L6_resource_opt")
    p1a.add_argument("--out", type=Path, default=DEFAULT_OUT)
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
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
