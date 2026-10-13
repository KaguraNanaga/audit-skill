#!/usr/bin/env python3
"""Evidence Reviewer: sourced single and incremental reviews, with recoverable local history."""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import ledger as L
import readers
from prepare import inventory


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_work(project, work):
    L.atomic_json(project / 'staging' / 'working.json', work)


def get_work(project):
    work = load(project / 'staging/working.json')
    path = project / 'ledger/ledger.json'
    if path.exists():
        ledger = load(path); L.thaw(ledger)
        L.require(work.get('update_context') and work['run']['id'] != ledger['latest_run_id'], 'This review is committed; stage a new update before changing it')
        L.require(work['update_context']['base_sha256'] == ledger['integrity_sha256'], 'Staged update has a stale base; recover before continuing')
    L.require(work['run']['state'] == 'staging', 'Preparation failed or work is committed; preserve logs and recover')
    return work


def local_path(project, rel):
    p = project / rel
    L.require(not p.is_symlink() and p.resolve().is_relative_to(project.resolve()), 'Project path escapes project or is a symlink')
    return p


def check_files(project, work, check_outputs=False):
    for row in work['records'].values():
        if row['kind'] == 'SourceVersion' and row.get('local_snapshot'):
            p = local_path(project, row['local_snapshot'])
            L.require(p.is_file() and readers.digest(p) == row['sha256'], 'Source snapshot changed or unavailable: ' + str(p))
        if row['kind'] == 'SourceVersion' and row.get('raw_tool_path'):
            p = local_path(project, row['raw_tool_path'])
            L.require(p.is_file() and readers.digest(p) == row['raw_tool_sha256'], 'Raw web tool response changed or unavailable')
    for artifact in work['artifacts']:
        p = local_path(project, artifact['path'])
        L.require(p.is_file() and readers.digest(p) == artifact['sha256'], 'Registered rendering/image changed or unavailable')
    if check_outputs:
        for row in work['records'].values():
            if row['kind'] == 'OutputRecord':
                p = local_path(project, row['path'])
                L.require(p.is_file() and readers.digest(p) == row['sha256'], 'Output missing or changed; use export to restore from ledger: ' + str(p))


def add_units(project, work, version_id, extracted):
    units = []
    for item in extracted['units']:
        u = dict(item, id=L.uid())
        units.append(u)
        read_id = L.add(work, 'ReadRecord', dict(source_version_id=version_id, unit_id=u['id'], locator=u['locator'],
                                               state=u['state'], method=extracted['reader_version'], render_version=None,
                                               errors=u.get('errors', []), limitations=u['limitations']))
        u['read_id'] = read_id
        if u.get('artifact'):
            p = Path(u.pop('artifact'))
            artifact = dict(id=L.uid(), source_version_id=version_id, locator=u['locator'],
                            path=p.relative_to(project).as_posix(), sha256=readers.digest(p), method='embedded/original image')
            work['artifacts'].append(artifact)
            u['artifact_id'] = artifact['id']
    work['units'][version_id] = units


