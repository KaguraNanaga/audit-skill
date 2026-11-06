"""Deterministic candidate accounting and delivery states; no evidence inference."""
import re
from . import ledger as L

VERSION = 1
TYPES = {'pending_read', 'tool_blocked', 'not_provided', 'insufficient'}
DECISIONS = {'unread', 'tool_blocked', 'irrelevant', 'insufficient', 'sufficient'}


def search_scope(work):
    run = work['run']
    return list(dict.fromkeys(run.get('active_source_version_ids', run['source_version_snapshot'])
        + run.get('changed_version_ids', [])
        + ([work['project']['selected_main_version']] if work['project'].get('selected_main_version') else [])))


def source_name(work, vid):
    version = work['records'][vid]
    return version.get('actual_name') or work['records'][version['source_id']]['actual_name']


def filename_hits(work, versions, expression):
    pattern = re.compile(expression, re.IGNORECASE)
    return [dict(source_version_id=vid, match_type='filename', actual_name=source_name(work, vid),
                 text=source_name(work, vid), locator={'unit': 'source_name'},
                 warning='文件名命中，仅供定位；不表示正文已读或事实已获证。')
            for vid in versions if pattern.search(source_name(work, vid))]


def candidate_ids(work, gap):
    """Account for all saved filename hits, independently of terminal pagination."""
    records = work['records']; candidates = set(); covered = set()
    for sid in gap.get('search_record_ids', []):
        search = records.get(sid, {})
        if search.get('kind') == 'SearchRecord' and not search.get('external'):
            candidates.update(h['source_version_id'] for h in search.get('results', [])
                              if isinstance(h, dict) and isinstance(h.get('source_version_id'), str)
                              and h['source_version_id'] in work['units'])
        if search.get('kind') != 'SearchRecord' or search.get('search_target') not in {'names', 'both'}:
            continue
        L.require(search.get('search_version') == 2 and not search.get('external'), '缺证候选搜索需使用 search --target names 或 both')
        versions = search.get('material_snapshot', [])
        L.require(isinstance(versions, list) and set(versions) <= set(work['units']), '候选搜索版本范围无效')
        keywords = search.get('keywords', [])
        L.require(isinstance(keywords, list) and len(keywords) == 1 and L.nonempty(keywords[0]), '候选搜索缺少真实检索式')
        expected = filename_hits(work, versions, keywords[0])
        actual = [h for h in search.get('results', []) if isinstance(h, dict) and h.get('match_type') == 'filename']
        L.require(actual == expected, '文件名候选与检索式/来源版本不一致；重新执行搜索')
        covered.update(versions)
        candidates.update(h['source_version_id'] for h in expected)
    L.require(set(search_scope(work)) <= covered,
              '缺证前须检索本轮全部活动来源的文件名：search --target names（或 both）；旧搜索未覆盖新增版本时请重查')
    return candidates


