"""Renderer 12 adds frozen plans, standards and coverage; renderers 1–11 stay frozen."""
import hashlib
from . import ledger as L, history, reporting_v11
from .persistence import atomic_bytes
from evidence_review import coverage, plans


def render(work, project=None, relative_root='../..', output_directory='outputs'):
    output=reporting_v11.render(work,project,relative_root,output_directory)
    output.update(coverage.exports(work))
    plan=plans.active(work)
    notice=('本轮采用冻结计划版本 '+plan['id']+'；计划确认仅授权程序范围，不确认审计结论。' if plan else
            '本历史轮次未建立检查计划；新视图不追认计划或检查覆盖。')
    links='[检查项覆盖](coverage-checks.md) · [方案覆盖](coverage-scheme.md)'
    if plan:links+=' · [检查计划](inspection-plan.md) · [标准表](standards.md) · [计划内线索](discovery-clues.md) · [计划外发现](out-of-plan.md)'
    for name in ('review.md','handoff.md'):output[name]+='\n\n## 检查计划与覆盖矩阵\n\n'+notice+'\n\n'+links+'\n'
    return output


def export_compact(project,ledger,api):
    directory=project/'outputs'/('compact-'+L.uid());directory.mkdir(parents=True,exist_ok=False)
    files={};order=ledger.get('run_order',[ledger['latest_run_id']])
    for rid in order:
        work=history.as_of(ledger,rid)
        for name,content in render(work,relative_root='../../..',output_directory=directory.relative_to(project).as_posix()).items():
            path=directory/rid/name;data=content.encode('utf-8');atomic_bytes(path,data)
            files[path.relative_to(project).as_posix()]=hashlib.sha256(data).hexdigest()
    L.atomic_json(directory/'manifest.json',dict(renderer_version=12,derived_from_ledger_sha256=ledger['integrity_sha256'],
        tool='review.py export --compact --renderer 12',tool_version='renderer-12',parameters={'runs':order,'renderer':12},
        created_at=L.now(),files=files,limitation='Derived view; no amendment of history or audit confirmation'))
    return dict(state='completed',compact_directory=str(directory),manifest=str(directory/'manifest.json'),renderer_version=12,ledger_changed=False,history_changed=False)
