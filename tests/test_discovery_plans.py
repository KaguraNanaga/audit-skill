import copy
import unittest
from stage7_support import Helpers,review,L


class Plans(Helpers,unittest.TestCase):
    def test_plan_references_enums_temporaries_and_unfrozen_gate(self):
        self.seed();self.frozen={'plan_version_id':'unfrozen'}
        self.assertIn('冻结',self.check(self.assessment(),False)['error'])
        for mode in ('reference','enum','temporary','mapping','readiness','objective'):
            p=copy.deepcopy(self.plan)
            if mode=='reference':p['scheme_items'][0]['source_ref']['unit_id']='missing'
            elif mode=='enum':p['checks'][0]['applicability']['state']='maybe'
            elif mode=='temporary':del p['checks'][0]['temporary']['steps']
            elif mode=='mapping':p['checks'][0]['scheme_links']=[]
            elif mode=='readiness':p['checks'][0]['materials'][0]['unit_refs']=[]
            else:del p['scheme_items'][0]['objective']
            self.call('check-plan','--plan',self.json_file('bad.json',p),success=False)
        first=self.freeze();self.assertTrue(first['ready_to_execute'])
        repeated=self.call('freeze-plan','--plan',self.base/'plan.json','--confirmation',self.base/'confirmation.json')
        self.assertTrue(repeated['idempotent'])

    def test_confirmation_hash_version_changes_and_preserved_snapshots(self):
        self.seed();self.freeze();first=review.get_work(self.project);old=copy.deepcopy(first['records'][self.frozen['plan_version_id']])
        changed=copy.deepcopy(self.plan);changed['title']='修订范围';changed['previous_plan_id']=old['id'];changed['revision_reason']='合成范围修订'
        self.call('freeze-plan','--plan',self.json_file('p2.json',changed),'--confirmation',self.base/'confirmation.json',success=False)
        second=self.freeze(changed);self.assertEqual(second['version'],2)
        work=review.get_work(self.project);self.assertEqual(work['records'][old['id']],old)
        self.plan=changed;self.check(self.assessment())
        frozen=self.project/work['records'][second['plan_version_id']]['path'];frozen.write_text('{}',encoding='utf-8')
        self.assertIn('快照',self.check(self.assessment(),False)['error'])

    def test_partial_mapping_suggestions_and_evaluation(self):
        self.seed();p=self.plan
        p['scheme_items'].append(dict(code='S2',objective='评价经营情况',original_text='评价经营情况。',source_ref=dict(self.ref,quote='评价经营情况。'),type='评价描述'))
        link=p['checks'][0]['scheme_links'][0];link.update(degree='部分对应',coverage='部分',remaining_scope='其他合同事项')
        self.freeze();a=self.assessment();self.assertIn('delivery',self.check(a,False)['error'])
        a['delivery']=dict(status='partial',reason='评价类待模板',next_step='由审计人员确定指标')
        self.check(a)
        result=self.call('scaffold','--plan-version',self.frozen['plan_version_id']);self.assertFalse(result['ready_to_submit'])
        skeleton=review.load(result['assessment']);self.assertIsNone(skeleton['executions'][0]['status'])
        self.assertEqual(skeleton['executions'][0]['plan_version_id'],self.frozen['plan_version_id'])


if __name__=='__main__':unittest.main(verbosity=2)
