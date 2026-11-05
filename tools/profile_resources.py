#!/usr/bin/env python3
"""Measure synthetic CLI workloads locally; no network and no audit evaluation.

RSS is the actual high-water mark of each isolated Python command, including
interpreter overhead. It is not an arbitrary-input memory bound.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def worker():
    metrics, script, *arguments = sys.argv[2:]
    sys.path.insert(0, str(Path(script).parent))
    sys.argv = [script, *arguments]
    start = time.perf_counter(); code = 0
    try:
        runpy.run_path(script, run_name='__main__')
    except SystemExit as exc:
        code = exc.code or 0
    finally:
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak = int(rss if sys.platform == 'darwin' else rss * 1024)
            state = 'measured'
        except ImportError:
            peak = None; state = '未验证：resource unavailable on this platform'
        Path(metrics).write_text(json.dumps(dict(peak_rss_bytes=peak, rss_status=state,
            elapsed_seconds=time.perf_counter()-start, exit_code=code)), encoding='utf-8')
    raise SystemExit(code)


def profile(runtime, directory, sources, bounded):
    directory.mkdir(); project = directory/'project'; cli = runtime/'evidence-reviewer/scripts/review.py'
    request = directory/'request.json'
    request.write_text(json.dumps(dict(goal='Synthetic resource measurement only',modes=['coverage'],source_roots=[str(sources)])),encoding='utf-8')
    records = []
    def call(command, *arguments):
        index = len(records); stem = directory/f'{index:02}-{command}'
        argv = [sys.executable,'-B',str(Path(__file__).resolve()),'--worker',str(stem.with_suffix('.metrics.json')),
                str(cli),command,'--project',str(project),*map(str,arguments)]
        with stem.with_suffix('.stdout.json').open('wb') as out, stem.with_suffix('.stderr.txt').open('wb') as err:
            result = subprocess.run(argv,stdout=out,stderr=err)
        row = json.loads(stem.with_suffix('.metrics.json').read_text())
        row.update(command=command,arguments=list(map(str,arguments)),stdout_bytes=stem.with_suffix('.stdout.json').stat().st_size,
                   stderr_bytes=stem.with_suffix('.stderr.txt').stat().st_size,returncode=result.returncode)
        records.append(row)
        if result.returncode:raise RuntimeError('Measured command failed; retain logs: '+str(stem))
        return json.loads(stem.with_suffix('.stdout.json').read_text(encoding='utf-8'))
    call('begin','--request',request)
    if bounded:
        packet=call('inspect','--summary','--limit','20');vid=packet['sources'][0]['source_version_id']
        page=call('read','--version',vid,'--limit','20');unit=page['units'][0];uid=unit['unit_id'];quote=unit['text']
    else:
        packet=call('inspect');src=packet['sources'][0];vid=src['version']['id'];unit=src['units'][0];uid=unit['id'];quote=unit['text']
        del packet
    call('search','--pattern','Synthetic item','--purpose','Synthetic resource workload',*(['--limit','10'] if bounded else []))
    scaffold=call('scaffold','--version',vid,'--unit',uid)
    assessment_path=Path(scaffold['assessment']);assessment=json.loads(assessment_path.read_text(encoding='utf-8'))
    assessment['evidence'][0].update(verbatim_quote=quote,reviewer_summary='Synthetic engineering measurement only',reading_method='read first synthetic unit',verification_state='extracted_only',limitations=['No business judgment'])
    assessment['tasks']=[dict(key='scope',objective='Synthetic workload measurement',procedure='Read one fixture unit and measure commands',population='generated synthetic files',sampling_basis='engineering check, not a business sample',actual_scope='one fixture unit; search and deterministic CLI execution',uncovered_scope='business interpretation of remaining materials',execution_state='partial',result='undetermined',basis='No audit judgment in this resource measurement',next_step='Professional review if used for business',source_version_ids=[vid],record_ids=['evidence_1'])]
    assessment['answers']=[dict(text='Measured synthetic workload, no audit conclusion.',evidence_ids=['evidence_1'],task_ids=['scope'])]
    assessment['review_checks']=[dict(target_id='scope',reason='Resource test boundary',result='Partial synthetic procedure only; no claim of audit completeness',evidence_ids=['evidence_1'])]
    assessment_path.write_text(json.dumps(assessment),encoding='utf-8')
    call('check-assessment','--assessment',assessment_path);final=call('finalize','--assessment',assessment_path)
    call('validate');call('export')
    outputs={p.name:p.stat().st_size for p in (project/'outputs'/final['run_id']).iterdir()}
    ledger=json.loads((project/'ledger/ledger.json').read_text(encoding='utf-8'))
    return dict(runtime_cli_sha256=hashlib.sha256(cli.read_bytes()).hexdigest(),commands=records,outputs=outputs,
                source_versions=len(ledger['units']),units=sum(map(len,ledger['units'].values())),
                ledger_bytes=(project/'ledger/ledger.json').stat().st_size)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():raise ValueError('Choose a new output directory')
    out.mkdir(parents=True)
    sys.path.insert(0,str(ROOT/'tests'))
    from generate_usability_fixtures import generate
    spec_path=ROOT/'tests/usability-fixtures/project-spec.json';spec=json.loads(spec_path.read_text(encoding='utf-8'))
    input_hashes=generate(out/'sources',spec)
    result=dict(environment=dict(platform=platform.platform(),python=sys.version),
                spec_sha256=hashlib.sha256(spec_path.read_bytes()).hexdigest(),input_hashes=input_hashes,
                limitation='One synthetic workload; not a memory bound, host/model test or audit accuracy evaluation')
    if args.baseline:
        baseline=args.baseline.resolve();manifest=json.loads((baseline/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
        for rel,sha in manifest['files'].items():
            if hashlib.sha256((baseline/rel).read_bytes()).hexdigest()!=sha:raise ValueError('Baseline manifest mismatch: '+rel)
        result['baseline_manifest_sha256']=hashlib.sha256((baseline/'RELEASE_MANIFEST.json').read_bytes()).hexdigest()
        result['baseline']=profile(baseline,out/'baseline',out/'sources',False)
    result['candidate']=profile(ROOT,out/'candidate',out/'sources',True)
    path=out/'resource-profiling.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(report=str(path),environment=result['environment'],candidate_outputs=result['candidate']['outputs']),ensure_ascii=False))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker()
    else:main()
