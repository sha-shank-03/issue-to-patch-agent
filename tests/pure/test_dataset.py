import hashlib
import json
from unittest.mock import patch
import stat
from issue_to_patch.observations import compare, parse
from issue_to_patch.providers import ProviderError, ScriptedProvider
from issue_to_patch.tools import Tools
from issue_to_patch.protocol import parse_action
from issue_to_patch.workspace import AuthorityError, SOURCE, Trust, atomic_json, no_reparse
from scripts.freeze import verify
from helpers import LocalCase, typed_output


class DatasetTests(LocalCase):
    def test_nine_frozen_cases_split_and_family_denominators(self):
        receipt = verify(self.repo)
        self.assertEqual((receipt["case_count"], receipt["development_count"], receipt["held_out_count"]), (9, 3, 6))
        for family in ("validation", "pagination", "transaction"):
            cases = [item for item in receipt["cases"].values() if item["family"] == family]
            self.assertEqual(len(cases), 3)
            self.assertEqual(sum(item["split"] == "held-out" for item in cases), 2)
            self.assertTrue(all(item["independent_scenarios"] == 7 for item in cases))

    def test_candidate_bytes_and_oracle_types_match_all_manifests(self):
        for case_id in verify(self.repo)["cases"]:
            trust = Trust(self.repo, case_id)
            info = trust.case_info
            candidates = json.loads((self.repo / info["candidate_sources"]).read_text())
            for role, source in candidates.items():
                self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), trust.candidates[role.replace("-", "_")])
            expected = json.loads((self.repo / info["independent_expected"]).read_text())
            # Parser round trip validates shape only; no Java semantics claim.
            self.assertEqual(compare(typed_output(expected), expected)["passed_assertions"], len(expected))

    def test_held_out_scripts_are_unavailable(self):
        for case_id in ("V02", "V03", "P02", "P03", "T02", "T03"):
            with self.subTest(case=case_id), self.assertRaises(ProviderError):
                ScriptedProvider(case_id=case_id, repo=self.repo)

    def test_case_digest_cannot_authorize_another_case(self):
        ws, trust = self.workspace("P01")
        other = json.loads((self.repo / "evaluation/cases/T01/candidate_sources.json").read_text())["repair"]
        ws.path(SOURCE).write_text(other, encoding="utf-8", newline="\n")
        self.assertFalse(trust.permits(ws.path(SOURCE)))

    def test_private_inputs_oracles_and_candidate_sources_denied_for_all_cases(self):
        for case_id in Trust(self.repo).data["cases"]:
            ws, trust = self.workspace(case_id, case_id)
            for path in (trust.case_info["independent_expected"], trust.case_info["independent_inputs"],
                         trust.case_info["candidate_sources"], "manifest.json", "public/expected.json"):
                with self.subTest(case=case_id, path=path), self.assertRaises(AuthorityError):
                    ws.read(path)
            files = Tools(ws, None, trust).dispatch(parse_action('{"id":"a","tool":"list_files","args":{}}'))["files"]
            self.assertEqual(set(files), {SOURCE, "public/PublicProbe.java", "contract.md", "issue.md"})

    def test_oracle_and_input_tampering_denies_execution_permission(self):
        ws, trust = self.workspace("T03")
        for key in ("independent_expected", "independent_inputs", "independent_probe", "candidate_sources"):
            target = self.repo / trust.case_info[key]
            original = target.read_bytes()
            target.write_bytes(original + b" ")
            with self.subTest(key=key), self.assertRaises(AuthorityError):
                trust.permits(ws.path(SOURCE))
            target.write_bytes(original)

    def test_atomic_report_failure_preserves_previous_report(self):
        path = self.repo / "report.json"
        atomic_json(path, {"status": "old"})
        with patch("issue_to_patch.workspace.os.replace", side_effect=OSError("injected replace failure")):
            with self.assertRaises(OSError):
                atomic_json(path, {"status": "new"})
        self.assertEqual(json.loads(path.read_text()), {"status": "old"})

    def test_windows_reparse_and_symlink_attributes_denied_without_creating_links(self):
        target = self.repo / "fixtures/V01/src/ShopApi.java"
        for attrs in (type("Attrs", (), {"st_mode": stat.S_IFREG, "st_file_attributes": 0x400})(),
                      type("Attrs", (), {"st_mode": stat.S_IFLNK, "st_file_attributes": 0})()):
            with patch("pathlib.Path.lstat", return_value=attrs), self.assertRaises(AuthorityError):
                no_reparse(target)


class ObservationTests(LocalCase):
    def test_duplicate_missing_unexpected_and_fake_pass_denied(self):
        expected = {"one.accepted": True, "one.ids": [1, 2]}
        good = typed_output(expected)
        for raw in (good + good, "PASS\n", good.splitlines()[0] + "\n", good + "extra.accepted\tbool\ttrue\n"):
            with self.subTest(raw=raw), self.assertRaises(AuthorityError):
                compare(raw, expected)

    def test_wrong_typed_values_cannot_equal_boolean_or_integer_list(self):
        result = compare("one\taccepted\tint\t1\none\tids\tints\t2,1\n", {"one.accepted": True, "one.ids": [1, 2]})
        self.assertEqual(set(result["failures"]), {"one.accepted", "one.ids"})

    def test_nonfinite_unknown_types_and_oversized_values_denied(self):
        for raw in ("a\tb\tfloat\tNaN\n", "a\tb\tbool\tTRUE\n", "a\tb\tint\t1.0\n",
                    "a\tb\tints\t1,,2\n", "a\tb\tints\t" + "1," * 128 + "1\n", "x" * 65537):
            with self.subTest(length=len(raw)), self.assertRaises(AuthorityError):
                parse(raw)
