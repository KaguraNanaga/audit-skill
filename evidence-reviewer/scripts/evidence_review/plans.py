"""Human-authored plans, exact-source references and immutable confirmation snapshots."""
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from core import ledger as L, program_packs as P
from core.persistence import atomic_bytes

SCHEMA = 'inspection-plan-1'
KINDS = {'PackSnapshot', 'PlanVersion', 'PlanConfirmation', 'Standard', 'CheckExecution', 'DiscoveryClue'}


def reference(work, item):
    P.fields(item, ('source_version_id', 'unit_id', 'quote'), '原文引用')
    v = work['records'].get(item['source_version_id'], {})
    u = next((u for u in work['units'].get(item['source_version_id'], []) if u['id'] == item['unit_id']), None)
    L.require(v.get('kind') == 'SourceVersion' and u, '原文单元不存在')
    L.require(u['locator'].get('unit') not in {'ocr_derived', 'table_query_derived'}, '计划/依据原文不能使用派生单元替代')
    L.require(L.nonempty(item['quote']) and item['quote'] in u['text'], '原文引用不是所列单元的逐字文本')
    return v, u


def active(work):
    plan = work['records'].get(work['run'].get('plan_version_id'), {})
    return plan if plan.get('kind') == 'PlanVersion' else None


def enable(work):
    work['project']['workflow'] = 'discovery'
    work['run']['discovery_version'] = 1
    work['run']['scheme_coverage_version'] = 1


