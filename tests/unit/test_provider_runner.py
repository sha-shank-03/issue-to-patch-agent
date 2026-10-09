import http.server
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest

from issue_to_patch.protocol import ProtocolError, parse_action
from issue_to_patch.providers import OllamaProvider, ProviderError, ScriptedProvider
from issue_to_patch.runner import JavaRunner, parse_observations
from issue_to_patch.workspace import AuthorityError

REPO = Path(__file__).resolve().parents[2]


class DoubleHandler(http.server.BaseHTTPRequestHandler):
    response_bytes = b""
    status_code = 200
    delay = 0
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).requests.append({"path": self.path, "body": json.loads(body)})
        time.sleep(type(self).delay)
        try:
            self.send_response(type(self).status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(type(self).response_bytes)))
            if type(self).status_code == 302:
                self.send_header("Location", "http://example.invalid/do-not-follow")
            self.end_headers()
            self.wfile.write(type(self).response_bytes)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *args):
        pass


class ProviderContractTests(unittest.TestCase):
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
        self.response = {"model": "fictional-test-model", "done": True,
                         "message": {"role": "assistant", "content": json.dumps({"id": "double", "tool": "list_files", "args": {}})},
                         "prompt_eval_count": 13, "eval_count": 7}
        DoubleHandler.requests = []
        DoubleHandler.status_code, DoubleHandler.delay = 200, 0
        self.send(self.response)

    def send(self, data):
        DoubleHandler.response_bytes = json.dumps(data).encode("utf-8")

    def provider(self, **kwargs):
        return OllamaProvider("fictional-test-model", self.endpoint, allow_local_model=True, **kwargs)

    def test_actual_http_contract_schema_history_and_usage(self):
        reply = self.provider().decide({"state": "INSPECTING", "source": "fictional"})
        self.assertEqual(parse_action(reply.action_json).tool, "list_files")
        self.assertEqual(reply.usage, {"prompt_eval_count": 13, "eval_count": 7})
        request = DoubleHandler.requests[0]
        self.assertEqual(request["path"], "/api/chat")
        self.assertFalse(request["body"]["stream"])
        self.assertIn("oneOf", request["body"]["format"])
        self.assertEqual(json.loads(request["body"]["messages"][1]["content"])["source"], "fictional")

    def test_opt_in_and_remote_endpoints_denied_without_requests(self):
        with self.assertRaises(ProviderError):
            OllamaProvider("fictional-test-model")
        for endpoint in ("https://127.0.0.1:1", "http://example.invalid", "http://localhost", "http://127.0.0.1/api/chat", "http://x@127.0.0.1"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ProviderError):
                OllamaProvider("fictional-test-model", endpoint, allow_local_model=True)
        self.assertEqual(DoubleHandler.requests, [])

    def test_http_failures_and_redirect_have_no_retry_or_fallback(self):
        for status in (302, 429, 503):
            DoubleHandler.status_code = status
            before = len(DoubleHandler.requests)
            with self.subTest(status=status), self.assertRaises(ProviderError):
                self.provider().decide({})
            self.assertEqual(len(DoubleHandler.requests), before + 1)

    def test_wrong_native_metadata_and_usage_denied(self):
        for changes in ({"model": "different"}, {"done": False}, {"eval_count": True}, {"prompt_eval_count": -1}, {"message": {"content": "{}"}}):
            self.send(dict(self.response, **changes))
            with self.subTest(changes=changes), self.assertRaises(ProviderError):
                self.provider().decide({})

    def test_malformed_and_oversized_responses_denied(self):
        for content in (b"not-json", b"x" * 65537, b'{"done":true,"done":true}'):
            DoubleHandler.response_bytes = content
            with self.subTest(size=len(content)), self.assertRaises(ProviderError):
                self.provider().decide({})

    def test_unknown_model_action_denied_at_dispatch_protocol(self):
        self.response["message"]["content"] = '{"id":"bad","tool":"shell","args":{}}'
        self.send(self.response)
        reply = self.provider().decide({})
        with self.assertRaises(ProtocolError):
            parse_action(reply.action_json)

    def test_read_timeout_is_bounded(self):
        DoubleHandler.delay = 0.15
        started = time.monotonic()
        with self.assertRaises(ProviderError):
            self.provider(timeout=0.02).decide({})
        self.assertLess(time.monotonic() - started, 1)

    def test_script_requires_actual_prior_feedback(self):
        script = ScriptedProvider()
        script.decide({"last_result": None})
        with self.assertRaises(ProviderError):
            script.decide({"last_result": {"status": "fabricated"}})


class ObservationAndProcessTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows environment contract")
    def test_windows_system_drive_is_preserved(self):
        result = JavaRunner(REPO, None)._run([sys.executable, "-c", "import os; print(os.environ.get('SystemDrive', 'missing'))"], REPO, 2)
        self.assertEqual(result["stdout"].strip(), os.environ["SystemDrive"])

    def test_missing_duplicate_and_fake_probe_records_denied(self):
        for output in ("", "PASS", "0\ttrue\t200\t1\n0\ttrue\t200\t1", "0\t1\t200\t1"):
            with self.subTest(output=output), self.assertRaises(AuthorityError):
                parse_observations(output, {0})

    def test_owned_harmless_process_timeout(self):
        result = JavaRunner(REPO, None)._run([sys.executable, "-c", "import time; time.sleep(2)"], REPO, 0.05)
        self.assertEqual(result["status"], "timeout")
        self.assertIsNotNone(result["exit_code"])

    def test_owned_harmless_output_is_capped(self):
        result = JavaRunner(REPO, None)._run([sys.executable, "-c", "print('x' * 300000)"], REPO, 2)
        self.assertEqual(result["status"], "output_limit")
        self.assertLessEqual(len(result["stdout"].encode()) + len(result["stderr"].encode()), 262144)
