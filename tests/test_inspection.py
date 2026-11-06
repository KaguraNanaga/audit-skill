"""Bounded views, complete provenance, legacy bytes and recovery regressions."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import unittest
from urllib.parse import unquote

import test_public as public
from generate_usability_fixtures import generate
sys.path.insert(0, str(public.ROOT / 'evidence-reviewer/scripts'))
import review
from core import ledger as L
from core import reporting_v10


class Inspection(unittest.TestCase):
    for name in ('setUp','tearDown','json_file','call','begin','find','evidence','simple_assessment','finalize'):
        locals()[name] = public.PublicCLI.__dict__[name]

    def seed(self):
        for i in range(7):
            (self.sources / f'中文 文件 {i}.txt').write_text(('line α🙂 %s\n' % i) * 4, encoding='utf-8')
        return self.begin()

    def test_streamed_canonical_bytes_hashes_and_failed_write_preserve_authority(self):
        from core.persistence import atomic_chunks
        value={'中文': ['🙂\n"\\',None,True,1.25,-0.0]*20000,'nested':{'b':2,'a':1}}
        expected=L.encoded(value)
        self.assertEqual(b''.join(L.encoded_chunks(value)),expected)
        self.assertEqual(L.checksum(value),hashlib.sha256(expected).hexdigest())
        path=self.base/'authority.json';L.atomic_json(path,value);self.assertEqual(path.read_bytes(),expected)
        def failing():
            yield b'new incomplete'
            raise RuntimeError('synthetic serialization failure')
        with self.assertRaises(RuntimeError):atomic_chunks(path,failing())
        self.assertEqual(path.read_bytes(),expected)
        self.assertFalse(list(self.base.glob('.write-*.tmp')))

    def test_catalog_pagination_matches_full_inspect_without_mutation(self):
        packet = self.seed(); path = self.project/'staging/working.json'; before = path.read_bytes()
        ids = []; offset = 0; snapshot = None
        while True:
            args = ['--summary', '--limit', '2', '--offset', str(offset)]
            if snapshot: args += ['--snapshot', snapshot]
            part = self.call('inspect', *args); snapshot = part['snapshot']
            self.assertLess(len(json.dumps(part)), 8000)
            ids += [s['source_version_id'] for s in part['sources']]
            if part['next_offset'] is None: break
            offset = part['next_offset']
        self.assertEqual(ids, [s['version']['id'] for s in packet['sources']])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(before, path.read_bytes())
        self.call('inspect','--limit','2',success=False)
        self.call('inspect','--summary','--records',success=False)
        self.call('inspect','--summary','--offset','999',success=False)
        self.call('inspect','--summary','--limit','101',success=False)
        self.call('inspect','--summary','--snapshot','wrong',success=False)

    def test_long_unicode_unit_fragments_reconstruct_exactly_and_end_cursor(self):
        body = '中文🙂 α\\\"' * 3000 + ' END_MARKER\nnext line'
        (self.sources/'long.txt').write_text(body,encoding='utf-8')
        src = self.begin()['sources'][0]; vid=src['version']['id']; original=[u['text'] for u in src['units']]
        path=self.project/'staging/working.json'; before=path.read_bytes()
        offset=text_offset=0; parts={}; snapshot=None
        while True:
            args=['--version',vid,'--chars','512','--limit','2','--offset',str(offset),'--text-offset',str(text_offset)]
            if snapshot:args+=['--snapshot',snapshot]
            page=self.call('read',*args)
            self.assertLessEqual(sum(len(u['text']) for u in page['units']),512)
            self.assertLess(len(json.dumps(page,ensure_ascii=False).encode()),12000)
            for u in page['units']:parts.setdefault(u['unit_id'],[]).append(u['text'])
            if page['next'] is None:break
            cursor=page['next'];offset=cursor['offset'];text_offset=cursor['text_offset'];snapshot=cursor['snapshot']
        self.assertEqual([''.join(parts[u['id']]) for u in src['units']],original)
        end=self.call('read','--version',vid,'--offset',len(src['units']))
        self.assertEqual(end['units'],[]);self.assertIsNone(end['next'])
        self.call('read','--version',vid,'--text-offset','9999999',success=False)
        self.call('read','--version',vid,'--unit','unknown',success=False)
        self.assertEqual(before,path.read_bytes())

    def test_read_snapshot_rejects_changed_scope_and_metadata_is_explicitly_truncated(self):
        src=self.seed()['sources'][0];vid=src['version']['id']
        page=self.call('read','--version',vid)
        work=review.get_work(self.project);u=copy.deepcopy(work['units'][vid][0]);u['id']=L.uid()
        work['units'][vid].append(u);review.save_work(self.project,work)
        self.call('read','--version',vid,'--snapshot',page['snapshot'],success=False)
        work['units'][vid].pop();work['units'][vid][0]['limitations']=['巨量元数据'*5000];review.save_work(self.project,work)
        result=self.call('read','--version',vid,'--limit','1')
        self.assertTrue(result['units'][0]['limitations']['truncated'])
        self.assertGreater(result['units'][0]['limitations']['total_chars'],1000)
        self.assertLess(len(json.dumps(result)),20000)

    def test_bounded_search_preserves_full_record_and_saved_cursor(self):
        (self.sources/'matches.txt').write_text(('x'*900+' TARGET 中文🙂\n')*31,encoding='utf-8')
        self.begin()
        hit=self.call('search','--pattern','TARGET','--purpose','Synthetic pagination','--limit','3')
        self.assertEqual((hit['matches'],hit['returned'],hit['remaining']),(31,3,28))
        self.assertIn('TARGET',hit['results'][0]['text']);self.assertGreater(hit['results'][0]['text_start'],0)
        work=review.get_work(self.project);record=work['records'][hit['search_record_id']]
        self.assertEqual(len(record['results']),31);self.assertTrue(record['results'][0]['text'].startswith('x'*900))
        before=(self.project/'staging/working.json').read_bytes();offset=0;ids=[]
        while True:
            part=self.call('search-results','--search-id',hit['search_record_id'],'--offset',offset,'--limit',7)
            ids += [r['unit_id'] for r in part['results']]
            if part['next_offset'] is None:break
            offset=part['next_offset']
        self.assertEqual(ids,[r['unit_id'] for r in record['results']]);self.assertEqual(len(ids),len(set(ids)))
        scope=self.call('search-results','--search-id',hit['search_record_id'],'--section','scope')
        self.assertEqual(scope['total'],1)
        unread=self.call('search-results','--search-id',hit['search_record_id'],'--section','unread_parts')
        self.assertEqual(unread['total'],0);self.assertIsNone(unread['next_offset'])
        self.call('search','--pattern','TARGET','--purpose','invalid','--limit','0',success=False)
        self.assertEqual(before,(self.project/'staging/working.json').read_bytes())

    def test_read_as_of_and_committed_do_not_leak_later_units(self):
        src=self.seed()['sources'][0];first=self.finalize(self.simple_assessment(src))
        vid=src['version']['id'];before=self.call('read','--version',vid,'--run',first['run_id'])
        request=self.json_file('update.json',dict(event_id='cursor-run',reason='Synthetic continuation'))
        self.call('update','--request',request)
        current=self.call('read','--version',vid)
        self.assertNotEqual(current['run_id'],first['run_id'])
        self.assertEqual(self.call('read','--version',vid,'--committed')['units'],before['units'])
        self.assertEqual(self.call('read','--version',vid,'--run',first['run_id'])['units'],before['units'])

    def test_new_export_rebuild_complete_appendices_and_tamper_detection(self):
        packet=self.seed();self.call('search','--pattern','line','--purpose','Synthetic','--limit','1')
        result=self.finalize(self.simple_assessment(packet['sources'][0]))
        directory=self.project/'outputs'/result['run_id']
        before={p.name:p.read_bytes() for p in directory.iterdir()}
        raw=json.loads((self.project/'ledger/ledger.json').read_text(encoding='utf-8'));work=L.thaw(raw)
        self.assertEqual({r['renderer_version'] for r in work['records'].values() if r['kind']=='OutputRecord'},{11})
        self.assertEqual(sum(r.get('output_kind')=='history' for r in work['records'].values()),1)
        rows=[json.loads(line) for line in (directory/'records.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows,[r for r in work['records'].values() if r['kind']!='OutputRecord'])
        self.assertIn('Synthetic source excerpt only',(directory/'evidence.md').read_text(encoding='utf-8'))
        self.assertNotIn('Synthetic source excerpt only',(directory/'review.md').read_text(encoding='utf-8'))
        units=[json.loads(line) for line in (directory/'units.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(units,[dict(source_version_id=v,unit=u) for v,us in work['units'].items() for u in us])
        (directory/'records.jsonl').write_text('changed',encoding='utf-8');self.call('validate',success=False)
        self.call('export');self.call('validate')
        self.assertEqual(before,{p.name:p.read_bytes() for p in directory.iterdir()})
        for p in directory.glob('*.md'):
            for target in re.findall(r'\]\(<([^<>]+)>\)',p.read_text(encoding='utf-8')):
                rel, _, fragment=unquote(target).partition('#')
                resolved=(p.parent/rel).resolve()
                self.assertTrue(resolved.is_file(),target)
                if fragment:self.assertIn('id="'+fragment+'"',resolved.read_text(encoding='utf-8'))

    def test_legacy_1_to_9_validate_rebuild_and_explicit_compact_preserve_authority(self):
        fixtures=json.loads((public.ROOT/'tests/platform-fixtures/legacy.json').read_text(encoding='utf-8'))
        fixtures+=json.loads((public.ROOT/'tests/usability-fixtures/legacy-7-9.json').read_text(encoding='utf-8'))
        for n,f in enumerate(fixtures):
            with self.subTest(renderer=f['renderer']):
                self.project=self.base/f'legacy-{n}';self.project.mkdir()
                for rel,body in {**f['files'],f['source_path']:f['source_text']}.items():
                    p=self.project/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body.encode('utf-8'))
                L.atomic_json(self.project/'ledger/ledger.json',f['ledger']);L.atomic_json(self.project/'outputs/current.json',f['pointer'])
                authority={rel:(self.project/rel).read_bytes() for rel in list(f['files'])+['ledger/ledger.json','outputs/current.json']}
                self.call('validate');self.assertFalse(list((self.project/'outputs').glob('compact-*')))
                # Legacy 1-6 contain their historical absolute root; existing tests cover
                # unchanged export. Portable 7-9 must reconstruct after relocation.
                if f['renderer']>=7:
                    for rel in f['files']:(self.project/rel).unlink()
                    self.call('export')
                result=self.call('export','--compact');directory=Path(result['compact_directory'])
                self.assertEqual(result['renderer_version'],10)
                self.assertEqual(authority,{rel:(self.project/rel).read_bytes() for rel in authority})
                for md in directory.rglob('*.md'):
                    for target in re.findall(r'\]\(<([^<>]+)>\)',md.read_text(encoding='utf-8')):
                        self.assertTrue((md.parent/unquote(target).partition('#')[0]).resolve().is_file(),target)
                self.call('validate')

    def test_synthetic_large_project_and_frozen_spec_determinism(self):
        manifest=json.loads((public.ROOT/'tests/input-sha256-usability.json').read_text(encoding='utf-8'))
        for rel,sha in manifest['files'].items():self.assertEqual(hashlib.sha256((public.ROOT/rel).read_bytes()).hexdigest(),sha)
        spec=json.loads((public.ROOT/'tests/usability-fixtures/project-spec.json').read_text(encoding='utf-8'))
        self.sources.rmdir();first=generate(self.sources,spec);second=generate(self.base/'duplicate',spec);self.assertEqual(first,second)
        request=self.json_file('request.json',dict(goal='Synthetic load, not an audit opinion',modes=['query'],source_roots=[str(self.sources)]))
        self.call('begin','--request',request)
        summary=self.call('inspect','--summary','--limit','5');self.assertEqual(summary['total_sources'],98)
        self.assertLess(len(json.dumps(summary).encode()),12000)
        hit=self.call('search','--pattern','Synthetic item','--purpose','Synthetic full-scan check','--limit','2')
        self.assertEqual(hit['matches'],spec['documents']*spec['lines_per_document']);self.assertEqual(hit['returned'],2)
        work=review.get_work(self.project);vid=next(iter(work['units']));unit=work['units'][vid][0]
        assessment=dict(evidence=[dict(key='e',source_version_id=vid,unit_id=unit['id'],verbatim_quote=unit['text'],reviewer_summary='Synthetic only',reading_method='test fixture',verification_state='extracted_only',limitations=[])],answers=[dict(text='Engineering size check only',evidence_ids=['e'])])
        candidate=L.materialize(work,assessment,project=self.project);candidate['run']['finished_at']='synthetic'
        output=reporting_v10.render(candidate)
        self.assertLess(len(output['review.md'].encode()),15000)
        self.assertLess(len(output['handoff.md'].encode()),3000)
        self.assertEqual(len(output['units.jsonl'].splitlines()),sum(map(len,work['units'].values())))
        # A full search record is retained, even though its Markdown summary is small.
        saved=[json.loads(s) for s in output['records.jsonl'].splitlines() if 'SearchRecord' in s]
        self.assertEqual(len(next(r for r in saved if r['kind']=='SearchRecord')['results']),hit['matches'])

if __name__=='__main__':unittest.main(verbosity=2)
