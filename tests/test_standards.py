import copy
import unittest
from stage7_support import Helpers,standards


class Standards(Helpers,unittest.TestCase):
    def test_date_boundaries_and_missing_dates(self):
        s=dict(effective_at='2031-01-01',repealed_at='2032-01-01')
        for day,expected in [('2030-12-31','不成立'),('2031-01-01','成立'),('2031-12-31','成立'),('2032-01-01','不成立'),(None,'无法确定')]:
            self.assertEqual(standards.time_state(s,day),expected)
        s['repealed_at']=None;self.assertEqual(standards.time_state(s,'2031-06-01'),'无法确定')

    def test_verified_original_and_six_axis_gates(self):
        self.seed();self.freeze();a=self.assessment(True);self.check(a)
        for state in ('仅有二手来源','待核实'):
            b=copy.deepcopy(a);b['standards'][0]['verification_state']=state
            self.assertIn('原文',self.check(b,False)['error'])
        for axis in standards.AXES:
            b=copy.deepcopy(a);b['clues'][0]['standard_applications'][0]['judgments'][axis]['state']='无法确定'
            if axis=='time':b['standards'][0]['repealed_at']=None
            self.check(b,False)
            b['clues'][0].update(verification_status='待核实',basis_pending=True);b['executions'][0]['status']='发现线索待核实'
            b['delivery']=dict(status='partial',reason='适用性待核',next_step='核对该项原文条件')
            self.check(b)

    def test_guidance_and_internal_conflict(self):
        self.seed();self.freeze();a=self.assessment(True)
        a['standards'][0]['nature']='导向性政策';self.assertIn('导向性',self.check(a,False)['error'])
        a['clues'][0]['conclusion_type']='评价';self.check(a)
        a['standards'][0].update(nature='强制性要求',level='本单位制度')
        upper=copy.deepcopy(a['standards'][0]);upper.update(key='upper',level='法律',name='合成上位规则')
        a['standards'].append(upper);a['standards'][0]['relationships']=[dict(standard_id='upper',relation='冲突',reason='合成冲突，非真实法律判断')]
        self.assertIn('制度',self.check(a,False)['error'])
        a['clues'][0]['institutional_inconsistency']=dict(description='制度与上位规定不一致（合成）',standard_ids=['s','upper'])
        self.check(a)

    def test_standard_cannot_use_ai_original_and_clue_has_no_motive(self):
        self.seed();self.freeze();a=self.assessment(True)
        a['source_annotations']=[dict(source_id=self.source['source']['id'],role='ai_analysis',role_basis='Synthetic negative test')]
        self.assertIn('AI',self.check(a,False)['error'])
        a.pop('source_annotations');a['clues'][0]['motive']='Synthetic unsupported intent'
        self.assertIn('动机',self.check(a,False)['error'])


if __name__=='__main__':unittest.main(verbosity=2)
