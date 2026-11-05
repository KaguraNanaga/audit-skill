"""Create an intentionally incomplete assessment from real registered IDs."""
from pathlib import Path
from . import ledger as L
from .persistence import atomic_bytes


def run(args,api):
    L.require(1<=args.limit<=100,'Scaffold limit must be 1..100')
    project=args.project.resolve()
    with L.lock(project):
        work=api.get_work(project);api.check_files(project,work)
        versions=args.version if args.version is not None else list(work['run'].get('active_source_version_ids',work['run']['source_version_snapshot']))
        L.require(set(versions)<=set(work['units']),'Unknown scaffold version')
        wanted=set(args.unit or []);all_units={u['id'] for v in versions for u in work['units'][v]}
        L.require(wanted<=all_units,'Unknown unit or unit outside selected versions')
        candidates=[(v,u) for v in versions for u in work['units'][v] if not wanted or u['id'] in wanted]
        selected=candidates[:args.limit]
        assessment=dict(evidence=[dict(key=f'evidence_{i}',source_version_id=v,unit_id=u['id'],verbatim_quote='',reviewer_summary='',reading_method=None,verification_state=None,limitations=[]) for i,(v,u) in enumerate(selected,1)],
                        answers=[dict(text='',evidence_ids=[],calculation_ids=[],rule_ids=[],task_ids=[])],limitations=[])
        for evidence,(_,unit) in zip(assessment['evidence'],selected):
            if unit['locator'].get('unit')=='table_query_derived':
                evidence.update(query_id=unit['locator']['query_id'],result_locator=unit['locator']['result_locator'])
        if work.get('update_context'):
            assessment.update(screening=[dict(change_id=c['id'],topics=[],new_matters='',scope_decision=None,basis='',affected_ids=[]) for c in work['run']['changes']],
                impact_review=[dict(target_id=eid,decision=None,basis='',evidence_ids=[],source_version_ids=[],calculation_ids=[],search_record_ids=[]) for eid in work['update_context']['candidate_ids']])
        out=args.out.expanduser().resolve() if args.out else project/'assessment.json'
        L.require(out.parent==project and out.suffix=='.json','Scaffold output must be a new JSON file directly inside the project')
        help_path=out.with_suffix('.README.md')
        L.require(not out.exists() and not out.is_symlink() and not help_path.exists() and not help_path.is_symlink(),'Scaffold never overwrites an existing assessment or instructions')
        instructions='''# 评估骨架填写说明

此文件只预填真实ID，没有完成审查或形成结论。JSON中没有注释字段。

1. 实际读取所选单元和相关上下文，填写逐字摘录、概括、读取方法及核验状态；删除不采用的空Evidence。
2. 图像和OCR命中回到原页，实际查看后登记observations。骨架不会伪造viewed或业务判断。
3. 填写答案和真实依据。需要任务、主张、计算时按assessment接口新增；判断字段留空的骨架应被check-assessment拒绝。
4. 更新轮次逐项填写screening、impact_review；实际延期和不受影响理由由执行会话判断。
5. 选择范围及截断见下表。未纳入骨架不表示不相关、已读或无需核查。

'''
        instructions+=f'候选单元：{len(candidates)}；预填：{len(selected)}；未纳入：{len(candidates)-len(selected)}。\n\n'
        instructions+='| Evidence key | 来源版本 | 单元 | 状态 |\n|---|---|---|---|\n'
        for i,(v,u) in enumerate(selected,1):instructions+=f'| evidence_{i} | {v} | {u["id"]} | {u["state"]} |\n'
        atomic_bytes(out,L.encoded(assessment));atomic_bytes(help_path,instructions.encode('utf-8'))
        return dict(state='scaffold_created',assessment=str(out),instructions=str(help_path),selected_units=len(selected),omitted_units=len(candidates)-len(selected),reviewed=False,ready_to_submit=False)