def begin(args):
    project = args.project.expanduser().resolve()
    request = load(args.request)
    goal = request.get('goal', request.get('user_request'))
    modes = request.get('modes', [request.get('mode', 'query')])
    L.require(L.nonempty(goal) and isinstance(modes, list) and bool(modes) and set(modes) <= L.MODES, 'Specify goal and review modes; use update command for an existing project')
    L.require(not request.get('selected_main_version'), 'New source version IDs are assigned by begin; select the actual version with select-main afterward')
    roots = request.get('source_roots', [request['source_root']] if request.get('source_root') else [])
    roots = [Path(p).expanduser().resolve() for p in roots]
    L.require(bool(roots) or set(modes) == {'rules'}, 'Local sources required except pure rules query')
    for root in roots:
        L.require(root.is_dir() and not project.is_relative_to(root) and not root.is_relative_to(project), 'Project must be outside source roots, and sources must be existing directories')
    L.require(not project.exists(), 'Project path must be new; existing work is never overwritten')
    excluded = [Path(p) for p in request.get('exclusions', [])]
    L.require(all(not p.is_absolute() and '..' not in p.parts for p in excluded), 'Exclusions must be relative paths')
    output = request.get('output', {'format': 'md'})
    L.require(output.get('format', 'md') in {'md', 'chat'}, 'Core export is Markdown; use available document skills after review for other formats')
    project.mkdir(parents=True)
    run_id, project_id = L.uid(), L.uid()
    work = {'schema_version': L.SCHEMA, 'project': {'id': project_id, 'scope_revision': L.uid(),
            'goal': goal, 'modes': modes, 'scope': request.get('scope', {}), 'source_roots': [str(p) for p in roots],
            'requested_source_urls': request.get('source_urls', []), 'requested_main_document': request.get('main_document'),
            'excluded_roots': request.get('exclusions', []), 'selected_main_version': None,
            'main_selection_reason': None, 'output_request': output},
            'run': {'id': run_id, 'previous_run_id': None, 'started_at': L.now(), 'finished_at': None,
                    'state': 'staging', 'validation_version': 2, 'visual_checks_version': 1, 'visual_checks': [], 'source_version_snapshot': [], 'selected_main_version': None,
                    'skill_version': L.VERSION, 'tool_versions': {'reader': readers.VERSION, 'python': sys.version},
                    'model_version': request.get('model_version'), 'errors': [], 'unfinished_steps': ['session_review', 'validation', 'commit', 'export']},
            'records': {}, 'units': {}, 'artifacts': [], 'excluded': [], 'outcome': None}
    work['run']['scope_revision'] = work['project']['scope_revision']
    save_work(project, work)
    try:
        known_paths = set()
        for root in roots:
            files, skipped, errors = inventory(root, excluded)
            work['excluded'] += [dict(x, root=str(root)) for x in skipped]
            work['run']['errors'] += [dict(x, root=str(root), stage='inventory') for x in errors]
            for f in files:
                original = root / f['relative_path']
                if str(original) in known_paths: continue
                known_paths.add(str(original))
                source_id, version_id = L.uid(), L.uid()
                snapshot = project / 'sources' / version_id / original.name
                snapshot.parent.mkdir(parents=True)
                shutil.copyfile(original, snapshot)
                L.require(readers.digest(snapshot) == f['sha256'] == readers.digest(original), 'Source changed during snapshot copy')
                snapshot.chmod(0o444)
                L.add(work, 'Source', dict(actual_name=original.name, known_paths=[str(original)], urls=[], role='unknown',
                                         role_basis='Not yet classified by reviewer', issuer=None, signature_status='unknown',
                                         confirmation_scope=None, origin_group_id=source_id), source_id)
                L.add(work, 'SourceVersion', dict(source_id=source_id, actual_name=original.name, sha256=f['sha256'], availability='local_snapshot',
                          format=original.suffix.lower(), local_snapshot=snapshot.relative_to(project).as_posix(), url=None,
                          discovered_at=L.now(), acquired_at=L.now(), formed_at=None, facts_period=None, received_at=None,
                          derived_from_version_ids=[], processing_method=readers.VERSION, audio_version_id=None), version_id)
                work['run']['source_version_snapshot'].append(version_id)
                extracted = readers.read(snapshot, project / 'cache' / version_id)
                work['records'][version_id]['processing'] = extracted['processing']
                add_units(project, work, version_id, extracted)
                save_work(project, work)
        if request.get('main_document'):
            selected = str(request['main_document'])
            matches = [v for v in work['run']['source_version_snapshot']
                       if selected in work['records'][work['records'][v]['source_id']]['known_paths']
                       or selected == work['records'][work['records'][v]['source_id']]['actual_name']]
            L.require(len(matches) == 1, 'Requested main document is absent or ambiguous; select a precise source scope')
            work['project'].update(selected_main_version=matches[0], main_selection_reason='Explicit request main_document')
            work['run']['selected_main_version'] = matches[0]
        save_work(project, work)
        return {'project': str(project), 'run_id': run_id, 'files': len(known_paths), 'packet': str(project / 'staging/working.json'), 'state': 'staging', 'reviewed': False}
    except Exception as exc:
        work['run']['state'] = 'failed'
        work['run']['errors'].append({'stage': 'begin', 'error': str(exc)})
        save_work(project, work)
        raise


