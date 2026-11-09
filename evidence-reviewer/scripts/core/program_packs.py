"""Local JSON program packs. Methods are data, never executable instructions."""
import hashlib
import json
import re
from pathlib import Path
from . import ledger as L
from .persistence import atomic_bytes

SCHEMA = 'audit-program-pack-1'
FIELDS = ('code', 'title', 'domains', 'assertions', 'applicability', 'authority_types',
          'materials', 'steps', 'anomaly_conditions', 'exceptions', 'decision_authority',
          'unable_to_execute', 'tools')
ASSERTIONS = {'存在', '存在（发生）', '完整性', '权利和义务', '计价和分摊', '截止', '准确性', '列报'}
TOOL_STATES = {'已实现', '人工核查', '待实现', '宿主工具'}
COMMON = Path(__file__).resolve().parents[2] / 'packs/common/pack.json'


def fields(obj, names, where):
    L.require(isinstance(obj, dict), where + ' 必须为对象')
    L.require(not set(names) - set(obj), where + ' 缺字段：' + ','.join(sorted(set(names)-set(obj))))


def strings(value, where, empty=False):
    L.require(isinstance(value, list) and (empty or bool(value)) and all(L.nonempty(x) for x in value), where + ' 必须为文本列表')


def check_item(item):
    fields(item, FIELDS, '检查项')
    for name in ('code', 'title', 'applicability', 'decision_authority', 'unable_to_execute'):
        L.require(L.nonempty(item[name]), '检查项缺少 ' + name)
    L.require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', item['code']), '检查项 code 无效')
    for name in ('domains', 'authority_types', 'materials', 'steps', 'anomaly_conditions', 'exceptions', 'assertions'):
        strings(item[name], name, empty=name == 'assertions')
    L.require(set(item['assertions']) <= ASSERTIONS, '非法报表认定')
    L.require(isinstance(item['tools'], list) and item['tools'], '工具支持须明确登记')
    for tool in item['tools']:
        fields(tool, ('description', 'status', 'command'), '工具支持')
        L.require(L.nonempty(tool['description']) and tool['status'] in TOOL_STATES, '工具支持状态无效')
        L.require(tool['command'] is None or L.nonempty(tool['command']), '工具命令应为文本或 null')


def validate(pack):
    fields(pack, ('schema_version', 'pack_id', 'version', 'title', 'description', 'source', 'checks', 'overrides'), '程序包')
    L.require(pack['schema_version'] == SCHEMA, '未知程序包 schema')
    for key in ('pack_id', 'version', 'title', 'description'):
        L.require(L.nonempty(pack[key]), '程序包缺少 ' + key)
    L.require(isinstance(pack['source'], dict), 'source 必须为对象')
    L.require(isinstance(pack['checks'], list) and pack['checks'], '程序包没有检查项')
    seen = set()
    for item in pack['checks']:
        check_item(item)
        L.require(item['code'] not in seen, '重复检查项 ID：' + item['code'])
        seen.add(item['code'])
    L.require(isinstance(pack['overrides'], list), 'overrides 必须为列表')
    overridden = set()
    for override in pack['overrides']:
        fields(override, ('code', 'pack_id', 'version', 'sha256', 'reason'), '覆盖声明')
        L.require(all(L.nonempty(override[k]) for k in override), '覆盖声明字段不能为空')
        L.require(override['code'] in seen and override['code'] not in overridden, '覆盖 ID 不存在或重复')
        L.require(re.fullmatch('[0-9a-f]{64}', override['sha256']), '覆盖指纹无效')
        overridden.add(override['code'])
    return pack


def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def markdown(pack):
    validate(pack)
    lines = ['# ' + pack['title'], '', '> 由 pack.json 生成；修改 JSON 后运行 pack-render。', '',
             pack['description'], '', f"程序包：{pack['pack_id']}；版本：{pack['version']}", '']
    labels = dict(domains='审计领域', assertions='相关报表认定', applicability='适用条件', authority_types='可能涉及的依据类型',
                  materials='所需材料', steps='执行步骤', anomaly_conditions='异常条件', exceptions='常见合理解释与例外',
                  decision_authority='决策主体与权限', unable_to_execute='无法执行时')
    for item in pack['checks']:
        lines += ['## ' + item['code'] + ' ' + item['title'], '']
        for key, label in labels.items():
            value = item[key]
            lines += ['### ' + label, '']
            lines += ([f'{i}. {v}' for i, v in enumerate(value, 1)] if isinstance(value, list) else [value]) or ['不涉及']
            lines += ['']
        lines += ['### 工具支持', '']
        for t in item['tools']:
            lines += [f"- {t['description']}：{t['status']}" + (f"（{t['command']}）" if t['command'] else '')]
        lines += ['']
    if pack.get('notes'): lines += ['## 内容转换说明', '', *('- ' + x for x in pack['notes']), '']
    return '\n'.join(lines)


