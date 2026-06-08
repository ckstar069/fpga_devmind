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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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
        print("  To install:")
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
