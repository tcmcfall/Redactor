# SPDX-License-Identifier: GPL-3.0-or-later
"""Release-time staging of installed native OCR into the portable folder.

This developer tool is not imported or called by the application. On Unix it
copies non-system dependencies; macOS install names are rewritten locally.
"""
import argparse
import hashlib
import json
import tarfile
import urllib.request
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]



def preserve_macos_sources(originals, target):
    """Keep exact installed Homebrew recipes, verified sources and notices."""
    sources=target/'source';notices=target/'licenses'
    sources.mkdir(exist_ok=True);notices.mkdir(exist_ok=True)
    kegs=set()
    for original in originals:
        if 'Cellar' in original.parts:
            index=original.parts.index('Cellar')
            kegs.add(Path(*original.parts[:index+3]))
    records=[]
    for keg in sorted(kegs):
        name=keg.parent.name
        recipe=keg/'.brew'/f'{name}.rb'
        formula=recipe.read_text()
        url=re.search(r'^\s*url "([^"\n]+)"',formula,re.M)
        digest=re.search(r'^\s*sha256 "([a-f0-9]{64})"',formula,re.M)
        if not url or not digest:raise RuntimeError(f'Cannot identify source checksum in {recipe}')
        urls=[url.group(1),*re.findall(r'^\s*mirror "([^"\n]+)"',formula,re.M)]
        archive=sources/f'{name}-{keg.name}.source'
        for address in urls:
            try:
                request=urllib.request.Request(address,headers={'User-Agent':'Redactor-native-source-builder'})
                with urllib.request.urlopen(request,timeout=90) as response,archive.open('wb') as output:
                    shutil.copyfileobj(response,output)
                with archive.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
                if actual!=digest.group(1):raise ValueError('Native source checksum mismatch')
                break
            except Exception:
                archive.unlink(missing_ok=True)
                if address==urls[-1]:raise
        shutil.copy2(recipe,sources/f'{name}-{keg.name}.rb')
        count=0
        with tarfile.open(archive,'r:*') as package:
            for member in package.getmembers():
                relative=Path(member.name)
                if not member.isfile() or member.size>10_000_000 or relative.is_absolute() or '..' in relative.parts:continue
                if not relative.name.lower().startswith(('license','copying','copyright','notice')):continue
                destination=notices/name/relative
                destination.parent.mkdir(parents=True,exist_ok=True)
                with package.extractfile(member) as source,destination.open('wb') as output:shutil.copyfileobj(source,output)
                count+=1
        if not count:raise RuntimeError(f'No license notices found for {name}; review before distributing')
        records.append({'name':name,'installed_version':keg.name,'source_url':address,'sha256':actual,'notices':count})
    (sources/'MANIFEST.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


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
                if sys.platform=='darwin' and dependency.startswith('@'):
                    def expand(value):
                        return value.replace('@loader_path',str(original.parent)).replace('@executable_path',str(args.executable.resolve().parent))
                    candidates=[Path(expand(dependency))]
                    if dependency.startswith('@rpath/'):
                        commands=subprocess.check_output(['otool','-l',str(original)],text=True)
                        rpaths=re.findall(r'cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset',commands)
                        suffix=dependency[len('@rpath/'):]
                        candidates=[Path(expand(value))/suffix for value in rpaths]+[original.parent/suffix]
                    dep=next((candidate for candidate in candidates if candidate.is_file()),dep)
                if not dep.is_absolute() or not dep.exists():
                    if sys.platform=='darwin' and dependency.startswith('@'):
                        raise RuntimeError(f'Cannot resolve portable OCR dependency {dependency} from {original}')
                    continue
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
    if sys.platform=='darwin':preserve_macos_sources(seen,target)
    executable = target/'tesseract.exe' if sys.platform=='win32' else target/'bin/tesseract'
    subprocess.run([str(executable), '--version'], check=True)
    print('Staged native portable OCR:',target)


if __name__=='__main__':main()
