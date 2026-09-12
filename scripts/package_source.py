# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Create a reviewable GPL source archive without user data or build artifacts."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
TOP_LEVEL = ["pyproject.toml", "LICENSE", "README.md", "BUILDING.md", "SOURCE-DISTRIBUTION.md",
             "THIRD-PARTY-NOTICES.md", "MANIFEST.in", ".gitignore", ".gitattributes", "launcher.py", "cli_launcher.py", "Setup-Redactor.ps1",
             "Start-Redactor.ps1", "Install-OCR.ps1", "start-redactor.sh", "requirements-windows-tested.txt"]
DIRECTORIES = ["redactor", "tests", "scripts", ".github"]
EXTENSIONS = {".1",".py", ".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".sh", ".ps1"}


def collect_sources():
    paths = [ROOT / name for name in TOP_LEVEL if (ROOT / name).is_file()]
    for directory in DIRECTORIES:
        paths.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in EXTENSIONS and "__pycache__" not in p.parts)
    return sorted(set(paths))


def manifest():
    items = []
    for name in ["PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "cryptography",
                 "python-docx", "openpyxl", "python-pptx", "pypdfium2", "Pillow", "striprtf", "odfpy",
                 "lxml", "cffi", "defusedxml", "XlsxWriter", "et_xmlfile", "typing_extensions", "pycparser", "prompt_toolkit", "wcwidth", "py7zr", "rarfile", "texttable", "pycryptodomex", "brotli", "psutil", "pyppmd", "pybcj", "multivolumefile", "inflate64"]:
        try:
            dist = metadata.distribution(name)
            version = dist.version
            item = {"name": name, "version": version,
                    "pypi_release_metadata": f"https://pypi.org/pypi/{name}/{version}/json",
                    "upstream": dist.metadata.get_all("Project-URL") or [dist.metadata.get("Home-page", "")]}
            items.append(item)
        except metadata.PackageNotFoundError:
            pass
    qt_version = metadata.version("PySide6")
    qt_series = ".".join(qt_version.split(".")[:2])
    return {"application": "Redactor", "version": VERSION, "license": "GPL-3.0-or-later",
            "dependencies": items,
            "qt_corresponding_source": f"https://download.qt.io/archive/qt/{qt_series}/{qt_version}/single/qt-everywhere-src-{qt_version}.tar.xz",
            "pyside_corresponding_source": f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{qt_version}-src/",
            "note": "Dependency source links identify upstream materials. Convey required dependency sources alongside binary releases; do not treat links alone as a compliance guarantee."}


def package(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"Redactor-{VERSION}-source.zip"
    base = f"Redactor-{VERSION}-source"
    source_files = collect_sources()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        hashes = {}
        for path in source_files:
            relative = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            archive.writestr(f"{base}/{relative}", content)
            hashes[relative] = hashlib.sha256(content).hexdigest()
        archive.writestr(f"{base}/DEPENDENCY-SOURCES.json", json.dumps(manifest(), indent=2))
        archive.writestr(f"{base}/SOURCE-SHA256.json", json.dumps(hashes, indent=2))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix(".zip.sha256").write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    print(f"Created {archive_path} ({len(source_files)} source files)")
    return archive_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    package(parser.parse_args().output)
