# Source code and modification rights

Redactor's original application code and documentation are provided under the **GNU General Public License, version 3 or (at your option) any later version** (`GPL-3.0-or-later`). The full license is in `LICENSE`. Redactor is provided without warranty, to the extent permitted by law.

You may study, modify and redistribute Redactor under those terms. Preserve copyright and license notices. When conveying modified versions, identify your changes and provide the corresponding source as required by the GPL. This repository does not restrict users from modifying, rebuilding or running their own version.

## What accompanies a build

`scripts/build.py` places a versioned source archive alongside every native application it builds:

- Windows/Linux: `Redactor/source/Redactor-0.2.1-source.zip`
- macOS: `Redactor-portable/source/Redactor-0.2.1-source.zip`

The archive contains the complete Redactor application source, resources, tests, packaging scripts, platform workflows, user documentation, license notices, dependency information and build instructions. It excludes user vaults, imported documents, credentials, caches and binary build output. `SOURCE-SHA256.json` records each application's source-file hash, and a SHA-256 file accompanies the archive.

Generate a standalone source package at any time:

```bash
python scripts/package_source.py
```

The resulting ZIP is written under `releases/`. Package source from the same checkout used to build the binaries. Use the source archive that matches the executable.

## Updating Redactor

Extract the source archive, read `BUILDING.md`, create a fresh virtual environment and install `.[dev]`. Modify the code, run `python -m pytest -q`, and build natively for each target OS with `python scripts/build.py`. Use synthetic data for tests. Increment the application and package version consistently before a new release.

The application is organized into:

- `redactor/app.py`: native interface, review workflow, lookup, account controls and locking.
- `redactor/engine.py`: detection, pseudonyms, collision checks and exact reversible matching.
- `redactor/vault.py`, `redactor/storage.py`, `redactor/databases.py`: password protection, separate encrypted database files, hashed user folders and account authorization.
- `redactor/formats.py`: local extraction, OCR and fresh content-only exports.
- `redactor/resources/User-Guide.md`: end-user documentation included in the Help menu.
- `tests/`: behavioral, storage, format and UI tests.
- `scripts/` and `.github/workflows/`: source/native packaging and platform builds.

## Dependencies and binary redistribution

Dependencies retain their own licenses. See `THIRD-PARTY-NOTICES.md` and the notices copied into each binary package's `licenses` directory. The generated `DEPENDENCY-SOURCES.json` lists exact installed versions, PyPI release metadata endpoints and upstream Qt/PySide source locations.

The Redactor source ZIP includes Redactor's corresponding application source; it is not a claim that every bundled dependency's source is inside that ZIP. In particular, distributors conveying Qt/PySide binaries must also satisfy those libraries' applicable LGPL/GPL source and relinking obligations. Keep the dynamic libraries replaceable, preserve their notices, and accompany distributed binaries with the exact required dependency source materials or another delivery mechanism permitted by the applicable license. The build does not invent a written source offer on your behalf.

For release preparation, `scripts/fetch_dependency_sources.py` can download exact-version Python source distributions and Qt/PySide source archives into a companion directory. It is an online build-time tool, never called by the application. Review its report for any unavailable archives and resolve omissions before external binary distribution. Keep dependency source materials available together with the corresponding binary release.

PDF processing uses permissively licensed pypdfium2/PDFium; AGPL-only PDF dependencies are not part of the application.
