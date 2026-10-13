"""Append-only revision chains, as-of exports, and recoverable local commits."""
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import ledger as L

SCHEMA = 'evidence-ledger-2.0'
BUSINESS = {'ReviewTask', 'Claim', 'EvidenceGap', 'Calculation', 'RuleApplication', 'Finding'}
IMMUTABLE = {'SourceVersion', 'Evidence', 'EvidenceLink', 'ReadRecord', 'SearchRecord', 'HumanDecision', 'OutputRecord'}


def fault(name):
    if os.environ.get('EVIDENCE_REVIEWER_FAILPOINT') == name:
        os._exit(86)


def signed(value):
    out = copy.deepcopy(value)
    out.pop('integrity_sha256', None)
    out['integrity_sha256'] = L.checksum(out)
    return out


def snapshot(work, current):
    return dict(project=copy.deepcopy(work['project']), outcome=copy.deepcopy(work['outcome']),
                current=copy.deepcopy(current), record_order=list(work['records']),
                unit_version_ids=list(work['units']), artifact_ids=[a['id'] for a in work['artifacts']],
                assessment_sha256=work['assessment_sha256'])


def upgrade(base):
    L.thaw(base)  # Verify before conversion; never repair by silently discarding data.
    out = copy.deepcopy(base)
    out.pop('integrity_sha256', None)
    if base['schema_version'] == SCHEMA:
        return out
    w = L.thaw(base)
    out.update(schema_version=SCHEMA, run_order=[base['latest_run_id']],
               run_snapshots={base['latest_run_id']: snapshot(w, base['current'])})
    return out


def append_revision(ledger, body, run, reason, triggers):
    eid = body['id']
    previous = ledger['current'].get(eid)
    before = ledger['revisions'][previous]['after'] if previous else None
    if before == body:
        return False
    if before:
        L.require(before['kind'] == body['kind'] and body['kind'] not in IMMUTABLE, 'Immutable event/source record cannot be rewritten')
    rid = L.uid()
    ledger['revisions'][rid] = dict(id=rid, entity_id=eid, previous_revision_id=previous,
        run_id=run['id'], time=run['finished_at'], actor='Codex session with deterministic tools',
        before=copy.deepcopy(before), after=copy.deepcopy(body), reason=reason, trigger_refs=triggers)
    ledger['current'][eid] = rid
    if eid not in ledger['entities']:
        ledger['entities'][eid] = dict(id=eid, kind=body['kind'], created_run_id=run['id'])
    return True


def build(base, work):
    out = upgrade(base)
    run = work['run']
    L.require(run['previous_run_id'] == base['latest_run_id'], 'Update base is not the latest completed run')
    L.require(run['id'] not in out['runs'], 'Run already committed')
    out['runs'][run['id']] = copy.deepcopy(run)
    out['run_order'].append(run['id'])
    L.require(set(base['current']) <= set(work['records']), 'Historical entities may not be deleted')
    triggers = [c['id'] for c in run.get('changes', [])] + run.get('changed_version_ids', [])
    for eid, body in work['records'].items():
        reason = work.get('_revision_reasons', {}).get(eid, run.get('reason', 'Initial record in this review'))
        append_revision(out, body, run, reason, triggers)
    out.update(project=copy.deepcopy(work['project']), latest_run_id=run['id'],
               record_order=list(work['records']), units=copy.deepcopy(work['units']),
               artifacts=copy.deepcopy(work['artifacts']), outcome=copy.deepcopy(work['outcome']),
               assessment_sha256=work['assessment_sha256'])
    out['run_snapshots'][run['id']] = snapshot(work, out['current'])
    return out