def inspect(args):
    project = args.project.resolve()
    ledger_path = project / 'ledger/ledger.json'
    work = L.thaw(load(ledger_path)) if ledger_path.exists() else load(project / 'staging/working.json')
    if getattr(args, 'run', None):
        import history
        work = history.as_of(load(ledger_path), args.run)
    elif not getattr(args, 'committed', False) and (project / 'staging/working.json').exists():
        staged = load(project / 'staging/working.json')
        if staged.get('update_context') and staged['run']['id'] != work['run']['id']:
            work = get_work(project)
    versions = args.version or work['run']['source_version_snapshot']
    records = work['records']
    rows = []
    for vid in versions:
        L.require(vid in work['units'], 'Unknown version')
        v = records[vid]
        rows.append({'version': v, 'source': records[v['source_id']], 'units': work['units'][vid],
                     'artifacts': [dict(a, absolute_path=str(project / a['path'])) for a in work['artifacts'] if a['source_version_id'] == vid]})
    result = {'project': work['project'], 'run': work['run'], 'sources': rows,
              'search_records': [r for r in records.values() if r['kind'] == 'SearchRecord']}
    if getattr(args, 'records', False):
        result['review_records'] = [r for r in records.values() if r['kind'] not in {'Source', 'SourceVersion', 'ReadRecord', 'OutputRecord'}]
    return result


def search(args):
    project = args.project.resolve()
    with L.lock(project):
        work = get_work(project)
        versions = args.version if args.version is not None else list(dict.fromkeys(work['run'].get('active_source_version_ids', work['run']['source_version_snapshot']) + work['run'].get('changed_version_ids', []) + ([work['project']['selected_main_version']] if work['project'].get('selected_main_version') else [])))
        L.require(set(versions) <= set(work['units']), 'Unknown search version')
        pattern = re.compile(args.pattern, re.IGNORECASE)
        results, unread = [], []
        for vid in versions:
            for u in work['units'][vid]:
                if u['state'] in {'unread', 'failed', 'manual_check'}:
                    unread.append({'source_version_id': vid, 'unit_id': u['id'], 'state': u['state']})
                if pattern.search(u['text']):
                    results.append({'source_version_id': vid, 'unit_id': u['id'], 'locator': u['locator'], 'text': u['text']})
        record_id = L.add(work, 'SearchRecord', dict(purpose=args.purpose, material_snapshot=list(versions),
                          scope=[work['records'][work['records'][v]['source_id']]['actual_name'] for v in versions],
                          keywords=[args.pattern], method='regex over all extracted units of selected snapshots; no OCR',
                          tool='review.py search', queried_at=L.now(), results=results, unread_parts=unread,
                          task_ids=[], claim_ids=[], external=False))
        save_work(project, work)
        return {'search_record_id': record_id, 'matches': len(results), 'results': results, 'unread_parts': unread, 'searched_version_ids': versions, 'scope_selection': 'explicit' if args.version is not None else 'active_changed_and_selected_main'}


def select_main(args):
    project = args.project.resolve()
    with L.lock(project):
        work = get_work(project)
        L.require(args.version in work['run']['source_version_snapshot'], 'Main must be an available source version')
        L.require(L.nonempty(args.reason), 'Main selection requires reason')
        previous = work['project'].get('selected_main_version')
        work['project'].update(selected_main_version=args.version, main_selection_reason=args.reason)
        work['run']['selected_main_version'] = args.version
        if work.get('update_context') and previous != args.version:
            import updates
            updates.add_change(work, 'main_changed', args.reason, old_version_id=previous, new_version_id=args.version)
            updates.mark_candidates(work)
        save_work(project, work)
        return {'selected_main_version': args.version}


