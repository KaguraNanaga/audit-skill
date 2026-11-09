import copy
import unittest
from stage7_support import Helpers,P,L,review


class Packs(Helpers,unittest.TestCase):
    def test_required_unique_enums_generated_and_privacy(self):
        p=P.load(P.COMMON);self.assertEqual(len(p['checks']),14)
        self.assertEqual(P.markdown(p),P.COMMON.with_name('checks.md').read_text(encoding='utf-8'))
        for change in ('missing','duplicate','enum'):
            b=copy.deepcopy(p)
            if change=='missing':del b['checks'][0]['materials']
            elif change=='duplicate':b['checks'].append(b['checks'][0])
            else:b['checks'][0]['tools'][0]['status']='invented'
            with self.assertRaises(ValueError):P.validate(b)
        p['description']='合成示例有限公司；合成〔2031〕1号；联系人：张三'
        self.assertEqual(len(P.privacy_candidates(p)),3)

    def test_local_pack_collision_explicit_override_and_snapshot(self):
        self.seed();work=review.get_work(self.project);common=P.snapshots(work)[0]
        local=copy.deepcopy(common['data']);local.update(pack_id='local',checks=[local['checks'][0]])
        path=self.json_file('local.json',local)
        with self.assertRaisesRegex(ValueError,'冲突'):P.install(self.project,work,['local.json'],self.base/'request.json')
        local['overrides']=[dict(code='CON-01',pack_id='common',version=common['data']['version'],sha256=common['pack_sha256'],reason='合成显式覆盖')]
        self.json_file('local.json',local);P.install(self.project,work,['local.json'],self.base/'request.json')
        resolved,overrides=P.resolve(P.snapshots(work));self.assertEqual(resolved['CON-01']['pack_id'],'local');self.assertEqual(len(overrides),1)
        path.unlink();review.save_work(self.project,work);review.check_files(self.project,work)
        changed=copy.deepcopy(P.snapshots(work));changed[-1]['data']['overrides'][0]['sha256']='0'*64;changed[-1]['pack_sha256']=L.checksum(changed[-1]['data'])
        with self.assertRaisesRegex(ValueError,'指纹'):P.resolve(changed)


if __name__=='__main__':unittest.main(verbosity=2)
