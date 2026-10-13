"""Single-run evidence ledger, deterministic decimal calculations and linked Markdown export."""
import ast
import copy
import hashlib
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN
from pathlib import Path
from urllib.parse import quote as urlquote

SCHEMA = 'evidence-ledger-1.0'
VERSION = '0.3.1'
MODES = {'query', 'verify', 'coverage', 'draft', 'review', 'rules'}
KINDS = {'Source', 'SourceVersion', 'ReadRecord', 'ReviewTask', 'Claim', 'Evidence', 'EvidenceLink',
         'SearchRecord', 'EvidenceGap', 'Calculation', 'RuleApplication', 'Finding', 'HumanDecision', 'OutputRecord'}
ASSESSMENTS = {'unassessed', 'insufficient', 'partial', 'supported', 'refuted'}
ROLES = {'business', 'signed', 'draft', 'department_statement', 'transcript', 'template', 'ai_analysis',
         'workpaper', 'external_rule', 'policy_explanation', 'unknown'}


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def checksum(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uid() + '.tmp')
    try:
        with tmp.open('xb') as f:
            f.write(encoded(value))
            f.flush()
            os.fsync(f.fileno())
        if path.name == 'ledger.json' and os.environ.get('EVIDENCE_REVIEWER_FAILPOINT') == 'before_replace':
            os._exit(86)  # Explicit local fault-injection test; the previous ledger remains intact.
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def lock(project):
    import fcntl
    with (Path(project) / '.writer.lock').open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another writer holds the project lock')
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def add(work, kind, body, entity_id=None):
    entity_id = entity_id or uid()
    require(entity_id not in work['records'], 'Duplicate stable ID')
    work['records'][entity_id] = dict(body, id=entity_id, kind=kind)
    return entity_id


def current_records(ledger):
    return {entity_id: ledger['revisions'][ledger['current'][entity_id]]['after'] for entity_id in ledger['record_order']}


