# SPDX-License-Identifier: GPL-3.0-or-later
"""All application-owned storage lives in the movable application directory."""
from pathlib import Path
import os
import sys


def root() -> Path:
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable).resolve()
        if sys.platform == 'darwin' and executable.parent.name == 'MacOS' and executable.parents[1].name == 'Contents':
            return executable.parents[3]  # beside Redactor.app, not inside signed bundle
        return executable.parent
    return Path(__file__).resolve().parent.parent


def directory(name: str) -> Path:
    path = root() / name
    path.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        path.chmod(0o700)
    return path


def output_path(value) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root() / path
    path = path.resolve()
    if not path.is_relative_to(root().resolve()):
        raise ValueError('R008: Choose an output inside the portable Redactor folder. Move the entire folder to move its data.')
    return path


def configure():
    cache = directory('data/tmp')
    for name in ('TMP', 'TEMP', 'TMPDIR'):
        os.environ[name] = str(cache)
    import tempfile
    tempfile.tempdir = str(cache)


def atomic_replace(source, destination):
    """Retry short Windows sharing/AV holds without falling back to in-place writes."""
    import time
    for attempt in range(4):
        try:
            os.replace(source,destination)
            return
        except PermissionError as exc:
            if os.name != 'nt' or getattr(exc,'winerror',None) not in (5,32,33) or attempt==3:
                raise
            time.sleep(.1 * 2**attempt)
