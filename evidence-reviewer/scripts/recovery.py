"""Recover from validated transaction ancestry, preserving a healthy authoritative ledger."""
import copy
import shutil
from pathlib import Path
import ledger as L


def order(value): return value.get('run_order', [value['latest_run_id']])


def contains(descendant, ancestor):
    """Compare preserved history, never mtimes or just an apparent run count."""
    if descendant['project']['id'] != ancestor['project']['id']: return False
    a, d = order(ancestor), order(descendant)
    if d[:len(a)] != a: return False
    if any(descendant['runs'].get(k) != v for k, v in ancestor['runs'].items()): return False
    if any(descendant['revisions'].get(k) != v for k, v in ancestor['revisions'].items()): return False
    if any(descendant['units'].get(k) != v for k, v in ancestor['units'].items()): return False
    import history as H
    for rid in a:
        aw, dw = H.as_of(ancestor, rid), H.as_of(descendant, rid)
        if any(aw[k] != dw[k] for k in ('project', 'records', 'outcome', 'artifacts', 'assessment_sha256')): return False
    return True


def reconstruct_base(candidate, wanted_hash):
    """Accept an archived prefix only when its exact hash matches the receipt."""
    import history as H
    rid = candidate['runs'][candidate['latest_run_id']]['previous_run_id']
    if not rid or candidate.get('schema_version') != H.SCHEMA: return None
    known = order(candidate)[:order(candidate).index(rid)+1]
    snap = candidate['run_snapshots'][rid]; work = H.as_of(candidate, rid)
    base = copy.deepcopy(candidate)
    base.update(latest_run_id=rid, run_order=known,
                runs={r: candidate['runs'][r] for r in known},
                run_snapshots={r: candidate['run_snapshots'][r] for r in known},
                entities={i: e for i, e in candidate['entities'].items() if e['created_run_id'] in known},
                revisions={i: r for i, r in candidate['revisions'].items() if r['run_id'] in known},
                units=work['units'], artifacts=work['artifacts'])
    for field in ('current', 'record_order', 'project', 'outcome', 'assessment_sha256'): base[field] = snap[field]
    variants = [base]
    if len(known) == 1:
        single = copy.deepcopy(base); single['schema_version'] = L.SCHEMA
        single.pop('run_order'); single.pop('run_snapshots'); variants.append(single)
    for variant in variants:
        point = H.signed(variant)
        if point['integrity_sha256'] == wanted_hash:
            L.validate_records(L.thaw(point)); return point
    return None


