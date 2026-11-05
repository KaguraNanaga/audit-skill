"""Bounded, read-only views. Delivery of a fragment never records a review/view."""
import hashlib
import json
from collections import Counter

from . import ledger as L

NOTICE = '返回内容仅供定位/读取；未返回不表示不相关，返回成功不代表已核查。'


def load_work(args, api):
    project = args.project.resolve()
    ledger_path = project / 'ledger/ledger.json'
    ledger = api.load(ledger_path) if ledger_path.exists() else None
    work = L.thaw(ledger) if ledger else api.load(project / 'staging/working.json')
    if getattr(args, 'run', None):
        L.require(ledger is not None, '--run requires a committed ledger')
        from . import history
        L.require(args.run in ledger['runs'], 'Unknown run')
        return history.as_of(ledger, args.run)
    if not getattr(args, 'committed', False) and (project / 'staging/working.json').exists():
        staged = api.load(project / 'staging/working.json')
        if staged.get('update_context') and staged['run']['id'] != work['run']['id']:
            return api.get_work(project)
    return work


def bounds(args, total):
    offset = getattr(args, 'offset', 0)
    limit = getattr(args, 'limit', None)
    limit = 20 if limit is None else limit
    L.require(isinstance(offset, int) and 0 <= offset <= total, 'offset must be within 0..total')
    L.require(isinstance(limit, int) and 1 <= limit <= 100, 'limit must be 1..100')
    return offset, limit