def privacy_candidates(pack):
    """Heuristic review list, not named-entity recognition or a privacy guarantee."""
    text = json.dumps(pack, ensure_ascii=False)
    patterns = [r'[\u4e00-\u9fff]{2,20}(?:有限公司|集团公司)', r'[\u4e00-\u9fff]{1,8}[〔\[]\d{4}[〕\]]\s*\d+号',
                r'(?:姓名|联系人|法定代表人)\s*[:：]\s*[\u4e00-\u9fff]{2,4}']
    return sorted({m.group() for p in patterns for m in re.finditer(p, text)})


def resolve(snapshots):
    result, overrides, packs, replaced = {}, [], set(), set()
    for snap in snapshots:
        pack = validate(snap['data']); sha = L.checksum(pack)
        L.require(snap['pack_sha256'] == sha, '程序包快照指纹不符')
        L.require(pack['pack_id'] not in packs, '重复程序包 ID：' + pack['pack_id'])
        packs.add(pack['pack_id'])
        declarations = {o['code']: o for o in pack['overrides']}
        for item in pack['checks']:
            code = item['code']; old = result.get(code); declared = declarations.get(code)
            if old:
                L.require(declared and code not in replaced, '检查项 ID 冲突，须显式且唯一覆盖：' + code)
                L.require(all(declared[k] == old[k] for k in ('pack_id', 'version', 'sha256')), '覆盖声明未指向实际原包版本及指纹')
                overrides.append(dict(declared, replacement_pack_id=pack['pack_id'], replacement_sha256=sha))
                replaced.add(code)
            else:
                L.require(not declared, '覆盖声明指向不存在的检查项：' + code)
            result[code] = dict(item=item, pack_id=pack['pack_id'], version=pack['version'], sha256=sha, snapshot_id=snap['id'])
    return result, overrides


def snapshots(work, ids=None):
    ids = work['run'].get('pack_snapshot_ids', []) if ids is None else ids
    L.require(isinstance(ids, list) and len(ids) == len(set(ids)), '程序包快照 ID 列表无效')
    rows = [work['records'].get(i, {}) for i in ids]
    L.require(all(r.get('kind') == 'PackSnapshot' for r in rows), '程序包快照引用无效')
    return rows


def install(project, work, paths, request_path):
    L.require(isinstance(paths, list) and all(L.nonempty(x) for x in paths), 'packs 必须为路径列表')
    candidates = [COMMON] + [(Path(request_path).resolve().parent / Path(p).expanduser()).resolve() for p in paths]
    rows, contents = [], []
    for path in candidates:
        raw = path.read_bytes(); data = validate(json.loads(raw.decode('utf-8')))
        contents.append(raw)
        digest = hashlib.sha256(raw).hexdigest()
        old = next((r for r in work['records'].values() if r['kind'] == 'PackSnapshot' and r['sha256'] == digest), None)
        row = old or dict(id=L.uid(), kind='PackSnapshot', data=data, pack_sha256=L.checksum(data), sha256=digest,
                         path='packs/' + digest + '/pack.json', acquired_at=L.now())
        rows.append(row)
    resolve(rows)  # Reject collisions before creating snapshots.
    for raw, row in zip(contents, rows):
        if row['id'] not in work['records']:
            target=project/row['path']
            L.require(target.resolve().is_relative_to(project.resolve()) and not target.is_symlink(), '程序包快照路径越界')
            atomic_bytes(target, raw)
            work['records'][row['id']] = row
    work['run']['pack_snapshot_ids'] = [r['id'] for r in rows]


def command(args, api):
    pack = load(args.pack)
    if args.command == 'pack-render':
        data = markdown(pack).encode('utf-8')
        if args.check:
            L.require(args.out.is_file() and args.out.read_bytes() == data, '生成 Markdown 与 JSON 不一致')
        else: atomic_bytes(args.out, data)
    return dict(state='validated', checks=len(pack['checks']), pack_sha256=L.checksum(pack), privacy_candidates=privacy_candidates(pack))