def decimal_calc(expression, values, places, rounding):
    require(isinstance(places, int) and 0 <= places <= 12, 'rounding places must be 0..12')
    require(rounding in {'ROUND_HALF_UP', 'ROUND_HALF_EVEN', 'ROUND_DOWN'}, 'Unsupported rounding')
    require(isinstance(expression, str) and len(expression) <= 2000, 'Invalid formula length')
    tree = ast.parse(expression, mode='eval')
    require(sum(1 for _ in ast.walk(tree)) <= 160, 'Formula too complex')

    def calc(node):
        if isinstance(node, ast.Expression):
            return calc(node.body)
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = calc(node.left), calc(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            return a / b
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return calc(node.operand) * (1 if isinstance(node.op, ast.UAdd) else -1)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('sum', 'min', 'max', 'abs') and not node.keywords:
            args = [calc(x) for x in node.args]
            require(bool(args), 'Empty function args')
            if node.func.id == 'abs':
                require(len(args) == 1, 'abs accepts one input')
                return abs(args[0])
            return {'sum': sum, 'min': min, 'max': max}[node.func.id](args)
        raise ValueError('Formula supports named inputs, + - * / and sum/min/max/abs only; constants must be documented inputs')

    with localcontext() as context:
        context.prec = 38
        result = calc(tree)
        require(result.is_finite(), 'Non-finite calculation')
        return str(result.quantize(Decimal(1).scaleb(-places), rounding=rounding))


def materialize(work, assessment):
    """Resolve session-authored aliases; no business answers or case-name routing."""
    if work.get('update_context') and not work.get('_applying_update'):
        import updates
        return updates.materialize(work, assessment)
    work = copy.deepcopy(work)
    allowed = {'source_annotations', 'observations', 'tasks', 'claims', 'evidence', 'links', 'gaps',
               'calculations', 'rules', 'findings', 'human_decisions', 'answers', 'draft', 'review_checks', 'limitations', 'link_retirements'}
    require(isinstance(assessment, dict) and not set(assessment) - allowed, 'Unknown assessment fields')
    require(not assessment.get('link_retirements') or work.get('_applying_update'), 'Link retirement requires an update')
    mapping = {}
    groups = {'tasks': 'ReviewTask', 'claims': 'Claim', 'evidence': 'Evidence', 'links': 'EvidenceLink',
              'gaps': 'EvidenceGap', 'calculations': 'Calculation', 'rules': 'RuleApplication', 'findings': 'Finding',
              'human_decisions': 'HumanDecision'}
    for group in groups:
        require(isinstance(assessment.get(group, []), list), group + ' must be a list')
        for item in assessment.get(group, []):
            require(isinstance(item, dict) and nonempty(item.get('key')), 'Each entity needs a local key')
            key = item['key']
            require(key not in mapping and key not in work['records'], 'Duplicate key: ' + key)
            existing = item.get('id')
            if existing:
                require(work.get('_applying_update') and existing in work['records'], 'Existing IDs require a staged update')
                require(work['records'][existing]['kind'] == groups[group], 'Cannot change entity kind')
                require(groups[group] in {'ReviewTask', 'Claim', 'EvidenceGap', 'Calculation', 'RuleApplication', 'Finding'}, 'Evidence/event records are immutable; add a new record')
                require(existing not in mapping.values(), 'Duplicate update target')
            mapping[key] = existing or uid()

    def resolve(value, field=''):
        if isinstance(value, dict):
            return {k: resolve(v, k) for k, v in value.items() if k != 'key'}
        if isinstance(value, list):
            return [resolve(v, field[:-1] if field.endswith('_ids') else field) for v in value]
        if isinstance(value, str) and (field.endswith('_id') or field.endswith('_refs')):
            return mapping.get(value, value)
        return value

    for annotation in assessment.get('source_annotations', []):
        require(set(annotation) <= {'source_id', 'role', 'role_basis', 'issuer', 'signature_status', 'confirmation_scope',
                                     'origin_group_id', 'formed_at', 'facts_period', 'received_at', 'transcript_kind',
                                     'confirmed_speakers', 'audio_version_id'}, 'Unknown source annotation')
        source = work['records'].get(annotation.get('source_id'))
        require(source and source['kind'] == 'Source', 'Annotation source missing')
        for key, value in annotation.items():
            if key != 'source_id': source[key] = value
    for observation in assessment.get('observations', []):
        read = work['records'].get(observation.get('read_id'))
        require(read and read['kind'] == 'ReadRecord', 'Observation read_id missing')
        require(nonempty(observation.get('observation')), 'Visual observation required')
        artifact_id = observation.get('artifact_id')
        artifact = next((a for a in work['artifacts'] if a['id'] == artifact_id), None)
        require(artifact and artifact['source_version_id'] == read['source_version_id'], 'Observation must link a registered rendering/image')
        require(artifact.get('locator') in (None, read['locator']), 'Observation artifact does not cover this unit')
        add(work, 'ReadRecord', dict(source_version_id=read['source_version_id'], unit_id=read['unit_id'],
                                   locator=read['locator'], state='viewed', method='Codex visual inspection',
                                   render_version=artifact['sha256'], artifact_id=artifact_id,
                                   observation=observation['observation'], errors=[],
                                   limitations=observation.get('limitations', [])))
    for group, kind in groups.items():
        for raw in assessment.get(group, []):
            body = resolve(raw)
            existing = raw.get('id')
            if existing:
                require(nonempty(body.get('revision_reason')), 'Updated entity needs revision_reason')
                work.setdefault('_revision_reasons', {})[existing] = body['revision_reason']
                body = dict(work['records'][existing], **body)
                if kind == 'Calculation' and 'result' not in raw: body.pop('result', None)
            body.pop('revision_reason', None)
            if kind == 'EvidenceGap': body['validation_version'] = 2
            if kind == 'Calculation':
                values = {}
                for item in body.get('inputs', []):
                    name = item.get('name')
                    require(nonempty(name) and name.isidentifier() and name not in values, 'Unique input names required')
                    require(isinstance(item.get('value'), str), 'Decimal inputs must be strings')
                    value = Decimal(item['value'])
                    require(value.is_finite() and len(item['value']) < 100, 'Invalid decimal input')
                    values[name] = value
                computed = decimal_calc(body['formula'], values, body['rounding']['places'], body['rounding']['mode'])
                if 'result' in body: require(body['result'] == computed, 'Supplied calculation result differs from engine')
                body.update(result=computed, script_version='decimal-ast-1.0', calculation_engine='Python decimal, precision 38')
            if kind == 'Finding' and not existing:
                body['last_reviewed_run'] = work['run']['id']
            if existing:
                body.update(id=existing, kind=kind)
                work['records'][existing] = body
            else:
                add(work, kind, body, mapping[raw['key']])
    work['outcome'] = {k: resolve(assessment.get(k, default)) for k, default in
                       [('answers', []), ('draft', None), ('review_checks', []), ('limitations', [])]}
    work['assessment_sha256'] = checksum(assessment)
    if work.get('_applying_update'): work['_assessment_aliases'] = mapping
    return work


def validate_records(work):
    records, run = work['records'], work['run']
    errors = []

    def check(ok, msg):
        if not ok: errors.append(msg)

    def ref(entity_id, kind, where):
        obj = records.get(entity_id)
        check(obj is not None and obj.get('kind') in (kind if isinstance(kind, tuple) else (kind,)), where + ': invalid ' + str(kind) + ' reference ' + str(entity_id))
        return obj or {}

    def refs(row, field, kind, required=False):
        values = row.get(field, [])
        check(isinstance(values, list), row['kind'] + '.' + field + ' must be a list')
        if not isinstance(values, list): return
        if required: check(bool(values), row['kind'] + '.' + field + ' cannot be empty')
        for value in values: ref(value, kind, row['id'] + '.' + field)

    def needed(row, fields):
        for field in fields:
            check(field in row, row['kind'] + ' missing ' + field)

    def source_unit(version_id, unit_id, where):
        version = ref(version_id, 'SourceVersion', where)
        u = next((u for u in work['units'].get(version_id, []) if u['id'] == unit_id), None)
        check(u is not None, where + ': unknown source unit')
        return version, u or {}

    check(len(run['source_version_snapshot']) == len(set(run['source_version_snapshot'])), 'Duplicate source version in run snapshot')
    check(set(run['source_version_snapshot']) == set(work['units']), 'Run snapshot and extracted source units differ')
    check(run.get('scope_revision') == work['project'].get('scope_revision'), 'Run scope revision differs from project')
    check(run.get('selected_main_version') == work['project'].get('selected_main_version'), 'Run main version differs from project')
    retired = {}
    for item in run.get('evidence_link_retirements', []):
        lid = item.get('link_id')
        ref(lid, 'EvidenceLink', 'retirement')
        check(lid not in retired and nonempty(item.get('reason')), 'Retirement needs unique link and reason')
        check(item.get('retired_in_run_id') in work.get('_known_run_ids', [run['id']]), 'Unknown retirement run')
        retired[lid] = item
    for lid in retired:
        link = records.get(lid, {})
        claim = records.get(link.get('claim_id'), {})
        if link.get('source_usage') == 'fact_basis' and claim.get('assessment') in {'supported', 'partial'}:
            alternatives = [r for r in records.values() if r.get('kind') == 'EvidenceLink'
                            and r.get('claim_id') == claim['id'] and r.get('direction') == 'supports'
                            and r['id'] not in retired and r['id'] != lid]
            check(bool(alternatives), 'Supported claim still depends solely on retired fact evidence; revise it or supply a current supporting link')
    unit_ids = [u['id'] for units in work['units'].values() for u in units]
    check(len(unit_ids) == len(set(unit_ids)), 'Duplicate source unit ID')

    for key, row in records.items():
        kind = row.get('kind')
        check(key == row.get('id') and kind in KINDS, 'Invalid entity identity/kind')
        if kind == 'Source':
            check(row.get('role') in ROLES, 'Invalid source role')
            check(row.get('signature_status') in ('unknown', 'unsigned', 'signed_unverified', 'verified'), 'Invalid signature status')
            if row.get('role') != 'unknown': check(nonempty(row.get('role_basis')), 'Classified source needs role_basis')
            if row.get('origin_group_id') != row['id']:
                ref(row.get('origin_group_id'), 'Source', row['id'] + '.origin_group_id')
        elif kind == 'SourceVersion':
            ref(row.get('source_id'), 'Source', row['id'])
            if row.get('based_on_output_id'): ref(row['based_on_output_id'], 'OutputRecord', row['id'])
            check(row['id'] in run['source_version_snapshot'], 'Source version absent from run snapshot')
            refs(row, 'derived_from_version_ids', 'SourceVersion')
            check(row['id'] not in row.get('derived_from_version_ids', []), 'Self-derived source version')
            if row.get('local_snapshot'): check(bool(row.get('sha256')), 'Snapshot without fingerprint')
        elif kind == 'ReadRecord':
            source_unit(row.get('source_version_id'), row.get('unit_id'), row['id'])
            check(row.get('state') in {'unread', 'extracted', 'viewed', 'failed', 'manual_check'}, 'Invalid reading state')
            if row.get('state') == 'viewed': check(nonempty(row.get('observation')) and row.get('artifact_id'), 'Viewed record missing actual observation/artifact')
        elif kind == 'ReviewTask':
            needed(row, ['objective', 'procedure', 'population', 'sampling_basis', 'actual_scope', 'uncovered_scope', 'execution_state', 'result', 'basis', 'next_step'])
            check(row.get('execution_state') in {'not_started', 'partial', 'done', 'not_applicable'}, 'Invalid task execution state')
            check(row.get('result') in {'no_exception', 'exception', 'undetermined', 'not_applicable'}, 'Invalid task result')
            check(nonempty(row.get('basis')), 'Task needs reasoning/evidence boundary')
            if row.get('execution_state') == 'not_applicable': check(row.get('result') == 'not_applicable', 'N/A task result mismatch')
            refs(row, 'source_version_ids', 'SourceVersion')
            refs(row, 'record_ids', ('SourceVersion', 'Evidence', 'Claim', 'Finding'))
        elif kind == 'Claim':
            needed(row, ['proposition', 'type', 'origin', 'assessment', 'basis'])
            check(row.get('type') in {'fact', 'assumption', 'normative'}, 'Invalid claim type')
            check(row.get('origin') in {'source_statement', 'reviewer_hypothesis', 'reviewer_opinion'}, 'Invalid claim origin')
            check(row.get('assessment') in ASSESSMENTS, 'Invalid claim assessment')
            refs(row, 'task_ids', 'ReviewTask', True)
            refs(row, 'child_ids', 'Claim')
            if row.get('parent_id'): ref(row['parent_id'], 'Claim', row['id'])
            if row.get('origin') == 'source_statement':
                loc = row.get('source_locator') or {}
                source_unit(loc.get('source_version_id'), loc.get('unit_id'), row['id'])
        elif kind == 'Evidence':
            needed(row, ['verbatim_quote', 'reviewer_summary', 'reading_method', 'verification_state', 'limitations'])
            version, u = source_unit(row.get('source_version_id'), row.get('unit_id'), row['id'])
            quote = row.get('verbatim_quote')
            image_description = row.get('image_region_description')
            check(bool(quote) or nonempty(image_description), 'Evidence needs exact quote or observed image description')
            if quote: check(isinstance(quote, str) and quote in u.get('text', ''), 'Evidence quote does not occur in cited unit')
            if image_description or row.get('verification_state') == 'original_viewed':
                check(any(r['kind'] == 'ReadRecord' and r.get('state') == 'viewed' and r.get('unit_id') == row.get('unit_id') and r.get('source_version_id') == row.get('source_version_id') for r in records.values()), 'Visual evidence has no view record')
            check(row.get('verification_state') in {'extracted_only', 'original_viewed', 'transcript_unverified', 'tool_body_read', 'snippet_only'}, 'Invalid verification state')
        elif kind == 'EvidenceLink':
            ev = ref(row.get('evidence_id'), 'Evidence', row['id'])
            ref(row.get('claim_id'), 'Claim', row['id'])
            needed(row, ['direction', 'supported_scope', 'conditions', 'sufficiency', 'limitations', 'source_usage'])
            check(row.get('direction') in {'supports', 'opposes', 'context'}, 'Invalid evidence direction')
            check(row.get('source_usage') in {'fact_basis', 'statement_only', 'context'}, 'Invalid source usage')
            srcver = records.get(ev.get('source_version_id'), {})
            src = records.get(srcver.get('source_id'), {})
            if src.get('role') in {'ai_analysis', 'template', 'workpaper'}:
                check(row.get('source_usage') != 'fact_basis' or row['id'] in retired, 'AI/template/workpaper cannot independently establish business fact')
        elif kind == 'SearchRecord':
            needed(row, ['purpose', 'material_snapshot', 'scope', 'method', 'tool', 'queried_at', 'results', 'unread_parts'])
            refs(row, 'task_ids', 'ReviewTask')
            refs(row, 'claim_ids', 'Claim')
            for version_id in row.get('material_snapshot', []): ref(version_id, 'SourceVersion', row['id'])
            if row.get('external'):
                check(row.get('acquisition_state') in {'full_body', 'partial_body', 'snippet_only', 'unavailable', 'tool_unavailable'}, 'Invalid web acquisition state')
                check(row.get('body_opened') == (row.get('acquisition_state') in {'full_body', 'partial_body'}), 'Web body status contradicts acquisition state')
        elif kind == 'EvidenceGap':
            needed(row, ['expected_fact', 'reason_insufficient', 'minimal_request', 'state'])
            refs(row, 'task_ids', 'ReviewTask', True)
            refs(row, 'claim_ids', 'Claim')
            refs(row, 'search_record_ids', 'SearchRecord', True)
            check(row.get('state') in {'open', 'satisfied', 'withdrawn'}, 'Invalid gap state')
            if row.get('validation_version', 1) >= 2 and row.get('state') != 'open':
                check(nonempty(row.get('resolution_reason')), 'Closed gap needs resolution_reason')
                if row.get('state') == 'satisfied': refs(row, 'resolution_evidence_ids', 'Evidence', True)
        elif kind == 'Calculation':
            needed(row, ['purpose', 'inputs', 'formula', 'rounding', 'result', 'result_kind', 'assumptions', 'limitations', 'unit', 'currency'])
            check(row.get('result_kind') in {'recalculation', 'conditional_estimate', 'scale_check'}, 'Invalid result kind')
            vals = {}
            for inp in row.get('inputs', []):
                needed(dict(inp, kind='CalculationInput'), ['name', 'value', 'raw_value', 'unit', 'currency', 'period', 'tax_basis', 'normalization'])
                try:
                    check(isinstance(inp.get('value'), str), 'Decimal input must be string')
                    vals[inp['name']] = Decimal(inp['value'])
                except (KeyError, TypeError, InvalidOperation): check(False, 'Invalid decimal input')
                if inp.get('source_version_id'):
                    _, u = source_unit(inp['source_version_id'], inp.get('unit_id'), row['id'])
                    check(nonempty(inp.get('raw_value')) and inp['raw_value'] in u.get('text', ''), 'Calculation raw input not present at cited unit')
                else:
                    check(inp.get('input_kind') == 'parameter' and nonempty(inp.get('basis')), 'Non-source input must be a documented assumption parameter')
            try:
                check(row.get('result') == decimal_calc(row['formula'], vals, row['rounding']['places'], row['rounding']['mode']), 'Calculation not reproducible')
            except Exception as exc: check(False, 'Calculation error: ' + str(exc))
        elif kind == 'RuleApplication':
            needed(row, ['name', 'issuer', 'reposting_body', 'document_number', 'nature', 'published_at', 'effective_at', 'repealed_at', 'jurisdiction', 'official_url', 'attachment_url', 'critical_text', 'subjects', 'conditions', 'exceptions', 'behavior_time', 'applicability_reason', 'unknowns', 'verification_state'])
            refs(row, 'task_ids', 'ReviewTask')
            refs(row, 'claim_ids', 'Claim')
            refs(row, 'search_record_ids', 'SearchRecord')
            check(row.get('verification_state') in {'body_verified', 'unverified', 'snippet_only'}, 'Invalid rule verification state')
            if row.get('source_version_id'):
                version, u = source_unit(row['source_version_id'], row.get('unit_id'), row['id'])
                check(row.get('critical_text') in u.get('text', ''), 'Rule critical text absent from source unit')
                if version.get('acquisition_state') in {'snippet_only', 'unavailable', 'tool_unavailable'}:
                    check(row.get('verification_state') != 'body_verified', 'Snippet cannot verify rule body')
            else:
                check(row.get('verification_state') in {'unverified', 'snippet_only'}, 'Verified rule requires actual source')
        elif kind == 'Finding':
            needed(row, ['proposition', 'summary', 'impact', 'impact_basis', 'severity', 'recommended_action', 'contact_role', 'assessment', 'workflow', 'disposition', 'review_freshness', 'closure_reason'])
            refs(row, 'task_ids', 'ReviewTask', True)
            refs(row, 'claim_ids', 'Claim', True)
            refs(row, 'supporting_link_ids', 'EvidenceLink')
            refs(row, 'opposing_link_ids', 'EvidenceLink')
            refs(row, 'calculation_ids', 'Calculation')
            refs(row, 'rule_ids', 'RuleApplication')
            check(row.get('assessment') in ASSESSMENTS, 'Invalid finding assessment')
            check(row.get('workflow') in {'open', 'awaiting_evidence', 'awaiting_action', 'awaiting_review', 'closed'}, 'Invalid workflow')
            check(row.get('disposition') in {'active', 'withdrawn', 'superseded'}, 'Invalid disposition')
            check(row.get('review_freshness') in {'current', 'needs_review'}, 'Invalid freshness')
            if row.get('workflow') == 'closed': check(nonempty(row.get('closure_reason')), 'Closed finding requires reason')
            if row.get('disposition') == 'superseded': ref(row.get('successor_id'), 'Finding', row['id'])
            check(row.get('last_reviewed_run') in work.get('_known_run_ids', [run['id']]), 'Wrong finding review run')
            for field, direction in [('supporting_link_ids', 'supports'), ('opposing_link_ids', 'opposes')]:
                for link_id in row.get(field, []):
                    link = records.get(link_id, {})
                    if row.get('disposition') == 'active': check(link_id not in retired, 'Current finding still uses a retired evidence link')
                    check(link.get('direction') == direction and link.get('claim_id') in row.get('claim_ids', []), 'Finding link direction or claim mismatch')
        elif kind == 'HumanDecision':
            needed(row, ['target_id', 'decision', 'reason', 'at', 'actual_actor', 'source_evidence_id'])
            ref(row.get('target_id'), tuple(KINDS), row['id'])
            ref(row.get('source_evidence_id'), 'Evidence', row['id'])
            check(nonempty(row.get('actual_actor')) and row.get('actual_actor').lower() not in {'ai', 'codex', 'assistant'}, 'Human decision requires actual person and external evidence')
        elif kind == 'OutputRecord':
            check(row.get('run_id') in work.get('_known_run_ids', [run['id']]) and row.get('source_role') == 'workpaper_or_draft', 'Invalid output provenance')

    # Detect derived/source lineage cycles, not merely immediate self-references.
    for kind, field in [('SourceVersion', 'derived_from_version_ids'), ('Source', 'origin_group_id')]:
        def walk(key, ancestors):
            if key in ancestors:
                check(False, 'Source lineage cycle')
                return
            row = records.get(key, {})
            nexts = row.get(field, [])
            if isinstance(nexts, str): nexts = [] if nexts == key else [nexts]
            for target in nexts: walk(target, ancestors | {key})
        for key, row in records.items():
            if row['kind'] == kind: walk(key, set())
    outcome = work.get('outcome', {})
    check(bool(outcome.get('answers')), 'At least one task answer is required; findings are optional')
    for answer in outcome.get('answers', []):
        check(nonempty(answer.get('text')), 'Answer text required')
        refs(dict(answer, kind='Answer', id='answer'), 'evidence_ids', 'Evidence')
        refs(dict(answer, kind='Answer', id='answer'), 'calculation_ids', 'Calculation')
        refs(dict(answer, kind='Answer', id='answer'), 'rule_ids', 'RuleApplication')
        refs(dict(answer, kind='Answer', id='answer'), 'task_ids', 'ReviewTask')
        check(any(answer.get(k) for k in ('evidence_ids', 'calculation_ids', 'rule_ids', 'task_ids')), 'Answer requires traceable basis, including an undetermined task for unavailable material')
    if 'draft' in work['project']['modes']:
        draft = outcome.get('draft')
        check(isinstance(draft, dict) and bool(draft.get('sections')), 'Draft mode requires a draft with sourced sections')
        if isinstance(draft, dict):
            check(draft.get('confirmation_status') == 'unconfirmed', 'Generated draft cannot be marked confirmed')
            for section in draft.get('sections', []):
                refs(dict(section, kind='DraftSection', id='draft'), 'evidence_ids', 'Evidence')
                refs(dict(section, kind='DraftSection', id='draft'), 'calculation_ids', 'Calculation')
    checks = outcome.get('review_checks', [])
    if set(work['project']['modes']) & {'verify', 'coverage', 'review', 'draft'}:
        check(bool(checks), 'Review needs an explicit final check of conclusions and selected non-findings')
    for item in checks:
        ref(item.get('target_id'), ('ReviewTask', 'Claim', 'Finding', 'EvidenceGap', 'Calculation', 'RuleApplication') if work.get('_known_run_ids') else ('ReviewTask', 'Claim', 'Finding'), 'review_check')
        check(nonempty(item.get('reason')) and nonempty(item.get('result')), 'Review check needs selection reason and result')
        refs(dict(item, kind='ReviewCheck', id='review_check'), 'evidence_ids', 'Evidence')
    main = work['project'].get('selected_main_version')
    if main: ref(main, 'SourceVersion', 'selected_main_version')
    require(not errors, '\n'.join(errors))
    from visual_checks import validate as validate_visual_checks
    validate_visual_checks(work)
    from reporting import reading_coverage
    coverage = reading_coverage(work)
    return {'entities': len(records), 'calculations': sum(r['kind'] == 'Calculation' for r in records.values()), 'errors': [],
            'structure_valid': True, 'material_reading': coverage['state'], 'reading_issues': coverage['issues']}


def freeze(work):
    ledger = {'schema_version': SCHEMA, 'project': work['project'], 'runs': {work['run']['id']: work['run']},
              'entities': {}, 'revisions': {}, 'current': {}, 'latest_run_id': work['run']['id'],
              'record_order': list(work['records']),
              'units': work['units'], 'artifacts': work['artifacts'], 'outcome': work['outcome'],
              'assessment_sha256': work['assessment_sha256']}
    for key, body in work['records'].items():
        revision_id = uid()
        ledger['entities'][key] = {'id': key, 'kind': body['kind'], 'created_run_id': work['run']['id']}
        ledger['revisions'][revision_id] = {'id': revision_id, 'entity_id': key, 'previous_revision_id': None,
                                          'run_id': work['run']['id'], 'time': work['run']['finished_at'], 'actor': 'Codex session with deterministic tools',
                                          'before': None, 'after': body, 'reason': 'Initial single-review record', 'trigger_refs': work['run']['source_version_snapshot']}
        ledger['current'][key] = revision_id
    return ledger


def thaw(ledger):
    if ledger.get('schema_version') == 'evidence-ledger-2.0':
        import history
        return history.thaw(ledger)
    require(ledger.get('schema_version') == SCHEMA, 'Unknown ledger schema')
    unsigned = {k: v for k, v in ledger.items() if k != 'integrity_sha256'}
    require(ledger.get('integrity_sha256') == checksum(unsigned), 'Ledger integrity mismatch; preserve damaged file and inspect validated-candidate/backup, never reset to empty')
    require(set(ledger['entities']) == set(ledger['current']), 'Entity/current mismatch')
    require(set(ledger.get('record_order', [])) == set(ledger['current']) and len(ledger['record_order']) == len(ledger['current']), 'Missing or invalid stable record order')
    require(len(ledger['current']) == len(ledger['revisions']), 'Single-run ledger contains unreferenced or missing initial revisions')
    for entity_id, revision_id in ledger['current'].items():
        rev = ledger['revisions'].get(revision_id)
        require(rev and rev.get('entity_id') == entity_id and rev['after']['id'] == entity_id, 'Broken revision pointer')
        require(rev['after']['kind'] == ledger['entities'][entity_id]['kind'], 'Revision kind mismatch')
        require(rev.get('before') is None and rev.get('previous_revision_id') is None, 'Single-run initial revision has a fabricated prior state')
        require(rev['run_id'] in ledger['runs'] and ledger['runs'][rev['run_id']]['state'] == 'completed', 'Revision references incomplete run')
    run = ledger['runs'][ledger['latest_run_id']]
    require(run['state'] == 'completed', 'Latest run incomplete')
    return dict(project=ledger['project'], run=run, records=current_records(ledger), units=ledger['units'],
                artifacts=ledger['artifacts'], outcome=ledger['outcome'], assessment_sha256=ledger['assessment_sha256'])


def locator_text(locator):
    names = {'physical_page': '物理页', 'sheet': '工作表', 'cell_range': '单元格', 'part': '部件',
             'block_path': 'XML锚点', 'paragraph_anchor': '行/段锚点', 'record_number': '记录行',
             'cue_id': '字幕编号', 'time_start': '起点', 'time_end': '终点', 'layer': '文字层'}
    return '；'.join(f'{names.get(k,k)}={v}' for k, v in locator.items() if k != 'unit' and v is not None)


def render(work, project_path):
    # Match JSON round-trip ordering even inside locators/rounding/search dictionaries.
    normalized = json.loads(encoded(work))
    normalized['records'] = {key: normalized['records'][key] for key in work['records']}
    work = normalized
    r, outcome, run = work['records'], work['outcome'], work['run']
    old_outputs = [x for x in r.values() if x['kind'] == 'OutputRecord' and x.get('run_id') == run['id']]
    renderer_version = work.get('_renderer_version', old_outputs[0].get('renderer_version', 1) if old_outputs else 6)
    if renderer_version >= 6:
        import reporting
        return reporting.render(work, project_path)
    if renderer_version >= 5:
        import reporting_v5
        return reporting_v5.render(work, project_path)
    if renderer_version >= 4:
        import history
        return history.render(work, project_path)
    full = bool(set(work['project']['modes']) & {'verify', 'coverage', 'review', 'draft'})

    def source_name(version, source):
        if work.get('_version_labels'):
            return version.get('actual_name') or (Path(version['local_snapshot']).name if version.get('local_snapshot') and version.get('format') != 'web' else source['actual_name'])
        return source['actual_name']

    def evidence_label(eid):
        e = r[eid]
        v = r[e['source_version_id']]
        s = r[v['source_id']]
        locator = next(u['locator'] for u in work['units'][v['id']] if u['id'] == e['unit_id'])
        path = str(Path(project_path) / v['local_snapshot']) if v.get('local_snapshot') else s.get('urls', [''])[0]
        return f"[{source_name(v, s)}](<{path}>)（{locator_text(locator)}；版本 {v['id']}）"

    def bases(item):
        parts = [evidence_label(eid) for eid in item.get('evidence_ids', [])]
        parts += [f"复算：{r[x]['purpose']} = {r[x]['result']} {r[x]['unit']}" for x in item.get('calculation_ids', [])]
        parts += [f"规则：{r[x]['name']}，{r[x]['applicability_reason']}" for x in item.get('rule_ids', [])]
        return '；'.join(parts)

    lines = ['# ' + ('审查结果' if full or renderer_version == 1 else '查询结果'), '', f"目标：{work['project']['goal']}", '',
             f"轮次：`{run['id']}`；完成时间：{run['finished_at']}。" + ('这是供人工审定的审查结果。' if full or renderer_version == 1 else ''), '',
             f"主稿：{work['project'].get('selected_main_version') or '未指定／本任务不要求'}", '', '## 本次结果', '']
    for answer in outcome['answers']:
        lines += [answer['text'], '', bases(answer), '']
    if outcome['limitations']:
        lines += ['## 限制', ''] + ['- ' + str(x) for x in outcome['limitations']] + ['']
    tasks = [x for x in r.values() if x['kind'] == 'ReviewTask']
    if tasks or renderer_version == 1: lines += ['## 业务检查覆盖', '']
    for task in tasks:
        lines += [f"### {task['objective']}", '', f"程序：{task['procedure']}", '',
                  f"总体：{task['population']}；抽查依据：{task['sampling_basis']}", '',
                  f"实际范围：{task['actual_scope']}；未覆盖：{task['uncovered_scope']}", '',
                  f"执行：{task['execution_state']}；结果：{task['result']}。{task['basis']}", '', f"下一步：{task['next_step']}", '']
    findings = [x for x in r.values() if x['kind'] == 'Finding']
    if findings:
        lines += ['## 问题与意见', '']
        for f in findings:
            lines += [f"### {f['proposition']}", '', f['summary'], '',
                      f"证据判断：{f['assessment']}；处理进度：{f['workflow']}；意见效力：{f['disposition']}；复核状态：{f['review_freshness']}", '',
                      f"影响：{f['impact']}。依据：{f['impact_basis']}；严重程度：{f['severity']}", '',
                      f"建议：{f['recommended_action']}；关闭原因：{f['closure_reason'] or '不适用'}", '']
            for label, field in [('支持', 'supporting_link_ids'), ('反证', 'opposing_link_ids')]:
                for lid in f.get(field, []):
                    link = r[lid]
                    lines += [f"- {label}：{evidence_label(link['evidence_id'])}；{link['supported_scope']}；条件：{link['conditions']}；限制：{link['limitations']}"]
            lines += ['']
    gaps = [g for g in r.values() if g['kind'] == 'EvidenceGap' and g['state'] == 'open']
    if gaps or full or renderer_version == 1: lines += ['## 必要补充材料', '']
    if not gaps and (full or renderer_version == 1): lines += ['本次没有登记尚待索取的材料。', '']
    for g in gaps:
        lines += [f"- 为核实“{g['expected_fact']}”：{g['minimal_request']}。现有不足：{g['reason_insufficient']}"]
        for sid in g['search_record_ids']:
            search = r[sid]
            lines += [f"  已查：{search['scope']}；方法：{search['method']}；结果：{search['results']}；未读：{search['unread_parts']}"]
    lines += ['', '## 原件、读取覆盖及出处', '']
    for version_id in run['source_version_snapshot']:
        version = r[version_id]
        src = r[version['source_id']]
        path = str(Path(project_path) / version['local_snapshot']) if version.get('local_snapshot') else (src.get('urls') or [''])[0]
        lines += [f"### [{source_name(version, src)}](<{path}>)", '',
                  f"角色：{src['role']}；身份依据：{src['role_basis']}；签署：{src['signature_status']}；同源组：{src['origin_group_id']}", '',
                  f"版本：`{version_id}`；取得：{version['availability']}；SHA256：{version.get('sha256') or '正文未取得'}", '']
        if version.get('url'): lines += [f"官方/来源页面：[{version['url']}]({version['url']})；获取状态：{version.get('acquisition_state')}；保存类型：{version.get('snapshot_kind')}", '']
        ordered_reads = list(r.values())
        if renderer_version >= 2:
            order = {u['id']: i for i, u in enumerate(work['units'][version_id])}
            ordered_reads = sorted((x for x in r.values() if x['kind'] == 'ReadRecord'), key=lambda x: (order.get(x.get('unit_id'), -1), x.get('state') == 'viewed', x['id']))
        for read in ordered_reads:
            if read['kind'] == 'ReadRecord' and read['source_version_id'] == version_id:
                lines += [f"- {locator_text(read['locator']) or '整文件'}：{read['state']}；{'；'.join(read.get('limitations', []))}" + (f"；错误：{read['errors']}" if read.get('errors') else '') + (f"；回看：{read['observation']}" if read.get('observation') else '')]
        lines += ['']
    evidence = [e for e in r.values() if e['kind'] == 'Evidence']
    if evidence: lines += ['## 证据摘录及证明边界', '']
    for e in evidence:
        lines += [evidence_label(e['id']), '', f"原文摘录：{e.get('verbatim_quote') or '无；依据图像观察'}", '',
                  f"审查概括：{e['reviewer_summary']}；图像说明：{e.get('image_region_description') or '不适用'}", '',
                  f"读取：{e['reading_method']}；核验：{e['verification_state']}；限制：{e['limitations']}", '']
    calculations = [c for c in r.values() if c['kind'] == 'Calculation']
    if calculations: lines += ['## 可追溯复算', '']
    for c in calculations:
        lines += [f"### {c['purpose']}", '', f"公式：`{c['formula']}`；结果：{c['result']} {c['unit']}（{c['currency']}）；类型：{c['result_kind']}", '',
                  f"舍入：{c['rounding']}；假设：{c['assumptions']}；限制：{c['limitations']}", '']
        for inp in c['inputs']:
            origin = inp.get('basis', '')
            if inp.get('source_version_id'):
                v = r[inp['source_version_id']]
                u = next(u for u in work['units'][v['id']] if u['id'] == inp['unit_id'])
                origin = source_name(v, r[v['source_id']]) + '；' + locator_text(u['locator'])
            lines += [f"- {inp['name']}：原值 {inp['raw_value']} → {inp['value']}；{inp['unit']}/{inp['currency']}；期间：{inp['period']}；税口径：{inp['tax_basis']}；转换：{inp['normalization']}；出处：{origin}"]
        lines += ['']
    rules = [x for x in r.values() if x['kind'] == 'RuleApplication']
    if rules: lines += ['## 制度依据及适用条件', '']
    for rule in rules:
        lines += [f"### {rule['name']}", '', f"发布：{rule['issuer']}；转载：{rule['reposting_body']}；文号：{rule['document_number']}；性质：{rule['nature']}", '',
                  f"发布/生效/废止：{rule['published_at']} / {rule['effective_at']} / {rule['repealed_at']}", '',
                  f"关键原文：{rule['critical_text']}；核验：{rule['verification_state']}", '',
                  f"主体：{rule['subjects']}；条件：{rule['conditions']}；例外：{rule['exceptions']}；行为时点：{rule['behavior_time']}", '',
                  f"适用：{rule['applicability_reason']}；待核：{rule['unknowns']}", '']
        for label, field in [('官方页面', 'official_url'), ('附件', 'attachment_url')]:
            if rule.get(field): lines += [f"[{label}]({rule[field]})", '']
    if outcome['review_checks'] or full or renderer_version == 1: lines += ['## 最终复核与初始历史', '']
    for item in outcome['review_checks']:
        lines += [f"- 选择理由：{item['reason']}；复核结果：{item['result']}。{bases(item)}"]
    if full or renderer_version == 1:
        lines += ['', f"本轮创建稳定ID、原件版本及初始Revision；所有判断与导出对应 {run['id']}。未实施跨批补证更新。", '']
    result = {'review.md': '\n'.join(lines)}
    if renderer_version >= 3 and set(work['project']['modes']) == {'query'}:
        concise = ['# 查询结果', '']
        for answer in outcome['answers']:
            concise += [answer['text'], '', bases(answer), '']
        for c in calculations:
            concise += [f"复算：`{c['formula']}` = {c['result']} {c['unit']}。", '']
            for inp in c['inputs']:
                if inp.get('source_version_id'):
                    v = r[inp['source_version_id']]
                    s = r[v['source_id']]
                    u = next(u for u in work['units'][v['id']] if u['id'] == inp['unit_id'])
                    target = str(Path(project_path) / v['local_snapshot']) if v.get('local_snapshot') else v['url']
                    concise += [f"- {inp['name']} = {inp['value']} {inp['unit']}：[ {source_name(v, s)} ](<{target}>)，{locator_text(u['locator'])}"]
            if c['assumptions'] or c['limitations']:
                concise += ['', f"计算条件：{c['assumptions']}；限制：{c['limitations']}", '']
        if outcome['limitations']: concise += ['限制：' + '；'.join(outcome['limitations']), '']
        concise += [f"出处与读取记录已保存，对应轮次 `{run['id']}`。", '']
        result['review.md'] = '\n'.join(concise)
    if outcome.get('draft'):
        draft = outcome['draft']
        dl = ['# ' + draft.get('title', '取证记录草稿'), '', '状态：草稿，未经确认。', '', f"对应轮次：`{run['id']}`", '']
        for section in draft['sections']:
            dl += ['## ' + section['heading'], '', section['text'], '', bases(section), '']
        dl += ['签字：待实际签署；确认日期：未取得；确认范围：未取得。', '']
        result['draft.md'] = '\n'.join(dl)
    result['handoff.md'] = '\n'.join(['# 项目交接', '', '目标：' + work['project']['goal'], '',
                                    f"最后完成轮次：`{run['id']}`；主稿：{work['project'].get('selected_main_version') or '未指定／不要求'}", '',
                                    f"[本轮审查结果](<{Path(project_path)/'outputs'/run['id']/'review.md'}>)", '',
                                    f"开放缺证：{len(gaps)}；未完成业务任务：{sum(t['execution_state'] in ('partial','not_started') for t in tasks)}。", '',
                                    '台账为 ledger/ledger.json，Markdown是导出视图。重建导出使用 review.py export；新材料更新属于阶段2，勿直接改写已提交台账。', ''])
    return result
