# Building Redactor

Redactor uses one Python/PySide6 codebase and one encrypted vault format. Native packages must be built on their target operating system and architecture. A Windows executable does not run natively on macOS or Linux.

## Target matrix

| Target | Package | Build environment | Validation |
| --- | --- | --- | --- |
| Windows 11 x64 | `Redactor/Redactor.exe` with its sibling files | Windows, Python 3.11–3.14 | Locally tested; see test output |
| Current macOS, Apple Silicon | `Redactor.app` | ARM64 macOS, Python 3.12 | Workflow supplied; native execution still required |
| Current macOS, Intel | `Redactor.app` | x64 macOS, Python 3.12 | Workflow supplied; native execution still required |
| RHEL 10 x64 desktop | `Redactor/Redactor` in a tar archive | RHEL 10, Python 3.12 | Workflow supplied; native execution still required |

The application targets current desktop releases. This is not a claim of completed certification on every OS release or of Red Hat vendor support. RHEL 8/9, Windows ARM and Linux ARM packages have not been validated. Test new OS releases on actual hardware or a VM before deployment.

The packaged executable accepts `--smoke-test <output-directory>` for a synthetic-data packaging check. It creates a temporary training vault, verifies replacement/restoration, lookup, document adapters and bundled resources, then writes a report and screenshot to the specified directory. It does not open or modify the user's real account. Run this on each native artifact before distribution.

## Windows

```powershell
.\Setup-Redactor.ps1
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/build.py
```

Run `dist/Redactor/Redactor.exe`. Keep the entire `Redactor` directory together. All build outputs, caches and portable runtime files stay inside the repository. Default output is dist/Redactor and work is build/. Do not configure external AppData output paths. The Windows release puts Redactor.exe and Redactor-cli.exe in the root of the extracted portable folder. Keep _internal and tools alongside them. The development runtime is a build prerequisite; compiled end-user packages include Python.

## macOS

Install Python 3.12 as a build prerequisite. To ship image import, stage a native relocatable Tesseract build with its required dynamic libraries and English tessdata in tools/tesseract before building. Do not rely on a user system OCR installation. Then:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python scripts/build.py
open dist/Redactor.app
```

Build separately on Apple Silicon and Intel. The provided GitHub Actions workflow does this with native runners. No signing credentials are supplied. For distribution, provide a Developer ID identity through `REDACTOR_CODESIGN_IDENTITY`, then notarize and staple the resulting app using your organization's Apple tooling. Unsigned development builds may be blocked by Gatekeeper.

## Red Hat Enterprise Linux 10

Use a RHEL 10 desktop with Python 3.12, pip and Qt's X11/Wayland dependencies. System dependencies typically include `libxkbcommon`, `libxkbcommon-x11`, `xcb-util-cursor`, `xcb-util-wm`, `xcb-util-image`, `xcb-util-keysyms`, `xcb-util-renderutil`, `mesa-libGL`, `dbus-libs`, `fontconfig` and `dejavu-sans-mono-fonts`. Install them through your approved RHEL repositories. Portable OCR needs a native relocatable Tesseract executable, required libraries and English tessdata staged under tools/tesseract. Availability depends on enabled repositories; this project does not enable third-party repositories automatically.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python scripts/build.py
./dist/Redactor/Redactor
```

The RHEL workflow requires a self-hosted runner labeled `self-hosted`, `linux`, `x64`, `rhel-10`, with those prerequisites already installed. It deliberately has manual dispatch only; do not run untrusted pull requests on a privileged self-hosted runner. Tests in offscreen mode do not replace an interactive check of window controls, clipboard, dialogs, DPI and the display server on RHEL.

## Release acceptance

Before distributing a build, run the tests and manually verify account creation, lock/unlock, lookup, custom selection, replacement, restoration, password change, backup recovery, deletion confirmation, OCR and representative document formats on the target OS. Use synthetic data. Verify the packaged build can find the User Guide and all document dependencies. Confirm any signing, notarization and dependency license requirements for your distribution.

Dependency ranges are in `pyproject.toml`. `requirements-windows-tested.txt` records the local Windows test environment. Resolve and retain a separate locked environment for each release target; do not copy Windows-only dependency pins into Linux/macOS environments.

## Portable distribution checklist

The GUI and console executables are both built by scripts/build.py. Windows/Linux ship the Redactor directory; macOS ships Redactor-portable containing Redactor.app, the console executable and runtime files. Package each entire folder. Run the packaged smoke test and console --help on the native target. Do not label an artifact self-contained for OCR until its native tools/tesseract has been staged and validated with no system OCR fallback. RAR encoding is optional and requires a separately licensed native utility; ZIP/TAR/7z are built in.

Sources include the terminal workspace and man page. Release archives must exclude data, exports, test vaults and diagnostics. Publish compiled files as GitHub release assets, with corresponding source/dependency source archives and checksums; never add user vaults to Git history. The supplied native workflows currently build application artifacts; native OCR staging is an explicit prerequisite, not an implicit network download by Redactor.
