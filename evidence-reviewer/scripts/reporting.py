"""Renderer 6: unresolved visual scopes persist; renderer 5 is frozen separately."""
from pathlib import Path


def reading_coverage(work):
    run = work['run']; issues = []; seen = set()
    for error in list(run.get('intake_issues', [])) + list(run.get('errors', [])):
        marker = (error.get('root'), error.get('path'), str(error.get('error')), error.get('stage', 'inventory'))
        if marker in seen: continue
        seen.add(marker)
        issues.append(dict(file=str(Path(error.get('root', '')) / error.get('path', '未取得文件名')),
                           stage=error.get('stage', 'inventory'), reason=error.get('error', str(error)), uncovered_scope='该文件未能完整取得，未覆盖其内容'))
    active = set(run.get('active_source_version_ids', run['source_version_snapshot'])) | set(run.get('changed_version_ids', []))
    if work['project'].get('selected_main_version'): active.add(work['project']['selected_main_version'])
    viewed = {(r['source_version_id'], r['unit_id']) for r in work['records'].values() if r['kind'] == 'ReadRecord' and r['state'] == 'viewed'}
    for vid in sorted(active):
        version = work['records'][vid]
        name = version.get('actual_name') or work['records'][version['source_id']]['actual_name']
        if version.get('acquisition_state') in {'partial_body', 'snippet_only'}:
            issues.append(dict(file=name, source_version_id=vid, stage='web_body',
                               reason='最近取得的内容只有部分正文或摘要', uncovered_scope='本次未取得的正文及现行时效仍待核'))
        for u in work['units'].get(vid, []):
            if u['state'] in {'unread', 'failed', 'manual_check'} and (vid, u['id']) not in viewed:
                issues.append(dict(file=name, source_version_id=vid, locator=u['locator'], stage='read',
                                   reason='；'.join(u.get('errors', []) + u.get('limitations', [])) or u['state'], uncovered_scope='该单元未完成读取或原页核查'))
    from visual_checks import current_checks, observations
    for item in current_checks(work):
        if item['state'] == 'pending':
            coverage = observations(work, item['scopes'])
            scope_text = []
            for s in item['scopes']:
                v = work['records'][s['source_version_id']]
                from ledger import locator_text
                units = [locator_text(u['locator']) for u in work['units'][v['id']] if u['id'] in s['unit_ids']]
                scope_text.append((v.get('actual_name') or work['records'][v['source_id']]['actual_name']) + '（版本' + v['id'] + '；' + '、'.join(units) + '）')
            issues.append(dict(file=item['description'], stage='visual', visual_check_id=item['id'],
                reason=item['history'][-1]['reason'], scopes=item['scopes'], missing_scope=coverage['missing'],
                uncovered_scope='关键视觉变化未核，相关业务含义不能视为已确认；需核范围：' + '；'.join(scope_text)))
    return dict(state='partial' if issues else 'complete', issues=issues,
                meaning='材料读取状态，不等于业务审查充分性或原件真实性')


def render(work, project):
    from history import render as old_render
    result = old_render(work, project)
    coverage = reading_coverage(work)
    lines = ['## 自动汇总的材料读取覆盖', '', '结构校验通过不等于材料读取充分。读取状态：' + ('部分完成' if coverage['issues'] else '未登记读取失败；不代表已核查全部业务事实') + '。', '']
    for issue in coverage['issues']:
        lines += ['- 文件：' + issue['file'] + '；阶段：' + issue['stage'] + '；原因：' + str(issue['reason']) + '；未覆盖：' + issue['uncovered_scope'] + '。']
    section = '\n'.join(lines) + '\n'
    result['review.md'] += '\n' + section
    result['handoff.md'] += '\n' + section
    for source in work['records'].values():
        if source['kind'] == 'Source' and source.get('latest_acquisition_state'):
            state = source['latest_acquisition_state']; retained = source.get('retained_full_body_version_ids', [])
            text = '\n网页获取：' + source['actual_name'] + '；最近尝试=' + state + '。'
            if retained:
                text += ' 可检索完整正文版本：' + '、'.join(retained) + '；各版本取得时间见来源记录。'
            text += ' 获取成功或旧正文仍在均不自动证明规则现行有效；当前时效适用须另行核查。\n'
            result['review.md'] += text; result['handoff.md'] += text
    retired = work['run'].get('evidence_link_retirements', [])
    if retired:
        result['history.md'] += '\n## 已停止当前采用的证据关系\n\n'
        for item in retired:
            result['history.md'] += '- ' + item['link_id'] + '；停止轮次：' + item['retired_in_run_id'] + '；理由：' + item['reason'] + '\n'
    gaps = [g for g in work['records'].values() if g['kind'] == 'EvidenceGap' and g['state'] != 'open']
    if gaps:
        gap_section = '\n## 已处理的补证事项\n\n'
        for gap in gaps:
            verified = bool(gap.get('resolution_reason')) and (gap['state'] != 'satisfied' or gap.get('resolution_evidence_ids'))
            status = '已满足，有解决依据' if gap['state'] == 'satisfied' and verified else '已撤回要求，不表示取得证明' if gap['state'] == 'withdrawn' and verified else '旧版关闭状态缺少解决依据，仍需复核'
            gap_section += '- ' + gap['expected_fact'] + '：' + status + '；' + str(gap.get('resolution_reason') or '未取得解决理由') + '\n'
        result['review.md'] += gap_section
        result['handoff.md'] += gap_section
    from visual_checks import current_checks
    checks = current_checks(work)
    if checks:
        history_section = '\n## 原页视觉核查沿革\n\n'
        for item in checks:
            history_section += '- ' + item['id'] + '；' + item['description'] + '；状态：' + item['state'] + '\n'
            for e in item['history']:
                history_section += '  - 轮次：' + e['run_id'] + '；' + e['state'] + '；' + e['reason'] + '；观察：' + '、'.join(e['observation_ids']) + '\n'
            if item['state'] != 'pending':
                label = '对应范围已完成查看' if item['state']=='viewed' else '已退出相关核查范围，不表示已经查看'
                line = '\n原页核查处理：' + item['description'] + '；' + label + '；理由：' + item['history'][-1]['reason'] + '。\n'
                result['review.md'] += line; result['handoff.md'] += line
        result['history.md'] += history_section
    return result
