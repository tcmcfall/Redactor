# SPDX-License-Identifier: GPL-3.0-or-later
"""Encrypted database plus SHA-256/SHA-512 in a bounded portable archive."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile
from .portable import root, directory

NAMES = {'database.redactor', 'SHA256SUMS', 'SHA512SUMS'}
LIMIT = 100_000_000


def rar_tool():
    return next((p for p in [root() / 'tools/rar/rar.exe', root() / 'tools/rar/rar'] if p.is_file()), None)


def bundle(payload: bytes, path: Path):
    files = {'database.redactor': payload,
             'SHA256SUMS': (hashlib.sha256(payload).hexdigest()+'  database.redactor\n').encode(),
             'SHA512SUMS': (hashlib.sha512(payload).hexdigest()+'  database.redactor\n').encode()}
    with tempfile.TemporaryDirectory(dir=directory('data/tmp')) as temporary:
        temp = Path(temporary)
        archive = temp / ('export'+path.suffix.lower())
        if path.suffix.lower() == '.zip':
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for name, data in files.items(): z.writestr(name,data)
        elif path.suffix.lower() == '.tar':
            # gzip-compressed TAR despite simple user-facing .tar suffix; readers auto-detect.
            with tarfile.open(archive,'w:gz') as z:
                for name, data in files.items():
                    info = tarfile.TarInfo(name); info.size=len(data); info.mode=0o600
                    z.addfile(info,io.BytesIO(data))
        elif path.suffix.lower() in ('.7z','.zip7'):
            import py7zr
            with py7zr.SevenZipFile(archive,'w') as z:
                for name,data in files.items(): z.writestr(data,name)
        elif path.suffix.lower() == '.rar':
            tool = rar_tool()
            if not tool: raise ValueError('R011: RAR creation requires a licensed native rar utility in tools/rar. Choose ZIP, TAR or 7z instead.')
            for name,data in files.items(): (temp/name).write_bytes(data)
            result = subprocess.run([str(tool),'a','-ep','-idq',str(archive),*sorted(files)],cwd=temp,capture_output=True,timeout=120,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if result.returncode: raise ValueError('R011: Portable RAR utility failed. Check its platform and license or choose ZIP.')
        else: raise ValueError('R011: Choose .zip, .tar, .rar or .7z (.zip7).')
        # Atomic destination replacement on the same filesystem.
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, sibling = tempfile.mkstemp(dir=path.parent,prefix='.redactor-bundle-')
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(archive.read_bytes()); stream.flush(); os.fsync(stream.fileno())
            from .portable import atomic_replace
            atomic_replace(sibling,path)
        finally:
            if Path(sibling).exists(): Path(sibling).unlink()


def unpack(path: Path) -> bytes:
    if path.stat().st_size > LIMIT: raise ValueError('R005: Database archive exceeds 100 MB.')
    suffix = path.suffix.lower()
    if suffix in ('.redactor','.vault'): return path.read_bytes()  # legacy raw encrypted files
    files = {}
    if suffix == '.zip':
        with zipfile.ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)!=3 or {i.filename for i in infos}!=NAMES or sum(i.file_size for i in infos)>LIMIT: raise ValueError('R011: Invalid archive members or size.')
            files={i.filename:z.read(i) for i in infos}
    elif suffix == '.tar':
        with tarfile.open(path,'r:*') as z:
            infos=z.getmembers()
            if len(infos)!=3 or {i.name for i in infos}!=NAMES or not all(i.isfile() for i in infos) or sum(i.size for i in infos)>LIMIT: raise ValueError('R011: Invalid TAR members or size.')
            files={i.name:z.extractfile(i).read() for i in infos}
    elif suffix in ('.7z','.zip7'):
        import py7zr
        with py7zr.SevenZipFile(path,'r') as z:
            infos=z.list()
            if len(infos)!=3 or {i.filename for i in infos}!=NAMES or any(i.is_directory or getattr(i,'is_symlink',False) for i in infos) or sum(i.uncompressed for i in infos)>LIMIT: raise ValueError('R011: Invalid 7z members or size.')
            with tempfile.TemporaryDirectory(dir=directory('data/tmp')) as temporary:
                z.extractall(path=temporary)
                files={name:(Path(temporary)/name).read_bytes() for name in NAMES}
    elif suffix == '.rar':
        import rarfile
        tool = rar_tool()
        if not tool: raise ValueError('R011: Place a native RAR utility in tools/rar or ask for ZIP export.')
        rarfile.UNRAR_TOOL = str(tool)
        with rarfile.RarFile(path) as z:
            infos=z.infolist()
            if len(infos)!=3 or {i.filename for i in infos}!=NAMES or not all(i.isfile() for i in infos) or sum(i.file_size for i in infos)>LIMIT: raise ValueError('R011: Invalid RAR members or size.')
            files={i.filename:z.read(i) for i in infos}
    else: raise ValueError('R011: Unsupported database archive.')
    payload=files['database.redactor']
    for algorithm, name in [('sha256','SHA256SUMS'),('sha512','SHA512SUMS')]:
        expected=(hashlib.new(algorithm,payload).hexdigest()+'  database.redactor\n').encode()
        if files[name]!=expected: raise ValueError('R011: Database checksum mismatch. Obtain an intact export; do not import this file.')
    return payload
