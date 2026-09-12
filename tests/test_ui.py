# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from redactor.app import MainWindow, STYLE
from redactor.vault import Vault


@pytest.fixture
def window(tmp_path, qtbot, qapp, monkeypatch):
    def unexpected_error(parent, message):
        pytest.fail(str(message))
    monkeypatch.setattr("redactor.app.error", unexpected_error)
    qapp.setStyleSheet(STYLE)
    vault = Vault.create(tmp_path, "Test account", "A strong test passphrase")
    window = MainWindow(vault)
    monkeypatch.setattr(window, "ask_selection_scope", lambda rows, selected: "all")
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "relock", True))
    window.show()
    yield window
    # pytest-qt closes/deletes registered widgets before fixture teardown.


def test_review_generate_lookup_restore_and_stale_preview(window, qtbot):
    source = "Jane Smith at IBM uses 10.2.3.4."
    window.source.setPlainText(source)
    assert not window.generate_button.isEnabled()
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert len(window.candidates) >= 3
    window.reviewed.setChecked(True)
    window.generate()
    output = window.output.toPlainText()
    assert "Jane Smith" not in output and "IBM" not in output
    assert window.copy_button.isEnabled()
    window.show_page(1)
    window.vault_search.setText("IBM")
    assert window.vault_table.rowCount() == 1
    replacement = window.vault_table.item(0, 1).text()
    window.vault_search.setText(replacement)
    assert window.vault_table.item(0, 0).text() == "IBM"
    window.switch_mode("restore")
    window.source.setPlainText(output)
    window.reviewed.setChecked(True)
    window.generate()
    assert window.output.toPlainText() == source
    window.source.insertPlainText("changed")
    assert not window.copy_button.isEnabled()
    assert not window.output.toPlainText()


def test_candidate_edit_invalidates_review(window, qtbot):
    window.source.setPlainText("IBM")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    window.reviewed.setChecked(True)
    window.generate()
    window.table.item(0, 3).setText("Wonka Industries R1234ABCD")
    assert not window.has_output and not window.reviewed.isChecked()


def test_unicode_highlight_uses_qt_positions(window, qtbot):
    window.source.setPlainText("😀 Jane Smith")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert any(s.cursor.selectedText() == "Jane Smith" for s in window.source.extraSelections())


def test_no_output_released_if_vault_save_fails(window, qtbot, monkeypatch):
    window.source.setPlainText("IBM")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    def fail(): raise OSError("Disk full")
    errors = []
    monkeypatch.setattr(window.vault, "save", fail)
    monkeypatch.setattr("redactor.app.error", lambda parent, message: errors.append(str(message)))
    window.reviewed.setChecked(True)
    window.generate()
    assert errors and not window.has_output and window.vault.data["mappings"] == []


def test_lock_clears_current_clipboard_and_plaintext(window):
    from PySide6.QtWidgets import QApplication
    window.source.setPlainText("Sensitive input")
    QApplication.clipboard().setText("Sensitive output")
    window.owned_clipboard = "Sensitive output"
    window.lock()
    assert not QApplication.clipboard().text()
    assert not window.vault.data and not window.source.toPlainText()


def test_multiline_manual_value_editor(qtbot):
    from redactor.app import SensitiveValueEditor
    editor = SensitiveValueEditor("Project Silver\nMaple")
    qtbot.addWidget(editor)
    assert editor.text() == "Project Silver\nMaple"


def test_multirow_shift_ctrl_and_bulk_marking(window, qtbot):
    from redactor.engine import Candidate
    window.source.setPlainText("IBM GNMA Jane Smith")
    window.candidates = [Candidate(value, "Custom", replacement, "test") for value, replacement in
                         [("IBM", "XYZ"), ("GNMA", "ACME"), ("Jane Smith", "Leia Orgas")]]
    window.fill_candidates()
    def click(row, modifier=Qt.KeyboardModifier.NoModifier):
        position = window.table.visualItemRect(window.table.item(row, 1)).center()
        qtbot.mouseClick(window.table.viewport(), Qt.MouseButton.LeftButton, modifier, position)
    click(0)
    click(2, Qt.KeyboardModifier.ShiftModifier)
    assert len(window.table.selectionModel().selectedRows()) == 3
    qtbot.mouseClick(window.mark_rows_insensitive, Qt.MouseButton.LeftButton)
    assert all(not c.selected for c in window.candidates)
    assert len(window.table.selectionModel().selectedRows()) == 3
    click(1, Qt.KeyboardModifier.ControlModifier)
    assert {i.row() for i in window.table.selectionModel().selectedRows()} == {0, 2}
    qtbot.mouseClick(window.mark_rows_sensitive, Qt.MouseButton.LeftButton)
    assert [c.selected for c in window.candidates] == [True, False, True]
    window.reviewed.setChecked(True)
    window.generate()
    assert "GNMA" in window.output.toPlainText()
    # Toggling a selected row checkbox affects the highlighted group.
    qtbot.mouseClick(window.table.viewport(), Qt.MouseButton.LeftButton,
                     pos=window.table.visualItemRect(window.table.item(0, 0)).center())
    assert all(not c.selected for c in window.candidates)
    assert not window.has_output and not window.reviewed.isChecked()