def render_source(args):
    project = args.project.resolve()
    with L.lock(project):
        work = get_work(project)
        L.require(args.version in work['units'], 'Unknown version')
        version = work['records'][args.version]
        src = project / version['local_snapshot']
        folder = project / 'cache' / args.version / ('render-' + L.uid())
        folder.mkdir(parents=True)
        artifacts = []
        if version['format'] == '.pdf':
            pages = args.pages or [u['locator']['physical_page'] for u in work['units'][args.version] if u['locator'].get('physical_page')]
            L.require(bool(pages), 'PDF has no readable page index; encrypted/damaged file needs remediation')
            for page in pages:
                u = next((u for u in work['units'][args.version] if u['locator'].get('physical_page') == page), None)
                L.require(u, 'Page outside source')
                prefix = folder / f'page-{page}'
                subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile', '-scale-to', '1600', '-png', str(src), str(prefix)], check=True, capture_output=True, timeout=60)
                artifacts.append((prefix.with_suffix('.png'), u['locator']))
            method = 'Poppler pdftoppm page render'
        elif version['format'] in {'.docx', '.doc'}:
            L.require(args.docx_renderer and Path(args.docx_renderer).is_file(), 'Pass actual available document skill render_docx.py path')
            if version['format'] == '.doc': src = project / 'cache' / args.version / 'converted.docx'
            env = os.environ.copy()
            if args.fontconfig: env['FONTCONFIG_FILE'] = str(Path(args.fontconfig).resolve())
            subprocess.run([sys.executable, args.docx_renderer, str(src), '--output_dir', str(folder)], check=True, capture_output=True, timeout=120, env=env)
            artifacts = [(p, None) for p in sorted(folder.glob('page-*.png'))]
            L.require(bool(artifacts), 'DOCX render returned no pages')
            method = 'Document skill renderer; page binding requires visual anchor matching'
        else:
            raise ValueError('Core render supports PDF/DOCX/DOC; embedded images already registered; use available spreadsheet tool for workbook views')
        for path, locator in artifacts:
            work['artifacts'].append(dict(id=L.uid(), source_version_id=args.version, locator=locator,
                                         path=path.relative_to(project).as_posix(), sha256=readers.digest(path), method=method))
        save_work(project, work)
        return {'artifacts': [dict(a, absolute_path=str(project / a['path'])) for a in work['artifacts'] if a['source_version_id'] == args.version], 'viewed': False}


