"""Two deterministic coverage views, with unexecuted scope kept visible."""
import csv
import io
import json
from . import plans


def matrix(work):
    plan=plans.active(work)
    if not plan:return [],[]
    records=work['records'];payload=plan['payload']
    results={r['check_code']:r for r in records.values() if r['kind']=='CheckExecution' and r['plan_version_id']==plan['id']}
    checks=[]; schemes=[]
    for c in payload['checks']:
        r=results.get(c['code']); clues=[records[i] for i in r['clue_ids']] if r else []
        status=r['status'] if r else ('待执行' if c['selection']=='选用' else '未选用')
        checks.append({'检查实例':c['code'],'检查项':c['check_code'],'程序类型':c['origin'],
            '方案条目':'；'.join(x['scheme_code'] for x in c['scheme_links']),'执行状态':status,
            '复核状态':r['review_freshness'] if r else '未执行','范围完成':bool(r and r['scope_complete']),
            '被审计单位权限内':sum(x['category']=='被审计单位权限内' for x in clues),
            '涉及上级或外部决策':sum(x['category']=='涉及上级或外部决策' for x in clues),
            '情况记录':sum(x['category']=='情况记录' for x in clues),
            '依据待确认':sum(x['basis_pending'] for x in clues),
            '无法执行或未选用原因':r['reason'] if r and status in {'无法执行','未选用'} else c['selection_reason'] if c['selection']!='选用' else '',
            '未覆盖范围':r['uncovered_scope'] if r else '未执行' if c['selection']=='选用' else '',
            '补证需求':'；'.join(dict.fromkeys([m['request'] for m in c['materials'] if m['request']]+[records[g]['minimal_request'] for g in (r['gap_ids'] if r else []) if records[g]['state']=='open'])),
            '计划版本':plan['id']})
    for s in payload['scheme_items']:
        related=[(c,l) for c in payload['checks'] for l in c['scheme_links'] if l['scheme_code']==s['code'] and c['selection']=='选用']
        if work['run'].get('scheme_coverage_version'):
            details=[]
            for c,l in related:
                r=results.get(c['code'])
                d=next((x for x in r.get('scheme_results',[]) if x['scheme_code']==s['code']),None) if r else None
                current=bool(r and r['review_freshness']=='current' and r['status'] not in {'无法执行','未选用'})
                details.append((c,l,r,d,current))
            executed=[x for x in details if x[4] and x[3] and x[3]['state']!='未覆盖']
            state='评价类待模板' if s['type']=='评价描述' else '未覆盖'
            if s['type']!='评价描述' and executed:
                state='已覆盖' if len(executed)==len(related) and all(d['state']=='已覆盖' and l['coverage']=='完整' for c,l,r,d,current in executed) else '部分覆盖'
            remaining=[l['remaining_scope'] for c,l in related if l['remaining_scope']]
            remaining += [d['uncovered_scope'] if d and current else '待复核或未登记逐目标执行范围' if r else '尚未执行该目标' for c,l,r,d,current in details if not d or not current or d['uncovered_scope']]
            schemes.append({'方案条目':s['code'],'独立检查目标':s['objective'],'类型':s['type'],'原文':s['original_text'],'覆盖情况':state,
                            '对应检查项':'；'.join(c['code']+'/'+c['check_code'] for c,l in related),
                            '实际执行范围':'；'.join(c['code']+'：'+d['actual_scope'] for c,l,r,d,current in executed),
                            '剩余范围':'；'.join(dict.fromkeys(remaining)),
                            '逐目标说明':'；'.join(c['code']+'：'+d['reason'] for c,l,r,d,current in details if d),
                            '计划版本':plan['id']})
            continue
        executed=[(c,l) for c,l in related if (r:=results.get(c['code'])) and r['status'] not in {'无法执行','未选用'} and r['review_freshness']=='current']
        state='评价类待模板' if s['type']=='评价描述' else '未覆盖'
        if s['type']!='评价描述' and executed:
            state='已覆盖' if len(executed)==len(related) and all(results[c['code']]['scope_complete'] and l['coverage']=='完整' for c,l in executed) else '部分覆盖'
        schemes.append({'方案条目':s['code'],'独立检查目标':s['objective'],'类型':s['type'],'原文':s['original_text'],'覆盖情况':state,
                        '对应检查项':'；'.join(c['code']+'/'+c['check_code'] for c,l in related),
                        '剩余范围':'；'.join(dict.fromkeys([l['remaining_scope'] for c,l in related if l['remaining_scope']]+[results[c['code']]['uncovered_scope'] for c,l in related if c['code'] in results and results[c['code']]['uncovered_scope']])),
                        '计划版本':plan['id']})
    return checks,schemes


def csv_text(rows):
    out=io.StringIO(newline='')
    if rows:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader()
        for row in rows:
            # Literal text remains text when opened in spreadsheet applications.
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()})
    return '\ufeff'+out.getvalue()


def md_table(rows,title):
    if not rows:return '# '+title+'\n\n未建立本视图所需的检查计划，不追认历史检查覆盖。\n'
    return '# '+title+'\n\n覆盖表示已登记程序的执行范围，不表示无问题、依据已确认或审计完成。\n\n'+ '\n'.join([
        '|'+ '|'.join(rows[0])+'|','|'+'|'.join('---' for _ in rows[0])+'|',
        *('|'+'|'.join(plans.md_cell(x) for x in r.values())+'|' for r in rows)])+'\n'


def exports(work):
    checks,schemes=matrix(work)
    out={'coverage-checks.md':md_table(checks,'检查项覆盖矩阵'),'coverage-checks.csv':csv_text(checks),
         'coverage-scheme.md':md_table(schemes,'方案条目覆盖矩阵'),'coverage-scheme.csv':csv_text(schemes)}
    plan=plans.active(work)
    if not plan:return out
    out['inspection-plan.md']=plans.render(plan['payload'],work)+'\n冻结版本：'+plan['id']+'\n'
    standards=['# 标准表','','所有条款追溯实际来源；适用性在每条线索上单独记录。','']
    for r in work['records'].values():
        if r['kind']!='Standard':continue
        standards += ['## '+r['name'],'','标准 ID：'+r['id'],'']
        standards += [f'- {k}：'+json.dumps(v,ensure_ascii=False,sort_keys=True) for k,v in sorted(r.items()) if k not in {'kind','id'}]
        standards += ['']
    out['standards.md']='\n'.join(standards)
    for origin,filename in [('计划内','discovery-clues.md'),('计划外发现','out-of-plan.md')]:
        lines=['# '+origin,'','供审计人员复核确认的工作草稿。','']
        for r in work['records'].values():
            if r['kind']!='DiscoveryClue' or r['plan_version_id']!=plan['id'] or r['origin']!=origin:continue
            label='待复核，旧判断仅供追溯' if r['review_freshness']=='needs_review' else '依据待确认，仅供人工判断' if r['basis_pending'] else r['verification_status']
            lines+=['## '+r['fact'],'',label+'；'+r['category']+'；'+r['review_freshness'],'']
            lines += ['事实出处：'+'；'.join('[证据](evidence.md#e-'+eid+')' for eid in r['fact_evidence_ids']),'']
            lines += [f'- {k}：'+json.dumps(v,ensure_ascii=False,sort_keys=True) for k,v in sorted(r.items()) if k not in {'kind','fact','fact_evidence_ids'}]
            lines+=['']
        out[filename]='\n'.join(lines)
    return out
