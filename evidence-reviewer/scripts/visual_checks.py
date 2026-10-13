"""Version/range-bound visual work, carried forward until observed or explicitly released."""
import copy
import ledger as L


def scopes_for(work, change, visual):
    wanted = {v for v in (change.get('old_version_id'), change.get('new_version_id')) if v}
    scopes = copy.deepcopy(visual.get('scopes')) if 'scopes' in visual else [
        dict(source_version_id=v, unit_ids=[u['id'] for u in work['units'][v]]) for v in sorted(wanted)]
    validate_scopes(work, scopes, wanted)
    return scopes


def validate_scopes(work, scopes, wanted=None):
    L.require(isinstance(scopes, list) and bool(scopes), 'Visual check needs a nonempty version/unit scope')
    versions = []
    for scope in scopes:
        L.require(isinstance(scope, dict) and set(scope) == {'source_version_id', 'unit_ids'}, 'Invalid visual scope fields')
        v, units = scope['source_version_id'], scope['unit_ids']; versions.append(v)
        L.require(v in work['units'] and isinstance(units, list) and bool(units) and len(set(units)) == len(units),
                  'Visual scope needs an existing version and unique nonempty unit IDs')
        L.require(set(units) <= {u['id'] for u in work['units'][v]}, 'Visual scope cites an unknown source unit')
    L.require(len(set(versions)) == len(versions), 'Duplicate visual scope version')
    if wanted is not None: L.require(set(versions) == wanted, 'Visual scope must cover each old/new version')


def observations(work, scopes, artifact_ids=None, read_ids=None):
    """Only match the exact source version, unit and registered rendering of that unit."""
    artifacts = {a['id']: a for a in work['artifacts']}
    wanted = {(s['source_version_id'], u) for s in scopes for u in s['unit_ids']}
    found = {}
    for r in work['records'].values():
        if r['kind'] != 'ReadRecord' or r.get('state') != 'viewed' or not L.nonempty(r.get('observation')): continue
        if artifact_ids is not None and r.get('artifact_id') not in artifact_ids: continue
        if read_ids is not None and r['id'] not in read_ids: continue
        pair = (r['source_version_id'], r['unit_id']); a = artifacts.get(r.get('artifact_id'))
        if pair not in wanted or not a or a['source_version_id'] != pair[0] or r.get('render_version') != a['sha256']: continue
        u = next(u for u in work['units'][pair[0]] if u['id'] == pair[1])
        if r.get('locator') != u['locator']: continue
        if work['records'][pair[0]].get('format') == '.pdf':
            if a.get('locator') != u['locator']: continue
        elif a.get('locator') not in (None, u['locator']): continue
        found.setdefault(pair, r['id'])
    return dict(complete=set(found) == wanted, observation_ids=sorted(found.values()),
                missing=[dict(source_version_id=v, unit_id=u) for v, u in sorted(wanted-set(found))])


def new_check(work, change, visual, run_id):
    return dict(id='visual-'+change['id'], change_id=change['id'], opened_run_id=run_id,
                description=change['description'], scopes=scopes_for(work, change, visual), state='pending',
                history=[dict(run_id=run_id, state='pending', reason=visual['basis'], observation_ids=[])])


