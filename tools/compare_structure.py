#!/usr/bin/env python3
"""Run old/new local code on identical frozen fixtures; no source/fixture rewriting."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

RUNNER=r'''
import contextlib,io,itertools,json,sys,uuid
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import review as R
counter=itertools.count(1)
R.L.uid=lambda:str(uuid.UUID(int=next(counter)))
R.L.now=lambda:'2026-11-04T00:00:00+00:00'
project=Path(sys.argv[2]);request=Path(sys.argv[3]);result={}
for command,extra in [('begin',['--request',str(request)]),('inspect',[])]:
    sys.argv=[str(Path(sys.argv[1])/'review.py'),command,'--project',str(project),*extra]
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream): status=R.main()
    if status: raise RuntimeError('Comparison command failed: '+command)
    result[command]=json.loads(stream.getvalue())
print(json.dumps(result,ensure_ascii=False))
'''


def normalized(value, project):
    if isinstance(value,dict): return {k:normalized(v,project) for k,v in value.items()}
    if isinstance(value,list): return [normalized(v,project) for v in value]
    if isinstance(value,str): return value.replace(str(project),'$PROJECT')
    return value


def compare(baseline, candidate, cases=('financial','contract','controls','responsibility')):
    baseline,candidate=Path(baseline).resolve(),Path(candidate).resolve();results=[]
    with tempfile.TemporaryDirectory(prefix='structure-compare-') as tmp:
        tmp=Path(tmp).resolve()
        for case in cases:
            sources=candidate/'tests/cases'/case/'sources'
            request=tmp/(case+'-request.json')
            request.write_text(json.dumps(dict(goal='Synthetic structure-only comparison',modes=['query'],source_roots=[str(sources)])),encoding='utf-8')
            packets=[]
            for index,root in enumerate((baseline,candidate)):
                project=tmp/(case+'-'+str(index))
                process=subprocess.run([sys.executable,'-B','-c',RUNNER,str(root/'evidence-reviewer/scripts'),str(project),str(request)],capture_output=True,text=True,encoding='utf-8')
                if process.returncode: raise ValueError('Before/after execution failed: '+process.stderr[-3000:])
                packets.append(normalized(json.loads(process.stdout),project))
            if packets[0]!=packets[1]:
                raise ValueError('Before/after packets differ for '+case)
            sources=packets[1]['inspect']['sources']
            results.append(dict(case=case,files=len(sources),units=sum(len(s['units']) for s in sources),
                                source_sha256=[s['version']['sha256'] for s in sources]))
    return dict(ok=True,cases=results,excluded_fields=[],
                controlled_fields=['L.uid: deterministic UUID sequence, with all reference fields still compared',
                                   'L.now: fixed clock, with all timestamp fields still compared'],
                normalized_fields=['Absolute project-root prefix in string values -> $PROJECT'],
                unchanged_checks='All other begin/inspect fields, original hashes, text, locators, formulas, caches, states, limits and versions are compared')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    try:
        result=compare(args.baseline,args.candidate);print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=False));return 1


if __name__=='__main__': raise SystemExit(main())
