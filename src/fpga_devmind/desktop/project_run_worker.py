"""QThread worker for running the project trace pipeline in the GUI (T026).

This module is imported only when PySide6 is available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore


class ProjectRunWorker(QtCore.QThread):
    """Worker thread that calls run_p1b_trace_project without blocking the GUI."""

    finished_success = QtCore.Signal(dict)  # metadata dict
    finished_error = QtCore.Signal(str)  # error message

    def __init__(
        self,
        project_root: Path,
        concepts: list[str],
        out_dir: Path,
        parent: Any = None,  # pyright: ignore[reportExplicitAny]
    ) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._concepts = concepts
        self._out_dir = out_dir

    def run(self) -> None:
        """Execute the pipeline in the worker thread."""
        try:
            from fpga_devmind.p1b_project_cli import run_p1b_trace_project

            metadata = run_p1b_trace_project(
                self._project_root,
                self._concepts,
                self._out_dir,
            )
            self.finished_success.emit(metadata)
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(str(exc))
