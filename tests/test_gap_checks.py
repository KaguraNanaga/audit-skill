"""Candidate gates and delivery states; simulated observations are not audit review."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import unittest

import test_public as public
from generate_gap_fixtures import generate
sys.path.insert(0, str(public.ROOT/'evidence-reviewer/scripts'))
import review
from core import ledger as L, gap_checks


class GapChecks(unittest.TestCase):
    for name in ('setUp','tearDown','json_file','call','begin','find','evidence','simple_assessment','finalize'):
        locals()[name] = public.PublicCLI.__dict__[name]

    def seed(self, count=1):
        for i in range(count):
            (self.sources/f'合成 receipt {i:02}.txt').write_text(f'Synthetic other contract X{i:02}; no relation to target T.\n',encoding='utf-8')
        return self.begin()

    def search(self, pattern='receipt', target='names', **kw):
        args=['--pattern',pattern,'--purpose','Synthetic candidate accounting','--target',target,'--limit','1']
        if kw.get('vid'): args+=['--version',kw['vid']]
        return self.call('search', *args)

    def assessment(self, packet, sid, reviews=None, kind='not_provided', partial=False):
        task=dict(key='t',objective='Synthetic receipt review',procedure='Review declared candidates',population='synthetic sources',
                  sampling_basis='all named candidates',actual_scope='declared units',uncovered_scope='no business judgment',
                  execution_state='partial' if partial else 'done',result='undetermined',basis='Engineering test only',
                  next_step='Open original pages' if partial else 'Human confirmation',source_version_ids=[s['version']['id'] for s in packet['sources']],record_ids=[])
        a=dict(tasks=[task],gaps=[dict(key='g',task_ids=['t'],claim_ids=[],expected_fact='Synthetic target T receipt',search_record_ids=[sid],
                    reason_insufficient='Candidate disposition recorded below',minimal_request='Synthetic target T receipt from responsible custodian',state='open',
                    gap_type=kind,candidate_reviews=reviews or [])],answers=[dict(text='Engineering validation only; no audit conclusion',task_ids=['t'])])
        if partial:a['delivery']=dict(status='partial',reason='Original page review not performed in this structural test',next_step='Open named original pages')
        return a

    def check(self, assessment, success=True):
        return self.call('check-assessment','--assessment',self.json_file('candidate.json',assessment),success=success)

    def candidate(self, source, decision='unread', evidence=None):
        return dict(source_version_id=source['version']['id'],decision=decision,reason='Synthetic candidate disposition only',
                    unit_ids=[u['id'] for u in source['units']],evidence_ids=evidence or [])

    def reviewed(self, packet, sid, kind='not_provided'):
        a=self.assessment(packet,sid,kind=kind)
        a['evidence']=[self.evidence(s,'e'+str(i)) for i,s in enumerate(packet['sources'])]
        a['gaps'][0]['candidate_reviews']=[self.candidate(s,'irrelevant',['e'+str(i)]) for i,s in enumerate(packet['sources'])]
        return a

    def test_frozen_inputs_and_scan_generation(self):
        frozen=json.loads((public.ROOT/'tests/input-sha256-gap-checks.json').read_text(encoding='utf-8'))
        self.assertEqual(frozen['frozen_on'],'2026-11-06')
        for rel,sha in frozen['files'].items():self.assertEqual(hashlib.sha256((public.ROOT/rel).read_bytes()).hexdigest(),sha,rel)
        folder=generate(self.base/'generated')
        for p in folder.iterdir():self.assertEqual(p.read_bytes(),(public.ROOT/'tests/gap-fixtures/sources'/p.name).read_bytes())

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'pypdf unavailable: scan PDF reader not tested')
    def test_filename_finds_scanned_receipt_without_claiming_content_read(self):
        shutil.copyfile(public.ROOT/'tests/gap-fixtures/sources/合成 收款凭证.pdf',self.sources/'合成 收款凭证.pdf')
        packet=self.begin();source=packet['sources'][0]
        self.assertEqual(source['units'][0]['state'],'manual_check');self.assertEqual(source['units'][0]['text'],'')
        text=self.search('收款凭证',target='text');self.assertEqual(text['matches'],0)
        for target in ('names','both'):
            hit=self.search('收款凭证',target=target);self.assertEqual(hit['matches'],1)
            self.assertEqual(hit['results'][0]['match_type'],'filename');self.assertNotIn('unit_id',hit['results'][0])
            self.assertIn('仅供定位',hit['results'][0]['warning'])
        work=review.get_work(self.project)
        self.assertFalse(any(r['kind']=='ReadRecord' and r['state']=='viewed' for r in work['records'].values()))
        a=self.assessment(packet,text['search_record_id'])
        self.assertIn('文件名',self.check(a,False)['error'])
        a=self.assessment(packet,hit['search_record_id'],[self.candidate(source)])
        self.assertIn('候选仍未读',self.check(a,False)['error'])
        a['gaps'][0]['gap_type']='pending_read';a['tasks'][0]['execution_state']='partial'
        a['delivery']=dict(status='partial',reason='Scan not viewed',next_step='Open synthetic receipt original page')
        done=self.finalize(a);self.assertEqual(done['review_state'],'partial');self.assertEqual(done['commit_state'],'completed')
        output=(self.project/'outputs'/done['run_id']/'review.md').read_text(encoding='utf-8')
        execution=output.split('## 材料核查待办')[1].split('## 必要补充材料')[0]
        external=output.split('## 必要补充材料')[1].split('## 证据与计算明细')[0]
        self.assertIn('pending_read',execution);self.assertNotIn(a['gaps'][0]['minimal_request'],external)
        self.assertIn('阶段性成果',output);self.assertEqual(self.call('validate')['review_state'],'partial')

    def test_all_paginated_candidates_and_full_active_scope_are_required(self):
        packet=self.seed(12);hit=self.search();self.assertEqual(hit['matches'],12);self.assertEqual(hit['returned'],1)
        a=self.reviewed(packet,hit['search_record_id']);a['gaps'][0]['candidate_reviews'].pop()
        self.assertIn('分页后部',self.check(a,False)['error'])
        sid=self.search(vid=packet['sources'][0]['version']['id'])['search_record_id']
        a=self.reviewed(packet,sid);self.assertIn('全部活动来源',self.check(a,False)['error'])
        a=self.reviewed(packet,hit['search_record_id']);self.assertEqual(self.check(a)['review_state'],'recorded_scope_complete')
        done=self.finalize(a);self.assertEqual(done['review_state'],'recorded_scope_complete')
        self.assertTrue(self.call('validate')['structure_valid'])

    def test_text_candidates_in_combined_search_cannot_be_ignored(self):
        (self.sources/'目录.txt').write_text('Synthetic receipt candidate in text only',encoding='utf-8')
        packet=self.begin();hit=self.search(target='both')
        self.assertNotIn('match_type',hit['results'][0])
        self.assertIn('候选尚未逐项处理',self.check(self.assessment(packet,hit['search_record_id']),False)['error'])

    def test_irrelevant_candidates_and_actual_absence_are_allowed_with_evidence(self):
        packet=self.seed();sid=self.search()['search_record_id'];a=self.reviewed(packet,sid)
        self.check(a);bad=copy.deepcopy(a);bad['evidence']=[];bad['gaps'][0]['candidate_reviews'][0]['evidence_ids']=[]
        self.assertIn('只有文件名',self.check(bad,False)['error'])
        sid=self.search('genuinely-absent-name')['search_record_id'];a=self.assessment(packet,sid)
        self.assertEqual(self.check(a)['review_state'],'recorded_scope_complete')
        for field,value in [('decision',[]),('source_version_id',{}),('unit_ids',[{}]),('evidence_ids',[{}])]:
            bad=self.reviewed(packet,self.search()['search_record_id']);bad['gaps'][0]['candidate_reviews'][0][field]=value
            self.assertIn('error',self.check(bad,False))

    def test_insufficient_and_sufficient_candidate_dispositions(self):
        packet=self.seed();a=self.reviewed(packet,self.search()['search_record_id'],kind='insufficient')
        self.assertIn('至少一项',self.check(a,False)['error'])
        a['gaps'][0]['candidate_reviews'][0]['decision']='insufficient';self.check(a)
        a['gaps'][0]['gap_type']='not_provided';self.assertIn('使用 insufficient',self.check(a,False)['error'])
        a['gaps'][0]['candidate_reviews'][0]['decision']='sufficient';self.assertIn('足以证明',self.check(a,False)['error'])

    def test_image_exclusion_requires_matching_original_observation(self):
        shutil.copyfile(public.ROOT/'tests/ocr-fixtures/synthetic.png',self.sources/'receipt.png')
        packet=self.begin();source=packet['sources'][0];unit=source['units'][0]
        a=self.assessment(packet,self.search()['search_record_id'],[self.candidate(source,'irrelevant',['e'])])
        a['evidence']=[dict(key='e',source_version_id=source['version']['id'],unit_id=unit['id'],verbatim_quote='',
            image_region_description='Synthetic reference-matching test only',reviewer_summary='No audit assertion',
            reading_method='Simulated observation',verification_state='original_viewed',limitations=['Structural simulation'])]
        self.check(a,False)
        # Synthetic observation exercises the structural gate, not actual visual audit ability.
        a['observations']=[dict(read_id=unit['read_id'],artifact_id=source['artifacts'][0]['id'],observation='Synthetic gate simulation only')]
        self.check(a)
        # A text-carrying manual unit still cannot bypass the observation gate via extracted_only.
        work=review.get_work(self.project);work['units'][source['version']['id']][0]['text']='Synthetic text';review.save_work(self.project,work)
        a.pop('observations');a['evidence'][0].pop('image_region_description');a['evidence'][0].update(verbatim_quote='Synthetic text',verification_state='extracted_only')
        self.assertIn('observations',self.check(a,False)['error'])

    def test_tool_blocked_and_partial_delivery_need_reason_and_next_step(self):
        packet=self.seed();a=self.assessment(packet,self.search()['search_record_id'],[self.candidate(packet['sources'][0],'tool_blocked')],kind='tool_blocked',partial=True)
        self.check(a)
        for bad_delivery in (None,{},dict(status='partial',reason='real cause'),dict(status='recorded_scope_complete')):
            b=copy.deepcopy(a)
            if bad_delivery is None:b.pop('delivery')
            else:b['delivery']=bad_delivery
            self.assertIn('delivery',self.check(b,False)['error'])
        a['gaps']=[];a.pop('delivery');self.assertIn('delivery',self.check(a,False)['error'])
        query=self.simple_assessment(packet['sources'][0]);self.assertEqual(self.check(query)['review_state'],'not_assessed')

    def test_reviewing_only_first_page_cannot_exclude_a_scan_candidate(self):
        packet=self.seed();source=packet['sources'][0];work=review.get_work(self.project)
        # Structural simulation: an extracted first unit followed by an unviewed page.
        extra=copy.deepcopy(work['units'][source['version']['id']][0])
        extra.update(id=L.uid(),state='manual_check',text='',locator=dict(unit='page',page=2))
        work['units'][source['version']['id']].append(extra);review.save_work(self.project,work)
        a=self.reviewed(packet,self.search()['search_record_id'])
        self.assertIn('未列入核查范围',self.check(a,False)['error'])
        a['gaps'][0]['validation_version']=2
        self.assertIn('未列入核查范围',self.check(a,False)['error'])

    def test_new_version_invalidates_gap_search_and_deferred_gaps_remain_pending(self):
        packet=self.seed();a=self.reviewed(packet,self.search()['search_record_id']);first=self.finalize(a)
        (self.sources/'receipt-new.txt').write_text('Synthetic new candidate',encoding='utf-8')
        self.call('update','--request',self.json_file('update.json',dict(event_id='new-receipt',reason='Synthetic new candidate',source_roots=[str(self.sources)])))
        work=review.get_work(self.project);gap=next(r for r in work['records'].values() if r['kind']=='EvidenceGap')
        with self.assertRaisesRegex(ValueError,'新增版本'):gap_checks.candidate_ids(work,gap)
        # Defer is an explicit partial delivery, not a newly verified external request.
        revised=dict(answers=[dict(text='New candidate still unreviewed',task_ids=gap['task_ids'])],
            screening=[dict(change_id=c['id'],topics=['synthetic receipts'],new_matters='New candidate',scope_decision='targeted',basis='Filename inventory',affected_ids=[]) for c in work['run']['changes']],
            impact_review=[dict(target_id=i,decision='defer',basis='Pending original review') for i in work['update_context']['candidate_ids']],
            delivery=dict(status='partial',reason='New candidate unreviewed',next_step='Inspect new receipt'))
        # A fresh search is still required for any current v3 gap, even when delivery is partial.
        self.assertIn('新增版本',self.check(revised,False)['error'])
        sid=self.search()['search_record_id']
        revised['gaps']=[dict(id=gap['id'],key='g',revision_reason='New candidate pending',gap_type='pending_read',search_record_ids=[sid],
                            candidate_reviews=[self.candidate(s) for s in self.call('inspect')['sources']])]
        task=next(r for r in work['records'].values() if r['kind']=='ReviewTask')
        revised['tasks']=[dict(id=task['id'],key='t',revision_reason='Review new candidate',execution_state='partial',next_step='Open new receipt')]
        revised['impact_review']=[dict(target_id=i,decision='review',basis='Registered new pending candidates',source_version_ids=work['run']['active_source_version_ids'],search_record_ids=[sid]) for i in work['update_context']['candidate_ids']]
        second=self.finalize(revised);self.assertEqual(second['review_state'],'partial');self.assertEqual(self.call('validate')['outputs'],'verified')
        self.assertNotEqual(first['run_id'],second['run_id'])

    def test_legacy_10_validate_export_and_opt_in_11_preserve_all_authority_bytes(self):
        f=json.loads((public.ROOT/'tests/gap-fixtures/legacy-10.json').read_text(encoding='utf-8'))
        for rel,body in {**f['files'],f['source_path']:f['source_text']}.items():
            p=self.project/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body.encode('utf-8'))
        L.atomic_json(self.project/'ledger/ledger.json',f['ledger']);L.atomic_json(self.project/'outputs/current.json',f['pointer'])
        authority={rel:(self.project/rel).read_bytes() for rel in list(f['files'])+['ledger/ledger.json','outputs/current.json']}
        self.call('inspect');self.call('validate');self.assertFalse(list((self.project/'outputs').glob('compact-*')))
        for rel in f['files']:(self.project/rel).unlink()
        self.call('export');self.call('validate')
        result=self.call('export','--compact','--renderer','11');self.assertEqual(result['renderer_version'],11)
        view=next(Path(result['compact_directory']).glob('*/review.md')).read_text(encoding='utf-8')
        self.assertIn('旧版缺口尚未按候选核查规则复核',view)
        self.assertNotIn('Legacy synthetic request',view.split('## 必要补充材料')[1])
        self.assertEqual(authority,{rel:(self.project/rel).read_bytes() for rel in authority})
        self.call('validate')


if __name__=='__main__':unittest.main(verbosity=2)
