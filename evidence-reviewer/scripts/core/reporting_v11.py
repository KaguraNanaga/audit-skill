"""Renderer 11: candidate checks and explicit partial delivery; renderer 10 is frozen."""
import hashlib
import json
from collections import Counter, defaultdict
from urllib.parse import quote

from . import ledger as L
from .persistence import atomic_bytes


def jsonl(rows):
    return ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n' for row in rows)


def text(value):
    if value is None: return '未记录'
    if isinstance(value, (dict, list)): return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def render(work, project=None, relative_root='../..', output_directory='outputs'):
    """Do not call legacy renderers or copy/JSON-normalize the entire work packet."""
    records, run, outcome = work['records'], work['run'], work['outcome']
    groups = defaultdict(list)
    for row in records.values(): groups[row['kind']].append(row)
    from .reporting import reading_coverage
    coverage = reading_coverage(work)
    from .visual_checks import current_checks
    visual = current_checks(work)
    wanted_units = {(e['source_version_id'], e['unit_id']) for e in groups['Evidence']}
    for c in groups['Calculation']:
        wanted_units.update((i['source_version_id'], i['unit_id']) for i in c['inputs'] if i.get('source_version_id'))
    unit_index = {(v, u['id']): u for v, units in work['units'].items() for u in units if (v, u['id']) in wanted_units}

    def link(label, path, fragment=None):
        label = str(label).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ')
        return '[' + label + '](<' + quote(relative_root + '/' + path, safe='/.-_~') + ('#' + quote(fragment, safe='-_.') if fragment else '') + '>)'

    def output_link(label, name, fragment=None):
        return link(label, output_directory + '/' + run['id'] + '/' + name, fragment)

    def source(vid, uid=None):
        version = records[vid]; src = records[version['source_id']]
        name = version.get('actual_name') or src['actual_name']
        label = link(name, version['local_snapshot']) if version.get('local_snapshot') else name + '（正文快照未取得）'
        if uid:
            locator = unit_index.get((vid, uid), {}).get('locator', {})
            label += '；' + L.locator_text(locator)
        return label + '；版本 ' + vid

    def evidence(eid, detail=False):
        e = records[eid]; vid = e['source_version_id']; uid = e['unit_id']
        if detail: return source(vid, uid) + '；证据 ' + eid
        version = records[vid]
        name = version.get('actual_name') or records[version['source_id']]['actual_name']
        locator = L.locator_text(unit_index.get((vid, uid), {}).get('locator', {}))
        return output_link(name + ('（' + locator + '）' if locator else ''), 'evidence.md', 'e-' + eid)

    def bases(row):
        result = [evidence(eid) for eid in row.get('evidence_ids', [])]
        result += [output_link(f"复算：{records[i]['purpose']} = {records[i]['result']} {records[i]['unit']}", 'calculations.md', 'c-' + i) for i in row.get('calculation_ids', [])]
        result += [output_link('规则：' + records[i]['name'], 'rules.md', 'r-' + i) + '；' + records[i]['applicability_reason'] for i in row.get('rule_ids', [])]
        result += ['任务：' + records[i]['objective'] for i in row.get('task_ids', [])]
        return '；'.join(result)

    def fields(row, names):
        return [label + '：' + text(row.get(key)) + '\n' for key, label in names]

    tasks = groups['ReviewTask']
    pending = [r for r in records.values() if r.get('review_freshness') == 'needs_review']
    incomplete = [t for t in tasks if t['execution_state'] in {'not_started', 'partial'}]
    gaps = [g for g in groups['EvidenceGap'] if g['state'] == 'open']
    external_gaps = [g for g in gaps if g.get('validation_version', 1) >= 3
                     and g.get('gap_type') in {'not_provided', 'insufficient'} and g.get('review_freshness') != 'needs_review']
    execution_gaps = [g for g in gaps if g not in external_gaps]
    from .gap_checks import summary
    delivery = summary(work)
    delivery_label = {'partial': '阶段性成果：仍有未完成程序或待核材料',
                      'recorded_scope_complete': '已登记程序完成：不代表整个审计完成或结论已确认',
                      'not_assessed': '未登记业务程序完成状态'}[delivery['review_state']]
    active_findings = [f for f in groups['Finding'] if f['disposition'] == 'active' and f['workflow'] != 'closed']
    active_ids = {f['id'] for f in active_findings}
    retired = [f for f in groups['Finding'] if f['id'] not in active_ids]
    counts = dict(Counter(t['execution_state'] for t in tasks))
    overview = (f"登记来源版本 {len(run['source_version_snapshot'])}；未完成业务任务 {len(incomplete)}；"
                f"开放缺证 {len(gaps)}；待复核对象 {len(pending)}；读取/原页核查限制 {len(coverage['issues'])}。")
    lines = ['# 审查结果', '', '供审计人员复核确认的工作草稿。', '',
             delivery_label, '', '阶段性原因：' + text(delivery.get('delivery_reason')),
             '下一步：' + text(delivery.get('next_step')), '',
             '目标：' + work['project']['goal'], '', f"轮次：{run['id']}；台账提交时间：{run['finished_at']}", '',
             overview, '', '上述计数反映已登记状态；结构有效不表示业务核查完成，extracted不表示执行会话已阅读。', '',
             '## 本次结果', '']
    for answer in outcome['answers']:
        lines += [answer['text'], '', bases(answer), '']
    lines += ['## 限制与未完成程序', '']
    lines += ['- ' + text(x) for x in outcome.get('limitations', [])]
    for t in incomplete:
        lines += [f"- {t['objective']}：{t['execution_state']} / {t['result']}；未覆盖：{text(t['uncovered_scope'])}；下一步：{text(t['next_step'])}"]
    for row in pending:
        label = next((row[k] for k in ('objective', 'proposition', 'expected_fact', 'purpose', 'name') if row.get(k)), row['id'])
        lines += ['- 待复核：' + label + '；旧判断仅供追溯。']
    lines += ['', '自动读取限制按文件/阶段汇总如下；完整逐单元明细见' + output_link('读取限制附录', 'coverage.jsonl') + '。', '']
    issue_counts = Counter((i['file'], i['stage']) for i in coverage['issues'])
    for (name, stage), count in sorted(issue_counts.items())[:20]:
        lines += [f'- {name}；{stage}；{count}项']
    if len(issue_counts) > 20: lines += [f'- 另有 {len(issue_counts)-20} 组，见完整附录。']
    lines += ['', '## 业务检查覆盖', '', '任务执行状态：' + text(counts), '']
    for t in tasks:
        lines += ['### ' + t['objective'], '', '任务ID：' + t['id'], '']
        lines += fields(t, [('procedure','程序'), ('population','总体'), ('sampling_basis','选取依据'),
                           ('actual_scope','实际范围'), ('uncovered_scope','未覆盖范围'), ('execution_state','执行状态'),
                           ('result','结果'), ('basis','依据与边界'), ('next_step','下一步')])
    lines += ['## 问题与意见', '']
    if not active_findings: lines += ['本轮没有登记当前问题意见；这本身不代表已完成核查或不存在问题。', '']
    for f in active_findings:
        lines += ['### ' + f['proposition'], '', f['summary'], '']
        lines += fields(f, [('assessment','证据判断'), ('workflow','处理进度'), ('review_freshness','复核状态'),
                           ('impact','影响'), ('impact_basis','影响依据'), ('severity','严重程度'),
                           ('recommended_action','建议'), ('contact_role','需沟通的角色')])
        for label, key in [('支持', 'supporting_link_ids'), ('反证', 'opposing_link_ids')]:
            for lid in f.get(key, []):
                row = records[lid]
                lines += ['- ' + label + '：' + evidence(row['evidence_id']) + '；证明范围：' + text(row['supported_scope'])
                          + '；条件：' + text(row['conditions']) + '；充分程度：' + text(row['sufficiency'])
                          + '；限制：' + text(row['limitations'])]
        lines += ['', bases(f), '']
    lines += ['## 材料核查待办', '', '以下尚未完成候选核查，属于执行待办或工具限制，不能作为企业缺证清单。', '']
    for g in execution_gaps:
        lines += ['- 待核事实：' + g['expected_fact'] + '；原因：' + g['reason_insufficient']
                  + ('；旧版缺口尚未按候选核查规则复核' if g.get('validation_version', 1) < 3 else '；类型：' + text(g.get('gap_type')))]
        for candidate in g.get('candidate_reviews', [])[:10]:
            lines += ['  - 候选：' + source(candidate['source_version_id']) + '；' + candidate['decision'] + '；' + candidate['reason']]
        if len(g.get('candidate_reviews', [])) > 10: lines += ['  - 更多候选及全部处理依据见records.jsonl。']
    if not execution_gaps: lines += ['未登记材料核查待办。', '']
    lines += ['', '## 必要补充材料', '', '以下已登记目录检索和候选核查；补证必要性由执行者判断，结构校验不证明材料不存在。', '']
    if not external_gaps: lines += ['本次没有经过候选核查后登记的对外补证要求。', '']
    for g in external_gaps:
        lines += ['- 待证事实：' + g['expected_fact'] + '；不足原因：' + g['reason_insufficient'] + '；最小补证：' + g['minimal_request']]
        for sid in g['search_record_ids']:
            s = records[sid]
            lines += [f"  - 搜索 {sid}：范围版本 {len(s['material_snapshot'])}；命中 {len(s['results'])}；未读项 {len(s['unread_parts'])}；完整记录见附录，不能凭未命中认定不存在。"]
        for candidate in g.get('candidate_reviews', [])[:10]:
            lines += ['  - 已核候选：' + source(candidate['source_version_id']) + '；' + candidate['decision'] + '；' + candidate['reason']]
    for g in groups['EvidenceGap']:
        if g['state'] != 'open':
            verified = bool(g.get('resolution_reason')) and (g['state'] != 'satisfied' or g.get('resolution_evidence_ids'))
            lines += ['- 已处理：' + g['expected_fact'] + '；' + g['state'] + '；' + text(g.get('resolution_reason'))
                      + ('；旧版关闭状态缺少解决依据，仍需复核' if not verified else '')]
    review_lines = lines
    lines = ['# 证据摘录及证明边界', '', '完整原文、概括及限制；正文出处使用同一证据ID。', '']
    for e in groups['Evidence']:
        lines += ['<a id="e-' + e['id'] + '"></a>', '', evidence(e['id'], detail=True), '']
        lines += fields(e, [('verbatim_quote','原文摘录'), ('reviewer_summary','审查概括'),
                           ('image_region_description','图像说明'), ('reading_method','读取方法'),
                           ('verification_state','核验状态'), ('limitations','限制')])
    evidence_text = '\n'.join(lines) + '\n'
    lines = ['# 可追溯复算', '']
    for c in groups['Calculation']:
        lines += ['<a id="c-' + c['id'] + '"></a>', '', '### ' + c['purpose'], '']
        lines += fields(c, [('formula','公式'), ('result','结果'), ('unit','单位'), ('currency','币种'),
                           ('result_kind','类型'), ('rounding','舍入'), ('assumptions','假设'), ('limitations','限制')])
        for i in c['inputs']:
            origin = source(i['source_version_id'], i['unit_id']) if i.get('source_version_id') else text(i.get('basis'))
            lines += ['- 输入：' + text(i) + '；出处：' + origin]
        lines += ['']
    calculations_text = '\n'.join(lines) + '\n'
    lines = ['# 制度依据及适用条件', '']
    for rule in groups['RuleApplication']:
        lines += ['<a id="r-' + rule['id'] + '"></a>', '', '### ' + rule['name'], '']
        lines += fields(rule, [('issuer','发布机构'), ('document_number','文号'), ('nature','性质'),
            ('published_at','发布日期'), ('effective_at','生效日期'), ('repealed_at','废止日期'), ('critical_text','关键原文'),
            ('verification_state','核验状态'), ('subjects','主体'), ('conditions','条件'), ('exceptions','例外'),
            ('behavior_time','行为时点'), ('applicability_reason','适用理由'), ('unknowns','待核'), ('official_url','官方页面'), ('attachment_url','附件')])
    rules_text = '\n'.join(lines) + '\n'
    lines = review_lines
    lines += ['', '## 证据与计算明细', '', output_link('证据摘录及证明边界', 'evidence.md') + '；' + output_link('完整复算输入与舍入', 'calculations.md') + '；' + output_link('制度依据及适用条件', 'rules.md'), '', '## 本轮最终复核', '']
    for c in outcome.get('review_checks', []):
        lines += ['- ' + c['reason'] + '；' + c['result'] + '；' + bases(c)]
    for kind, title in [('OCRAttempt', 'OCR 定位层'), ('TableQuery', '表查询来源')]:
        if groups[kind]:
            from .derived import WARNING as OCR_WARNING
            from .table_query import WARNING as QUERY_WARNING
            lines += ['', '## ' + title, '', OCR_WARNING if kind == 'OCRAttempt' else QUERY_WARNING, '',
                      '登记状态：' + text(dict(Counter(r['state'] for r in groups[kind]))) + '；完整来源、参数、失败原因及结果文件见记录附录。', '']
    lines += ['## 完整附录与历史', '',
        output_link('来源目录', 'sources.md') + '；' + output_link('记录、搜索和派生来源', 'records.jsonl') + '；'
        + output_link('全部单元', 'units.jsonl') + '；' + output_link('图像登记', 'artifacts.jsonl') + '；'
        + output_link('读取限制', 'coverage.jsonl') + '；' + output_link('变更', 'changes.md') + '；' + output_link('历史', 'history.md'), '',
        '附录为台账派生视图，可能很大；用inspect --summary、read或search-results按范围读取，勿将整份附录载入上下文。', '']
    result = {'review.md': '\n'.join(lines), 'evidence.md': evidence_text, 'calculations.md': calculations_text, 'rules.md': rules_text}
    result['records.jsonl'] = jsonl(r for r in records.values() if r['kind'] != 'OutputRecord')
    result['units.jsonl'] = jsonl(dict(source_version_id=v, unit=u) for v, units in work['units'].items() for u in units)
    result['artifacts.jsonl'] = jsonl(work['artifacts'])
    result['coverage.jsonl'] = jsonl(coverage['issues'])
    source_lines = ['# 来源目录', '', '抽取状态不表示已经阅读或完成业务核查。详细记录见records.jsonl与units.jsonl。', '']
    active = set(run.get('active_source_version_ids', run['source_version_snapshot']))
    for vid in run['source_version_snapshot']:
        v = records[vid]; s = records[v['source_id']]
        source_lines += ['- ' + source(vid) + '；活动版本=' + str(vid in active) + '；SHA256=' + str(v.get('sha256'))
                         + '；角色=' + s['role'] + '；抽取状态=' + text(dict(Counter(u['state'] for u in work['units'][vid])))]
    result['sources.md'] = '\n'.join(source_lines) + '\n'
    changes = {k: run.get(k, []) for k in ('changes', 'screening', 'impact_review')}
    result['changes.md'] = '# 本轮变更与影响复核\n\n```json\n' + json.dumps(changes, ensure_ascii=False, sort_keys=True, indent=2) + '\n```\n'
    positions = {rid: i for i, rid in enumerate(work.get('_run_order', [run['id']]))}
    revisions = sorted(work.get('_history', []), key=lambda r: (positions[r['run_id']], r['entity_id'], r['id']))
    result['history.jsonl'] = jsonl(revisions)
    history_lines = ['# 截至本轮的判断历史', '', output_link('完整跨轮修订', 'history.jsonl'), '',
                     '初始对象及Revision保存在权威台账；撤回、关闭、待复核与当前意见分开。', '']
    for f in retired:
        history_lines += ['- 已撤回、替代或关闭：' + f['proposition'] + '；' + f['disposition'] + ' / ' + f['workflow']
                          + '；' + text(f.get('closure_reason') or f.get('summary'))]
    for item in run.get('evidence_link_retirements', []):
        history_lines += ['- 停止当前采用的证据关系：' + text(item)]
    for item in visual: history_lines += ['- 原页视觉核查沿革：' + text(item)]
    result['history.md'] = '\n'.join(history_lines) + '\n'
    handoff = ['# 项目交接', '', delivery_label, '', '阶段性原因：' + text(delivery.get('delivery_reason')),
               '下一步：' + text(delivery.get('next_step')), '', '目标：' + work['project']['goal'], '', '轮次：' + run['id'], '', overview, '',
               output_link('当前结果和待办', 'review.md') + '；' + output_link('读取限制', 'coverage.jsonl') + '；' + output_link('历史', 'history.md'), '',
               'ledger/ledger.json为权威台账。新材料用update；提交中断用recover；缺失导出用export。', '',
               '完成提交不表示业务程序全部完成；继续时先读当前结果的“限制与未完成程序”和任务next_step。', '']
    if incomplete or gaps or pending:
        handoff += ['## 继续处理', '']
        for t in incomplete[:10]:
            handoff += ['- 程序：' + t['objective'] + '；未覆盖：' + text(t['uncovered_scope']) + '；下一步：' + text(t['next_step'])]
        for g in execution_gaps[:10]:
            handoff += ['- 先完成材料核查：' + g['expected_fact'] + '；' + g['reason_insufficient']]
        for g in external_gaps[:10]:
            handoff += ['- 待证事实：' + g['expected_fact'] + '；最小补证：' + g['minimal_request']]
        omitted_gaps = max(0,len(execution_gaps)-10) + max(0,len(external_gaps)-10)
        if len(incomplete)>10 or omitted_gaps or pending:
            handoff += [f'另有未展开的未完成程序 {max(0,len(incomplete)-10)}、开放缺证 {omitted_gaps}、待复核对象 {len(pending)}；完整内容见当前结果。']
    result['handoff.md'] = '\n'.join(handoff)
    if outcome.get('draft'):
        draft = outcome['draft']; dl = ['# ' + draft.get('title', '工作草稿'), '', '状态：草稿，未经确认。', '']
        for section in draft['sections']: dl += ['## ' + section['heading'], '', section['text'], '', bases(section), '']
        dl += ['签字：待实际签署；确认日期：未取得；确认范围：未取得。', '']
        result['draft.md'] = '\n'.join(dl)
    return result


