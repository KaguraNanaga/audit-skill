#!/usr/bin/env python3
"""Copy one frozen case and the released skill to a fresh evaluation input.

This is packaging, NOT an access-control sandbox or a model runner. Expected
answers, generators and development history never enter the package.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def checked_file(root, relative, expected_hash):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe manifest path')
    path = root / rel
    if path.resolve() != path.absolute() or not path.is_file():
        raise ValueError('Symlink or missing input: ' + relative)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Frozen input differs: ' + relative)
    return data


def prepare(case, destination, root=ROOT):
    root, destination = Path(root).absolute(), Path(destination).absolute()
    if case not in {f'stage6-{i:02}' for i in range(1, 7)} | {'stage7-06'}:
        raise ValueError('Unknown frozen evaluation case')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Destination already exists; choose a fresh directory')
    if destination.parent.resolve() != destination.parent.absolute():
        raise ValueError('Destination ancestors must not be symlinks')
    if not destination.parent.is_dir():
        raise ValueError('Create destination parent first')
    release = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    freeze = json.loads((root / ('tests/input-sha256-stage7.json' if case=='stage7-06' else 'tests/input-sha256-stage6.json')).read_text(encoding='utf-8'))
    prefix = f'tests/cases/{case}/'
    files = {}
    for rel, sha in release['files'].items():
        if rel.startswith('evidence-reviewer/'):
            files['input/' + rel] = checked_file(root, rel, sha)
    for rel, sha in freeze['files'].items():
        if rel.startswith(prefix):
            inner = rel[len(prefix):]
            if inner != 'request.md' and not inner.startswith('sources/'):
                raise ValueError('Unexpected case input')
            files['input/' + inner] = checked_file(root, rel, sha)
    if 'input/request.md' not in files or 'input/evidence-reviewer/SKILL.md' not in files:
        raise ValueError('Incomplete evaluation input')
    actual = {p.relative_to(root).as_posix() for p in (root / prefix).rglob('*') if p.is_file() or p.is_symlink()}
    frozen = {rel for rel in freeze['files'] if rel.startswith(prefix)}
    if actual != frozen:
        raise ValueError('Case has missing or unfrozen inputs')
    metadata = {'case': case, 'package_version': release['package_version'], 'engine_version': release['engine_version'],
                'evaluation_status': '待执行', 'isolation_enforced': False,
                'note': 'Packaging only. Host must restrict access; remove version/run identifiers from scoring copy.',
                'files': {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(files.items())}}
    destination.mkdir()
    try:
        for rel, data in files.items():
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (destination / 'administrator.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {'case': case, 'input_directory': str(destination / 'input'), 'copied_files': len(files), 'evaluation_status': '待执行', 'isolation_enforced': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.output), ensure_ascii=False))
