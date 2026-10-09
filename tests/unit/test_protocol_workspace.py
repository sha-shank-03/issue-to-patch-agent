import json
from pathlib import Path
import shutil
import tempfile
import unittest

from issue_to_patch.protocol import ProtocolError, parse_action
from issue_to_patch.providers import ORIGINAL, REPAIRED, NOVEL
from issue_to_patch.tools import Tools
from issue_to_patch.workspace import AuthorityError, SOURCE, Trust, VISIBLE, Workspace

REPO = Path(__file__).resolve().parents[2]


def action(tool, args=None, identifier="test"):
    return parse_action(json.dumps({"id": identifier, "tool": tool, "args": args or {}}))


class ProtocolTests(unittest.TestCase):
    def test_valid_typed_action(self):
        self.assertEqual(action("list_files").tool, "list_files")

    def test_duplicate_json_keys_denied(self):
        with self.assertRaises(ProtocolError):
            parse_action('{"id":"a","id":"b","tool":"list_files","args":{}}')

    def test_unknown_shell_extra_fields_and_nonfinite_denied(self):
        for raw in ('{"id":"a","tool":"shell","args":{}}',
                    '{"id":"a","tool":"list_files","args":{},"command":"java"}',
                    '{"id":"a","tool":"list_files","args":{"x":NaN}}'):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                parse_action(raw)

    def test_wrong_argument_types_and_bounds_denied(self):
        for value in (True, 0, -1, 201, "10"):
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                action("read_file", {"path": SOURCE, "start_line": 1, "max_lines": value})

    def test_private_check_is_not_in_protocol(self):
        with self.assertRaises(ProtocolError):
            action("run_check", {"check": "independent"})


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / "work/unit"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        shutil.copytree(REPO / "fixtures", self.repo / "fixtures")
        shutil.copytree(REPO / "evaluation", self.repo / "evaluation", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "demos", self.repo / "demos")
        shutil.copytree(REPO / "issue_to_patch", self.repo / "issue_to_patch", ignore=shutil.ignore_patterns("__pycache__"))
        self.trust = Trust(self.repo)
        self.ws = Workspace(self.repo, self.repo / "work/runs/unit", self.trust)
        self.tools = Tools(self.ws, None, self.trust)

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, new=REPAIRED, identifier="edit", digest=None):
        return action("replace_text", {"path": SOURCE, "preimage_sha256": digest or self.ws.digest,
                                       "old": ORIGINAL, "new": new}, identifier)

    def test_inventory_and_search_do_not_expose_verifier(self):
        self.assertEqual(self.tools.dispatch(action("list_files"))["files"], list(VISIBLE))
        result = self.tools.dispatch(action("search", {"query": "quantity"}, "search"))
        self.assertTrue(all(item["path"] in VISIBLE for item in result["matches"]))

    def test_hostile_and_private_paths_denied(self):
        for path in ("../evaluation/trusted.json", "evaluation/IndependentProbe.java", "C:/secret", "C:secret",
                     "//server/share", "src/ShopApi.java:stream", "src/shopapi.java", "src/../src/ShopApi.java"):
            with self.subTest(path=path), self.assertRaises(AuthorityError):
                self.ws.read(path)

    def test_public_probe_cannot_be_edited(self):
        with self.assertRaises(AuthorityError):
            self.ws.path("public/PublicProbe.java", write=True)

    def test_edit_and_finish_require_reproduction(self):
        for request in (self.edit(), action("finish", {"summary": "done"})):
            with self.subTest(tool=request.tool), self.assertRaises(AuthorityError):
                self.tools.dispatch(request)

    def test_stale_digest_does_not_write(self):
        original = self.ws.digest
        self.tools.reproduced = True
        with self.assertRaises(AuthorityError):
            self.tools.dispatch(self.edit(digest="0" * 64))
        self.assertEqual(self.ws.digest, original)

    def test_idempotent_edit_and_conflicting_id(self):
        self.tools.reproduced = True
        request = self.edit()
        first = self.tools.dispatch(request)
        second = self.tools.dispatch(request)
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["source_sha256"], second["source_sha256"])
        self.assertEqual(self.ws.patch_attempts, 1)
        with self.assertRaises(AuthorityError):
            self.tools.dispatch(action("list_files", identifier=request.id))

    def test_semantically_equivalent_novel_code_is_not_permitted(self):
        self.tools.reproduced = True
        result = self.tools.dispatch(self.edit(NOVEL))
        self.assertEqual(result["execution"], "proposal_only")
        self.assertFalse(self.trust.permits(self.ws.path(SOURCE)))

    def test_edit_invalidates_public_result(self):
        self.tools.reproduced = True
        self.tools.public_result = {"status": "passed", "source_sha256": self.ws.digest}
        self.tools.dispatch(self.edit())
        self.assertIsNone(self.tools.public_result)

    def test_frozen_workspace_denies_write_and_closed_tools_deny_read(self):
        self.ws.frozen = True
        with self.assertRaises(AuthorityError):
            self.ws.replace(**self.edit().args)
        self.tools.closed = True
        with self.assertRaises(AuthorityError):
            self.tools.dispatch(action("list_files"))

    def test_probe_copy_tampering_detected(self):
        self.ws.path("public/PublicProbe.java").write_text("tampered", encoding="utf-8")
        with self.assertRaises(AuthorityError):
            self.ws.verify_public_copy(self.trust)

    def test_protected_probe_and_allowlist_tampering_detected(self):
        for relative in ("evaluation/IndependentProbe.java", "evaluation/trusted.json"):
            target = self.repo / relative
            original = target.read_bytes()
            target.write_bytes(original + b" ")
            with self.subTest(relative=relative), self.assertRaises(AuthorityError):
                self.trust.verify_immutable()
            target.write_bytes(original)
