# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Online release-preparation utility; never imported by the offline app.

Downloads matching source distributions with PyPI SHA-256 verification, plus Qt
source. Saves a report and fails if any dependency source cannot be obtained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from package_source import manifest


def download(url, destination, expected=None):
    request = urllib.request.Request(url, headers={"User-Agent": "Redactor-source-packager/0.2.1"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
            digest.update(block)
    actual = digest.hexdigest()
    if expected and expected != actual:
        destination.unlink()
        raise ValueError("Source archive SHA-256 mismatch")
    return actual


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("releases/dependency-sources"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = []
    info = manifest()
    for dependency in info["dependencies"]:
        name = dependency["name"]
        if name.lower() in {"pyside6", "pyside6_essentials", "pyside6_addons", "shiboken6"}:
            continue  # Distributed together in the Qt for Python source archive below.
        try:
            with urllib.request.urlopen(dependency["pypi_release_metadata"], timeout=45) as response:
                release = json.load(response)
            source = next(item for item in release["urls"] if item["packagetype"] == "sdist")
            sha = download(source["url"], args.output / source["filename"], source["digests"]["sha256"])
            report.append({"name": name, "url": source["url"], "sha256": sha, "status": "downloaded"})
        except Exception as exc:
            report.append({"name": name, "status": "missing", "reason": str(exc)})
    qt_url = info["qt_corresponding_source"]
    pyside_version = next(d["version"] for d in info["dependencies"] if d["name"] == "PySide6")
    pyside_url = info["pyside_corresponding_source"] + f"pyside-setup-everywhere-src-{pyside_version}.tar.xz"
    for name, url in [("Qt", qt_url), ("Qt for Python", pyside_url)]:
        try:
            sha = download(url, args.output / url.rsplit("/", 1)[-1])
            report.append({"name": name, "url": url, "sha256": sha, "status": "downloaded"})
        except Exception as exc:
            report.append({"name": name, "status": "missing", "reason": str(exc), "url": url})
    (args.output / "SOURCE-DOWNLOAD-REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for item in report:
        print(item["name"], item["status"])
    if any(item["status"] == "missing" for item in report):
        raise SystemExit("Some sources are unavailable. See the report and resolve them before distributing a complete dependency-source bundle.")


if __name__ == "__main__":
    main()
