"""Refresh pure Python payloads after a full Windows build, without recollecting DLLs.

Refuse new modules/import dependencies; use build.py for dependency changes.
The ordinary full build remains the default release build method.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import dis
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.building.build_main import Analysis

ROOT=Path(__file__).resolve().parents[1]

def imports(code):
    names={instruction.argval for instruction in dis.get_instructions(code) if instruction.opname=='IMPORT_NAME'}
    for value in code.co_consts:
        if isinstance(value,types.CodeType):names.update(imports(value))
    return names

def main():
    if sys.platform!='win32':raise SystemExit('This payload refresh supports Windows; build natively with build.py elsewhere.')
    for name in ['Redactor','Redactor-cli']:
        binary=ROOT/'dist/Redactor'/(name+'.exe')
        pyz=CArchiveReader(str(binary)).open_embedded_archive('PYZ.pyz')
        for path in (ROOT/'redactor').glob('*.py'):
            module='redactor' if path.stem=='__init__' else 'redactor.'+path.stem
            if module not in pyz.toc:
                # Each entry point excludes modules used only by the other UI.
                continue
            fresh=compile(path.read_bytes(),str(path),'exec',dont_inherit=True)
            if imports(fresh)!=imports(pyz.extract(module)):
                raise SystemExit(f'Imports changed in {module}; run a full build.')
        cached=ast.literal_eval((ROOT/'build'/name/'Analysis-00.toc').read_text(encoding='utf-8'))
        values=dict(zip((item[0] for item in Analysis._GUTS),cached))
        work=ROOT/'build/python-refresh'/name
        work.mkdir(parents=True,exist_ok=True)
        spec=work/(name+'.spec')
        spec.write_text('pyz = PYZ('+repr(values['pure'])+')\nexe = EXE(pyz, '+repr(values['scripts'])+', [], exclude_binaries=True, name='+repr(name)+', console='+repr(name.endswith('-cli'))+', upx=True)\n',encoding='utf-8')
        for stamp in ['PYZ-00.toc','PKG-00.toc','EXE-00.toc']:
            (work/name/stamp).unlink(missing_ok=True)
        env=os.environ.copy()
        env['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.cache/pyinstaller')
        env['TEMP']=env['TMP']=env['TMPDIR']=str(ROOT/'.cache/tmp')
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--workpath',str(work),'--distpath',str(ROOT/'dist'),str(spec)],env=env,check=True)
        rebuilt=work/name/(name+'.exe')
        shutil.copy2(rebuilt,binary)
        if name.endswith('-cli'):shutil.copy2(rebuilt,ROOT/'dist/Redactor-cli'/(name+'.exe'))
    print('Python payloads refreshed; run packaged verification before distribution.')

if __name__=='__main__':main()
