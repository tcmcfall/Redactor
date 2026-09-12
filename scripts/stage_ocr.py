# SPDX-License-Identifier: GPL-3.0-or-later
"""Release-time staging of installed native OCR into the portable folder.

This developer tool is not imported or called by the application. On Unix it
copies non-system dependencies; macOS install names are rewritten locally.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',type=Path,required=True);p.add_argument('--tessdata',type=Path,required=True)
    args=p.parse_args();target=ROOT/'tools/tesseract';target.mkdir(parents=True,exist_ok=True)
    if sys.platform=='win32':
        import pefile
        queue=[args.executable];seen=set()
        while queue:
            path=queue.pop()
            if path.name.casefold() in seen:continue
            seen.add(path.name.casefold());shutil.copy2(path,target/path.name)
            pe=pefile.PE(str(path),fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
            for entry in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
                dependency=args.executable.parent/entry.dll.decode()
                if dependency.exists():queue.append(dependency)
            pe.close()
        if (args.executable.parent/'doc').exists():shutil.copytree(args.executable.parent/'doc',target/'doc',dirs_exist_ok=True)
    else:
        bindir=target/'bin';libdir=target/'lib';bindir.mkdir(exist_ok=True);libdir.mkdir(exist_ok=True)
        binary=bindir/'tesseract';shutil.copy2(args.executable,binary)
        queue=[(args.executable.resolve(),binary)];seen=set()
        while queue:
            original,local=queue.pop(0)
            if original in seen:continue
            seen.add(original)
            if sys.platform=='darwin':
                output=subprocess.check_output(['otool','-L',str(original)],text=True)
                dependencies=[line.strip().split(' (')[0] for line in output.splitlines()[1:]]
            else:
                output=subprocess.check_output(['ldd',str(original)],text=True)
                dependencies=re.findall(r'=> (/\S+)',output)
            for dependency in dependencies:
                dep=Path(dependency)
                if not dep.is_absolute() or not dep.exists():continue
                if sys.platform=='darwin' and (dependency.startswith('/usr/lib/') or dependency.startswith('/System/')):continue
                if sys.platform!='darwin' and dep.name.startswith(('libc.so','libm.so','libpthread.so','libdl.so','librt.so','ld-linux')):continue
                copied=libdir/dep.name
                if not copied.exists():shutil.copy2(dep.resolve(),copied)
                queue.append((dep.resolve(),copied))
                if sys.platform=='darwin':
                    rewritten=('@executable_path/../lib/' if local==binary else '@loader_path/')+dep.name
                    subprocess.run(['install_name_tool','-change',dependency,rewritten,str(local)],check=True)
            if sys.platform=='darwin':
                if local!=binary:subprocess.run(['install_name_tool','-id','@loader_path/'+local.name,str(local)],check=True)
                subprocess.run(['codesign','--force','--sign','-',str(local)],check=True)
    data=target/'tessdata';data.mkdir(exist_ok=True)
    for name in ('eng.traineddata','osd.traineddata'):
        source=args.tessdata/name
        if source.exists():shutil.copy2(source,data/name)
    if not (data/'eng.traineddata').exists():raise SystemExit('English tessdata missing')
    executable = target/'tesseract.exe' if sys.platform=='win32' else target/'bin/tesseract'
    subprocess.run([str(executable), '--version'], check=True)
    print('Staged native portable OCR:',target)


if __name__=='__main__':main()
