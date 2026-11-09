import copy
import csv
import io
import unittest
from stage7_support import Helpers,review,L
from evidence_review.coverage import matrix


class Results(Helpers,unittest.TestCase):
    def test_complete_chain_counts_csv_and_out_of_plan_separation(self):
        self.seed();self.freeze();a=self.assessment(True)
        other=copy.deepcopy(a['clues'][0]);other.update(key='outside',origin='计划外发现',check_codes=[],category='情况记录',conclusion_type='事实记录')
        a['clues'].append(other)
        done=self.finalize(a);self.assertEqual(self.call('validate')['outputs'],'verified');self.call('export')
        ledger=review.load(self.project/'ledger/ledger.json');self.assertEqual(ledger['schema_version'],'evidence-ledger-4.0')
        work=L.thaw(ledger);checks,schemes=matrix(work)
        self.assertEqual(checks[0]['被审计单位权限内'],1);self.assertEqual(checks[0]['情况记录'],0);self.assertEqual(schemes[0]['覆盖情况'],'已覆盖')
        out=self.project/'outputs'/done['run_id'];self.assertIn('合成付款差异',(out/'out-of-plan.md').read_text())
        rows=list(csv.DictReader(io.StringIO((out/'coverage-checks.csv').read_text(encoding='utf-8-sig'))))
        self.assertEqual(rows[0]['被审计单位权限内'],'1')
        authority=(self.project/'ledger/ledger.json').read_bytes();(out/'coverage-checks.csv').unlink();self.call('export')
        self.assertEqual((self.project/'ledger/ledger.json').read_bytes(),authority)

    def test_pending_coverage_and_duplicate_result_rejected(self):
        self.seed();link=self.plan['checks'][0]['scheme_links'][0];link.update(degree='部分对应',coverage='部分',remaining_scope='尚无关联的其他范围')
        self.freeze();a=self.assessment();a['delivery']=dict(status='partial',reason='方案条目部分覆盖',next_step='核对剩余范围并修订计划');self.check(a)
        work=L.materialize(review.get_work(self.project),a,project=self.project)
        self.assertEqual(matrix(work)[1][0]['覆盖情况'],'部分覆盖')
        b=copy.deepcopy(a);b['executions'].append(dict(b['executions'][0],key='dup'));self.assertIn('重复',self.check(b,False)['error'])
        a['executions']=[];a['delivery']=dict(status='partial',reason='检查尚未执行',next_step='按冻结计划实施')
        self.finalize(a);work=L.thaw(review.load(self.project/'ledger/ledger.json'))
        self.assertEqual(matrix(work)[0][0]['执行状态'],'待执行');self.assertEqual(matrix(work)[1][0]['覆盖情况'],'未覆盖')
        self.assertEqual(self.call('validate')['review_state'],'partial')

    def test_outside_clue_cannot_be_adopted_by_in_plan_result(self):
        self.seed();self.freeze();a=self.assessment(True);a['clues'][0].update(origin='计划外发现',check_codes=[])
        self.assertIn('计划外',self.check(a,False)['error'])

    def test_cannot_execute_requires_reason_and_is_uncovered(self):
        self.seed();self.freeze();a=self.assessment()
        a['executions'][0].update(status='无法执行',scope_complete=False,actual_scope='',uncovered_scope='合成工具受阻',reason='合成不可执行原因',evidence_ids=[])
        a['tasks'][0].update(execution_state='partial',result='undetermined',uncovered_scope='合成工具受阻')
        a['delivery']=dict(status='partial',reason='合成工具受阻',next_step='修复后继续')
        self.check(a);work=L.materialize(review.get_work(self.project),a,project=self.project)
        self.assertEqual(matrix(work)[1][0]['覆盖情况'],'未覆盖')
        a['executions'][0]['reason']='';self.check(a,False)

    def test_pending_program_applicability_allows_only_partial_pending_result(self):
        self.seed();self.plan['checks'][0]['applicability']=dict(state='待确认',reason='合成适用前提待核')
        self.freeze();a=self.assessment(True);self.check(a,False)
        a['clues'][0]['verification_status']='待核实';a['executions'][0].update(status='发现线索待核实',scope_complete=False,uncovered_scope='先核查程序适用前提')
        a['delivery']=dict(status='partial',reason='适用前提待核',next_step='核实前提，必要时修订计划')
        self.check(a)

    def test_update_keeps_plan_and_history_then_scope_requires_confirmation(self):
        self.seed();self.freeze();first=self.finalize(self.assessment())
        oldfiles={p:p.read_bytes() for p in (self.project/'outputs'/first['run_id']).iterdir()}
        request=self.json_file('update.json',dict(event_id='stage7-continue',reason='合成继续检查'))
        self.call('update','--request',request);work=review.get_work(self.project)
        self.assertEqual(work['run']['plan_version_id'],self.frozen['plan_version_id'])
        a=self.simple_assessment(self.source);a.update(screening=[],impact_review=[],review_checks=[dict(target_id=next(r['id'] for r in work['records'].values() if r['kind']=='ReviewTask'),reason='合成复核',result='范围未变',evidence_ids=['ev'])])
        second=self.finalize(a);self.call('validate');self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertTrue(all(p.read_bytes()==v for p,v in oldfiles.items()))
        self.call('update','--request',self.json_file('scope.json',dict(event_id='scope-change',reason='范围变更',scope={'period':'new'})))
        work=review.get_work(self.project);self.assertIsNone(work['run'].get('plan_version_id'))
        from evidence_review.execution import validate
        with self.assertRaisesRegex(ValueError,'尚未冻结'):validate(work)


if __name__=='__main__':unittest.main(verbosity=2)
