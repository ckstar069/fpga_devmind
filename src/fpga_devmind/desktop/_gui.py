"""PySide6 GUI entry point for the Desktop Agent Shell (T020).

Delegates to product_shell.py.  This module is imported only when PySide6
is available.  If PySide6 is not installed, ``desktop_app.py`` prints a
dependency message instead.
"""

from __future__ import annotations

from typing import Any

from fpga_devmind.desktop.product_shell import (  # pyright: ignore[reportMissingImports]
    run_gui as _run_gui,
)


def run_gui(args: Any) -> int:  # pyright: ignore[reportExplicitAny]
    """Run the PySide6 GUI event loop."""
    return _run_gui(args)
