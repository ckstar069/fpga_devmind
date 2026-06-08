"""PySide6 GUI for the Desktop Agent Shell (T009).

This module is imported only when PySide6 is available.  If PySide6 is
not installed, ``desktop_app.py`` prints a dependency message instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWidgets  # type: ignore[import-untyped]

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.view_models import (
    BundleSummaryViewModel,
    JsonTreeNode,
    MarkdownPreviewViewModel,
    RunSummaryViewModel,
    build_bundle_summary,
    build_json_tree,
    build_markdown_preview,
    build_run_summary,
)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QtWidgets.QMainWindow):
    """T009 minimum viable desktop shell."""

    def __init__(self, artifact_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("fpga_devmind — Desktop Agent Shell (T009)")
        self.resize(1200, 800)

        self._central = QtWidgets.QWidget()
        self.setCentralWidget(self._central)
        self._layout = QtWidgets.QVBoxLayout(self._central)

        # --- Top: directory picker + load button ---
        self._dir_layout = QtWidgets.QHBoxLayout()
        self._dir_input = QtWidgets.QLineEdit()
        self._dir_input.setPlaceholderText(
            "Artifact directory (e.g. /tmp/fpga_devmind/p1b_peak_idx)"
        )
        if artifact_dir is not None:
            self._dir_input.setText(str(artifact_dir))
        self._browse_btn = QtWidgets.QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)
        self._load_btn = QtWidgets.QPushButton("Load Bundle")
        self._load_btn.clicked.connect(self._on_load)
        self._dir_layout.addWidget(self._dir_input, stretch=1)
        self._dir_layout.addWidget(self._browse_btn)
        self._dir_layout.addWidget(self._load_btn)
        self._layout.addLayout(self._dir_layout)

        # --- Status label ---
        self._status = QtWidgets.QLabel("No bundle loaded.")
        self._layout.addWidget(self._status)

        # --- Tabs ---
        self._tabs = QtWidgets.QTabWidget()
        self._layout.addWidget(self._tabs, stretch=1)

        # Run Summary tab
        self._run_summary_widget = QtWidgets.QWidget()
        self._run_summary_layout = QtWidgets.QFormLayout(
            self._run_summary_widget
        )
        self._tabs.addTab(self._run_summary_widget, "Run Summary")

        # JSON Tree tab
        self._json_tree_widget = QtWidgets.QWidget()
        self._json_tree_layout = QtWidgets.QVBoxLayout(
            self._json_tree_widget
        )
        self._json_selector = QtWidgets.QComboBox()
        self._json_selector.currentTextChanged.connect(
            self._on_json_selected
        )
        self._json_tree_layout.addWidget(self._json_selector)
        self._json_tree_view = QtWidgets.QTreeWidget()
        self._json_tree_view.setHeaderLabels(["Key", "Value", "Type"])
        self._json_tree_layout.addWidget(self._json_tree_view)
        self._tabs.addTab(self._json_tree_widget, "JSON Tree")

        # Markdown Preview tab
        self._md_widget = QtWidgets.QWidget()
        self._md_layout = QtWidgets.QVBoxLayout(self._md_widget)
        self._md_text = QtWidgets.QPlainTextEdit()
        self._md_text.setReadOnly(True)
        self._md_layout.addWidget(self._md_text)
        self._tabs.addTab(self._md_widget, "Markdown")

        # Diagnostics tab
        self._diag_widget = QtWidgets.QWidget()
        self._diag_layout = QtWidgets.QVBoxLayout(self._diag_widget)
        self._diag_list = QtWidgets.QListWidget()
        self._diag_layout.addWidget(self._diag_list)
        self._tabs.addTab(self._diag_widget, "Diagnostics")

        self._bundle = None
        if artifact_dir is not None:
            self._on_load()

    # --- slots ---

    def _on_browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Artifact Directory"
        )
        if path:
            self._dir_input.setText(path)

    def _on_load(self) -> None:
        path_str = self._dir_input.text().strip()
        if not path_str:
            self._status.setText("Please enter an artifact directory.")
            return

        path = Path(path_str)
        self._bundle = load_bundle(path)

        self._update_run_summary()
        self._update_json_selector()
        self._update_markdown()
        self._update_diagnostics()

        summary = build_bundle_summary(self._bundle)
        status_text = (
            "Bundle: {} | Complete: {} | Artifacts: {} | "
            "Errors: {} | Warnings: {}"
        ).format(
            summary.bundle_type,
            "yes" if summary.is_complete else "no",
            summary.artifact_count,
            summary.error_count,
            summary.warning_count,
        )
        self._status.setText(status_text)

    def _update_run_summary(self) -> None:
        # Clear previous fields.
        while self._run_summary_layout.rowCount() > 0:
            self._run_summary_layout.removeRow(0)

        if self._bundle is None:
            self._run_summary_layout.addRow(
                "Status", QtWidgets.QLabel("No bundle loaded.")
            )
            return

        vm = build_run_summary(self._bundle)
        if not vm.is_loaded:
            self._run_summary_layout.addRow(
                "Error", QtWidgets.QLabel(vm.load_error or "Unknown error")
            )
            return

        self._run_summary_layout.addRow(
            "Concept", QtWidgets.QLabel(vm.concept)
        )
        self._run_summary_layout.addRow(
            "Status", QtWidgets.QLabel(vm.status)
        )
        self._run_summary_layout.addRow(
            "Project", QtWidgets.QLabel(vm.project_root)
        )
        self._run_summary_layout.addRow(
            "Output", QtWidgets.QLabel(vm.output_dir)
        )
        self._run_summary_layout.addRow(
            "Elapsed",
            QtWidgets.QLabel("{:.3f}s".format(vm.elapsed_seconds)),
        )
        self._run_summary_layout.addRow(
            "Mapping Claims",
            QtWidgets.QLabel(str(vm.mapping_claims)),
        )
        self._run_summary_layout.addRow(
            "Evidence Items",
            QtWidgets.QLabel(str(vm.evidence_items)),
        )
        self._run_summary_layout.addRow(
            "Blocking Diagnostics",
            QtWidgets.QLabel(str(vm.blocking_diagnostics)),
        )
        self._run_summary_layout.addRow(
            "Schema Version",
            QtWidgets.QLabel(vm.schema_version),
        )

    def _update_json_selector(self) -> None:
        self._json_selector.clear()
        if self._bundle is None:
            return
        for name in sorted(self._bundle.artifacts.keys()):
            artifact = self._bundle.artifacts[name]
            if artifact.content_type == "json":
                self._json_selector.addItem(name)
        if self._json_selector.count() > 0:
            self._on_json_selected(self._json_selector.currentText())

    def _on_json_selected(self, name: str) -> None:
        self._json_tree_view.clear()
        if self._bundle is None or not name:
            return

        vm = build_json_tree(self._bundle, name)
        if not vm.is_loaded or vm.root is None:
            item = QtWidgets.QTreeWidgetItem(
                ["Error", vm.load_error or "Unknown", "error"]
            )
            self._json_tree_view.addTopLevelItem(item)
            return

        self._add_tree_node(None, vm.root)
        self._json_tree_view.expandToDepth(2)

    def _add_tree_node(
        self,
        parent: QtWidgets.QTreeWidgetItem | None,
        node: JsonTreeNode,
    ) -> QtWidgets.QTreeWidgetItem:
        item = QtWidgets.QTreeWidgetItem([node.key, node.value, node.value_type])
        if parent is None:
            self._json_tree_view.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            self._add_tree_node(item, child)
        return item

    def _update_markdown(self) -> None:
        self._md_text.clear()
        if self._bundle is None:
            return

        vm = build_markdown_preview(self._bundle, "concept_trace.md")
        if not vm.is_loaded:
            # Fallback: show concept_trace.mmd
            vm = build_markdown_preview(
                self._bundle, "concept_trace.mmd"
            )

        if vm.is_loaded:
            self._md_text.setPlainText(vm.content)

    def _update_diagnostics(self) -> None:
        self._diag_list.clear()
        if self._bundle is None:
            return
        for d in self._bundle.diagnostics:
            label = "[{}]".format(d.severity.upper())
            if d.artifact:
                label += " {}:".format(d.artifact)
            label += " {}".format(d.message)
            self._diag_list.addItem(label)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_gui(args: Any) -> int:  # pyright: ignore[reportExplicitAny]
    """Run the PySide6 GUI event loop."""
    app = QtWidgets.QApplication(sys.argv)

    artifact_dir = getattr(args, "artifact_dir", None)
    if artifact_dir is not None:
        artifact_dir = Path(artifact_dir)

    window = MainWindow(artifact_dir)
    window.show()
    return app.exec()