def validate_payload(work, plan, current=False):
    P.fields(plan, ('schema_version', 'title', 'previous_plan_id', 'revision_reason', 'pack_snapshot_ids',
                    'scheme_items', 'checks', 'overrides'), '检查计划')
    L.require(plan['schema_version'] == SCHEMA and L.nonempty(plan['title']), '检查计划版本或标题无效')
    if current:
        L.require(plan['pack_snapshot_ids'] == work['run'].get('pack_snapshot_ids'), '计划未采用本轮程序包快照')
        previous = work['run'].get('plan_version_id') or work['run'].get('previous_plan_id')
        L.require(plan['previous_plan_id'] == previous, '新计划须引用当前/上一冻结版本')
    if plan['previous_plan_id']:
        L.require(work['records'].get(plan['previous_plan_id'], {}).get('kind') == 'PlanVersion', '前版计划不存在')
        L.require(L.nonempty(plan['revision_reason']), '计划变更必须说明原因')
    library, overrides = P.resolve(P.snapshots(work, plan['pack_snapshot_ids']))
    L.require(plan['overrides'] == overrides, '计划必须如实列出全部程序包覆盖声明')
    items = plan['scheme_items']; checks = plan['checks']
    L.require(isinstance(items, list) and items and isinstance(checks, list), '方案条目和检查项须为列表')
    schemes, instances = {}, set()
    for s in items:
        P.fields(s, ('code', 'objective', 'original_text', 'source_ref', 'type'), '方案条目')
        L.require(L.nonempty(s['code']) and s['code'] not in schemes, '方案条目 ID 重复或为空')
        L.require(L.nonempty(s['objective']), '填写拆分后的单一检查目标 objective；原文保存在 original_text')
        L.require(s['type'] in {'问题发现', '评价描述', '情况核查'}, '方案条目类型无效')
        reference(work, s['source_ref'])
        L.require(s['original_text'] == s['source_ref']['quote'], '方案原文与引用不一致')
        schemes[s['code']] = s
    mapped = set()
    for c in checks:
        P.fields(c, ('code', 'origin', 'check_code', 'temporary', 'scheme_links', 'selection', 'selection_reason',
                     'applicability', 'materials', 'material_readiness'), '计划检查项')
        L.require(L.nonempty(c['code']) and c['code'] not in instances, '计划检查实例 ID 重复或为空')
        instances.add(c['code'])
        L.require(c['origin'] in {'库检查项', '临时程序'}, '检查项 origin 无效')
        if c['origin'] == '临时程序':
            P.check_item(c['temporary'])
            L.require(c['check_code'] == c['temporary']['code'] and c['check_code'] not in library, '临时程序 ID 与通用/本地包冲突')
            definition = c['temporary']
        else:
            L.require(c['check_code'] in library and c['temporary'] is None, '检查项不存在或临时程序字段矛盾')
            definition = library[c['check_code']]['item']
        L.require(c['selection'] in {'选用', '建议补充', '未选用'} and L.nonempty(c['selection_reason']), '填写选用状态和理由')
        a = c['applicability']; P.fields(a, ('state', 'reason'), '适用条件')
        L.require(a['state'] in {'成立', '不成立', '待确认'} and L.nonempty(a['reason']), '适用条件无效')
        links = c['scheme_links']; L.require(isinstance(links, list), 'scheme_links 必须为列表')
        L.require(a['state'] != '不成立' or (not links and c['selection'] == '未选用'), '明显不适用的检查项不得匹配或选用')
        L.require(c['selection'] != '选用' or links, '计划选用项须对应方案条目；范围外项目先列建议补充')
        linked = set()
        for link in links:
            P.fields(link, ('scheme_code', 'degree', 'reason', 'coverage', 'scope', 'remaining_scope'), '方案匹配')
            sc = link['scheme_code']
            L.require(sc in schemes and sc not in linked, '方案匹配重复或不存在')
            linked.add(sc)
            L.require(schemes[sc]['type'] != '评价描述', '评价类待指标模板，本阶段不加入执行检查项')
            L.require(link['degree'] in {'直接对应', '部分对应', '可能相关'} and L.nonempty(link['reason']), '匹配程度/理由无效')
            L.require(link['coverage'] in {'完整', '部分'} and L.nonempty(link['scope']), '填写覆盖范围')
            L.require(link['degree'] == '直接对应' or link['coverage'] == '部分', '部分/可能匹配不能声明完整覆盖')
            L.require((link['coverage'] == '完整' and link['remaining_scope'] == '') or
                      (link['coverage'] == '部分' and L.nonempty(link['remaining_scope'])), '填写真实剩余范围')
            if c['selection'] == '选用': mapped.add(sc)
        materials = c['materials']; L.require(isinstance(materials, list) and materials, '材料就绪逐项登记')
        L.require([m.get('name') for m in materials] == definition['materials'], '材料清单须完整对应检查项要求及顺序')
        states = []
        for m in materials:
            P.fields(m, ('name', 'state', 'reason', 'unit_refs', 'search_record_ids', 'request'), '材料就绪')
            L.require(m['state'] in {'齐全', '部分齐全', '缺失'} and L.nonempty(m['reason']), '材料状态/理由无效')
            L.require(isinstance(m['unit_refs'], list) and isinstance(m['search_record_ids'], list), '材料引用须为列表')
            for ref in m['unit_refs']: reference(work, ref)
            for sid in m['search_record_ids']:
                L.require(work['records'].get(sid, {}).get('kind') == 'SearchRecord', '盘点搜索引用无效')
            if m['state'] != '缺失': L.require(bool(m['unit_refs']), '材料就绪须引用具体单元')
            if m['state'] != '齐全':
                L.require(L.nonempty(m['request']) and m['search_record_ids'], '缺失/部分齐全材料须列补证需求及实际检索记录')
            else: L.require(m['request'] == '', '齐全材料不应同时请求补证')
            states.append(m['state'])
        ready = '齐全' if all(s == '齐全' for s in states) else '缺失' if all(s == '缺失' for s in states) else '部分齐全'
        L.require(c['material_readiness'] == ready, '材料整体就绪程度与明细矛盾')
    L.require(all(s['type'] == '评价描述' or code in mapped for code, s in schemes.items()),
              '方案条目缺少选用检查项：无对应检查项时填写临时程序及其实施限制')
    return library


def md_cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>').replace('\r', '')


