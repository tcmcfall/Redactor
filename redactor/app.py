# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent, QLockFile, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFormLayout, QMessageBox, QDialogButtonBox, QCheckBox,
    QComboBox, QStackedWidget, QFrame, QSplitter, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QFileDialog, QInputDialog,
    QButtonGroup, QProgressBar, QTextBrowser, QTabBar,
)

from .engine import Candidate, KINDS, detect, suggest, prepare_mappings, replace_exact, restore, validate_mappings, literal_pattern
from .engine import candidate_occurrences, occurrence_selected, replace_candidates, find_similar_values
from .formats import read_file, export_file, INPUT_EXTENSIONS, OUTPUT_EXTENSIONS, MAX_TEXT, NOTICE, tesseract_path
from .vault import Vault, vault_directory, derive
from .portable import directory, output_path, configure, atomic_replace
from .widgets import Brand, ColumnFilters, document
from .operations import audit_text, bulk_proposal, save_mappings
from .analyst_ui import AnalystActions, import_account_dialog

STYLE = """
QWidget { color: #203b37; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QDialog { background: #f5f6f2; }
QMenuBar, QMenu, QStatusBar { background: #eef2eb; color: #203b37; }
QMenuBar::item:selected, QMenu::item:selected { background: #d4e3d7; }
QLabel#brand { font-size: 26px; font-weight: 700; letter-spacing: -1px; }
QLabel#title { font-size: 27px; font-weight: 650; }
QLabel#muted { color: #61736d; }
QLabel#eyebrow { color: #467567; font-size: 11px; font-weight: 700; }
QLabel#notice { background: #edf2e7; border: 1px solid #dbe5d3; border-radius: 7px; padding: 10px; color: #506345; }
QLabel#security { background: #fbe0e0; border: 2px solid #8b2424; border-radius: 8px; padding: 16px; color: black; font-size: 15px; font-weight: 600; }
QFrame#sidebar { background: #e9eee7; border-right: 1px solid #d8e0d7; }
QPushButton { background: #ffffff; border: 1px solid #ccd7d0; border-radius: 6px; padding: 9px 14px; }
QPushButton:hover { background: #edf4ef; border-color: #829e8d; }
QPushButton:pressed, QPushButton:checked { background: #dae9df; border-color: #6e9380; }
QPushButton#primary { background: #245b48; color: white; border-color: #245b48; font-weight: 600; }
QPushButton#primary:hover { background: #32735b; }
QPushButton#danger { color: #a23c34; border-color: #dfc6c1; }
QPushButton:disabled { color: #99a59d; background: #edf0eb; border-color: #e0e5df; }
QPushButton#nav { text-align: left; padding: 12px 15px; border: none; background: transparent; }
QPushButton#nav:checked { background: #d4e3d7; color: #174a36; font-weight: 650; }
QTextEdit, QLineEdit, QComboBox { background: #ffffff; border: 1px solid #ccd7d0; border-radius: 6px; padding: 7px; selection-background-color: #c2dfce; selection-color: #183a2c; }
QTextEdit:focus, QLineEdit:focus { border-color: #52866b; }
QTableWidget { background: #ffffff; border: 1px solid #d7dfd6; gridline-color: #edf0eb; selection-background-color: #dcece1; selection-color: #203b37; }
QHeaderView::section { background: #eef2eb; padding: 8px; border: none; border-bottom: 1px solid #d7dfd6; text-align: left; font-weight: 600; }
QTabBar::tab { background: #e9eee7; color: #203b37; padding: 10px 16px; border: 1px solid #b8cec0; }
QTabBar::tab:selected { background: #d4e3d7; color: #174a36; font-weight: bold; }
QComboBox QAbstractItemView { background: #ffffff; color: #203b37; selection-background-color: #d4e3d7; selection-color: #174a36; }
QCheckBox { spacing: 8px; }
QSplitter::handle { background: #d5dfd3; }
QSplitter::handle:hover { background: #86ab94; }
QToolTip { background: #ffffff; color: #203b37; border: 1px solid #bfcfc3; padding: 5px; }
QProgressBar { border: none; background: #e1e9de; max-height: 4px; }
QProgressBar::chunk { background: #47795b; }
"""


def label(text, name=None, wrap=False):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    if name: item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def button(text, callback, primary=False):
    item = QPushButton(text.replace("&", "&&"))
    if primary: item.setObjectName("primary")
    item.clicked.connect(callback)
    return item


def error(parent, message):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Redactor")
    box.setTextFormat(Qt.TextFormat.PlainText)
    from .errors import record
    owner = parent
    while owner is not None and not getattr(owner, 'vault', None): owner = owner.parent()
    info = record(message, getattr(owner, 'vault', None))
    box.setText(info['code'] + ' — ' + info['title'])
    box.setInformativeText(str(message) + '\n\nRecommended action: ' + info['recommended_action'] + '\n\nHelp → Error Guide → ' + info['code'])
    box.setDetailedText('Reference: ' + info['help'] + '\nDiagnostic categories are logged in data/logs/errors.jsonl.')
    help_button = box.addButton('Open Error Guide', QMessageBox.ButtonRole.HelpRole)
    help_button.clicked.connect(lambda: document(parent, 'Error-Guide.md'))
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()


def confirm(parent, title, message) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(message)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    return box.exec() == QMessageBox.StandardButton.Yes


class WorkerSignals(QObject):
    success = Signal(object)
    failure = Signal(str)


class Worker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function, self.signals = function, WorkerSignals()

    def run(self):
        try: self.signals.success.emit(self.function())
        except Exception as exc: self.signals.failure.emit(str(exc))


