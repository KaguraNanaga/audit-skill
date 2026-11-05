"""Typed OCR lineage and structural adoption checks; no interpretation of image facts."""
import math
from . import ledger as L

WARNING = 'OCR 派生，仅供定位，需打开原页确认'
SCHEMA = 'evidence-ledger-3.0'


def is_ocr(unit):
    return unit.get('locator', {}).get('unit') == 'ocr_derived'


def unit_at(work, version, unit_id):
    return next((u for u in work['units'].get(version, []) if u['id'] == unit_id), None)


def validate_block(block):
    L.require(isinstance(block.get('text'), str) and bool(block['text'].strip()), 'OCR block needs text')
    score = block.get('confidence')
    L.require(isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 1, 'Invalid OCR confidence')
    bbox = block.get('bbox')
    L.require(isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(p, list) and len(p) == 2 and all(isinstance(n, (int,float)) and not isinstance(n,bool) and math.isfinite(n) and n >= 0 for n in p) for p in bbox), 'Invalid OCR pixel bbox')
    L.require(max(p[0] for p in bbox) > min(p[0] for p in bbox) and max(p[1] for p in bbox) > min(p[1] for p in bbox), 'Empty OCR bbox')
    L.require(block.get('frame', 1) == 1, 'Multi-frame image requires separately registered page images; no frame is silently adopted')


def parent_viewed(work, unit):
    origin = unit['derived_from']
    return any(r['kind'] == 'ReadRecord' and r.get('state') == 'viewed'
               and r.get('source_version_id') == origin['source_version_id']
               and r.get('unit_id') == origin['unit_id']
               and r.get('artifact_id') == origin['artifact_id']
               and r.get('render_version') == origin['image_sha256']
               and L.nonempty(r.get('observation')) for r in work['records'].values())


def validate(work):
    index={(v,u['id']):u for v,units in work['units'].items() for u in units}
    def lookup(w,v,u): return index.get((v,u))
    artifacts = {a['id']: a for a in work['artifacts']}
    attempts = {r['id']: r for r in work['records'].values() if r['kind'] == 'OCRAttempt'}
    for attempt in attempts.values():
        L.require(work['run'].get('derived_units_version') == 1, 'OCR records require a versioned derived-unit schema')
        L.require(attempt.get('state') in {'extracted', 'failed'}, 'Invalid OCR attempt state')
        L.require(attempt.get('source_version_id') in work['units'], 'OCR source version missing')
        L.require(lookup(work, attempt['source_version_id'], attempt.get('unit_id')) is not None, 'OCR parent unit missing')
        L.require(L.nonempty(attempt.get('engine')) and isinstance(attempt.get('parameters'), dict), 'OCR engine/parameters missing')
        if attempt['state'] == 'failed':
            L.require(bool(attempt.get('errors')) and not attempt.get('unit_ids'), 'Failed OCR cannot claim extracted units')
        else:
            L.require(L.nonempty(attempt.get('version')) and attempt.get('raw_path') and attempt.get('raw_sha256'), 'OCR raw result/version missing')
            L.require(isinstance(attempt.get('unit_ids'), list), 'OCR output unit list missing')
    seen = {}
    for vid, units in work['units'].items():
        for unit in units:
            if not is_ocr(unit):
                continue
            L.require(work['run'].get('derived_units_version') == 1, 'OCR unit requires versioned schema')
            origin = unit.get('derived_from', {})
            parent = lookup(work, vid, origin.get('unit_id'))
            artifact = artifacts.get(origin.get('artifact_id'))
            L.require(origin.get('source_version_id') == vid and parent and not is_ocr(parent), 'OCR must derive from an original unit in the same source version')
            L.require(artifact and artifact['source_version_id'] == vid and artifact['sha256'] == origin.get('image_sha256') and artifact.get('locator') == parent['locator'], 'OCR page image/version/locator mismatch')
            L.require(origin.get('physical_page') == parent['locator'].get('physical_page'), 'OCR physical page mismatch')
            attempt = attempts.get(unit.get('attempt_id'))
            L.require(attempt and attempt['state'] == 'extracted' and attempt['source_version_id'] == vid and attempt['unit_id'] == parent['id'] and attempt.get('artifact_id') == artifact['id'], 'OCR attempt lineage mismatch')
            L.require(attempt.get('image_sha256') == artifact['sha256'] and unit.get('state') == 'extracted', 'OCR attempt image hash/state mismatch')
            L.require(unit['id'] in attempt['unit_ids'] and WARNING in unit.get('limitations', []), 'OCR unit not registered with its attempt/warning')
            L.require(unit['locator'].get('parent_unit_id') == parent['id'] and unit['locator'].get('physical_page') == origin.get('physical_page') and unit['locator'].get('attempt_id') == attempt['id'], 'OCR locator/provenance mismatch')
            validate_block(unit)
            seen.setdefault(attempt['id'], []).append(unit['id'])
    for aid, attempt in attempts.items():
        L.require(attempt.get('unit_ids', []) == seen.get(aid, []), 'OCR attempt/unit list mismatch')
    for record in work['records'].values():
        unit = lookup(work, record.get('source_version_id'), record.get('unit_id'))
        if unit and is_ocr(unit):
            if record['kind'] == 'ReadRecord':
                L.require(record.get('state') != 'viewed', 'OCR cannot be marked viewed; observe the original page')
            if record['kind'] == 'Evidence':
                L.require(record.get('verification_state') != 'original_viewed', 'OCR is a derived locator, not original-viewed evidence')
                L.require(parent_viewed(work, unit), 'OCR-only evidence cannot be submitted: add an observation of the matching original page image/version, then cite the original page for visual facts')
        if record['kind'] == 'Claim':
            loc = record.get('source_locator') or {}
            unit = lookup(work, loc.get('source_version_id'), loc.get('unit_id'))
            if unit and is_ocr(unit):
                L.require(parent_viewed(work, unit), 'OCR-only claim requires a matching original-page observation')
        if record['kind'] == 'Calculation':
            for inp in record.get('inputs', []):
                unit = lookup(work, inp.get('source_version_id'), inp.get('unit_id'))
                L.require(not unit or not is_ocr(unit), 'OCR cannot supply factual Calculation inputs; use independently verified original-source values')