def render(plan, work):
    library, _ = P.resolve(P.snapshots(work, plan['pack_snapshot_ids']))
    lines = ['# ' + plan['title'], '', '计划 SHA256：' + L.checksum(plan), '',
             '确认前仅进行方案阅读、盘点与计划准备；等待用户确认后冻结，才执行检查项。', '',
             '|方案条目|独立检查目标|类型|原文及出处|', '|---|---|---|---|']
    for s in plan['scheme_items']:
        ref = s['source_ref']; v = work['records'][ref['source_version_id']]
        name = v.get('actual_name') or work['records'][v['source_id']]['actual_name']
        lines += ['|' + '|'.join(map(md_cell, (s['code'], s['objective'], '评价类，待指标模板' if s['type']=='评价描述' else s['type'],
                    s['original_text'] + '；' + name + '；' + ref['unit_id']))) + '|']
    lines += ['', '|检查实例/检查项|方案匹配及范围|选用及理由|适用性|材料就绪|补证需求|', '|---|---|---|---|---|---|']
    for c in plan['checks']:
        definition = c['temporary'] if c['origin']=='临时程序' else library[c['check_code']]['item']
        links = '；'.join(f"{x['scheme_code']} {x['degree']}：{x['reason']}；覆盖{x['scope']}；剩余{x['remaining_scope']}" for x in c['scheme_links'])
        lines += ['|'+'|'.join(map(md_cell, (c['code']+'/'+c['check_code']+' '+definition['title']+'（'+c['origin']+'）',links,
                    c['selection']+'：'+c['selection_reason'],c['applicability']['state']+'：'+c['applicability']['reason'],
                    c['material_readiness'],'；'.join(m['request'] for m in c['materials'] if m['request']))))+'|']
    lines += ['', '## 程序、材料与工具明细', '']
    for c in plan['checks']:
        d = c['temporary'] if c['origin']=='临时程序' else library[c['check_code']]['item']
        lines += ['### '+c['code'], '', *[f'{i}. {s}' for i,s in enumerate(d['steps'],1)], '',
                  '合理解释与例外：'+'；'.join(d['exceptions']), '',
                  '工具支持：'+'；'.join(t['description']+'（'+t['status']+'）' for t in d['tools']), '']
        for m in c['materials']:
            lines += ['- '+m['name']+'：'+m['state']+'；'+m['reason']+'；单元 '+', '.join(r['unit_id'] for r in m['unit_refs'])]
    lines += ['', '## 本地覆盖声明', '', *([json.dumps(o,ensure_ascii=False,sort_keys=True) for o in plan['overrides']] or ['无']), '',
              '变更原因：'+plan['revision_reason'], '']
    return '\n'.join(lines)


def validate(work):
    rows = work['records']; enabled = work['run'].get('discovery_version')
    if not enabled:
        L.require(not any(r['kind'] in KINDS for r in rows.values()), '发现型记录不能关闭检查计划校验')
        return
    L.require(enabled == 1 and work['project'].get('workflow') == 'discovery', '发现型流程标识无效')
    P.resolve(P.snapshots(work))
    for row in rows.values():
        if row['kind'] == 'PackSnapshot':
            P.validate(row['data']); L.require(row['pack_sha256'] == L.checksum(row['data']), '包快照内容指纹不符')
        if row['kind'] != 'PlanVersion': continue
        p = row['payload']; validate_payload(work, p)
        L.require(row['plan_sha256'] == L.checksum(p), '冻结计划指纹不符')
        confirmation = rows.get(row['confirmation_id'], {})
        L.require(confirmation.get('kind') == 'PlanConfirmation' and confirmation.get('plan_version_id') == row['id'], '计划缺少匹配确认')
        validate_confirmation(confirmation['confirmation'], row['plan_sha256'])
        previous = rows.get(p['previous_plan_id'])
        L.require(row['version'] == (previous['version']+1 if previous else 1), '计划版本链无效')
    for row in rows.values():
        if row['kind'] == 'PlanConfirmation':
            L.require(rows.get(row.get('plan_version_id'), {}).get('confirmation_id') == row['id'], '孤立计划确认')
    if work['run'].get('plan_version_id'):
        p = active(work); L.require(p is not None, '活动冻结计划不存在')
        L.require(p['payload']['pack_snapshot_ids'] == work['run']['pack_snapshot_ids'], '程序包改变后须重新确认计划')


def validate_confirmation(c, sha):
    P.fields(c, ('plan_sha256', 'source', 'quote', 'confirmed_at', 'session_ref', 'message_ref'), '用户确认记录')
    L.require(c['source'] == 'user_conversation' and c['plan_sha256'] == sha, '确认来源或计划指纹不符')
    L.require(all(L.nonempty(c[k]) for k in ('quote','session_ref','message_ref','confirmed_at')), '须记录实际用户确认及会话出处')
    try: dt = datetime.fromisoformat(c['confirmed_at'])
    except (TypeError, ValueError): raise ValueError('确认时间须为 ISO 日期时间')
    L.require(dt.tzinfo is not None, '确认时间须带时区')