def recover(args, api):
    import history as H
    project = args.project.resolve()
    with L.lock(project):
        ledger_path = project / 'ledger/ledger.json'; wp = project / 'staging/working.json'; tx_path = project / 'staging/transaction.json'
        warnings = []; transactions = []; healthy = None; identified = None
        def load_json(path):
            try: return api.load(path)
            except Exception as exc:
                warnings.append(dict(path=str(path), error=str(exc))); return None
        value = load_json(ledger_path) if ledger_path.exists() else None
        if value:
            try:
                work = L.thaw(value); L.validate_records(work); identified = value
                api.check_files(project, work); healthy = value
            except Exception as exc: warnings.append(dict(path=str(ledger_path), error=str(exc)))
        current_tx = load_json(tx_path) if tx_path.exists() else None
        work = load_json(wp) if wp.exists() else None
        if getattr(args, 'abort', False):
            L.require(healthy is not None, 'Repair the ledger and referenced files before aborting pending work')
            L.require(work is not None and work['run']['id'] not in healthy['runs'], 'Cannot abort a committed run')
            L.require(L.nonempty(getattr(args, 'reason', None)), 'Abort requires a reason')
            run_id = work['run']['id']; dest = project / 'staging/aborted' / run_id; dest.mkdir(parents=True, exist_ok=False)
            shutil.move(str(wp), str(dest/'working.json'))
            if current_tx and current_tx.get('run_id') == run_id:
                shutil.move(str(tx_path), str(dest/'transaction.json'))
            L.atomic_json(dest/'abort.json', dict(run_id=run_id, at=L.now(), reason=args.reason))
            return dict(state='aborted', preserved_at=str(dest), latest_run_id=healthy['latest_run_id'])
        aborted = set()
        for path in sorted((project/'staging/aborted').glob('*/abort.json')):
            packet = load_json(path.parent/'working.json')
            if packet: aborted.add(packet['run']['id'])
        # Include legacy abort archives: older code could have moved the previous completed receipt there.
        paths = [tx_path] + sorted((project/'ledger/transactions').glob('*.json')) + sorted((project/'staging/aborted').glob('*/transaction.json'))
        seen = set()
        for path in paths:
            if not path.exists(): continue
            tx = current_tx if path == tx_path else load_json(path)
            if not isinstance(tx, dict) or not tx.get('run_id') or tx['run_id'] in aborted: continue
            key = (tx.get('run_id'), tx.get('candidate_sha256'), tx.get('state'))
            if key in seen: continue
            seen.add(key); transactions.append((tx, path))
        if not transactions:
            candidate = project/'staging/validated-candidate.json'
            later_traces = list((project/'staging/candidates').glob('*.json')) or list((project/'ledger/backups').glob('*.json'))
            if candidate.exists() and not later_traces:
                first = load_json(candidate)
                if first and len(order(first)) == 1:
                    transactions.append((dict(state='prepared', run_id=first['latest_run_id'], candidate_path='staging/validated-candidate.json', candidate_sha256=first.get('integrity_sha256'), base_sha256=None), candidate))
        points = {}; declared_runs = set(identified['runs']) if identified else set(); checked_transactions = []
        project_id = healthy['project']['id'] if healthy else identified['project']['id'] if identified else None
        for tx, path in transactions:
            parsed = {}; usable = {}
            for kind, field in [('candidate', 'candidate_sha256'), ('backup', 'base_sha256')]:
                try:
                    point_path = api.local_path(project, tx[kind+'_path']); point = api.load(point_path)
                    L.require(point['integrity_sha256'] == tx[field], 'Recovery point fingerprint mismatch')
                    pw = L.thaw(point); L.validate_records(pw)
                    if project_id: L.require(point['project']['id'] == project_id, 'Foreign project recovery point')
                    if kind == 'candidate': L.require(point['latest_run_id'] == tx['run_id'], 'Receipt run and candidate mismatch')
                    parsed[kind] = point
                    api.check_files(project, pw); usable[kind] = point
                except Exception as exc: warnings.append(dict(path=str(path), point=kind, error=str(exc)))
            candidate, backup = parsed.get('candidate'), parsed.get('backup')
            relation_valid = True
            if candidate:
                if tx.get('base_sha256') is None:
                    relation_valid = len(order(candidate)) == 1
                else:
                    base = backup or (healthy if healthy and healthy['integrity_sha256'] == tx['base_sha256'] else None) or reconstruct_base(candidate, tx['base_sha256'])
                    relation_valid = bool(base and candidate['runs'][candidate['latest_run_id']]['previous_run_id'] == base['latest_run_id'] and contains(candidate, base))
                if not relation_valid:
                    warnings.append(dict(path=str(path), error='Candidate ancestry does not match transaction base'))
                    continue
                declared_runs.update(candidate['runs'])
            elif backup:
                # A valid backup is a fallback for this receipt, never proof that the target completed.
                declared_runs.update(backup['runs']); declared_runs.add(tx['run_id'])
            if not parsed: continue
            checked_transactions.append(tx)
            for kind, point in usable.items():
                points.setdefault(point['integrity_sha256'], dict(value=point, kind=kind, tx=tx))
        if healthy:
            chosen = healthy; origin = 'authoritative'; chosen_tx = None
            # Resume only a linked prepared transaction, never downgrade to an old cache/backup.
            candidates = [p for p in points.values() if p['kind'] == 'candidate' and p['tx']['state'] in {'prepared', 'rolled_back'}
                          and p['tx'].get('base_sha256') == healthy['integrity_sha256'] and contains(p['value'], healthy)
                          and p['value']['latest_run_id'] != healthy['latest_run_id']]
            L.require(len(candidates) <= 1, 'Ambiguous prepared transactions; preserve all recovery points')
            if candidates: chosen = candidates[0]['value']; origin = 'candidate'; chosen_tx = candidates[0]['tx']
            else:
                chosen_tx = next((tx for tx in checked_transactions if tx.get('candidate_sha256') == healthy['integrity_sha256']), None)
        else:
            L.require(bool(points), 'No verified transaction recovery point; preserve damaged ledger and recovery files')
            valid = list(points.values())
            maxima = [p for p in valid if not any(p['value']['integrity_sha256'] != q['value']['integrity_sha256'] and contains(q['value'], p['value']) for q in valid)]
            L.require(len(maxima) == 1, 'Ambiguous recovery histories; no automatic branch selection')
            selected = maxima[0]; chosen = selected['value']; origin = selected['kind']; chosen_tx = selected['tx']
        unrecovered = sorted(declared_runs - set(chosen['runs']) - aborted)
        if healthy and chosen['integrity_sha256'] == healthy['integrity_sha256']:
            # Do not replace a healthy authority merely because ancillary recovery files are damaged.
            pass
        else:
            if ledger_path.exists():
                damaged = project/'ledger/damaged'/(L.uid()+'.json'); damaged.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ledger_path, damaged)
            L.atomic_json(ledger_path, chosen)
        H.write_exports(project, chosen, api)
        state = 'rolled_back' if unrecovered else 'completed'
        if chosen_tx:
            receipt = copy.deepcopy(chosen_tx); receipt['state'] = state; receipt['recovered_at'] = L.now()
            # Preserve an unrelated prepared transaction; otherwise maintain the chosen verified index.
            if not current_tx or current_tx.get('run_id') in chosen['runs'] or current_tx.get('run_id') == receipt['run_id']:
                L.atomic_json(tx_path, receipt)
            if not unrecovered and receipt['run_id'] == chosen['latest_run_id']:
                durable = project/'ledger/transactions'/(receipt['run_id']+'.json')
                if not durable.exists(): L.atomic_json(durable, receipt)
        if work and work['run']['id'] == chosen['latest_run_id'] and not unrecovered:
            work['run']['state'] = 'completed'; api.save_work(project, work)
        pending = work['run']['id'] if work and work['run']['id'] not in chosen['runs'] and work['run']['state'] != 'completed' and work['run']['id'] not in aborted else None
        result = dict(state=state, recovered_from=origin, run_id=chosen['latest_run_id'], pending_review_run_id=pending,
                      unrecovered_run_ids=unrecovered, outputs='verified', errors=[], recovery_warnings=warnings)
        L.atomic_json(project/'ledger/recoveries'/(L.uid()+'.json'), result)
        return result
