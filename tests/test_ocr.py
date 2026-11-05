"""OCR lineage/guard simulations are separate from real optional backend tests."""
import copy,hashlib,json,os,shutil,subprocess,sys,unittest
from pathlib import Path
from unittest.mock import patch
import test_public as public
ROOT=public.ROOT;sys.path.insert(0,str(ROOT/'evidence-reviewer/scripts'))
import review
from core import ocr,ocr_backends,ledger as L,derived,history,recovery

class OCRContract(unittest.TestCase):
    for name in ('setUp','tearDown','json_file','call','begin','find','evidence','simple_assessment','finalize'):
        locals()[name]=public.PublicCLI.__dict__[name]

    def image(self):
        shutil.copyfile(ROOT/'tests/ocr-fixtures/synthetic.png',self.sources/'image.png')
        return self.begin()['sources'][0]

    def args(self,source,**kw):
        return type('Args',(),dict(project=self.project,version=source['version']['id'],pages=None,engine='tesseract',timeout=30,**kw))()

    def simulate(self,source):
        blocks=json.loads((ROOT/'tests/ocr-fixtures/blocks.json').read_text())
        with patch.object(ocr_backends,'describe',return_value=dict(engine='synthetic-test',version='simulation-1',parameters={'simulation':True})),patch.object(ocr_backends,'recognize',return_value=blocks):
            return ocr.run(self.args(source),review)

    def pending(self,source):
        return dict(tasks=[dict(key='pending',objective='Synthetic image remains unviewed',procedure='Structural test only',population='one image',sampling_basis='all',actual_scope='registered',uncovered_scope='visual facts',execution_state='partial',result='undetermined',basis='No actual human or model visual review in this test',next_step='Open original image',source_version_ids=[source['version']['id']],record_ids=[])],answers=[dict(text='Synthetic original remains unverified',task_ids=['pending'])])

    def test_frozen_fixture(self):
        manifest=json.loads((ROOT/'tests/input-sha256-stage3.json').read_text())
        self.assertEqual(manifest['frozen_on'],'2026-11-05')
        for rel,sha in manifest['files'].items():self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),sha)

    def test_lineage_search_warning_and_original_state(self):
        source=self.image();parent=source['units'][0];self.simulate(source)
        after=self.call('inspect')['sources'][0];u=after['units'][1]
        self.assertEqual(after['units'][0],parent);self.assertTrue(derived.is_ocr(u))
        self.assertEqual(u['derived_from']['image_sha256'],source['artifacts'][0]['sha256'])
        self.assertEqual(u['derived_from']['unit_id'],parent['id'])
        hit=self.call('search','--pattern','123.45','--purpose','Synthetic OCR location')['results'][0]
        self.assertEqual(hit['warning'],derived.WARNING)
        self.assertTrue(self.call('search','--pattern','absent','--purpose','Synthetic missing')['unread_parts'])

    def test_ocr_only_check_and_finalize_rejected_then_matching_observation(self):
        source=self.image();self.simulate(source);source=self.call('inspect')['sources'][0]
        a=self.simple_assessment(source);path=self.json_file('a.json',a)
        for command in ('check-assessment','finalize'):
            self.assertIn('OCR-only',self.call(command,'--assessment',path,success=False)['error'])
        self.assertFalse((self.project/'ledger/ledger.json').exists())
        a['observations']=[dict(read_id=source['units'][1]['read_id'],artifact_id=source['artifacts'][0]['id'],observation='Structural simulation only')]
        self.assertIn('original page',self.call('check-assessment','--assessment',self.json_file('bad.json',a),success=False)['error'])
        # A synthetic observation tests reference matching; it is not a report of actual visual review.
        a['observations'][0]['read_id']=source['units'][0]['read_id']
        self.finalize(a);self.call('validate')
        text=next((self.project/'outputs').glob('*/review.md')).read_text()
        self.assertIn(derived.WARNING,text)
        before=(self.project/'ledger/ledger.json').read_bytes();self.call('export')
        self.assertEqual((self.project/'ledger/ledger.json').read_bytes(),before)
        portable=self.call('export','--portable')
        self.assertEqual(portable['renderer_version'],9)
        self.assertIn(derived.WARNING,next(Path(portable['portable_directory']).glob('*/review.md')).read_text())
        self.assertEqual((self.project/'ledger/ledger.json').read_bytes(),before)

    def test_wrong_image_hash_does_not_satisfy_observation(self):
        source=self.image();self.simulate(source);work=review.get_work(self.project)
        a=self.simple_assessment(self.call('inspect')['sources'][0]);artifact=copy.deepcopy(work['artifacts'][0]);artifact.update(id=L.uid(),path='cache/other.png')
        p=self.project/artifact['path'];p.parent.mkdir(exist_ok=True);p.write_bytes((self.sources/'image.png').read_bytes()+b'synthetic other rendition')
        artifact['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();work['artifacts'].append(artifact);review.save_work(self.project,work)
        a['observations']=[dict(read_id=source['units'][0]['read_id'],artifact_id=artifact['id'],observation='Structural wrong rendition only')]
        self.assertIn('OCR-only',self.call('check-assessment','--assessment',self.json_file('a.json',a),success=False)['error'])

    def test_unavailable_failure_and_timeout_keep_remaining_work(self):
        source=self.image()
        invalid=self.base/'not-an-image.png';invalid.write_text('https://example.invalid/image.png')
        with patch.object(ocr_backends,'run_tool') as process:
            with self.assertRaisesRegex(ValueError,'local image'):
                ocr_backends.recognize(invalid,self.base/'out.json',dict(engine='tesseract'),1)
            process.assert_not_called()
        for failure in (FileNotFoundError('synthetic backend unavailable'),TimeoutError('synthetic timeout')):
            with patch.object(ocr_backends,'describe',side_effect=failure):result=ocr.run(self.args(source),review)
            self.assertEqual(result['state'],'partial')
        work=review.get_work(self.project);self.assertEqual(len(work['units'][source['version']['id']]),1)
        self.assertEqual([r['state'] for r in work['records'].values() if r['kind']=='OCRAttempt'],['failed','failed'])
        self.finalize(self.pending(source));self.call('validate')

    def test_raw_result_and_lineage_tampering_rejected(self):
        source=self.image();self.simulate(source);work=review.get_work(self.project)
        work['units'][source['version']['id']][1]['derived_from']['image_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'mismatch'):derived.validate(work)
        work=review.get_work(self.project);attempt=next(r for r in work['records'].values() if r['kind']=='OCRAttempt')
        (self.project/attempt['raw_path']).write_text('[]')
        self.assertIn('OCR result',self.call('check-assessment','--assessment',self.json_file('a.json',self.pending(source)),success=False)['error'])

    def test_later_ocr_never_enters_old_units_exports_or_recovery_prefix(self):
        source=self.image();first=self.finalize(self.pending(source));base=json.loads((self.project/'ledger/ledger.json').read_text());rid=first['run_id']
        exports={p:p.read_bytes() for p in (self.project/'outputs'/rid).glob('*.md')}
        self.call('update','--request',self.json_file('u.json',dict(event_id='ocr-later',reason='Synthetic derived locator addition')))
        self.simulate(source);a=self.pending(source)
        a.update(screening=[],impact_review=[]);path=self.json_file('new.json',a)
        # Exercise the actual interrupted commit and ancestry recovery, not just a helper.
        proc=subprocess.run([sys.executable,'-B',str(public.CLI),'finalize','--project',str(self.project),'--assessment',str(path)],env=dict(os.environ,EVIDENCE_REVIEWER_FAILPOINT='after_replace'),capture_output=True)
        self.assertEqual(proc.returncode,86,proc.stderr)
        current=json.loads((self.project/'ledger/ledger.json').read_text());self.assertTrue(recovery.contains(current,base))
        downgraded=copy.deepcopy(current);downgraded['schema_version']='evidence-ledger-2.0'
        with self.assertRaisesRegex(ValueError,'schema 3'):
            L.thaw(history.signed(downgraded))
        self.assertEqual(recovery.reconstruct_base(current,base['integrity_sha256']),base)
        self.call('recover');self.call('validate')
        old=self.call('inspect','--run',rid);self.assertEqual(len(old['sources'][0]['units']),1)
        self.assertEqual(len(self.call('inspect')['sources'][0]['units']),2)
        for p,content in exports.items():self.assertEqual(p.read_bytes(),content)
        self.call('update','--request',self.json_file('tamper-update.json',dict(event_id='tamper-original',reason='Synthetic immutable-unit guard')))
        work=review.get_work(self.project)
        work['units'][source['version']['id']][0]['limitations'].append('synthetic forbidden historical mutation')
        # The build guard is independent of business assertions or OCR backend availability.
        with self.assertRaisesRegex(ValueError,'Historical units'):
            history.build(current,work)

    def test_existing_schema1_and2_update_adds_ocr_without_rewriting_history(self):
        fixtures=json.loads((ROOT/'tests/platform-fixtures/legacy.json').read_text())
        # Existing frozen schema 1/2 are validated in test_platform. Construct a real renderer-7
        # image project using the verified stage-1.5 runtime, then update with the current CLI.
        baseline=os.environ.get('EVIDENCE_REVIEWER_STRUCTURE_CANDIDATE')
        if not baseline:self.skipTest('Verified stage-1.5 baseline unavailable: old runtime comparison not executed')
        shutil.copyfile(ROOT/'tests/ocr-fixtures/synthetic.png',self.sources/'image.png')
        request=self.json_file('req.json',dict(goal='Synthetic legacy image',modes=['query'],source_roots=[str(self.sources)]))
        def old(command,*args):
            p=subprocess.run([sys.executable,'-B',str(Path(baseline)/'evidence-reviewer/scripts/review.py'),command,'--project',str(self.project),*map(str,args)],capture_output=True,text=True,encoding='utf-8',check=True)
            return json.loads(p.stdout)
        old('begin','--request',request);source=old('inspect')['sources'][0]
        old('finalize','--assessment',self.json_file('old.json',self.pending(source)))
        for i in range(2):
            base=json.loads((self.project/'ledger/ledger.json').read_text());self.assertEqual(base['schema_version'],'evidence-ledger-'+str(i+1)+'.0')
            before=(self.project/'ledger/ledger.json').read_bytes();self.call('validate');self.assertEqual(before,(self.project/'ledger/ledger.json').read_bytes())
            if not i:
                old('update','--request',self.json_file('old-update.json',dict(event_id='old-update',reason='Synthetic old schema2')))
                old('finalize','--assessment',self.json_file('old2.json',dict(self.pending(source),screening=[],impact_review=[])))
        self.call('update','--request',self.json_file('u.json',dict(event_id='add-ocr',reason='Explicit new-schema OCR update')))
        self.simulate(source)
        self.finalize(dict(self.pending(source),screening=[],impact_review=[]));self.call('validate')
        self.assertTrue(recovery.contains(json.loads((self.project/'ledger/ledger.json').read_text()),base))

class RealOCR(unittest.TestCase):
    def test_rapidocr_actual_local_backend(self):self.actual('rapidocr')
    def test_tesseract_actual_local_backend(self):self.actual('tesseract')
    def actual(self,engine):
        try:metadata=ocr_backends.describe(engine)
        except (FileNotFoundError,ModuleNotFoundError) as exc:
            if os.environ.get('EVIDENCE_REVIEWER_REQUIRE_OCR') in {engine,'all'}:raise
            self.skipTest(str(exc)+'; real recognition not executed')
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            blocks=ocr_backends.recognize(ROOT/'tests/ocr-fixtures/synthetic.png',Path(tmp)/'raw.json',metadata,120)
            self.assertTrue(blocks)
            for block in blocks:derived.validate_block(block)
            # Locate a stable label; numeric correctness is not this layer's contract.
            # Tesseract actually read the frozen 123.45 as 125,45 in the first CI run.
            self.assertIn('AMOUNT', ' '.join(b['text'] for b in blocks))
        case=OCRContract(methodName='test_frozen_fixture');case.setUp()
        try:
            source=case.image()
            args=case.args(source);args.engine=engine
            result=ocr.run(args,review);self.assertEqual(result['state'],'completed',result)
            hit=case.call('search','--pattern','AMOUNT','--purpose','Actual OCR locator smoke test')['results'][0]
            self.assertEqual(hit['warning'],derived.WARNING)
            source=case.call('inspect')['sources'][0]
            assessment=case.simple_assessment(source)
            error=case.call('check-assessment','--assessment',case.json_file('a.json',assessment),success=False)
            self.assertIn('OCR-only',error['error'])
        finally:case.tearDown()

if __name__=='__main__':unittest.main(verbosity=2)
