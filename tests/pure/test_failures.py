import io
import json
from pathlib import Path
from unittest.mock import patch
from issue_to_patch.agent import run
from issue_to_patch.protocol import ProviderReply, parse_action
from issue_to_patch.providers import OllamaProvider, ProviderError, ScriptedProvider, ORIGINAL, REPAIRED
from issue_to_patch.runner import JavaRunner
from issue_to_patch.tools import Tools
from issue_to_patch.workspace import AuthorityError, BudgetError, SOURCE, Trust
from helpers import LocalCase, ProtocolRunnerDouble


def request(tool, args=None, identifier="test"):
    return json.dumps({"id": identifier, "tool": tool, "args": args or {}})


class Replies:
    def __init__(self, *replies, usage=None):
        self.replies, self.index, self.usage = replies, 0, usage

    def decide(self, observation):
        value = self.replies[self.index]
        self.index += 1
        if isinstance(value, BaseException):
            raise value
        return ProviderReply(value, {"provider": "unit_double", "model": None}, self.usage)


class LoopFailureTests(LocalCase):
    def execute(self, provider, **kwargs):
        return run(self.repo, provider, runner_factory=ProtocolRunnerDouble, **kwargs)

    def test_development_scripts_close_loop_with_explicit_double_label(self):
        for case in ("V01", "P01", "T01"):
            report, output = self.execute(ScriptedProvider(case_id=case, repo=self.repo), case_id=case)
            self.assertEqual(report["status"], "ACCEPTED")
            self.assertEqual(report["evidence_kind"], "scripted_protocol_double")
            self.assertEqual(report["commands"], [])
            self.assertIsNone(report["live_heldout_solve_rate"])
            trace = (output / "trace.jsonl").read_text()
            self.assertNotIn("evaluation/", trace)
            self.assertNotIn("IndependentProbe", trace)
            self.assertNotIn("independent_expected", trace)

    def test_false_fix_rejection_and_novel_proposal_are_control_flow_only(self):
        report, _ = self.execute(ScriptedProvider("false-fix"))
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(report["public_check"]["status"], "passed")
        novel, _ = self.execute(ScriptedProvider("novel"))
        self.assertEqual(novel["status"], "REVIEW_REQUIRED")
        self.assertEqual(novel["post_edit_processes"], 0)
        self.assertEqual(novel["independent"]["status"], "not_run")

    def test_one_protocol_correction_then_abstention(self):
        report, _ = self.execute(Replies("bad json", request("abstain", {"reason": "cannot proceed"})))
        self.assertEqual(report["status"], "ABSTAINED")
        self.assertEqual(report["decisions"], 2)

    def test_second_protocol_error_terminates_without_tool_execution(self):
        report, _ = self.execute(Replies("bad json", "bad json"))
        self.assertEqual(report["status"], "POLICY_DENIED")
        self.assertEqual(report["commands"], [])

    def test_unknown_tool_denied_and_not_retried_indefinitely(self):
        raw = request("shell", {"command": "java"})
        report, _ = self.execute(Replies(raw, raw))
        self.assertEqual(report["status"], "POLICY_DENIED")

    def test_denied_finish_is_recorded_and_never_evaluated(self):
        report, output = self.execute(Replies(request("finish", {"summary": "PASS"})))
        self.assertEqual(report["status"], "POLICY_DENIED")
        self.assertEqual(report["independent"]["status"], "not_run")
        self.assertEqual(json.loads((output / "trace.jsonl").read_text())["result"]["status"], "denied")

    def test_decision_limit_stops_before_next_provider_request(self):
        provider = Replies(request("list_files", identifier="one"), request("list_files", identifier="two"))
        report, _ = self.execute(provider, max_decisions=1)
        self.assertEqual(report["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(provider.index, 1)

    def test_wall_limit_after_provider_prevents_tool_action(self):
        current = [100.0]
        class SlowDouble:
            def decide(self, observation):
                current[0] += 3
                return ProviderReply(request("run_check", {"check": "public"}), {"provider": "unit_double"})
        with patch("issue_to_patch.agent.time.monotonic", side_effect=lambda: current[0]):
            report, _ = self.execute(SlowDouble(), wall_seconds=2)
        self.assertEqual(report["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(report["public_checks"], 0)

    def test_observed_token_limit_prevents_tool_action(self):
        provider = Replies(request("run_check", {"check": "public"}), usage={"prompt_eval_count": 10, "eval_count": 2})
        report, _ = self.execute(provider, max_observed_tokens=11)
        self.assertEqual(report["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(report["observed_tokens"], 12)
        self.assertEqual(report["public_checks"], 0)

    def test_unknown_usage_is_explicit_and_not_estimated(self):
        provider = Replies(request("abstain", {"reason": "none"}), usage={"prompt_eval_count": None, "eval_count": None})
        report, _ = self.execute(provider)
        self.assertFalse(report["token_usage_complete"])
        self.assertIsNone(report["model_usage"][0]["eval_count"])

    def test_provider_failure_has_no_fallback_or_retry(self):
        provider = Replies(ProviderError("injected timeout"))
        report, _ = self.execute(provider)
        self.assertEqual(report["status"], "INFRA_ERROR")
        self.assertEqual(provider.index, 1)
        self.assertEqual(report["commands"], [])

    def test_keyboard_cancellation_saves_report_without_evaluation(self):
        report, _ = self.execute(Replies(KeyboardInterrupt()))
        self.assertEqual((report["status"], report["exit_code"]), ("CANCELLED", 130))
        self.assertEqual(report["independent"]["status"], "not_run")

    def test_infrastructure_failures_never_count_as_reproduction(self):
        for status in ("infrastructure_error", "compile_error", "probe_error"):
            class FailureDouble(ProtocolRunnerDouble):
                def observe(self, ws, independent=False):
                    return {"status": status, "source_sha256": ws.digest}
            report, _ = run(self.repo, Replies(request("run_check", {"check": "public"})), runner_factory=FailureDouble)
            self.assertEqual(report["status"], "INFRA_ERROR")
            self.assertEqual(report["patch_attempts"], 0)

    def test_passing_original_stops_as_not_reproduced(self):
        class PassingDouble(ProtocolRunnerDouble):
            def observe(self, ws, independent=False):
                return {"status": "observed", "source_sha256": ws.digest,
                        "output": "-1\tfalse\t200\t0\n0\tfalse\t200\t0\n5\ttrue\t195\t1\n"}
        report, _ = run(self.repo, Replies(request("run_check", {"check": "public"})), runner_factory=PassingDouble)
        self.assertEqual(report["status"], "NOT_REPRODUCED")
        self.assertEqual(report["patch_attempts"], 0)


class EditBudgetTests(LocalCase):
    def test_check_budget_has_distinct_budget_error(self):
        ws, trust = self.workspace()
        tools = Tools(ws, ProtocolRunnerDouble(self.repo, trust), trust)
        for index in range(5):
            tools.dispatch(parse_action(request("run_check", {"check": "public"}, str(index))))
        with self.assertRaises(BudgetError):
            tools.dispatch(parse_action(request("run_check", {"check": "public"}, "six")))
        self.assertEqual(tools.checks, 5)

    def test_patch_and_changed_line_limits_preserve_source(self):
        ws, _ = self.workspace()
        for old, new in ((ORIGINAL, REPAIRED), (REPAIRED, ORIGINAL), (ORIGINAL, REPAIRED)):
            ws.replace(SOURCE, ws.digest, old, new)
        digest = ws.digest
        with self.assertRaises(BudgetError):
            ws.replace(SOURCE, digest, REPAIRED, ORIGINAL)
        self.assertEqual(ws.digest, digest)
        other, _ = self.workspace(name="lines")
        other.changed_lines = 199
        with self.assertRaises(BudgetError):
            other.replace(SOURCE, other.digest, ORIGINAL, REPAIRED)
        self.assertEqual(other.digest, other.original_digest)

    def test_invalid_match_and_failed_atomic_edit_preserve_source(self):
        ws, _ = self.workspace()
        for old in ("missing text", "quantity"):
            with self.assertRaises(AuthorityError):
                ws.replace(SOURCE, ws.digest, old, "new")
        with patch("issue_to_patch.workspace.os.replace", side_effect=OSError("injected edit commit failure")):
            with self.assertRaises(OSError):
                ws.replace(SOURCE, ws.digest, ORIGINAL, REPAIRED)
        self.assertEqual(ws.digest, ws.original_digest)
        self.assertEqual(ws.patch_attempts, 0)

    def test_finish_rejects_stale_public_digest(self):
        ws, trust = self.workspace()
        tools = Tools(ws, None, trust)
        tools.reproduced = True
        tools.public_result = {"status": "passed", "source_sha256": ws.digest}
        ws.replace(SOURCE, ws.digest, ORIGINAL, REPAIRED)
        with self.assertRaises(AuthorityError):
            tools.dispatch(parse_action(request("finish", {"summary": "stale"})))


class ProviderMockTests(LocalCase):
    def provider(self):
        return OllamaProvider("fictional", allow_local_model=True)

    def test_endpoint_and_opt_in_restrictions_before_transport(self):
        with self.assertRaises(ProviderError):
            OllamaProvider("fictional")
        for endpoint in ("https://127.0.0.1", "http://localhost", "http://example.invalid", "http://127.0.0.1/path",
                         "http://user:pass@127.0.0.1", "http://127.0.0.1?x=1", "http://127.0.0.1:bad", "http://127.0.0.1#x"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ProviderError):
                OllamaProvider("fictional", endpoint, allow_local_model=True)

    def test_mock_transport_rejects_redirect_malformed_usage_and_large_response(self):
        valid = {"model": "fictional", "done": True, "message": {"role": "assistant", "content": request("list_files")},
                 "prompt_eval_count": 1, "eval_count": 2}
        bad_usage = dict(valid, eval_count=True)
        wrong_model = dict(valid, model="different")
        for status, raw in ((302, b"redirect"), (200, b"not json"), (200, b"x" * 65537),
                            (200, json.dumps(bad_usage).encode()), (200, json.dumps(wrong_model).encode())):
            with patch("issue_to_patch.providers.http.client.HTTPConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status, response.read.return_value = status, raw
                provider = self.provider()
                with self.assertRaises(ProviderError):
                    provider.decide({"state": "INSPECTING"})
                self.assertEqual(provider.request_count, 1)
                connection.return_value.close.assert_called_once()
                connection.return_value.request.assert_called_once()

    def test_context_limit_prevents_transport_creation(self):
        with patch("issue_to_patch.providers.http.client.HTTPConnection") as connection:
            provider = self.provider()
            with self.assertRaises(ProviderError):
                provider.decide({"source": "x" * 65536})
            connection.assert_not_called()
            self.assertEqual(provider.request_count, 0)


class SynchronousThread:
    def __init__(self, target, args, **kwargs):
        self.target, self.args = target, args
    def start(self):
        self.target(*self.args)
    def join(self, **kwargs):
        pass


class ProcessDouble:
    def __init__(self, output=b""):
        self.stdout, self.stderr = io.BytesIO(output), io.BytesIO()
        self.returncode, self.kills, self.waits = None, 0, 0
    def poll(self):
        return self.returncode
    def kill(self):
        self.kills += 1
        self.returncode = -9
    def wait(self):
        self.waits += 1
        return self.returncode


class ProcessOwnershipTests(LocalCase):
    def runner(self):
        return JavaRunner(self.repo, Trust(self.repo))

    def test_expired_deadline_prevents_process_launch(self):
        runner = self.runner()
        runner.deadline = 0
        with patch("issue_to_patch.runner.subprocess.Popen") as popen, self.assertRaises(BudgetError):
            runner._run(["fictional"], self.repo, 1)
        popen.assert_not_called()

    def test_timeout_kills_and_reaps_only_owned_process_double(self):
        proc, clock = ProcessDouble(), [0.0]
        def tick():
            clock[0] += 1
            return clock[0]
        with patch("issue_to_patch.runner.subprocess.Popen", return_value=proc), \
                patch("issue_to_patch.runner.threading.Thread", SynchronousThread), \
                patch("issue_to_patch.runner.time.monotonic", side_effect=tick):
            result = self.runner()._run(["fictional"], self.repo, 0.1)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual((proc.kills, proc.waits), (1, 1))
        self.assertTrue(proc.stdout.closed and proc.stderr.closed)

    def test_output_overflow_kills_reaps_and_caps_double_output(self):
        proc = ProcessDouble(b"x" * 300000)
        with patch("issue_to_patch.runner.subprocess.Popen", return_value=proc), \
                patch("issue_to_patch.runner.threading.Thread", SynchronousThread):
            result = self.runner()._run(["fictional"], self.repo, 1)
        self.assertEqual(result["status"], "output_limit")
        self.assertEqual(len(result["stdout"].encode()), 262144)
        self.assertEqual((proc.kills, proc.waits), (1, 1))

    def test_cancellation_kills_reaps_and_closes_owned_double(self):
        proc = ProcessDouble()
        with patch("issue_to_patch.runner.subprocess.Popen", return_value=proc), \
                patch("issue_to_patch.runner.threading.Thread", SynchronousThread), \
                patch("issue_to_patch.runner.time.sleep", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.runner()._run(["fictional"], self.repo, 30)
        self.assertEqual((proc.kills, proc.waits), (1, 1))
        self.assertTrue(proc.stdout.closed and proc.stderr.closed)
