#!/usr/bin/env python3
"""Freeze synthetic old ledgers using the pinned, local pre-stage-1 Git commit.
No business inputs, no network; run explicitly, never from the test suite.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '51149fb'


def main():
    with tempfile.TemporaryDirectory(prefix='legacy-fixture-') as tmp:
        scripts = Path(tmp) / 'scripts'
        scripts.mkdir()
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE,
                                        'evidence-reviewer/scripts'], cwd=ROOT, text=True).splitlines()
        for name in names:
            (scripts / Path(name).name).write_bytes(subprocess.check_output(['git', 'show', BASELINE + ':' + name], cwd=ROOT))
        code = r'''
import copy, hashlib, itertools, json, sys, uuid
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, sys.argv[1])
import ledger as L, history as H, review as R
base = Path(sys.argv[2]); sources = base/'sources'; sources.mkdir()
(sources/'synthetic.txt').write_text('Synthetic recorded amount: 123.45\n', encoding='utf-8')
seq=itertools.count(1); L.uid=lambda:str(uuid.UUID(int=next(seq))); L.now=lambda:'2026-11-04T00:00:00+00:00'
request=base/'request.json'; request.write_text(json.dumps(dict(goal='Synthetic legacy compatibility', modes=['query'], source_roots=[str(sources)])),encoding='utf-8')
project=base/'project'; R.begin(NS(project=project,request=request)); raw=R.load(project/'staging/working.json')
raw['project']['source_roots']=['/synthetic-fixture-materials']
raw['run']['tool_versions']['python']='synthetic baseline environment'
for r in raw['records'].values():
    if r['kind']=='Source': r['known_paths']=['/synthetic-fixture-materials/synthetic.txt']
vid=next(iter(raw['units'])); u=raw['units'][vid][0]
a=dict(evidence=[dict(key='e',source_version_id=vid,unit_id=u['id'],verbatim_quote=u['text'],reviewer_summary='Synthetic only',reading_method='text',verification_state='extracted_only',limitations=[])],answers=[dict(text='Synthetic statement only; no audit conclusion.',evidence_ids=['e'])])
fixtures=[]
for renderer in range(1,7):
    w=L.materialize(raw,a); w['run'].update(state='completed',finished_at=L.now(),unfinished_steps=[])
    w['_renderer_version']=renderer
    exports=L.render(w,Path('/synthetic-old-project')); w.pop('_renderer_version')
    for name,body in exports.items():
        L.add(w,'OutputRecord',dict(run_id=w['run']['id'],output_kind=name.split('.')[0],path='outputs/'+w['run']['id']+'/'+name,renderer_version=renderer,sha256=hashlib.sha256(body.encode()).hexdigest(),source_role='workpaper_or_draft',actual_confirmation_status='unconfirmed',evidence_ids=[]))
    w['assessment_sha256']=L.checksum(a)
    frozen=H.signed(L.freeze(w)); L.validate_records(L.thaw(frozen))
    variants=[frozen]
    if renderer==6: variants.append(H.signed(H.upgrade(frozen)))
    for ledger in variants:
        L.thaw(ledger)
        files={r['path']:exports[r['output_kind']+'.md'] for r in L.thaw(ledger)['records'].values() if r['kind']=='OutputRecord'}
        fixtures.append(dict(renderer=renderer,ledger=ledger,files=files,source_path=raw['records'][vid]['local_snapshot'],source_text='Synthetic recorded amount: 123.45\n',pointer=dict(run_id=w['run']['id'],ledger_sha256=ledger['integrity_sha256'],files=list(files))))
print(json.dumps(fixtures,ensure_ascii=False,indent=2))
'''
        content = subprocess.check_output([sys.executable, '-B', '-c', code, str(scripts), tmp], cwd=ROOT)
    fixture = ROOT / 'tests/platform-fixtures/legacy.json'
    fixture.write_bytes(content)
    (ROOT / 'tests/input-sha256-stage1.json').write_text(json.dumps({
        'frozen_on': '2026-11-04', 'baseline_commit': BASELINE,
        'files': {fixture.relative_to(ROOT).as_posix(): hashlib.sha256(content).hexdigest()},
    }, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
