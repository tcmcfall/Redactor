# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Explicit packaging diagnostic using synthetic data in a temporary vault."""
import json
from pathlib import Path
import tempfile
from importlib.resources import files


def run(output_directory):
    from PySide6.QtWidgets import QApplication
    from .app import MainWindow, STYLE
    from .engine import detect, restore
    from .formats import export_file, read_file, tesseract_path
    from .vault import Vault
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "failed", "checks": []}
    try:
        with tempfile.TemporaryDirectory(prefix="redactor-smoke-") as temporary:
            directory = Path(temporary)
            vault = Vault.create(directory, "Synthetic test", "Synthetic test passphrase only")
            text = "Tavi Quill at ZQC uses 10.2.3.4. Identifier 000-12-3456."
            window = MainWindow(vault)
            window.source.setPlainText(text)
            window.candidates = detect(text, [])
            window.fill_candidates()
            window.generate()
            assert window.has_output
            obfuscated = window.output.toPlainText()
            assert "Tavi Quill" not in obfuscated and "10.2.3.4" not in obfuscated
            assert restore(obfuscated, vault.data["mappings"])[0] == text
            report["checks"].append("encrypted mapping + exact roundtrip")
            window.show()
            app.processEvents()
            window.grab().save(str(output / "packaged-workspace.png"))
            window.show_page(1)
            window.vault_search.setText("ZQC")
            assert window.vault_table.rowCount() == 1
            report["checks"].append("value lookup")
            for extension in [".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".rtf", ".odt", ".ods", ".odp"]:
                path = directory / ("work" + extension)
                export_file(path, obfuscated)
                imported = read_file(path).text
                assert vault.data["mappings"][0]["replacement"] in imported
                report["checks"].append(extension + " export/import")
            if tesseract_path():
                image = directory / "scan.png"
                export_file(image, "Training identifier 123-45-6789")
                recognized = read_file(image).text
                assert "123-45-6789" in recognized, f"Synthetic OCR mismatch: {recognized!r}"
                report["checks"].append("local OCR")
            else:
                report["ocr"] = "not installed"
            guide = files("redactor").joinpath("resources/User-Guide.md").read_text(encoding="utf-8")
            assert "User Guide" in guide
            examples = list(files("redactor").joinpath("resources/examples").iterdir())
            assert len(examples) >= 7
            report["checks"].append("bundled guide and practice examples")
            window.relock = True
            window.close()
            assert not vault.data
            report["checks"].append("lock clears vault")
            report["status"] = "passed"
    except Exception as exc:
        report["error"] = repr(exc)
    (output / "smoke-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["status"] != "passed":
        raise SystemExit(1)
