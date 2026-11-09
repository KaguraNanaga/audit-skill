"""Standards and six explicit applicability judgments; no legal inference."""
from datetime import date
from . import ledger as L, program_packs as P

LEVELS = {'法律','行政法规','部门规章','地方性法规和规章','规范性文件和政策','上级单位制度','本单位制度','合同'}
UPPER_LEVELS = LEVELS - {'本单位制度', '合同'}
AXES = ('subject','time','territory','matter_conditions','hierarchy','nature')
JUDGMENTS = {'成立','不成立','无法确定'}


def iso(value):
    if value is None: return None
    L.require(isinstance(value,str), '日期须为 YYYY-MM-DD 或 null')
    try: parsed = date.fromisoformat(value)
    except ValueError: raise ValueError('日期须为 YYYY-MM-DD')
    L.require(parsed.isoformat() == value, '日期须为 YYYY-MM-DD')
    return parsed


def time_state(standard, behavior_date):
    start, end, event = map(iso, (standard['effective_at'],standard['repealed_at'],behavior_date))
    if start and end: L.require(start < end, '施行日期须早于废止日期')
    if not all((start,end,event)): return '无法确定'
    return '成立' if start <= event < end else '不成立'


def validate(work):
    from evidence_review.plans import reference
    records=work['records']
    for s in records.values():
        if s['kind'] != 'Standard': continue
        P.fields(s, ('summary','level','name','document_number','article','effective_at','repealed_at','subjects','territory',
                     'matter_conditions','exceptions','nature','relationships','source_ref','rule_id','critical_text','verification_state'), '标准表')
        L.require(s['level'] in LEVELS and s['nature'] in {'强制性要求','导向性政策'}, '标准层级或性质无效')
        L.require(s['verification_state'] in {'已核对原文','仅有二手来源','待核实'}, '标准核实状态无效')
        for key in ('summary','name','subjects','territory','matter_conditions','exceptions'):
            L.require(L.nonempty(s[key]), '标准表缺少 '+key+'；未知须明确写待核实')
        for key in ('document_number','article'):
            L.require(s[key] is None or L.nonempty(s[key]), '文号/条款未知用 null')
        time_state(s,None)
        L.require(not (s['source_ref'] and s['rule_id']), '原文引用和 rules 引用选其一')
        if s['source_ref']:
            v,u=reference(work,s['source_ref'])
            L.require(s['critical_text'] == s['source_ref']['quote'], '标准条款与原文不符')
        elif s['rule_id']:
            r=records.get(s['rule_id'],{})
            L.require(r.get('kind')=='RuleApplication', '标准 rules 引用不存在')
            v,u=reference(work,dict(source_version_id=r.get('source_version_id'),unit_id=r.get('unit_id'),quote=r.get('critical_text')))
            L.require(s['critical_text']==r['critical_text'], '标准条款与 rules 原文不符')
            if s['verification_state']=='已核对原文': L.require(r['verification_state']=='body_verified','rules 原文尚未核实')
        else:
            L.require(s['verification_state']=='待核实' and s['critical_text'] is None, '无来源时条款留 null，不使用模型记忆')
            v,u={},{}
        if s['verification_state']=='已核对原文':
            L.require(v and v.get('acquisition_state') not in {'partial_body','snippet_only','unavailable','tool_unavailable'}, '正文未取得，不能标已核对原文')
            source=records[v['source_id']]
            L.require(source['role'] not in {'ai_analysis','template','workpaper'}, 'AI/模板/底稿不是已核对的标准原文')
            if u.get('state') in {'manual_check','failed','unread'}:
                L.require(any(r['kind']=='ReadRecord' and r.get('state')=='viewed' and r.get('unit_id')==u['id'] and r.get('source_version_id')==v['id'] for r in records.values()), '依据原页尚未实际观察')
        L.require(isinstance(s['relationships'],list),'依据关系须为列表')
        for rel in s['relationships']:
            P.fields(rel,('standard_id','relation','reason'),'依据关系')
            L.require(rel['standard_id']!=s['id'] and records.get(rel['standard_id'],{}).get('kind')=='Standard','依据关系引用无效')
            L.require(rel['relation'] in {'更严格','冲突'} and L.nonempty(rel['reason']),'依据关系需类型和理由')


def applicability(work, clue, enforce=True):
    apps=clue['standard_applications']
    L.require(isinstance(apps,list),'逐依据适用性须为列表')
    seen=set(); pending=False; supports=False; conflicts=set()
    for app in apps:
        P.fields(app,('standard_id','judgments'),'适用性')
        sid=app['standard_id'];s=work['records'].get(sid,{})
        L.require(s.get('kind')=='Standard' and sid not in seen,'依据不存在或重复')
        seen.add(sid);j=app['judgments']
        L.require(isinstance(j,dict) and set(j)==set(AXES),'逐项填写六项适用性')
        for axis in AXES:
            P.fields(j[axis],('state','reason'),'适用性 '+axis)
            L.require(j[axis]['state'] in JUDGMENTS and L.nonempty(j[axis]['reason']),'适用性判断/理由无效')
        temporal=time_state(s,clue['behavior_date'])
        if enforce: L.require(j['time']['state']==temporal,'时间效力与记录日期不一致；缺失日期须为无法确定')
        unknown=any(j[a]['state']=='无法确定' for a in AXES)
        inapplicable=any(j[a]['state']=='不成立' for a in AXES)
        pending |= unknown or s['verification_state']!='已核对原文'
        if enforce and clue['verification_status']=='已核实':
            L.require(s['verification_state']=='已核对原文','未核对原文的依据不能支撑发现线索并已核实')
            L.require(not unknown and not inapplicable,'依据待确认或不适用，不能登记发现线索并已核实')
        supports |= s['nature']=='强制性要求' and not unknown and not inapplicable and s['verification_state']=='已核对原文'
        for rel in s['relationships']:
            other=work['records'][rel['standard_id']]
            levels={s['level'],other['level']}
            if rel['relation']=='冲突' and '本单位制度' in levels and levels & UPPER_LEVELS:
                conflicts.update((sid,other['id']))
    if enforce and clue['conclusion_type']=='违规':
        L.require(apps and any(work['records'][a['standard_id']]['nature']=='强制性要求' for a in apps), '导向性政策不能单独支撑违规类结论')
        if clue['verification_status']=='已核实': L.require(supports,'违规类结论没有已核实且适用的强制性依据')
    if clue['category']!='情况记录': L.require(apps,'异常线索须登记依据；依据未知可建待核实标准')
    if enforce and conflicts:
        issue=clue.get('institutional_inconsistency')
        P.fields(issue,('description','standard_ids'),'制度与上位规定不一致')
        ids=issue['standard_ids']
        L.require(L.nonempty(issue['description']) and isinstance(ids,list) and all(isinstance(i,str) and work['records'].get(i,{}).get('kind')=='Standard' for i in ids) and len(ids)==len(set(ids)) and conflicts<=set(ids),
                  '记录制度与上位规定不一致及双方依据，不只记录执行人员违规')
    if enforce: L.require(clue['basis_pending'] is pending,'依据待确认标记与依据核实/适用性不一致')
    return pending