def as_of(ledger, run_id):
    if ledger['schema_version'] != SCHEMA:
        L.require(run_id == ledger['latest_run_id'], 'Unknown run')
        return L.thaw(ledger)
    snap = ledger['run_snapshots'][run_id]
    index = ledger['run_order'].index(run_id)
    known = ledger['run_order'][:index + 1]
    records = {eid: copy.deepcopy(ledger['revisions'][snap['current'][eid]]['after']) for eid in snap['record_order']}
    work = dict(project=copy.deepcopy(snap['project']), run=copy.deepcopy(ledger['runs'][run_id]),
                records=records, units={v: copy.deepcopy(ledger['units'][v]) for v in snap['unit_version_ids']},
                artifacts=[copy.deepcopy(a) for a in ledger['artifacts'] if a['id'] in snap['artifact_ids']],
                outcome=copy.deepcopy(snap['outcome']), assessment_sha256=snap['assessment_sha256'],
                _known_run_ids=known,
                _history=[copy.deepcopy(r) for r in ledger['revisions'].values()
                          if ledger['runs'][run_id]['previous_run_id'] is not None and r['run_id'] in known and r['after']['kind'] in BUSINESS],
                _run_order=known)
    if not work['run'].get('visual_checks_version'):
        from visual_checks import legacy_checks
        work['_legacy_visual_checks'] = legacy_checks(ledger, run_id)
    return work


def thaw(ledger):
    unsigned = {k: v for k, v in ledger.items() if k != 'integrity_sha256'}
    L.require(ledger.get('integrity_sha256') == L.checksum(unsigned), 'Ledger integrity mismatch; preserve damaged file and run recover')
    order = ledger.get('run_order', [])
    L.require(order and len(order) == len(set(order)) and set(order) == set(ledger['runs']), 'Invalid run order')
    L.require(ledger['latest_run_id'] == order[-1], 'Latest run pointer mismatch')
    L.require(set(ledger['entities']) == set(ledger['current']) == set(ledger['record_order']) and len(ledger['record_order']) == len(ledger['current']), 'Invalid entity/current/order mapping')
    L.require(set(ledger['run_snapshots']) == set(order), 'Missing run snapshot')
    reachable, events = set(), set()
    positions = {r: i for i, r in enumerate(order)}
    for i, rid in enumerate(order):
        run = ledger['runs'][rid]
        L.require(run['id'] == rid and run['state'] == 'completed', 'Uncommitted run in authoritative ledger')
        L.require(run['previous_run_id'] == (order[i-1] if i else None), 'Broken run chain')
        if run.get('event_id'):
            L.require(run['event_id'] not in events, 'Duplicate update event')
            events.add(run['event_id'])
        snap = ledger['run_snapshots'][rid]
        L.require(set(snap['current']) == set(snap['record_order']) and len(snap['record_order']) == len(snap['current']), 'Invalid historical record order')
        for eid, rev_id in snap['current'].items():
            rev = ledger['revisions'].get(rev_id)
            L.require(rev and rev['entity_id'] == eid and positions[rev['run_id']] <= i, 'Historical snapshot cites a future/missing revision')
        L.require(set(snap['unit_version_ids']) == set(run['source_version_snapshot']), 'Historical material snapshot mismatch')
        active = run.get('active_source_version_ids', run['source_version_snapshot'])
        L.require(set(active) <= set(run['source_version_snapshot']) and len(active) == len(set(active)), 'Invalid active source snapshot')
        if i:
            prev = ledger['run_snapshots'][order[i-1]]
            L.require(set(prev['current']) <= set(snap['current']), 'Historical entity disappeared')
        aswork = as_of(ledger, rid)
        L.validate_records(aswork)
        from visual_checks import validate as validate_visual, current_checks
        if i: validate_visual(aswork, current_checks(as_of(ledger, order[i-1])))
        if i and ledger['runs'][order[i-1]].get('visual_checks_version'):
            L.require(run.get('visual_checks_version') == 1, 'Visual check persistence cannot be disabled')
        retirements = run.get('evidence_link_retirements', [])
        if i:
            previous_retirements = ledger['runs'][order[i-1]].get('evidence_link_retirements', [])
            L.require(retirements[:len(previous_retirements)] == previous_retirements, 'Historical link retirements changed or disappeared')
        for retirement in retirements:
            lid = retirement['link_id']; retired_run = retirement['retired_in_run_id']
            L.require(positions[ledger['entities'][lid]['created_run_id']] < positions[retired_run] <= i,
                      'Link retirement must follow original adoption')
        if run.get('update_summary'):
            pending = {x['id'] for x in aswork['records'].values() if x['kind'] in BUSINESS and x.get('review_freshness') == 'needs_review'}
            L.require(pending == set(run['update_summary']['pending_ids']), 'Pending review summary differs from current objects')
    for eid, tail in ledger['current'].items():
        seen = set()
        while tail:
            L.require(tail not in seen, 'Revision cycle')
            seen.add(tail); reachable.add(tail)
            rev = ledger['revisions'].get(tail)
            L.require(rev and rev['id'] == tail and rev['entity_id'] == eid and rev['after']['id'] == eid, 'Broken revision identity')
            L.require(rev['after']['kind'] == ledger['entities'][eid]['kind'], 'Revision kind changed')
            L.require(L.nonempty(rev.get('reason')), 'Revision needs reason')
            previous = rev['previous_revision_id']
            if previous:
                old = ledger['revisions'].get(previous)
                L.require(old and old['entity_id'] == eid and old['after'] == rev['before'], 'Revision before/after chain mismatch')
                L.require(positions[old['run_id']] < positions[rev['run_id']], 'Revision chronology mismatch')
                L.require(rev['before'] != rev['after'], 'Meaningless duplicate revision')
                L.require(rev['after']['kind'] not in IMMUTABLE, 'Immutable record has a later revision')
            else:
                L.require(rev['before'] is None and ledger['entities'][eid]['created_run_id'] == rev['run_id'], 'Invalid initial revision')
            tail = previous
    L.require(reachable == set(ledger['revisions']), 'Orphan revision')
    current = ledger['run_snapshots'][order[-1]]
    for field in ('current', 'record_order', 'project', 'outcome', 'assessment_sha256'):
        L.require(ledger[field] == current[field], 'Latest snapshot/top-level mismatch: ' + field)
    return as_of(ledger, order[-1])