def export_compact(project, ledger, api):
    """Opt-in new view of old runs; authoritative outputs and pointer remain untouched."""
    from . import history
    directory = project / 'outputs' / ('compact-' + L.uid())
    directory.mkdir(parents=True, exist_ok=False)
    files = {}
    order = ledger.get('run_order', [ledger['latest_run_id']])
    for rid in order:
        work = history.as_of(ledger, rid)
        exports = render(work, relative_root='../../..', output_directory=directory.relative_to(project).as_posix())
        for name, content in exports.items():
            path = directory / rid / name
            data = content.encode('utf-8'); atomic_bytes(path, data)
            files[path.relative_to(project).as_posix()] = hashlib.sha256(data).hexdigest()
    L.atomic_json(directory / 'manifest.json', dict(renderer_version=11,
        derived_from_ledger_sha256=ledger['integrity_sha256'], tool='review.py export --compact --renderer 11',
        tool_version='renderer-11', parameters={'runs': order, 'relative_to': 'containing Markdown file', 'renderer': 11},
        created_at=L.now(), files=files, limitation='Derived view; no amendment of ledger/history or audit confirmation'))
    return dict(state='completed', compact_directory=str(directory), manifest=str(directory/'manifest.json'),
                renderer_version=11, ledger_changed=False, history_changed=False)
