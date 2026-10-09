"""Lease-only actual loopback HTTP edge contracts, with no model server."""
import http.server
import json
import threading
import unittest
from issue_to_patch.protocol import parse_action
from issue_to_patch.providers import OllamaProvider, ProviderError
from test_provider_runner import DoubleHandler


class AdditionalProviderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), DoubleHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        DoubleHandler.requests = []
        DoubleHandler.status_code, DoubleHandler.delay = 200, 0
        self.valid = {"model": "fictional-edge", "done": True,
                      "message": {"role": "assistant", "content": '{"id":"a","tool":"list_files","args":{}}'}}

    def provider(self):
        return OllamaProvider("fictional-edge", self.endpoint, allow_local_model=True)

    def send(self, raw):
        DoubleHandler.response_bytes = raw
        return self.provider().decide({"state": "INSPECTING"})

    def test_missing_usage_round_trips_as_unknown(self):
        reply = self.send(json.dumps(self.valid).encode())
        self.assertEqual(reply.usage, {"prompt_eval_count": None, "eval_count": None})
        self.assertEqual(parse_action(reply.action_json).tool, "list_files")

    def test_exact_byte_limit_accepted_and_one_byte_over_rejected(self):
        padded = dict(self.valid, padding="")
        base = json.dumps(padded).encode()
        padded["padding"] = "x" * (65536 - len(base))
        raw = json.dumps(padded).encode()
        self.assertEqual(len(raw), 65536)
        self.assertEqual(parse_action(self.send(raw).action_json).tool, "list_files")
        with self.assertRaises(ProviderError):
            self.send(raw + b" ")

    def test_invalid_utf8_and_non_object_json_are_rejected(self):
        for raw in (b"\xff", b"[]", b"null", b"true"):
            with self.subTest(raw=raw), self.assertRaises(ProviderError):
                self.send(raw)

    def test_native_tool_calls_wrong_roles_and_content_types_are_rejected(self):
        for message in ({"role": "user", "content": "{}"}, {"role": "assistant", "content": {}},
                        {"role": "assistant", "content": "{}", "tool_calls": [{"name": "shell"}]}):
            with self.subTest(message=message), self.assertRaises(ProviderError):
                self.send(json.dumps(dict(self.valid, message=message)).encode())

    def test_context_cap_blocks_transport_before_any_server_request(self):
        provider = self.provider()
        with self.assertRaises(ProviderError):
            provider.decide({"source": "x" * 65536})
        self.assertEqual(provider.request_count, 0)
        self.assertEqual(DoubleHandler.requests, [])
