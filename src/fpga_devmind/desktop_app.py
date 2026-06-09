"""Desktop Agent Shell entry point (T009).

Tries to launch a PySide6 GUI.  If PySide6 is not installed, prints a
gentle dependency message and exits gracefully.

Usage:
    PYTHONPATH=src python3 -m fpga_devmind.desktop_app --artifact-dir /tmp/...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpga-devmind-desktop")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Path to a P1a or P1b artifact directory",
    )
    parser.add_argument(
        "--recent",
        action="store_true",
        default=False,
        help="Auto-select the most recent artifact bundle from /tmp/fpga_devmind",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve --recent: auto-select the most recent artifact bundle.
    if args.recent:
        from fpga_devmind.desktop.sample_artifacts import (
            find_recent_artifact_bundles,
        )

        bundles = find_recent_artifact_bundles()
        if not bundles:
            print("No artifact bundles found in /tmp/fpga_devmind.")
            print()
            print("Generate one first, for example:")
            print(
                "  PYTHONPATH=src python3 -m fpga_devmind.cli "
                "p1b-trace-concept \\"
            )
            print(
                "    --project /path/to/fpga_project_coarse_sync_glm \\"
            )
            print("    --concept peak_idx \\")
            print("    --out /tmp/fpga_devmind/p1b_peak_idx")
            return 0
        args.artifact_dir = bundles[0].path
        print("Auto-selected: {} ({})".format(
            bundles[0].path, bundles[0].bundle_type
        ))

    # Attempt PySide6 import with graceful fallback.
    try:
        from PySide6 import QtWidgets  # type: ignore[import-untyped]
    except ImportError:
        print("=" * 60)
        print("  fpga_devmind Desktop Agent Shell (T009)")
        print("=" * 60)
        print()
        print("  PySide6 is not installed.")
        print()
        print("  To install the desktop extras:")
        print('    pip install -e ".[desktop]"')
        print()
        print("  Or install PySide6 directly:")
        print("    pip3 install pyside6")
        print()
        print("  The loader / view-model layer is available without GUI:")
        print(
            "    from fpga_devmind.desktop.artifact_loader import load_bundle"
        )
        print(
            "    from fpga_devmind.desktop.view_models import "
            "build_run_summary"
        )
        print()
        print("  For CLI-only artifact inspection, use:")
        print("    fpga-devmind p1b-trace-concept ...")
        print()
        return 0

    from fpga_devmind.desktop._gui import run_gui

    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
