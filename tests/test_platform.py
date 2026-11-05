"""Stage-1 deterministic regressions; real optional tool tests explicitly skip."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import test_public as public

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'evidence-reviewer/scripts'
sys.path.insert(0, str(SCRIPTS))
from core import converters
from core import history
from core import ledger as L
from core import locking
from core import persistence
from core import prepare
from core import readers
import review
from core import updates


class PlatformCLI(unittest.TestCase):
    # Reuse helpers, not the existing test methods (no duplicate test counts).
    for name in ('setUp', 'tearDown', 'json_file', 'call', 'begin', 'find', 'evidence', 'simple_assessment', 'finalize'):
        locals()[name] = public.PublicCLI.__dict__[name]

    def test_new_fixture_freeze(self):
        manifest = json.loads((ROOT/'tests/input-sha256-stage1.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['frozen_on'], '2026-11-04')
        for rel, sha in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(), sha)

    def test_unicode_spaces_long_paths_and_move_complete_chain(self):
        deep = self.sources
        for i in range(12):
            deep = deep / ('材料 空格-' + str(i) + '-' + 'x'*16)
        try:
            deep.mkdir(parents=True)
            source = deep/'中文 金额.txt'
            source.write_text('Synthetic amount: 12.30', encoding='utf-8')
        except OSError as exc:
            if os.name == 'nt':
                self.skipTest('Windows long-path OS support unavailable: ' + str(exc))
            raise
        packet = self.begin()
        assessment = self.simple_assessment(self.find(packet, '中文 金额.txt'))
        self.finalize(assessment)
        before = (self.project/'ledger/ledger.json').read_bytes()
        shutil.move(str(self.project), str(self.base/'迁移 后的项目'))
        self.project = self.base/'迁移 后的项目'
        self.assertEqual(self.call('validate')['outputs'], 'verified')
        self.call('export')
        self.assertEqual((self.project/'ledger/ledger.json').read_bytes(), before)
        self.assert_links_resolve(self.project)
        # Empty update after relocation also commits successfully and retains history.
        request=self.json_file('update.json',dict(event_id='move-check',reason='Synthetic relocation check'))
        self.call('update','--request',request)
        self.finalize(assessment)
        self.call('export')
        self.assertEqual(self.call('validate')['outputs'],'verified')
        self.assert_links_resolve(self.project)

    def assert_links_resolve(self, project):
        count=0
        for md in (project/'outputs').rglob('*.md'):
            for target in re.findall(r'\]\(<([^<>]+)>\)',md.read_text(encoding='utf-8')):
                target, _, fragment=unquote(target).partition('#')
                self.assertFalse(Path(target).is_absolute(),target)
                self.assertNotIn('\\',target)
                resolved=(md.parent/target).resolve()
                self.assertTrue(resolved.is_file(),target)
                if fragment:self.assertIn('id="'+fragment+'"',resolved.read_text(encoding='utf-8'))
                count+=1
        self.assertGreater(count,0)

    def test_legacy_renderers_validate_without_export_and_explicit_portable(self):
        fixtures=json.loads((ROOT/'tests/platform-fixtures/legacy.json').read_text(encoding='utf-8'))
        for i, fixture in enumerate(fixtures):
            with self.subTest(renderer=fixture['renderer'],schema=fixture['ledger']['schema_version']):
                self.project=self.base/('old-'+str(i)); self.project.mkdir()
                for rel,text in {**fixture['files'],fixture['source_path']:fixture['source_text']}.items():
                    path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode('utf-8'))
                L.atomic_json(self.project/'ledger/ledger.json',fixture['ledger'])
                L.atomic_json(self.project/'outputs/current.json',fixture['pointer'])
                def authority():
                    return {rel:(self.project/rel).read_bytes() for rel in list(fixture['files'])+['ledger/ledger.json','outputs/current.json']}
                before=authority()
                self.call('validate')
                self.assertEqual(authority(),before)
                self.assertFalse(list((self.project/'outputs').glob('portable-*')))
                self.call('export')
                self.assertEqual(authority(),before)
                self.assertFalse(list((self.project/'outputs').glob('portable-*')))
                result=self.call('export','--portable')
                self.assertEqual(authority(),before)
                directory=Path(result['portable_directory'])
                self.assertTrue((directory/'manifest.json').is_file())
                for md in directory.rglob('*.md'):
                    for target in re.findall(r'\]\(<([^<>]+)>\)',md.read_text(encoding='utf-8')):
                        self.assertTrue((md.parent/unquote(target)).resolve().is_file(),target)
                self.call('validate')

    def test_matching_uses_original_hash_even_if_converter_changes(self):
        original=self.sources/'legacy.doc'; original.write_bytes(b'Synthetic original bytes; no actual DOC conversion in this unit test')
        def extracted(label):
            return dict(reader_version='synthetic-'+label,units=[readers.unit({'unit':'block'},'Synthetic amount 17.00')],processing=[dict(method=label,sha256=hashlib.sha256(label.encode()).hexdigest())])
        request=self.json_file('begin.json',dict(goal='Synthetic converter identity',modes=['query'],source_roots=[str(self.sources)]))
        with patch.object(readers,'read',return_value=extracted('converter-A')):
            review.begin(type('Args',(),dict(project=self.project,request=request))())
        packet=self.call('inspect'); src=self.find(packet,'legacy.doc'); self.finalize(self.simple_assessment(src))
        new_batch=self.base/'new-batch';new_batch.mkdir();shutil.copyfile(original,new_batch/'renamed.doc')
        request=self.json_file('update.json',dict(event_id='other-platform',reason='Same original from another converter environment',source_roots=[str(new_batch)]))
        with patch.object(readers,'read',return_value=extracted('converter-B')) as converter:
            updates.start(type('Args',(),dict(project=self.project,request=request))(),review)
            converter.assert_not_called()
        after=self.call('inspect')
        self.assertEqual(len(after['sources']),1)
        self.assertEqual(after['sources'][0]['version']['id'],src['version']['id'])
        self.assertEqual(after['run']['changed_version_ids'],[])
        self.assertTrue(all(c['type'] in {'path_moved','path_added','unchanged'} for c in after['run']['changes']))

    def test_windows_invalid_names_record_failed_and_continue(self):
        # On Windows create real device-like names using the extended namespace.
        names=['CON','NUL.txt','COM1.doc','LPT9.xls','trailing.','trailing ']
        for name in names:
            path=self.sources/name
            if os.name=='nt': path=Path('\\\\?\\'+str(path))
            path.write_bytes(b'Synthetic invalid-name input')
        (self.sources/'valid.txt').write_text('Synthetic readable input',encoding='utf-8')
        request=self.json_file('invalid.json',dict(goal='Synthetic invalid filenames',modes=['query'],source_roots=[str(self.sources)],main_document='NUL.txt'))
        with patch.object(prepare,'WINDOWS',True):
            result=review.begin(type('Args',(),dict(project=self.project,request=request))())
        self.assertEqual(result['state'],'staging')
        packet=self.call('inspect')
        self.assertEqual([s['source']['actual_name'] for s in packet['sources']],['valid.txt'])
        self.assertIsNone(packet['project']['selected_main_version'])
        self.assertIn('failed acquisition',packet['project']['main_selection_reason'])
        failed=packet['run']['errors']; self.assertEqual(len(failed),len(names))
        self.assertTrue(all(f['state']=='failed' for f in failed))
        self.assertEqual({f['path'] for f in failed},set(names))
        self.finalize(self.simple_assessment(packet['sources'][0]))
        self.assertEqual(len(self.call('validate')['reading_issues']),len(names))
        if os.name=='nt':
            for name in names: Path('\\\\?\\'+str(self.sources/name)).unlink()

    def test_interrupted_commit_recover_and_pointer_rebuild(self):
        (self.sources/'text.txt').write_text('Synthetic original',encoding='utf-8')
        source=self.find(self.begin(),'text.txt'); a=self.simple_assessment(source)
        path=self.json_file('assessment.json',a)
        with patch.dict(os.environ,{'EVIDENCE_REVIEWER_FAILPOINT':'before_replace'}):
            result=subprocess.run([sys.executable,'-B',str(public.CLI),'finalize','--project',str(self.project),'--assessment',str(path)],capture_output=True)
        self.assertEqual(result.returncode,86)
        self.assertFalse((self.project/'ledger/ledger.json').exists())
        recovered=self.call('recover');self.assertEqual(recovered['state'],'completed')
        (self.project/'outputs/current.json').unlink()
        self.call('export');self.call('validate')


class LocalMechanics(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='platform-mechanics-');self.base=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_kernel_lock_contention_timeout_and_crash_release(self):
        code="import sys,time;sys.path.insert(0,sys.argv[1]);from core.locking import lock;from pathlib import Path\nwith lock(Path(sys.argv[2])):\n print('locked',flush=True)\n time.sleep(30)\n"
        p=subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS),str(self.base)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        try:
            self.assertEqual(p.stdout.readline().strip(),'locked')
            # Metadata readable while the system byte lock is held.
            data=json.loads((self.base/'.writer.lock.json').read_text(encoding='utf-8'))
            self.assertEqual(data['pid'],p.pid)
            self.assertEqual((self.base/'.writer.lock').stat().st_size,0)
            with self.assertRaisesRegex(ValueError,'timeout'):
                with locking.lock(self.base,timeout=0.12,interval=0.02): self.fail('Concurrent writer entered')
            p.kill();p.wait(timeout=5)
            with self.assertWarnsRegex(RuntimeWarning,'residual'):
                with locking.lock(self.base,timeout=1): pass
            self.assertEqual(json.loads((self.base/'.writer.lock.json').read_text())['state'],'released')
            with self.assertRaisesRegex(RuntimeError,'synthetic'):
                with locking.lock(self.base): raise RuntimeError('synthetic')
            with locking.lock(self.base,timeout=0): pass
            self.assertEqual((self.base/'.writer.lock').read_bytes(),b'')
        finally:
            if p.poll() is None: p.kill();p.wait(timeout=5)
            p.stdout.close();p.stderr.close()

    def test_replace_retry_bound_and_preserves_old_authority(self):
        target=self.base/'file';target.write_bytes(b'old');source=self.base/'new';source.write_bytes(b'new')
        occupied=PermissionError('synthetic sharing violation');occupied.winerror=32
        real=persistence.os.replace
        with patch.object(persistence.os,'name','nt'),patch.object(persistence.os,'replace',side_effect=[occupied,occupied,None]) as operation,patch.object(persistence.time,'sleep'):
            persistence.replace(source,target)
            self.assertEqual(operation.call_count,3)
        with patch.object(persistence.os,'name','nt'),patch.object(persistence.os,'replace',side_effect=occupied) as operation,patch.object(persistence.time,'sleep'):
            with self.assertRaisesRegex(OSError,'6 attempt'):
                persistence.replace(source,target)
            self.assertEqual(operation.call_count,6)
        self.assertEqual(target.read_bytes(),b'old')
        self.assertEqual(source.read_bytes(),b'new')
        real(source,target);self.assertEqual(target.read_bytes(),b'new')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows sharing test; not applicable on POSIX')
    def test_real_windows_sharing_violation_eventually_replaces(self):
        target=self.base/'occupied.txt'; target.write_bytes(b'old')
        code="import sys,time;f=open(sys.argv[1],'rb');print('open',flush=True);time.sleep(0.3);f.close()"
        proc=subprocess.Popen([sys.executable,'-c',code,str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(),'open')
            persistence.atomic_bytes(target,b'new')
            self.assertEqual(target.read_bytes(),b'new')
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None: proc.kill();proc.wait(timeout=5)
            proc.stdout.close();proc.stderr.close()

    def test_directory_sync_skip_is_windows_only(self):
        with patch.object(persistence.os,'name','nt'),patch.object(persistence.os,'open') as opening:
            self.assertFalse(persistence.sync_directory(self.base));opening.assert_not_called()
        if os.name!='nt': self.assertTrue(persistence.sync_directory(self.base))

    def test_converter_timeout_terminates_process(self):
        started=time.monotonic()
        with self.assertRaises(TimeoutError):
            converters.run_tool([sys.executable,'-c','import time; time.sleep(30)'],timeout=0.15)
        self.assertLess(time.monotonic()-started,15)

    def test_conversion_provenance_fallback_profile_cleanup(self):
        original=self.base/'中文 合同.doc';original.write_bytes(b'Synthetic document')
        cache=self.base/'cache';cache.mkdir();records=[];profiles=[]
        def run(argv,timeout):
            if argv[-1] in {'--version','-help'}: return ('Synthetic converter 1.0','')
            if '-convert' in argv: raise RuntimeError('synthetic textutil failure')
            profiles.append(Path(unquote(argv[1].split('=',1)[1].removeprefix('file://'))))
            folder=Path(argv[argv.index('--outdir')+1]); (folder/'input.docx').write_bytes(b'Synthetic converted bytes')
            return ('converted','')
        with patch.object(converters,'PLATFORM','darwin'),patch.object(converters.shutil,'which',return_value=sys.executable),patch.object(converters,'run_tool',side_effect=run):
            converters.convert(original,cache,'docx',records)
        self.assertEqual([r['state'] for r in records],['failed','converted'])
        self.assertEqual(records[-1]['parent_sha256'],readers.digest(original))
        self.assertTrue(records[-1]['sha256']);self.assertTrue(records[-1]['version']);self.assertTrue(records[-1]['parameters'])
        self.assertTrue(all(not p.parent.exists() for p in profiles))
        records=[]
        with patch.object(converters,'PLATFORM','linux'),patch.object(converters,'soffice_path',return_value=sys.executable),patch.object(converters,'run_tool',side_effect=[('Synthetic 1.0',''),TimeoutError('synthetic timeout')]):
            with self.assertRaises(ValueError): converters.convert(original,cache,'docx',records)
        self.assertEqual(records[0]['state'],'failed')
        uri=records[0]['parameters'][0].split('=',1)[1]
        self.assertFalse(Path(unquote(uri.removeprefix('file://'))).parent.exists())
        records=[]
        with patch.object(converters,'PLATFORM','linux'),patch.object(converters,'soffice_path',return_value=None):
            with self.assertRaises(ValueError): converters.convert(original,cache,'docx',records)
        self.assertEqual(records[0]['state'],'tool_unavailable')

    def test_soffice_environment_override_and_missing_reader_continue(self):
        with patch.dict(os.environ,{'EVIDENCE_REVIEWER_SOFFICE':sys.executable}):
            self.assertEqual(Path(converters.soffice_path()).resolve(),Path(sys.executable).resolve())
        bad=self.base/'bad.xls';bad.write_bytes(b'Synthetic unreadable legacy workbook')
        with patch.object(converters,'soffice_path',return_value=None):
            failed=readers.read(bad,self.base/'cache')
        self.assertEqual(failed['units'][0]['state'],'failed')
        good=self.base/'good.txt';good.write_text('Synthetic remaining material',encoding='utf-8')
        self.assertEqual(readers.read(good,self.base/'cache-good')['units'][0]['state'],'extracted')

    @unittest.skipUnless(shutil.which('pdftoppm') and importlib.util.find_spec('pypdf'),'Poppler/pypdf unavailable: real PDF rendering not tested')
    def test_real_poppler_render_remains_unviewed(self):
        project=self.base/'project';sources=self.base/'sources';sources.mkdir()
        shutil.copyfile(ROOT/'tests/cases/contract/sources/合同及补充页.pdf',sources/'mixed.pdf')
        request=self.base/'request.json';request.write_text(json.dumps(dict(goal='Synthetic render test',modes=['query'],source_roots=[str(sources)])))
        review.begin(type('Args',(),dict(project=project,request=request))())
        w=review.get_work(project);vid=next(iter(w['units']))
        result=review.render_source(type('Args',(),dict(project=project,version=vid,pages=[2]))())
        self.assertFalse(result['viewed']);self.assertTrue(result['artifacts'])
        self.assertFalse(any(r.get('state')=='viewed' for r in review.get_work(project)['records'].values()))

    @unittest.skipUnless(converters.soffice_path() and importlib.util.find_spec('openpyxl'),'LibreOffice/openpyxl unavailable: real DOC/XLS round trip not tested')
    def test_real_libreoffice_doc_and_xls_conversion(self):
        # Generate binary legacy files from synthetic RTF and shipped synthetic XLSX.
        with tempfile.TemporaryDirectory(prefix='legacy-tools-') as tmp:
            tmp=Path(tmp).resolve(); rtf=tmp/'input.rtf';rtf.write_text(r'{\rtf1\ansi Synthetic amount 123.45}',encoding='ascii')
            exe=converters.soffice_path()
            for source,target in [(rtf,'doc'),(ROOT/'tests/cases/financial/sources/权益桥接.xlsx','xls')]:
                out=tmp/target;out.mkdir()
                converters.run_tool([exe,'-env:UserInstallation='+(tmp/('profile-'+target)).as_uri(),'--headless','--convert-to',target,'--outdir',str(out),str(source)],timeout=60)
                legacy=out/(source.stem+'.'+target);self.assertTrue(legacy.is_file())
                packet=readers.read(legacy,self.base/target)
                self.assertFalse(any(u['state']=='failed' for u in packet['units']),packet)
                self.assertTrue(any(r.get('state')=='converted' for r in packet['processing']))
                self.assertTrue(any('123.45' in u['text'] for u in packet['units']) if target=='doc' else any(u.get('formula') for u in packet['units']))


if __name__=='__main__': unittest.main(verbosity=2)
