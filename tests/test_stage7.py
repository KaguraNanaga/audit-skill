import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from stage7_support import Helpers,public,review
import generate_stage7_fixtures as generator
sys.path.insert(0,str(public.ROOT/'tools'))
import prepare_evaluation


class Stage7(Helpers,unittest.TestCase):
    def test_frozen_case_reproduction_and_separated_answers(self):
        files=generator.generate(self.base)
        manifest=review.load(public.ROOT/'tests/input-sha256-stage7.json')
        self.assertEqual(manifest['frozen_on'],'2026-11-09')
        self.assertEqual(set(files),set(manifest['files']))
        for rel,data in files.items():
            self.assertEqual(hashlib.sha256(data).hexdigest(),manifest['files'][rel])
            self.assertEqual(data,(public.ROOT/rel).read_bytes())
        result=prepare_evaluation.prepare('stage7-06',self.base.resolve()/'evaluation')
        folder=Path(result['input_directory']);self.assertTrue((folder/'sources/合成审计方案.md').is_file())
        self.assertFalse(list(folder.rglob('*expected*')));self.assertFalse((folder/'sources/复核稿.md').exists())
        for p in (public.ROOT/'tests/cases/stage6-06/sources').iterdir():
            self.assertEqual(p.read_bytes(),(folder/'sources'/p.name).read_bytes())

    def test_interrupted_plan_freeze_can_resume_without_authorizing_results(self):
        self.seed();p=self.json_file('plan.json',self.plan);checked=self.call('check-plan','--plan',p)
        c=self.json_file('confirmation.json',dict(plan_sha256=checked['plan_sha256'],source='user_conversation',quote='合成测试确认',confirmed_at='2031-05-01T00:00:00+00:00',session_ref='synthetic',message_ref='synthetic'))
        result=subprocess.run([sys.executable,'-B',str(public.CLI),'freeze-plan','--project',str(self.project),'--plan',str(p),'--confirmation',str(c)],env=dict(os.environ,EVIDENCE_REVIEWER_FAILPOINT='after_plan_snapshot'),capture_output=True)
        self.assertEqual(result.returncode,86);self.assertIsNone(review.get_work(self.project)['run'].get('plan_version_id'))
        orphan=next((self.project/'plans').glob('*/frozen.json'));before=orphan.read_bytes()
        frozen=self.call('freeze-plan','--plan',p,'--confirmation',c)
        self.assertEqual(frozen['plan_version_id'],orphan.parent.name);self.assertEqual(before,orphan.read_bytes())


if __name__=='__main__':unittest.main(verbosity=2)
