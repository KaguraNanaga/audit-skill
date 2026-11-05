"""Scaffolds use real IDs, remain incomplete, and preserve existing files."""
import json,unittest
import test_public as public
class Scaffold(unittest.TestCase):
    for name in ('setUp','tearDown','json_file','call','begin'):
        locals()[name]=public.PublicCLI.__dict__[name]
    def test_real_ids_empty_judgments_bounded_selection_and_no_overwrite(self):
        (self.sources/'text.txt').write_text('Synthetic one\nSynthetic two\nSynthetic three')
        packet=self.begin();version=packet['sources'][0]['version']['id'];unit=packet['sources'][0]['units'][1]['id']
        result=self.call('scaffold','--version',version,'--unit',unit)
        assessment=json.loads((self.project/'assessment.json').read_text());ev=assessment['evidence'][0]
        self.assertEqual((ev['source_version_id'],ev['unit_id']),(version,unit));self.assertEqual(ev['reviewer_summary'],'');self.assertIsNone(ev['verification_state'])
        self.assertFalse(result['ready_to_submit']);self.assertTrue((self.project/'assessment.README.md').is_file())
        self.call('check-assessment','--assessment',self.project/'assessment.json',success=False)
        before=(self.project/'assessment.json').read_bytes();self.call('scaffold',success=False);self.assertEqual(before,(self.project/'assessment.json').read_bytes())
        truncated=self.call('scaffold','--out',self.project/'limited.json','--limit','1');self.assertEqual(truncated['omitted_units'],2)
        self.call('scaffold','--out',self.project/'unknown.json','--unit','invented',success=False)
if __name__=='__main__':unittest.main(verbosity=2)
