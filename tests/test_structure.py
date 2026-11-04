"""Structure-only regressions; no test is an audit conclusion."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'evidence-reviewer/scripts'
sys.path.insert(0,str(SCRIPTS));sys.path.insert(0,str(ROOT/'tools'))
import review
from core import ledger as L
from check_links import check_links
from compare_structure import compare

COMMON={'accuracy-and-context.md','assessment.md','intake.md','workflow.md','incremental.md','visual-followup.md','audit-profiles.md'}


class LinkChecks(unittest.TestCase):
    def test_repository_links(self):
        result=check_links(ROOT)
        self.assertTrue(result['ok'],result['errors'])
        self.assertGreater(result['checked_local_links'],0)

    def test_links_fragments_references_unicode_and_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'中文 文档.md').write_text('# 中文 标题\n',encoding='utf-8')
            readme=root/'README.md'
            readme.write_text('[中文](<中文%20文档.md#中文-标题>)\n[x][r]\n[r]: <中文%20文档.md>\n```md\n[ignored](missing.md)\n```\n',encoding='utf-8')
            self.assertTrue(check_links(root)['ok'])
            for bad in ('[x](missing.md)','[x](../outside.md)','[x](中文%20文档.md#absent)','[x][undefined]'):
                readme.write_text(bad,encoding='utf-8');self.assertFalse(check_links(root)['ok'])


class StructureBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value=os.environ.get('EVIDENCE_REVIEWER_BASELINE')
        if not value: raise unittest.SkipTest('Provide verified stage-1 directory with EVIDENCE_REVIEWER_BASELINE; baseline comparisons not executed')
        cls.baseline=Path(value).resolve()
        cls.candidate=Path(os.environ.get('EVIDENCE_REVIEWER_STRUCTURE_CANDIDATE', str(ROOT))).resolve()
        manifest=json.loads((cls.baseline/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
        for rel,sha in manifest['files'].items():
            if hashlib.sha256((cls.baseline/rel).read_bytes()).hexdigest()!=sha:
                raise ValueError('Baseline differs from stage-1 manifest: '+rel)

    def test_before_after_begin_inspect(self):
        result=compare(self.baseline,self.candidate)
        self.assertTrue(result['ok']);self.assertEqual(result['excluded_fields'],[])
        self.assertEqual(len(result['cases']),4)

    def test_moved_runtime_ast_changes_only_imports(self):
        class WithoutImports(ast.NodeTransformer):
            def visit_Import(self,node): return None
            def visit_ImportFrom(self,node): return None
        for old in (self.baseline/'evidence-reviewer/scripts').glob('*.py'):
            scripts=self.candidate/'evidence-reviewer/scripts'
            new=scripts/old.name if old.name=='review.py' else scripts/'core'/old.name
            with self.subTest(file=old.name):
                def structure(path): return ast.dump(WithoutImports().visit(ast.parse(path.read_text(encoding='utf-8'))),include_attributes=False)
                self.assertEqual(structure(old),structure(new))

    def test_rule_prose_preserved(self):
        def normalize(s):
            s=re.sub(r'references/(?:(?:common|evidence-review)/)?','',s)
            return re.sub(r'\.\./(?:common|evidence-review)/','',s)
        for old in (self.baseline/'evidence-reviewer/references').glob('*.md'):
            folder='common' if old.name in COMMON else 'evidence-review'
            self.assertEqual(normalize(old.read_text(encoding='utf-8')),normalize((self.candidate/'evidence-reviewer/references'/folder/old.name).read_text(encoding='utf-8')),old.name)
        original=(self.baseline/'evidence-reviewer/SKILL.md').read_text(encoding='utf-8')
        combined=normalize((self.candidate/'evidence-reviewer/SKILL.md').read_text(encoding='utf-8')+'\n'+(self.candidate/'evidence-reviewer/references/evidence-review/index.md').read_text(encoding='utf-8'))
        for section in re.split(r'(?m)(?=^## )',original)[1:]:
            self.assertIn(normalize(section).strip(),combined,section.splitlines()[0])

    def test_old_preparation_entry_help(self):
        def help_at(root):
            result=subprocess.run([sys.executable,'-B',str(root/'evidence-reviewer/scripts/prepare.py'),'--help'],capture_output=True,text=True,encoding='utf-8',check=True)
            return result.stdout
        self.assertEqual(help_at(self.baseline),help_at(self.candidate))

    def test_stage1_export_rebuild_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);sources=base/'sources';sources.mkdir()
            (sources/'text.txt').write_text('Synthetic structure regression only',encoding='utf-8')
            project=base/'project';request=base/'request.json'
            request.write_text(json.dumps(dict(goal='Synthetic unchanged export',modes=['query'],source_roots=[str(sources)])),encoding='utf-8')
            cli=self.baseline/'evidence-reviewer/scripts/review.py'
            invoke(cli,project,'begin','--request',request)
            packet=invoke(cli,project,'inspect');assessment=assessment_for(packet)
            path=base/'assessment.json';path.write_text(json.dumps(assessment),encoding='utf-8')
            invoke(cli,project,'finalize','--assessment',path)
            before={p.relative_to(project).as_posix():p.read_bytes() for p in (project/'outputs').rglob('*.md')}
            ledger=(project/'ledger/ledger.json').read_bytes()
            next((project/'outputs').rglob('review.md')).unlink()
            invoke(SCRIPTS/'review.py',project,'export')
            self.assertEqual({rel:(project/rel).read_bytes() for rel in before},before)
            self.assertEqual((project/'ledger/ledger.json').read_bytes(),ledger)
            invoke(SCRIPTS/'review.py',project,'validate')


def invoke(cli,project,command,*args):
    result=subprocess.run([sys.executable,'-B',str(cli),command,'--project',str(project),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode: raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def assessment_for(packet):
    source=packet['sources'][0];unit=next(u for u in source['units'] if u['text'])
    return dict(evidence=[dict(key='e',source_version_id=source['version']['id'],unit_id=unit['id'],verbatim_quote=unit['text'],reviewer_summary='Synthetic text only',reading_method='text',verification_state='extracted_only',limitations=[])],answers=[dict(text='Synthetic statement retained; no audit conclusion.',evidence_ids=['e'])])


class LegacyCommands(unittest.TestCase):
    def test_pre_stage1_ledgers_inspect_validate_update_export(self):
        fixtures=json.loads((ROOT/'tests/platform-fixtures/legacy.json').read_text(encoding='utf-8'))
        for fixture in (f for f in fixtures if f['renderer']==6):
            with self.subTest(schema=fixture['ledger']['schema_version']),tempfile.TemporaryDirectory() as tmp:
                project=Path(tmp)/'project';project.mkdir()
                for rel,text in {**fixture['files'],fixture['source_path']:fixture['source_text']}.items():
                    path=project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode('utf-8'))
                L.atomic_json(project/'ledger/ledger.json',fixture['ledger']);L.atomic_json(project/'outputs/current.json',fixture['pointer'])
                cli=SCRIPTS/'review.py';invoke(cli,project,'inspect');invoke(cli,project,'validate');invoke(cli,project,'export')
                request=Path(tmp)/'update.json';request.write_text(json.dumps(dict(event_id='structure-compat',reason='Synthetic no-change continuation')),encoding='utf-8')
                invoke(cli,project,'update','--request',request)
                packet=invoke(cli,project,'inspect')
                assessment=assessment_for(packet);assessment.update(screening=[],impact_review=[])
                path=Path(tmp)/'assessment.json';path.write_text(json.dumps(assessment),encoding='utf-8')
                invoke(cli,project,'check-assessment','--assessment',path);invoke(cli,project,'finalize','--assessment',path)
                invoke(cli,project,'validate');invoke(cli,project,'export')
                for rel,text in fixture['files'].items():self.assertEqual((project/rel).read_bytes(),text.encode('utf-8'))


if __name__=='__main__':unittest.main(verbosity=2)
