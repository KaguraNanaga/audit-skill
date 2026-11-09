"""Synthetic engineering helpers. Confirmation fixtures are not actual user approval."""
import copy
import sys
from pathlib import Path
import test_public as public
sys.path.insert(0,str(public.ROOT/'evidence-reviewer/scripts'))
import review
from core import ledger as L, program_packs as P, standards


class Helpers:
    for name in ('setUp','tearDown','json_file','call','find','evidence','simple_assessment','finalize'):
        locals()[name]=public.PublicCLI.__dict__[name]

    def seed(self):
        (self.sources/'synthetic.txt').write_text('检查合同付款。评价经营情况。\n合成条款：合同金额100.00元；付款110.00元；审批由合成董事会决定。\n施行2031-01-01；废止2032-01-01；付款2031-06-01。\n',encoding='utf-8')
        request=self.json_file('request.json',dict(goal='Synthetic planning test',modes=['verify'],source_roots=[str(self.sources)],workflow='discovery'))
        self.call('begin','--request',request)
        packet=self.call('inspect');self.source=packet['sources'][0]
        self.ref=dict(source_version_id=self.source['version']['id'],unit_id=self.source['units'][0]['id'],quote='检查合同付款。')
        # Text reader's first unit contains all fixture lines.
        self.fullref=dict(self.ref,quote=self.source['units'][0]['text'])
        work=review.get_work(self.project)
        item=copy.deepcopy(P.load(P.COMMON)['checks'][0]);item.update(code='TMP-01',materials=['合成条款和付款记录'])
        self.plan=dict(schema_version='inspection-plan-1',title='合成检查计划',previous_plan_id=None,revision_reason='',
            pack_snapshot_ids=work['run']['pack_snapshot_ids'],overrides=[],
            scheme_items=[dict(code='S1',objective='核对合同付款',original_text=self.ref['quote'],source_ref=self.ref,type='问题发现')],
            checks=[dict(code='C1',origin='临时程序',check_code='TMP-01',temporary=item,
                scheme_links=[dict(scheme_code='S1',degree='直接对应',reason='合成条款与付款核对',coverage='完整',scope='合成一笔付款',remaining_scope='')],
                selection='选用',selection_reason='合成范围内',applicability=dict(state='成立',reason='存在合成合同付款'),
                materials=[dict(name='合成条款和付款记录',state='齐全',reason='已取得合成原文',unit_refs=[self.fullref],search_record_ids=[],request='')],material_readiness='齐全')])
        return work

    def freeze(self,plan=None):
        plan=plan or self.plan
        p=self.json_file('plan.json',plan);checked=self.call('check-plan','--plan',p)
        c=self.json_file('confirmation.json',dict(plan_sha256=checked['plan_sha256'],source='user_conversation',
            quote='合成确认记录，仅用于结构测试，不是实际人工授权。',confirmed_at='2031-05-01T10:00:00+08:00',session_ref='synthetic-session',message_ref='synthetic-message'))
        self.frozen=self.call('freeze-plan','--plan',p,'--confirmation',c)
        return self.frozen

    def assessment(self,with_clue=False):
        ev=self.evidence(self.source,'e')
        task=dict(key='t',objective='合成付款核查',procedure='合成条款与付款比较',population='一笔',sampling_basis='全量合成样本',
            actual_scope='合成一笔付款',uncovered_scope='',execution_state='done',result='exception' if with_clue else 'no_exception',
            basis='结构测试，无审计判断',next_step='人工复核',source_version_ids=[self.source['version']['id']],record_ids=[])
        a=dict(evidence=[ev],tasks=[task],answers=[dict(text='仅用于工程验证',evidence_ids=['e'],task_ids=['t'])],
            review_checks=[dict(target_id='t',reason='合成最终检查',result='结构断言',evidence_ids=['e'])],
            executions=[dict(key='x',plan_version_id=self.frozen['plan_version_id'],check_code='C1',status='发现线索并已核实' if with_clue else '已执行未发现异常',
                scope_complete=True,actual_scope='合成一笔付款',uncovered_scope='',reason='合成执行',evidence_ids=['e'],calculation_ids=[],
                scheme_results=[dict(scheme_code='S1',state='已覆盖',actual_scope='合成一笔付款',uncovered_scope='',reason='合成逐目标执行')],
                clue_ids=['c'] if with_clue else [],gap_ids=[],task_ids=['t'])])
        if with_clue:
            s=dict(key='s',summary='合成标准',level='合同',name='合成合同',document_number=None,article='合成条款',effective_at='2031-01-01',repealed_at='2032-01-01',
                subjects='合成双方',territory='合成区域',matter_conditions='合成付款',exceptions='合成材料未约定例外',nature='强制性要求',relationships=[],source_ref=self.fullref,rule_id=None,
                critical_text=self.fullref['quote'],verification_state='已核对原文')
            d=dict(state='有证据',description='合成董事会',reason='合成原文',evidence_ids=['e'])
            c=dict(key='c',plan_version_id=self.frozen['plan_version_id'],origin='计划内',check_codes=['C1'],fact='合成付款差异',fact_evidence_ids=['e'],behavior_date='2031-06-01',
                standard_applications=[dict(standard_id='s',judgments={k:dict(state='成立',reason='合成适用条件') for k in standards.AXES})],actual_decision=d,required_decision=copy.deepcopy(d),
                category='被审计单位权限内',conclusion_type='违规',verification_status='已核实',basis_pending=False)
            a.update(standards=[s],clues=[c])
        return a

    def check(self,a,success=True):
        return self.call('check-assessment','--assessment',self.json_file('assessment.json',a),success=success)
