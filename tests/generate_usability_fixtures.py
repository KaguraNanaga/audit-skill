#!/usr/bin/env python3
"""Generate synthetic load inputs or freeze old renderers from a verified local baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def generate(folder, spec):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    for index in range(spec['documents']):
        body = ''.join(f'Synthetic item {index:03d}-{row:04d}: recorded value {row}.00; supporting attachment pending review.\n'
                       for row in range(spec['lines_per_document']))
        (folder / f'合成 材料 {index:03d}.txt').write_text(body, encoding='utf-8', newline='')
    (folder / '合成大表.csv').write_text('id,amount,category\n' + ''.join(
        f'{i},{i}.00,G{i%4}\n' for i in range(spec['table_rows'])), encoding='utf-8', newline='')
    (folder / '长单元.txt').write_text('中文🙂尾部定位' * spec['long_text_repeats'] + ' END_MARKER', encoding='utf-8', newline='')
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def legacy(baseline):
    manifest = json.loads((baseline / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    for rel, sha in manifest['files'].items():
        if hashlib.sha256((baseline / rel).read_bytes()).hexdigest() != sha:
            raise ValueError('Baseline differs from manifest: ' + rel)
    code = r'''
import copy,hashlib,itertools,json,sys,uuid
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(sys.argv[1])/'evidence-reviewer/scripts'))
import review as R
from core import ledger as L,history as H
base=Path(sys.argv[2]);sources=base/'input';sources.mkdir();(sources/'synthetic.txt').write_text('Synthetic ledger amount: 123.45\n',encoding='utf-8')
seq=itertools.count(1);L.uid=lambda:str(uuid.UUID(int=next(seq)));L.now=lambda:'2026-11-05T00:00:00+00:00'
request=base/'request.json';request.write_text(json.dumps(dict(goal='Synthetic old renderer compatibility',modes=['coverage'],source_roots=[str(sources)])),encoding='utf-8')
project=base/'project';R.begin(NS(project=project,request=request));raw=R.load(project/'staging/working.json')
raw['project']['source_roots']=['/synthetic-input'];raw['run']['tool_versions']['python']='frozen synthetic baseline'
for row in raw['records'].values():
 if row['kind']=='Source':row['known_paths']=['/synthetic-input/synthetic.txt']
vid=next(iter(raw['units']));u=raw['units'][vid][0]
a=dict(tasks=[dict(key='t',objective='Synthetic declared partial program',procedure='Register text only',population='one file',sampling_basis='one synthetic file',actual_scope='extracted text',uncovered_scope='no business judgment',execution_state='partial',result='undetermined',basis='Engineering fixture only',next_step='Human review',source_version_ids=[vid],record_ids=[])],evidence=[dict(key='e',source_version_id=vid,unit_id=u['id'],verbatim_quote=u['text'],reviewer_summary='Synthetic only',reading_method='text',verification_state='extracted_only',limitations=[])],answers=[dict(text='Synthetic statement only; no audit conclusion.',evidence_ids=['e'],task_ids=['t'])],review_checks=[dict(target_id='t',reason='Engineering coverage',result='Declared partial; no business judgment',evidence_ids=['e'])])
fixtures=[]
for renderer in (7,8,9):
 w=L.materialize(raw,a);w['run'].update(state='completed',finished_at=L.now(),unfinished_steps=[]);w['_renderer_version']=renderer
 exports=L.render(w,Path('/synthetic-old-project'));w.pop('_renderer_version')
 for name,body in exports.items():L.add(w,'OutputRecord',dict(run_id=w['run']['id'],output_kind=name.split('.')[0],path='outputs/'+w['run']['id']+'/'+name,renderer_version=renderer,sha256=hashlib.sha256(body.encode()).hexdigest(),source_role='workpaper_or_draft',actual_confirmation_status='unconfirmed',evidence_ids=[]))
 frozen=H.signed(L.freeze(w));L.validate_records(L.thaw(frozen))
 files={'outputs/'+w['run']['id']+'/'+name:body for name,body in exports.items()}
 fixtures.append(dict(renderer=renderer,ledger=frozen,files=files,source_path=raw['records'][vid]['local_snapshot'],source_text='Synthetic ledger amount: 123.45\n',pointer=dict(run_id=w['run']['id'],ledger_sha256=frozen['integrity_sha256'],files=list(files))))
print(json.dumps(fixtures,ensure_ascii=False,indent=2))
'''
    with tempfile.TemporaryDirectory(prefix='renderer-baseline-') as tmp:
        data = subprocess.check_output([sys.executable, '-B', '-c', code, str(baseline), tmp])
    (ROOT / 'tests/usability-fixtures/legacy-7-9.json').write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path)
    group.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if args.baseline: legacy(args.baseline.resolve())
    else:
        spec = json.loads((ROOT / 'tests/usability-fixtures/project-spec.json').read_text(encoding='utf-8'))
        print(json.dumps(generate(args.output, spec), ensure_ascii=False))

if __name__ == '__main__': main()
