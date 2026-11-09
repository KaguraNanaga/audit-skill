"""Run the actual pre-stage7 runtime, then preserve its ledger and export bytes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from stage7_support import Helpers,review


class Compatibility(Helpers,unittest.TestCase):
    def test_actual_renderer11_ledger_without_reexport_and_explicit_new_view(self):
        value=os.environ.get('EVIDENCE_REVIEWER_STAGE7_BASELINE')
        if not value:self.skipTest('EVIDENCE_REVIEWER_STAGE7_BASELINE absent: actual pre-stage7 engine comparison not executed')
        root=Path(value);m=json.loads((root/'RELEASE_MANIFEST.json').read_text())
        for rel,sha in m['files'].items():self.assertEqual(hashlib.sha256((root/rel).read_bytes()).hexdigest(),sha)
        cli=root/'evidence-reviewer/scripts/review.py'
        def old(command,*args):
            result=subprocess.run([sys.executable,'-B',str(cli),command,'--project',str(self.project),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
        (self.sources/'text.txt').write_text('Synthetic legacy input 100.00',encoding='utf-8')
        old('begin','--request',self.json_file('request.json',dict(goal='Synthetic legacy query',modes=['query'],source_roots=[str(self.sources)])))
        packet=old('inspect');a=self.simple_assessment(packet['sources'][0]);old('finalize','--assessment',self.json_file('a.json',a))
        paths=[self.project/'ledger/ledger.json',*list((self.project/'outputs').rglob('*'))]
        before={p:p.read_bytes() for p in paths if p.is_file()}
        self.call('inspect');self.call('validate');self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.call('export');self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.call('export','--compact','--renderer','12');self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.call('update','--request',self.json_file('u.json',dict(event_id='legacy-continue',reason='Synthetic continuation')))
        a.update(screening=[],impact_review=[]);self.finalize(a);self.call('validate')


if __name__=='__main__':unittest.main(verbosity=2)
