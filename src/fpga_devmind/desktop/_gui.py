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
from fpga_devmind.desktop.agent_panel_models import (
    AgentPanelResponse,
    query_artifact_bundle,
)
from fpga_devmind.desktop.agent_plan_models import (
    AgentPlanPreview,
    build_agent_plan_preview,
)
from fpga_devmind.desktop.trace_view_models import (
    ConceptTraceViewModel,
    build_concept_trace_view_model,
)
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

        # Concept Trace tab (T010)
        self._trace_widget = QtWidgets.QWidget()
        self._trace_layout = QtWidgets.QVBoxLayout(self._trace_widget)
        self._trace_subtabs = QtWidgets.QTabWidget()

        # Nodes sub-tab
        self._trace_nodes_widget = QtWidgets.QWidget()
        self._trace_nodes_layout = QtWidgets.QVBoxLayout(self._trace_nodes_widget)
        self._trace_nodes_table = QtWidgets.QTableWidget()
        self._trace_nodes_table.setColumnCount(7)
        self._trace_nodes_table.setHorizontalHeaderLabels(
            ["Node ID", "Label", "Kind", "Stage", "Confidence", "Evidence", "Diagnostics"]
        )
        self._trace_nodes_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._trace_nodes_layout.addWidget(self._trace_nodes_table)
        self._trace_subtabs.addTab(self._trace_nodes_widget, "Nodes")

        # Edges sub-tab
        self._trace_edges_widget = QtWidgets.QWidget()
        self._trace_edges_layout = QtWidgets.QVBoxLayout(self._trace_edges_widget)
        self._trace_edges_table = QtWidgets.QTableWidget()
        self._trace_edges_table.setColumnCount(6)
        self._trace_edges_table.setHorizontalHeaderLabels(
            ["Edge ID", "From", "To", "Type", "Confidence", "Claims"]
        )
        self._trace_edges_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._trace_edges_layout.addWidget(self._trace_edges_table)
        self._trace_subtabs.addTab(self._trace_edges_widget, "Edges")

        # Claims sub-tab
        self._trace_claims_widget = QtWidgets.QWidget()
        self._trace_claims_layout = QtWidgets.QVBoxLayout(self._trace_claims_widget)
        self._trace_claims_table = QtWidgets.QTableWidget()
        self._trace_claims_table.setColumnCount(10)
        self._trace_claims_table.setHorizontalHeaderLabels(
            [
                "Claim ID",
                "Concept",
                "Confidence",
                "Bridge",
                "L5/L6 Ev.",
                "RTL Ev.",
                "Bridge Ev.",
                "Missing",
                "Diagnostics",
            ]
        )
        self._trace_claims_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._trace_claims_layout.addWidget(self._trace_claims_table)
        self._trace_subtabs.addTab(self._trace_claims_widget, "Claims")

        # Evidence sub-tab
        self._trace_evidence_widget = QtWidgets.QWidget()
        self._trace_evidence_layout = QtWidgets.QVBoxLayout(self._trace_evidence_widget)
        self._trace_evidence_table = QtWidgets.QTableWidget()
        self._trace_evidence_table.setColumnCount(6)
        self._trace_evidence_table.setHorizontalHeaderLabels(
            ["Evidence ID", "Source", "File", "Symbol", "Strength", "Claim Refs"]
        )
        self._trace_evidence_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._trace_evidence_layout.addWidget(self._trace_evidence_table)
        self._trace_subtabs.addTab(self._trace_evidence_widget, "Evidence")

        # Diagnostics sub-tab
        self._trace_diag_widget = QtWidgets.QWidget()
        self._trace_diag_layout = QtWidgets.QVBoxLayout(self._trace_diag_widget)
        self._trace_diag_table = QtWidgets.QTableWidget()
        self._trace_diag_table.setColumnCount(6)
        self._trace_diag_table.setHorizontalHeaderLabels(
            ["ID", "Severity", "Issue Type", "Target Claim", "Message", "Action"]
        )
        self._trace_diag_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._trace_diag_layout.addWidget(self._trace_diag_table)
        self._trace_subtabs.addTab(self._trace_diag_widget, "Diagnostics")

        self._trace_layout.addWidget(self._trace_subtabs)
        self._tabs.addTab(self._trace_widget, "Concept Trace")

        # Agent tab (T011)
        self._agent_widget = QtWidgets.QWidget()
        self._agent_layout = QtWidgets.QVBoxLayout(self._agent_widget)

        # Input row
        self._agent_input_row = QtWidgets.QHBoxLayout()
        self._agent_question = QtWidgets.QLineEdit()
        self._agent_question.setPlaceholderText(
            "Ask a question (e.g. summary, claims, evidence, diagnostics, unknown, nodes, edges, or a claim/evidence ID)"
        )
        self._agent_ask_btn = QtWidgets.QPushButton("Ask")
        self._agent_ask_btn.clicked.connect(self._on_agent_ask)
        self._agent_input_row.addWidget(self._agent_question, stretch=1)
        self._agent_input_row.addWidget(self._agent_ask_btn)
        self._agent_layout.addLayout(self._agent_input_row)

        # Answer output
        self._agent_answer = QtWidgets.QPlainTextEdit()
        self._agent_answer.setReadOnly(True)
        self._agent_layout.addWidget(self._agent_answer)

        # Plan Preview output (T012)
        self._agent_plan_preview = QtWidgets.QPlainTextEdit()
        self._agent_plan_preview.setReadOnly(True)
        self._agent_plan_preview.setPlaceholderText(
            "Load an artifact bundle first."
        )
        self._agent_layout.addWidget(self._agent_plan_preview)

        self._tabs.addTab(self._agent_widget, "Agent")

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
        self._update_concept_trace()

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
            self._diag_list.addItem("No bundle loaded.")
            return
        for d in self._bundle.diagnostics:
            label = "[{}]".format(d.severity.upper())
            if d.artifact:
                label += " {}:".format(d.artifact)
            label += " {}".format(d.message)
            self._diag_list.addItem(label)

    # --- Concept Trace (T010) ---

    def _update_concept_trace(self) -> None:
        """Refresh all Concept Trace sub-tables."""
        self._clear_trace_tables()
        if self._bundle is None:
            self._set_trace_error("No bundle loaded.")
            return

        vm = build_concept_trace_view_model(self._bundle)
        if not vm.is_loaded:
            self._set_trace_error(vm.load_error or "Unable to load trace view")
            return

        self._populate_nodes_table(vm)
        self._populate_edges_table(vm)
        self._populate_claims_table(vm)
        self._populate_evidence_table(vm)
        self._populate_diagnostics_table(vm)

    def _clear_trace_tables(self) -> None:
        for table in (
            self._trace_nodes_table,
            self._trace_edges_table,
            self._trace_claims_table,
            self._trace_evidence_table,
            self._trace_diag_table,
        ):
            table.setRowCount(0)

    def _set_trace_error(self, message: str) -> None:
        """Show a single-row error in the Nodes table."""
        self._trace_nodes_table.setRowCount(1)
        self._trace_nodes_table.setItem(
            0, 0, QtWidgets.QTableWidgetItem(message)
        )

    def _populate_nodes_table(self, vm: ConceptTraceViewModel) -> None:
        table = self._trace_nodes_table
        table.setRowCount(len(vm.nodes))
        for i, row in enumerate(vm.nodes):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.node_id))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.label))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.kind))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.stage_id))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.confidence))
            table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(row.evidence_count)))
            table.setItem(
                i, 6, QtWidgets.QTableWidgetItem("yes" if row.has_diagnostics else "no")
            )

    def _populate_edges_table(self, vm: ConceptTraceViewModel) -> None:
        table = self._trace_edges_table
        table.setRowCount(len(vm.edges))
        for i, row in enumerate(vm.edges):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.edge_id))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.from_label))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.to_label))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.edge_type))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.confidence))
            table.setItem(i, 5, QtWidgets.QTableWidgetItem(row.claim_refs))

    def _populate_claims_table(self, vm: ConceptTraceViewModel) -> None:
        table = self._trace_claims_table
        table.setRowCount(len(vm.claims))
        for i, row in enumerate(vm.claims):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.claim_id))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.concept_ref))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.confidence))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.bridge_kind))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(row.l5_l6_evidence_count)))
            table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(row.rtl_evidence_count)))
            table.setItem(
                i, 6, QtWidgets.QTableWidgetItem(str(row.bridge_evidence_count))
            )
            table.setItem(
                i, 7, QtWidgets.QTableWidgetItem(row.required_missing_evidence)
            )
            table.setItem(i, 8, QtWidgets.QTableWidgetItem(str(row.diagnostic_count)))

    def _populate_evidence_table(self, vm: ConceptTraceViewModel) -> None:
        table = self._trace_evidence_table
        table.setRowCount(len(vm.evidence))
        for i, row in enumerate(vm.evidence):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.evidence_id))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.source_type))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.file_path))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.symbol))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.evidence_strength))
            table.setItem(
                i, 5, QtWidgets.QTableWidgetItem(row.referenced_by_claims)
            )

    def _populate_diagnostics_table(self, vm: ConceptTraceViewModel) -> None:
        table = self._trace_diag_table
        table.setRowCount(len(vm.diagnostics))
        for i, row in enumerate(vm.diagnostics):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.diagnostic_id))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.severity))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.issue_type))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.target_claim_id))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.message))
            table.setItem(
                i, 5, QtWidgets.QTableWidgetItem(row.recommended_action)
            )


    def _on_agent_ask(self) -> None:
        """Handle Ask button click in the Agent tab."""
        question = self._agent_question.text().strip()
        if not question:
            self._agent_answer.setPlainText(
                "Please enter a question.\n"
                "Supported: summary, claims, evidence, diagnostics, "
                "unknown, nodes, edges, or a specific claim/evidence ID."
            )
            self._agent_plan_preview.setPlainText("")
            return
        if self._bundle is None:
            self._agent_answer.setPlainText(
                "No bundle loaded. Please load an artifact bundle first."
            )
            self._agent_plan_preview.setPlainText("")
            return

        vm = query_artifact_bundle(self._bundle, question)
        if not vm.is_loaded:
            self._agent_answer.setPlainText(
                vm.load_error or "Query failed."
            )
            self._agent_plan_preview.setPlainText("")
            return

        lines = [vm.answer_text]
        if vm.referenced_claim_ids:
            lines.append("")
            lines.append(
                "Referenced claims: {}".format(
                    ", ".join(vm.referenced_claim_ids)
                )
            )
        if vm.referenced_evidence_ids:
            lines.append("")
            lines.append(
                "Referenced evidence: {}".format(
                    ", ".join(vm.referenced_evidence_ids)
                )
            )
        if vm.referenced_diagnostic_ids:
            lines.append("")
            lines.append(
                "Referenced diagnostics: {}".format(
                    ", ".join(vm.referenced_diagnostic_ids)
                )
            )
        if vm.uncertainty_notes:
            lines.append("")
            lines.append("Uncertainty notes:")
            for note in vm.uncertainty_notes:
                lines.append("  - {}".format(note))

        self._agent_answer.setPlainText("\n".join(lines))

        # Build and display read-only plan preview (T012).
        plan = build_agent_plan_preview(self._bundle, question, vm)
        self._agent_plan_preview.setPlainText(
            self._format_plan_preview(plan)
        )

    def _format_plan_preview(self, plan: AgentPlanPreview) -> str:
        """Format a read-only plan preview into plain text."""
        if not plan.is_loaded:
            return plan.load_error or "Plan preview unavailable."

        lines: list[str] = []
        lines.append("## Intent: {}".format(plan.intent))
        lines.append("")

        if plan.steps:
            lines.append("### Steps")
            for step in plan.steps:
                lines.append("  [{}] {}".format(step.step_id, step.title))
                lines.append("      Rationale: {}".format(step.rationale))
                if step.read_artifacts:
                    lines.append(
                        "      Read artifacts: {}".format(
                            ", ".join(step.read_artifacts)
                        )
                    )
                if step.referenced_claim_ids:
                    lines.append(
                        "      Referenced claims: {}".format(
                            ", ".join(step.referenced_claim_ids)
                        )
                    )
                if step.referenced_evidence_ids:
                    lines.append(
                        "      Referenced evidence: {}".format(
                            ", ".join(step.referenced_evidence_ids)
                        )
                    )
                if step.referenced_diagnostic_ids:
                    lines.append(
                        "      Referenced diagnostics: {}".format(
                            ", ".join(step.referenced_diagnostic_ids)
                        )
                    )
                lines.append(
                    "      Action: {} | Executable now: {}".format(
                        step.allowed_action,
                        "yes" if step.is_executable_now else "no",
                    )
                )
                lines.append("")
        else:
            lines.append("No steps generated.")
            lines.append("")

        if plan.safety_notes:
            lines.append("### Safety Notes")
            for note in plan.safety_notes:
                lines.append("  - {}".format(note))
            lines.append("")

        if plan.unsupported_reason:
            lines.append(
                "Unsupported reason: {}".format(plan.unsupported_reason)
            )

        return "\n".join(lines)


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
