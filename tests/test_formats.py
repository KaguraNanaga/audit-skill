"""OFD/XML/WPS contracts; simulated adapters are not actual rendering tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import test_public as public

ROOT = public.ROOT
sys.path.insert(0, str(ROOT / 'evidence-reviewer/scripts'))
import review
from core import converters, derived, ledger as L, ocr, ocr_backends, ofd_render, readers, updates
import generate_format_fixtures as generator


class Formats(unittest.TestCase):
    for name in ('setUp', 'tearDown', 'json_file', 'call', 'begin', 'find', 'evidence', 'simple_assessment', 'finalize'):
        locals()[name] = public.PublicCLI.__dict__[name]

    def source(self, name='mixed.ofd'):
        shutil.copyfile(ROOT / 'tests/format-fixtures' / name, self.sources / name)
        return self.begin()['sources'][0]

    def args(self, source, **kwargs):
        return type('Args', (), dict(project=self.project, version=source['version']['id'], pages=None, ofd_renderer=None, **kwargs))()

    def pending(self, source):
        return dict(tasks=[dict(key='pending', objective='Synthetic page review remains pending', procedure='Automated structure check only',
            population='synthetic package', sampling_basis='all pages registered', actual_scope='XML text layer', uncovered_scope='page appearance',
            execution_state='partial', result='undetermined', basis='No actual visual review in this test', next_step='Open actual page rendering',
            source_version_ids=[source['version']['id']], record_ids=[])], answers=[dict(text='Synthetic page appearance remains unverified', task_ids=['pending'])])

    def test_frozen_inputs_and_generator_determinism(self):
        frozen = json.loads((ROOT / 'tests/input-sha256-stage2.json').read_text())
        self.assertEqual(frozen['frozen_on'], '2026-11-05')
        with patch.object(generator, 'ROOT', self.base):
            generator.main()
        for rel, sha in frozen['files'].items():
            for folder in (ROOT, self.base):
                self.assertEqual(hashlib.sha256((folder / rel).read_bytes()).hexdigest(), sha, rel)

    def test_ofd_physical_pages_objects_search_and_pending_visual_review(self):
        source = self.source()
        expected = json.loads((ROOT / 'tests/expected/formats.json').read_text())
        pages = [u for u in source['units'] if u['locator']['unit'] == 'page']
        objects = [u for u in source['units'] if u['locator']['unit'] == 'block']
        self.assertEqual(len(pages), expected['ofd_pages'])
        self.assertEqual([u['state'] for u in pages], ['manual_check', 'manual_check'])
        self.assertEqual([u['text'] for u in objects], expected['ofd_text'])
        self.assertEqual([u['locator']['object_id'] for u in objects], expected['ofd_object_ids'])
        self.assertEqual(objects[0]['locator']['boundary'], '10 20 100 10')
        self.assertEqual(objects[0]['text_codes'][0]['attributes']['DeltaX'], '4 4')
        self.assertTrue(all('physical_page' in u['locator'] and 'object_path' in u['locator'] for u in objects))
        self.assertTrue(all('仅文本层' in u['limitations'][0] for u in source['units']))
        self.assertEqual(source['artifacts'], [])
        hit = self.call('search', '--pattern', '123.4500', '--purpose', 'Synthetic OFD location')
        self.assertEqual(hit['results'][0]['unit_id'], objects[0]['id'])
        self.assertEqual(len(hit['unread_parts']), 2)
        record = source['version']['processing'][0]
        self.assertEqual(record['parent_sha256'], source['version']['sha256'])
        self.assertTrue(record['version'])
        self.assertTrue(record['parameters']['text_layer_only'])
        self.finalize(self.simple_assessment(source))
        self.assertTrue(self.call('validate')['reading_issues'])
        self.call('export')

    def test_ofd_missing_or_damaged_page_continues_and_archive_references_are_local(self):
        parts = generator.ofd_parts()
        del parts['Doc_0/Pages/Page_0/Content.xml']
        path = self.base / 'missing.ofd'
        generator.package(path, parts)
        packet = readers.read(path, self.base / 'cache')
        self.assertEqual([u['state'] for u in packet['units']], ['failed', 'manual_check'])
        self.assertEqual([u['locator']['physical_page'] for u in packet['units']], [1, 2])
        for reference in ('../../outside.xml', 'https://example.invalid/content.xml'):
            parts = generator.ofd_parts()
            parts['OFD.xml'] = parts['OFD.xml'].replace('Doc_0/Document.xml', reference)
            generator.package(path, parts)
            self.assertEqual(readers.read(path, self.base / 'cache')['units'][0]['state'], 'failed')
        parts = generator.ofd_parts()
        parts['../outside.xml'] = '<bad/>'
        generator.package(path, parts)
        self.assertEqual(readers.read(path, self.base / 'cache')['units'][0]['state'], 'failed')

    def test_generic_xml_namespace_index_attributes_and_entity_rejection(self):
        source = self.source('invoice.xml')
        amounts = [u for u in source['units'] if u['locator']['element_path'].endswith('Amount[1]')]
        self.assertEqual([u['text'] for u in amounts], ['123.4500', '0.0100'])
        self.assertIn('{urn:synthetic:invoice}Line[2]', amounts[1]['locator']['element_path'])
        self.assertEqual(source['units'][0]['xml_attributes'], {'currency': 'CNY'})
        for encoding in ('utf-8', 'utf-16'):
            bad = self.base / 'entities.xml'
            bad.write_bytes('<!DOCTYPE Invoice [<!ENTITY value SYSTEM "https://example.invalid/data">]><Invoice>&value;</Invoice>'.encode(encoding))
            packet = readers.read(bad, self.base / encoding)
            self.assertEqual(packet['units'][0]['state'], 'failed')
            self.assertIn('DTD/entity', packet['units'][0]['errors'][0])
        self.finalize(self.simple_assessment(source))
        self.call('validate')

    def test_pptx_uses_declared_slide_order_and_keeps_unviewed_pages(self):
        source = self.source('slides.pptx')
        text = [u for u in source['units'] if u['text']]
        self.assertEqual([u['text'] for u in text], ['SYNTHETIC FIRST 123.45', '合成第二页'])
        self.assertEqual([u['locator']['slide'] for u in text], [1, 2])
        self.assertEqual(text[0]['locator']['part'], 'ppt/slides/slide9.xml')
        self.assertEqual([u['state'] for u in source['units'] if u['locator']['unit'] == 'page'], ['manual_check', 'manual_check'])
        self.assertEqual(source['artifacts'], [])

    def test_wps_routes_and_original_derived_fingerprints_simulated_converter(self):
        # Simulates converter output only. Does not claim proprietary WPS coverage.
        docx = self.base / 'synthetic.docx'
        generator.package(docx, {'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic text</w:t></w:r></w:p></w:body></w:document>'})
        fixtures = {'docx': docx, 'xlsx': ROOT / 'tests/table-fixtures/small.xlsx', 'pptx': ROOT / 'tests/format-fixtures/slides.pptx'}
        for suffix, target in (('.wps', 'docx'), ('.et', 'xlsx'), ('.dps', 'pptx')):
            path = self.base / ('中文 空格' + suffix)
            path.write_bytes(b'Synthetic converter input; not a proprietary WPS sample')
            cache = self.base / target
            def convert(argv, timeout):
                if argv[-1] == '--version':
                    return 'Simulated LibreOffice 1.0', ''
                self.assertEqual(argv[argv.index('--convert-to') + 1], target)
                self.assertIn('-env:UserInstallation=file:', argv[1])
                shutil.copyfile(fixtures[target], Path(argv[argv.index('--outdir') + 1]) / ('input.' + target))
                return 'simulated', ''
            with patch.object(converters, 'soffice_path', return_value=sys.executable), patch.object(converters, 'run_tool', side_effect=convert):
                result = readers.read(path, cache)
            self.assertTrue(any(u['text'] for u in result['units']))
            record = result['processing'][0]
            self.assertEqual(record['state'], 'converted')
            self.assertEqual(record['parent_sha256'], readers.digest(path))
            self.assertEqual(record['sha256'], readers.digest(fixtures[target]))
            self.assertEqual(record['version'], 'Simulated LibreOffice 1.0')
            profile = Path(url2pathname(unquote(urlparse(record['parameters'][0].split('=', 1)[1]).path)))
            self.assertFalse(profile.parent.exists())

    def test_unavailable_wps_and_bad_xml_do_not_abort_begin(self):
        for suffix in ('.wps', '.et', '.dps'):
            (self.sources / ('missing' + suffix)).write_bytes(b'Synthetic missing tool')
        (self.sources / 'bad.xml').write_text('<broken>')
        (self.sources / 'good.txt').write_text('Synthetic remaining file')
        request = self.json_file('begin.json', dict(goal='Synthetic per-file failure', modes=['query'], source_roots=[str(self.sources)]))
        with patch.object(converters, 'soffice_path', return_value=None):
            review.begin(type('Args', (), dict(project=self.project, request=request))())
        packet = self.call('inspect')
        self.assertEqual(len(packet['sources']), 5)
        for source in packet['sources']:
            self.assertEqual(source['units'][0]['state'], 'extracted' if source['source']['actual_name'] == 'good.txt' else 'failed')
            if source['version']['format'] in {'.wps', '.et', '.dps'}:
                self.assertEqual(source['version']['processing'][0]['state'], 'tool_unavailable')

    def simulated_adapter(self):
        # The copied bitmap is deliberately unrelated to OFD: adapter contract only.
        adapter = self.base / 'synthetic adapter.py'
        adapter.write_text("import sys,shutil\nfrom pathlib import Path\nif '--version' in sys.argv:\n print('Synthetic adapter simulation 1.0');raise SystemExit\nout=Path(sys.argv[sys.argv.index('--output_dir')+1])\nfor n in sys.argv[sys.argv.index('--pages')+1:]:\n shutil.copyfile(" + repr(str(ROOT / 'tests/ocr-fixtures/synthetic.png')) + ",out/('page-'+n+'.png'))\n", encoding='utf-8')
        return adapter

    def test_ofd_render_adapter_contract_exact_observations_and_ocr_lineage(self):
        source = self.source()
        args = self.args(source)
        args.ofd_renderer = str(self.simulated_adapter())
        args.pages = [1]
        result = review.render_source(args)
        self.assertEqual(result['state'], 'rendered')
        self.assertFalse(result['viewed'])
        self.assertEqual(len(result['artifacts']), 3)  # page and two exact object locators
        self.assertEqual(len({a['path'] for a in result['artifacts']}), 1)
        self.assertTrue(all(a['provenance']['parent_sha256'] == source['version']['sha256'] for a in result['artifacts']))
        self.assertFalse(any(r.get('state') == 'viewed' for r in review.get_work(self.project)['records'].values()))
        blocks = json.loads((ROOT / 'tests/ocr-fixtures/blocks.json').read_text())
        args.engine = 'tesseract'
        args.timeout = 30
        with patch.object(ocr_backends, 'describe', return_value=dict(engine='synthetic-test', version='simulation-1', parameters={'simulation': True})), patch.object(ocr_backends, 'recognize', return_value=blocks):
            self.assertEqual(ocr.run(args, review)['state'], 'completed')
        current = self.call('inspect')['sources'][0]
        unit = next(u for u in current['units'] if derived.is_ocr(u))
        self.assertEqual(unit['derived_from']['unit_id'], source['units'][0]['id'])
        self.assertEqual(unit['derived_from']['image_sha256'], result['artifacts'][0]['sha256'])
        assessment = self.simple_assessment(current)
        assessment['evidence'][0]['unit_id'] = unit['id']
        assessment['evidence'][0]['verbatim_quote'] = unit['text']
        self.assertIn('OCR-only', self.call('check-assessment', '--assessment', self.json_file('a.json', assessment), success=False)['error'])
        original_object = next(u for u in current['units'] if u['locator']['unit'] == 'block')
        assessment = self.simple_assessment(current)
        assessment['evidence'][0]['verification_state'] = 'original_viewed'
        # Observing the page or another object does not mark this exact object read.
        assessment['observations'] = [dict(read_id=current['units'][0]['read_id'], artifact_id=result['artifacts'][0]['id'], observation='Synthetic guard simulation, not actual visual review')]
        self.assertIn('view record', self.call('check-assessment', '--assessment', self.json_file('wrong.json', assessment), success=False)['error'])
        artifact = next(a for a in result['artifacts'] if a['locator'] == original_object['locator'])
        assessment['observations'] = [dict(read_id=original_object['read_id'], artifact_id=artifact['id'], observation='Synthetic guard simulation, not actual visual review')]
        self.finalize(assessment)
        self.call('validate')

    def test_ofd_missing_renderer_timeout_and_no_page_files_are_recorded(self):
        source = self.source()
        args = self.args(source)
        self.assertEqual(review.render_source(args)['state'], 'tool_unavailable')
        args.ofd_renderer = str(self.simulated_adapter())
        with patch.object(ofd_render, 'run_tool', side_effect=[('Synthetic 1.0', ''), TimeoutError('Synthetic timeout')]):
            self.assertEqual(review.render_source(args)['state'], 'failed')
        work = review.get_work(self.project)
        record = work['run']['errors'][-1]
        temporary = Path(record['parameters'][record['parameters'].index('--output_dir') + 1])
        self.assertFalse(temporary.exists())
        with patch.object(ofd_render, 'run_tool', return_value=('Synthetic 1.0', '')):
            self.assertEqual(review.render_source(args)['state'], 'failed')
        self.assertEqual(self.call('inspect')['sources'][0]['artifacts'], [])
        self.assertTrue(all(u['state'] != 'viewed' for u in self.call('inspect')['sources'][0]['units']))
        self.finalize(self.pending(source))
        self.call('validate')

    def test_original_fingerprint_controls_update_despite_different_converter_output(self):
        original = self.sources / 'synthetic.wps'
        original.write_bytes(b'Synthetic fixed original; simulated conversion')
        first = dict(reader_version=readers.VERSION, processing=[dict(converter='synthetic platform A', version='1', state='converted', sha256='a' * 64)],
                     units=[readers.unit(dict(unit='block', part='converted.xml'), 'Synthetic conversion A')])
        request = self.json_file('begin.json', dict(goal='Synthetic converter independence', modes=['query'], source_roots=[str(self.sources)]))
        def first_read(path, cache):
            cache.mkdir(parents=True)
            artifact = cache / 'converted.txt'
            artifact.write_text('Synthetic conversion artifact A')
            packet = copy.deepcopy(first)
            packet['processing'][0].update(artifact=str(artifact), sha256=readers.digest(artifact), parent_sha256=readers.digest(path))
            return packet
        with patch.object(readers, 'read', side_effect=first_read):
            review.begin(type('Args', (), dict(project=self.project, request=request))())
        source = self.call('inspect')['sources'][0]
        self.finalize(self.simple_assessment(source))
        second = copy.deepcopy(first)
        second['units'][0]['text'] = 'Synthetic different conversion B'
        second['processing'][0].update(converter='synthetic platform B', sha256='b' * 64)
        update = self.json_file('update.json', dict(event_id='other-platform', reason='Same original on another platform', source_roots=[str(self.sources)]))
        with patch.object(readers, 'read', return_value=second) as reader:
            updates.start(type('Args', (), dict(project=self.project, request=update))(), review)
            reader.assert_not_called()
        after = self.call('inspect')
        self.assertEqual(len(after['sources']), 1)
        self.assertEqual(after['sources'][0]['version']['id'], source['version']['id'])
        self.assertFalse(any(c['type'] in {'source_replaced', 'source_added', 'source_reparsed'} for c in after['run']['changes']))
        assessment = self.simple_assessment(source)
        assessment.update(screening=[], impact_review=[])
        self.finalize(assessment)
        self.call('validate')

    def test_stage4_old_unsupported_ofd_stays_unchanged_until_explicit_reparse(self):
        baseline = os.environ.get('EVIDENCE_REVIEWER_STAGE4_BASELINE')
        if not baseline:
            self.skipTest('Verified stage4 runtime unavailable: old OFD project comparison not executed')
        shutil.copyfile(ROOT / 'tests/format-fixtures/mixed.ofd', self.sources / 'mixed.ofd')
        request = self.json_file('old.json', dict(goal='Synthetic old unsupported format', modes=['query'], source_roots=[str(self.sources)]))
        def old(command, *args):
            proc = subprocess.run([sys.executable, '-B', str(Path(baseline) / 'evidence-reviewer/scripts/review.py'), command, '--project', str(self.project), *map(str, args)], capture_output=True, text=True, encoding='utf-8', check=True)
            return json.loads(proc.stdout)
        old('begin', '--request', request)
        source = old('inspect')['sources'][0]
        self.assertEqual(source['units'][0]['state'], 'unread')
        first = old('finalize', '--assessment', self.json_file('a.json', self.pending(source)))
        authority = (self.project / 'ledger/ledger.json').read_bytes()
        exports = {p: p.read_bytes() for p in (self.project / 'outputs' / first['run_id']).glob('*.md')}
        self.call('validate')
        self.assertEqual((self.project / 'ledger/ledger.json').read_bytes(), authority)
        self.assertEqual(self.call('inspect')['sources'][0]['units'], source['units'])
        self.call('export')
        self.call('update', '--request', self.json_file('u.json', dict(event_id='explicit-reparse', reason='Explicit OFD reader upgrade', source_roots=[str(self.sources)],
            source_bindings=[dict(path=str(self.sources / 'mixed.ofd'), source_id=source['source']['id'], relation='reparse', reason='Explicitly extract newly supported OFD')])) )
        packet = self.call('inspect')
        change = packet['run']['changes'][0]
        self.assertEqual(change['type'], 'source_reparsed')
        self.assertFalse(change['byte_changed'])
        self.assertTrue(change['visual_check_required'])
        new = next(s for s in packet['sources'] if s['version']['id'] == change['new_version_id'])
        assessment = self.pending(new)
        assessment.update(screening=[dict(change_id=change['id'], topics=['OFD support'], new_matters='New XML extraction only', scope_decision='targeted', basis='Same original SHA; page images unavailable', affected_ids=[], visual_check=dict(state='unavailable', basis='No actual OFD renderer in this automated structure test'))],
            impact_review=[dict(target_id=eid, decision='unaffected', basis='Prior task still reports visual review pending; text extraction does not complete it') for eid in packet['run']['impact_candidates']['candidate_ids']])
        self.finalize(assessment)
        self.call('validate')
        self.assertEqual(self.call('inspect', '--run', first['run_id'])['sources'][0]['units'], source['units'])
        for path, data in exports.items():
            self.assertEqual(path.read_bytes(), data)
        next(iter(exports)).unlink()
        self.call('export')
        for path, data in exports.items():
            self.assertEqual(path.read_bytes(), data)

    def test_actual_libreoffice_three_wps_compatible_routes(self):
        executable = converters.soffice_path()
        if not executable:
            if os.environ.get('EVIDENCE_REVIEWER_REQUIRE_OFFICE'):
                self.fail('LibreOffice required in this CI job')
            self.skipTest('LibreOffice unavailable: actual WPS-compatible routes not executed')
        # Export real MS-compatible binary files from synthetic sources, then use
        # their documented WPS suffixes. This is not native WPS producer coverage.
        rtf = self.base / 'synthetic.rtf'
        rtf.write_text(r'{\rtf1\ansi SYNTHETIC 123.45}', encoding='ascii')
        cases = [(rtf, 'doc:MS Word 97', '.wps'), (ROOT / 'tests/table-fixtures/small.xlsx', 'xls:MS Excel 97', '.et'),
                 (ROOT / 'tests/format-fixtures/slides.pptx', 'ppt:MS PowerPoint 97', '.dps')]
        for source, target, suffix in cases:
            with tempfile.TemporaryDirectory(prefix='wps-compatible-') as temporary:
                folder = Path(temporary).resolve()
                converters.run_tool([executable, '-env:UserInstallation=' + (folder / 'profile').as_uri(), '--headless', '--convert-to', target, '--outdir', str(folder), str(source)], timeout=60)
                binary = folder / (source.stem + '.' + target.split(':')[0])
                self.assertTrue(binary.is_file(), str(binary))
                original = self.base / ('中文 合成' + suffix)
                shutil.copyfile(binary, original)
                result = readers.read(original, self.base / suffix[1:])
                self.assertFalse(any(u['state'] == 'failed' for u in result['units']), result)
                self.assertTrue(any(u['text'] for u in result['units']))
                record = result['processing'][0]
                self.assertEqual(record['converter'], 'LibreOffice')
                self.assertTrue(record['version'])
                self.assertEqual(record['parent_sha256'], readers.digest(original))

    def test_actual_optional_ofd_renderer(self):
        adapter = os.environ.get('EVIDENCE_REVIEWER_OFD_RENDERER')
        if not adapter or not Path(adapter).is_file():
            self.skipTest('Actual OFD adapter unavailable: actual OFD page rendering not verified; contract simulation is separate')
        source = self.source()
        args = self.args(source)
        args.ofd_renderer = adapter
        result = review.render_source(args)
        self.assertEqual(result['state'], 'rendered', result)
        self.assertEqual(result['pages'], [1, 2])
        self.assertFalse(result['viewed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
