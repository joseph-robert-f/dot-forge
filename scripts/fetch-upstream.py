#!/usr/bin/env python3
"""Explicit opt-in fetch or import of the pinned GPL upstream source.

Never run during generation. No application binary is downloaded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Import an already obtained matching source checkout')
    parser.add_argument('--git',action='store_true',help='Explicitly fetch from the official Git repository')
    parser.add_argument('--output',type=Path,default=ROOT/'vendor/upstream')
    args=parser.parse_args()
    if bool(args.source)==args.git:parser.error('choose exactly one of --source or --git')
    if args.output.exists():parser.error('output must not already exist')
    pin=json.loads((ROOT/'upstream.lock.json').read_text())
    with tempfile.TemporaryDirectory(prefix='printkit-upstream-') as temp:
        source=args.source
        if args.git:
            source=Path(temp)/'checkout'
            subprocess.run(['git','init',str(source)],check=True)
            subprocess.run(['git','-C',str(source),'fetch','--depth=1',pin['repository']+'.git',pin['commit']],check=True)
            subprocess.run(['git','-C',str(source),'checkout','--detach','FETCH_HEAD'],check=True)
            actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
            if actual!=pin['commit']:raise SystemExit('commit mismatch')
        stage=Path(temp)/'selected';stage.mkdir()
        for name,digest in pin['files'].items():
            path=source/name
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise SystemExit('pinned source mismatch: '+name)
            dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(stage,args.output)
    print(json.dumps({'status':'verified','commit':pin['commit'],'files':len(pin['files'])}))

if __name__=='__main__':main()