class Login(QDialog):
    def __init__(self, directory):
        super().__init__()
        self.directory, self.vault = directory, None
        self.failed_attempts = 0
        self.setWindowTitle("Redactor — unlock local vault")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(Brand())
        layout.addWidget(label("Sensitive work. Familiar words. Local control.", "muted"))
        self.create_account = QCheckBox("Create a new local account")
        self.create_account.setChecked(not any(directory.glob("*.vault")))
        layout.addWidget(self.create_account)
        form = QFormLayout()
        self.username, self.password, self.repeat = QLineEdit(), QLineEdit(), QLineEdit()
        self.username.setPlaceholderText("Your local username")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("&Username", self.username)
        form.addRow("&Password", self.password)
        self.repeat_label = QLabel("&Confirm password")
        self.repeat_label.setBuddy(self.repeat)
        form.addRow(self.repeat_label, self.repeat)
        layout.addLayout(form)
        layout.addWidget(label("Your password encrypts your vault. Use at least 12 characters when creating an account. There is no password reset or recovery service.", "notice", True))
        self.submit = button("Unlock vault", self.login, True)
        self.submit.setDefault(True)
        layout.addWidget(self.submit)
        layout.addWidget(label("OFFLINE BY DESIGN · Redactor performs no network or internet communication at any stage. All processing and storage stay in this portable folder.", "eyebrow", True))
        self.create_account.toggled.connect(self.update_mode)
        self.update_mode()

    def import_account(self):
        imported = import_account_dialog(self, self.directory)
        if imported:
            self.vault = imported
            self.accept()

    def update_mode(self):
        create = self.create_account.isChecked()
        self.repeat.setVisible(create)
        self.repeat_label.setVisible(create)
        self.submit.setText("Create encrypted vault" if create else "Unlock vault")

    def login(self):
        if self.create_account.isChecked() and self.password.text() != self.repeat.text():
            error(self, "Passwords do not match.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            fn = Vault.create if self.create_account.isChecked() else Vault.open
            self.vault = fn(self.directory, self.username.text(), self.password.text())
            self.vault.commit("account_unlocked", interface="gui")
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self.failed_attempts += 1
            self.submit.setEnabled(False)
            QTimer.singleShot(min(30000, 1000 * 2 ** min(self.failed_attempts - 1, 5)), lambda: self.submit.setEnabled(True))
            error(self, exc)
            return
        QApplication.restoreOverrideCursor()
        self.password.clear()
        self.repeat.clear()
        self.accept()


class MappingDialog(QDialog):
    def __init__(self, parent, original, kind, replacement):
        super().__init__(parent)
        self.setWindowTitle("Sensitive value")
        self.resize(570, 280)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.original, self.replacement = SensitiveValueEditor(original), QLineEdit(replacement)
        self.kind = QComboBox()
        self.kind.addItems(KINDS)
        self.kind.setCurrentText(kind)
        form.addRow("Sensitive &value", self.original)
        form.addRow("&Type", self.kind)
        form.addRow("&Replacement", self.replacement)
        layout.addLayout(form)
        layout.addWidget(button("Generate another suggestion", self.generate))
        self.explanation = label("Exact spelling is retained. Different capitalization and abbreviations are stored as separate values.", "notice", True)
        layout.addWidget(self.explanation)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def generate(self):
        try:
            parent = self.parent()
            forbidden = [self.original.text(), parent.source.toPlainText()]
            forbidden += [v for m in parent.vault.data["mappings"] for v in [m["original"], m["replacement"], *m.get("aliases", [])]]
            self.replacement.setText(suggest(self.kind.currentText(), forbidden, self.original.text()))
        except Exception as exc: error(self, exc)


class SensitiveValueEditor(QTextEdit):
    def __init__(self, text):
        super().__init__()
        self.setAcceptRichText(False)
        self.setPlainText(text)
        self.setMaximumHeight(75)

    def text(self):
        return self.toPlainText()


class CandidateTable(QTableWidget):
    """Keep the highlighted group intact when its Use checkbox is clicked."""
    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        rows = {item.row() for item in self.selectionModel().selectedRows()}
        self._group_checkbox_click = (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
            and index.isValid() and index.column() == 0
            and index.row() in rows and len(rows) > 1
        )
        if self._group_checkbox_click:
            item = self.item(index.row(), 0)
            item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "_group_checkbox_click", False):
            self._group_checkbox_click = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MainWindow(AnalystActions, QMainWindow):
    def __init__(self, vault: Vault):
        super().__init__()
        self.account_vault = vault
        self.open_databases = [vault]
        self.workspace_states = {}
        self.active_database = 0
        self.vault = vault
        self.candidates = []
        self.denied_similar = set()
        self.busy = False
        self.has_output = False
        self.mode = "redact"
        self.last_active = time.monotonic()
        self.owned_clipboard = None
        self.input_path = None
        self.relock = False
        self.setWindowTitle("Redactor")
        self.resize(1320, 920)
        self.setMinimumSize(1000, 740)
        root = QWidget()
        horizontal = QHBoxLayout(root)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(175)
        sidebar.setMaximumWidth(280)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(18, 28, 18, 20)
        nav.setSpacing(10)
        nav.addWidget(Brand())
        nav.addWidget(label("LOCAL DATA WORKSPACE", "eyebrow"))
        nav.addSpacing(28)
        self.pages = QStackedWidget()
        self.nav_group = QButtonGroup(self)
        for index, title in enumerate(["Workspace", "Conversion vault", "Audit activity", "Account & security"]):
            item = button(title, lambda checked=False, i=index: self.show_page(i))
            item.setObjectName("nav")
            item.setCheckable(True)
            self.nav_group.addButton(item, index)
            nav.addWidget(item)
        self.nav_group.button(0).setChecked(True)
        nav.addStretch()
        nav.addWidget(label("●  Processing stays local", "eyebrow"))
        nav.addWidget(label(vault.data["username"], "muted", True))
        self.lock_button = button("Lock vault  ·  Ctrl+L", self.lock)
        nav.addWidget(self.lock_button)
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setChildrenCollapsible(False)
        main_split.addWidget(sidebar); main_split.addWidget(self.pages)
        main_split.setSizes([210, 1110])
        horizontal.addWidget(main_split)
        wrapper = QWidget(); wrapper_layout = QVBoxLayout(wrapper)
        tabs_row = QHBoxLayout()
        self.database_tabs = QTabBar(); self.database_tabs.addTab('Main database'); self.database_tabs.setExpanding(False)
        tabs_row.addWidget(self.database_tabs,1)
        tabs_row.addWidget(button('Merge…', self.merge_databases))
        tabs_row.addWidget(button('New database', self.new_database))
        tabs_row.addWidget(button('Open exported database…', self.import_database))
        wrapper_layout.addLayout(tabs_row)
        wrapper_layout.addWidget(root)
        self.setCentralWidget(wrapper)
        self.make_workspace()
        self.make_vault_page()
        self.make_audit_page()
        self.make_account_page()
        self.statusBar().showMessage("Vault unlocked. Documents are held in memory until you explicitly export.")
        self.make_menu()
        from .databases import Database
        for database_id in vault.data.get('databases', {}):
            database = Database(vault,database_id); self.open_databases.append(database)
            self.database_tabs.addTab(database.data.get('title','Database'))
        self.database_tabs.currentChanged.connect(self.switch_database)
        QApplication.instance().installEventFilter(self)
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start(15000)
        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.setSingleShot(True)
        self.clipboard_timer.timeout.connect(self.clear_clipboard)
        if vault.data.get("remind", True) and vault.password_age >= 60:
            QTimer.singleShot(300, lambda: QMessageBox.information(self, "Optional password reminder", f"Your password was changed {vault.password_age} days ago. You may change it in Account & security, or keep using it. This is optional."))

    def page(self, title, subtitle):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(subtitle, "muted", True))
        self.pages.addWidget(widget)
        return layout

    def make_workspace(self):
        layout = self.page("A little fiction. A lot of privacy.", "Review sensitive details, work with substitutes, then bring the originals back.")
        modes = QHBoxLayout()
        group = QButtonGroup(self)
        self.redact_button = button("1  Review & replace", lambda: self.switch_mode("redact"))
        self.restore_button = button("2  Restore work product", lambda: self.switch_mode("restore"))
        for b in [self.redact_button, self.restore_button]:
            b.setCheckable(True)
            group.addButton(b)
            modes.addWidget(b)
        self.redact_button.setChecked(True)
        modes.addStretch()
        modes.addWidget(button("Format support", self.format_help))
        layout.addLayout(modes)
        self.notice = label("Start with text or import a file. Detection suggests candidates; review the whole input before sharing any output.", "notice", True)
        layout.addWidget(self.notice)
        toolbar = QHBoxLayout()
        self.import_button = button("Import file…", self.import_document)
        self.scan_button = button("Scan input  ·  Ctrl+R", self.scan, True)
        self.mark_button = button("Mark selection sensitive", self.mark_selection)
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.scan_button)
        toolbar.addWidget(self.mark_button)
        toolbar.addStretch()
        toolbar.addWidget(button("Clear workspace", self.clear_workspace))
        layout.addLayout(toolbar)
        vertical = self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        editors = self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        for splitter in (vertical, editors):
            splitter.setHandleWidth(10)
            splitter.setChildrenCollapsible(False)
            splitter.setOpaqueResize(True)
        for title, attr, placeholder in [
            ("INPUT", "source", "Paste sensitive material here, or import a document.\n\nSelect any overlooked value and choose “Mark selection sensitive.”"),
            ("WORK PRODUCT", "output", "Your reviewed substitutions will appear here.\n\nOriginals remain in your encrypted vault.")]:
            widget = QWidget()
            box = QVBoxLayout(widget)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(label(title, "eyebrow"))
            editor = QTextEdit()
            editor.setAcceptRichText(False)
            editor.setPlaceholderText(placeholder)
            editor.setAccessibleName(title)
            editor.setMinimumSize(100, 70)
            editor.setFont(QFont("Consolas", 11))
            setattr(self, attr, editor)
            box.addWidget(editor)
            editors.addWidget(widget)
        self.output.setReadOnly(True)
        self.source.textChanged.connect(self.source_changed)
        vertical.addWidget(editors)
        review = QWidget()
        box = QVBoxLayout(review)
        box.setContentsMargins(0, 8, 0, 0)
        bar = QHBoxLayout()
        self.review_title = label("SUGGESTED SUBSTITUTIONS  ·  Scan input to begin", "eyebrow")
        title_bar = QHBoxLayout()
        title_bar.addWidget(self.review_title)
        box.addLayout(title_bar)
        self.mark_rows_sensitive = button("Mark Selection Sensitive", lambda: self.mark_selected_rows(True))
        self.mark_rows_insensitive = button("Mark Selection Insensitive", lambda: self.mark_selected_rows(False))
        self.ignore_saved_button = button("Ignore saved suggestion", self.ignore_saved_suggestion)
        self.ignore_saved_button.setToolTip("Generate a fresh substitute for selected saved values. Earlier aliases remain restorable after saving. This changes the suggestion, not whether an occurrence is sensitive.")
        bar.addWidget(self.mark_rows_sensitive)
        bar.addWidget(self.mark_rows_insensitive)
        title_bar.addStretch()
        title_bar.addWidget(self.ignore_saved_button)
        bar.addStretch()
        self.select_all = button("Select all", lambda: self.select_candidates(True))
        self.select_none = button("Select none", lambda: self.select_candidates(False))
        bar.addWidget(self.select_all)
        bar.addWidget(self.select_none)
        box.addLayout(bar)
        self.table = CandidateTable(0, 6)
        self.table.setHorizontalHeaderLabels(["Use", "Sensitive value", "Type", "Replacement (editable)", "Occurrence", "Why suggested"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setToolTip("Shift-click selects a range; Ctrl-click adds or removes rows. Use the marking buttons or toggle a selected checkbox to apply to the group.")
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(3, 260)
        self.table.setColumnWidth(0, 42)
        self.table.setColumnWidth(2, 133)
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(5, 190)
        self.table.setMinimumHeight(115)
        self.candidate_filters = ColumnFilters(self.table)
        self.selection_scope = QComboBox()
        self.selection_scope.addItems(['Ask each time', 'All same values', 'Just selected occurrences'])
        self.selection_scope.setToolTip('Choose scope once to avoid repeated prompts. Insensitive occurrences remain in exported work.')
        selection_bar = QHBoxLayout()
        selection_bar.addWidget(label('Scope'))
        selection_bar.addWidget(self.selection_scope)
        self.review_type = QComboBox(); self.review_type.addItems(['All types', *KINDS])
        self.review_type.currentTextChanged.connect(lambda v: self.candidate_filters.set_values(2, None if v == 'All types' else {v}))
        selection_bar.addWidget(self.review_type)
        selection_bar.addWidget(button('Clear filters', self.candidate_filters.clear))
        selection_bar.addWidget(button('Expand review', lambda: self.workspace_splitter.setSizes([100, 600])))
        box.addLayout(selection_bar)
        self.table.itemChanged.connect(self.candidate_changed)
        self.table.itemSelectionChanged.connect(self.focus_candidate)
        self.table.itemSelectionChanged.connect(self.update_selection_actions)
        self.update_selection_actions()
        box.addWidget(self.table)
        self.review_widget = review
        vertical.addWidget(review)
        editors.handle(1).setToolTip("Drag left or right to resize Input and Work Product.")
        editors.handle(1).setCursor(Qt.CursorShape.SplitHCursor)
        vertical.handle(1).setToolTip("Drag up or down to resize the editors and suggested substitutions.")
        vertical.handle(1).setCursor(Qt.CursorShape.SplitVCursor)
        vertical.setSizes([330, 220])
        layout.addWidget(vertical, 1)
        self.reviewed = QCheckBox("I reviewed the full input and selected values, including anything detection missed.")
        layout.addWidget(self.reviewed)
        self.reviewed.toggled.connect(self.update_actions)
        footer = QHBoxLayout()
        self.generate_button = button("Replace selected values", self.generate, True)
        self.copy_button = button("Copy work product", self.copy_output)
        self.export_button = button("Export work product…", self.export_output)
        footer.addWidget(self.generate_button)
        footer.addStretch()
        footer.addWidget(self.copy_button)
        footer.addWidget(self.export_button)
        layout.addLayout(footer)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.update_actions()

    def make_vault_page(self):
        layout = self.page("Your conversion vault", "Exact originals and their substitutes. Older replacement spellings remain restorable when you edit a substitute.")
        self.vault_search = QLineEdit()
        self.vault_search.setPlaceholderText("Filter originals, replacements or types…")
        self.vault_search.textChanged.connect(self.refresh_vault)
        layout.addWidget(self.vault_search)
        filters = QHBoxLayout()
        self.vault_type = QComboBox(); self.vault_type.addItems(['All types', *KINDS])
        self.vault_type.currentTextChanged.connect(lambda v: self.vault_filters.set_values(2, None if v == 'All types' else {v}))
        filters.addWidget(self.vault_type)
        filters.addWidget(button('Select visible rows', self.select_visible_vault))
        filters.addWidget(button('Clear filters', lambda: self.vault_filters.clear()))
        filters.addWidget(label('Click headers to sort · Right-click to filter', 'muted'))
        layout.addLayout(filters)
        self.vault_table = QTableWidget(0, 5)
        self.vault_table.setHorizontalHeaderLabels(["Sensitive value", "Current replacement", "Type", "Older aliases", "Created"])
        self.vault_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.vault_table.setColumnWidth(0, 230)
        self.vault_table.setColumnWidth(1, 250)
        self.vault_table.setSortingEnabled(True)
        self.vault_filters = ColumnFilters(self.vault_table)
        self.vault_table.verticalHeader().hide()
        self.vault_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vault_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vault_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for shortcut, callback in [('Ctrl+C', self.copy_mappings), ('Ctrl+V', self.paste_mappings)]:
            action = QAction(self.vault_table); action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(callback); self.vault_table.addAction(action)
        self.vault_table.doubleClicked.connect(self.edit_mapping)
        layout.addWidget(self.vault_table, 1)
        detail = QFormLayout()
        self.lookup_original = QLineEdit()
        self.lookup_replacement = QLineEdit()
        self.lookup_original.setReadOnly(True)
        self.lookup_replacement.setReadOnly(True)
        detail.addRow("Selected original", self.lookup_original)
        detail.addRow("Selected replacement", self.lookup_replacement)
        layout.addLayout(detail)
        self.vault_table.itemSelectionChanged.connect(self.lookup_detail)
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("Edit selected value…", self.edit_mapping))
        delete = button("Delete selected…", self.delete_selected)
        delete.setObjectName("danger")
        toolbar.addWidget(button('Copy rows', self.copy_mappings))
        toolbar.addWidget(button('Paste rows', self.paste_mappings))
        toolbar.addWidget(delete)
        toolbar.addWidget(button('Batch update…', self.bulk_update))
        toolbar.addStretch()
        flush = button("Flush all mappings…", self.flush)
        flush.setObjectName("danger")
        toolbar.addWidget(flush)
        layout.addLayout(toolbar)
        batch = QHBoxLayout()
        batch.addWidget(button('Obfuscate selected in input', lambda: self.transform_selected(False)))
        batch.addWidget(button('Restore selected in input', lambda: self.transform_selected(True)))
        layout.addLayout(batch)
        layout.addWidget(label("Deleting a mapping also deletes its old aliases. Work that uses those replacements will no longer restore unless you have an encrypted backup. Sensitive originals may remain in detailed audit history until separately purged.", "notice", True))

    def make_audit_page(self):
        layout = self.page("Audit activity", "Encrypted local records of conversions and vault changes. Records include user, UTC time, touched values and exact before/after changes. They are sensitive.")
        self.audit_table = QTableWidget(0, 5)
        self.audit_table.setHorizontalHeaderLabels(["Time (UTC)", "User", "Database", "Action", "Details"])
        self.audit_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.audit_table.setColumnWidth(0, 200)
        self.audit_table.setColumnWidth(1, 170)
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.audit_table.verticalHeader().hide()
        self.audit_table.itemDoubleClicked.connect(self.audit_detail)
        layout.addWidget(self.audit_table, 1)
        layout.addWidget(button("Export activity as JSON…", self.export_audit))
        layout.addWidget(button("Purge this database history…", self.purge_history))
        layout.addWidget(label("This is an operational history, not a certified or externally tamper-evident audit system. Exact restoration requires unchanged substitutes and the matching vault.", "notice", True))

    def make_account_page(self):
        layout = self.page("Account & security", "A local account. An encrypted vault. You control both.")
        self.age_label = label("", "security", True)
        layout.addWidget(self.age_label)
        self.reminder = QCheckBox("Show an optional reminder at sign-in after 60 days without a password change")
        self.reminder.setChecked(self.vault.data.get("remind", True))
        self.reminder.toggled.connect(self.save_reminder)
        layout.addWidget(self.reminder)
        layout.addWidget(button("Change password…", self.change_password))
        layout.addWidget(button("Export password-protected database…", self.backup))
        layout.addWidget(button("Open exported database in a new tab…", self.import_database))
        layout.addWidget(label("Vault location\n" + str(self.vault.path), "security", True))
        layout.addWidget(label("Redactor makes no network requests. Files are read locally. Workspaces are not saved automatically. Your session locks after 15 minutes without keyboard or mouse activity. Text copied by Redactor is cleared from the current clipboard after 60 seconds or when locking, if it is still there.", "security", True))
        layout.addWidget(label("Export archives use the separate password you set at export. Older raw backups use their original account password. Changing the local account password re-encrypts all local database tabs, but does not re-encrypt existing exports. Clipboard history, OS paging, screen capture, malware and other logged-in applications are outside Redactor’s protection.", "security", True))
        license_text = QLabel('GPL version 3 or later — free software to use, study, modify and redistribute under its terms; no warranty.<br><a style="color: #174a36" href="https://www.gnu.org/licenses/gpl-3.0.en.html">GNU General Public License homepage</a> (copy to your browser; Redactor does not open network links).')
        license_text.setWordWrap(True); license_text.setOpenExternalLinks(False)
        license_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        license_text.linkActivated.connect(lambda _: QMessageBox.information(self, 'License homepage', 'https://www.gnu.org/licenses/gpl-3.0.en.html\nCopy this address to your browser if desired. Redactor has not contacted it.'))
        layout.addWidget(license_text)
        layout.addStretch()
        self.update_age()

    def make_menu(self):
        menu = self.menuBar().addMenu("&File")
        for name, shortcut, callback in [("&Import…", "Ctrl+O", self.import_document), ("&Export…", "Ctrl+S", self.export_output), ("&Lock", "Ctrl+L", self.lock), ("E&xit", "Ctrl+Q", self.close)]:
            action = QAction(name, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
        menu = self.menuBar().addMenu("&Review")
        menu.addAction("Review possible database matches", self.review_database_matches)
        for name, shortcut, callback in [("&Scan input", "Ctrl+R", self.scan), ("&Mark selection sensitive", "Ctrl+M", self.mark_selection)]:
            action = QAction(name, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
        help_menu = self.menuBar().addMenu("&Help")
        guide = help_menu.addAction("User Guide", self.user_guide)
        guide.setShortcut(QKeySequence("F1"))
        help_menu.addAction("Supported formats & limits", self.format_help)
        help_menu.addAction("Error Guide & recovery", lambda: document(self, "Error-Guide.md"))
        help_menu.addAction("Portable, forensic & CLI guide", lambda: document(self, "Portable-Forensics-CLI.md"))
        help_menu.addAction("Practice examples", self.practice_examples)
        help_menu.addAction("License & source code", self.source_information)

    def practice_examples(self):
        from importlib.resources import files
        root = files("redactor").joinpath("resources/examples")
        choices = ["Practice workbook (instructions)"] + sorted(p.name for p in root.iterdir() if p.name.endswith((".txt", ".json")))
        selected, ok = QInputDialog.getItem(self, "Synthetic practice examples", "Use a separate Training account to keep practice mappings apart from real work.\nChoose a workbook or sample:", choices, 0, False)
        if not ok: return
        if selected == choices[0]:
            dialog = QDialog(self)
            dialog.setWindowTitle("Redactor — Practice workbook")
            dialog.resize(900, 720)
            layout = QVBoxLayout(dialog)
            viewer = QTextBrowser()
            viewer.setOpenExternalLinks(False)
            viewer.setMarkdown(root.joinpath("Practice-Workbook.md").read_text(encoding="utf-8"))
            layout.addWidget(viewer)
            layout.addWidget(button("Close", dialog.accept))
            dialog.exec()
            return
        if self.source.toPlainText() and not confirm(self, "Load practice example?", "This replaces the current workspace input and preview. Saved mappings remain. Continue?"): return
        self.pages.setCurrentIndex(0)
        self.nav_group.button(0).setChecked(True)
        self.redact_button.setChecked(True)
        self.switch_mode("redact")
        self.input_path = None
        self.source.setPlainText(root.joinpath(selected).read_text(encoding="utf-8"))
        self.scan()

    def source_information(self):
        QMessageBox.information(self, "License & source code", "Redactor 0.2.0 is free software under GPL version 3 or later, without warranty. You may study, modify and redistribute it under the license terms.\n\nNative packages include source/Redactor-0.2.0-source.zip beside the application (on macOS, inside Contents/Resources). It contains application code, tests, the User Guide and build scripts. See LICENSE and SOURCE-DISTRIBUTION.md in the package.\n\nFrom a source checkout, run python scripts/package_source.py to create an updated source package. Third-party libraries retain their own licenses and notices.")

    def user_guide(self):
        from importlib.resources import files
        dialog = QDialog(self)
        dialog.setWindowTitle("Redactor — User Guide")
        dialog.resize(920, 760)
        layout = QVBoxLayout(dialog)
        viewer = QTextBrowser()
        viewer.setOpenExternalLinks(False)
        viewer.setOpenLinks(False)
        viewer.setMarkdown(files("redactor").joinpath("resources/User-Guide.md").read_text(encoding="utf-8"))
        layout.addWidget(viewer)
        layout.addWidget(button("Close", dialog.accept))
        dialog.exec()

    def show_page(self, index):
        self.nav_group.button(index).setChecked(True)
        self.pages.setCurrentIndex(index)
        if index == 1: self.refresh_vault()
        if index == 2: self.refresh_audit()
        if index == 3: self.update_age()

    def update_age(self):
        self.age_label.setText(f"Signed in as {self.vault.data['username']}\nLast password change: {self.vault.password_age} days ago. Password changes are optional.")

    def switch_mode(self, mode):
        if mode == self.mode: return
        self.mode = mode
        self.invalidate()
        self.candidates = []
        self.fill_candidates()
        self.review_widget.setVisible(mode == "redact")
        self.scan_button.setVisible(mode == "redact")
        self.mark_button.setVisible(mode == "redact")
        self.generate_button.setText("Restore exact replacements" if mode == "restore" else "Replace selected values")
        self.reviewed.setText("I understand restored output contains sensitive originals and is for local reporting." if mode == "restore" else "I reviewed the full input and selected values, including anything detection missed.")
        self.notice.setText("Paste or import the completed AI work into INPUT. Only exact, case-sensitive saved replacements will be restored. Review anything the AI reworded." if mode == "restore" else "Scan the input, review suggestions, and mark any missed values before generating work product.")
        self.source.setExtraSelections([])

    def invalidate(self):
        self.output.clear()
        self.has_output = False
        self.reviewed.setChecked(False)
        self.update_actions()

    def source_changed(self):
        self.invalidate()
        self.candidates = []
        self.fill_candidates()

    def update_actions(self):
        self.generate_button.setEnabled(not self.busy and self.reviewed.isChecked() and bool(self.source.toPlainText().strip()))
        self.copy_button.setEnabled(not self.busy and self.has_output)
        self.export_button.setEnabled(not self.busy and self.has_output)

    def set_busy(self, busy):
        self.busy = busy
        self.centralWidget().setEnabled(not busy)
        self.menuBar().setEnabled(not busy)
        self.progress.setVisible(busy)
        self.update_actions()

    def run_worker(self, function, done):
        self.set_busy(True)
        worker = Worker(function)
        def success(result):
            self.set_busy(False)
            try: done(result)
            except Exception as exc: error(self, exc)
        def failure(message):
            self.set_busy(False)
            error(self, message)
        worker.signals.success.connect(success)
        worker.signals.failure.connect(failure)
        self.worker = worker
        QThreadPool.globalInstance().start(worker)

    def import_document(self):
        if self.busy: return
        path, _ = QFileDialog.getOpenFileName(self, "Import local file", "", "Supported files (" + " ".join("*" + x for x in sorted(INPUT_EXTENSIONS)) + ");;All files (*)")
        if not path: return
        if self.source.toPlainText() and not confirm(self, "Replace workspace input?", "Importing replaces the current input and preview. Existing saved mappings remain in your vault. Continue?"): return
        self.statusBar().showMessage("Reading locally… OCR may take a moment.")
        def done(result):
            self.vault.commit("document_import", source=str(path), input_text=result.text, input_sha256=hashlib.sha256(result.text.encode()).hexdigest())
            self.input_path = Path(path)
            self.denied_similar.clear()
            self.source.setPlainText(result.text)
            self.notice.setText(result.note)
            self.statusBar().showMessage(f"Imported {len(result.text):,} characters. Review the extracted text.")
            if self.mode == "redact": self.scan()
        self.run_worker(lambda: read_file(Path(path)), done)

    def scan(self):
        if self.busy or self.mode != "redact": return
        text = self.source.toPlainText()
        if not text.strip(): return
        if len(text) > MAX_TEXT:
            error(self, "Input exceeds one million characters. Split it into smaller parts.")
            return
        self.invalidate()
        mappings = copy.deepcopy(self.vault.data["mappings"])
        denied = self.denied_similar.copy()
        self.statusBar().showMessage("Scanning offline for candidates…")
        def finish(result):
            self.candidates = result
            self.fill_candidates()
            if not result:
                self.notice.setText('No sensitive information was identified. The imported text remains editable. Select any value and choose Mark selection sensitive, or edit the input and scan again.')
            saved = sum(c.reason == "Saved mapping" for c in result)
            self.statusBar().showMessage(f"{len(result)} distinct candidate values; {saved} saved replacements suggested. Keep them or select rows and choose Ignore saved suggestion.")
        def done(result):
            candidates, similar = result
            revised = self.review_similar_values(text, similar)
            if revised != text:
                self.source.setPlainText(revised)
                self.run_worker(lambda: detect(revised, mappings), finish)
            else:
                finish(candidates)
        self.run_worker(lambda: (detect(text, mappings), find_similar_values(text, mappings, denied)), done)

    def review_database_matches(self):
        self.denied_similar.clear()
        self.scan()

    def resolve_similar_value(self, match):
        box = QMessageBox(self)
        box.setWindowTitle("Possible match to a saved original")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(f"Imported value:\n{match.imported}\n\nSaved original:\n{match.original}\n\nSaved replacement:\n{match.replacement}")
        box.setInformativeText(match.reason + ".\n\nConfirm match replaces every exact instance of the imported spelling in the working input with the saved original. Restoration will return that saved spelling. Edit lets you correct the value yourself. Deny leaves it unchanged and separate. The source file is never modified.")
        accept = box.addButton("Confirm match", QMessageBox.ButtonRole.AcceptRole)
        edit = box.addButton("Edit value…", QMessageBox.ButtonRole.ActionRole)
        deny = box.addButton("Deny match", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Stop review", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() == accept: return "confirm", match.original
        if box.clickedButton() == deny: return "deny", None
        if box.clickedButton() == edit:
            value, ok = QInputDialog.getText(self, "Correct imported value", "Replacement text in the working input (the original file is unchanged):", text=match.imported)
            if ok and value.strip(): return "edit", value
        return "stop", None

    def review_similar_values(self, text, matches):
        working = text
        previous = copy.deepcopy(self.vault.data)
        denied = self.denied_similar.copy()
        changed = False
        try:
            for match in matches:
                if not literal_pattern([match.imported]).search(working): continue
                action, replacement = self.resolve_similar_value(match)
                if action == "stop": break
                mapping_ids = [m["id"] for m in self.vault.data["mappings"] if m["original"] == match.original]
                if action == "deny":
                    denied.add((match.imported, match.original))
                    self.vault.audit("similar_match_denied", mapping_ids=mapping_ids, imported=match.imported, original=match.original)
                else:
                    working, counts = replace_exact(working, {match.imported: replacement})
                    self.vault.audit("similar_match_confirmed" if action == "confirm" else "similar_value_edited",
                                     mapping_ids=mapping_ids, occurrences=sum(counts.values()), before=match.imported, after=replacement)
                changed = True
            if changed: self.vault.save()
            self.denied_similar = denied
            if len(matches) == 50:
                self.notice.setText("Reviewed a batch of up to 50 possible database matches. Scan again to review additional candidates. Only explicitly confirmed/edited text was changed.")
            return working
        except Exception as exc:
            self.vault.data = previous
            error(self, exc)
            return text

    def fill_candidates(self):
        text = self.source.toPlainText()
        self.row_occurrences = sorted(
            [(index, start, end) for index, c in enumerate(self.candidates)
             for start, end in candidate_occurrences(text, c)], key=lambda item: (item[1], -item[2]))
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.row_occurrences))
        for row, (index, start, end) in enumerate(self.row_occurrences):
            c = self.candidates[index]
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Checked if occurrence_selected(c, start) else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            location = f"Line {text.count(chr(10), 0, start) + 1}, column {start - text.rfind(chr(10), 0, start)}"
            for col, value in enumerate([c.original, c.kind, c.replacement, location, c.reason], 1):
                item = QTableWidgetItem(value)
                item.setToolTip(text[max(0, start-50):min(len(text), end+50)] if col == 4 else value)
                if col != 3: item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        self.candidate_filters.apply()
        self.review_title.setText(f"SUGGESTED SUBSTITUTIONS  ·  {len(self.candidates)} values / {len(self.row_occurrences)} occurrences")
        self.update_selection_actions()
        self.highlight()

    def candidate_changed(self, item):
        if item.row() >= len(self.row_occurrences): return
        if item.column() == 0:
            rows = {index.row() for index in self.table.selectionModel().selectedRows()}
            if item.row() not in rows:
                rows = {item.row()}
            self.set_candidate_rows(rows, item.checkState() == Qt.CheckState.Checked)
            return
        index, _, _ = self.row_occurrences[item.row()]
        c = self.candidates[index]
        c.replacement = self.table.item(item.row(), 3).text()
        self.table.blockSignals(True)
        for row, (other, _, _) in enumerate(self.row_occurrences):
            if other == index: self.table.item(row, 3).setText(c.replacement)
        self.table.blockSignals(False)
        self.invalidate()
        self.highlight()

    def select_candidates(self, selected):
        self.set_candidate_rows([r for r in range(len(self.row_occurrences)) if not self.table.isRowHidden(r)], selected)

    def update_selection_actions(self):
        rows = self.table.selectionModel().selectedRows()
        selected = bool(rows)
        self.mark_rows_sensitive.setEnabled(selected)
        self.mark_rows_insensitive.setEnabled(selected)
        self.ignore_saved_button.setEnabled(any(
            index.row() < len(getattr(self, "row_occurrences", [])) and
            self.candidates[self.row_occurrences[index.row()][0]].reason == "Saved mapping" for index in rows))

    def ignore_saved_suggestion(self):
        indexes = {self.row_occurrences[row.row()][0] for row in self.table.selectionModel().selectedRows()}
        indexes = {index for index in indexes if self.candidates[index].reason == "Saved mapping"}
        if not indexes: return
        try:
            forbidden = [self.source.toPlainText()] + [c.original for c in self.candidates] + [c.replacement for c in self.candidates]
            forbidden += [value for mapping in self.vault.data["mappings"]
                          for value in [mapping["original"], mapping["replacement"], *mapping.get("aliases", [])]]
            proposed = {}
            for index in indexes:
                c = self.candidates[index]
                proposed[index] = suggest(c.kind, forbidden, c.original)
                forbidden.append(proposed[index])
            for index, replacement in proposed.items():
                self.candidates[index].replacement = replacement
                self.candidates[index].reason = "Saved suggestion ignored; new substitute"
            self.table.blockSignals(True)
            for row, (index, _, _) in enumerate(self.row_occurrences):
                if index in indexes:
                    self.table.item(row, 3).setText(self.candidates[index].replacement)
                    self.table.item(row, 5).setText(self.candidates[index].reason)
            self.table.blockSignals(False)
            self.invalidate()
            self.update_selection_actions()
            self.statusBar().showMessage("Fresh replacements suggested for these values. Generate to save; older aliases remain restorable.")
        except Exception as exc:
            self.table.blockSignals(False)
            error(self, exc)

    def mark_selected_rows(self, sensitive):
        rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        self.set_candidate_rows(rows, sensitive)

    def set_candidate_rows(self, rows, selected):
        rows = [row for row in rows if 0 <= row < len(self.row_occurrences)]
        if not rows: return
        # Undo Qt's tentative checkbox change until the user chooses a scope.
        self.sync_occurrence_checks()
        scope = self.ask_selection_scope(rows, selected)
        if scope is None: return
        if scope == "all":
            indexes = {self.row_occurrences[row][0] for row in rows}
            rows = [row for row, (index, _, _) in enumerate(self.row_occurrences) if index in indexes]
        starts = {}
        for row in rows:
            index, start, _ = self.row_occurrences[row]
            starts.setdefault(index, set()).add(start)
        for index, affected in starts.items():
            c = self.candidates[index]
            included = {start for other, start, _ in self.row_occurrences
                        if other == index and occurrence_selected(c, start)}
            c.included_starts = included | affected if selected else included - affected
            c.selected = bool(c.included_starts)
        self.sync_occurrence_checks()
        self.invalidate()
        self.highlight()

    def ask_selection_scope(self, rows, selected):
        if self.selection_scope.currentIndex() == 1: return 'all'
        if self.selection_scope.currentIndex() == 2: return 'selected'
        box = QMessageBox(self)
        box.setWindowTitle("Apply selection change")
        box.setTextFormat(Qt.TextFormat.PlainText)
        action = "sensitive" if selected else "insensitive"
        indexes = {self.row_occurrences[row][0] for row in rows}
        total = sum(1 for index, _, _ in self.row_occurrences if index in indexes)
        box.setText(f"Mark {len(rows)} selected occurrence(s) {action}?")
        box.setInformativeText(f"Apply this to all {total} occurrences of the same exact values, or only the selected occurrences? Marking an occurrence insensitive leaves its original text in the work product.")
        all_button = box.addButton("All same values", QMessageBox.ButtonRole.AcceptRole)
        selected_button = box.addButton("Just selected", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(all_button)
        box.exec()
        if box.clickedButton() == all_button: return "all"
        if box.clickedButton() == selected_button: return "selected"
        return None

    def sync_occurrence_checks(self):
        self.table.blockSignals(True)
        try:
            for row, (index, start, _) in enumerate(self.row_occurrences):
                self.table.item(row, 0).setCheckState(Qt.CheckState.Checked if occurrence_selected(self.candidates[index], start) else Qt.CheckState.Unchecked)
        finally:
            self.table.blockSignals(False)

    def highlight(self):
        text = self.source.toPlainText()
        spans = sorted({(start, end) for c in self.candidates for start, end in candidate_occurrences(text, c)
                        if occurrence_selected(c, start)})
        selections = []
        if spans:
            # Qt cursor positions are UTF-16 offsets, Python string indexes are code points.
            offsets = [0]
            for char in text: offsets.append(offsets[-1] + (2 if ord(char) > 0xffff else 1))
            for i, (start, end) in enumerate(spans):
                if i >= 2500: break
                selection = QTextEdit.ExtraSelection()
                cursor = self.source.textCursor()
                cursor.setPosition(offsets[start])
                cursor.setPosition(offsets[end], QTextCursor.MoveMode.KeepAnchor)
                selection.cursor = cursor
                selection.format.setBackground(QColor("#ffedb1"))
                selection.format.setForeground(QColor("#533e12"))
                selections.append(selection)
        self.source.setExtraSelections(selections)

    def focus_candidate(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(getattr(self, "row_occurrences", [])): return
        _, start, end = self.row_occurrences[row]
        text = self.source.toPlainText()
        cursor = self.source.textCursor()
        cursor.setPosition(len(text[:start].encode("utf-16-le")) // 2)
        cursor.setPosition(len(text[:end].encode("utf-16-le")) // 2, QTextCursor.MoveMode.KeepAnchor)
        self.source.setTextCursor(cursor)
        self.source.ensureCursorVisible()

    def mark_selection(self):
        if self.busy or self.mode != "redact": return
        original = self.source.textCursor().selectedText().replace("\u2029", "\n")
        if not original.strip():
            error(self, "Highlight a sensitive value in the INPUT field first.")
            return
        try:
            replacement = suggest("Custom", [self.source.toPlainText(), *[c.replacement for c in self.candidates]], original)
            dialog = MappingDialog(self, original, "Custom", replacement)
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            original = dialog.original.text()
            if not original or original not in self.source.toPlainText():
                raise ValueError("The sensitive value must appear exactly in the current input.")
            self.candidates = [c for c in self.candidates if c.original != original]
            self.candidates.append(Candidate(original, dialog.kind.currentText(), dialog.replacement.text(), "Marked by you"))
            self.invalidate()
            self.fill_candidates()
        except Exception as exc: error(self, exc)

    def generate(self):
        if self.busy or not self.reviewed.isChecked(): return
        text = self.source.toPlainText()
        if len(text) > MAX_TEXT:
            error(self, "Input exceeds one million characters.")
            return
        previous = copy.deepcopy(self.vault.data)
        try:
            if self.mode == "redact":
                mappings, conversions = prepare_mappings(self.candidates, self.vault.data["mappings"], text, strict=True)
                result, counts = replace_candidates(text, self.candidates, conversions)
                existing_ids = {m["id"] for m in previous["mappings"]}
                mappings = [m for m in mappings if m["id"] in existing_ids or m["original"] in counts]
                self.vault.data["mappings"] = mappings
                ids = [m["id"] for m in mappings if m["original"] in counts]
                audit_text(self.vault, "redacted", text, result, occurrences=sum(counts.values()), mapping_ids=ids)
                message = f"Replaced {sum(counts.values())} occurrences using {len(counts)} mappings. Review the work product before sharing."
                excluded = sum(not occurrence_selected(self.candidates[index], start) for index, start, _ in self.row_occurrences)
                if excluded: message += f" {excluded} excluded occurrence(s) were intentionally left unchanged."
            else:
                result, counts, unknown = restore(text, self.vault.data["mappings"])
                ids = [m["id"] for m in self.vault.data["mappings"] if any(a in counts for a in [m["replacement"], *m.get("aliases", [])])]
                audit_text(self.vault, "restored", text, result, occurrences=sum(counts.values()), mapping_ids=ids, unresolved_markers=len(unknown))
                message = f"Restored {sum(counts.values())} exact occurrences. This output contains sensitive originals."
                if unknown: message += f" {len(unknown)} unresolved or changed markers remain; inspect them manually."
                if not counts: message += " No saved replacements matched. Check the input and account."
            self.output.setPlainText(result)
            self.has_output = True
            self.notice.setText(message)
            self.statusBar().showMessage(message)
            self.update_actions()
        except Exception as exc:
            self.vault.data = previous
            error(self, exc)

    def copy_output(self):
        if not self.has_output or self.busy: return
        if self.mode == "restore" and not confirm(self, "Copy sensitive output?", "The restored work product contains sensitive originals. Copy it to the system clipboard for local use?"): return
        try:
            self.vault.commit("copied_output", mode=self.mode, output_text=self.output.toPlainText())
            text = self.output.toPlainText()
            QApplication.clipboard().setText(text)
            self.owned_clipboard = text
            self.clipboard_timer.start(60000)
            self.statusBar().showMessage("Copied. Current clipboard will be cleared in 60 seconds if unchanged. OS clipboard history is separate.")
        except Exception as exc: error(self, exc)

    def clear_clipboard(self):
        if self.owned_clipboard is not None and QApplication.clipboard().text() == self.owned_clipboard:
            QApplication.clipboard().clear()
        self.owned_clipboard = None

    def export_output(self):
        if not self.has_output or self.busy: return
        warning = "Export creates a new content-only file. Original layout, graphics, formulas and metadata are not retained."
        if self.mode == "restore": warning += "\n\nThis file will contain SENSITIVE ORIGINALS. Keep it local and protected."
        else: warning += "\n\nConfirm you have inspected the work product for missed sensitive data."
        if not confirm(self, "Export reviewed work product?", warning): return
        default_ext = self.input_path.suffix.lower() if self.input_path and self.input_path.suffix.lower() in OUTPUT_EXTENSIONS else ".txt"
        formats = [default_ext] + sorted(OUTPUT_EXTENSIONS - {default_ext})
        filters = ";;".join(f"{ext[1:].upper()} file (*{ext})" for ext in formats)
        name, selected = QFileDialog.getSaveFileName(self, "Export work product", str(directory("exports") / (("restored-work" if self.mode == "restore" else "obfuscated-work") + default_ext)), filters)
        if not name: return
        try: path = output_path(name)
        except Exception as exc:
            error(self, exc); return
        if not path.suffix: path = path.with_suffix(selected.split("(*")[-1].rstrip(")"))
        if self.input_path and path.resolve() == self.input_path.resolve():
            error(self, "Choose a new filename so the source document is preserved.")
            return
        # Write to a sibling temporary file then atomically publish a completed artifact.
        import tempfile
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".redactor-export-", suffix=path.suffix, dir=path.parent)
            os.close(fd)
            export_file(Path(temporary), self.output.toPlainText())
            self.vault.commit("export_prepared", mode=self.mode, format=path.suffix.lower(), destination=str(path), output_text=self.output.toPlainText())
            atomic_replace(temporary, path)
            self.statusBar().showMessage("Exported: " + str(path))
        except Exception as exc: error(self, exc)
        finally:
            if temporary and Path(temporary).exists(): Path(temporary).unlink()

    def clear_workspace(self):
        if self.busy: return
        if self.source.toPlainText() and not confirm(self, "Clear workspace?", "Clear the current input and output? Export work you want to keep first. Saved mappings remain in the vault."): return
        self.source.clear()
        self.denied_similar.clear()
        self.source.document().clearUndoRedoStacks()
        self.output.clear()
        self.input_path = None
        self.clear_clipboard()

    def refresh_vault(self):
        query = self.vault_search.text().casefold()
        self.visible_mappings = [m for m in self.vault.data["mappings"] if query in " ".join([m["original"], m["replacement"], m["kind"], *m.get("aliases", [])]).casefold()]
        self.vault_table.setSortingEnabled(False)
        self.vault_table.setRowCount(len(self.visible_mappings))
        for row, m in enumerate(self.visible_mappings):
            for col, value in enumerate([m["original"], m["replacement"], m["kind"], "\n".join(m.get("aliases", [])), m["created"][:10]]):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setData(Qt.ItemDataRole.UserRole, m["id"])
                self.vault_table.setItem(row, col, item)
        self.vault_table.setSortingEnabled(True)
        self.vault_filters.apply()
        self.lookup_detail()

    def lookup_detail(self):
        row = self.vault_table.currentRow()
        if 0 <= row < len(getattr(self, "visible_mappings", [])):
            mapping = self.mapping_at(row)
            identity = (getattr(self.vault, 'database_id', 'main'), mapping['id'])
            if getattr(self, '_last_lookup', None) != identity:
                try: self.vault.commit('lookup', mapping_ids=[mapping['id']])
                except Exception as exc: error(self, exc)
                self._last_lookup = identity
            self.lookup_original.setText(mapping["original"])
            self.lookup_replacement.setText(mapping["replacement"])
            self.lookup_original.setCursorPosition(0)
            self.lookup_replacement.setCursorPosition(0)
        else:
            self.lookup_original.clear()
            self.lookup_replacement.clear()

    def edit_mapping(self):
        row = self.vault_table.currentRow()
        if row < 0: return
        original_mapping = self.mapping_at(row)
        dialog = MappingDialog(self, original_mapping["original"], original_mapping["kind"], original_mapping["replacement"])
        dialog.explanation.setText("Changing the original changes what ALL current and older aliases restore to. Changing only the replacement retains older aliases for previous work.")
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        if dialog.original.text() != original_mapping["original"] and not confirm(self, "Change restoration target?", "All saved aliases for this value will now restore to the new original. This changes historical restoration results. Continue?"): return
        old = copy.deepcopy(self.vault.data)
        try:
            if dialog.replacement.text() != original_mapping["replacement"]:
                original_mapping["aliases"] = list(dict.fromkeys([*original_mapping.get("aliases", []), original_mapping["replacement"]]))
                original_mapping["replacement"] = dialog.replacement.text()
                original_mapping["aliases"] = [a for a in original_mapping["aliases"] if a != original_mapping["replacement"]]
            original_mapping["original"] = dialog.original.text()
            original_mapping["kind"] = dialog.kind.currentText()
            validate_mappings(self.vault.data["mappings"], strict=True)
            self.vault.commit("mapping_edited", mapping_ids=[original_mapping["id"]])
            self.invalidate()
            self.candidates = []
            self.fill_candidates()
            self.refresh_vault()
        except Exception as exc:
            self.vault.data = old
            self.refresh_vault()
            error(self, exc)

    def delete_selected(self):
        rows = {index.row() for index in self.vault_table.selectionModel().selectedRows()}
        ids = {self.mapping_at(row)["id"] for row in rows if not self.vault_table.isRowHidden(row)}
        if ids: self.delete_mappings(ids, "DELETE")

    def flush(self):
        ids = {m["id"] for m in self.vault.data["mappings"]}
        if ids: self.delete_mappings(ids, "FLUSH")

    def delete_mappings(self, ids, word):
        text, ok = QInputDialog.getText(self, "Permanent mapping deletion", f"Delete {len(ids)} mappings and all their aliases?\nPrevious work using them will no longer restore without a backup.\nThis does not erase exports, backups or OS storage remnants.\n\nType {word} to confirm:")
        if not ok or text != word: return
        old = copy.deepcopy(self.vault.data)
        try:
            self.vault.data["mappings"] = [m for m in self.vault.data["mappings"] if m["id"] not in ids]
            self.vault.commit("mappings_deleted", mapping_ids=sorted(ids), count=len(ids))
            self.invalidate()
            self.candidates = []
            self.fill_candidates()
            self.refresh_vault()
        except Exception as exc:
            self.vault.data = old
            error(self, exc)

    def purge_history(self):
        text, ok = QInputDialog.getText(self, 'Purge sensitive audit history', 'This permanently removes current and imported history for the active database. It affects audit/retention capabilities; mappings remain. Type PURGE:')
        if not ok or text != 'PURGE': return
        old = copy.deepcopy(self.vault.data)
        try:
            self.vault.data['audit'] = []; self.vault.data.pop('imported_audit', None)
            self.vault.commit('history_purged'); self.refresh_audit()
        except Exception as exc:
            self.vault.data = old; error(self, exc)

    def refresh_audit(self):
        events = self.audit_events = list(reversed(self.vault.data["audit"])) + list(reversed(self.vault.data.get("imported_audit", [])))
        self.audit_table.setRowCount(len(events))
        for row, event in enumerate(events):
            for col, value in enumerate([event["at"], event.get("user", "Legacy / unknown"), event.get("database", {}).get("title", "Legacy / unknown"), event["action"], json.dumps({k: v for k, v in event.items() if k not in {"at", "action"}})]):
                self.audit_table.setItem(row, col, QTableWidgetItem(value))

    def export_audit(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export activity", str(directory("exports") / "redactor-activity.json"), "JSON (*.json)")
        if path and confirm(self, "Export sensitive audit?", "Audit exports contain originals and document text. Keep them protected. Continue?"):
            try: output_path(path).write_text(json.dumps(self.vault.data["audit"], indent=2), encoding="utf-8")
            except Exception as exc: error(self, exc)

    def save_reminder(self, enabled):
        old = self.account_vault.data.get("remind", True)
        try:
            self.account_vault.data["remind"] = enabled
            self.account_vault.commit("reminder_preference_changed", enabled=enabled)
        except Exception as exc:
            self.account_vault.data["remind"] = old
            self.reminder.blockSignals(True)
            self.reminder.setChecked(old)
            self.reminder.blockSignals(False)
            error(self, exc)

    def change_password(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Change password")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        fields = []
        for title in ["Current password", "New password", "Confirm new password"]:
            field = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(title, field)
            fields.append(field)
        layout.addLayout(form)
        layout.addWidget(label("Use at least 12 characters. Older encrypted backups retain their old password.", "notice", True))
        def change():
            try:
                if fields[1].text() != fields[2].text(): raise ValueError("New passwords do not match.")
                self.vault.change_password(fields[0].text(), fields[1].text())
                for f in fields: f.clear()
                self.update_age()
                dialog.accept()
                self.statusBar().showMessage("Password changed. The active vault has been re-encrypted.")
            except Exception as exc: error(dialog, exc)
        layout.addWidget(button("Change password", change, True))
        dialog.exec()

    def format_help(self):
        QMessageBox.information(self, "Formats & exact restoration", "Import: TXT, Markdown, CSV, TSV, JSON, XML, HTML, logs, PDF, DOCX, XLSX, PPTX, RTF, ODT, ODS, ODP, PNG, JPEG, TIFF, BMP, WebP.\n\nExport: text/Markdown, CSV/TSV, PDF, DOCX, XLSX, PPTX, RTF, ODT/ODS/ODP and text rendered as PNG/JPEG/TIFF/BMP/WebP. Multi-page images require TIFF.\n\n" + NOTICE + "\n\nLegacy DOC/XLS/PPT: convert locally to modern Office formats first. Macro-enabled and password-protected Office files are not supported. Embedded image text in Office or mixed-content PDFs is not extracted. Image-only PDF pages and image files use English OCR. OCR is " + ("available." if tesseract_path() else "unavailable; see Error Guide R006 for portable OCR setup.") + "\n\nLimits: 50 MB/file; 1 million extracted characters; 500 PDF pages. Only the first 2,500 matching occurrences are visually highlighted; all are processed.\n\nAsk online AI tools to preserve substitutes exactly, including capitalization and IDs. Reworded, truncated or translated substitutes cannot be restored automatically. Automatic detection is heuristic, including names and organizations. Review all content and context before sharing.")

    def eventFilter(self, obj, event):
        if event.type() in {QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel}:
            self.last_active = time.monotonic()
        return super().eventFilter(obj, event)

    def check_idle(self):
        if not self.busy and time.monotonic() - self.last_active > 900 and QApplication.activeModalWidget() is None:
            self.lock()

    def lock(self):
        if self.busy: return
        self.relock = True
        self.close()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            return
        if not self.relock and self.source.toPlainText() and not confirm(self, "Close Redactor?", "Unsaved workspace text will be cleared. Your saved mappings remain encrypted. Close the app?"):
            event.ignore()
            return
        self.idle_timer.stop()
        self.clipboard_timer.stop()
        self.clear_clipboard()
        QApplication.instance().removeEventFilter(self)
        self.source.clear()
        self.source.document().clearUndoRedoStacks()
        self.output.clear()
        self.candidates.clear()
        self.vault_table.clearContents()
        self.lookup_original.clear()
        self.lookup_replacement.clear()
        self.audit_table.clearContents()
        if hasattr(self, "visible_mappings"): self.visible_mappings.clear()
        self.workspace_states.clear()
        self.denied_similar.clear()
        if hasattr(self, 'audit_events'): self.audit_events.clear()
        for database in self.open_databases[1:]: database.close()
        self.account_vault.close()
        event.accept()


def QTextDocumentFindCaseSensitive():
    from PySide6.QtGui import QTextDocument
    return QTextDocument.FindFlag.FindCaseSensitively


def main():
    configure()
    app = QApplication(sys.argv)
    app.setApplicationName("Redactor")
    app.setOrganizationName("Redactor Local")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    directory = vault_directory()
    # One process prevents lost updates between simultaneously unlocked accounts.
    lock = QLockFile(str(directory.parent / "redactor.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "Redactor is already open", "Use the existing Redactor window. Only one instance can access the vaults at a time.")
        return
    while True:
        login = Login(directory)
        if login.exec() != QDialog.DialogCode.Accepted: break
        window = MainWindow(login.vault)
        login.deleteLater()
        window.show()
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop()
        window.destroyed.connect(loop.quit)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # Capture relock before Qt destroys the widget.
        state = {"relock": False}
        def on_destroyed(*args):
            state["relock"] = window.relock
        window.destroyed.connect(on_destroyed)
        loop.exec()
        if not state["relock"]: break
    lock.unlock()


if __name__ == "__main__":
    main()