def validate(work):
    records = work['records']
    enabled = work['run'].get('gap_checks_version')
    if enabled is not None: L.require(enabled == VERSION, 'Unknown gap checks version')
    if not enabled and not any(r['kind'] == 'EvidenceGap' and r.get('validation_version', 1) >= 3 for r in records.values()):
        return
    # Keep the additional index proportional to declared candidate scopes, not the full ledger.
    wanted = set()
    for g in records.values():
        if g.get('kind') == 'EvidenceGap' and isinstance(g.get('candidate_reviews'), list):
            for item in g['candidate_reviews']:
                if isinstance(item, dict) and isinstance(item.get('source_version_id'), str) and isinstance(item.get('unit_ids', []), list):
                    wanted.update((item['source_version_id'], u) for u in item.get('unit_ids', []) if isinstance(u, str))
    units = {(v, u['id']): u for v, rows in work['units'].items() for u in rows if (v, u['id']) in wanted}
    viewed = {(r['source_version_id'], r['unit_id']) for r in records.values()
              if r['kind'] == 'ReadRecord' and r.get('state') == 'viewed' and r.get('artifact_id') and L.nonempty(r.get('observation'))}
    for gap in records.values():
        if gap['kind'] != 'EvidenceGap' or gap.get('validation_version', 1) < 3:
            continue
        L.require(enabled == VERSION, 'New gap records require gap_checks_version=1; cannot disable the checks')
        if gap.get('state') != 'open': continue
        prefix = '缺口 ' + gap['id'] + '：'
        L.require(gap.get('gap_type') in TYPES, prefix + '填写 gap_type：pending_read/tool_blocked/not_provided/insufficient')
        required = candidate_ids(work, gap)
        reviews = gap.get('candidate_reviews')
        L.require(isinstance(reviews, list), prefix + '填写 candidate_reviews，未读候选用 unread，不伪造已核')
        seen = set(); decisions = set()
        for item in reviews:
            L.require(isinstance(item, dict), prefix + '候选核查必须是对象')
            vid = item.get('source_version_id'); decision = item.get('decision')
            L.require(isinstance(vid, str) and vid in work['units'] and vid not in seen, prefix + '候选来源不存在或重复')
            L.require(isinstance(decision, str) and decision in DECISIONS and L.nonempty(item.get('reason')), prefix + '候选核查需明确 decision 和 reason')
            seen.add(vid); decisions.add(decision)
            ids = item.get('unit_ids', []); evidence_ids = item.get('evidence_ids', [])
            L.require(isinstance(ids, list) and all(isinstance(u, str) for u in ids) and len(ids) == len(set(ids)) and all((vid, u) in units for u in ids), prefix + '候选核查单元范围无效')
            L.require(isinstance(evidence_ids, list) and all(isinstance(e, str) for e in evidence_ids), prefix + 'evidence_ids 必须是ID列表')
            evidence = [records.get(e, {}) for e in evidence_ids]
            L.require(all(e.get('kind') == 'Evidence' and e.get('source_version_id') == vid and e.get('unit_id') in ids for e in evidence), prefix + '核查依据须属于本候选及所列单元')
            if decision in {'irrelevant', 'insufficient', 'sufficient'}:
                L.require(bool(ids) and bool(evidence), prefix + '已核/排除候选需列真实单元和 Evidence；只有文件名不能排除')
                pending_units = {u['id'] for u in work['units'][vid]
                                 if u.get('state') in {'manual_check', 'failed', 'unread'}
                                 and u.get('locator', {}).get('unit') not in {'ocr_derived', 'table_query_derived'}}
                L.require(pending_units <= set(ids), prefix + '候选还有未列入核查范围的扫描/失败/未抽取单元；先补看或保持 unread/tool_blocked')
                cited = {e['unit_id'] for e in evidence}
                for uid in ids:
                    unit = units[(vid, uid)]
                    L.require(unit.get('locator', {}).get('unit') not in {'ocr_derived', 'table_query_derived'}, prefix + '候选核查回到原件单元，不用派生单元代替')
                    if unit.get('state') in {'manual_check', 'failed', 'unread'}:
                        L.require((vid, uid) in viewed, prefix + '扫描/未抽取单元尚无实际 observations：' + vid + '/' + uid)
                    else:
                        L.require(uid in cited or (vid, uid) in viewed, prefix + '所列已核单元缺实际 Evidence/observations：' + uid)
        L.require(required <= seen, prefix + '文件名候选尚未逐项处理：' + ', '.join(sorted(required - seen)) + '；包括分页后部命中')
        kind = gap['gap_type']
        if kind in {'not_provided', 'insufficient'}:
            L.require(not decisions & {'unread', 'tool_blocked', 'sufficient'}, prefix + '候选仍未读/受阻或已声明足以证明；先继续核查、调整缺口类别或据实关闭，不能作为对外缺证')
            L.require(L.nonempty(gap.get('minimal_request')), prefix + '对外补证需具体最小请求')
            if kind == 'not_provided':
                L.require(decisions <= {'irrelevant'}, prefix + '存在已核相关材料时使用 insufficient，并说明不足')
            else:
                L.require('insufficient' in decisions, prefix + '已核但不足需至少一项带依据的 insufficient 候选')
        else:
            L.require(('unread' in decisions if kind == 'pending_read' else 'tool_blocked' in decisions), prefix + '执行缺口需对应未读/工具受阻候选')
            L.require(any(records.get(t, {}).get('execution_state') in {'not_started', 'partial'} for t in gap.get('task_ids', [])), prefix + '执行缺口须关联未完成任务并记录下一步')

    if not enabled: return
    delivery = work.get('outcome', {}).get('delivery')
    pending = pending_items(work)
    if delivery is not None:
        L.require(isinstance(delivery, dict) and set(delivery) <= {'status', 'reason', 'next_step'}, 'delivery 字段无效')
        L.require(delivery.get('status') in {'partial', 'recorded_scope_complete'}, 'delivery.status 必须为 partial 或 recorded_scope_complete')
    if pending or (delivery or {}).get('status') == 'partial':
        L.require(isinstance(delivery, dict) and delivery.get('status') == 'partial'
                  and L.nonempty(delivery.get('reason')) and L.nonempty(delivery.get('next_step')),
                  '仍有未完成程序/待核缺口：继续核查；阶段性保存时填写 delivery={status:partial,reason:实际原因,next_step:具体续办}，提交成功不表示业务完成')
    if (delivery or {}).get('status') == 'recorded_scope_complete':
        L.require(any(r['kind'] == 'ReviewTask' for r in records.values()), '未登记业务任务，不能声明已登记程序完成')


def pending_items(work):
    pending = []
    for r in work['records'].values():
        if r['kind'] == 'ReviewTask' and r.get('execution_state') in {'not_started', 'partial'}:
            pending.append(r['id'])
        elif r.get('review_freshness') == 'needs_review':
            pending.append(r['id'])
        elif r['kind'] == 'EvidenceGap' and r.get('state') == 'open' and (
                r.get('validation_version', 1) < 3 or r.get('gap_type') in {'pending_read', 'tool_blocked'}):
            pending.append(r['id'])
    return pending


def summary(work):
    pending = pending_items(work)
    delivery = work.get('outcome', {}).get('delivery') or {}
    tasks = [r for r in work['records'].values() if r['kind'] == 'ReviewTask']
    state = 'partial' if pending or delivery.get('status') == 'partial' else 'recorded_scope_complete' if tasks else 'not_assessed'
    return dict(review_state=state, pending_count=len(pending), pending_ids=pending[:20],
                pending_omitted=max(0, len(pending)-20),
                delivery_reason=delivery.get('reason'), next_step=delivery.get('next_step'),
                review_notice='仅反映已登记程序；台账提交、结构有效或程序完成均不表示审计结论已获确认。')
