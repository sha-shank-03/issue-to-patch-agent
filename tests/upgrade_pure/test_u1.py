"""Pure U1 contracts: no sockets, subprocesses, Java, credentials or CLI demo launches."""
from dataclasses import replace
from contextlib import redirect_stdout, redirect_stderr
import base64
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from issue_to_patch.protocol import Action
from issue_to_patch_upgrade.core import Budget, Config, Failure, Limits, digest, encoded
from issue_to_patch_upgrade.doubles import InertGateway, completion
from issue_to_patch_upgrade.events import Events, redact
from issue_to_patch_upgrade.fixture import DATASET_HASH, FALSE_FIX, ORIGINAL, REPAIRED, SOURCE, SOURCE_PATH
from issue_to_patch_upgrade.gateway import GatewayProvider, function_tools, parse_completion
from issue_to_patch_upgrade.loop import run
from issue_to_patch_upgrade.sandbox_double import InertSandbox
from issue_to_patch_upgrade.tools import Tools
from issue_to_patch_upgrade.transport import OwnedTransport, ReservationGate, decode_worker, worker_input
from issue_to_patch_upgrade.verifier import verify

REPO = Path(__file__).resolve().parents[2]


class PureContracts(unittest.TestCase):
    recorded_reports = {}
    def setUp(self):
        from issue_to_patch_upgrade.cli import source_version
        self.code_version = source_version()
        self.config = Config("test/synthetic-coder", "test")
        self.no_process = patch("subprocess.Popen", side_effect=AssertionError("pure test must not spawn"))
        self.no_socket = patch("socket.socket", side_effect=AssertionError("pure test must not bind/connect"))
        self.no_process.start()
        self.no_socket.start()
        self.addCleanup(self.no_process.stop)
        self.addCleanup(self.no_socket.stop)

    def tool(self, name, args=None, id="a"):
        return Action(id, name, args or {})

    def reproduced(self):
        tools = Tools(InertSandbox(), self.config.limits)
        tools.execute(self.tool("run_check", {"check": "public"}, id="reproduce"))
        return tools

    def repair(self, tools, pattern=REPAIRED, id="edit"):
        return tools.execute(self.tool("replace_text", {"path": SOURCE_PATH, "old": ORIGINAL,
                             "new": pattern, "preimage_sha256": tools.source_sha256}, id=id))

    def test_explicit_configuration(self):
        for model, provider in (("", "test"), ("test/no spaces", "test"), ("test/synthetic-coder", "")):
            with self.subTest(model=model), self.assertRaises(Failure):
                Config(model, provider)
        with self.assertRaises(Failure):
            Config("openai/unselected", "openai")
        self.assertEqual(Config("openai/unselected", "openai", "live").mode, "live")

    def test_limit_validation(self):
        for kwargs in ({"requests": True}, {"wall_seconds": float("nan")}, {"request_seconds": 21}, {"edits": 4}):
            with self.subTest(kwargs=kwargs), self.assertRaises(Failure):
                Limits(**kwargs)

    def test_native_schema_has_exact_functions(self):
        tools = function_tools()
        self.assertEqual({t["function"]["name"] for t in tools}, {
            "list_files", "read_file", "search", "run_check", "replace_text", "show_diff", "finish", "abstain"})
        self.assertTrue(all(t["function"]["parameters"]["additionalProperties"] is False for t in tools))

    def test_native_call_roundtrip(self):
        reply = parse_completion(completion(self.config.model, "call_1", "list_files", {}), self.config)
        self.assertEqual((reply.action.id, reply.action.tool), ("call_1", "list_files"))
        self.assertEqual(reply.assistant_message["tool_calls"][0]["id"], reply.action.id)
        self.assertIsNone(reply.usage)

    def test_malformed_envelopes(self):
        seed = json.loads(completion(self.config.model, "call_1", "list_files", {}))
        mutations = [lambda d: d.update(model="other/model"), lambda d: d.update(choices=[]),
                     lambda d: d["choices"][0].update(index=False),
                     lambda d: d["choices"][0].update(finish_reason="length"),
                     lambda d: d["choices"][0]["message"].update(content='{"tool":"finish"}'),
                     lambda d: d["choices"][0]["message"].update(refusal="denied"),
                     lambda d: d["choices"][0]["message"].update(tool_calls=[]),
                     lambda d: d["choices"][0]["message"]["tool_calls"].append(d["choices"][0]["message"]["tool_calls"][0])]
        for mutate in mutations:
            data = json.loads(json.dumps(seed))
            mutate(data)
            with self.subTest(mutation=mutate), self.assertRaises(Failure):
                parse_completion(encoded(data), self.config)

    def test_duplicate_and_nonfinite_json(self):
        for raw in (b'{"id":1,"id":2}', b'{"x":NaN}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(Failure):
                parse_completion(raw, self.config)

    def test_unknown_function_and_bad_arguments(self):
        for name, args in (("shell", {}), ("list_files", {"extra": 1}), ("read_file", {"path":SOURCE_PATH,
                           "start_line":True,"max_lines":10}), ("run_check", {"check":"private"})):
            with self.subTest(name=name), self.assertRaises(Failure):
                parse_completion(completion(self.config.model, "call_1", name, args), self.config)
        raw = json.loads(completion(self.config.model, "call_1", "list_files", {}))
        raw["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = []
        with self.assertRaises(Failure):
            parse_completion(encoded(raw), self.config)

    def test_usage_validation(self):
        for usage in ({"prompt_tokens":1,"completion_tokens":2,"total_tokens":4},
                      {"prompt_tokens":True,"completion_tokens":0,"total_tokens":1},
                      {"prompt_tokens":1,"completion_tokens":2049,"total_tokens":2050}):
            with self.subTest(usage=usage), self.assertRaises(Failure):
                parse_completion(completion(self.config.model,"call_1","list_files",{},usage=usage), self.config)

    def test_response_cap(self):
        config = replace(self.config, limits=replace(self.config.limits, response_bytes=10))
        with self.assertRaises(Failure):
            parse_completion(completion(config.model,"call_1","list_files",{}), config)

    def test_provider_sends_native_routing_fields(self):
        transport = InertGateway()
        provider = GatewayProvider(self.config, transport)
        provider.decide([{"role":"user","content":"fixture"}], Budget(self.config.limits))
        request = transport.requests[0]
        self.assertEqual(request["providerOptions"], {"gateway":{"only":["test"]}})
        self.assertFalse(request["stream"])
        self.assertFalse(request["parallel_tool_calls"])
        self.assertNotIn("response_format", request)
        self.assertEqual(request["max_tokens"], 2048)

    def test_history_and_request_caps_before_exchange(self):
        transport = InertGateway()
        config = replace(self.config, limits=replace(self.config.limits, history_bytes=10))
        with self.assertRaises(Failure):
            GatewayProvider(config, transport).decide([{"role":"user","content":"too large"}], Budget(config.limits))
        self.assertEqual(transport.requests, [])
        config = replace(self.config, limits=replace(self.config.limits, request_bytes=10))
        with self.assertRaises(Failure):
            GatewayProvider(config, transport).decide([], Budget(config.limits))
        self.assertEqual(transport.requests, [])

    def test_request_tool_token_deadline_counters(self):
        now = [10.0]
        limits = Limits(requests=1,tools=1,tokens=5,wall_seconds=2)
        budget = Budget(limits,clock=lambda:now[0])
        budget.request()
        with self.assertRaises(Failure): budget.request()
        budget.tool()
        with self.assertRaises(Failure): budget.tool()
        budget.usage({"total_tokens":5})
        with self.assertRaises(Failure): budget.check()
        now[0] = 13
        self.assertEqual(budget.snapshot()["active_seconds"],3)
        self.assertEqual(budget.snapshot()["requests"],1)
        with self.assertRaises(Failure): budget.check()

    def test_mutation_requires_reproduction(self):
        tools = Tools(InertSandbox(), self.config.limits)
        with self.assertRaises(Failure): self.repair(tools)
        self.assertEqual(tools.source, SOURCE)

    def test_manifest_paths_and_protected_edits(self):
        for path in ("../evaluation.py", "C:/secret", "\\\\server\\share", "src/QuantityApi.java:stream", "issue.md"):
            tools = self.reproduced()
            with self.subTest(path=path), self.assertRaises(Failure):
                tools.execute(self.tool("replace_text", {"path":path,"old":ORIGINAL,"new":REPAIRED,
                                                         "preimage_sha256":tools.source_sha256}))
            self.assertEqual(tools.source, SOURCE)

    def test_wrong_preimage_and_old_match(self):
        for old, sha in ((ORIGINAL,"0"*64),("not present",digest(SOURCE))):
            tools = self.reproduced()
            with self.subTest(old=old), self.assertRaises(Failure):
                tools.execute(self.tool("replace_text", {"path":SOURCE_PATH,"old":old,"new":REPAIRED,"preimage_sha256":sha}))
            self.assertEqual(tools.edits,0)

    def test_duplicate_id_is_idempotent_and_conflict_denied(self):
        tools = self.reproduced()
        action = self.tool("replace_text", {"path":SOURCE_PATH,"old":ORIGINAL,"new":REPAIRED,
                                            "preimage_sha256":tools.source_sha256})
        tools.execute(action)
        self.assertTrue(tools.execute(action)["idempotent_replay"])
        self.assertEqual(tools.edits,1)
        with self.assertRaises(Failure): tools.execute(self.tool("show_diff",id="a"))

    def test_finish_requires_current_public_and_changed_source(self):
        tools = self.reproduced()
        self.repair(tools)
        with self.assertRaises(Failure): tools.execute(self.tool("finish", {"summary":"untrusted"}, id="finish"))
        tools.execute(self.tool("run_check", {"check":"public"}, id="public"))
        self.assertEqual(tools.execute(self.tool("finish", {"summary":"review"}, id="finish"))["status"],"finish_requested")
        tools.seal()
        with self.assertRaises(Failure): tools.execute(self.tool("show_diff",id="after"))

    def test_independent_verifier_sealing_and_hash(self):
        tools = self.reproduced()
        self.repair(tools)
        tools.execute(self.tool("run_check", {"check":"public"}, id="public"))
        candidate = tools.seal()
        result = verify(candidate,actor_closed=True)
        self.assertEqual(result["status"],"simulated_contract_pass")
        self.assertFalse(result["domain_verified"])
        self.assertEqual(verify(candidate,actor_closed=False)["status"],"proposal_invalid")
        self.assertEqual(verify(replace(candidate,source=SOURCE),actor_closed=True)["status"],"proposal_invalid")

    def test_public_pass_false_fix_independently_rejected(self):
        tools = self.reproduced()
        self.repair(tools,FALSE_FIX)
        self.assertEqual(tools.execute(self.tool("run_check", {"check":"public"}, id="public"))["status"],"passed")
        result = verify(tools.seal(),actor_closed=True)
        self.assertEqual((result["status"],result["simulated_passed"]), ("simulated_contract_rejected",5))

    def test_unknown_source_never_executed(self):
        with self.assertRaises(Failure): InertSandbox().observe("arbitrary generated Java",(1,))
        self.assertEqual(InertSandbox.generated_code_processes,0)

    def test_pure_feedback_loop_native_correlation(self):
        transport = InertGateway()
        report = run(GatewayProvider(self.config,transport),InertSandbox(),self.config,code_version=self.code_version)
        self.recorded_reports["repair"] = report
        self.assertEqual((report["status"],report["edits"],report["public_checks"]), ("CONTRACT_COMPLETE",2,3))
        self.assertFalse(report["independent"]["domain_verified"])
        self.assertEqual(report["generated_code_host_processes"],0)
        tools = [m for m in report["messages"] if m["role"]=="tool"]
        self.assertEqual(len(tools),10)
        self.assertEqual([json.loads(m["content"])["status"] for m in tools if
                          json.loads(m["content"])["status"]=="semantic_failure"],["semantic_failure","semantic_failure"])
        for index in range(2,len(report["messages"]),2):
            self.assertEqual(report["messages"][index]["tool_calls"][0]["id"],report["messages"][index+1]["tool_call_id"])
        self.assertEqual(report["dataset_sha256"],DATASET_HASH)
        self.assertIsNone(report["actual_model_tokens"])

    def test_failures_stop_without_retry_or_false_completion(self):
        expected = {"http-401":"AUTHORIZATION_DENIED","http-402":"FUNDS_DENIED","http-429":"RATE_LIMITED",
                    "http-503":"PROVIDER_ERROR","malformed":"PROTOCOL_ERROR","unknown-tool":"PROTOCOL_ERROR",
                    "early-finish":"POLICY_DENIED","ambiguous-loss":"TRANSPORT_ERROR"}
        for scenario, state in expected.items():
            transport = InertGateway(scenario)
            report = run(GatewayProvider(self.config,transport),InertSandbox(),self.config,code_version=self.code_version)
            with self.subTest(scenario=scenario):
                self.assertEqual(report["status"],state)
                self.assertEqual(report["budget"]["requests"],1)
                self.assertEqual(report["edits"],0)
                self.assertTrue(report["actor_closed"])
                self.assertEqual(report["independent"]["status"],"not_run")
                self.recorded_reports[scenario] = report

    def test_run_request_bound_and_cancellation(self):
        config = replace(self.config,limits=replace(self.config.limits,requests=2))
        transport = InertGateway()
        report = run(GatewayProvider(config,transport),InertSandbox(),config)
        self.assertEqual((report["status"],report["budget"]["requests"]),("BUDGET_EXHAUSTED",2))
        report = run(GatewayProvider(self.config,InertGateway()),InertSandbox(),self.config,cancel=lambda:True)
        self.assertEqual((report["status"],report["budget"]["requests"]),("CANCELLED",0))

    def test_deadline_after_response_prevents_tool_effect(self):
        now = [0.0]
        config = replace(self.config,limits=replace(self.config.limits,wall_seconds=2))
        class AdvancingDouble(InertGateway):
            def exchange(self,body,*,budget,cancel=None):
                result = super().exchange(body,budget=budget,cancel=cancel)
                now[0] += 3
                return result
        report = run(GatewayProvider(config,AdvancingDouble()),InertSandbox(),config,clock=lambda:now[0])
        self.assertEqual((report["status"],report["budget"]["requests"],report["budget"]["tool_attempts"]),
                         ("BUDGET_EXHAUSTED",1,0))
        self.assertEqual(report["budget"]["active_seconds"],3)

    def test_forged_public_observation_is_not_verifier_truth(self):
        tools=self.reproduced()
        self.repair(tools)
        tools.execute(self.tool("run_check",{"check":"public"},id="public"))
        candidate=tools.seal()
        bad={**candidate.public_result,"records":[{"quantity":0,"accepted":True}]}
        self.assertEqual(verify(replace(candidate,public_result=bad),actor_closed=True)["status"],"proposal_invalid")

    def test_invalid_transport_shape_is_typed(self):
        class BadDouble(InertGateway):
            def exchange(self,*args,**kwargs):
                from issue_to_patch_upgrade.transport import Response
                return Response(200,None)
        report=run(GatewayProvider(self.config,BadDouble()),InertSandbox(),self.config)
        self.assertEqual((report["status"],report["error"]),("TRANSPORT_ERROR","invalid_transport_reply"))

    def test_cli_resume_preserves_counters_and_gateway_has_no_fallback(self):
        from issue_to_patch_upgrade.cli import main
        saved={"run_id":"1"*32,"budget":{"requests":7,"tool_attempts":9,"active_seconds":14}}
        output=io.StringIO()
        with patch("issue_to_patch_upgrade.cli.load_report",return_value=saved),redirect_stdout(output):
            code=main(["resume","--run","1"*32])
        self.assertEqual(code,3)
        self.assertEqual(json.loads(output.getvalue())["preserved_budget"],saved["budget"])
        errors=io.StringIO()
        with redirect_stderr(errors):
            code=main(["run","--provider","gateway","--model","openai/unselected","--serving-provider","openai"])
        self.assertEqual(code,3)
        self.assertEqual(json.loads(errors.getvalue())["status"],"AUTHORIZATION_DENIED")

    def test_live_cannot_use_inert_sandbox_or_read_key(self):
        config = Config("openai/unselected","openai","live")
        with self.assertRaises(Failure): run(None,InertSandbox(),config)
        transport = OwnedTransport(config)
        with self.assertRaises(Failure): transport.exchange(b"{}",budget=Budget(config.limits))
        self.assertEqual(transport.started,0)

    def test_per_run_cost_gate_unknown_zero_and_held_reservation(self):
        config = Config("openai/unselected","openai","live")
        for gate in (ReservationGate(), ReservationGate(authorized=True,allocation_inr=1,quote_inr=None)):
            with self.assertRaises(Failure): gate.reserve(config)
        gate = ReservationGate(authorized=True,allocation_inr="2",quote_inr="1.25",model=config.model,
                               serving_provider=config.serving_provider,metadata_verified=True)
        gate.reserve(config)
        with self.assertRaises(Failure): gate.reserve(config)
        self.assertEqual(gate.snapshot()["held_reservations_inr"],"1.25")
        self.assertIsNone(gate.snapshot()["actual_cost_inr"])

    def test_worker_input_origin_and_secret_channel(self):
        data = json.loads(worker_input(self.config,b"{}",10,port=54321))
        self.assertIsNone(data["credential"])
        self.assertNotIn("host",data)
        with self.assertRaises(Failure): worker_input(self.config,b"{}",10,port=1,credential="synthetic")
        with self.assertRaises(Failure): worker_input(Config("openai/unselected","openai","live"),b"{}",10,credential="bad\r\nkey")

    def test_worker_reply_limits_and_discard_error_text(self):
        result = decode_worker(encoded({"status":200,"body":base64.b64encode(b"{}").decode(),"error":None,"ambiguous":False}),10)
        self.assertEqual(result.body,b"{}")
        for record in ({"status":200,"body":"not base64!","error":None,"ambiguous":False},
                       {"status":None,"body":"canary","error":"raw-secret-canary","ambiguous":True}):
            with self.assertRaises(Failure) as ctx: decode_worker(encoded(record),10)
            self.assertNotIn("canary",str(ctx.exception))

    def test_telemetry_redacts_canaries_nested_keys_and_bearer(self):
        secret = "synthetic-canary-no-credential"
        value = {"authorization":"Bearer " + secret,"child":[{"text":"prefix " + secret}],
                 "model":"test/synthetic-coder","usage":{"total_tokens":12},"text":"sk-proj-synthetic API_KEY=synthetic"}
        cleaned = redact(value,(secret,))
        self.assertNotIn(secret,json.dumps(cleaned))
        self.assertNotIn("sk-proj-synthetic",json.dumps(cleaned))
        self.assertEqual(cleaned["usage"]["total_tokens"],12)
        events = Events({"mode":"local-double"},Budget(self.config.limits),(secret,))
        events.append("error",error=secret)
        self.assertNotIn(secret,json.dumps(events.records))

    def test_event_cap_and_terminal_budget_evidence(self):
        events = Events({},Budget(self.config.limits))
        with self.assertRaises(Failure): events.append("oversize",value="x"*65537)
        self.assertEqual(events.records,[])

    def test_private_verifier_records_not_in_acting_history(self):
        report = run(GatewayProvider(self.config,InertGateway()),InertSandbox(),self.config)
        messages = encoded(report["messages"]).decode()
        self.assertNotIn('"quantity":100',messages)
        self.assertNotIn("raw_simulated_records",messages)
        self.assertEqual(report["events"][-2]["kind"],"actor_closed")

    def test_original_frozen_source_and_guard_preserved(self):
        from scripts.freeze import verify as verify_freeze
        freeze = verify_freeze(REPO)
        self.assertEqual(freeze["freeze_sha256"],"14e1c6d5f476550fa308e91433e24718e9e0a53801441dc25675cfb658eea34c")
        self.assertEqual(freeze["trust_sha256"],"70fed424125df3b9bb02b33ede90fadb056358d5d56949ebb1cac241807fc86e")
        text = (REPO/"issue_to_patch/runner.py").read_text(encoding="utf-8")
        self.assertIn("permits",text)

    def test_new_python_source_compiles_in_memory(self):
        paths = list((REPO/"issue_to_patch_upgrade").glob("*.py"))
        paths += list((REPO/"tests/upgrade_transport").glob("*.py"))
        paths += [REPO/"scripts/upgrade_acceptance.py"]
        for path in paths:
            with self.subTest(path=path.name): compile(path.read_text(encoding="utf-8"),path.name,"exec")


if __name__ == "__main__":
    unittest.main()