def render(work, project):
    """Use the stable source/detail formatter, separating current tasks from retired history."""
    w = copy.deepcopy(work)
    w['_renderer_version'] = 3
    w['_version_labels'] = True
    retired = [x for x in w['records'].values() if x['kind'] == 'Finding' and (x['disposition'] != 'active' or x['workflow'] == 'closed')]
    retired_ids = {x['id'] for x in retired}
    w['records'] = {i: x for i, x in w['records'].items() if i not in retired_ids}
    # Keep retired records for references in the formatter; suppress only their presentation.
    # Other objects never refer to Finding fields in base rendering, so restores are unnecessary.
    result = L.render(w, project)
    text = result['review.md'].replace('## 最终复核与初始历史', '## 本轮最终复核')
    text = text.replace(f"本轮创建稳定ID、原件版本及初始Revision；所有判断与导出对应 {work['run']['id']}。未实施跨批补证更新。",
                        f"本轮判断、变化与导出对应 {work['run']['id']}；历史见同轮history.md。")
    run = work['run']
    pending = [x for x in work['records'].values() if x['kind'] in BUSINESS and x.get('review_freshness') == 'needs_review']
    if pending:
        notice = '本轮仍有待复核对象；下列旧判断仅供追溯，不能称为已按新材料验证。'
        text = text.replace('\n\n', '\n\n' + notice + '\n\n', 1)
        text += '\n## 尚待复核\n\n'
        for x in pending:
            label = next((x[k] for k in ('proposition', 'objective', 'purpose', 'expected_fact', 'name') if x.get(k)), x['id'])
            text += '- ' + label + '\n'
    text += '\n## 本轮变化与效力\n\n'
    for c in run.get('changes', []):
        text += f"- {c['type']}：{c['description']}。\n"
    if not run.get('changes'): text += '本轮未登记材料或范围变化。\n'
    if retired:
        text += '\n### 已撤回、替代或关闭的意见（不列入当前待办）\n\n'
        for f in retired:
            text += f"- {f['proposition']}：{f['assessment']} / {f['workflow']} / {f['disposition']}；{f.get('closure_reason') or f.get('summary')}\n"
    active = run.get('active_source_version_ids', run['source_version_snapshot'])
    inactive = [v for v in run['source_version_snapshot'] if v not in active]
    if inactive:
        text += '\n历史原件快照仍保留；以下版本已不作为本轮活动版本：' + '、'.join(inactive) + '。\n'
    access = [s for s in work['records'].values() if s['kind'] == 'Source' and s.get('access_status') not in {None, 'available'}]
    if access:
        text += '\n### 原来源当前可用性\n\n'
        for source in access:
            text += f"- {source['actual_name']}：{source['access_status']}；已取得的历史快照与出处继续保留，此状态不说明历史事实或规则效力改变。\n"
    text += f"\n[本轮变更记录](<{Path(project)/'outputs'/run['id']/'changes.md'}>)；[截至本轮的判断历史](<{Path(project)/'outputs'/run['id']/'history.md'}>)\n"
    result['review.md'] = text
    change_lines = ['# 本轮变更与影响复核', '', f"轮次：{run['id']}；上一轮：{run.get('previous_run_id') or '无'}", '']
    for c in run.get('changes', []):
        change_lines += [f"## {c['type']}：{c['description']}", '', '```json', json.dumps(c, ensure_ascii=False, indent=2, sort_keys=True), '```', '']
    for s in run.get('screening', []):
        change_lines += ['主题筛查：' + json.dumps(s, ensure_ascii=False, sort_keys=True), '']
    for d in run.get('impact_review', []):
        change_lines += ['影响复核：' + json.dumps(d, ensure_ascii=False, sort_keys=True), '']
    result['changes.md'] = '\n'.join(change_lines)
    history_lines = ['# 截至本轮的判断历史', '', '历史与现状分开；撤回、整改关闭和待复核均保留原判断。', '']
    revisions = [r for r in work.get('_history', []) if r['after']['kind'] in BUSINESS]
    positions = {r: i for i, r in enumerate(work.get('_run_order', [run['id']]))}
    for rev in sorted(revisions, key=lambda x: (positions[x['run_id']], x['entity_id'], x['id'])):
        after, before = rev['after'], rev['before'] or {}
        fields = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        history_lines += [f"## {after['kind']} / {after['id']}", '', f"轮次：{rev['run_id']}；时间：{rev['time']}；理由：{rev['reason']}", '',
                         '```json', json.dumps({k: {'before': before.get(k), 'after': after.get(k)} for k in fields}, ensure_ascii=False, indent=2, sort_keys=True), '```', '']
    if not revisions:
        history_lines += ['初始轮次的完整对象和初始Revision保存在权威台账；尚无跨轮变更。', '']
    result['history.md'] = '\n'.join(history_lines)
    open_gaps = sum(x['kind'] == 'EvidenceGap' and x['state'] == 'open' for x in work['records'].values())
    result['handoff.md'] = '\n'.join(['# 项目交接', '', '目标：' + work['project']['goal'], '',
        f"最后完成轮次：{run['id']}；上一轮：{run.get('previous_run_id') or '无'}；当前主稿：{work['project'].get('selected_main_version') or '不要求'}", '',
        f"开放缺证：{open_gaps}；待复核对象：{len(pending)}。本轮完成不表示全部业务事项已有定论。", '',
        f"[当前结果](<{Path(project)/'outputs'/run['id']/'review.md'}>)；[变更](<{Path(project)/'outputs'/run['id']/'changes.md'}>)；[历史](<{Path(project)/'outputs'/run['id']/'history.md'}>)", '',
        'ledger/ledger.json为唯一权威台账。新材料用review.py update；提交中断用recover；缺失导出用export。历史文件不可作为最新结果，原件和既有台账不手改。', ''])
    return result