def reference_blockers(work, item):
    """Follow current judgment/answer adoption, not mere archived evidence or version ancestry."""
    records = work['records']; versions = {s['source_version_id'] for s in item['scopes']}
    sources = {records[v]['source_id'] for v in versions}
    blockers = []
    if work['project'].get('selected_main_version') in versions: blockers.append('selected_main_version')
    def reaches(value, seen):
        if isinstance(value, dict):
            return any(reaches(v, seen) for k, v in value.items() if k not in {'id', 'kind'})
        if isinstance(value, list): return any(reaches(v, seen) for v in value)
        if not isinstance(value, str): return False
        if value in versions or value in sources: return True
        if value not in records or value in seen: return False
        row = records[value]
        # A version's provenance and a search's historical scope are not current adoption.
        if row['kind'] in {'Source', 'SourceVersion', 'SearchRecord', 'ReadRecord', 'OutputRecord', 'HumanDecision'}: return False
        return reaches(row, seen | {value})
    findings = [r for r in records.values() if r['kind'] == 'Finding']
    active = [r for r in findings if r['disposition'] == 'active' and r['workflow'] != 'closed']
    old_only = {i for r in findings if r not in active for key in ('claim_ids','calculation_ids','rule_ids') for i in r.get(key, [])}
    still_used = {i for r in active for key in ('claim_ids','calculation_ids','rule_ids') for i in r.get(key, [])}
    for r in records.values():
        if r['kind'] == 'Finding': include = r in active
        elif r['kind'] == 'ReviewTask': include = r.get('execution_state') != 'not_applicable'
        elif r['kind'] in {'Claim','Calculation','RuleApplication'}: include = r['id'] not in old_only-still_used
        elif r['kind'] == 'EvidenceGap': include = r.get('state') == 'open'
        else: include = False
        if include and reaches(r, {r['id']}): blockers.append(r['id'])
    for key in ('answers', 'draft', 'review_checks'):
        if reaches((work.get('outcome') or {}).get(key, []), set()): blockers.append('outcome.'+key)
    return blockers


def append_state(item, run_id, state, reason, observation_ids=None, decision=None):
    item['state'] = state
    event = dict(run_id=run_id, state=state, reason=reason, observation_ids=observation_ids or [])
    if decision: event['decision'] = decision
    item['history'].append(event)


def reconcile(work, screening, resolutions):
    run = work['run']; rows = copy.deepcopy(run.get('visual_checks', []))
    changes = {c['id']: c for c in run.get('changes', [])}
    for s in screening:
        visual = s.get('visual_check', {}); change = changes[s['change_id']]
        if not change.get('visual_check_required'): continue
        item = new_check(work, change, visual, run['id'])
        coverage = observations(work, item['scopes'], artifact_ids=visual.get('artifact_ids') if visual['state']=='viewed' else None)
        if visual['state'] == 'viewed':
            L.require(coverage['complete'], 'Changed visual requires registered actual observations covering every scoped unit of old and new versions')
        L.require(not any(r['id'] == item['id'] for r in rows), 'Duplicate visual check')
        rows.append(item)
    # Re-adoption reopens a released scope; a new round alone never closes a pending scope.
    for item in rows:
        if item['state'] == 'released':
            active = set(run.get('active_source_version_ids', run['source_version_snapshot']))
            withdrawn = item['history'][-1].get('decision') == 'withdrawn'
            if reference_blockers(work, item) or (withdrawn and active & {s['source_version_id'] for s in item['scopes']}):
                append_state(item, run['id'], 'pending', '该版本范围重新进入主稿、活动采用或当前判断，原未核事项重新开放')
        if item['state'] == 'pending':
            coverage = observations(work, item['scopes'])
            if coverage['complete']:
                append_state(item, run['id'], 'viewed', '对应来源版本和全部登记范围已有有效原页观察', coverage['observation_ids'])
    L.require(isinstance(resolutions, list), 'visual_resolutions must be a list')
    seen = set()
    for action in resolutions:
        L.require(isinstance(action, dict) and set(action) <= {'check_id','decision','reason'}, 'Invalid visual resolution fields')
        item = next((r for r in rows if r['id'] == action.get('check_id')), None)
        L.require(item and item['id'] not in seen and L.nonempty(action.get('reason')), 'Visual resolution needs unique known check and reason')
        seen.add(item['id'])
        L.require(action.get('decision') in {'withdrawn','not_relevant'}, 'Visual resolution decision must be withdrawn or not_relevant')
        L.require(item['state'] == 'pending', 'Only pending visual work can be released')
        L.require(not reference_blockers(work, item), 'Visual scope is still used by the selected main or a current judgment/answer')
        if action['decision'] == 'withdrawn':
            active = set(run.get('active_source_version_ids', run['source_version_snapshot']))
            L.require(not active & {s['source_version_id'] for s in item['scopes']}, 'Withdraw visual scope only after its versions exit active adoption')
        append_state(item, run['id'], 'released', action['reason'], decision=action['decision'])
    run.update(visual_checks_version=1, visual_checks=rows)


