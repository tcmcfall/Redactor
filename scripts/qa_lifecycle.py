# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Exercise the real application loop through lock, re-login and exit."""
import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog
import redactor.app as application
from redactor.vault import Vault

with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    count = {"logins": 0, "windows": 0}
    original_window = application.MainWindow
    class TestLogin(QDialog):
        def __init__(self, location):
            super().__init__()
            count["logins"] += 1
            self.vault = Vault.create(location, "Lifecycle", "Lifecycle test passphrase") if count["logins"] == 1 else Vault.open(location, "Lifecycle", "Lifecycle test passphrase")
        def exec(self):
            return QDialog.DialogCode.Accepted
    class TestWindow(original_window):
        def __init__(self, vault):
            super().__init__(vault)
            count["windows"] += 1
            QTimer.singleShot(100, self.lock if count["windows"] == 1 else self.close)
    application.Login = TestLogin
    application.MainWindow = TestWindow
    application.vault_directory = lambda: directory
    application.main()
    assert count == {"logins": 2, "windows": 2}, count
    print("Application lifecycle passed: login, lock, re-login, exit.")
