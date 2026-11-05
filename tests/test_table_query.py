"""Deterministic selection, exact decimal sums and versioned query citations."""
import copy,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,unittest
from decimal import Decimal
from pathlib import Path
import test_public as public
ROOT=public.ROOT;sys.path.insert(0,str(ROOT/'evidence-reviewer/scripts'))
import review
from core import readers,ledger as L,history,table_query as T

class Tables(unittest.TestCase):
    for name in ('setUp','tearDown','json_file','call','begin','find','evidence','simple_assessment','finalize'):
        locals()[name]=public.PublicCLI.__dict__[name]

    def source(self,extension='csv'):
        shutil.copyfile(ROOT/('tests/table-fixtures/small.'+extension),self.sources/('small.'+extension))
        return self.begin()['sources'][0]

    def query(self,source,spec,limit=2):
        return self.call('table-query','--version',source['version']['id'],'--spec',self.json_file('spec.json',spec),'--limit',str(limit))

    def records(self,result,name):
        return [json.loads(s) for s in (self.project/result['files'][name]['path']).read_text().splitlines()]

    def test_freeze_and_generator_determinism(self):
        m=json.loads((ROOT/'tests/input-sha256-stage4.json').read_text());self.assertEqual(m['frozen_on'],'2026-11-05')
        for rel,sha in m['files'].items():self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),sha)
        # Regenerate into an isolated root, never over the frozen distribution.
        import generate_table_fixtures as generator
        original=generator.ROOT
        try:
            generator.ROOT=self.base;generator.main()
            for rel,sha in m['files'].items():self.assertEqual(hashlib.sha256((self.base/rel).read_bytes()).hexdigest(),sha,rel)
        finally:generator.ROOT=original

    def test_filter_group_sum_count_and_tsv_parity(self):
        source=self.source('csv');spec=dict(filters=[dict(column='category',op='eq',value='A'),dict(column='id',op='contains',value='c'),dict(column='amount',op='number_range',min='-1',max='1'),dict(column='date',op='date_range',min='2031-01-04',max='2031-01-04')],group_by=['category'],aggregates=[dict(op='sum',column='amount',**{'as':'total'}),dict(op='count',**{'as':'n'})])
        result=self.query(source,spec);self.assertEqual(result['state'],'completed',result)
        self.assertEqual(result['summary']['matched_rows'],1)
        repeated=self.query(source,spec)
        w=review.get_work(self.project)
        self.assertEqual(w['records'][result['query_id']]['result_fingerprint'],w['records'][repeated['query_id']]['result_fingerprint'])
        self.assertEqual(result['group_preview'][0]['values'],dict(category='A',total='-0.0300',n='1'))
        row=result['preview'][0];self.assertEqual(row['locator']['record_number'],4);self.assertTrue(row['unit_ids'])
        path=self.base/'tsv-source';path.mkdir();shutil.copyfile(ROOT/'tests/table-fixtures/small.tsv',path/'small.tsv')
        other=self.base/'tsv-project';req=self.json_file('r2.json',dict(goal='Synthetic TSV',modes=['query'],source_roots=[str(path)]))
        review.begin(type('A',(),dict(project=other,request=req))());w=review.get_work(other)
        result2=T.run(type('A',(),dict(project=other,version=next(iter(w['units'])),spec=self.base/'spec.json',limit=2))(),review)
        self.assertEqual(result2['group_preview'][0]['values'],result['group_preview'][0]['values'])

    def test_50000_rows_full_scan_bounded_output_and_independent_oracle(self):
        shutil.copyfile(ROOT/'tests/table-fixtures/synthetic-ledger-50000.csv',self.sources/'ledger.csv')
        request=self.json_file('large.json',dict(goal='Synthetic large table only',modes=['query'],source_roots=[str(self.sources)]))
        self.call('begin','--request',request);work=review.get_work(self.project);vid=next(iter(work['units']))
        source=dict(version=dict(id=vid));del work
        spec=dict(filters=[dict(column='category',op='eq',value='G1'),dict(column='date',op='date_range',min='2031-01-10',max='2031-01-20'),dict(column='amount',op='number_range',min='0')],aggregates=[dict(op='sum',column='amount',**{'as':'total'}),dict(op='count',**{'as':'n'})])
        result=self.query(source,spec,limit=3);expected=json.loads((ROOT/'tests/expected/table-query.json').read_text())
        self.assertEqual(result['summary']['scanned_rows'],50000);self.assertEqual(result['summary']['matched_rows'],expected['large_matched'])
        self.assertEqual(len(result['preview']),3);self.assertLess(len(json.dumps(result)),15000)
        self.assertEqual(Decimal(result['group_preview'][0]['values']['total']),Decimal(expected['large_sum_cents'])/100)
        self.assertEqual(result['group_preview'][0]['values']['n'],str(expected['large_matched']))
        with (self.project/result['files']['rows.jsonl']['path']).open(encoding='utf-8') as stream:
            self.assertEqual(sum(1 for _ in stream),expected['large_matched'])

    @unittest.skipUnless(importlib.util.find_spec('openpyxl'),'openpyxl unavailable: real XLSX query not tested')
    def test_xlsx_raw_precision_formula_cache_failure_and_reader_equivalence(self):
        source=self.source('xlsx')
        result=self.query(source,dict(sheet='Ledger',filters=[dict(column='date',op='date_range',max='2031-01-05')],aggregates=[dict(op='sum',column='amount',**{'as':'total'})]),limit=10)
        self.assertEqual(result['state'],'completed',result)
        self.assertEqual(result['preview'][3]['values']['amount'],'12345678901234567890.1234567890')
        self.assertEqual(result['group_preview'][0]['values']['total'],'12345678901234567893.3234567890')
        bad=self.query(source,dict(sheet='Ledger',aggregates=[dict(op='sum',column='amount',**{'as':'total'})]))
        self.assertEqual(bad['state'],'failed');self.assertIn('decimal string',bad['errors'][0])
        baseline=os.environ.get('EVIDENCE_REVIEWER_STAGE3_BASELINE')
        if not baseline:self.skipTest('Stage3 baseline unavailable: old/new XLSX reader comparison not executed')
        # Direct readers return no random IDs; require all existing unit fields to match.
        code="import sys,json,tempfile;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from core.readers import xlsx;print(json.dumps(xlsx(Path(sys.argv[2]),Path(tempfile.gettempdir())),sort_keys=True))"
        old=subprocess.run([sys.executable,'-B','-c',code,str(Path(baseline)/'evidence-reviewer/scripts'),str(ROOT/'tests/table-fixtures/small.xlsx')],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(old.stdout),readers.xlsx(ROOT/'tests/table-fixtures/small.xlsx',self.base))

    @unittest.skipUnless(importlib.util.find_spec('openpyxl'),'openpyxl unavailable: native XLSX dates not tested')
    def test_xlsx_native_datetime_filters_by_calendar_date_and_retains_time(self):
        from datetime import datetime
        import openpyxl
        wb=openpyxl.Workbook();ws=wb.active;ws.append(['id','date','amount']);ws.append(['a',datetime(2031,1,2,15,30),'1.2300'])
        wb.save(self.sources/'dates.xlsx');wb.close()
        source=self.begin()['sources'][0]
        result=self.query(source,dict(sheet='Sheet',filters=[dict(column='date',op='date_range',min='2031-01-02',max='2031-01-02')]))
        self.assertEqual(result['state'],'completed',result);self.assertEqual(result['summary']['matched_rows'],1)
        self.assertEqual(result['preview'][0]['values']['date'],'2031-01-02T15:30:00')

    def assessment(self,result):
        ref=dict(query_id=result['query_id'],result_locator=dict(kind='group',index=1,field='total'))
        return dict(evidence=[dict(key='e',**ref,verbatim_quote='3.2000',reviewer_summary='Synthetic arithmetic only',reading_method='saved table query',verification_state='extracted_only',limitations=[])],
            calculations=[dict(key='c',purpose='Synthetic query result reuse',inputs=[dict(name='a',value='3.2000',raw_value='3.2000',**ref,unit='元',currency='CNY',period='synthetic',tax_basis='unspecified',normalization='exact query sum')],formula='a',rounding=dict(places=4,mode='ROUND_HALF_UP'),unit='元',currency='CNY',result_kind='recalculation',assumptions=[],limitations=[])],answers=[dict(text='Synthetic query result, no audit conclusion',evidence_ids=['e'],calculation_ids=['c'])])

    def simple_query(self):
        source=self.source();result=self.query(source,dict(filters=[dict(column='date',op='date_range',max='2031-01-04')],aggregates=[dict(op='sum',column='amount',**{'as':'total'})]));return source,result

    def test_query_evidence_calculation_finalize_move_export_and_tampering(self):
        source,result=self.simple_query();a=self.assessment(result)
        self.finalize(a);self.assertTrue(self.call('validate')['structure_valid'])
        packet=self.call('inspect');derived=[u for u in packet['sources'][0]['units'] if u['locator'].get('unit')=='table_query_derived'];self.assertEqual(len(derived),1)
        portable=self.call('export','--portable');self.assertEqual(portable['renderer_version'],9)
        before=(self.project/'ledger/ledger.json').read_bytes();shutil.move(str(self.project),str(self.base/'moved project'));self.project=self.base/'moved project'
        self.call('validate');self.call('export');self.assertEqual((self.project/'ledger/ledger.json').read_bytes(),before)
        review_text=next((self.project/'outputs').glob('*/review.md')).read_text();self.assertIn(T.WARNING,review_text)
        groups=self.project/result['files']['groups.jsonl']['path'];groups.write_text('tampered')
        self.assertIn('Query result',self.call('validate',success=False)['error'])

    def test_invalid_query_reference_wrong_amount_and_original_viewed_are_rejected(self):
        source,result=self.simple_query();a=self.assessment(result)
        for change in ('wrong_amount','wrong_field','viewed'):
            bad=copy.deepcopy(a)
            if change=='wrong_amount':bad['calculations'][0]['inputs'][0]['value']='3.21'
            elif change=='wrong_field':bad['evidence'][0]['result_locator']['field']='absent'
            else:bad['evidence'][0]['verification_state']='original_viewed'
            self.call('check-assessment','--assessment',self.json_file(change+'.json',bad),success=False)

    def test_bad_values_record_failure_and_explicit_empty_query(self):
        (self.sources/'bad.csv').write_text('id,amount\na,"1,000.00"\nb,\n')
        source=self.begin()['sources'][0]
        failed=self.query(source,dict(aggregates=[dict(op='sum',column='amount',**{'as':'total'})]))
        self.assertEqual(failed['state'],'failed');self.assertFalse(failed['files'])
        empty=self.query(source,dict(filters=[dict(column='id',op='eq',value='missing')],aggregates=[dict(op='count',**{'as':'n'})]))
        self.assertEqual(empty['summary']['matched_rows'],0);self.assertEqual(empty['group_preview'][0]['values']['n'],'0')
        self.call('table-query','--version',source['version']['id'],'--spec',self.json_file('invalid.json',{'filters':[{'column':'id','op':'eval','value':'x'}]}),success=False)

    def test_stage3_ledger_history_renderer8_and_query_update_compatibility(self):
        baseline=os.environ.get('EVIDENCE_REVIEWER_STAGE3_BASELINE')
        if not baseline:self.skipTest('Provide verified stage3 baseline for renderer8 compatibility')
        shutil.copyfile(ROOT/'tests/table-fixtures/small.csv',self.sources/'small.csv')
        req=self.json_file('old.json',dict(goal='Synthetic stage3 compatibility',modes=['query'],source_roots=[str(self.sources)]))
        cli=Path(baseline)/'evidence-reviewer/scripts/review.py'
        def old(command,*args):
            p=subprocess.run([sys.executable,'-B',str(cli),command,'--project',str(self.project),*map(str,args)],capture_output=True,text=True,encoding='utf-8',check=True);return json.loads(p.stdout)
        old('begin','--request',req);source=old('inspect')['sources'][0];first=old('finalize','--assessment',self.json_file('a.json',self.simple_assessment(source)))
        before={p:p.read_bytes() for p in (self.project/'outputs'/first['run_id']).glob('*.md')};authority=(self.project/'ledger/ledger.json').read_bytes()
        self.call('validate');self.call('export');self.assertEqual(authority,(self.project/'ledger/ledger.json').read_bytes())
        self.call('update','--request',self.json_file('update.json',dict(event_id='new-query',reason='Explicit query addition')))
        result=self.query(source,dict(filters=[dict(column='date',op='date_range',max='2031-01-04')],aggregates=[dict(op='sum',column='amount',**{'as':'total'})]))
        self.assertEqual(self.call('inspect')['run']['tool_versions']['reader'],readers.VERSION)
        a=self.assessment(result);a.update(screening=[],impact_review=[]);self.finalize(a);self.call('validate')
        historical=self.call('inspect','--run',first['run_id']);self.assertFalse(any(u['locator'].get('unit')=='table_query_derived' for u in historical['sources'][0]['units']))
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)
        next(iter(before)).unlink();self.call('export')
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)

if __name__=='__main__':unittest.main(verbosity=2)
