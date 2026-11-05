"""Append optional OCR locator units to staged work, preserving original units and states."""
import copy
from pathlib import Path
from . import ledger as L
from . import readers
from . import ocr_backends as backend
from .derived import WARNING, is_ocr, validate_block


def run(args, api):
    project = args.project.resolve()
    L.require(0 < args.timeout <= 3600, 'OCR timeout must be 1..3600 seconds')
    with L.lock(project):
        work = api.get_work(project)
        L.require(args.version in work['units'], 'Unknown OCR source version')
        api.check_files(project, work)
        units = [u for u in work['units'][args.version] if not is_ocr(u) and u['locator'].get('unit') in {'page','image'}]
        if args.pages:
            L.require(all(p > 0 for p in args.pages) and len(set(args.pages)) == len(args.pages), 'Use unique positive physical page numbers')
            present = {u['locator'].get('physical_page', 1) for u in units}
            L.require(set(args.pages) <= present, 'OCR page outside registered source units')
            units = [u for u in units if u['locator'].get('physical_page', 1) in args.pages]
        L.require(bool(units), 'OCR needs a registered page or image unit; document XML anchors are not physical pages')
        work['run']['derived_units_version'] = 1
        results = []
        for parent in units:
            before = copy.deepcopy(work)
            aid = L.uid()
            record = dict(source_version_id=args.version, unit_id=parent['id'], physical_page=parent['locator'].get('physical_page'),
                          engine=args.engine, version=None, parameters={'timeout_seconds': args.timeout},
                          state='failed', errors=[], unit_ids=[], created_at=L.now(), created_run_id=work['run']['id'])
            try:
                artifact = next((a for a in reversed(work['artifacts']) if a['source_version_id'] == args.version and a.get('locator') == parent['locator']), None)
                L.require(artifact is not None, 'No registered page image: run render first; OCR never fabricates page images')
                image = api.local_path(project, artifact['path'])
                L.require(readers.digest(image) == artifact['sha256'], 'Page image fingerprint changed')
                record.update(artifact_id=artifact['id'], image_sha256=artifact['sha256'])
                metadata = backend.describe(args.engine)
                record.update(copy.deepcopy(metadata))
                record['parameters'] = dict(metadata['parameters'], timeout_seconds=args.timeout)
                folder = project / 'cache' / args.version / ('ocr-' + aid)
                folder.mkdir(parents=True)
                blocks = backend.recognize(image, folder/'worker.json', metadata, args.timeout)
                L.require(isinstance(blocks, list), 'OCR backend must return a block list')
                for block in blocks: validate_block(block)
                raw = folder/'result.json'
                L.atomic_json(raw, blocks)
                record.update(state='extracted', raw_path=raw.relative_to(project).as_posix(), raw_sha256=readers.digest(raw))
                for i, block in enumerate(blocks, 1):
                    uid = L.uid()
                    locator = dict(unit='ocr_derived', parent_unit_id=parent['id'], physical_page=parent['locator'].get('physical_page'), block=i, attempt_id=aid)
                    unit = readers.unit(locator, block['text'], limitations=[WARNING], id=uid, attempt_id=aid,
                        confidence=block['confidence'], bbox=block['bbox'], frame=1, coordinate_system='pixels; origin top-left of registered image',
                        derived_from=dict(source_version_id=args.version, unit_id=parent['id'], physical_page=parent['locator'].get('physical_page'), artifact_id=artifact['id'], image_sha256=artifact['sha256']))
                    unit['read_id'] = L.add(work, 'ReadRecord', dict(source_version_id=args.version, unit_id=uid, locator=locator,
                        state='extracted', method='OCR locator: ' + args.engine, render_version=None, errors=[], limitations=[WARNING]))
                    work['units'][args.version].append(unit); record['unit_ids'].append(uid)
            except Exception as exc:
                work = before
                record['unit_ids'] = []
                record.update(state='failed', errors=[f'{type(exc).__name__}: {exc}'], failure_kind='tool_unavailable' if isinstance(exc, (FileNotFoundError, ModuleNotFoundError)) else 'failed')
            L.add(work, 'OCRAttempt', record, aid)
            api.save_work(project, work)
            results.append(dict(attempt_id=aid, physical_page=record['physical_page'], state=record['state'], units=len(record['unit_ids']), errors=record['errors']))
        return dict(state='partial' if any(r['state']=='failed' for r in results) else 'completed', attempts=results,
                    warning=WARNING, original_reading_states_changed=False, reviewed=False)
