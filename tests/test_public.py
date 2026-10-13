#!/usr/bin/env python3
"""Public CLI regressions. These test data handling, not audit judgement.

Run: python3 -B tests/test_public.py
Projects are created in temporary directories and removed after each test.
PDF and XLSX cases are explicitly skipped if their reader dependency is absent.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "evidence-reviewer/scripts/review.py"
CASES = ROOT / "tests/cases"


class PublicCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="public-audit-test-")
        self.base = Path(self.tmp.name)
        self.sources = self.base / "sources"
        self.sources.mkdir()
        self.project = self.base / "project"

    def tearDown(self):
        self.tmp.cleanup()

    def json_file(self, name, value):
        path = self.base / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def call(self, command, *args, success=True):
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), command, "--project", str(self.project), *map(str, args)],
            capture_output=True, text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
        payload = result.stdout if result.returncode == 0 else result.stderr
        try:
            data = json.loads(payload)
        except ValueError:
            self.fail("CLI did not return JSON: " + payload.replace(str(self.base), "<temporary>"))
        if success:
            self.assertEqual(result.returncode, 0, payload.replace(str(self.base), "<temporary>"))
        else:
            self.assertNotEqual(result.returncode, 0, "Expected CLI rejection")
        return data

    def begin(self):
        request = self.json_file("begin.json", {
            "goal": "Synthetic fixture query; no real audit conclusion", "modes": ["query"],
            "source_roots": [str(self.sources)],
        })
        result = self.call("begin", "--request", request)
        self.assertFalse(result["reviewed"])
        return self.call("inspect")

    @staticmethod
    def find(packet, filename):
        return next(source for source in packet["sources"] if source["source"]["actual_name"] == filename)

    @staticmethod
    def evidence(source, key="ev"):
        unit = next(u for u in source["units"] if u["text"])
        return dict(key=key, source_version_id=source["version"]["id"], unit_id=unit["id"],
                    verbatim_quote=unit["text"], reviewer_summary="Synthetic source excerpt only",
                    reading_method="read extracted unit", verification_state="extracted_only", limitations=[])

    def simple_assessment(self, source):
        return {"evidence": [self.evidence(source)], "answers": [{
            "text": "Read the cited synthetic statement; no broader audit conclusion.",
            "evidence_ids": ["ev"], "calculation_ids": [], "rule_ids": [], "task_ids": [],
        }]}

    def finalize(self, assessment):
        path = self.json_file("assessment.json", assessment)
        self.call("check-assessment", "--assessment", path)
        return self.call("finalize", "--assessment", path)

    def test_frozen_synthetic_inputs_match_recorded_hashes(self):
        manifest_path = ROOT / "tests/input-sha256.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative, expected in manifest.items():
            candidate = ROOT / relative
            self.assertEqual(hashlib.sha256(candidate.read_bytes()).hexdigest(), expected, relative)

    def test_snapshots_survive_original_changes_and_project_is_not_overwritten(self):
        original = self.sources / "amount.txt"
        original.write_text("Synthetic opening amount: 321.45\n", encoding="utf-8")
        initial = self.begin()
        original.write_text("Synthetic changed amount: 999.99\n", encoding="utf-8")
        retained = self.find(self.call("inspect"), "amount.txt")
        self.assertIn("321.45", retained["units"][0]["text"])
        self.assertEqual(initial["sources"][0]["version"]["sha256"], retained["version"]["sha256"])
        self.call("begin", "--request", self.base / "begin.json", success=False)

    def test_decimal_recalculation_rounding_finalize_and_export_validation(self):
        (self.sources / "numbers.txt").write_text("A=100.005; B=0.010\n", encoding="utf-8")
        source = self.find(self.begin(), "numbers.txt")
        unit = source["units"][0]
        assessment = self.simple_assessment(source)
        inputs = [dict(name=name, value=value, raw_value=value,
                       source_version_id=source["version"]["id"], unit_id=unit["id"], unit="元",
                       currency="CNY", period="synthetic period", tax_basis="not applicable",
                       normalization="exact decimal text") for name, value in [("a", "100.005"), ("b", "0.010")]]
        assessment["calculations"] = [dict(key="calc", purpose="Original precision before rounding",
            inputs=inputs, formula="a - b", rounding={"places": 2, "mode": "ROUND_HALF_UP"},
            unit="元", currency="CNY", result_kind="recalculation", assumptions=[], limitations=[])]
        assessment["answers"][0]["calculation_ids"] = ["calc"]
        candidate = self.call("check-assessment", "--assessment", self.json_file("candidate.json", assessment))
        self.assertEqual(candidate["calculations"][0]["result"], "100.00")
        rejected = copy.deepcopy(assessment)
        rejected["calculations"][0]["result"] = "99.99"
        self.call("check-assessment", "--assessment", self.json_file("wrong-result.json", rejected), success=False)
        final = self.finalize(assessment)
        self.assertEqual(final["state"], "completed")
        validated = self.call("validate")
        self.assertTrue(validated["structure_valid"])
        self.assertEqual(validated["outputs"], "verified")
        self.assertTrue((self.project / "outputs/current.json").is_file())

    def test_fabricated_quote_and_unviewed_image_evidence_are_rejected(self):
        (self.sources / "text.txt").write_text("Synthetic recorded amount: 73.20", encoding="utf-8")
        shutil.copyfile(CASES / "controls/sources/003-approval.png", self.sources / "image.png")
        packet = self.begin()
        assessment = self.simple_assessment(self.find(packet, "text.txt"))
        assessment["evidence"][0]["verbatim_quote"] = "A statement absent from the cited source"
        result = self.call("check-assessment", "--assessment", self.json_file("invented.json", assessment), success=False)
        self.assertIn("quote", result["error"])
        source = self.find(packet, "image.png")
        assessment["evidence"] = [dict(key="ev", source_version_id=source["version"]["id"],
            unit_id=source["units"][0]["id"], verbatim_quote="", reviewer_summary="Unsupported visual assertion",
            reading_method="not actually viewed", verification_state="original_viewed",
            image_region_description="Asserted approval without observation", limitations=[])]
        result = self.call("check-assessment", "--assessment", self.json_file("unviewed.json", assessment), success=False)
        self.assertIn("view record", result["error"])

    def test_unread_images_remain_partial_after_structural_validation(self):
        shutil.copyfile(CASES / "controls/sources/003-approval.png", self.sources / "image.png")
        packet = self.begin()
        source = self.find(packet, "image.png")
        self.assertEqual(source["units"][0]["state"], "manual_check")
        assessment = {"tasks": [dict(key="pending", objective="Read synthetic approval image",
            procedure="Inventory only; visual reading not performed", population="one image", sampling_basis="whole image intended",
            actual_scope="file registered only", uncovered_scope="all image content", execution_state="partial",
            result="undetermined", basis="No actual visual reading in this automated test", next_step="Actually view image",
            source_version_ids=[source["version"]["id"]], record_ids=[])],
            "answers": [dict(text="Image registered; approval status remains unverified.", evidence_ids=[],
                             calculation_ids=[], rule_ids=[], task_ids=["pending"])],
            "limitations": ["No actual visual reading in this automated test"]}
        final = self.finalize(assessment)
        self.assertTrue(final["structure_valid"])
        self.assertNotEqual(final["material_reading"], "complete")
        self.assertTrue(final["reading_issues"])
        validated = self.call("validate")
        self.assertTrue(validated["reading_issues"])

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl unavailable: XLSX reader not tested")
    def test_xlsx_formula_is_preserved_without_inventing_cached_result(self):
        shutil.copyfile(CASES / "financial/sources/权益桥接.xlsx", self.sources / "bridge.xlsx")
        source = self.find(self.begin(), "bridge.xlsx")
        formula_units = [u for u in source["units"] if u.get("formula") == "=SUM(B4:B7)"]
        self.assertEqual(len(formula_units), 1)
        formula = formula_units[0]
        self.assertNotIn("80900", formula["text"])
        self.assertEqual(formula["cached_or_display_value"], None)
        self.assertEqual(formula["recalculated_value"], None)
        self.assertIn("100000", " ".join(u["text"] for u in source["units"]))

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf unavailable: PDF reader not tested")
    def test_mixed_pdf_keeps_scanned_page_unread_after_text_extraction(self):
        shutil.copyfile(CASES / "contract/sources/合同及补充页.pdf", self.sources / "mixed.pdf")
        source = self.find(self.begin(), "mixed.pdf")
        self.assertEqual(len(source["units"]), 2)
        self.assertIn("2030-01-20", source["units"][0]["text"])
        self.assertEqual(source["units"][1]["state"], "manual_check")
        self.assertEqual(source["units"][1]["text"], "")

    def test_update_retains_prior_version_and_requires_new_review(self):
        original = self.sources / "numbers.txt"
        original.write_text("Synthetic amount: 45.10", encoding="utf-8")
        source = self.find(self.begin(), "numbers.txt")
        first = self.finalize(self.simple_assessment(source))
        old_version = source["version"]["id"]
        original.write_text("Synthetic amount: 46.20", encoding="utf-8")
        request = self.json_file("update.json", {"event_id": "synthetic-correction-1", "reason": "New synthetic evidence",
                                                "source_roots": [str(self.sources)]})
        self.call("update", "--request", request)
        packet = self.call("inspect", "--records")
        self.assertNotEqual(packet["run"]["id"], first["run_id"])
        self.assertEqual(packet["run"]["state"], "staging")
        versions = {s["version"]["id"]: s for s in packet["sources"]}
        self.assertIn(old_version, versions)
        self.assertIn("45.10", versions[old_version]["units"][0]["text"])
        new_sources = [s for s in packet["sources"] if "46.20" in s["units"][0]["text"]]
        self.assertEqual(len(new_sources), 1)
        committed = self.call("inspect", "--committed")
        self.assertEqual(committed["run"]["id"], first["run_id"])
        self.assertTrue(packet["run"]["changes"])
        # A new source alone never silently commits a replacement conclusion.
        pointer = json.loads((self.project / "outputs/current.json").read_text(encoding="utf-8"))
        self.assertEqual(pointer["run_id"], first["run_id"])
        self.assertEqual(packet["run"]["impact_candidates"]["candidate_ids"], [])
        revised = self.simple_assessment(new_sources[0])
        revised["screening"] = [dict(change_id=change["id"], topics=["synthetic amount"],
            new_matters="Changed synthetic statement from 45.10 to 46.20; no other business claims are in this query",
            scope_decision="targeted", basis="Read old and new text units", affected_ids=[])
            for change in packet["run"]["changes"]]
        revised["impact_review"] = []
        second = self.finalize(revised)
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(self.call("validate")["outputs"], "verified")
        historical = self.call("inspect", "--run", first["run_id"])
        self.assertIn("45.10", historical["sources"][0]["units"][0]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
