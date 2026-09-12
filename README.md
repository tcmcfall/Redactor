# Redactor

A local desktop workspace for reviewable sensitive-data substitutions and exact restoration, with an encrypted per-user vault.

**GPL-3.0-or-later.** Source packages include the application, tests, build tools and documentation. See [source distribution](SOURCE-DISTRIBUTION.md) and [LICENSE](LICENSE).

[Portable releases and source downloads](https://github.com/tcmcfall/Redactor/releases)

## Portable version 0.2

The current `Redactor.exe` belongs directly in the portable root with `_internal`, `tools` and `data`. All application-owned files stay in that folder. Multiple database tabs share the authenticated local account; copy/paste and merge actions preview conflicts before saving. RAR exchange is offered when a licensed portable RAR encoder is supplied.

See [portable, forensic and CLI guide](redactor/resources/Portable-Forensics-CLI.md), [Error Guide](redactor/resources/Error-Guide.md) and [RHEL man page](redactor/resources/redactor.1).

## Start on Windows

Run `Start-Redactor.ps1` after setup, or open the packaged `Redactor.exe` with its companion directory intact. To set up from source:

```powershell
.\Setup-Redactor.ps1
.\Start-Redactor.ps1
```

Create your own username and password at first launch. There are no default credentials. Portable Windows binaries include OCR in `tools/tesseract`; no system installation is used.

## What is implemented

- Native Qt desktop UI, keyboard navigation, window controls and resizable working panes.
- Candidate highlighting for names, businesses/abbreviations, hostnames, IPs, SSNs, cards and emails; manual sensitive-text selection.
- Fictional suggestions, custom replacements, collision rejection and exact one-pass restoration.
- Searchable original/replacement lookup with retained older aliases and confirmed edit/delete/flush actions.
- AES-GCM encrypted local vault with scrypt password derivation, atomic writes, password changes and optional 60-day reminders.
- Password-protected ZIP/TAR/7z database exchange with SHA-256/SHA-512 checksums, detailed encrypted audit activity, session locking and current-clipboard expiry.
- Modern Office, PDF, OpenDocument, text and image content import/export; local Tesseract OCR.
- In-app User Guide (F1), standalone documentation, source packaging and native Windows/macOS/RHEL build workflows.
- Six synthetic practice datasets and a guided workbook, accessible from Help → Practice examples.

## Read before use

Detection is heuristic and requires review. This is a functional initial implementation, not a certified de-identification or government data-handling product. Exports reconstruct **reviewed text only**, without original layouts, graphics, formulas, metadata or embedded objects. Legacy Office formats require local conversion. AI-modified substitute spellings cannot be reliably restored automatically.

The app makes no network requests. Installation/build tooling can download dependencies. Vault encryption does not protect an already compromised computer or an unlocked screen.

## Documentation

- [User Guide](redactor/resources/User-Guide.md): full user-facing workflows and limitations.
- [Build instructions and platform status](BUILDING.md): Windows, macOS Apple Silicon/Intel, RHEL 10 x64.
- [Source distribution](SOURCE-DISTRIBUTION.md): modification and source-package workflow.
- [Third-party notices](THIRD-PARTY-NOTICES.md).

## Development

```bash
python -m venv .venv
# Activate the environment using your platform's normal command.
python -m pip install '.[dev]'
python -m pytest -q
python -m redactor
python scripts/build.py
python scripts/package_source.py
```

macOS and RHEL packages require native builds and validation on those systems; Windows cannot cross-compile them. Source repository: https://github.com/tcmcfall/Redactor. Native macOS/RHEL validation is reported separately from Windows validation.
