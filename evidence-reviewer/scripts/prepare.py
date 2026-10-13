#!/usr/bin/env python3
"""Stage-0 inventory only. Does not extract or review evidence."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED = {'cache','ledger','outputs','expected','results','research','design','tests','audit-skill','node_modules','__pycache__'}
MODES = ('query','verify','coverage','draft','review','rules','update')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def inventory(root, exclusions):
    files, skipped, errors = [], [], []
    def rejected(rel):
        return any(s.startswith(('.', '~$')) or s in EXCLUDED for s in rel.parts) or any(rel == e or e in rel.parents for e in exclusions)
    def walk_error(error):
        errors.append({'path':str(error.filename),'error':str(error)})
    for current, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in sorted(dirs.copy()):
            p = Path(current)/name
            if p.is_symlink() or rejected(p.relative_to(root)):
                dirs.remove(name)
                skipped.append({'path':p.relative_to(root).as_posix(),'reason':'excluded_or_symlink'})
        dirs.sort()
        for name in sorted(names):
            p = Path(current)/name
            rel = p.relative_to(root)
            if p.is_symlink() or rejected(rel):
                skipped.append({'path':rel.as_posix(),'reason':'excluded_or_symlink'})
                continue
            try:
                before = p.stat()
                if not p.is_file():
                    skipped.append({'path':rel.as_posix(),'reason':'not_regular_file'})
                    continue
                sha = digest(p)
                after = p.stat()
                if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
                    raise OSError('File changed during hashing; retry with stable source')
                files.append({'relative_path':rel.as_posix(),'sha256':sha,'bytes':after.st_size,
                              'format':p.suffix.lower() or 'unknown','role':'unknown','read_state':'unread'})
            except OSError as e:
                errors.append({'path':rel.as_posix(),'error':str(e)})
    return files, skipped, errors

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path)
    p.add_argument('--goal',required=True)
    p.add_argument('--mode',choices=MODES,default='query')
    p.add_argument('--exclude',action='append',default=[])
    p.add_argument('--out',type=Path,required=True)
    a = p.parse_args()
    try:
        if not a.goal.strip(): raise ValueError('goal must not be empty')
        root = a.root.expanduser().resolve() if a.root else None
        out = a.out.expanduser().resolve()
        if root and (not root.is_dir() or out.is_relative_to(root)):
            raise ValueError('root must be a directory; out must be outside source root')
        if root is None and a.mode != 'rules': raise ValueError('root required except for rules mode')
        exclusions = [Path(x) for x in a.exclude]
        if any(x.is_absolute() or '..' in x.parts for x in exclusions):
            raise ValueError('exclude must be a relative path without ..')
        files, skipped, errors = inventory(root, exclusions) if root else ([],[],[])
        data = {'schema_version':'intake-0.1','implementation_stage':0,
                'captured_at':datetime.now(timezone.utc).isoformat(),
                'goal':a.goal,'mode':a.mode,'source_root':str(root) if root else None,
                'selected_main_version':None,'files':files,'excluded':skipped,'errors':errors,
                'inventory_status':'partial' if errors else 'complete',
                'review_status':'not_started','note':'Inventory is not file reading or audit coverage.'}
        out.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation: a failed rerun cannot replace originals or prior output.
        with out.open('x',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.write('\n')
        print(json.dumps({'out':str(out),'files':len(files),'errors':len(errors),'review_status':'not_started'},ensure_ascii=False))
        return 1 if errors else 0
    except (OSError,ValueError) as e:
        print(str(e),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
