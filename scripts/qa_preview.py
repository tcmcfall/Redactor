# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Generate a synthetic-data UI preview; does not use a real account."""
import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from redactor.app import MainWindow, STYLE
from redactor.vault import Vault
from redactor.engine import detect

from redactor.portable import configure
configure()
app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
with tempfile.TemporaryDirectory() as directory:
    vault = Vault.create(Path(directory), "Local preview", "Synthetic preview passphrase")
    window = MainWindow(vault)
    window.source.setPlainText("INVESTIGATION NOTES\n\nJane Smith at International Business Machines (IBM) reviewed unusual activity on prod-server.example.com.\n\nThe connection originated from 10.24.8.12. Follow up with Jane Smith before publishing the report.\n\nCase reference: 123-45-6789\nPayment record: 4111 1111 1111 1111\n\nNext step: compare the event timeline and prepare a concise audit summary.")
    window.candidates = detect(window.source.toPlainText(), [])
    window.fill_candidates()
    window.reviewed.setChecked(True)
    window.generate()
    window.show()
    def capture():
        output = Path(__file__).resolve().parents[1] / "qa-output"
        output.mkdir(exist_ok=True)
        window.grab().save(str(output / "workspace.png"))
        window.show_page(1)
        window.nav_group.button(1).setChecked(True)
        window.grab().save(str(output / "lookup.png"))
        window.show_page(3)
        app.processEvents()
        window.grab().save(str(output / 'account.png'))
        from redactor.app import Login
        login = Login(Path(directory));login.show();app.processEvents()
        login.grab().save(str(output / 'login.png'));login.close()
        window.relock = True
        window.close()
        app.quit()
    QTimer.singleShot(500, capture)
    app.exec()