def import_web(args):
    """Record actual session tool acquisition, including failed search/open attempts."""
    project = args.project.resolve()
    record = load(args.record)
    with L.lock(project):
        work = get_work(project)
        for field in ['purpose', 'query', 'tool', 'queried_at', 'acquisition_state', 'url', 'title', 'text', 'errors', 'unread_parts']:
            L.require(field in record, 'Web record missing ' + field)
        state = record['acquisition_state']
        L.require(state in {'full_body', 'partial_body', 'snippet_only', 'unavailable', 'tool_unavailable'}, 'Invalid acquisition state')
        L.require(L.nonempty(record['tool']) and L.nonempty(record['queried_at']), 'Actual tool and query time required')
        L.require(state in {'unavailable', 'tool_unavailable'} or (L.nonempty(record['text']) and record.get('raw_tool_path')), 'Successful acquisition requires retained raw tool output')
        if state in {'unavailable', 'tool_unavailable'}: L.require(not record['text'], 'Failed acquisition cannot contain pretend body text')
        if state == 'tool_unavailable': L.require(bool(record['errors']), 'Unavailable tool needs reason')
        capture_id = L.uid()
        cache = project / 'cache' / ('web-' + capture_id)
        cache.mkdir(parents=True)
        raw_path = None
        if record.get('raw_tool_path'):
            raw = Path(record['raw_tool_path']).resolve()
            L.require(raw.is_file(), 'Raw tool output not found')
            # Content must occur in the supplied tool response, not merely a session paraphrase.
            if record['text']:
                raw_content = raw.read_text()
                try:
                    decoded = json.loads(raw_content)
                    raw_content += '\n' + json.dumps(decoded, ensure_ascii=False)
                    def strings(obj):
                        if isinstance(obj, str): return [obj]
                        if isinstance(obj, list): return [s for x in obj for s in strings(x)]
                        if isinstance(obj, dict): return [s for x in obj.values() for s in strings(x)]
                        return []
                    raw_content += '\n' + '\n'.join(strings(decoded))
                except ValueError: pass
                L.require(record['text'] in raw_content, 'Imported text is not an exact excerpt of retained tool output')
            raw_path = cache / 'tool-response.txt'
            shutil.copyfile(raw, raw_path)
        source_id, version_id = record.get('source_id') or L.uid(), L.uid()
        existing = source_id in work['records']
        L.require(not record.get('source_id') or (work.get('update_context') and existing and work['records'][source_id]['kind'] == 'Source'), 'Web source binding requires an existing source in a staged update')
        previous_version = None
        if existing:
            import updates
            previous_version = next((v for v in updates.active_versions(work) if work['records'][v]['source_id'] == source_id), None)
        snapshot = None
        if record['text']:
            snapshot = project / 'sources' / version_id / 'web-tool-excerpt.txt'
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(record['text'])
            snapshot.chmod(0o444)
        if not existing:
            L.add(work, 'Source', dict(actual_name=record['title'], known_paths=[], urls=[record['url']] if record['url'] else [], role='unknown',
                                     role_basis='Web source role requires reviewer classification', issuer=None, signature_status='unknown',
                                     confirmation_scope=None, origin_group_id=source_id), source_id)
        L.add(work, 'SourceVersion', dict(source_id=source_id, actual_name=record['title'], sha256=readers.digest(snapshot) if snapshot else None,
                      availability='tool_excerpt_saved' if snapshot else 'unavailable', format='web',
                      local_snapshot=snapshot.relative_to(project).as_posix() if snapshot else None,
                      url=record['url'], acquisition_state=state, snapshot_kind='tool_response_excerpt' if snapshot else None,
                      discovered_at=record['queried_at'], acquired_at=record.get('acquired_at', record['queried_at']),
                      formed_at=None, facts_period=None, received_at=L.now(), derived_from_version_ids=[], processing_method=record['tool'],
                      raw_tool_path=raw_path.relative_to(project).as_posix() if raw_path else None,
                      raw_tool_sha256=readers.digest(raw_path) if raw_path else None), version_id)
        work['run']['source_version_snapshot'].append(version_id)
        extracted = {'reader_version': record['tool'], 'units': [readers.unit(
            {'unit': 'web', 'url': record['url'], 'paragraph_anchor': record.get('locator', 'tool excerpt')}, record['text'],
            'extracted' if record['text'] else 'failed', limitations=record['unread_parts'] + ['Stored tool excerpt is not an original HTML byte snapshot'], errors=record['errors'])]}
        add_units(project, work, version_id, extracted)
        search_id = L.add(work, 'SearchRecord', dict(purpose=record['purpose'], material_snapshot=list(work['run']['source_version_snapshot']),
                             scope=record.get('scope', record['url']), keywords=[record['query']], method='actual session search/open tool capture',
                             tool=record['tool'], queried_at=record['queried_at'], results=[{'url': record['url'], 'source_version_id': version_id}],
                             unread_parts=record['unread_parts'], external=True, body_opened=state in {'full_body', 'partial_body'},
                             acquisition_state=state, institution=record.get('institution'), candidate_urls=record.get('candidate_urls', []),
                             errors=record['errors'], task_ids=[], claim_ids=[]))
        if work.get('update_context'):
            import updates
            updates.register_external(work, source_id, version_id, previous_version, state)
        save_work(project, work)
        return {'source_version_id': version_id, 'search_record_id': search_id, 'acquisition_state': state}


