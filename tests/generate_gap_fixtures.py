#!/usr/bin/env python3
"""Deterministic synthetic gap inputs; legacy outputs come from a verified baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from generate_stage6_cases import pdf_bytes

ROOT = Path(__file__).resolve().parents[1]
LINES = ['合成材料，非真实业务。', '合成收款凭证 R-2040-01',
         '合同：合成服务合同 HT-2040-01', '收款金额：人民币 12345.67 元',
         '收款日期：2040-03-15', '本页不含真实签名、印章或银行信息。']


def generate(folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    asset = json.loads((ROOT/'tests/gap-fixtures/receipt-raster.json').read_text(encoding='utf-8'))
    (folder/'合成 收款凭证.pdf').write_bytes(pdf_bytes([asset]))
    (folder/'合成 凭证目录.txt').write_text('合成材料，非真实业务。核查合成服务合同 HT-2040-01 的收款凭证。\n', encoding='utf-8', newline='')
    return folder


def legacy(baseline, destination):
    manifest = json.loads((baseline/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    for rel, sha in manifest['files'].items():
        if hashlib.sha256((baseline/rel).read_bytes()).hexdigest() != sha:
            raise ValueError('Baseline differs from manifest: '+rel)
    code = r'''
import hashlib,itertools,json,sys,uuid
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(sys.argv[1])/'evidence-reviewer/scripts'))
import review as R
from core import ledger as L,history as H
base=Path(sys.argv[2]);sources=base/'input';sources.mkdir();(sources/'synthetic.txt').write_text('Synthetic ledger amount: 123.45\n',encoding='utf-8')
seq=itertools.count(1);L.uid=lambda:str(uuid.UUID(int=next(seq)));L.now=lambda:'2026-11-06T00:00:00+00:00'
request=base/'request.json';request.write_text(json.dumps(dict(goal='Synthetic renderer 10 with an old unreviewed gap',modes=['coverage'],source_roots=[str(sources)])),encoding='utf-8')
project=base/'project';R.begin(NS(project=project,request=request))
hit=R.search(NS(project=project,pattern='absent',purpose='Synthetic text-only search',version=None,limit=None))
raw=R.load(project/'staging/working.json');raw['project']['source_roots']=['/synthetic-input'];raw['run']['tool_versions']['python']='frozen synthetic baseline'
for row in raw['records'].values():
 if row['kind']=='Source':row['known_paths']=['/synthetic-input/synthetic.txt']
vid=next(iter(raw['units']));u=raw['units'][vid][0]
a=dict(tasks=[dict(key='t',objective='Synthetic declared partial program',procedure='Register text only',population='one file',sampling_basis='all',actual_scope='extracted text',uncovered_scope='no business judgment',execution_state='partial',result='undetermined',basis='Engineering fixture only',next_step='Human review',source_version_ids=[vid],record_ids=[])],evidence=[dict(key='e',source_version_id=vid,unit_id=u['id'],verbatim_quote=u['text'],reviewer_summary='Synthetic only',reading_method='text',verification_state='extracted_only',limitations=[])],gaps=[dict(key='g',task_ids=['t'],claim_ids=[],expected_fact='Synthetic unverified receipt',search_record_ids=[hit['search_record_id']],reason_insufficient='Legacy text-only search',minimal_request='Legacy synthetic request',state='open')],answers=[dict(text='Synthetic statement only; no audit conclusion.',evidence_ids=['e'],task_ids=['t'])],review_checks=[dict(target_id='t',reason='Engineering coverage',result='Declared partial; no business judgment',evidence_ids=['e'])])
w=L.materialize(raw,a);w['run'].update(state='completed',finished_at=L.now(),unfinished_steps=[])
exports=L.render(w,Path('/synthetic-old-project'))
for name,body in exports.items():L.add(w,'OutputRecord',dict(run_id=w['run']['id'],output_kind=name.split('.')[0],path='outputs/'+w['run']['id']+'/'+name,renderer_version=10,sha256=hashlib.sha256(body.encode()).hexdigest(),source_role='workpaper_or_draft',actual_confirmation_status='unconfirmed',evidence_ids=[]))
frozen=H.signed(L.freeze(w));L.validate_records(L.thaw(frozen))
files={'outputs/'+w['run']['id']+'/'+name:body for name,body in exports.items()}
print(json.dumps(dict(renderer=10,ledger=frozen,files=files,source_path=raw['records'][vid]['local_snapshot'],source_text='Synthetic ledger amount: 123.45\n',pointer=dict(run_id=w['run']['id'],ledger_sha256=frozen['integrity_sha256'],files=list(files))),ensure_ascii=False,indent=2))
'''
    with tempfile.TemporaryDirectory(prefix='gap-baseline-') as tmp:
        data = subprocess.check_output([sys.executable, '-B', '-c', code, str(baseline), tmp])
    destination.write_bytes(data)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    args=parser.parse_args()
    if args.baseline: legacy(args.baseline.resolve(), args.output)
    else: generate(args.output)
