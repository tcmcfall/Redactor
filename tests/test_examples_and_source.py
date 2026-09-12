# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from redactor.engine import detect, prepare_mappings, replace_exact, restore

EXAMPLES = Path(__file__).resolve().parents[1] / "redactor/resources/examples"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.txt")) + sorted(EXAMPLES.glob("*.json")))
def test_synthetic_example_roundtrip(path):
    text = path.read_text(encoding="utf-8")
    candidates = detect(text, [])
    mappings, conversions = prepare_mappings(candidates, [], text)
    output, counts = replace_exact(text, conversions)
    assert counts
    assert restore(output, mappings)[0] == text


def test_source_package_contains_code_guide_samples_and_no_vaults(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from package_source import package
    archive_path = package(tmp_path)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        root = names[0].split("/")[0]
        assert f"{root}/LICENSE" in names
        assert f"{root}/redactor/app.py" in names
        assert f"{root}/redactor/resources/User-Guide.md" in names
        assert f"{root}/redactor/resources/examples/Practice-Workbook.md" in names
        assert f"{root}/scripts/build.py" in names
        assert not any(n.endswith(".vault") or "/.venv/" in n or "__pycache__" in n for n in names)
        manifest = json.loads(archive.read(f"{root}/SOURCE-SHA256.json"))
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read(f"{root}/{name}")).hexdigest() == digest
