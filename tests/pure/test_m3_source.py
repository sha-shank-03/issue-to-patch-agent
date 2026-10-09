import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from evaluation.development import PairedProvider, canonical_sha, regressions, semantic_context
from issue_to_patch.protocol import parse_action
from issue_to_patch.providers import OllamaProvider, ProviderError
from scripts.release_check import verify_ci

REPO = Path(__file__).resolve().parents[2]


def observation(clock=119.9):
    return {"protocol_version": 1, "case": "V01", "state": "INSPECTING", "issue": "fictional issue",
            "contract": "fictional contract", "visible_files": ["src/ShopApi.java"], "source_sha256": "a" * 64,
            "history": [], "last_result": None,
            "remaining": {"decisions": 20, "patches": 3, "public_checks": 5, "observed_tokens": 16384, "wall_seconds": clock}}


class PairedSourceTests(unittest.TestCase):
    def test_context_changes_are_detected_except_explicit_clock_telemetry(self):
        first = observation()
        other = observation(119.1)
        self.assertEqual(canonical_sha(semantic_context(first)), canonical_sha(semantic_context(other)))
        other["contract"] += " changed"
        self.assertNotEqual(canonical_sha(semantic_context(first)), canonical_sha(semantic_context(other)))
        other = copy.deepcopy(first)
        other["remaining"]["patches"] = 2
        self.assertNotEqual(canonical_sha(semantic_context(first)), canonical_sha(semantic_context(other)))

    def test_same_prefix_and_first_candidate_then_one_candidate_stops(self):
        providers = [PairedProvider("V01", mode, REPO) for mode in ("one_candidate", "feedback_loop")]
        sequences = []
        for provider in providers:
            data, actions = observation(), []
            for index, status in enumerate(("listed", "read", "searched", "semantic_failure", "edited", "semantic_failure")):
                action = parse_action(provider.decide(data).action_json)
                actions.append(action)
                data["last_result"] = {"status": status}
                if index == 4:
                    data["source_sha256"] = "b" * 64
            sequences.append(actions)
            actions.append(parse_action(provider.decide(data).action_json))
        self.assertEqual(sequences[0][:6], sequences[1][:6])
        self.assertEqual(sequences[0][6].tool, "abstain")
        self.assertEqual(sequences[1][6].tool, "replace_text")
        self.assertEqual(providers[0].first_candidate_sha256, providers[1].first_candidate_sha256)
        self.assertEqual(providers[0].prefix_sha256, providers[1].prefix_sha256)
        self.assertEqual(providers[0].prefix_action_count, 6)
        self.assertEqual((providers[0].edits, providers[1].edits), (1, 2))

    def test_held_out_or_unknown_mode_cannot_enter_paired_harness(self):
        for case, mode in (("V02", "one_candidate"), ("T03", "feedback_loop"), ("V01", "live")):
            with self.subTest(case=case, mode=mode), self.assertRaises(ValueError):
                PairedProvider(case, mode, REPO)

    def test_regressions_count_previously_passing_assertions_only(self):
        original = {"status": "rejected", "assertions": [{"id": "a", "passed": True}, {"id": "b", "passed": True}, {"id": "c", "passed": False}]}
        final = {"status": "rejected", "assertions": [{"id": "a", "passed": False}, {"id": "b", "passed": True}, {"id": "c", "passed": True}]}
        self.assertEqual(regressions(original, final), {"status": "compared", "count": 1, "denominator": 2, "ids": ["a"]})
        final["assertions"].pop()
        with self.assertRaises(ValueError):
            regressions(original, final)

    def test_infrastructure_failure_is_not_zero_regressions(self):
        result = regressions({"status": "infrastructure_error"}, {"status": "accepted"})
        self.assertEqual(result["status"], "not_comparable")
        self.assertIsNone(result["count"])
        self.assertIsNone(result["denominator"])


class ProviderBoundarySourceTests(unittest.TestCase):
    def transport(self, raw, status=200):
        provider = OllamaProvider("fictional", allow_local_model=True)
        with patch("issue_to_patch.providers.http.client.HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status, response.read.return_value = status, raw
            reply = provider.decide({"state": "INSPECTING", "issue": "data"})
            body = json.loads(connection.return_value.request.call_args.args[2])
            connection.return_value.close.assert_called_once()
            return reply, body

    def test_missing_usage_stays_null_and_request_is_native_structured_nonstreaming(self):
        raw = json.dumps({"model": "fictional", "done": True, "message": {"role": "assistant", "content": '{"id":"a","tool":"list_files","args":{}}'}}).encode()
        reply, body = self.transport(raw)
        self.assertEqual(reply.usage, {"prompt_eval_count": None, "eval_count": None})
        self.assertIsNone(body.get("tools"))
        self.assertFalse(body["stream"])
        self.assertIn("oneOf", body["format"])
        self.assertEqual(body["options"], {"temperature": 0, "num_predict": 2048})

    def test_non_object_invalid_utf8_and_nonfinite_envelope_rejected(self):
        for raw in (b"[]", b"null", b"\xff", b'{"model":"fictional","done":true,"eval_count":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ProviderError):
                self.transport(raw)

    def test_tool_calls_nonassistant_nonstring_content_and_float_usage_rejected(self):
        valid = {"model": "fictional", "done": True, "message": {"role": "assistant", "content": "{}"}}
        for message in ({"role": "user", "content": "{}"}, {"role": "assistant", "content": {}},
                        {"role": "assistant", "content": "{}", "tool_calls": [{"name": "shell"}]}):
            with self.subTest(message=message), self.assertRaises(ProviderError):
                self.transport(json.dumps(dict(valid, message=message)).encode())
        with self.assertRaises(ProviderError):
            self.transport(json.dumps(dict(valid, eval_count=1.5)).encode())

    def test_request_exception_closes_connection_without_retry(self):
        provider = OllamaProvider("fictional", allow_local_model=True)
        with patch("issue_to_patch.providers.http.client.HTTPConnection") as connection:
            connection.return_value.request.side_effect = OSError("fictional unavailable server")
            with self.assertRaises(ProviderError):
                provider.decide({})
            connection.return_value.request.assert_called_once()
            connection.return_value.close.assert_called_once()


class CiSourceTests(unittest.TestCase):
    def setUp(self):
        self.text = (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.pins = json.loads((REPO / "docs/ci-actions.json").read_text(encoding="utf-8"))

    def test_verified_pins_and_bounded_workflow_policy(self):
        verify_ci(self.text, self.pins)

    def test_moving_pin_credentials_or_missing_platform_is_rejected(self):
        for text in (self.text.replace(self.pins["actions"]["actions/checkout"]["sha"], "v7"),
                     self.text.replace("contents: read", "contents: write"),
                     self.text.replace("persist-credentials: false", "persist-credentials: true"),
                     self.text.replace("ubuntu-latest, windows-latest", "ubuntu-latest"),
                     self.text + "\n# ${{ secrets.API_KEY }}\n"):
            with self.subTest(text=text[-80:]), self.assertRaises(ValueError):
                verify_ci(text, self.pins)
