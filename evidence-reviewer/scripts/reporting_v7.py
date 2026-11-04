"""Portable derived Markdown views; existing renderers 1–6 stay byte-compatible."""
import copy
import hashlib
import re
from urllib.parse import quote

import ledger as L
from persistence import atomic_bytes

ROOT_TOKEN = '__EVIDENCE_PROJECT_ROOT__'


def render(work, project=None, relative_root='../..', output_directory='outputs'):
    from reporting import render as previous
    result = previous(work, ROOT_TOKEN)
    def link(match):
        suffix = match.group(1).replace('\\', '/').lstrip('/')
        if suffix.startswith('outputs/'):
            suffix = output_directory + '/' + suffix[len('outputs/'):]
        return '](<' + quote(relative_root + '/' + suffix, safe='/.-_~') + '>)'
    return {name: re.sub(r'\]\(<' + ROOT_TOKEN + r'[\\/]([^<>\n]*)>\)', link, text)
            for name, text in result.items()}


def export_portable(project, ledger, api):
    """Explicit export only. No ledger/history/pointer changes, new directory each time."""
    import history as H
    work = L.thaw(ledger)
    api.check_files(project, work, check_outputs=True)
    directory = project / 'outputs' / ('portable-' + L.uid())
    directory.mkdir(parents=True, exist_ok=False)
    files = {}
    for run_id in ledger.get('run_order', [ledger['latest_run_id']]):
        historical = H.as_of(ledger, run_id)
        for name, text in render(historical, relative_root='../../..', output_directory=directory.relative_to(project).as_posix()).items():
            path = directory / run_id / name
            content = text.encode('utf-8')
            atomic_bytes(path, content)
            files[path.relative_to(project).as_posix()] = hashlib.sha256(content).hexdigest()
    manifest = dict(renderer_version=7, derived_from_ledger_sha256=ledger['integrity_sha256'],
                    derived_from_engine=work['run'].get('skill_version'),
                    tool='review.py export --portable', tool_version='portable-renderer-7',
                    parameters={'relative_to': 'containing Markdown file', 'runs': list(ledger['runs'])},
                    created_at=L.now(), files=files,
                    historical_outputs={r['path']:r['sha256'] for r in work['records'].values() if r['kind']=='OutputRecord'},
                    limitation='Derived view only; does not amend the authoritative ledger or confirm audit conclusions')
    L.atomic_json(directory / 'manifest.json', manifest)
    return dict(state='completed', portable_directory=str(directory), manifest=str(directory/'manifest.json'),
                renderer_version=7, ledger_changed=False, history_changed=False)
