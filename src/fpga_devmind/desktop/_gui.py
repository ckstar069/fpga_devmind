"""PySide6 GUI for the Desktop Agent Shell (T019).

This module is imported only when PySide6 is available.  If PySide6 is
not installed, ``desktop_app.py`` prints a dependency message instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6 import QtWidgets  # pyright: ignore[reportMissingImports, reportUnknownVariableType]

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.agent_panel_models import (
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
from fpga_devmind.desktop.agent_trace_view_models import (
    build_agent_runtime_trace_view_model,
)
from fpga_devmind.desktop.view_models import (
    JsonTreeNode,
    build_bundle_summary,
    build_json_tree,
    build_markdown_preview,
)
from fpga_devmind.desktop.overview_models import (
    SuggestedQuestion,
    build_overview_view_model,
    format_concept_trace_summary,
)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QtWidgets.QMainWindow):
    """T019 Desktop Agent Shell — FPGA Understanding overview."""

    def __init__(self, artifact_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("fpga_devmind — FPGA Understanding Agent Shell")
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

        # === Tab 0: Overview (T019 — replaces Run Summary) ===
        self._overview_widget = QtWidgets.QWidget()
        self._overview_layout = QtWidgets.QVBoxLayout(self._overview_widget)
        self._overview_text = QtWidgets.QTextEdit()
        self._overview_text.setReadOnly(True)
        self._overview_layout.addWidget(self._overview_text)
        self._tabs.addTab(self._overview_widget, "Overview")

        # === Tab 1: Concept Understanding (T019 — renamed from Concept Trace) ===
        self._trace_widget = QtWidgets.QWidget()
        self._trace_layout = QtWidgets.QVBoxLayout(self._trace_widget)

        # Natural language summary (T019)
        self._trace_summary = QtWidgets.QTextEdit()
        self._trace_summary.setReadOnly(True)
        self._trace_summary.setMaximumHeight(200)
        self._trace_layout.addWidget(self._trace_summary)

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
        self._tabs.addTab(self._trace_widget, "Concept Understanding")

        # === Tab 2: Agent (T019 — primary interaction entry) ===
        self._agent_widget = QtWidgets.QWidget()
        self._agent_layout = QtWidgets.QVBoxLayout(self._agent_widget)

        # Suggested questions label (T019)
        self._agent_suggestions_label = QtWidgets.QLabel()
        self._agent_suggestions_label.setWordWrap(True)
        self._agent_suggestions_label.setStyleSheet("color: #666; font-size: 12px;")
        self._agent_layout.addWidget(self._agent_suggestions_label)

        # Input row
        self._agent_input_row = QtWidgets.QHBoxLayout()
        self._agent_question = QtWidgets.QLineEdit()
        self._agent_question.setPlaceholderText(
            "输入问题，例如：概况、映射、证据、诊断、不确定、节点、边，或 claim/evidence ID"
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
            "选择上方问题，或输入自己的问题后点击 Ask。"
        )
        self._agent_layout.addWidget(self._agent_plan_preview)

        self._tabs.addTab(self._agent_widget, "Agent")

        # === Tab 3: Markdown ===
        self._md_widget = QtWidgets.QWidget()
        self._md_layout = QtWidgets.QVBoxLayout(self._md_widget)
        self._md_text = QtWidgets.QPlainTextEdit()
        self._md_text.setReadOnly(True)
        self._md_layout.addWidget(self._md_text)
        self._tabs.addTab(self._md_widget, "Markdown")

        # === Tab 4: Diagnostics ===
        self._diag_widget = QtWidgets.QWidget()
        self._diag_layout = QtWidgets.QVBoxLayout(self._diag_widget)
        self._diag_list = QtWidgets.QListWidget()
        self._diag_layout.addWidget(self._diag_list)
        self._tabs.addTab(self._diag_widget, "Diagnostics")

        # === Tab 5: Developer (T019 — renamed from JSON Tree, demoted) ===
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
        self._tabs.addTab(self._json_tree_widget, "Developer")

        # === Tab 6: Agent Runtime (T017 — conditional visibility) ===
        self._art_widget = QtWidgets.QWidget()
        self._art_layout = QtWidgets.QVBoxLayout(self._art_widget)

        # Summary form
        self._art_summary_widget = QtWidgets.QWidget()
        self._art_summary_layout = QtWidgets.QFormLayout(
            self._art_summary_widget
        )
        self._art_layout.addWidget(self._art_summary_widget)

        # Steps table
        self._art_steps_table = QtWidgets.QTableWidget()
        self._art_steps_table.setColumnCount(6)
        self._art_steps_table.setHorizontalHeaderLabels(
            ["Section", "ID", "Title", "Status", "Summary", "References"]
        )
        self._art_steps_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._art_layout.addWidget(self._art_steps_table)

        # Diagnostics table
        self._art_diag_label = QtWidgets.QLabel("Runtime Diagnostics")
        self._art_layout.addWidget(self._art_diag_label)
        self._art_diag_table = QtWidgets.QTableWidget()
        self._art_diag_table.setColumnCount(2)
        self._art_diag_table.setHorizontalHeaderLabels(
            ["Severity", "Message"]
        )
        self._art_diag_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self._art_layout.addWidget(self._art_diag_table)

        self._tabs.addTab(self._art_widget, "Agent Runtime")

        # --- Internal state ---
        self._bundle = None
        self._current_suggested_questions: list[SuggestedQuestion] = []

        # Initial Agent Runtime tab: disabled until agent_runtime bundle loaded
        art_idx = self._tabs.indexOf(self._art_widget)
        self._tabs.setTabEnabled(art_idx, False)

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

        # Update all tabs
        self._update_overview()
        self._update_concept_trace()
        self._update_agent_suggestions()
        self._update_json_selector()
        self._update_markdown()
        self._update_diagnostics()
        self._update_agent_runtime()

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

    # --- Overview tab (T019) ---

    def _update_overview(self) -> None:
        """Refresh the Overview tab with human-oriented summary."""
        self._overview_text.clear()

        if self._bundle is None:
            self._overview_text.setHtml(
                "<h2>FPGA Understanding Agent Shell</h2>"
                "<p>请在上方输入 artifact 目录，或使用 Browse... 选择。</p>"
                "<p>支持 P1b、P1a、agent_runtime 三种 bundle 类型。</p>"
            )
            self._current_suggested_questions = []
            return

        vm = build_overview_view_model(self._bundle)
        self._current_suggested_questions = list(vm.suggested_questions)

        if not vm.is_loaded:
            self._overview_text.setHtml(
                "<h2>加载失败</h2>"
                "<p>{}</p>".format(
                    vm.load_error or "Unknown error"
                )
            )
            return

        # Build HTML overview
        parts: list[str] = []
        parts.append("<h2>FPGA Understanding — {}</h2>".format(
            vm.concept_name or vm.bundle_type
        ))
        parts.append("<p><b>Bundle:</b> {} | <b>Project:</b> {}</p>".format(
            vm.bundle_type, vm.project_path or "(unknown)"
        ))
        parts.append("<hr>")
        parts.append("<h3>当前理解</h3>")
        # Convert newlines to <br>
        understanding_html = vm.current_understanding.replace(
            "\n", "<br>"
        )
        parts.append("<p>{}</p>".format(understanding_html))

        # Evidence summaries
        if vm.l5_l6_evidence_summary.total > 0 or vm.rtl_evidence_summary.total > 0:
            parts.append("<h3>证据概览</h3>")
            parts.append("<table border='1' cellpadding='4'>")
            parts.append(
                "<tr><th>类型</th><th>强</th><th>中</th>"
                "<th>弱</th><th>未知</th><th>总计</th></tr>"
            )
            for label, ev in [
                ("L5/L6 证据", vm.l5_l6_evidence_summary),
                ("RTL 证据", vm.rtl_evidence_summary),
            ]:
                parts.append(
                    "<tr><td>{}</td><td>{}</td><td>{}</td>"
                    "<td>{}</td><td>{}</td><td>{}</td></tr>".format(
                        label, ev.strong, ev.medium, ev.weak,
                        ev.unknown, ev.total,
                    )
                )
            parts.append("</table>")

        # Mapping confidence
        if vm.mapping_confidence.total > 0:
            mc = vm.mapping_confidence
            parts.append("<h3>映射可信度</h3>")
            parts.append("<p>Supported: {} | Inferred: {} | "
                         "Unknown: {} | Total: {}</p>".format(
                mc.supported, mc.inferred, mc.unknown, mc.total,
            ))

        # Unknown / limitations
        if vm.unknown_limitations:
            parts.append("<h3>不确定与限制</h3>")
            parts.append("<ul>")
            for lim in vm.unknown_limitations:
                parts.append("<li>{}</li>".format(lim))
            parts.append("</ul>")

        self._overview_text.setHtml("\n".join(parts))

    # --- Concept Understanding tab (T019) ---

    def _update_concept_trace(self) -> None:
        """Refresh all Concept Understanding sub-tables + summary."""
        self._trace_summary.clear()
        self._clear_trace_tables()

        if self._bundle is None:
            self._trace_summary.setPlainText(
                "请先加载 artifact bundle。\n"
                "支持 P1b 和 agent_runtime 类型。"
            )
            return

        vm = build_concept_trace_view_model(self._bundle)
        if not vm.is_loaded:
            if self._bundle.bundle_type != "p1b":
                self._trace_summary.setPlainText(
                    "当前 bundle 类型为 '{}'，不包含概念 trace 数据。\n"
                    "请加载 P1b bundle 查看 L5/L6-to-RTL 映射。".format(
                        self._bundle.bundle_type
                    )
                )
            else:
                self._trace_summary.setPlainText(
                    vm.load_error or "无法加载概念 trace 数据。"
                )
            return

        # Natural language summary (T019)
        summary_text = format_concept_trace_summary(vm)
        self._trace_summary.setPlainText(summary_text)

        # Populate tables
        self._populate_nodes_table(vm)
        self._populate_edges_table(vm)
        self._populate_claims_table(vm)
        self._populate_evidence_table(vm)
        self._populate_diagnostics_table(vm)

    # --- Agent tab (T019) ---

    def _update_agent_suggestions(self) -> None:
        """Update suggested questions label in Agent tab."""
        if not self._current_suggested_questions:
            self._agent_suggestions_label.setText(
                "💡 加载 artifact bundle 后，建议问题将显示在此处。"
            )
            return

        parts: list[str] = []
        for i, q in enumerate(self._current_suggested_questions, 1):
            parts.append("{}. {}".format(i, q.text))
        self._agent_suggestions_label.setText(
            "💡 建议问题:\n" + "\n".join(parts)
        )

    # --- JSON Tree (now "Developer") ---

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

    # --- Markdown ---

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

    # --- Diagnostics ---

    def _update_diagnostics(self) -> None:
        self._diag_list.clear()
        if self._bundle is None:
            self._diag_list.addItem("No bundle loaded.")
            return
        if not self._bundle.diagnostics:
            self._diag_list.addItem("✓ 无诊断信息 — bundle 完整。")
            return
        for d in self._bundle.diagnostics:
            label = "[{}]".format(d.severity.upper())
            if d.artifact:
                label += " {}:".format(d.artifact)
            label += " {}".format(d.message)
            self._diag_list.addItem(label)

    # --- Concept Trace table helpers ---

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

    # --- Agent interaction ---

    def _on_agent_ask(self) -> None:
        """Handle Ask button click in the Agent tab."""
        question = self._agent_question.text().strip()
        if not question:
            self._agent_answer.setPlainText(
                "请输入问题。\n"
                "支持: 概况、映射、证据、诊断、不确定、节点、边，\n"
                "或具体的 claim/evidence ID。"
            )
            self._agent_plan_preview.setPlainText("")
            return
        if self._bundle is None:
            self._agent_answer.setPlainText(
                "请先加载 artifact bundle。"
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

    # --- Agent Runtime Trace (T017) ---

    def _update_agent_runtime(self) -> None:
        """Refresh the Agent Runtime Trace tab."""
        self._clear_art_tables()

        # Conditional visibility (T019)
        is_art = (
            self._bundle is not None
            and self._bundle.bundle_type == "agent_runtime"
        )
        art_idx = self._tabs.indexOf(self._art_widget)
        self._tabs.setTabEnabled(art_idx, is_art)

        if self._bundle is None:
            self._art_summary_layout.addRow(
                "Status", QtWidgets.QLabel("No bundle loaded.")
            )
            return

        if not is_art:
            self._art_summary_layout.addRow(
                "Status",
                QtWidgets.QLabel(
                    "当前 bundle 类型为 '{}'。Agent Runtime tab 需要 "
                    "agent_runtime bundle。".format(self._bundle.bundle_type)
                ),
            )
            return

        vm = build_agent_runtime_trace_view_model(self._bundle)
        if not vm.is_loaded:
            self._art_summary_layout.addRow(
                "Error",
                QtWidgets.QLabel(vm.load_error or "Unknown error"),
            )
            return

        # Summary form
        for row in vm.summary_rows:
            self._art_summary_layout.addRow(
                row.field, QtWidgets.QLabel(row.value)
            )

        # Steps table
        self._art_steps_table.setRowCount(len(vm.step_rows))
        for i, row in enumerate(vm.step_rows):
            self._art_steps_table.setItem(
                i, 0, QtWidgets.QTableWidgetItem(row.section)
            )
            self._art_steps_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(row.item_id)
            )
            self._art_steps_table.setItem(
                i, 2, QtWidgets.QTableWidgetItem(row.title)
            )
            self._art_steps_table.setItem(
                i, 3, QtWidgets.QTableWidgetItem(row.status)
            )
            self._art_steps_table.setItem(
                i, 4, QtWidgets.QTableWidgetItem(row.summary)
            )
            self._art_steps_table.setItem(
                i, 5, QtWidgets.QTableWidgetItem(row.references)
            )

        # Diagnostics table
        self._art_diag_table.setRowCount(len(vm.diagnostic_rows))
        for i, row in enumerate(vm.diagnostic_rows):
            self._art_diag_table.setItem(
                i, 0, QtWidgets.QTableWidgetItem(row.severity)
            )
            self._art_diag_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(row.message)
            )

        # Hide diagnostics label/table when empty.
        has_diags = len(vm.diagnostic_rows) > 0
        self._art_diag_label.setVisible(has_diags)
        self._art_diag_table.setVisible(has_diags)

    def _clear_art_tables(self) -> None:
        """Clear all Agent Runtime tab widgets."""
        while self._art_summary_layout.rowCount() > 0:
            self._art_summary_layout.removeRow(0)
        self._art_steps_table.setRowCount(0)
        self._art_diag_table.setRowCount(0)
        self._art_diag_label.setVisible(True)
        self._art_diag_table.setVisible(True)


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
