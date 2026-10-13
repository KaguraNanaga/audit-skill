"""Manual incremental review: source changes, conservative impact scope, session reassessment."""
import copy
import difflib
import json
import shutil
from pathlib import Path

import history as H
import ledger as L
import readers
from prepare import inventory


def active_versions(work):
    explicit = work['run'].get('active_source_version_ids')
    if explicit is not None: return list(explicit)
    latest = {}
    for vid in work['run']['source_version_snapshot']:
        latest[work['records'][vid]['source_id']] = vid
    return list(latest.values())


def references(value, known):
    if isinstance(value, dict):
        return set().union(*(references(v, known) for k, v in value.items() if k not in {'id', 'kind'}))
    if isinstance(value, list): return set().union(*(references(v, known) for v in value))
    return {value} if isinstance(value, str) and value in known else set()


def affected_closure(records, seeds):
    affected = set(seeds)
    edges = {i: references(row, records) for i, row in records.items()}
    while True:
        more = {i for i, refs in edges.items() if refs & affected} - affected
        if not more: return affected
        affected |= more


def add_change(work, kind, description, **fields):
    item = dict(id=L.uid(), type=kind, description=description, **fields)
    work['run'].setdefault('changes', []).append(item)
    return item


def mark_candidates(work):
    ctx = work['update_context']
    material = [c for c in work['run']['changes'] if c['type'] not in {'path_moved', 'path_added', 'unchanged'}]
    seeds = {x for c in material for x in [c.get('source_id'), c.get('old_version_id'), c.get('new_version_id'), c.get('entity_id')] if x}
    direct = affected_closure(work['_base_records'], seeds)
    candidates = [i for i, x in work['_base_records'].items() if x['kind'] in H.BUSINESS] if material else []
    ctx.update(candidate_ids=candidates, direct_ids=sorted(set(candidates) & direct))
    for i in candidates:
        work['records'][i]['review_freshness'] = 'needs_review'
    work['run']['impact_candidates'] = dict(direct_ids=ctx['direct_ids'], candidate_ids=candidates,
        policy='Conservative project candidates until actual topic screening narrows scope; includes open gaps and prior no-exception tasks')


def diff_versions(work, old, new):
    def text(vid): return '\n'.join(u['text'] for u in work['units'].get(vid, []) if not u['locator'].get('layer'))
    a, b = text(old), text(new)
    old_images = [x['sha256'] for x in work['artifacts'] if x['source_version_id'] == old and x['method'] == 'embedded/original image']
    new_images = [x['sha256'] for x in work['artifacts'] if x['source_version_id'] == new and x['method'] == 'embedded/original image']
    fmt = work['records'][new]['format']
    visual = fmt == '.pdf' or bool(old_images != new_images) or (a == b and fmt in {'.docx', '.doc', '.pdf', '.png', '.jpg', '.jpeg', '.tiff'})
    return dict(text_changed=a != b, image_bytes_changed=old_images != new_images, visual_check_required=visual,
                text_diff='\n'.join(difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile=old or 'not provided', tofile=new, lineterm=''))[:30000],
                diff_limit='First 30000 characters only; read full source units/pages for the actual review')