def legacy_checks(ledger, upto):
    """Derive old unresolved scopes for read-only validation / next update, without editing old runs."""
    rows = []
    order = ledger.get('run_order', [ledger['latest_run_id']])
    for rid in order[:order.index(upto)+1]:
        run = ledger['runs'][rid]
        if run.get('visual_checks_version'):
            rows = copy.deepcopy(run['visual_checks']); continue
        snap = ledger.get('run_snapshots', {}).get(rid)
        current = snap['current'] if snap else ledger['current']
        records = {eid: ledger['revisions'][rev]['after'] for eid, rev in current.items()}
        artifact_ids = set(snap['artifact_ids']) if snap else {a['id'] for a in ledger['artifacts']}
        work = dict(records=records, units=ledger['units'], artifacts=[a for a in ledger['artifacts'] if a['id'] in artifact_ids])
        changes = {c['id']: c for c in run.get('changes', [])}
        for s in run.get('screening', []):
            if s.get('visual_check', {}).get('state') == 'unavailable':
                item = new_check(work, changes[s['change_id']], s['visual_check'], rid)
                rows.append(item)
        for item in rows:
            if item['state'] == 'pending':
                coverage = observations(work, item['scopes'])
                if coverage['complete']: append_state(item, rid, 'viewed', '旧轮已有匹配版本和范围的有效原页观察', coverage['observation_ids'])
    return rows


def current_checks(work):
    return work['run'].get('visual_checks', work.get('_legacy_visual_checks', []))


def validate(work, previous=None):
    run = work['run']
    if not run.get('visual_checks_version'): return
    rows = run.get('visual_checks')
    L.require(run['visual_checks_version'] == 1 and isinstance(rows, list), 'Missing or unknown visual check state version')
    ids = [x['id'] for x in rows]; L.require(len(ids) == len(set(ids)), 'Duplicate visual check identity')
    known = work.get('_known_run_ids', [run['id']]); pos = {r:i for i,r in enumerate(known)}
    for item in rows:
        validate_scopes(work, item['scopes'])
        events = item['history']
        L.require(events and events[0]['state'] == 'pending' and events[0]['run_id'] == item['opened_run_id'], 'Missing visual opening history')
        L.require(item['state'] == events[-1]['state'], 'Visual current state differs from history')
        last = -1
        for e in events:
            L.require(e['state'] in {'pending','viewed','released'} and L.nonempty(e.get('reason')) and e['run_id'] in pos, 'Invalid visual history event')
            L.require(pos[e['run_id']] >= last, 'Visual history chronology mismatch'); last = pos[e['run_id']]
            if e['state'] == 'viewed':
                L.require(bool(e.get('observation_ids')) and observations(work, item['scopes'], read_ids=e['observation_ids'])['complete'],
                          'Visual resolution lacks valid observations for the full scope')
            if e['state'] == 'released': L.require(e.get('decision') in {'withdrawn','not_relevant'}, 'Visual release needs a disposition')
        if item['state'] == 'released':
            L.require(not reference_blockers(work, item), 'Released visual scope is still currently used')
            if events[-1]['decision'] == 'withdrawn':
                L.require(not set(run.get('active_source_version_ids',run['source_version_snapshot'])) & {s['source_version_id'] for s in item['scopes']},
                          'Withdrawn visual scope is still active')
    if previous is not None:
        by_id = {r['id']:r for r in rows}
        for old in previous:
            new = by_id.get(old['id'])
            L.require(new is not None, 'Historical visual check disappeared')
            for field in ('id','change_id','opened_run_id','description','scopes'):
                L.require(new[field] == old[field], 'Historical visual scope changed')
            L.require(new['history'][:len(old['history'])] == old['history'], 'Historical visual event changed')
            L.require(all(e['run_id'] == run['id'] for e in new['history'][len(old['history']):]), 'Visual transition must belong to current run')