def assess(args, commit=False):
    project = args.project.resolve()
    assessment = load(args.assessment)
    with L.lock(project):
        ledger_path = project / 'ledger/ledger.json'
        if ledger_path.exists():
            ledger = load(ledger_path)
            staged_path = project / 'staging/working.json'
            staged = load(staged_path) if staged_path.exists() else None
            if staged and staged.get('update_context') and staged['run']['id'] != ledger['latest_run_id']:
                work = L.materialize(get_work(project), assessment)
                check_files(project, work)
                validation = L.validate_records(work)
                if not commit:
                    return dict(validation, state='validated_candidate', persisted=False,
                                pending_ids=work['run']['update_summary']['pending_ids'],
                                calculations=[{'id': r['id'], 'purpose': r['purpose'], 'result': r['result']} for r in work['records'].values() if r['kind'] == 'Calculation'])
                import history
                return history.finalize(project, work, sys.modules[__name__])
            work = L.thaw(ledger)
            L.require(work['assessment_sha256'] == L.checksum(assessment), 'Committed assessment differs; stage a new update instead of overwriting it')
            if ledger.get('schema_version') == 'evidence-ledger-2.0': write_exports(project, ledger)
            check_files(project, work, check_outputs=True)
            L.validate_records(work)
            return {'state': 'completed', 'idempotent_replay': True, 'run_id': work['run']['id']}
        work = get_work(project)
        L.require(work['run']['state'] == 'staging', 'Begin failed; preserve logs and start a new project after remedy')
        work = L.materialize(work, assessment)
        check_files(project, work)
        validation = L.validate_records(work)
        if not commit:
            return dict(validation, state='validated_candidate', persisted=False,
                        calculations=[{'purpose': r['purpose'], 'result': r['result']} for r in work['records'].values() if r['kind'] == 'Calculation'])
        work['run'].update(state='completed', finished_at=L.now(), unfinished_steps=[])
        exports = L.render(work, project)
        for name, content in exports.items():
            path = f"outputs/{work['run']['id']}/{name}"
            L.add(work, 'OutputRecord', dict(run_id=work['run']['id'], output_kind=name.split('.')[0], path=path,
                       renderer_version=6,
                       sha256=__import__('hashlib').sha256(content.encode()).hexdigest(), source_role='workpaper_or_draft',
                       actual_confirmation_status='unconfirmed', evidence_ids=[e['id'] for e in work['records'].values() if e['kind'] == 'Evidence']))
        L.validate_records(work)
        ledger = L.freeze(work)
        ledger['integrity_sha256'] = L.checksum(ledger)
        L.atomic_json(project / 'staging' / 'validated-candidate.json', ledger)
        L.atomic_json(project / 'staging/transaction.json', dict(state='prepared', run_id=work['run']['id'],
                      candidate_path='staging/validated-candidate.json', candidate_sha256=ledger['integrity_sha256'], base_sha256=None))
        L.atomic_json(ledger_path, ledger)
        write_exports(project, ledger)
        receipt = load(project / 'staging/transaction.json'); receipt['state'] = 'completed'
        L.atomic_json(project / 'staging/transaction.json', receipt)
        return {'state': 'completed', 'run_id': work['run']['id'], 'ledger': str(ledger_path),
                'review': str(project / 'outputs' / work['run']['id'] / 'review.md'), **validation}


