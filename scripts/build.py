# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Run on each target OS. PyInstaller does not cross-compile desktop apps."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import importlib.metadata as metadata

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--work", type=Path, default=ROOT / "build")
    parser.add_argument("--clean", action="store_true", help="Discard PyInstaller caches for a clean rebuild")
    args = parser.parse_args()
    local_cache = ROOT / '.cache'
    (local_cache / 'tmp').mkdir(parents=True,exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = os.environ['TMPDIR'] = str(local_cache / 'tmp')
    os.environ['PYINSTALLER_CONFIG_DIR'] = str(local_cache / 'pyinstaller')
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
               "--name", "Redactor", "--distpath", str(args.output), "--workpath", str(args.work),
               "--specpath", str(args.work), "--add-data", str(ROOT / "redactor/resources") + os.pathsep + "redactor/resources",
               "--collect-data", "pypdfium2_raw",
               # Office helpers open paths containing parts/../templates; on
               # POSIX the intermediate package directories must physically exist.
               "--collect-all", "docx", "--collect-all", "pptx",
               "--hidden-import", "PIL.TiffImagePlugin", "--hidden-import", "PIL.WebPImagePlugin",
               "--exclude-module", "pytest", "--exclude-module", "tkinter", str(ROOT / "launcher.py")]
    if args.clean:
        command.append("--clean")
    if sys.platform == "darwin":
        command += ['--runtime-hook', str(ROOT / 'scripts/packaged_diagnostics.py')]
        # Source-built cryptography can require newer OpenSSL than Python's
        # bundled copy. Give its actual dependencies precedence during collection.
        import cryptography.hazmat.bindings._rust as rust
        dependencies = subprocess.check_output(['otool', '-L', rust.__file__], text=True)
        for line in dependencies.splitlines()[1:]:
            library = Path(line.strip().split(' (')[0])
            if library.name.startswith(('libssl.', 'libcrypto.')) and library.is_file():
                command += ['--add-binary', str(library) + os.pathsep + '.']
        command += ["--osx-bundle-identifier", "local.redactor.desktop"]
        if os.environ.get("REDACTOR_CODESIGN_IDENTITY"):
            command += ["--codesign-identity", os.environ["REDACTOR_CODESIGN_IDENTITY"]]
    build_env = os.environ.copy()
    if sys.platform == "win32":
        # Do not accidentally bundle similarly named DLLs from unrelated tools
        # on the host PATH (for example an incompatible Poppler ICU library).
        windows = Path(os.environ.get("WINDIR", "C:/Windows"))
        build_env["PATH"] = os.pathsep.join([
            str(Path(sys.executable).parent), str(Path(sys.base_prefix)),
            str(Path(sys.base_prefix) / "DLLs"), str(windows / "System32"), str(windows),
        ])
    # Recreate executable containers even when a cached PYZ is rebuilt. This
    # avoids stale embedded code when filesystem timestamp/cache checks miss it.
    for target in ('Redactor', 'Redactor-cli'):
        for toc in ('PKG-00.toc', 'EXE-00.toc'):
            (args.work / target / toc).unlink(missing_ok=True)
    subprocess.run(command, cwd=ROOT, env=build_env, check=True)
    app_dir = args.output / ("Redactor.app" if sys.platform == "darwin" else "Redactor")
    resource_dir = app_dir / "Contents" / "Resources" if sys.platform == "darwin" else app_dir
    cli_command = [part for part in command if part != '--clean']
    cli_command.remove('--windowed')
    cli_command[cli_command.index('--name')+1] = 'Redactor-cli'
    cli_command[cli_command.index(str(ROOT / 'launcher.py'))] = str(ROOT / 'cli_launcher.py')
    # Console entry uses the same bundled libraries and remains entirely portable.
    if '--osx-bundle-identifier' in cli_command:
        i=cli_command.index('--osx-bundle-identifier');del cli_command[i:i+2]
    subprocess.run(cli_command,cwd=ROOT,env=build_env,check=True)
    cli_dir=args.output / 'Redactor-cli'
    portable_dir=app_dir if sys.platform!='darwin' else args.output / 'Redactor-portable'
    if sys.platform=='darwin':
        portable_dir.mkdir(exist_ok=True)
        shutil.copytree(app_dir,portable_dir / 'Redactor.app',dirs_exist_ok=True)
        resource_dir=portable_dir
    for entry in cli_dir.iterdir():
        if entry.is_dir():shutil.copytree(entry,portable_dir / entry.name,dirs_exist_ok=True)
        else:shutil.copy2(entry,portable_dir / entry.name)
    if (ROOT / 'tools/tesseract').exists():
        shutil.copytree(ROOT / 'tools/tesseract',portable_dir / 'tools/tesseract',dirs_exist_ok=True)
    for document in ['User-Guide.md','Error-Guide.md','Portable-Forensics-CLI.md','redactor.1']:
        shutil.copy2(ROOT / 'redactor/resources' / document,portable_dir / document)
    for name in ["LICENSE", "THIRD-PARTY-NOTICES.md", "SOURCE-DISTRIBUTION.md"]:
        shutil.copyfile(ROOT / name, resource_dir / name)
    shutil.copyfile(ROOT / "redactor/resources/User-Guide.md", resource_dir / "User-Guide.md")
    shutil.copytree(ROOT / "redactor/resources/examples", resource_dir / "examples", dirs_exist_ok=True)
    from package_source import package
    archive = package(resource_dir / "source")
    # Preserve dependency licenses from their installed distributions.
    for distribution in metadata.distributions():
        for entry in distribution.files or []:
            if any(term in entry.name.lower() for term in ("license", "copying", "notice")) and str(entry).endswith((".txt", ".md", "LICENSE", "COPYING", "NOTICE", ".rst")):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = resource_dir / "licenses" / distribution.metadata["Name"] / Path(str(entry)).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    # Python is not an importlib distribution, so preserve its notice separately.
    python_notice = resource_dir / 'licenses/Python/LICENSE.txt'
    python_notice.parent.mkdir(parents=True, exist_ok=True)
    installed_notice = Path(sys.base_prefix) / 'LICENSE.txt'
    if installed_notice.is_file():
        shutil.copy2(installed_notice, python_notice)
    else:
        # Build-time source acquisition only; never executed by Redactor.
        import urllib.request
        url = f'https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE'
        with urllib.request.urlopen(url, timeout=60) as response:
            python_notice.write_bytes(response.read())
    print(f"Built {platform.system()} {platform.machine()} application: {app_dir}")
    print("Portable build; no installation. Native OCR must be bundled in tools/tesseract. RAR requires a separately licensed portable encoder.")


if __name__ == "__main__":
    main()
