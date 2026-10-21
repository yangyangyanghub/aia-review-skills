#!/usr/bin/env python3
"""Install the complete AIA skill suite without replacing existing folders."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys

def files(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target',type=Path,required=True)
    ap.add_argument('--check',action='store_true',help='Only compare installed files, with no writes')
    args=ap.parse_args()
    source=Path(__file__).resolve().parent/'skills'
    skills=sorted(p for p in source.iterdir() if p.is_dir() and (p/'SKILL.md').is_file())
    if len(skills)!=15:
        ap.exit(2,'Expected the complete 15-skill bundle; aborting before writes.\n')
    target=args.target.expanduser().resolve()
    if args.check:
        problems=[]
        for s in skills:
            d=target/s.name
            if not d.is_dir() or files(s)!=files(d):
                problems.append(s.name)
        if problems:
            ap.exit(2,'Missing or different installed skills: '+', '.join(problems)+'\n')
        print('15 installed skills match source files (excluding Python caches).')
        return 0
    collisions=[s.name for s in skills if (target/s.name).exists() or (target/s.name).is_symlink()]
    if collisions:
        ap.exit(2,'Existing skills preserved; nothing installed. Collisions: '+', '.join(collisions)+'\n')
    created=[]
    try:
        target.mkdir(parents=True,exist_ok=True)
        for s in skills:
            d=target/s.name
            # mkdir is exclusive: do not merge into a folder created after preflight.
            d.mkdir()
            created.append(d)
            shutil.copytree(s,d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for s in skills:
            if files(s)!=files(target/s.name):
                raise OSError('Post-copy mismatch: '+s.name)
    except OSError as exc:
        for d in reversed(created):
            shutil.rmtree(d)
        ap.exit(2,f'Installation rolled back for folders created by this run: {exc}\n')
    print(f'Installed and compared {len(skills)} skills in {target}')
    return 0

if __name__=='__main__':
    sys.exit(main())