def command(args, api):
    project = args.project.resolve()
    with L.lock(project):
        work = api.get_work(project); api.check_files(project, work)
        L.require(work['run'].get('discovery_version') == 1, '先通过 begin/update 的 workflow: discovery 启用发现型流程')
        if args.command == 'plan-scaffold':
            versions = args.scheme_version or []
            L.require(versions and set(versions) <= set(work['units']), '指定真实 --scheme-version')
            _, overrides = P.resolve(P.snapshots(work))
            plan = dict(schema_version=SCHEMA, title='', previous_plan_id=work['run'].get('plan_version_id') or work['run'].get('previous_plan_id'),
                        revision_reason='',pack_snapshot_ids=work['run']['pack_snapshot_ids'],scheme_items=[],checks=[],overrides=overrides)
            hints = []
            for vid in versions:
                for u in work['units'][vid][:20]:
                    hints.append(dict(source_version_id=vid,unit_id=u['id'],text_preview=u['text'][:500]))
            out = args.out.resolve() if args.out else project/'inspection-plan.json'
            L.require(out.parent == project and not out.exists(), '骨架须为项目根目录内的新文件')
            L.atomic_json(out, plan)
            return dict(state='draft', path=str(out), source_hints=hints, ready_to_execute=False,
                        notice='这里只提供真实ID，需实际读完整方案并拆分、匹配；骨架不包含判断，不能直接冻结。')
        plan = api.load(args.plan); sha = L.checksum(plan)
        previous = active(work)
        if args.command == 'freeze-plan' and previous and previous['plan_sha256'] == sha:
            validate(work)
            confirmation=api.load(args.confirmation);validate_confirmation(confirmation,sha)
            L.require(confirmation == work['records'][previous['confirmation_id']]['confirmation'], '重复冻结的确认内容不同')
            return dict(state='frozen', idempotent=True, plan_version_id=previous['id'], plan_sha256=sha)
        validate_payload(work, plan, current=True)
        if args.command == 'check-plan':
            out = project/'plans/drafts'/(sha+'.md'); atomic_bytes(out, render(plan,work).encode('utf-8'))
            return dict(state='awaiting_user_confirmation', plan_sha256=sha, plan_table=str(out), ready_to_execute=False)
        confirmation = api.load(args.confirmation); validate_confirmation(confirmation, sha)
        pid, cid = L.uid(), L.uid(); old = work['records'].get(plan['previous_plan_id'])
        envelope = dict(plan=plan, confirmation=confirmation, frozen_at=L.now())
        # An interrupted freeze may leave an unreferenced, complete snapshot. Only
        # the same newly supplied confirmation and plan may explicitly resume it.
        for orphan in sorted((project/'plans').glob('*/frozen.json')):
            if orphan.parent.name in work['records']: continue
            candidate=api.load(api.local_path(project,orphan.relative_to(project).as_posix()))
            if candidate.get('plan')==plan and candidate.get('confirmation')==confirmation:
                pid=orphan.parent.name; envelope=candidate;break
        data = L.encoded(envelope); path = 'plans/'+pid+'/frozen.json'
        atomic_bytes(api.local_path(project,path), data)
        from core.history import fault
        fault('after_plan_snapshot')
        L.add(work,'PlanConfirmation',dict(plan_version_id=pid,confirmation=confirmation),cid)
        L.add(work,'PlanVersion',dict(payload=plan,plan_sha256=sha,confirmation_id=cid,version=old['version']+1 if old else 1,
                                   path=path,sha256=hashlib.sha256(data).hexdigest(),frozen_at=envelope['frozen_at']),pid)
        work['run']['plan_version_id']=pid
        validate(work); api.save_work(project,work)
        return dict(state='frozen',plan_version_id=pid,version=work['records'][pid]['version'],plan_sha256=sha,
                    ready_to_execute=True,notice='结构校验不独立证明会话确认真实。')