def test_inner_panes_resize_independently(window, qtbot):
    # Small CI desktops can pin both panes at their minimum heights.
    # Give this resizing check enough geometry to exercise both directions.
    window.workspace_splitter.setMinimumHeight(700)
    window.resize(1400, 1200)
    qtbot.wait(20)
    window.editor_splitter.setSizes([250, 650])
    qtbot.wait(20)
    left, right = window.editor_splitter.sizes()
    assert right > left
    window.editor_splitter.setSizes([650, 250])
    qtbot.wait(20)
    left, right = window.editor_splitter.sizes()
    assert left > right
    before = window.workspace_splitter.sizes()
    window.workspace_splitter.setSizes([120, 600])
    qtbot.wait(20)
    assert window.workspace_splitter.sizes() != before
    assert window.editor_splitter.handleWidth() == 10


def test_repeated_values_share_replacement_and_saved_mapping(window, qtbot):
    from redactor.engine import restore
    text = "IBM; IBM; IBM."
    window.source.setPlainText(text)
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert len(window.candidates) == 1
    replacement = window.candidates[0].replacement
    window.reviewed.setChecked(True)
    window.generate()
    assert window.output.toPlainText().count(replacement) == 3
    assert restore(window.output.toPlainText(), window.vault.data["mappings"])[0] == text
    window.source.setPlainText("IBM appears again. IBM.")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert next(c for c in window.candidates if c.original == "IBM").replacement == replacement


def test_selected_occurrence_only_and_cancel(window, qtbot, monkeypatch):
    from redactor.engine import restore
    text = "😀 IBM / IBM / IBM"
    window.source.setPlainText(text)
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert window.table.rowCount() == 3
    window.table.selectRow(1)
    assert window.source.textCursor().selectionStart() == 9
    monkeypatch.setattr(window, "ask_selection_scope", lambda rows, selected: "selected")
    window.mark_selected_rows(False)
    assert [window.table.item(i, 0).checkState() == Qt.CheckState.Checked for i in range(3)] == [True, False, True]
    window.reviewed.setChecked(True)
    window.generate()
    replacement = window.candidates[0].replacement
    assert window.output.toPlainText() == f"😀 {replacement} / IBM / {replacement}"
    assert restore(window.output.toPlainText(), window.vault.data["mappings"])[0] == text
    previous = window.output.toPlainText()
    monkeypatch.setattr(window, "ask_selection_scope", lambda rows, selected: None)
    window.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    assert window.table.item(0, 0).checkState() == Qt.CheckState.Checked
    assert window.output.toPlainText() == previous and window.reviewed.isChecked()
    monkeypatch.setattr(window, "ask_selection_scope", lambda rows, selected: "all")
    window.set_candidate_rows([1], False)
    assert not window.candidates[0].selected
    window.set_candidate_rows([1], True)
    assert all(window.table.item(i, 0).checkState() == Qt.CheckState.Checked for i in range(3))


@pytest.mark.parametrize("choice, expected", [("All same values", "all"), ("Just selected", "selected"), ("Cancel", None)])
def test_real_selection_scope_dialog(window, qtbot, choice, expected):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from redactor.engine import Candidate
    window.source.setPlainText("IBM IBM")
    window.candidates = [Candidate("IBM", "Business", "Acme R12345678", "test")]
    window.fill_candidates()
    def choose():
        dialog = QApplication.activeModalWidget()
        next(b for b in dialog.buttons() if b.text().replace("&", "") == choice).click()
    QTimer.singleShot(10, choose)
    assert MainWindow.ask_selection_scope(window, [0], False) == expected


def test_ignore_saved_replacement_keeps_old_alias_after_saving(window, qtbot):
    from redactor.engine import restore
    window.source.setPlainText("IBM IBM")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    window.reviewed.setChecked(True)
    window.generate()
    old = window.candidates[0].replacement
    window.source.setPlainText("IBM / IBM")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert window.candidates[0].reason == "Saved mapping"
    assert window.candidates[0].replacement == old
    window.table.selectRow(0)
    assert window.ignore_saved_button.isEnabled()
    qtbot.mouseClick(window.ignore_saved_button, Qt.MouseButton.LeftButton)
    new = window.candidates[0].replacement
    assert new != old
    assert window.table.item(0, 3).text() == window.table.item(1, 3).text() == new
    assert window.vault.data["mappings"][0]["replacement"] == old
    window.reviewed.setChecked(True)
    window.generate()
    assert window.output.toPlainText() == f"{new} / {new}"
    assert restore(f"{old} / {new}", window.vault.data["mappings"])[0] == "IBM / IBM"