def start(args, api):
    project = args.project.resolve()
    request = api.load(args.request)
    allowed = {'event_id', 'reason', 'source_roots', 'source_bindings', 'scope', 'goal', 'modes', 'main_document',
               'withdraw_sources', 'unavailable_sources', 'check_local_availability', 'changed_entity_ids', 'exclusions', 'source_annotations'}
    L.require(isinstance(request, dict) and not set(request) - allowed, 'Unknown update request fields')
    L.require(L.nonempty(request.get('event_id')) and L.nonempty(request.get('reason')), 'Update needs a stable event_id and reason')
    roots = [Path(p).expanduser().resolve() for p in request.get('source_roots', [])]
    excluded = [Path(p) for p in request.get('exclusions', [])]
    L.require(all(not p.is_absolute() and '..' not in p.parts for p in excluded), 'Exclusions must be relative paths')
    files, skipped, scan_errors = [], [], []
    for root in roots:
        L.require(root.is_dir() and not root.is_relative_to(project) and not project.is_relative_to(root), 'Update sources must be existing directories outside project')
        found, omit, errors = inventory(root, excluded)
        files.extend(dict(f, path=str(root / f['relative_path'])) for f in found)
        skipped.extend(omit); scan_errors.extend(dict(e, root=str(root)) for e in errors)
    files = list({f['path']: f for f in files}.values())
    inputs = dict(request=request, files=[{'path': f['path'], 'sha256': f['sha256']} for f in files], inventory_errors=scan_errors)
    fingerprint = L.checksum(inputs)
    with L.lock(project):
        base = api.load(project / 'ledger/ledger.json'); original = L.thaw(base)
        api.check_files(project, original, check_outputs=True)
        for run in base['runs'].values():
            if run.get('event_id') == request['event_id']:
                L.require(run['input_fingerprint'] == fingerprint, 'Same event_id has different inputs; use a new event for a real change')
                return dict(state='completed', idempotent_replay=True, run_id=run['id'], latest_run_id=base['latest_run_id'])
        wp = project / 'staging/working.json'
        if wp.exists():
            staged = api.load(wp)
            if staged['run']['id'] != base['latest_run_id'] and staged['run']['state'] != 'completed':
                L.require(staged.get('update_context', {}).get('input_fingerprint') == fingerprint, 'A different update is pending; finish it or recover --abort with reason')
                L.require(staged['run']['state'] == 'staging', 'Update preparation failed; preserve and abort before retry')
                return dict(state='staging', resumed=True, run_id=staged['run']['id'], changes=staged['run']['changes'])
        work = copy.deepcopy(original)
        work['_base_records'] = copy.deepcopy(original['records'])
        work.pop('_history', None)
        work['update_context'] = dict(base_sha256=base['integrity_sha256'], base_run_id=base['latest_run_id'],
                                      input_fingerprint=fingerprint, request=request)
        work['_known_run_ids'] = list(base.get('run_order', [base['latest_run_id']]))
        from visual_checks import current_checks
        visual_checks = copy.deepcopy(current_checks(original))
        run_id = L.uid(); work['_known_run_ids'].append(run_id)
        work['run'] = dict(id=run_id, previous_run_id=base['latest_run_id'], event_id=request['event_id'],
                           input_fingerprint=fingerprint, reason=request['reason'], started_at=L.now(), finished_at=None,
                           state='staging', validation_version=2, visual_checks_version=1, visual_checks=visual_checks, evidence_link_retirements=copy.deepcopy(original['run'].get('evidence_link_retirements', [])),
                           intake_issues=copy.deepcopy(original['run'].get('intake_issues', original['run'].get('errors', []))), source_version_snapshot=list(original['units']), active_source_version_ids=active_versions(original),
                           selected_main_version=original['project'].get('selected_main_version'), scope_revision=original['project']['scope_revision'],
                           skill_version=L.VERSION, tool_versions=copy.deepcopy(original['run']['tool_versions']), model_version=None,
                           errors=scan_errors, unfinished_steps=['topic_screening', 'impact_review', 'validation', 'commit', 'export'],
                           changes=[], changed_version_ids=[])
        work['run']['intake_issues'].extend(copy.deepcopy(scan_errors))
        work['outcome'] = None; work['excluded'] = skipped
        work.pop('assessment_sha256', None)
        api.save_work(project, work)
        try:
            bindings = {str(Path(x['path']).expanduser().resolve()): x for x in request.get('source_bindings', [])}
            L.require(len(bindings) == len(request.get('source_bindings', [])), 'Duplicate source binding path')
            L.require(set(bindings) <= {f['path'] for f in files}, 'Source binding path is outside supplied files')
            inherited_active = active_versions(work)
            current = {work['records'][v]['source_id']: v for v in inherited_active}
            inherited_current = dict(current)
            for f in files:
                path = Path(f['path']); binding = bindings.get(str(path), {})
                sid = binding.get('source_id')
                output_parent = binding.get('reviewed_output_id')
                if output_parent:
                    L.require(not sid and work['records'].get(output_parent, {}).get('kind') == 'OutputRecord', 'Returned record needs an actual prior OutputRecord, not a guessed source identity')
                    L.require(binding.get('relation') == 'returned_record' and L.nonempty(binding.get('reason')), 'Returned record binding needs reason')
                if sid:
                    L.require(sid in work['records'] and work['records'][sid]['kind'] == 'Source', 'Unknown bound source')
                    L.require(binding.get('relation') in {'replacement', 'correction', 'supplement', 'migration', 'reparse'}, 'Explicit binding needs relation')
                    L.require(L.nonempty(binding.get('reason')), 'Explicit binding needs reason')
                elif not output_parent:
                    matches = [s['id'] for s in work['records'].values() if s['kind'] == 'Source' and str(path) in s.get('known_paths', [])]
                    if not matches:
                        matches = list({work['records'][v]['source_id'] for v in current.values() if work['records'][v].get('sha256') == f['sha256']})
                    if len(matches) == 1: sid = matches[0]
                old = current.get(sid) if sid else None
                same = old and work['records'][old].get('sha256') == f['sha256']
                if same and binding.get('relation') != 'reparse':
                    src = work['records'][sid]
                    if str(path) not in src['known_paths']:
                        available_old = any(Path(p).is_file() for p in src.get('current_paths', src['known_paths']))
                        src['known_paths'].append(str(path)); src['current_paths'] = [str(path)]
                        add_change(work, 'path_added' if available_old else 'path_moved', str(path) + '与原快照同字节', source_id=sid, old_version_id=old, new_version_id=old, byte_changed=False)
                    continue
                if not sid:
                    sid = L.uid()
                    L.add(work, 'Source', dict(actual_name=path.name, known_paths=[str(path)], current_paths=[str(path)], urls=[], role='unknown',
                        role_basis='New source; classify after reading', issuer=None, signature_status='unknown', confirmation_scope=None, origin_group_id=sid), sid)
                else:
                    src = work['records'][sid]
                    if str(path) not in src['known_paths']: src['known_paths'].append(str(path))
                    src.update(current_paths=[str(path)], actual_name=path.name)
                vid = L.uid(); target = project / 'sources' / vid / path.name; target.parent.mkdir(parents=True)
                shutil.copyfile(path, target)
                L.require(readers.digest(target) == f['sha256'] == readers.digest(path), 'Source changed during update copy')
                target.chmod(0o444)
                derived = [old] if old and binding.get('relation') in {'correction', 'reparse', 'supplement'} else []
                L.add(work, 'SourceVersion', dict(source_id=sid, actual_name=path.name, sha256=f['sha256'], availability='local_snapshot', format=path.suffix.lower(),
                    local_snapshot=target.relative_to(project).as_posix(), url=None, discovered_at=L.now(), acquired_at=L.now(), formed_at=None,
                    facts_period=None, received_at=None, derived_from_version_ids=derived, processing_method=readers.VERSION, audio_version_id=None,
                    previous_version_id=old, version_relation=binding.get('relation', 'replacement' if old else 'new'),
                    based_on_output_id=output_parent,
                    identity_basis=binding.get('reason', 'Same known path' if old else 'New source; filename alone was not used for identity')), vid)
                extracted = readers.read(target, project / 'cache' / vid)
                work['records'][vid]['processing'] = extracted['processing']
                api.add_units(project, work, vid, extracted)
                work['run']['source_version_snapshot'].append(vid); work['run']['changed_version_ids'].append(vid)
                current[sid] = vid; work['records'][sid]['active_version_id'] = vid
                add_change(work, 'source_reparsed' if same else 'source_replaced' if old else 'source_added', path.name,
                    source_id=sid, old_version_id=old, new_version_id=vid, based_on_output_id=output_parent, byte_changed=not same, **diff_versions(work, old, vid))
                api.save_work(project, work)
            for event in request.get('withdraw_sources', []):
                sid = event['source_id']; L.require(sid in current and L.nonempty(event.get('reason')), 'Withdrawal needs known source and reason')
                old = current.pop(sid); work['records'][sid].update(active_version_id=None, access_status='withdrawn_by_request')
                add_change(work, 'source_withdrawn', event['reason'], source_id=sid, old_version_id=old)
            for event in request.get('unavailable_sources', []):
                sid = event['source_id']; L.require(sid in current and L.nonempty(event.get('reason')), 'Unavailable source needs known source and reason')
                work['records'][sid]['access_status'] = 'reported_unavailable'
                add_change(work, 'source_unavailable', event['reason'], source_id=sid, old_version_id=current[sid], basis='Explicit user/request report; not a network probe')
            if request.get('check_local_availability'):
                for sid, vid in current.items():
                    src = work['records'][sid]; paths = src.get('current_paths', src.get('known_paths', []))
                    if not paths: continue
                    state = 'available' if any(Path(p).is_file() for p in paths) else 'unavailable'
                    previous = src.get('access_status', 'available')
                    if state != previous:
                        src['access_status'] = state
                        add_change(work, 'source_access_changed', f"{src['actual_name']}原路径当前{state}；历史快照保留", source_id=sid, old_version_id=vid, inspected_paths=paths)
            # Multiple web versions can remain usable after an incomplete acquisition.
            work['run']['active_source_version_ids'] = [v for sid, vid in current.items()
                for v in ([x for x in inherited_active if work['records'][x]['source_id'] == sid]
                          if inherited_current.get(sid) == vid else [vid])]
            if 'scope' in request and request['scope'] != work['project']['scope']:
                work['project'].update(scope=request['scope'], scope_revision=L.uid())
                work['run']['scope_revision'] = work['project']['scope_revision']
                add_change(work, 'scope_changed', '用户调整审查范围', before=original['project']['scope'], after=request['scope'])
            for field in ('goal', 'modes'):
                if field in request and request[field] != work['project'][field]:
                    if field == 'modes': L.require(request[field] and set(request[field]) <= L.MODES, 'Unknown review mode')
                    else: L.require(L.nonempty(request[field]), 'Goal cannot be blank')
                    work['project'][field] = request[field]; add_change(work, 'goal_changed', '用户调整' + field)
            main = work['project'].get('selected_main_version')
            if 'main_document' in request:
                wanted = request['main_document']
                matches = [v for v in current.values() if wanted and (wanted == work['records'][work['records'][v]['source_id']]['actual_name'] or wanted in work['records'][work['records'][v]['source_id']]['known_paths'])]
                L.require(not wanted or len(matches) == 1, 'Requested new main is absent or ambiguous')
                main = matches[0] if wanted else None
            elif main and main not in work['run']['active_source_version_ids']:
                main = current.get(work['records'][main]['source_id'])
            if main != work['project'].get('selected_main_version'):
                add_change(work, 'main_changed', '当前主稿版本切换', old_version_id=work['project'].get('selected_main_version'), new_version_id=main)
                work['project'].update(selected_main_version=main, main_selection_reason=request.get('reason'))
                work['run']['selected_main_version'] = main
            for eid in request.get('changed_entity_ids', []):
                L.require(eid in work['_base_records'], 'Unknown changed entity')
                add_change(work, 'judgment_input_changed', request['reason'], entity_id=eid)
            stage_annotations(work, request.get('source_annotations', []), request['reason'])
            acquired_paths = {f['path'] for f in files}
            work['run']['intake_issues'] = [e for e in work['run']['intake_issues'] if str(Path(e.get('root', '')) / e.get('path', '')) not in acquired_paths]
            mark_candidates(work)
            api.save_work(project, work)
            return dict(state='staging', run_id=run_id, changes=work['run']['changes'], impact=work['run']['impact_candidates'], reviewed=False)
        except Exception as exc:
            work['run']['state'] = 'failed'; work['run']['errors'].append(dict(stage='update', error=str(exc)))
            api.save_work(project, work)
            raise