def preview(value, chars=1000):
    """Explicitly labelled metadata preview; full value remains in the packet/ledger."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return dict(text=text[:chars], total_chars=len(text), truncated=len(text) > chars)


def token(work, versions):
    digest = hashlib.sha256(work['run']['id'].encode('utf-8'))
    for vid in versions:
        digest.update(L.encoded(work['records'][vid]))
        for u in work['units'][vid]:
            digest.update(u['id'].encode('utf-8'))
    return digest.hexdigest()


def check_token(args, value):
    L.require(not getattr(args, 'snapshot', None) or args.snapshot == value,
              'Reading scope changed; obtain a fresh summary/cursor before continuing')


def catalog(args, work):
    versions = args.version or work['run']['source_version_snapshot']
    L.require(set(versions) <= set(work['units']), 'Unknown version')
    offset, limit = bounds(args, len(versions))
    snapshot = token(work, versions)
    check_token(args, snapshot)
    active = set(work['run'].get('active_source_version_ids', work['run']['source_version_snapshot']))
    rows = []
    for vid in versions[offset:offset + limit]:
        v = work['records'][vid]
        src = work['records'][v['source_id']]
        rows.append(dict(source_version_id=vid, source_id=v['source_id'],
                         actual_name=preview(v.get('actual_name') or src['actual_name'], 512),
                         format=v['format'], sha256=v.get('sha256'), active=vid in active,
                         units=len(work['units'][vid]),
                         extraction_states=dict(Counter(u['state'] for u in work['units'][vid])),
                         role=src['role'], acquisition_state=v.get('acquisition_state'),
                         local_snapshot=preview(v.get('local_snapshot'), 1000)))
    end = offset + len(rows)
    return dict(run_id=work['run']['id'], state=work['run']['state'], snapshot=snapshot,
                total_sources=len(versions), offset=offset, returned=len(rows), remaining=len(versions)-end,
                next_offset=end if end < len(versions) else None, sources=rows,
                intake_error_count=len(work['run'].get('errors', [])),
                notice=NOTICE, memory_limit='Bounds output only; the JSON ledger is still loaded in memory')


def read(args, api):
    work = load_work(args, api)
    vid = args.version
    L.require(vid in work['units'], 'Unknown version')
    units = work['units'][vid]
    if args.unit:
        units = [u for u in units if u['id'] == args.unit]
        L.require(bool(units), 'Unknown unit in selected version')
    offset, limit = bounds(args, len(units))
    L.require(256 <= args.chars <= 32000, 'chars must be 256..32000 (total text characters per response)')
    L.require(args.text_offset >= 0, 'text-offset must be nonnegative')
    L.require(offset < len(units) or args.text_offset == 0, 'text-offset requires a unit')
    snapshot = token(work, [vid]); check_token(args, snapshot)
    rows, budget, index, text_offset = [], args.chars, offset, args.text_offset
    while index < len(units) and len(rows) < limit and budget > 0:
        u = units[index]; text = u['text']
        L.require(text_offset <= len(text), 'text-offset is outside the unit')
        end = min(len(text), text_offset + budget)
        artifacts = [a for a in work['artifacts'] if a['source_version_id'] == vid
                     and a.get('locator') in (None, u['locator'])]
        row = dict(unit_id=u['id'], read_id=u['read_id'], state=u['state'],
                   locator=preview(u['locator'], 1500), text=text[text_offset:end],
                   text_start=text_offset, text_end=end, text_total=len(text),
                   text_complete=text_offset == 0 and end == len(text),
                   limitations=preview(u.get('limitations', [])), errors=preview(u.get('errors', [])),
                   artifact_count=len(artifacts), artifacts=[dict(id=a['id'], path=preview(a['path']),
                       sha256=a['sha256']) for a in artifacts[:3]])
        from .derived import is_ocr, WARNING
        if is_ocr(u):
            row.update(warning=WARNING, derived_from=preview(u['derived_from']))
        if u['locator'].get('unit') == 'table_query_derived':
            from .table_query import WARNING as QUERY_WARNING
            row.update(warning=QUERY_WARNING, derived_from=preview(u.get('derived_from')))
        rows.append(row); budget -= end - text_offset
        if end < len(text):
            text_offset = end
            break
        index += 1; text_offset = 0
    continuation = dict(offset=index, text_offset=text_offset, snapshot=snapshot) if index < len(units) else None
    return dict(run_id=work['run']['id'], source_version_id=vid, snapshot=snapshot,
                unit_filter=args.unit, total_units=len(units), offset=offset, units=rows,
                returned_units=len(rows), complete_units_before_next=index, remaining_units=len(units)-index,
                next=continuation, notice=NOTICE,
                metadata_notice='Metadata previews may be truncated; inspect --version retains full records. Artifact preview is limited to 3.')


def search_page(args, work, record, scope_selection=None):
    section = getattr(args, 'section', 'results')
    values = record[section]
    # External imports may use a scalar scope. Preserve it as one scope item.
    if not isinstance(values, list): values = [values]
    offset, limit = bounds(args, len(values))
    rows = []
    for index, hit in enumerate(values[offset:offset + limit], offset):
        if section == 'results' and isinstance(hit, dict) and 'unit_id' in hit:
            import re
            text = hit.get('text', '')
            match = re.search(record['keywords'][0], text, re.IGNORECASE)
            start = max(0, match.start() - 120) if match else 0
            row = dict(index=index, source_version_id=hit['source_version_id'], unit_id=hit['unit_id'],
                       locator=preview(hit.get('locator'), 1500), text=text[start:start+600],
                       text_start=start, text_end=min(start+600, len(text)), text_total=len(text),
                       truncated=start > 0 or start+600 < len(text))
            if hit.get('warning'): row['warning'] = hit['warning']
            rows.append(row)
        else:
            rows.append(dict(index=index, value=preview(hit, 2000)))
    end = offset + len(rows)
    return dict(search_record_id=record['id'], run_id=work['run']['id'], section=section,
                matches=len(record['results']), unread_count=len(record['unread_parts']),
                searched_version_count=len(record['material_snapshot']), total=len(values), offset=offset,
                returned=len(rows), remaining=len(values)-end, next_offset=end if end < len(values) else None,
                results=rows, scope_selection=scope_selection, notice=NOTICE,
                full_record_location='SearchRecord in staging/working.json or committed ledger/ledger.json; use search-results to continue')


def saved_search(args, api):
    work = load_work(args, api)
    record = work['records'].get(args.search_id)
    L.require(record and record['kind'] == 'SearchRecord', 'Unknown search record in selected run')
    return search_page(args, work, record)
