"""Execution/clue contracts. Recorded coverage is not an audit opinion."""
from core import ledger as L, program_packs as P, standards
from . import plans

STATES={'已执行未发现异常','发现线索并已核实','发现线索待核实','无法执行','未选用'}
CATEGORIES={'被审计单位权限内','涉及上级或外部决策','情况记录'}


def refs(work,ids,kind,required=False):
    L.require(isinstance(ids,list) and all(isinstance(i,str) for i in ids) and len(ids)==len(set(ids)), '引用须为不重复 ID 列表')
    L.require(not required or bool(ids),'缺少必要的 '+kind+' 引用')
    rows=[work['records'].get(i,{}) for i in ids]
    L.require(all(r.get('kind')==kind for r in rows),'无效 '+kind+' 引用')
    return rows


def facts(work,ids,required=True):
    rows=refs(work,ids,'Evidence',required)
    for e in rows:
        v=work['records'][e['source_version_id']];s=work['records'][v['source_id']]
        L.require(s['role'] not in {'ai_analysis','template','workpaper'},'AI/模板/底稿不能独立证明线索事实')
    return rows


def validate(work):
    plans.validate(work)
    if not work['run'].get('discovery_version'): return
    current=plans.active(work)
    L.require(current is not None,'检查计划尚未冻结：等待用户确认并执行 freeze-plan，不能提交执行结果')
    standards.validate(work)
    records=work['records'];unique=set()
    for row in records.values():
        if row['kind'] not in {'CheckExecution','DiscoveryClue'}: continue
        plan=records.get(row.get('plan_version_id'),{})
        L.require(plan.get('kind')=='PlanVersion','执行结果必须引用冻结计划')
        checks={c['code']:c for c in plan['payload']['checks']}
        L.require(row.get('recorded_run_id') in work.get('_known_run_ids',[work['run']['id']]),'执行记录轮次无效')
        L.require(row.get('review_freshness') in {'current','needs_review'},'执行记录复核状态无效')
        if row['kind']=='DiscoveryClue':
            L.require(not set(row)-{'id','kind','recorded_run_id','review_freshness','plan_version_id','origin','check_codes','fact','fact_evidence_ids','behavior_date','standard_applications','actual_decision','required_decision','category','conclusion_type','verification_status','basis_pending','institutional_inconsistency'}, '线索含未知字段；不设置动机字段')
            P.fields(row,('origin','check_codes','fact','fact_evidence_ids','behavior_date','standard_applications','actual_decision',
                          'required_decision','category','conclusion_type','verification_status','basis_pending'), '线索')
            L.require(row['origin'] in {'计划内','计划外发现'} and row['category'] in CATEGORIES,'线索来源/类别无效')
            L.require(row['conclusion_type'] in {'违规','评价','事实记录','制度与上位规定不一致'},'结论类别无效')
            L.require(row['verification_status'] in {'已核实','待核实'} and type(row['basis_pending']) is bool,'线索核实状态无效')
            L.require(L.nonempty(row['fact']),'线索事实不能为空')
            facts(work,row['fact_evidence_ids']);standards.iso(row['behavior_date'])
            codes=row['check_codes'];L.require(isinstance(codes,list) and all(isinstance(c,str) for c in codes) and len(codes)==len(set(codes)),'线索检查实例列表无效')
            if row['origin']=='计划内':
                L.require(codes and all(c in checks and checks[c]['selection']=='选用' for c in codes),'计划内线索须引用选用检查实例')
            else: L.require(not codes,'计划外发现不得计入计划内结果')
            for field in ('actual_decision','required_decision'):
                d=row[field];P.fields(d,('state','description','reason','evidence_ids'),field)
                L.require(d['state'] in {'有证据','待确认'} and L.nonempty(d['description']) and L.nonempty(d['reason']),'决策权限说明无效')
                facts(work,d['evidence_ids'],d['state']=='有证据')
                if row['verification_status']=='已核实' and row['category']!='情况记录': L.require(d['state']=='有证据','决策主体/权限待确认，线索不能标已核实')
            standards.applicability(work,row,enforce=row['review_freshness']=='current' and row['plan_version_id']==current['id'])
        else:
            P.fields(row,('check_code','status','scope_complete','actual_scope','uncovered_scope','reason','evidence_ids',
                          'calculation_ids','clue_ids','gap_ids','task_ids'), '执行结果')
            code=row['check_code'];L.require(code in checks,'执行检查实例不存在')
            key=(row['plan_version_id'],code);L.require(key not in unique,'同一计划检查实例有重复执行结果');unique.add(key)
            c=checks[code];status=row['status'];L.require(status in STATES and L.nonempty(row['reason']),'执行状态/原因无效')
            L.require(type(row['scope_complete']) is bool and isinstance(row['actual_scope'],str) and isinstance(row['uncovered_scope'],str),'执行范围字段无效')
            details=row.get('scheme_results')
            if work['run'].get('scheme_coverage_version') and row['recorded_run_id']==work['run']['id']:
                L.require(details is not None,'执行结果须逐个填写 scheme_results，不能把程序状态传播到未执行目标')
            if details is not None:
                L.require(isinstance(details,list),'scheme_results 须为列表')
                codes=[]
                for detail in details:
                    P.fields(detail,('scheme_code','state','actual_scope','uncovered_scope','reason'),'逐目标执行')
                    codes.append(detail['scheme_code'])
                    L.require(detail['state'] in {'已覆盖','部分覆盖','未覆盖'} and L.nonempty(detail['reason']),'逐目标状态/原因无效')
                    L.require(isinstance(detail['actual_scope'],str) and isinstance(detail['uncovered_scope'],str),'逐目标范围须为文字')
                    if detail['state']=='未覆盖':
                        L.require(detail['actual_scope']=='' and L.nonempty(detail['uncovered_scope']),'未覆盖目标须留空已执行范围并说明剩余范围')
                    else:
                        L.require(L.nonempty(detail['actual_scope']),'已执行目标须说明实际范围')
                        L.require((detail['uncovered_scope']=='') if detail['state']=='已覆盖' else L.nonempty(detail['uncovered_scope']),'逐目标完成状态与剩余范围矛盾')
                    if status in {'无法执行','未选用'}:L.require(detail['state']=='未覆盖','无法执行/未选用不能产生已执行目标')
                    if row['scope_complete']:L.require(detail['state']=='已覆盖','完整执行不能包含未完成目标')
                L.require(all(isinstance(x,str) for x in codes) and len(codes)==len(set(codes)) and set(codes)=={l['scheme_code'] for l in c['scheme_links']},'逐目标结果须与冻结方案映射一一对应')
            clues=refs(work,row['clue_ids'],'DiscoveryClue')
            refs(work,row['calculation_ids'],'Calculation');refs(work,row['gap_ids'],'EvidenceGap');refs(work,row['task_ids'],'ReviewTask',True)
            evidence=facts(work,row['evidence_ids'],False)
            L.require(all(x['plan_version_id']==row['plan_version_id'] and x['origin']=='计划内' and code in x['check_codes'] for x in clues),'线索属于其他计划/检查项或为计划外发现')
            if status=='未选用':
                L.require(c['selection']!='选用' and not row['scope_complete'] and not clues,'选用项改为未选用须先修订确认计划')
            elif status=='无法执行':
                L.require(c['selection']=='选用' and not row['scope_complete'] and L.nonempty(row['uncovered_scope']) and not clues,'无法执行须列范围及原因')
            else:
                L.require(c['selection']=='选用' and c['applicability']['state']!='不成立','仅执行已选用且非明显不适用的程序')
                if c['applicability']['state']=='待确认':
                    L.require(status=='发现线索待核实' and not row['scope_complete'],'程序适用条件待确认时保留部分执行和待核实，不标已核实/无异常')
                L.require(L.nonempty(row['actual_scope']) and evidence,'已执行程序须有实际范围和原件证据')
                L.require(row['scope_complete'] or L.nonempty(row['uncovered_scope']),'部分执行须披露剩余范围')
                if row['scope_complete']: L.require(row['uncovered_scope']=='','完整执行与剩余范围矛盾')
                if status=='已执行未发现异常': L.require(not clues and row['scope_complete'],'无异常须完成声明范围，且不能同时存在异常线索')
                elif status=='发现线索并已核实': L.require(clues and all(x['verification_status']=='已核实' and not x['basis_pending'] for x in clues),'依据待确认或线索待核实，不能标已核实')
                else: L.require(clues and any(x['verification_status']=='待核实' or x['basis_pending'] for x in clues),'待核实结果须引用待核实线索')
    # Every in-plan clue must be visible in the corresponding results, never orphaned.
    for clue in records.values():
        if clue['kind']=='DiscoveryClue' and clue['origin']=='计划内':
            for code in clue['check_codes']:
                L.require(any(r['kind']=='CheckExecution' and r['plan_version_id']==clue['plan_version_id'] and r['check_code']==code and clue['id'] in r['clue_ids'] for r in records.values()),'计划内线索未列入对应执行结果')
        if clue['kind']=='Finding' and clue.get('discovery_clue_id'):
            c=records.get(clue['discovery_clue_id'],{})
            L.require(c.get('kind')=='DiscoveryClue','Finding 需引用有效发现型线索')
            if clue['assessment']=='supported': L.require(c['verification_status']=='已核实' and not c['basis_pending'],'不能用旧 Finding 绕过依据待确认门槛')


def pending(work):
    if not work['run'].get('discovery_version'): return []
    plan=plans.active(work)
    if not plan:return ['discovery:unfrozen_plan']
    rows=work['records'];results={r['check_code']:r for r in rows.values() if r['kind']=='CheckExecution' and r['plan_version_id']==plan['id']}
    out=[]
    for c in plan['payload']['checks']:
        if c['selection']!='选用':continue
        r=results.get(c['code'])
        if not r or not r['scope_complete'] or r['status']=='发现线索待核实' or r.get('review_freshness')=='needs_review':out.append('check:'+c['code'])
        elif work['run'].get('scheme_coverage_version') and 'scheme_results' not in r:out.append('check:'+c['code'])
    out += ['scheme:'+s['code'] for s in plan['payload']['scheme_items'] if s['type']=='评价描述']
    out += ['scheme:'+l['scheme_code'] for c in plan['payload']['checks'] if c['selection']=='选用' for l in c['scheme_links'] if l['coverage']=='部分']
    out += [r['id'] for r in rows.values() if r['kind']=='DiscoveryClue' and r['plan_version_id']==plan['id'] and (r['basis_pending'] or r['verification_status']=='待核实')]
    return out