def write_exports(project, ledger, api):
    order = ledger.get('run_order', [ledger['latest_run_id']])
    for rid in order:
        work = as_of(ledger, rid)
        api.check_files(project, work)
        exports = L.render(work, project)
        for number, (name, content) in enumerate(exports.items()):
            rel = f'outputs/{rid}/{name}'
            record = next(r for r in work['records'].values() if r['kind'] == 'OutputRecord' and r['path'] == rel)
            L.require(hashlib.sha256(content.encode()).hexdigest() == record['sha256'], 'Renderer differs from committed output fingerprint: ' + rel)
            path = project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.tmp-' + L.uid())
            with tmp.open('xb') as f:
                f.write(content.encode()); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
            if rid == ledger['latest_run_id'] and number == 0: fault('after_first_export')
    work = L.thaw(ledger)
    api.check_files(project, work, check_outputs=True)
    fault('before_pointer')
    records = [x for x in work['records'].values() if x['kind'] == 'OutputRecord' and x['run_id'] == ledger['latest_run_id']]
    L.atomic_json(project / 'outputs/current.json', dict(run_id=ledger['latest_run_id'], ledger_sha256=ledger['integrity_sha256'], files=[x['path'] for x in records]))
    fault('after_pointer')


def finalize(project, work, api):
    base = api.load(project / 'ledger/ledger.json')
    L.require(base['integrity_sha256'] == work['update_context']['base_sha256'], 'Base ledger changed since update began')
    api.check_files(project, work)
    L.validate_records(work)
    work['run'].update(state='completed', finished_at=L.now(), unfinished_steps=[])
    ledger = build(base, work)
    # Freeze revision IDs before rendering history, then add immutable export records.
    preview = as_of(ledger, work['run']['id'])
    exports = L.render(preview, project)
    for name, content in exports.items():
        eid = L.uid()
        body = dict(id=eid, kind='OutputRecord', run_id=work['run']['id'], output_kind=name.split('.')[0],
                    path=f"outputs/{work['run']['id']}/{name}", renderer_version=6,
                    sha256=hashlib.sha256(content.encode()).hexdigest(), source_role='workpaper_or_draft',
                    actual_confirmation_status='unconfirmed', evidence_ids=[x['id'] for x in work['records'].values() if x['kind'] == 'Evidence'])
        append_revision(ledger, body, work['run'], 'Export of this committed run', [])
        ledger['record_order'].append(eid)
    snap = ledger['run_snapshots'][work['run']['id']]
    snap.update(current=copy.deepcopy(ledger['current']), record_order=list(ledger['record_order']))
    ledger = signed(ledger)
    L.thaw(ledger)
    backup = project / 'ledger/backups' / (base['latest_run_id'] + '-' + base['integrity_sha256'] + '.json')
    if backup.exists(): L.require(api.load(backup) == base, 'Existing backup differs')
    else: L.atomic_json(backup, base)
    candidate = project / 'staging/candidates' / (work['run']['id'] + '.json')
    L.atomic_json(candidate, ledger)
    receipt = dict(state='prepared', run_id=work['run']['id'], event_id=work['run']['event_id'],
                   candidate_path=candidate.relative_to(project).as_posix(), candidate_sha256=ledger['integrity_sha256'],
                   backup_path=backup.relative_to(project).as_posix(), base_sha256=base['integrity_sha256'])
    L.atomic_json(project / 'staging/transaction.json', receipt)
    L.atomic_json(project / 'ledger/ledger.json', ledger)
    fault('after_replace')
    write_exports(project, ledger, api)
    receipt['state'] = 'completed'
    L.atomic_json(project / 'staging/transaction.json', receipt)
    L.atomic_json(project / 'ledger/transactions' / (work['run']['id'] + '.json'), receipt)
    work['run']['state'] = 'completed'; api.save_work(project, work)
    return dict(state='completed', run_id=work['run']['id'], review=str(project / 'outputs' / work['run']['id'] / 'review.md'), errors=[])


def recover(args, api):
    from recovery import recover as restore
    return restore(args, api)