def register_external(work, source_id, version_id, previous_version, state):
    active = active_versions(work)
    previous = [v for v in active if work['records'][v]['source_id'] == source_id]
    full = [v for v in previous if work['records'][v].get('acquisition_state') == 'full_body']
    if state == 'full_body':
        active = [v for v in active if v not in previous] + [version_id]
    elif state not in {'unavailable', 'tool_unavailable'}:
        # Keep the older body searchable; partial/snippet acquisition does not establish supersession.
        active = list(dict.fromkeys(active + [version_id]))
    work['run']['active_source_version_ids'] = active
    source = work['records'][source_id]
    source.update(access_status='available' if state == 'full_body' else 'incomplete' if state in {'partial_body', 'snippet_only'} else 'unavailable',
                  latest_acquisition_version_id=version_id, latest_acquisition_state=state,
                  retained_full_body_version_ids=full if state != 'full_body' else [version_id],
                  body_currentness='not_determined_by_acquisition')
    work['run']['changed_version_ids'].append(version_id)
    add_change(work, 'web_access_failed' if state in {'unavailable', 'tool_unavailable'} else 'web_acquired',
               work['records'][source_id]['actual_name'], source_id=source_id, old_version_id=previous_version, new_version_id=version_id,
               acquisition_state=state, retained_previous_snapshot=bool(previous_version))
    mark_candidates(work)