@pytest.mark.parametrize("action, edited, expected", [("confirm", "Jane Smith", "Jane Smith / Jane Smith"),
                                                      ("edit", "Janet Smith", "Janet Smith / Janet Smith"),
                                                      ("deny", None, "jane smith / jane smith"),
                                                      ("stop", None, "jane smith / jane smith")])
def test_similar_original_review_actions(window, qtbot, monkeypatch, action, edited, expected):
    from redactor.engine import find_similar_values, prepare_mappings, Candidate
    mappings, _ = prepare_mappings([Candidate("Jane Smith", "Personal name", "Leia R12345678", "test")], [], "Jane Smith")
    window.vault.data["mappings"] = mappings
    text = "jane smith / jane smith"
    matches = find_similar_values(text, mappings)
    assert len(matches) == 1
    monkeypatch.setattr(window, "resolve_similar_value", lambda match: (action, edited))
    assert window.review_similar_values(text, matches) == expected
    assert window.vault.data["mappings"][0]["original"] == "Jane Smith"
    if action == "deny":
        assert ("jane smith", "Jane Smith") in window.denied_similar
    if action in {"confirm", "edit"}:
        assert window.vault.data["audit"][-1]["occurrences"] == 2


def test_scan_reviews_similar_original_before_suggesting_saved_replacement(window, qtbot, monkeypatch):
    from redactor.engine import prepare_mappings, Candidate
    mappings, _ = prepare_mappings([Candidate("Jane Smith", "Personal name", "Leia R12345678", "test")], [], "Jane Smith")
    window.vault.data["mappings"] = mappings
    monkeypatch.setattr(window, "resolve_similar_value", lambda match: ("confirm", match.original))
    window.source.setPlainText("Jnae Smith")
    window.scan()
    qtbot.waitUntil(lambda: not window.busy and bool(window.candidates), timeout=30000)
    assert window.source.toPlainText() == "Jane Smith"
    assert window.candidates[0].replacement == "Leia R12345678"
    assert window.candidates[0].reason == "Saved mapping"


def test_similarity_save_failure_leaves_imported_text_unchanged(window, monkeypatch):
    from redactor.engine import SimilarValue
    errors = []
    monkeypatch.setattr(window, "resolve_similar_value", lambda match: ("confirm", match.original))
    monkeypatch.setattr("redactor.app.error", lambda parent, message: errors.append(str(message)))
    def fail(): raise OSError("Disk full")
    monkeypatch.setattr(window.vault, "save", fail)
    before = len(window.vault.data["audit"])
    assert window.review_similar_values("Jnae Smith", [SimilarValue("Jnae Smith", "Jane Smith", "Leia R12345678", "typo", .95)]) == "Jnae Smith"
    assert errors and len(window.vault.data["audit"]) == before


def test_database_tabs_keep_independent_workspaces(window, qtbot, monkeypatch):
    from redactor.databases import add_database
    window.source.setPlainText('IBM')
    db=add_database(window.account_vault,'Second database')
    window.open_databases.append(db)
    window.database_tabs.addTab('Second database')
    window.database_tabs.setCurrentIndex(1)
    assert window.source.toPlainText()==''
    window.source.setPlainText('GNMA')
    window.database_tabs.setCurrentIndex(0)
    assert window.source.toPlainText()=='IBM'
    window.database_tabs.setCurrentIndex(1)
    assert window.source.toPlainText()=='GNMA'
    assert window.vault is db


def test_no_matches_keeps_editable_input(window,qtbot):
    window.source.setPlainText('nothing private here')
    window.scan();qtbot.waitUntil(lambda:not window.busy,timeout=30000)
    assert window.source.toPlainText()=='nothing private here'
    assert 'No sensitive information' in window.notice.text()
    assert window.candidates==[]


def test_lock_clears_all_database_workspace_and_audit_caches(window,qtbot):
    window.account_vault._saved_mappings=[{'original':'Private mapping snapshot'}]
    window.candidate_filters.allowed[1]={'Private filter'}
    window.vault_filters.allowed[0]={'Private vault filter'}
    window.workspace_states[1]={'input':'Private cached text'}
    window.audit_events=[{'input_text':'Sensitive audit cache'}]
    window.relock=True
    window.close()
    assert window.workspace_states=={} and window.audit_events==[]
    assert not window.account_vault.data
    assert not window.account_vault._saved_mappings
    assert window.table.rowCount()==0
    assert not window.candidate_filters.allowed and not window.vault_filters.allowed
