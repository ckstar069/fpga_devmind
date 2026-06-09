"""PySide6 GUI for the T020 AgentScope-style Desktop Product Shell.

Left navigation sidebar + main workspace with 12 pages.
Not a web app, not Electron.  PySide6 only.

This module is imported only when PySide6 is available.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from fpga_devmind.desktop.artifact_loader import load_bundle
from fpga_devmind.desktop.agent_panel_models import query_artifact_bundle
from fpga_devmind.desktop.agent_plan_models import (
    AgentPlanPreview,
    build_agent_plan_preview,
)
from fpga_devmind.desktop.concept_graph_view import (
    ConceptGraphScene,
    GraphFilterState,
    build_concept_graph_view_model,
    build_node_detail,
)
from fpga_devmind.desktop.trace_view_models import (
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
from fpga_devmind.desktop.page_view_models import (
    build_evidence_page_view_model,
    build_unknowns_page_view_model,
    build_overview_metrics,
    build_agent_runtime_page_state,
    build_plan_tools_page_state,
)


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

_NAV_BG = "#1e1e2e"
_NAV_TEXT = "#cdd6f4"
_NAV_GROUP = "#a6adc8"
_NAV_ACTIVE = "#313244"
_NAV_HOVER = "#252537"
_ACCENT = "#89b4fa"
_TOP_BG = "#f0f0f0"
_CONTENT_BG = "#f8f9fa"
_CARD_BG = "#ffffff"
_BORDER = "#e0e0e0"
_TEXT_DIM = "#666666"

_NAV_STYLE = """
QWidget {{
    background-color: {_NAV_BG};
    color: {_NAV_TEXT};
}}
QLabel {{
    color: {_NAV_GROUP};
    font-size: 11px;
    font-weight: bold;
    padding: 8px 12px 4px 12px;
}}
QPushButton {{
    background-color: transparent;
    color: {_NAV_TEXT};
    border: none;
    border-left: 3px solid transparent;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {_NAV_HOVER};
}}
QPushButton:active, QPushButton:checked {{
    background-color: {_NAV_ACTIVE};
    border-left: 3px solid {_ACCENT};
}}
""".format(**locals())

_TOP_BAR_STYLE = """
QWidget {{
    background-color: {_TOP_BG};
    border-bottom: 1px solid {_BORDER};
}}
QLabel {{
    color: #333333;
    font-size: 13px;
}}
QPushButton {{
    background-color: {_ACCENT};
    color: #1e1e2e;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: #74a0e8;
}}
QLineEdit {{
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    background-color: white;
}}
""".format(**locals())

_PAGE_STYLE = """
QWidget {{
    background-color: {_CONTENT_BG};
}}
QLabel {{
    color: #333333;
}}
QTextEdit, QPlainTextEdit {{
    background-color: {_CARD_BG};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 8px;
}}
QTableWidget {{
    background-color: {_CARD_BG};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    gridline-color: {_BORDER};
}}
QTableWidget::item {{
    padding: 4px;
}}
QHeaderView::section {{
    background-color: {_TOP_BG};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {_BORDER};
    font-weight: bold;
}}
QComboBox {{
    background-color: {_CARD_BG};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}
QListWidget {{
    background-color: {_CARD_BG};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 4px;
}}
""".format(**locals())


# ---------------------------------------------------------------------------
# Navigation button
# ---------------------------------------------------------------------------


class NavButton(QtWidgets.QPushButton):
    """A navigation button for the left sidebar."""

    def __init__(self, text: str, page_key: str) -> None:
        super().__init__(text)
        self.page_key = page_key
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QtWidgets.QMainWindow):
    """T020 AgentScope-style FPGA DevMind product shell."""

    def __init__(self, artifact_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("FPGA DevMind")
        self.resize(1400, 900)

        self._bundle: Any = None  # pyright: ignore[reportExplicitAny]
        self._current_suggested_questions: list[SuggestedQuestion] = []
        self._nav_buttons: dict[str, NavButton] = {}
        self._page_keys: list[str] = []
        self._last_plan_preview_text: str = ""

        # Top bar widgets (initialized in _build_top_bar)
        self._top_project_label = QtWidgets.QLabel()
        self._top_concept_label = QtWidgets.QLabel()
        self._top_status_label = QtWidgets.QLabel()
        self._dir_input = QtWidgets.QLineEdit()

        # Overview page widgets
        self._ov_project_card: QtWidgets.QWidget | None = None
        self._ov_concept_card: QtWidgets.QWidget | None = None
        self._ov_metric_labels: dict[str, QtWidgets.QLabel] = {}
        self._ov_summary = QtWidgets.QTextEdit()
        self._ov_suggestions = QtWidgets.QWidget()
        self._ov_suggestions_layout = QtWidgets.QVBoxLayout()

        # Concept trace page widgets
        self._ct_graph_view = QtWidgets.QGraphicsView()
        self._ct_graph_scene: Any = None  # ConceptGraphScene; pyright: ignore[reportExplicitAny]
        self._ct_graph_info = QtWidgets.QLabel()
        self._ct_graph_detail = QtWidgets.QTextEdit()
        self._ct_filter_modules = QtWidgets.QCheckBox()
        self._ct_filter_signals = QtWidgets.QCheckBox()
        self._ct_filter_always = QtWidgets.QCheckBox()
        self._ct_filter_weak = QtWidgets.QCheckBox()
        self._ct_summary = QtWidgets.QTextEdit()
        self._ct_nodes_table = QtWidgets.QTableWidget()
        self._ct_edges_table = QtWidgets.QTableWidget()
        self._ct_claims_table = QtWidgets.QTableWidget()
        self._ct_evidence_table = QtWidgets.QTableWidget()
        self._ct_diag_table = QtWidgets.QTableWidget()

        # Evidence page widgets
        self._evidence_stack = QtWidgets.QStackedWidget()
        self._evidence_header = QtWidgets.QTextEdit()
        self._evidence_groups_layout = QtWidgets.QVBoxLayout()
        self._evidence_detail = QtWidgets.QTextEdit()
        self._evidence_empty = QtWidgets.QLabel()

        # Unknowns page widgets
        self._unknowns_stack = QtWidgets.QStackedWidget()
        self._un_limitations_label = QtWidgets.QLabel()
        self._un_limitations = QtWidgets.QListWidget()
        self._un_notes_label = QtWidgets.QLabel()
        self._un_notes = QtWidgets.QListWidget()
        self._un_diagnostics_label = QtWidgets.QLabel()
        self._un_diagnostics = QtWidgets.QTableWidget()
        self._un_why_label = QtWidgets.QLabel()
        self._un_why = QtWidgets.QTextEdit()
        self._unknowns_empty = QtWidgets.QLabel()

        # Agent QA page widgets
        self._agent_question = QtWidgets.QLineEdit()
        self._agent_answer = QtWidgets.QTextEdit()
        self._agent_evidence = QtWidgets.QTextEdit()
        self._agent_limitations = QtWidgets.QTextEdit()
        self._agent_plan = QtWidgets.QTextEdit()
        self._agent_suggestions = QtWidgets.QWidget()
        self._agent_suggestions_layout = QtWidgets.QHBoxLayout()

        # Agent runtime page widgets
        self._art_stack = QtWidgets.QStackedWidget()
        self._art_summary = QtWidgets.QFormLayout()
        self._art_steps = QtWidgets.QTableWidget()
        self._art_diag = QtWidgets.QTableWidget()
        self._art_diag_label = QtWidgets.QLabel()
        self._art_info = QtWidgets.QTextEdit()

        # Raw data page widgets
        self._raw_selector = QtWidgets.QComboBox()
        self._raw_tree = QtWidgets.QTreeWidget()

        # Markdown page widgets
        self._md_display = QtWidgets.QPlainTextEdit()

        # Diagnostics page widgets
        self._diag_display = QtWidgets.QListWidget()

        # Project settings page widgets
        self._settings_path = QtWidgets.QLineEdit()
        self._settings_info = QtWidgets.QFormLayout()

        # Plan tools page widgets
        self._plan_display = QtWidgets.QTextEdit()

        # Central widget with horizontal layout: nav + content
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left navigation
        self._nav_widget = self._build_navigation()
        self._nav_widget.setFixedWidth(220)
        main_layout.addWidget(self._nav_widget)

        # Right area
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top bar
        self._top_bar = self._build_top_bar()
        right_layout.addWidget(self._top_bar)

        # Content stack
        self._content_stack = QtWidgets.QStackedWidget()
        right_layout.addWidget(self._content_stack, stretch=1)

        main_layout.addWidget(right, stretch=1)

        # Build all pages
        self._build_all_pages()

        # Navigate to overview
        self._navigate_to("overview")

        # Load initial bundle if provided
        if artifact_dir is not None:
            self._dir_input.setText(str(artifact_dir))
            self._on_load()

    # --- Navigation --------------------------------------------------------

    def _build_navigation(self) -> QtWidgets.QWidget:
        nav = QtWidgets.QWidget()
        nav.setStyleSheet(_NAV_STYLE)
        layout = QtWidgets.QVBoxLayout(nav)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(4)

        # Title
        title = QtWidgets.QLabel("FPGA DevMind")
        title.setStyleSheet(
            "color: {}; font-size: 16px; font-weight: bold; padding: 8px 16px;".format(
                _ACCENT
            )
        )
        layout.addWidget(title)

        # Subtitle
        subtitle = QtWidgets.QLabel("Understanding Agent Shell")
        subtitle.setStyleSheet(
            "color: {}; font-size: 11px; padding: 0 16px 8px 16px;".format(
                _NAV_GROUP
            )
        )
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Nav groups
        groups = [
            (
                "项目理解",
                [
                    ("概览", "overview"),
                    ("概念追踪", "concept_trace"),
                    ("证据", "evidence"),
                    ("不确定项", "unknowns"),
                ],
            ),
            (
                "Agent",
                [
                    ("Agent 问答", "agent_qa"),
                    ("Agent Runtime", "agent_runtime"),
                    ("计划与工具", "plan_tools"),
                ],
            ),
            (
                "开发者",
                [
                    ("Raw Data", "raw_data"),
                    ("Markdown", "markdown"),
                    ("Diagnostics", "diagnostics"),
                ],
            ),
            (
                "设置",
                [
                    ("项目设置", "project_settings"),
                    ("通用设置", "general_settings"),
                ],
            ),
        ]

        for group_name, items in groups:
            group_label = QtWidgets.QLabel(group_name)
            layout.addWidget(group_label)
            for text, key in items:
                btn = NavButton(text, key)
                btn.clicked.connect(
                    lambda _checked=False, k=key: self._navigate_to(k)
                )
                self._nav_buttons[key] = btn
                layout.addWidget(btn)
            layout.addSpacing(4)

        layout.addStretch(1)
        return nav

    def _navigate_to(self, page_key: str) -> None:
        """Switch to the given page and highlight its nav button."""
        if page_key not in self._page_keys:
            return
        idx = self._page_keys.index(page_key)
        self._content_stack.setCurrentIndex(idx)
        for key, btn in self._nav_buttons.items():
            btn.setChecked(key == page_key)

    # --- Top bar -----------------------------------------------------------

    def _build_top_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        bar.setStyleSheet(_TOP_BAR_STYLE)
        bar.setFixedHeight(56)
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)

        # Left: project info
        self._top_project_label = QtWidgets.QLabel("未加载项目")
        self._top_project_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._top_project_label)

        self._top_concept_label = QtWidgets.QLabel("")
        self._top_concept_label.setStyleSheet("color: {}; font-size: 12px;".format(_TEXT_DIM))
        layout.addWidget(self._top_concept_label)

        self._top_status_label = QtWidgets.QLabel("")
        self._top_status_label.setStyleSheet("color: {}; font-size: 12px;".format(_TEXT_DIM))
        layout.addWidget(self._top_status_label)

        layout.addStretch(1)

        # Right: Load artifact
        self._dir_input = QtWidgets.QLineEdit()
        self._dir_input.setPlaceholderText("Artifact directory...")
        self._dir_input.setFixedWidth(300)
        layout.addWidget(self._dir_input)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(browse_btn)

        load_btn = QtWidgets.QPushButton("Load")
        load_btn.clicked.connect(self._on_load)
        layout.addWidget(load_btn)

        return bar

    def _update_top_bar(self) -> None:
        if self._bundle is None or not self._bundle.is_complete:
            self._top_project_label.setText("未加载项目")
            self._top_concept_label.setText("")
            self._top_status_label.setText("")
            return

        summary = build_bundle_summary(self._bundle)
        meta = self._bundle.artifacts.get("run_metadata.json")
        concept = ""
        if meta and isinstance(meta.data, dict):
            concept = meta.data.get("concept", "")

        self._top_project_label.setText(
            self._bundle.bundle_type.upper()
        )
        if concept:
            self._top_concept_label.setText("| Concept: {}".format(concept))
        else:
            self._top_concept_label.setText("")

        status_text = "Complete" if summary.is_complete else "Incomplete"
        if summary.error_count > 0:
            status_text += " | {} errors".format(summary.error_count)
        self._top_status_label.setText("| {}".format(status_text))

        # Update dir input to show current path
        path_str = str(self._bundle.directory)
        if len(path_str) > 45:
            path_str = "..." + path_str[-42:]
        self._dir_input.setText(path_str)

    # --- Pages --------------------------------------------------------------

    def _build_all_pages(self) -> None:
        """Build all 12 pages and add them to the content stack."""
        pages = [
            ("overview", self._build_overview_page()),
            ("concept_trace", self._build_concept_trace_page()),
            ("evidence", self._build_evidence_page()),
            ("unknowns", self._build_unknowns_page()),
            ("agent_qa", self._build_agent_qa_page()),
            ("agent_runtime", self._build_agent_runtime_page()),
            ("plan_tools", self._build_plan_tools_page()),
            ("raw_data", self._build_raw_data_page()),
            ("markdown", self._build_markdown_page()),
            ("diagnostics", self._build_diagnostics_page()),
            ("project_settings", self._build_project_settings_page()),
            ("general_settings", self._build_general_settings_page()),
        ]
        for key, widget in pages:
            self._page_keys.append(key)
            self._content_stack.addWidget(widget)

    def _make_page_widget(self, title: str) -> QtWidgets.QWidget:
        """Create a standard page widget with title and scroll area."""
        page = QtWidgets.QWidget()
        page.setStyleSheet(_PAGE_STYLE)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #1e1e2e; margin-bottom: 8px;"
        )
        layout.addWidget(title_label)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        layout.addWidget(scroll, stretch=1)

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        scroll.setWidget(content)

        # Store content widget for later access
        setattr(page, "_content", content)
        setattr(page, "_content_layout", content_layout)

        return page

    # ========================================================================
    # Page 0: Overview
    # ========================================================================

    def _build_overview_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("概览")
        layout = getattr(page, "_content_layout")

        # Hero section
        hero = QtWidgets.QLabel(
            "<h1 style='margin:0; color:#1e1e2e;'>FPGA DevMind</h1>"
            "<p style='margin:4px 0 0 0; color:#666; font-size:14px;'>"
            "FPGA Understanding Agent Shell</p>"
        )
        layout.addWidget(hero)

        # Info cards row
        cards_row = QtWidgets.QHBoxLayout()
        cards_row.setSpacing(16)

        # Project card
        self._ov_project_card = self._make_card("当前项目")
        cards_row.addWidget(self._ov_project_card, stretch=1)

        # Concept card
        self._ov_concept_card = self._make_card("当前概念")
        cards_row.addWidget(self._ov_concept_card, stretch=1)

        layout.addLayout(cards_row)

        # Metrics row
        metrics_row = QtWidgets.QHBoxLayout()
        metrics_row.setSpacing(12)
        self._ov_metric_labels: dict[str, QtWidgets.QLabel] = {}
        metric_info = [
            ("Mapping Claims", "L5/L6 与 RTL 的映射声明"),
            ("Evidence Items", "支持理解的源码/RTL 证据"),
            ("RTL Objects", "相关 RTL module/signal/always/assign"),
            ("Unknowns", "不确定或缺失证据项"),
        ]
        for label, desc in metric_info:
            card = self._make_metric_card(label, "0", desc)
            metrics_row.addWidget(card, stretch=1)
            self._ov_metric_labels[label] = getattr(card, "_value_label")
        layout.addLayout(metrics_row)

        # Understanding summary
        summary_label = QtWidgets.QLabel("当前理解")
        summary_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(summary_label)

        self._ov_summary = QtWidgets.QTextEdit()
        self._ov_summary.setReadOnly(True)
        self._ov_summary.setMaximumHeight(160)
        layout.addWidget(self._ov_summary)

        # Suggested questions
        sq_label = QtWidgets.QLabel("建议问题")
        sq_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(sq_label)

        self._ov_suggestions = QtWidgets.QWidget()
        self._ov_suggestions_layout = QtWidgets.QVBoxLayout(self._ov_suggestions)
        self._ov_suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self._ov_suggestions_layout.setSpacing(6)
        layout.addWidget(self._ov_suggestions)

        # Next steps
        next_label = QtWidgets.QLabel("下一步")
        next_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(next_label)

        next_row = QtWidgets.QHBoxLayout()
        next_row.setSpacing(8)
        for text, key in [
            ("查看概念追踪", "concept_trace"),
            ("询问 Agent", "agent_qa"),
            ("查看证据", "evidence"),
        ]:
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(lambda _c=False, k=key: self._navigate_to(k))
            btn.setStyleSheet(
                "background-color: {}; color: white; border: none; "
                "border-radius: 4px; padding: 8px 16px; font-size: 13px;".format(
                    _ACCENT
                )
            )
            next_row.addWidget(btn)
        next_row.addStretch(1)
        layout.addLayout(next_row)

        layout.addStretch(1)
        return page

    def _make_card(self, title: str) -> QtWidgets.QWidget:
        card = QtWidgets.QWidget()
        card.setStyleSheet(
            "background-color: white; border: 1px solid {}; border-radius: 8px; padding: 12px;".format(
                _BORDER
            )
        )
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        t = QtWidgets.QLabel(title)
        t.setStyleSheet("font-size: 12px; color: {}; font-weight: bold;".format(_TEXT_DIM))
        layout.addWidget(t)
        v = QtWidgets.QLabel("—")
        v.setStyleSheet("font-size: 16px; color: #1e1e2e; margin-top: 4px;")
        layout.addWidget(v)
        setattr(card, "_value", v)
        return card

    def _make_metric_card(self, label: str, value: str, description: str = "") -> QtWidgets.QWidget:
        card = QtWidgets.QWidget()
        card.setStyleSheet(
            "background-color: white; border: 1px solid {}; border-radius: 8px; padding: 12px;".format(
                _BORDER
            )
        )
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        v = QtWidgets.QLabel(value)
        v.setStyleSheet("font-size: 24px; font-weight: bold; color: {};".format(_ACCENT))
        layout.addWidget(v)
        l = QtWidgets.QLabel(label)
        l.setStyleSheet("font-size: 12px; font-weight: bold; color: #333; margin-top: 4px;")
        layout.addWidget(l)
        if description:
            d = QtWidgets.QLabel(description)
            d.setStyleSheet("font-size: 10px; color: {}; margin-top: 2px;".format(_TEXT_DIM))
            layout.addWidget(d)
        setattr(card, "_value_label", v)
        return card

    def _update_overview(self) -> None:
        if self._bundle is None:
            if self._ov_project_card is not None:
                getattr(self._ov_project_card, "_value").setText("—")
            if self._ov_concept_card is not None:
                getattr(self._ov_concept_card, "_value").setText("—")
            self._ov_summary.setPlainText(
                "请在上方加载 artifact bundle 以开始。\n"
                "支持 P1b、P1a、agent_runtime 三种 bundle 类型。"
            )
            for label in self._ov_metric_labels:
                self._ov_metric_labels[label].setText("0")
            self._clear_suggestions()
            return

        vm = build_overview_view_model(self._bundle)
        self._current_suggested_questions = list(vm.suggested_questions)

        metrics = build_overview_metrics(self._bundle)

        if not vm.is_loaded:
            if self._ov_project_card is not None:
                getattr(self._ov_project_card, "_value").setText(vm.bundle_type or "—")
            if self._ov_concept_card is not None:
                getattr(self._ov_concept_card, "_value").setText("加载失败")
            self._ov_summary.setPlainText(vm.load_error or "加载失败")
            for label in self._ov_metric_labels:
                self._ov_metric_labels[label].setText("0")
            self._clear_suggestions()
            return

        # Cards
        project_text = vm.project_path or "—"
        if len(project_text) > 40:
            project_text = "..." + project_text[-37:]
        if self._ov_project_card is not None:
            getattr(self._ov_project_card, "_value").setText(project_text)
        if self._ov_concept_card is not None:
            getattr(self._ov_concept_card, "_value").setText(vm.concept_name or "—")

        # Metrics
        self._ov_metric_labels["Mapping Claims"].setText(str(metrics.mapping_claims))
        self._ov_metric_labels["Evidence Items"].setText(str(metrics.evidence_items))
        self._ov_metric_labels["RTL Objects"].setText(str(metrics.rtl_objects))
        self._ov_metric_labels["Unknowns"].setText(str(metrics.unknowns))

        # Summary
        self._ov_summary.setPlainText(vm.current_understanding)

        # Suggestions
        self._update_suggestions()

    def _clear_suggestions(self) -> None:
        while self._ov_suggestions_layout.count():
            item = self._ov_suggestions_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        empty = QtWidgets.QLabel("加载 bundle 后显示建议问题")
        empty.setStyleSheet("color: {}; font-size: 13px;".format(_TEXT_DIM))
        self._ov_suggestions_layout.addWidget(empty)

    def _update_suggestions(self) -> None:
        while self._ov_suggestions_layout.count():
            item = self._ov_suggestions_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        for q in self._current_suggested_questions:
            btn = QtWidgets.QPushButton(q.text)
            btn.setStyleSheet(
                "text-align: left; background: transparent; border: none; "
                "color: {}; font-size: 13px; padding: 4px 0;".format(_ACCENT)
            )
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, t=q.text: self._go_to_agent_with_question(t))
            self._ov_suggestions_layout.addWidget(btn)

    def _go_to_agent_with_question(self, question: str) -> None:
        self._navigate_to("agent_qa")
        self._agent_question.setText(question)
        self._on_agent_ask()

    # ========================================================================
    # Page 1: Concept Trace
    # ========================================================================

    def _build_concept_trace_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("概念追踪")
        layout = getattr(page, "_content_layout")

        # Concept Graph (graph first — T022/T023)
        graph_label = QtWidgets.QLabel("概念图")
        graph_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(graph_label)

        # Filter bar
        filter_bar = QtWidgets.QHBoxLayout()
        self._ct_filter_modules = QtWidgets.QCheckBox("模块")
        self._ct_filter_modules.setChecked(True)
        self._ct_filter_modules.stateChanged.connect(self._on_graph_filter_changed)
        filter_bar.addWidget(self._ct_filter_modules)
        self._ct_filter_signals = QtWidgets.QCheckBox("信号")
        self._ct_filter_signals.setChecked(True)
        self._ct_filter_signals.stateChanged.connect(self._on_graph_filter_changed)
        filter_bar.addWidget(self._ct_filter_signals)
        self._ct_filter_always = QtWidgets.QCheckBox("always/assign")
        self._ct_filter_always.setChecked(True)
        self._ct_filter_always.stateChanged.connect(self._on_graph_filter_changed)
        filter_bar.addWidget(self._ct_filter_always)
        self._ct_filter_weak = QtWidgets.QCheckBox("weak 证据")
        self._ct_filter_weak.setChecked(True)
        self._ct_filter_weak.stateChanged.connect(self._on_graph_filter_changed)
        filter_bar.addWidget(self._ct_filter_weak)
        filter_bar.addStretch(1)
        layout.addLayout(filter_bar)

        # Graph + detail panel
        graph_row = QtWidgets.QHBoxLayout()
        self._ct_graph_view = QtWidgets.QGraphicsView()
        self._ct_graph_view.setMinimumHeight(280)
        self._ct_graph_view.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.SmoothPixmapTransform
        )
        self._ct_graph_scene = ConceptGraphScene()
        self._ct_graph_scene.node_clicked.connect(self._on_graph_node_clicked)
        self._ct_graph_view.setScene(self._ct_graph_scene)
        graph_row.addWidget(self._ct_graph_view, stretch=2)

        self._ct_graph_detail = QtWidgets.QTextEdit()
        self._ct_graph_detail.setReadOnly(True)
        self._ct_graph_detail.setMaximumWidth(280)
        self._ct_graph_detail.setPlaceholderText("点击图节点查看详情")
        graph_row.addWidget(self._ct_graph_detail, stretch=1)
        layout.addLayout(graph_row)

        self._ct_graph_info = QtWidgets.QLabel("")
        self._ct_graph_info.setStyleSheet(
            "color: {}; font-size: 12px; padding: 4px 0px;".format(_TEXT_DIM)
        )
        self._ct_graph_info.setWordWrap(True)
        layout.addWidget(self._ct_graph_info)

        # Three-section summary
        summary_label = QtWidgets.QLabel("理解摘要")
        summary_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(summary_label)

        self._ct_summary = QtWidgets.QTextEdit()
        self._ct_summary.setReadOnly(True)
        self._ct_summary.setMaximumHeight(200)
        layout.addWidget(self._ct_summary)

        # Sub-tabs for tables
        sub_tabs = QtWidgets.QTabWidget()
        layout.addWidget(sub_tabs, stretch=1)

        # Nodes
        self._ct_nodes_table = QtWidgets.QTableWidget()
        self._ct_nodes_table.setColumnCount(7)
        self._ct_nodes_table.setHorizontalHeaderLabels(
            ["Node ID", "Label", "Kind", "Stage", "Confidence", "Evidence", "Diagnostics"]
        )
        sub_tabs.addTab(self._ct_nodes_table, "Nodes")

        # Edges
        self._ct_edges_table = QtWidgets.QTableWidget()
        self._ct_edges_table.setColumnCount(6)
        self._ct_edges_table.setHorizontalHeaderLabels(
            ["Edge ID", "From", "To", "Type", "Confidence", "Claims"]
        )
        sub_tabs.addTab(self._ct_edges_table, "Edges")

        # Claims
        self._ct_claims_table = QtWidgets.QTableWidget()
        self._ct_claims_table.setColumnCount(9)
        self._ct_claims_table.setHorizontalHeaderLabels(
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
        sub_tabs.addTab(self._ct_claims_table, "Claims")

        # Evidence
        self._ct_evidence_table = QtWidgets.QTableWidget()
        self._ct_evidence_table.setColumnCount(6)
        self._ct_evidence_table.setHorizontalHeaderLabels(
            ["Evidence ID", "Source", "File", "Symbol", "Strength", "Claim Refs"]
        )
        sub_tabs.addTab(self._ct_evidence_table, "Evidence")

        # Diagnostics
        self._ct_diag_table = QtWidgets.QTableWidget()
        self._ct_diag_table.setColumnCount(6)
        self._ct_diag_table.setHorizontalHeaderLabels(
            ["ID", "Severity", "Issue Type", "Target Claim", "Message", "Action"]
        )
        sub_tabs.addTab(self._ct_diag_table, "Diagnostics")

        return page

    def _on_graph_filter_changed(self) -> None:
        """Re-render graph when filter checkboxes change."""
        if self._bundle is None:
            return
        vm = build_concept_graph_view_model(self._bundle)
        if not vm.is_loaded:
            return
        vm.filter_state = GraphFilterState(
            show_modules=self._ct_filter_modules.isChecked(),
            show_signals=self._ct_filter_signals.isChecked(),
            show_always_assign=self._ct_filter_always.isChecked(),
            show_weak_evidence=self._ct_filter_weak.isChecked(),
        )
        self._ct_graph_scene.set_view_model(vm)

    def _on_graph_node_clicked(self, node: Any) -> None:
        """Handle click on a graph node — show full detail panel."""
        lines = ["【选中对象详情】", ""]
        lines.append("Node ID: {}".format(node.node_id))
        lines.append("Label: {}".format(node.label))
        lines.append("Kind: {}".format(node.kind))
        if node.stage:
            lines.append("Stage: {}".format(node.stage))
        if node.confidence:
            lines.append("Confidence: {}".format(node.confidence))
        if node.evidence_count:
            lines.append("Evidence: {} 条".format(node.evidence_count))
        if node.has_diagnostics:
            lines.append("Diagnostics: 有")

        # Try to enrich from graph data.
        from fpga_devmind.desktop.artifact_loader import get_graph
        if self._bundle is not None:
            graph = get_graph(self._bundle)
            detail = build_node_detail(node.node_id, graph)
            if detail is not None:
                if detail.evidence_ids:
                    lines.append("\n关联证据:")
                    for eid in detail.evidence_ids[:10]:
                        lines.append("  • {}".format(eid))
                    if len(detail.evidence_ids) > 10:
                        lines.append("  ... 以及 {} 条".format(len(detail.evidence_ids) - 10))
                if detail.claim_ids:
                    lines.append("\n关联声明:")
                    for cid in detail.claim_ids:
                        lines.append("  • {}".format(cid))

        self._ct_graph_detail.setPlainText("\n".join(lines))

        # Also update info line.
        info = "节点: {} | 类型: {} | 可信度: {}".format(
            node.label, node.kind, node.confidence or "—"
        )
        if node.evidence_count:
            info += " | 证据: {} 条".format(node.evidence_count)
        self._ct_graph_info.setText(info)

    def _update_concept_trace(self) -> None:
        self._ct_summary.clear()
        self._ct_graph_info.clear()
        self._ct_graph_detail.setPlainText("点击图节点查看详情")
        for table in [
            self._ct_nodes_table,
            self._ct_edges_table,
            self._ct_claims_table,
            self._ct_evidence_table,
            self._ct_diag_table,
        ]:
            table.setRowCount(0)

        if self._bundle is None:
            self._ct_summary.setPlainText(
                "请先加载 P1b concept trace bundle。\n"
                "使用顶部 Load 按钮或项目设置页面选择 artifact 目录。"
            )
            self._ct_graph_scene.set_view_model(
                build_concept_graph_view_model(load_bundle(Path("/nonexistent")))
            )
            return

        vm = build_concept_trace_view_model(self._bundle)
        if not vm.is_loaded:
            if self._bundle.bundle_type != "p1b":
                self._ct_summary.setPlainText(
                    "当前 bundle 类型为 '{}'，不包含概念 trace 数据。\n"
                    "请加载 P1b bundle 查看 L5/L6-to-RTL 映射。".format(
                        self._bundle.bundle_type
                    )
                )
            else:
                self._ct_summary.setPlainText(
                    vm.load_error or "无法加载概念 trace 数据。"
                )
            self._ct_graph_scene.set_view_model(
                build_concept_graph_view_model(self._bundle)
            )
            return

        self._ct_summary.setPlainText(format_concept_trace_summary(vm))
        gvm = build_concept_graph_view_model(self._bundle)
        if gvm.is_loaded:
            gvm.filter_state = GraphFilterState(
                show_modules=self._ct_filter_modules.isChecked(),
                show_signals=self._ct_filter_signals.isChecked(),
                show_always_assign=self._ct_filter_always.isChecked(),
                show_weak_evidence=self._ct_filter_weak.isChecked(),
            )
        self._ct_graph_scene.set_view_model(gvm)

        # Populate tables
        self._ct_nodes_table.setRowCount(len(vm.nodes))
        for i, row in enumerate(vm.nodes):
            self._ct_nodes_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.node_id))
            self._ct_nodes_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.label))
            self._ct_nodes_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.kind))
            self._ct_nodes_table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.stage_id))
            self._ct_nodes_table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.confidence))
            self._ct_nodes_table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(row.evidence_count)))
            self._ct_nodes_table.setItem(
                i, 6, QtWidgets.QTableWidgetItem("yes" if row.has_diagnostics else "no")
            )

        self._ct_edges_table.setRowCount(len(vm.edges))
        for i, row in enumerate(vm.edges):
            self._ct_edges_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.edge_id))
            self._ct_edges_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.from_label))
            self._ct_edges_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.to_label))
            self._ct_edges_table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.edge_type))
            self._ct_edges_table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.confidence))
            self._ct_edges_table.setItem(i, 5, QtWidgets.QTableWidgetItem(row.claim_refs))

        self._ct_claims_table.setRowCount(len(vm.claims))
        for i, row in enumerate(vm.claims):
            self._ct_claims_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.claim_id))
            self._ct_claims_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.concept_ref))
            self._ct_claims_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.confidence))
            self._ct_claims_table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.bridge_kind))
            self._ct_claims_table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(row.l5_l6_evidence_count)))
            self._ct_claims_table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(row.rtl_evidence_count)))
            self._ct_claims_table.setItem(i, 6, QtWidgets.QTableWidgetItem(str(row.bridge_evidence_count)))
            self._ct_claims_table.setItem(i, 7, QtWidgets.QTableWidgetItem(row.required_missing_evidence))
            self._ct_claims_table.setItem(i, 8, QtWidgets.QTableWidgetItem(str(row.diagnostic_count)))

        self._ct_evidence_table.setRowCount(len(vm.evidence))
        for i, row in enumerate(vm.evidence):
            self._ct_evidence_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.evidence_id))
            self._ct_evidence_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.source_type))
            self._ct_evidence_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.file_path))
            self._ct_evidence_table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.symbol))
            self._ct_evidence_table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.evidence_strength))
            self._ct_evidence_table.setItem(i, 5, QtWidgets.QTableWidgetItem(row.referenced_by_claims))

        self._ct_diag_table.setRowCount(len(vm.diagnostics))
        for i, row in enumerate(vm.diagnostics):
            self._ct_diag_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.diagnostic_id))
            self._ct_diag_table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.severity))
            self._ct_diag_table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.issue_type))
            self._ct_diag_table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.target_claim_id))
            self._ct_diag_table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.message))
            self._ct_diag_table.setItem(i, 5, QtWidgets.QTableWidgetItem(row.recommended_action))

    # ========================================================================
    # Page 2: Evidence
    # ========================================================================

    def _build_evidence_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("证据")
        layout = getattr(page, "_content_layout")

        self._evidence_stack = QtWidgets.QStackedWidget()
        layout.addWidget(self._evidence_stack, stretch=1)

        # Page 0: loaded content
        loaded_widget = QtWidgets.QWidget()
        loaded_layout = QtWidgets.QVBoxLayout(loaded_widget)
        loaded_layout.setContentsMargins(0, 0, 0, 0)

        # Evidence strength explanation header
        self._evidence_header = QtWidgets.QTextEdit()
        self._evidence_header.setReadOnly(True)
        self._evidence_header.setMaximumHeight(120)
        self._evidence_header.setPlainText(
            "证据强度说明：\n"
            "  • strong — 高置信度匹配，可直接支撑 mapping claim\n"
            "  • medium — 中等置信度，需要额外验证或上下文确认\n"
            "  • weak — 低置信度，仅供参考，不建议单独作为映射依据\n"
            "  • unknown — 未评估或无法判断强度\n"
            "\n证据越多、越强，mapping claim 的可信度就越高。"
        )
        loaded_layout.addWidget(self._evidence_header)

        # Dynamic groups container (separate from header)
        groups_widget = QtWidgets.QWidget()
        self._evidence_groups_layout = QtWidgets.QVBoxLayout(groups_widget)
        self._evidence_groups_layout.setContentsMargins(0, 0, 0, 0)
        loaded_layout.addWidget(groups_widget, stretch=1)

        # Evidence detail panel
        detail_label = QtWidgets.QLabel("证据详情")
        detail_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        loaded_layout.addWidget(detail_label)
        self._evidence_detail = QtWidgets.QTextEdit()
        self._evidence_detail.setReadOnly(True)
        self._evidence_detail.setMaximumHeight(160)
        self._evidence_detail.setPlaceholderText("选中上方表格中的证据行查看解释")
        loaded_layout.addWidget(self._evidence_detail)

        self._evidence_stack.addWidget(loaded_widget)

        # Page 1: empty/error
        self._evidence_empty = QtWidgets.QLabel("加载 bundle 以查看证据")
        self._evidence_empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._evidence_empty.setStyleSheet("color: {}; font-size: 14px;".format(_TEXT_DIM))
        self._evidence_stack.addWidget(self._evidence_empty)

        return page

    def _update_evidence(self) -> None:
        # Clear previous group widgets
        while self._evidence_groups_layout.count():
            item = self._evidence_groups_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        self._evidence_detail.setPlainText("")

        if self._bundle is None:
            self._evidence_stack.setCurrentIndex(1)
            self._evidence_empty.setText("请先加载 artifact bundle。")
            return

        vm = build_evidence_page_view_model(self._bundle)
        if not vm.is_loaded:
            self._evidence_stack.setCurrentIndex(1)
            self._evidence_empty.setText(vm.load_error or "无法加载证据数据。")
            return

        self._evidence_stack.setCurrentIndex(0)

        group_descriptions = {
            "L5/L6 代码证据": "从 L5/L6 Python 代码中提取的符号、类、函数、方法等证据项。",
            "RTL 证据": "从 RTL Verilog/SystemVerilog 中提取的模块、信号、always、assign 等证据项。",
            "桥接/映射证据": "连接 L5/L6 和 RTL 两边的桥接证据项。",
        }

        # Collect all evidence rows for lookup.
        all_evidence_rows: list[Any] = []  # pyright: ignore[reportExplicitAny]

        for group in vm.groups:
            group_label = QtWidgets.QLabel(group.title)
            group_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #333; margin-top: 8px;"
            )
            self._evidence_groups_layout.addWidget(group_label)

            desc = group_descriptions.get(group.title, "")
            if desc:
                desc_label = QtWidgets.QLabel(desc)
                desc_label.setStyleSheet(
                    "font-size: 11px; color: {}; margin-bottom: 4px;".format(_TEXT_DIM)
                )
                self._evidence_groups_layout.addWidget(desc_label)

            if not group.rows:
                empty_label = QtWidgets.QLabel("当前没有该类证据。")
                empty_label.setStyleSheet("color: {}; font-size: 12px;".format(_TEXT_DIM))
                self._evidence_groups_layout.addWidget(empty_label)
                continue

            table = QtWidgets.QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(
                ["Evidence ID", "Source", "File", "Symbol", "Strength", "Claim Refs"]
            )
            table.setRowCount(len(group.rows))
            for i, row in enumerate(group.rows):
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.evidence_id))
                table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.source_type))
                table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.file_path))
                table.setItem(i, 3, QtWidgets.QTableWidgetItem(row.symbol))
                table.setItem(i, 4, QtWidgets.QTableWidgetItem(row.evidence_strength))
                table.setItem(i, 5, QtWidgets.QTableWidgetItem(row.referenced_by_claims))
                all_evidence_rows.append(row)

            # Connect selection to detail panel.
            table.itemSelectionChanged.connect(
                lambda t=table, rows=all_evidence_rows: self._on_evidence_row_selected(t, rows)
            )
            self._evidence_groups_layout.addWidget(table)

    def _on_evidence_row_selected(
        self,
        table: QtWidgets.QTableWidget,
        rows: list[Any],  # pyright: ignore[reportExplicitAny]
    ) -> None:
        """Show detail explanation for the selected evidence row."""
        selected = table.selectedItems()
        if not selected:
            return
        row_idx = selected[0].row()
        if row_idx < 0 or row_idx >= len(rows):
            return
        row = rows[row_idx]
        lines = ["【证据详情解释】", ""]
        lines.append("Evidence ID: {}".format(row.evidence_id))
        lines.append("来源类型: {}".format(row.source_type))
        if "concept" in row.source_type.lower() or "l5" in row.source_type.lower() or "l6" in row.source_type.lower():
            lines.append("分类: L5/L6 代码证据")
        elif "rtl" in row.source_type.lower():
            lines.append("分类: RTL 证据")
        else:
            lines.append("分类: 其他证据")
        lines.append("符号: {}".format(row.symbol))
        lines.append("文件: {}".format(row.file_path))
        lines.append("")

        strength = row.evidence_strength
        lines.append("证据强度: {}".format(strength))
        if strength == "strong":
            lines.append("含义: 高置信度匹配，可直接支撑 mapping claim。")
        elif strength == "medium":
            lines.append("含义: 中等置信度，需要额外验证或上下文确认。")
        elif strength == "weak":
            lines.append("含义: 低置信度，仅供参考，不建议单独作为映射依据。")
        elif strength == "unknown":
            lines.append("含义: 未评估或无法判断强度。")
        else:
            lines.append("含义: 未定义强度等级。")

        lines.append("")
        if row.referenced_by_claims:
            lines.append("关联声明: {}".format(row.referenced_by_claims))
            lines.append("说明: 这条证据被上述 mapping claim 引用，是 claim 成立的基础之一。")
        else:
            lines.append("关联声明: 无")
            lines.append("说明: 当前这条证据未被任何 mapping claim 直接引用。")

        lines.append("")
        lines.append("为什么重要:")
        lines.append("证据是 mapping claim 的根基。没有足够数量和强度的证据，")
        lines.append("claim 的可信度只能停留在 inferred 或 unknown。")
        if strength in ("strong", "medium"):
            lines.append("当前证据强度较高，对 claim 有实质性支撑作用。")
        elif strength == "weak":
            lines.append("当前证据强度较低，建议补充更多证据或人工 review。")

        self._evidence_detail.setPlainText("\n".join(lines))

    # ========================================================================
    # Page 3: Unknowns
    # ========================================================================

    def _build_unknowns_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("不确定项与限制")
        layout = getattr(page, "_content_layout")

        self._unknowns_stack = QtWidgets.QStackedWidget()
        layout.addWidget(self._unknowns_stack, stretch=1)

        # Page 0: loaded
        loaded = QtWidgets.QWidget()
        loaded_layout = QtWidgets.QVBoxLayout(loaded)
        loaded_layout.setContentsMargins(0, 0, 0, 0)

        self._un_limitations_label = QtWidgets.QLabel("Unknown Limitations")
        self._un_limitations_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        loaded_layout.addWidget(self._un_limitations_label)

        self._un_limitations = QtWidgets.QListWidget()
        loaded_layout.addWidget(self._un_limitations)

        self._un_notes_label = QtWidgets.QLabel("Uncertainty Notes")
        self._un_notes_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        loaded_layout.addWidget(self._un_notes_label)

        self._un_notes = QtWidgets.QListWidget()
        loaded_layout.addWidget(self._un_notes)

        self._un_diagnostics_label = QtWidgets.QLabel("Grounding Diagnostics")
        self._un_diagnostics_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        loaded_layout.addWidget(self._un_diagnostics_label)

        self._un_diagnostics = QtWidgets.QTableWidget()
        self._un_diagnostics.setColumnCount(2)
        self._un_diagnostics.setHorizontalHeaderLabels(["Severity", "Message"])
        loaded_layout.addWidget(self._un_diagnostics)

        self._un_why_label = QtWidgets.QLabel("为什么不是 Confirmed")
        self._un_why_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        loaded_layout.addWidget(self._un_why_label)

        self._un_why = QtWidgets.QTextEdit()
        self._un_why.setReadOnly(True)
        loaded_layout.addWidget(self._un_why)

        self._unknowns_stack.addWidget(loaded)

        # Page 1: empty
        self._unknowns_empty = QtWidgets.QLabel("加载 P1b bundle 以查看不确定项")
        self._unknowns_empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._unknowns_empty.setStyleSheet("color: {}; font-size: 14px;".format(_TEXT_DIM))
        self._unknowns_stack.addWidget(self._unknowns_empty)

        return page

    def _update_unknowns(self) -> None:
        self._un_limitations.clear()
        self._un_notes.clear()
        self._un_diagnostics.setRowCount(0)
        self._un_why.clear()

        if self._bundle is None:
            self._unknowns_stack.setCurrentIndex(1)
            self._unknowns_empty.setText("请先加载 P1b concept trace bundle。")
            return

        vm = build_unknowns_page_view_model(self._bundle)
        if not vm.is_loaded:
            self._unknowns_stack.setCurrentIndex(1)
            self._unknowns_empty.setText(vm.load_error or "无法加载不确定项数据。")
            return

        self._unknowns_stack.setCurrentIndex(0)

        for lim in vm.limitations:
            self._un_limitations.addItem(lim)
        if not vm.limitations:
            self._un_limitations.addItem("暂无未知限制")

        for note in vm.uncertainty_notes:
            self._un_notes.addItem(note)
        if not vm.uncertainty_notes:
            self._un_notes.addItem("暂无不确定注释")

        self._un_diagnostics.setRowCount(len(vm.grounding_diagnostics))
        for i, diag in enumerate(vm.grounding_diagnostics):
            sev = diag.get("severity", "")
            msg = diag.get("message", "")
            self._un_diagnostics.setItem(i, 0, QtWidgets.QTableWidgetItem(sev))
            self._un_diagnostics.setItem(i, 1, QtWidgets.QTableWidgetItem(msg))
        if not vm.grounding_diagnostics:
            self._un_diagnostics.setRowCount(1)
            self._un_diagnostics.setItem(0, 0, QtWidgets.QTableWidgetItem("info"))
            self._un_diagnostics.setItem(0, 1, QtWidgets.QTableWidgetItem("无 grounding diagnostics"))

        self._un_why.setPlainText(vm.why_not_confirmed)

    # ========================================================================
    # Page 4: Agent QA
    # ========================================================================

    def _build_agent_qa_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("Agent 问答")
        layout = getattr(page, "_content_layout")

        # Agent note
        agent_note = QtWidgets.QLabel(
            "当前为本地确定性 Agent，基于已加载的 artifact 做规则化查询，不调用外部 LLM / API。"
        )
        agent_note.setStyleSheet(
            "font-size: 11px; color: {}; background-color: #f0f4ff; "
            "border: 1px solid #d0d8f0; border-radius: 4px; padding: 6px 10px;".format(
                _TEXT_DIM
            )
        )
        agent_note.setWordWrap(True)
        layout.addWidget(agent_note)

        # Suggested questions
        sq_label = QtWidgets.QLabel("💡 建议问题")
        sq_label.setStyleSheet("font-size: 13px; color: {};".format(_TEXT_DIM))
        layout.addWidget(sq_label)

        self._agent_suggestions = QtWidgets.QWidget()
        self._agent_suggestions_layout = QtWidgets.QHBoxLayout(self._agent_suggestions)
        self._agent_suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self._agent_suggestions_layout.setSpacing(8)
        layout.addWidget(self._agent_suggestions)

        # Input row
        input_row = QtWidgets.QHBoxLayout()
        self._agent_question = QtWidgets.QLineEdit()
        self._agent_question.setPlaceholderText(
            "输入问题，例如：概况、映射、证据、诊断、不确定、节点、边..."
        )
        ask_btn = QtWidgets.QPushButton("Ask")
        ask_btn.clicked.connect(self._on_agent_ask)
        ask_btn.setStyleSheet(
            "background-color: {}; color: white; border: none; "
            "border-radius: 4px; padding: 8px 20px; font-weight: bold;".format(_ACCENT)
        )
        input_row.addWidget(self._agent_question, stretch=1)
        input_row.addWidget(ask_btn)
        layout.addLayout(input_row)

        # Answer area
        ans_label = QtWidgets.QLabel("回答")
        ans_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        layout.addWidget(ans_label)

        self._agent_answer = QtWidgets.QTextEdit()
        self._agent_answer.setReadOnly(True)
        self._agent_answer.setPlaceholderText("选择上方问题或输入后点击 Ask")
        layout.addWidget(self._agent_answer)

        # Evidence referenced
        ev_label = QtWidgets.QLabel("引用的证据")
        ev_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        layout.addWidget(ev_label)

        self._agent_evidence = QtWidgets.QTextEdit()
        self._agent_evidence.setReadOnly(True)
        self._agent_evidence.setMaximumHeight(80)
        layout.addWidget(self._agent_evidence)

        # Limitations
        lim_label = QtWidgets.QLabel("限制与不确定")
        lim_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        layout.addWidget(lim_label)

        self._agent_limitations = QtWidgets.QTextEdit()
        self._agent_limitations.setReadOnly(True)
        self._agent_limitations.setMaximumHeight(80)
        layout.addWidget(self._agent_limitations)

        # Plan preview
        plan_label = QtWidgets.QLabel("计划预览")
        plan_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        layout.addWidget(plan_label)

        self._agent_plan = QtWidgets.QTextEdit()
        self._agent_plan.setReadOnly(True)
        self._agent_plan.setMaximumHeight(120)
        layout.addWidget(self._agent_plan)

        return page

    def _update_agent_qa(self) -> None:
        # Clear suggestion buttons
        while self._agent_suggestions_layout.count():
            item = self._agent_suggestions_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        if not self._current_suggested_questions:
            empty = QtWidgets.QLabel("加载 bundle 后显示建议问题")
            empty.setStyleSheet("color: {};".format(_TEXT_DIM))
            self._agent_suggestions_layout.addWidget(empty)
            return

        for q in self._current_suggested_questions[:6]:
            btn = QtWidgets.QPushButton(q.text)
            btn.setStyleSheet(
                "background-color: white; border: 1px solid {}; "
                "border-radius: 16px; padding: 6px 14px; font-size: 12px;".format(
                    _BORDER
                )
            )
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, t=q.text: self._ask_question(t))
            self._agent_suggestions_layout.addWidget(btn)
        self._agent_suggestions_layout.addStretch(1)

    def _ask_question(self, question: str) -> None:
        self._agent_question.setText(question)
        self._on_agent_ask()

    def _on_agent_ask(self) -> None:
        question = self._agent_question.text().strip()
        if not question:
            self._agent_answer.setPlainText("请输入问题。")
            self._agent_evidence.setPlainText("")
            self._agent_limitations.setPlainText("")
            self._agent_plan.setPlainText("")
            return
        if self._bundle is None:
            self._agent_answer.setPlainText("请先加载 artifact bundle。")
            self._agent_evidence.setPlainText("")
            self._agent_limitations.setPlainText("")
            self._agent_plan.setPlainText("")
            return

        vm = query_artifact_bundle(self._bundle, question)
        if not vm.is_loaded:
            self._agent_answer.setPlainText(vm.load_error or "Query failed.")
            self._agent_evidence.setPlainText("")
            self._agent_limitations.setPlainText("")
            self._agent_plan.setPlainText("")
            return

        self._agent_answer.setPlainText(vm.answer_text)

        ev_text = ""
        if vm.referenced_claim_ids:
            ev_text += "Claims: {}\n".format(", ".join(vm.referenced_claim_ids))
        if vm.referenced_evidence_ids:
            ev_text += "Evidence: {}\n".format(", ".join(vm.referenced_evidence_ids))
        if vm.referenced_diagnostic_ids:
            ev_text += "Diagnostics: {}".format(", ".join(vm.referenced_diagnostic_ids))
        self._agent_evidence.setPlainText(ev_text or "无引用证据")

        lim_text = ""
        if vm.uncertainty_notes:
            lim_text = "\n".join("- " + note for note in vm.uncertainty_notes)
        self._agent_limitations.setPlainText(lim_text or "无已知限制")

        plan = build_agent_plan_preview(self._bundle, question, vm)
        plan_text = self._format_plan_preview(plan)
        self._agent_plan.setPlainText(plan_text)
        self._last_plan_preview_text = plan_text

    def _format_plan_preview(self, plan: AgentPlanPreview) -> str:
        if not plan.is_loaded:
            return plan.load_error or "Plan preview unavailable."
        lines: list[str] = []
        lines.append("Intent: {}".format(plan.intent))
        if plan.steps:
            lines.append("")
            for step in plan.steps:
                lines.append("[{}] {}".format(step.step_id, step.title))
        if plan.safety_notes:
            lines.append("")
            lines.append("Safety Notes:")
            for note in plan.safety_notes:
                lines.append("  - {}".format(note))
        return "\n".join(lines)

    # ========================================================================
    # Page 5: Agent Runtime
    # ========================================================================

    def _build_agent_runtime_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("Agent Runtime")
        layout = getattr(page, "_content_layout")

        self._art_stack = QtWidgets.QStackedWidget()
        layout.addWidget(self._art_stack, stretch=1)

        # Page 0: trace content
        trace_widget = QtWidgets.QWidget()
        trace_layout = QtWidgets.QVBoxLayout(trace_widget)
        trace_layout.setContentsMargins(0, 0, 0, 0)

        self._art_summary = QtWidgets.QFormLayout()
        trace_layout.addLayout(self._art_summary)

        self._art_steps = QtWidgets.QTableWidget()
        self._art_steps.setColumnCount(6)
        self._art_steps.setHorizontalHeaderLabels(
            ["Section", "ID", "Title", "Status", "Summary", "References"]
        )
        trace_layout.addWidget(self._art_steps)

        self._art_diag_label = QtWidgets.QLabel("Runtime Diagnostics")
        trace_layout.addWidget(self._art_diag_label)

        self._art_diag = QtWidgets.QTableWidget()
        self._art_diag.setColumnCount(2)
        self._art_diag.setHorizontalHeaderLabels(["Severity", "Message"])
        trace_layout.addWidget(self._art_diag)

        self._art_stack.addWidget(trace_widget)

        # Page 1: info / unavailable
        self._art_info = QtWidgets.QTextEdit()
        self._art_info.setReadOnly(True)
        self._art_stack.addWidget(self._art_info)

        return page

    def _update_agent_runtime(self) -> None:
        # Clear tables
        while self._art_summary.rowCount() > 0:
            self._art_summary.removeRow(0)
        self._art_steps.setRowCount(0)
        self._art_diag.setRowCount(0)

        if self._bundle is None:
            self._art_stack.setCurrentIndex(1)
            self._art_info.setPlainText(
                "请先加载 artifact bundle。\n\n"
                "生成 agent_runtime bundle:\n"
                "  PYTHONPATH=src python -m fpga_devmind.cli desktop-sample-run"
            )
            return

        state = build_agent_runtime_page_state(self._bundle)
        if not state.is_visible:
            self._art_stack.setCurrentIndex(1)
            self._art_info.setPlainText(state.message)
            return

        if not state.is_loaded:
            self._art_stack.setCurrentIndex(1)
            self._art_info.setPlainText(state.load_error or "无法加载 trace。")
            return

        self._art_stack.setCurrentIndex(0)

        vm = build_agent_runtime_trace_view_model(self._bundle)
        if not vm.is_loaded:
            self._art_stack.setCurrentIndex(1)
            self._art_info.setPlainText(vm.load_error or "无法加载 trace。")
            return

        for row in vm.summary_rows:
            self._art_summary.addRow(row.field, QtWidgets.QLabel(row.value))

        self._art_steps.setRowCount(len(vm.step_rows))
        for i, row in enumerate(vm.step_rows):
            self._art_steps.setItem(i, 0, QtWidgets.QTableWidgetItem(row.section))
            self._art_steps.setItem(i, 1, QtWidgets.QTableWidgetItem(row.item_id))
            self._art_steps.setItem(i, 2, QtWidgets.QTableWidgetItem(row.title))
            self._art_steps.setItem(i, 3, QtWidgets.QTableWidgetItem(row.status))
            self._art_steps.setItem(i, 4, QtWidgets.QTableWidgetItem(row.summary))
            self._art_steps.setItem(i, 5, QtWidgets.QTableWidgetItem(row.references))

        self._art_diag.setRowCount(len(vm.diagnostic_rows))
        for i, row in enumerate(vm.diagnostic_rows):
            self._art_diag.setItem(i, 0, QtWidgets.QTableWidgetItem(row.severity))
            self._art_diag.setItem(i, 1, QtWidgets.QTableWidgetItem(row.message))

        has_diags = len(vm.diagnostic_rows) > 0
        self._art_diag_label.setVisible(has_diags)
        self._art_diag.setVisible(has_diags)

    # ========================================================================
    # Page 6: Plan & Tools
    # ========================================================================

    def _build_plan_tools_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("计划与工具")
        layout = getattr(page, "_content_layout")

        info = QtWidgets.QLabel(
            "此页面展示 Agent 执行查询时的只读工具计划预览。\n"
            "请在 Agent 问答页面输入问题后查看计划。"
        )
        info.setStyleSheet("color: {}; font-size: 13px;".format(_TEXT_DIM))
        layout.addWidget(info)

        self._plan_display = QtWidgets.QTextEdit()
        self._plan_display.setReadOnly(True)
        self._plan_display.setPlaceholderText(
            "在 Agent 问答页面提问后将自动显示计划预览。"
        )
        layout.addWidget(self._plan_display, stretch=1)

        layout.addStretch(1)
        return page

    def _update_plan_tools(self) -> None:
        state = build_plan_tools_page_state(self._last_plan_preview_text)
        self._plan_display.setPlainText(state.display_text)

    # ========================================================================
    # Page 7: Raw Data
    # ========================================================================

    def _build_raw_data_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("Raw Data")
        layout = getattr(page, "_content_layout")

        info = QtWidgets.QLabel(
            "此页面为开发者提供原始 JSON artifact 的树形浏览。"
        )
        info.setStyleSheet("color: {}; font-size: 12px;".format(_TEXT_DIM))
        layout.addWidget(info)

        selector_row = QtWidgets.QHBoxLayout()
        self._raw_selector = QtWidgets.QComboBox()
        self._raw_selector.currentTextChanged.connect(self._on_raw_selected)
        selector_row.addWidget(QtWidgets.QLabel("Artifact:"))
        selector_row.addWidget(self._raw_selector, stretch=1)
        layout.addLayout(selector_row)

        self._raw_tree = QtWidgets.QTreeWidget()
        self._raw_tree.setHeaderLabels(["Key", "Value", "Type"])
        layout.addWidget(self._raw_tree, stretch=1)

        return page

    def _update_raw_data(self) -> None:
        self._raw_selector.clear()
        self._raw_tree.clear()
        if self._bundle is None:
            return
        for name in sorted(self._bundle.artifacts.keys()):
            artifact = self._bundle.artifacts[name]
            if artifact.content_type == "json":
                self._raw_selector.addItem(name)
        if self._raw_selector.count() > 0:
            self._on_raw_selected(self._raw_selector.currentText())

    def _on_raw_selected(self, name: str) -> None:
        self._raw_tree.clear()
        if self._bundle is None or not name:
            return
        vm = build_json_tree(self._bundle, name)
        if not vm.is_loaded or vm.root is None:
            item = QtWidgets.QTreeWidgetItem(["Error", vm.load_error or "Unknown", "error"])
            self._raw_tree.addTopLevelItem(item)
            return
        self._add_tree_node(None, vm.root)
        self._raw_tree.expandToDepth(2)

    def _add_tree_node(
        self,
        parent: QtWidgets.QTreeWidgetItem | None,
        node: JsonTreeNode,
    ) -> QtWidgets.QTreeWidgetItem:
        item = QtWidgets.QTreeWidgetItem([node.key, node.value, node.value_type])
        if parent is None:
            self._raw_tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            self._add_tree_node(item, child)
        return item

    # ========================================================================
    # Page 8: Markdown
    # ========================================================================

    def _build_markdown_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("Markdown")
        layout = getattr(page, "_content_layout")

        info = QtWidgets.QLabel("Concept trace 的 Markdown 摘要预览。")
        info.setStyleSheet("color: {}; font-size: 12px;".format(_TEXT_DIM))
        layout.addWidget(info)

        self._md_display = QtWidgets.QPlainTextEdit()
        self._md_display.setReadOnly(True)
        layout.addWidget(self._md_display, stretch=1)

        return page

    def _update_markdown(self) -> None:
        self._md_display.clear()
        if self._bundle is None:
            return
        vm = build_markdown_preview(self._bundle, "concept_trace.md")
        if not vm.is_loaded:
            vm = build_markdown_preview(self._bundle, "concept_trace.mmd")
        if vm.is_loaded:
            self._md_display.setPlainText(vm.content)

    # ========================================================================
    # Page 9: Diagnostics
    # ========================================================================

    def _build_diagnostics_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("Diagnostics")
        layout = getattr(page, "_content_layout")

        info = QtWidgets.QLabel("Bundle 加载诊断信息。")
        info.setStyleSheet("color: {}; font-size: 12px;".format(_TEXT_DIM))
        layout.addWidget(info)

        self._diag_display = QtWidgets.QListWidget()
        layout.addWidget(self._diag_display, stretch=1)

        return page

    def _update_diagnostics(self) -> None:
        self._diag_display.clear()
        if self._bundle is None:
            self._diag_display.addItem("未加载 bundle。")
            return
        if not self._bundle.diagnostics:
            self._diag_display.addItem("✓ 无诊断信息 — bundle 完整。")
            return
        for d in self._bundle.diagnostics:
            label = "[{}]".format(d.severity.upper())
            if d.artifact:
                label += " {}:".format(d.artifact)
            label += " {}".format(d.message)
            self._diag_display.addItem(label)

    # ========================================================================
    # Page 10: Project Settings
    # ========================================================================

    def _build_project_settings_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("项目设置")
        layout = getattr(page, "_content_layout")

        # Artifact path
        path_label = QtWidgets.QLabel("Artifact 目录")
        path_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(path_label)

        path_row = QtWidgets.QHBoxLayout()
        self._settings_path = QtWidgets.QLineEdit()
        self._settings_path.setPlaceholderText("/path/to/artifact/bundle")
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        load_btn = QtWidgets.QPushButton("Load Bundle")
        load_btn.clicked.connect(self._on_load_from_settings)
        path_row.addWidget(self._settings_path, stretch=1)
        path_row.addWidget(browse_btn)
        path_row.addWidget(load_btn)
        layout.addLayout(path_row)

        layout.addSpacing(16)

        # Bundle info
        info_label = QtWidgets.QLabel("当前 Bundle 信息")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(info_label)

        self._settings_info = QtWidgets.QFormLayout()
        layout.addLayout(self._settings_info)

        layout.addStretch(1)
        return page

    def _update_project_settings(self) -> None:
        while self._settings_info.rowCount() > 0:
            self._settings_info.removeRow(0)

        if self._bundle is None:
            self._settings_info.addRow("状态", QtWidgets.QLabel("未加载"))
            return

        self._settings_info.addRow(
            "Bundle 类型", QtWidgets.QLabel(self._bundle.bundle_type)
        )
        self._settings_info.addRow(
            "目录", QtWidgets.QLabel(str(self._bundle.directory))
        )
        self._settings_info.addRow(
            "完整", QtWidgets.QLabel("是" if self._bundle.is_complete else "否")
        )
        self._settings_info.addRow(
            "Artifacts", QtWidgets.QLabel(str(len(self._bundle.artifacts)))
        )
        self._settings_info.addRow(
            "诊断数", QtWidgets.QLabel(str(len(self._bundle.diagnostics)))
        )

    def _on_load_from_settings(self) -> None:
        path = self._settings_path.text().strip()
        if path:
            self._dir_input.setText(path)
            self._on_load()

    # ========================================================================
    # Page 11: General Settings
    # ========================================================================

    def _build_general_settings_page(self) -> QtWidgets.QWidget:
        page = self._make_page_widget("通用设置")
        layout = getattr(page, "_content_layout")

        info = QtWidgets.QLabel(
            "通用设置将在未来版本中添加。\n"
            "当前版本: FPGA DevMind Desktop Shell (T020)"
        )
        info.setStyleSheet("color: {}; font-size: 13px;".format(_TEXT_DIM))
        layout.addWidget(info)

        layout.addStretch(1)
        return page

    def _update_general_settings(self) -> None:
        pass

    # ========================================================================
    # Event handlers
    # ========================================================================

    def _on_browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Artifact Directory"
        )
        if path:
            self._dir_input.setText(path)
            self._settings_path.setText(path)

    def _on_load(self) -> None:
        path_str = self._dir_input.text().strip()
        if not path_str:
            self._bundle = None
            self._refresh_all()
            return

        path = Path(path_str)
        self._bundle = load_bundle(path)
        self._settings_path.setText(str(path))
        self._refresh_all()

    def _refresh_all(self) -> None:
        """Update all pages after bundle load."""
        self._update_top_bar()
        self._update_overview()
        self._update_concept_trace()
        self._update_evidence()
        self._update_unknowns()
        self._update_agent_qa()
        self._update_agent_runtime()
        self._update_plan_tools()
        self._update_raw_data()
        self._update_markdown()
        self._update_diagnostics()
        self._update_project_settings()


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