def materialize(work, assessment):
    original_assessment = copy.deepcopy(assessment)
    extra = {'screening', 'impact_review', 'visual_resolutions'}
    for annotation in assessment.get('source_annotations', []):
        sid = annotation.get('source_id')
        if sid in work['_base_records'] and any(work['records'][sid].get(k) != v for k, v in annotation.items() if k != 'source_id'):
            raise ValueError('Source annotations changed; stage them with annotate-sources or update.source_annotations before topic/impact review')
    basic = {k: v for k, v in assessment.items() if k not in extra}
    work = copy.deepcopy(work); work['_applying_update'] = True
    work = L.materialize(work, basic)
    from adoptions import retire_links
    retire_links(work, assessment.get('link_retirements', []))
    aliases = work.pop('_assessment_aliases')
    def resolve(value):
        if isinstance(value, dict): return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, list): return [resolve(v) for v in value]
        return aliases.get(value, value) if isinstance(value, str) else value
    screening = resolve(assessment.get('screening', []))
    decisions = resolve(assessment.get('impact_review', []))
    changes = work['run']['changes']; known_changes = {c['id']: c for c in changes}
    L.require(isinstance(screening, list) and {s.get('change_id') for s in screening} == set(known_changes) and len(screening) == len(known_changes), 'Every change needs one actual topic screening, including unlinked new material')
    for s in screening:
        L.require(s.get('scope_decision') in {'targeted', 'topic', 'project'} and L.nonempty(s.get('basis')) and L.nonempty(s.get('new_matters')), 'Screening needs scope, basis and new-matter conclusion')
        L.require(isinstance(s.get('topics'), list) and bool(s['topics']), 'Screening requires actual topics')
        L.require(set(s.get('affected_ids', [])) <= set(work['records']), 'Screening has unknown affected IDs')
        change = known_changes[s['change_id']]
        if change.get('visual_check_required'):
            visual = s.get('visual_check', {})
            L.require(visual.get('state') in {'viewed', 'unavailable'} and L.nonempty(visual.get('basis')), 'Byte/image change needs actual visual check or explicit inability')
            if visual['state'] == 'viewed':
                wanted = {v for v in (change.get('old_version_id'), change.get('new_version_id')) if v}
                viewed = {r['source_version_id'] for r in work['records'].values() if r['kind'] == 'ReadRecord' and r['state'] == 'viewed' and r.get('artifact_id') in visual.get('artifact_ids', [])}
                L.require(wanted <= viewed, 'Changed visual requires registered actual observations of old and new versions')
    candidates = set(work['update_context']['candidate_ids'])
    L.require(isinstance(decisions, list) and {d.get('target_id') for d in decisions} == candidates and len(decisions) == len(candidates), 'Every impact candidate needs review, unaffected or defer decision')
    for decision in decisions:
        eid, action = decision['target_id'], decision.get('decision')
        L.require(action in {'review', 'unaffected', 'defer'} and L.nonempty(decision.get('basis')), 'Impact decision needs substantive basis')
        before = work['_base_records'][eid]; after = work['records'][eid]
        def substantive(row): return {k: v for k, v in row.items() if k not in {'review_freshness', 'last_reviewed_run'}}
        changed = substantive(before) != substantive(after)
        if action in {'unaffected', 'defer'}:
            L.require(not changed, 'Unreviewed entity cannot silently change its substantive judgment')
            work['records'][eid] = copy.deepcopy(before)
            if action == 'defer': work['records'][eid]['review_freshness'] = 'needs_review'
        else:
            L.require(any(decision.get(k) for k in ('evidence_ids', 'source_version_ids', 'calculation_ids', 'search_record_ids')), 'Actual re-review needs source/calculation/search basis')
            for field, kind in [('evidence_ids', 'Evidence'), ('source_version_ids', 'SourceVersion'), ('calculation_ids', 'Calculation'), ('search_record_ids', 'SearchRecord')]:
                for rid in decision.get(field, []): L.require(work['records'].get(rid, {}).get('kind') == kind, 'Bad impact review reference')
            if changed:
                after['review_freshness'] = 'current'
                if after['kind'] == 'Finding': after['last_reviewed_run'] = work['run']['id']
            elif 'review_freshness' in before: after['review_freshness'] = 'current'
            else: after.pop('review_freshness', None)
            if after['kind'] == 'EvidenceGap' and work['run']['changed_version_ids']:
                recent = [work['records'][r] for r in decision.get('search_record_ids', []) if r not in work['_base_records']]
                L.require(any(set(work['run']['changed_version_ids']) <= set(r['material_snapshot']) for r in recent), 'Gap recheck needs an actual search covering new versions')
            if after['kind'] == 'EvidenceGap' and after['state'] != 'open':
                L.require(L.nonempty(after.get('resolution_reason')), 'Closed gap needs resolution_reason')
                if after['state'] == 'satisfied':
                    L.require(bool(after.get('resolution_evidence_ids')) and all(work['records'].get(x, {}).get('kind') == 'Evidence' for x in after['resolution_evidence_ids']), 'Satisfied gap requires actual resolution evidence')
        work.setdefault('_revision_reasons', {}).setdefault(eid, decision['basis'])
    for eid, before in work['_base_records'].items():
        if before['kind'] in H.BUSINESS and eid not in candidates:
            L.require(work['records'][eid] == before, 'Undeclared judgment change; stage explicit changed_entity_ids or relevant new material first')
    substantive_changes = {i for i in candidates if {k: v for k, v in work['_base_records'][i].items() if k not in {'review_freshness', 'last_reviewed_run'}} !=
                           {k: v for k, v in work['records'][i].items() if k not in {'review_freshness', 'last_reviewed_run'}}}
    downstream = affected_closure(work['_base_records'], substantive_changes) - substantive_changes
    choices = {d['target_id']: d['decision'] for d in decisions}
    L.require(all(choices.get(i) != 'unaffected' for i in downstream & candidates), 'Changed calculation/rule/claim propagates to dependents; explicitly re-review or defer them')
    pending = [r['id'] for r in work['records'].values() if r['kind'] in H.BUSINESS and r.get('review_freshness') == 'needs_review']
    work['run'].update(screening=screening, impact_review=decisions,
                       update_summary=dict(pending_ids=pending, reviewed_ids=[d['target_id'] for d in decisions if d['decision'] == 'review'],
                                           unaffected_ids=[d['target_id'] for d in decisions if d['decision'] == 'unaffected']))
    from visual_checks import reconcile
    reconcile(work, screening, assessment.get('visual_resolutions', []))
    if pending: work['outcome']['limitations'].append('本轮仍有' + str(len(pending)) + '个对象待复核；旧判断未按全部新信息验证。')
    work['assessment_sha256'] = L.checksum(original_assessment)
    work.pop('_applying_update', None)
    return work


