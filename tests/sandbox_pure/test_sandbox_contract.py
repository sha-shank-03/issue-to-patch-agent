"""Pure U2-A contracts: prohibit sockets, child processes and Java execution."""
import base64
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

from issue_to_patch.protocol import Action
from issue_to_patch_upgrade.core import Failure, digest, encoded
from issue_to_patch_upgrade.fixture import SOURCE
from issue_to_patch_upgrade.transport import Response
from issue_to_patch_sandbox.client import SandboxClient
from issue_to_patch_sandbox.contract import (SandboxConfig,SandboxLimits,SandboxAuthorization,Proposal,
                                            synthetic_config,upload_archive,fixed_commands,ROOT,SOURCE_PATH,PROBE_PATH)
from issue_to_patch_sandbox.synthetic import SyntheticPlane,actor_candidate,probe_plan,contract_journey
from issue_to_patch_sandbox.transport import owned_transport
from issue_to_patch_sandbox.wire import decode_request

REPO = Path(__file__).resolve().parents[2]


class PureSandboxContracts(unittest.TestCase):
    recorded = {}
    def setUp(self):
        self.no_process = patch("subprocess.Popen",side_effect=AssertionError("pure test must not spawn"))
        self.no_socket = patch("socket.socket",side_effect=AssertionError("pure test must not open sockets"))
        self.no_process.start();self.no_socket.start()
        self.addCleanup(self.no_process.stop);self.addCleanup(self.no_socket.stop)
        self.config = synthetic_config()
        self.proposal = Proposal.from_actor(actor_candidate())

    def frame(self,path,method="GET",body=b"",**fields):
        value = {"method":method,"path":path,"payload":base64.b64encode(body).decode(),"content_type":"application/json","cwd":None}
        value.update(fields)
        return encoded(value)

    def test_configuration_pins_and_no_verified_example_image(self):
        for changes in ({"image":"synthetic/jdk17:latest"},{"project_id":""},{"team_id":"wrong"},
                        {"architecture":"arm64"},{"java_major":True},{"java_major":21},{"mode":"live"}):
            with self.subTest(changes=changes),self.assertRaises(Failure): replace(self.config,**changes)
        with self.assertRaises(FrozenInstanceError): self.config.mode="live"
        example=json.loads((REPO/"config/sandbox-u2a.example.json").read_text())
        self.assertIsNone(example["live_project_id"])
        self.assertIsNone(example["verified_image"])
        self.assertIs(example["external_enabled"],False)

    def test_limit_validation(self):
        for args in ({"requests":True},{"sessions":3},{"wall_seconds":float("nan")},
                     {"wall_seconds":5,"cleanup_seconds":10},{"command_ms":99},{"upload_bytes":65537}):
            with self.subTest(args=args),self.assertRaises(Failure): SandboxLimits(**args)

    def authorization(self,config):
        return SandboxAuthorization(config.project_id,config.team_id,config.image,"a"*64,"b"*64,"20","10",True,
                                    (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())

    def test_separate_live_authorization_fail_closed_without_transport(self):
        config=SandboxConfig("prj_contract","team_contract","contract/jdk17@sha256:"+"1"*64,mode="live")
        class NotCalled:
            mode="live"
            def exchange(self,*args,**kwargs): raise AssertionError("no external request")
        with self.assertRaises(Failure): SandboxClient(config,NotCalled())
        grant=self.authorization(config)
        grant.validate(config)  # Synthetic trust input validation only, no verified image or service access.
        for changes in ({"allocation_inr":"0"},{"worst_case_inr":"NaN"},{"worst_case_inr":"21"},
                        {"credential_free_image_attested":False},{"image":"different"},
                        {"expires_at":""},{"expires_at":"2000-01-01T00:00:00+00:00"},
                        {"image_receipt_sha256":"unverified"},{"allocation_inr":True}):
            with self.subTest(changes=changes),self.assertRaises(Failure):
                SandboxClient(config,NotCalled(),authorization=replace(grant,**changes))
        with self.assertRaises(Failure): owned_transport(config)

    def test_actor_seal_before_verifier_and_tamper_controls(self):
        for changed in (replace(self.proposal,actor_closed=False),replace(self.proposal,content=b"tampered"),
                        replace(self.proposal,original_sha256="c"*64),replace(self.proposal,source_sha256="d"*64)):
            plane=SyntheticPlane();client=SandboxClient(self.config,plane)
            with self.subTest(changed=changed.source_sha256),self.assertRaises(Failure): client.execute(changed,probe_plan("verifier"))
            self.assertEqual(plane.requests,[])
        actor=actor_candidate();Proposal.from_actor(actor)
        with self.assertRaises(Failure): actor.execute(Action("after-seal","read_file",{"path":SOURCE_PATH,"start_line":1,"max_lines":10}))

    def test_probe_hash_and_expectations_cannot_be_model_arguments(self):
        plane=SyntheticPlane();client=SandboxClient(self.config,plane)
        for changes in ({"probe":b"tampered"},{"role":"arbitrary"},{"expected":((0,False),(0,True))},
                        {"expected":((True,False),)},{"expected":((0,1),)}):
            with self.subTest(changes=changes),self.assertRaises(Failure):
                client.execute(self.proposal,replace(probe_plan("verifier"),**changes))
        self.assertEqual(plane.requests,[])

    def test_regular_bounded_deterministic_archive(self):
        plan=probe_plan("verifier")
        data=upload_archive(self.proposal,plan,self.config.limits)
        self.assertEqual(data,upload_archive(self.proposal,plan,self.config.limits))
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
            self.assertEqual(archive.getnames(),[SOURCE_PATH,PROBE_PATH])
            self.assertTrue(all(m.isfile() and m.mode==0o644 and m.mtime==0 for m in archive.getmembers()))
            self.assertEqual(archive.extractfile(SOURCE_PATH).read(),self.proposal.content)
            self.assertEqual(archive.extractfile(PROBE_PATH).read(),plan.probe)
        with self.assertRaises(Failure):
            upload_archive(replace(self.proposal,content=b"x"*32769,source_sha256=hashlib.sha256(b"x"*32769).hexdigest()),plan,self.config.limits)

    def test_fixed_host_routes_queries_and_headers(self):
        name="ipa-"+"a"*32+"-public-1"
        good="/v2/sandboxes/"+name+"?teamId=team_synthetic&projectId=prj_synthetic&resume=false"
        decode_request(self.frame(good))
        for path in ("https://evil.example/", "//evil.example/path", "/v9/sandboxes",good.replace("false","true"),
                     good+"&resume=false",good+"&key=secret",good.replace("/v2/","/%76%32/"),good+"#fragment"):
            with self.subTest(path=path),self.assertRaises(Failure): decode_request(self.frame(path))
        with self.assertRaises(Failure): decode_request(self.frame(good,cwd="C:/host"))
        with self.assertRaises(Failure): decode_request(self.frame(good,method=["GET"]))
        with self.assertRaises(Failure): decode_request(self.frame(good,payload="not base64"))

    def test_shell_environment_and_wrong_commands_denied_at_wire(self):
        path="/v2/sandboxes/sessions/sbx_1/cmd?teamId=team_synthetic"
        _,program,args=fixed_commands(self.config)[0]
        body={"command":program,"args":args,"cwd":ROOT,"env":{},"sudo":False,"wait":False,
              "logs":False,"attachStdin":False,"timeout":15000}
        decode_request(self.frame(path,"POST",encoded(body)))
        for change in ({"command":"bash","args":["-c","echo unsafe"]},{"env":{"TOKEN":"synthetic"}},
                       {"sudo":True},{"cwd":"/etc"},{"timeout":True},{"args":["-jar","model.jar"]}):
            with self.subTest(change=change),self.assertRaises(Failure): decode_request(self.frame(path,"POST",encoded(body|change)))
        read="/v2/sandboxes/sessions/sbx_1/fs/read?teamId=team_synthetic"
        with self.assertRaises(Failure): decode_request(self.frame(read,"POST",encoded({"cwd":ROOT,"path":"../secret"})))

    def test_creation_has_no_persistence_egress_ports_or_credentials(self):
        plane=SyntheticPlane();client=SandboxClient(self.config,plane)
        report=client.execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(report["status"],"CONTRACT_COMPLETE")
        request=next(r for r in plane.requests if r["path"].startswith("/v4"))
        body=parse_json_bytes(request["payload"])
        self.assertIs(body["persistent"],False)
        self.assertEqual(body["networkPolicy"],{"mode":"deny-all"})
        self.assertEqual(body["ports"],[]);self.assertEqual(body["env"],{})
        self.assertNotIn("source",body);self.assertNotIn("runtime",body)
        for change in ({"persistent":True},{"networkPolicy":{"mode":"allow-all"}},{"ports":[8080]},
                       {"env":{"AI_GATEWAY_API_KEY":"synthetic"}},{"resources":{"vcpus":True,"memory":2048}}):
            with self.subTest(change=change),self.assertRaises(Failure):
                decode_request(self.frame(request["path"],"POST",encoded(body|change)))

    def test_serial_public_and_verifier_journey(self):
        result=contract_journey()
        self.recorded["success"]=result
        self.assertEqual(result["status"],"CONTRACT_COMPLETE")
        self.assertIs(result["domain_verified"],False)
        self.assertTrue(result["actor_closed"])
        self.assertEqual(result["maximum_synthetic_sessions_active"],1)
        self.assertNotEqual(result["public"]["session_name"],result["verifier"]["session_name"])
        self.assertEqual(result["public"]["source_sha256"],result["verifier"]["source_sha256"])
        self.assertEqual(result["verifier"]["matched_count"],6)
        self.assertIsNone(result["verifier"]["journal"]["actual_cost_inr"])

    def test_private_probe_uploaded_only_to_distinct_closed_verifier_session(self):
        actor=actor_candidate();plane=SyntheticPlane();client=SandboxClient(self.config,plane)
        draft=replace(self.proposal,actor_closed=False)
        client.execute(draft,probe_plan("public"))
        self.assertFalse(actor.closed)
        sealed=Proposal.from_actor(actor)
        client.execute(sealed,probe_plan("verifier"))
        public,verifier=list(plane.sessions.values())
        self.assertNotIn(b"101",public["files"][PROBE_PATH])
        self.assertIn(b"101",verifier["files"][PROBE_PATH])
        self.assertTrue(actor.closed)

    def test_false_fix_rejected_after_public_contract_success(self):
        result=contract_journey("false-fix");self.recorded["false-fix"]=result
        self.assertEqual(result["public"]["status"],"CONTRACT_COMPLETE")
        self.assertEqual(result["verifier"]["status"],"CONTRACT_REJECTED")
        self.assertEqual(result["verifier"]["matched_count"],5)
        self.assertFalse(result["domain_verified"])

    def test_compile_runtime_source_log_and_false_completion_failures(self):
        expected={"compile-failure":"COMMAND_FAILED","wrong-runtime":"RUNTIME_MISMATCH",
                  "wrong-source":"CONTRACT_REJECTED","bad-log":"PROTOCOL_ERROR","false-completion":"CONTRACT_REJECTED"}
        for scenario,status in expected.items():
            with self.subTest(scenario=scenario):
                result=contract_journey(scenario);self.recorded[scenario]=result
                self.assertEqual(result["status"],status)
                self.assertTrue(result["public"]["cleanup_complete"])
                self.assertIsNone(result["verifier"])

    def test_lost_create_recovers_without_duplicate_and_remains_blocked(self):
        plane=SyntheticPlane("lost-create");client=SandboxClient(self.config,plane)
        result=client.execute(self.proposal,probe_plan("verifier"));self.recorded["lost-create"]=result
        self.assertEqual(result["status"],"TRANSPORT_ERROR")
        self.assertTrue(result["cleanup_complete"]);self.assertTrue(client.blocked)
        self.assertEqual(sum(r["path"].startswith("/v4") for r in plane.requests),1)
        self.assertTrue(all("resume=false" in r["path"] for r in plane.requests if r["method"]=="GET" and "projectId=" in r["path"]))
        count=len(plane.requests)
        with self.assertRaises(Failure): client.execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(len(plane.requests),count)

    def test_lost_create_missing_and_bad_identity_require_handoff(self):
        for scenario in ("lost-create-missing","wrong-image"):
            with self.subTest(scenario=scenario):
                plane=SyntheticPlane(scenario);client=SandboxClient(self.config,plane)
                result=client.execute(self.proposal,probe_plan("verifier"));self.recorded[scenario]=result
                self.assertEqual(result["status"],"HANDOFF_REQUIRED")
                self.assertFalse(result["cleanup_complete"]);self.assertTrue(client.blocked)
                self.assertEqual(sum(r["path"].startswith("/v4") for r in plane.requests),1)
                self.assertFalse(any("/cmd" in r["path"] for r in plane.requests))

    def test_stop_pending_recovery_never_replays_stop_or_resets_budget(self):
        plane=SyntheticPlane("stop-pending");client=SandboxClient(self.config,plane)
        result=client.execute(self.proposal,probe_plan("verifier"));self.recorded["stop-pending"]=result
        self.assertEqual(result["status"],"HANDOFF_REQUIRED")
        before=client.budget.requests
        self.assertFalse(client.recover());self.assertGreater(client.budget.requests,before)
        self.assertEqual(sum("/stop?" in r["path"] for r in plane.requests),1)
        for session in plane.sessions.values(): session["status"]="stopped"
        self.assertTrue(client.recover());self.assertTrue(client.blocked)
        self.assertEqual(client.budget.sessions,1)

    def test_deadline_after_create_reserves_cleanup_and_executes_no_commands(self):
        class Clock:
            value=0
            def __call__(self): return self.value
        clock=Clock()
        class Delayed(SyntheticPlane):
            def exchange(self,raw,**kwargs):
                value=super().exchange(raw,**kwargs)
                if self.requests[-1]["path"].startswith("/v4"): clock.value=111
                return value
        plane=Delayed();client=SandboxClient(self.config,plane,clock=clock)
        result=client.execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(result["status"],"BUDGET_EXHAUSTED")
        self.assertTrue(result["cleanup_complete"])
        self.assertFalse(any("/cmd" in r["path"] for r in plane.requests))
        self.assertEqual(result["budget"]["active_seconds"],111)

    def test_cancel_before_create_and_session_cap_are_cumulative(self):
        plane=SyntheticPlane();client=SandboxClient(self.config,plane,cancel=lambda:True)
        with self.assertRaises(Failure) as error: client.execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(error.exception.status,"CANCELLED");self.assertEqual(plane.requests,[])
        client=SandboxClient(self.config,plane)
        client.execute(self.proposal,probe_plan("public"));client.execute(self.proposal,probe_plan("verifier"))
        count=len(plane.requests)
        with self.assertRaises(Failure): client.execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(client.budget.sessions,2);self.assertEqual(len(plane.requests),count)

    def test_boolean_exit_and_raw_error_body_do_not_become_success(self):
        class BadExit(SyntheticPlane):
            def respond(self,method,path,payload=b""):
                response=super().respond(method,path,payload)
                if method=="GET" and "/cmd/" in path and not path.endswith("logs"):
                    data=json.loads(response.body);data["command"]["exitCode"]=True
                    return Response(200,encoded(data))
                return response
        result=SandboxClient(self.config,BadExit()).execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(result["status"],"PROTOCOL_ERROR");self.assertTrue(result["cleanup_complete"])
        class Denied(SyntheticPlane):
            def respond(self,method,path,payload=b""):
                if path=="/v4/sandboxes": return Response(403,b"Bearer synthetic-canary sk-proj-never-log")
                return super().respond(method,path,payload)
        result=SandboxClient(self.config,Denied()).execute(self.proposal,probe_plan("verifier"))
        self.assertNotIn("synthetic-canary",json.dumps(result));self.assertNotIn("sk-proj",json.dumps(result))

    def test_journal_has_write_ahead_identity_and_constant_error_codes(self):
        snapshots=[]
        result=contract_journey("lost-create",journal_sink=snapshots.append)
        pending=next(s for s in snapshots if s["active_session"] and s["active_session"]["create_sent"])
        self.assertIsNone(pending["active_session"]["session_id"])
        self.assertTrue(pending["active_session"]["name"].startswith("ipa-"))
        self.assertTrue(all(s["mode"]=="local-double" and not s["external_isolation_verified"] for s in snapshots))
        self.assertFalse(result["domain_verified"])

    def test_new_python_source_compiles_without_execution(self):
        files=list((REPO/"issue_to_patch_sandbox").glob("*.py"))+list((REPO/"tests/sandbox_transport").glob("*.py"))
        files += [REPO/"scripts/sandbox_contract_acceptance.py"]
        for path in files:
            with self.subTest(path=path.name): compile(path.read_text(encoding="utf-8"),path.name,"exec")

    def test_serial_lock_denies_overlapping_execution_and_recovery(self):
        plane=SyntheticPlane();client=SandboxClient(self.config,plane)
        client._lock.acquire()
        try:
            with self.assertRaises(Failure): client.execute(self.proposal,probe_plan("verifier"))
            with self.assertRaises(Failure): client.recover()
            self.assertEqual(plane.requests,[])
        finally: client._lock.release()

    def test_cleanup_restore_preserves_counters_identity_and_charges_downtime(self):
        class Clock:
            value=0
            def __call__(self): return self.value
        clock=Clock();plane=SyntheticPlane("stop-pending")
        client=SandboxClient(self.config,plane,clock=clock)
        client.execute(self.proposal,probe_plan("verifier"))
        snapshot=json.loads(encoded(client.journal));before=client.budget.requests
        clock.value=5
        restored=SandboxClient.for_cleanup(self.config,plane,snapshot,clock=clock)
        self.assertEqual(restored.run_id,client.run_id)
        self.assertEqual(restored.budget.requests,before);self.assertEqual(restored.budget.sessions,1)
        self.assertEqual(restored.budget.snapshot()["active_seconds"],5)
        for session in plane.sessions.values(): session["status"]="stopped"
        self.assertTrue(restored.recover());self.assertGreater(restored.budget.requests,before)
        self.assertTrue(restored.blocked)
        with self.assertRaises(Failure): restored.execute(self.proposal,probe_plan("verifier"))

    def test_cleanup_restore_rejects_tampered_identity_counters_and_clock(self):
        plane=SyntheticPlane("stop-pending");client=SandboxClient(self.config,plane)
        client.execute(self.proposal,probe_plan("verifier"))
        original=json.loads(encoded(client.journal))
        for changes in ({"config_sha256":"wrong"},{"run_id":"wrong"}):
            with self.subTest(changes=changes),self.assertRaises(Failure):
                SandboxClient.for_cleanup(self.config,plane,original|changes)
        for key,value in (("requests",True),("sessions",3),("active_seconds",-1),("last_monotonic",float("inf"))):
            altered=json.loads(encoded(original));altered["budget"][key]=value
            with self.subTest(key=key),self.assertRaises((Failure,ValueError)):
                SandboxClient.for_cleanup(self.config,plane,altered)
        with self.assertRaises(Failure):
            SandboxClient.for_cleanup(self.config,plane,original,clock=lambda:0)

    def test_cleanup_window_reaches_a_transport_that_uses_default_budget_check(self):
        class Clock:
            value=0
            def __call__(self): return self.value
        clock=Clock()
        class DefaultCheck(SyntheticPlane):
            def exchange(self,raw,*,budget,cancel=None):
                budget.check(cancel)  # Same check used by the accepted OwnedTransport boundary.
                reply=super().exchange(raw,budget=budget,cancel=cancel)
                if self.requests[-1]["path"].startswith("/v4"): clock.value=111
                return reply
        result=SandboxClient(self.config,DefaultCheck(),clock=clock).execute(self.proposal,probe_plan("verifier"))
        self.assertEqual(result["status"],"BUDGET_EXHAUSTED");self.assertTrue(result["cleanup_complete"])
        self.assertEqual(result["budget"]["active_seconds"],111)

    def test_remote_timeout_and_proposal_object_types_fail_before_java(self):
        class TooLong(SyntheticPlane):
            def respond(self,method,path,payload=b""):
                response=super().respond(method,path,payload)
                if path=="/v4/sandboxes":
                    value=json.loads(response.body);value["session"]["timeout"]=300000
                    return Response(200,encoded(value))
                return response
        plane=TooLong();result=SandboxClient(self.config,plane).execute(self.proposal,probe_plan("verifier"))
        self.assertNotEqual(result["status"],"CONTRACT_COMPLETE")
        self.assertFalse(any("/cmd" in r["path"] for r in plane.requests))
        client=SandboxClient(self.config,SyntheticPlane())
        with self.assertRaises(Failure): client.execute({},probe_plan("verifier"))


def parse_json_bytes(value):
    return json.loads(base64.b64decode(value))


if __name__=="__main__":
    unittest.main()