def write_exports(project, ledger):
    if ledger.get('schema_version') == 'evidence-ledger-2.0':
        import history
        return history.write_exports(project, ledger, sys.modules[__name__])
    work = L.thaw(ledger)
    check_files(project, work)
    exports = L.render(work, project)
    for name, content in exports.items():
        rel = f"outputs/{work['run']['id']}/{name}"
        record = next(r for r in work['records'].values() if r['kind'] == 'OutputRecord' and r['path'] == rel)
        L.require(__import__('hashlib').sha256(content.encode()).hexdigest() == record['sha256'], 'Renderer differs from committed output fingerprint')
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp-' + L.uid())
        with tmp.open('xb') as f:
            f.write(content.encode())
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    # Update export pointer only after all files match the authoritative ledger.
    check_files(project, work, check_outputs=True)
    L.atomic_json(project / 'outputs/current.json', {'run_id': work['run']['id'], 'ledger_sha256': ledger['integrity_sha256'],
                  'files': [r['path'] for r in work['records'].values() if r['kind'] == 'OutputRecord']})


def validate(args, export=False):
    project = args.project.resolve()
    with L.lock(project):
        ledger = load(project / 'ledger/ledger.json')
        work = L.thaw(ledger)
        result = L.validate_records(work)
        check_files(project, work)
        if export: write_exports(project, ledger)
        check_files(project, work, check_outputs=True)
        pointer = load(project / 'outputs/current.json')
        L.require(pointer['run_id'] == work['run']['id'] and pointer['ledger_sha256'] == ledger['integrity_sha256'], 'Output pointer does not match ledger')
        expected = [r['path'] for r in work['records'].values() if r['kind'] == 'OutputRecord' and r['run_id'] == work['run']['id']]
        L.require(pointer['files'] == expected, 'Output pointer file list does not match current run')
        return dict(result, state='completed', run_id=work['run']['id'], outputs='verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['begin', 'update', 'annotate-sources', 'inspect', 'search', 'select-main', 'render', 'import-web', 'check-assessment', 'finalize', 'validate', 'export', 'recover']:
        p = sub.add_parser(name)
        p.add_argument('--project', type=Path, required=True)
        if name == 'annotate-sources': p.add_argument('--annotations', type=Path, required=True)
        if name in {'begin', 'update'}: p.add_argument('--request', type=Path, required=True)
        if name in {'inspect', 'search'}: p.add_argument('--version', action='append')
        if name == 'inspect':
            p.add_argument('--run'); p.add_argument('--committed', action='store_true'); p.add_argument('--records', action='store_true')
        if name == 'recover':
            p.add_argument('--abort', action='store_true'); p.add_argument('--reason')
        if name == 'search':
            p.add_argument('--pattern', required=True)
            p.add_argument('--purpose', required=True)
        if name == 'select-main':
            p.add_argument('--version', required=True)
            p.add_argument('--reason', required=True)
        if name == 'render':
            p.add_argument('--version', required=True)
            p.add_argument('--pages', type=int, nargs='+')
            p.add_argument('--docx-renderer')
            p.add_argument('--fontconfig')
        if name == 'import-web': p.add_argument('--record', type=Path, required=True)
        if name in {'check-assessment', 'finalize'}: p.add_argument('--assessment', type=Path, required=True)
    args = parser.parse_args()
    try:
        import updates
        import history
        commands = {'begin': begin, 'inspect': inspect, 'search': search, 'select-main': select_main,
                    'render': render_source, 'import-web': import_web,
                    'check-assessment': assess, 'finalize': lambda a: assess(a, True),
                    'validate': validate, 'export': lambda a: validate(a, True),
                    'update': lambda a: updates.start(a, sys.modules[__name__]),
                    'annotate-sources': lambda a: updates.annotate(a, sys.modules[__name__]),
                    'recover': lambda a: history.recover(a, sys.modules[__name__])}
        print(json.dumps(commands[args.command](args), ensure_ascii=False, indent=2, allow_nan=False))
    except Exception as exc:
        print(json.dumps({'state': 'failed', 'error': f'{type(exc).__name__}: {exc}', 'command': args.command}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