ANNOTATION_FIELDS = {'source_id', 'role', 'role_basis', 'issuer', 'signature_status', 'confirmation_scope',
                     'origin_group_id', 'formed_at', 'facts_period', 'received_at', 'transcript_kind',
                     'confirmed_speakers', 'audio_version_id'}


def stage_annotations(work, annotations, reason):
    L.require(isinstance(annotations, list), 'source_annotations must be a list')
    seen = set()
    for annotation in annotations:
        L.require(isinstance(annotation, dict) and not set(annotation) - ANNOTATION_FIELDS, 'Unknown source annotation')
        sid = annotation.get('source_id'); source = work['records'].get(sid)
        L.require(source and source['kind'] == 'Source' and sid not in seen, 'Annotation source missing or duplicated')
        seen.add(sid)
        changed = {k: v for k, v in annotation.items() if k != 'source_id' and source.get(k) != v}
        if not changed: continue
        L.require(L.nonempty(reason), 'Source annotation change needs reason')
        before = {k: copy.deepcopy(source.get(k)) for k in changed}
        source.update(copy.deepcopy(changed))
        if sid in work['_base_records']:
            add_change(work, 'source_annotation_changed', reason, source_id=sid, before=before, after=changed)
    mark_candidates(work)


def annotate(args, api):
    project = args.project.resolve()
    request = api.load(args.annotations)
    L.require(isinstance(request, dict) and set(request) <= {'reason', 'source_annotations'} and L.nonempty(request.get('reason')), 'Annotations packet needs reason and source_annotations')
    with L.lock(project):
        work = api.get_work(project)
        L.require(work.get('update_context'), 'Initial source annotations belong in assessment; this command stages update changes')
        stage_annotations(work, request.get('source_annotations', []), request['reason'])
        api.save_work(project, work)
        return dict(state='staging', run_id=work['run']['id'], changes=work['run']['changes'], impact=work['run']['impact_candidates'], reviewed=False)
