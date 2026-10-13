"""Keep historical evidence links immutable while explicitly stopping current adoption."""
import copy
import ledger as L


def retire_links(work, requested):
    L.require(isinstance(requested, list), 'link_retirements must be a list')
    old = work['_base_records']; records = work['records']; run = work['run']
    rows = copy.deepcopy(run.get('evidence_link_retirements', [])); retired = {x['link_id'] for x in rows}
    used = {lid for f in records.values() if f['kind'] == 'Finding' and f['disposition'] == 'active'
            for field in ('supporting_link_ids', 'opposing_link_ids') for lid in f.get(field, [])}
    explicit = set()
    for item in requested:
        lid = item.get('link_id')
        L.require(lid in old and old[lid]['kind'] == 'EvidenceLink' and L.nonempty(item.get('reason')), 'Retirement requires an old link ID and reason')
        L.require(lid not in explicit, 'Duplicate link retirement')
        explicit.add(lid)
        L.require(lid not in used, 'Current finding still uses a retired evidence link')
        if lid not in retired:
            rows.append(dict(link_id=lid, reason=item['reason'], retired_in_run_id=run['id']))
            retired.add(lid)
    changed_sources = {c.get('source_id') for c in run.get('changes', []) if c['type'] == 'source_annotation_changed'}
    for lid, link in old.items():
        if link['kind'] != 'EvidenceLink' or link.get('source_usage') != 'fact_basis' or lid in retired or lid in used: continue
        ev = records[link['evidence_id']]; sid = records[ev['source_version_id']]['source_id']
        claim = records[link['claim_id']]
        if sid in changed_sources and records[sid]['role'] in {'ai_analysis', 'template', 'workpaper'} and claim['assessment'] in {'unassessed', 'insufficient', 'refuted'}:
            rows.append(dict(link_id=lid, retired_in_run_id=run['id'],
                             reason='来源身份已更正且当前主张不再据此成立；保留原采用历史。' + records[sid]['role_basis']))
            retired.add(lid)
    run['evidence_link_retirements'] = rows
