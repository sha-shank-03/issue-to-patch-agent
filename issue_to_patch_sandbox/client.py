"""Small serial REST lifecycle. No ambiguous mutation is automatically replayed."""
import base64
import hashlib
import re
import time
import threading
import uuid
from urllib.parse import urlencode

from issue_to_patch_upgrade.core import Failure, encoded, parse_json
from issue_to_patch_upgrade.events import redact
from . import SCHEMA_VERSION, VERSION, source_version
from .contract import ROOT, SOURCE_PATH, PROBE_PATH, SandboxConfig, Proposal, CheckPlan, fixed_commands, upload_archive


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",value):
        raise Failure("PROTOCOL_ERROR","sandbox_invalid_identifier",ambiguous=True)
    return value


class LifecycleBudget:
    def __init__(self, limits, *, clock=time.monotonic):
        self.limits,self.clock,self.started = limits,clock,clock()
        self.requests = self.sessions = self.output_bytes = 0

    @property
    def remaining(self):
        return max(0,self.limits.wall_seconds-(self.clock()-self.started))

    def check(self,cancel=None,*,cleanup=False):
        if cancel is not None and cancel():
            raise Failure("CANCELLED","sandbox_cancelled")
        if self.remaining <= (0 if cleanup else self.limits.cleanup_seconds):
            raise Failure("BUDGET_EXHAUSTED","sandbox_total_deadline")

    def snapshot(self):
        return {"requests":self.requests,"sessions":self.sessions,"output_bytes":self.output_bytes,
                "active_seconds":self.clock()-self.started,"last_monotonic":self.clock(),"remaining_seconds":self.remaining,
                "automatic_mutation_retries":0,"execution_resume":"not_supported"}


class TransportBudget:
    """Cleanup consumes the same total clock/counters, with the reserved cleanup window."""
    def __init__(self,budget,cleanup): self.budget,self.cleanup = budget,cleanup
    @property
    def remaining(self): return self.budget.remaining
    @property
    def limits(self): return self.budget.limits
    def check(self,cancel=None,*,cleanup=False): self.budget.check(cancel,cleanup=cleanup or self.cleanup)


class SandboxClient:
    def __init__(self,config,transport,*,authorization=None,clock=time.monotonic,cancel=None,journal_sink=None):
        if not isinstance(config,SandboxConfig):
            raise Failure("CONFIG_ERROR","sandbox_trusted_config_required")
        if getattr(transport,"mode",None) != config.mode:
            raise Failure("CONFIG_ERROR","sandbox_transport_mode_mismatch")
        if config.mode == "live":
            if authorization is None:
                raise Failure("AUTHORIZATION_DENIED","sandbox_separate_authorization_required")
            authorization.validate(config)
        self.config,self.transport,self.cancel = config,transport,cancel
        self.budget = LifecycleBudget(config.limits,clock=clock)
        self.run_id = uuid.uuid4().hex
        self.sink = journal_sink
        self.blocked = False
        self._lock = threading.Lock()
        self.active = None
        self.journal = {"schema_version":SCHEMA_VERSION,"version":VERSION,"run_id":self.run_id,
                        "code_version":source_version(),"mode":config.mode,"config_sha256":config.fingerprint,
                        "pins":{"project":config.project_id,"team":config.team_id,"image":config.image,"java_major":17},"events":[],
                        "active_session":None,"cleanup":"no_session","estimated_cost_inr":
                        authorization.worst_case_inr if authorization else None,
                        "actual_cost_inr":None,"reservation":"held" if authorization else "synthetic_none",
                        "external_isolation_verified":False}
        self._save()

    @classmethod
    def for_cleanup(cls,config,transport,journal,*,authorization=None,clock=time.monotonic,journal_sink=None):
        """Restore only owned cleanup. Downtime is charged; execution cannot resume."""
        import math
        value = parse_json(encoded(journal))
        if (not isinstance(value,dict) or value.get("schema_version")!=SCHEMA_VERSION
                or value.get("config_sha256")!=config.fingerprint or value.get("mode")!=config.mode
                or not isinstance(value.get("run_id"),str) or not re.fullmatch(r"[a-f0-9]{32}",value["run_id"])):
            raise Failure("POLICY_DENIED","sandbox_recovery_identity_invalid")
        a,b = value.get("active_session"),value.get("budget")
        if (not isinstance(a,dict) or not isinstance(b,dict) or a.get("role") not in {"public","verifier"}
                or not isinstance(a.get("name"),str) or not re.fullmatch("ipa-"+value["run_id"]+r"-(public|verifier)-[12]",a["name"])
                or any(type(a.get(k)) is not bool for k in ("actor_closed","create_sent","stop_sent","delete_sent"))
                or not a["create_sent"] or (a["role"]=="verifier" and not a["actor_closed"])
                or type(a.get("requested_timeout_ms")) is not int or not 1<=a["requested_timeout_ms"]<=180000
                or any(not isinstance(a.get(k),str) or not re.fullmatch(r"[0-9a-f]{64}",a[k]) for k in
                       ("source_sha256","probe_sha256","original_sha256","public_record_sha256"))):
            raise Failure("POLICY_DENIED","sandbox_recovery_identity_invalid")
        if a.get("session_id") is not None: identifier(a["session_id"])
        for key,maximum in (("requests",config.limits.requests),("sessions",config.limits.sessions),("output_bytes",config.limits.response_bytes)):
            if type(b.get(key)) is not int or not 0<=b[key]<=maximum:
                raise Failure("POLICY_DENIED","sandbox_recovery_budget_invalid")
        if b["sessions"]<1 or a["name"]!=f"ipa-{value['run_id']}-{a['role']}-{b['sessions']}":
            raise Failure("POLICY_DENIED","sandbox_recovery_budget_invalid")
        for key in ("active_seconds","last_monotonic"):
            if type(b.get(key)) not in (int,float) or not math.isfinite(b[key]) or b[key]<0:
                raise Failure("POLICY_DENIED","sandbox_recovery_clock_invalid")
        now = clock()
        if now < b["last_monotonic"]:
            raise Failure("HANDOFF_REQUIRED","sandbox_recovery_clock_discontinuity")
        instance = cls(config,transport,authorization=authorization,clock=clock)
        instance.run_id,instance.journal,instance.active = value["run_id"],value,a
        instance.budget.requests,instance.budget.sessions,instance.budget.output_bytes = b["requests"],b["sessions"],b["output_bytes"]
        instance.budget.started = now-b["active_seconds"]-(now-b["last_monotonic"])
        instance.blocked = True
        instance.sink = journal_sink
        instance.journal["recovery_code_version"] = source_version()
        instance._save()
        return instance

    def _save(self):
        self.journal.update(budget=self.budget.snapshot(),active_session=self.active,blocked=self.blocked)
        if self.sink:
            self.sink(redact(self.journal))

    def _event(self,kind,**fields):
        if len(self.journal["events"]) >= 128:
            raise Failure("BUDGET_EXHAUSTED","sandbox_event_limit")
        self.journal["events"].append({"kind":kind,"active_seconds":self.budget.clock()-self.budget.started,**fields})
        self._save()

    def _request(self,method,path,body=b"",*,binary=False,cleanup=False,named=False):
        self.budget.check(None if cleanup else self.cancel,cleanup=cleanup)
        cap = self.config.limits.requests - (0 if cleanup else 6)
        if self.budget.requests >= cap:
            raise Failure("BUDGET_EXHAUSTED","sandbox_request_limit")
        query = {"teamId":self.config.team_id}
        if named:
            query["projectId"] = self.config.project_id
            if method == "GET": query["resume"] = "false"
        if "/cmd/" in path and not path.endswith("/logs"):
            query["wait"] = "true"
        request = encoded({"method":method,"path":path+"?"+urlencode(query),
                           "content_type":"application/gzip" if binary else "application/json",
                           "cwd":ROOT if binary else None,"payload":base64.b64encode(body).decode("ascii")})
        if len(request) > self.config.limits.request_bytes:
            raise Failure("BUDGET_EXHAUSTED","sandbox_request_body_limit")
        self.budget.requests += 1
        self._event("http_requested",method=method,path=path,request_sha256=hashlib.sha256(request).hexdigest(),cleanup=cleanup)
        try:
            response = self.transport.exchange(request,budget=TransportBudget(self.budget,cleanup),cancel=None if cleanup else self.cancel)
            self.budget.check(None if cleanup else self.cancel,cleanup=cleanup)
        except Failure as failure:
            if failure.ambiguous:
                self.blocked = True
            self._event("http_failed",error=failure.code,ambiguous=failure.ambiguous)
            raise
        if (type(response.status) is not int or not isinstance(response.body,bytes)
                or len(response.body) > self.config.limits.response_bytes):
            raise Failure("PROTOCOL_ERROR","sandbox_response_limit",ambiguous=method != "GET")
        self._event("http_observed",http_status=response.status,response_sha256=hashlib.sha256(response.body).hexdigest())
        if response.status == 404 and cleanup:
            return None
        if response.status != 200:
            mapping = {401:"AUTHORIZATION_DENIED",403:"AUTHORIZATION_DENIED",402:"FUNDS_DENIED",429:"RATE_LIMITED"}
            ambiguous = method != "GET" and response.status >= 500
            if ambiguous: self.blocked = True
            raise Failure(mapping.get(response.status,"SANDBOX_API_ERROR"),"sandbox_http_"+str(response.status),ambiguous=ambiguous)
        return response.body

    def _json(self,*args,**kwargs):
        body = self._request(*args,**kwargs)
        if body is None: return None
        value = parse_json(body)
        if not isinstance(value,dict):
            raise Failure("PROTOCOL_ERROR","sandbox_response_schema")
        return value

    def _identity(self,value,*,named=True,running=False):
        if not isinstance(value,dict) or value.get("routes") != [] or not isinstance(value.get("session"),dict):
            raise Failure("PROTOCOL_ERROR","sandbox_session_schema")
        session = value["session"]
        sid = identifier(session.get("id"))
        if self.active["session_id"] is not None and sid != self.active["session_id"]:
            raise Failure("PROTOCOL_ERROR","sandbox_session_identity")
        expected = {"projectId":self.config.project_id,"sourceSandboxName":self.active["name"],
                    "cwd":ROOT,"vcpus":1,"memory":2048,"networkPolicy":{"mode":"deny-all"},
                    "architecture":self.config.architecture}
        if any(session.get(k) != v or (isinstance(v,int) and type(session.get(k)) not in (int,float)) for k,v in expected.items()):
            raise Failure("PROTOCOL_ERROR","sandbox_session_identity")
        if type(session.get("timeout")) not in (int,float) or not 0<session["timeout"]<=self.active["requested_timeout_ms"]:
            raise Failure("PROTOCOL_ERROR","sandbox_session_timeout")
        if session.get("status") not in {"pending","running","stopping","stopped","failed","aborted"}:
            raise Failure("PROTOCOL_ERROR","sandbox_session_status")
        if running and session["status"] != "running":
            raise Failure("HANDOFF_REQUIRED","sandbox_session_not_running")
        if named:
            meta = value.get("sandbox")
            if (not isinstance(meta,dict) or meta.get("name") != self.active["name"]
                    or meta.get("currentSessionId") != sid or meta.get("persistent") is not False
                    or meta.get("image") != self.config.image or meta.get("networkPolicy") != {"mode":"deny-all"}
                    or meta.get("tags") != {"run":self.run_id,"role":self.active["role"]}
                    or value.get("resumed",False) is not False):
                raise Failure("PROTOCOL_ERROR","sandbox_named_identity")
        return session

    def _command(self,label,program,args):
        sid = self.active["session_id"]
        payload = {"command":program,"args":args,"cwd":ROOT,"env":{},"sudo":False,
                   "wait":False,"logs":False,"attachStdin":False,"timeout":self.config.limits.command_ms}
        value = self._json("POST",f"/v2/sandboxes/sessions/{sid}/cmd",encoded(payload))
        command = value.get("command",{})
        if not isinstance(command,dict):
            raise Failure("PROTOCOL_ERROR","sandbox_command_schema")
        cid = identifier(command.get("id"))
        observed = self._json("GET",f"/v2/sandboxes/sessions/{sid}/cmd/{cid}").get("command",{})
        if not isinstance(observed,dict):
            raise Failure("PROTOCOL_ERROR","sandbox_command_schema")
        if any(observed.get(k) != v for k,v in {"id":cid,"sessionId":sid,"name":program,"args":args,"cwd":ROOT}.items()):
            raise Failure("PROTOCOL_ERROR","sandbox_command_identity")
        if type(observed.get("exitCode")) is not int:
            raise Failure("PROTOCOL_ERROR","sandbox_unfinished_or_invalid_exit")
        raw = self._request("GET",f"/v2/sandboxes/sessions/{sid}/cmd/{cid}/logs")
        output = {"stdout":"","stderr":""}
        for line in raw.splitlines():
            if not line: continue
            record = parse_json(line)
            if not isinstance(record,dict) or set(record) != {"stream","data"}:
                raise Failure("PROTOCOL_ERROR","sandbox_log_schema")
            if record["stream"] == "error":
                raise Failure("SANDBOX_API_ERROR","sandbox_log_stream_failed")
            if record["stream"] not in output or not isinstance(record["data"],str):
                raise Failure("PROTOCOL_ERROR","sandbox_log_schema")
            self.budget.output_bytes += len(record["data"].encode("utf-8"))
            if self.budget.output_bytes > self.config.limits.response_bytes:
                raise Failure("BUDGET_EXHAUSTED","sandbox_output_limit")
            output[record["stream"]] += record["data"]
        self._event("command_finished",command_id=cid,label=label,exit_code=observed["exitCode"],output_sha256=hashlib.sha256(raw).hexdigest())
        if observed["exitCode"] != 0:
            raise Failure("COMMAND_FAILED","sandbox_"+label+"_nonzero")
        return output

    def _read(self,path):
        return self._request("POST",f"/v2/sandboxes/sessions/{self.active['session_id']}/fs/read",
                             encoded({"path":path,"cwd":ROOT}))

    def execute(self,proposal,plan):
        if not self._lock.acquire(blocking=False):
            raise Failure("HANDOFF_REQUIRED","sandbox_operation_already_active")
        try:
            return self._execute(proposal,plan)
        finally:
            self._lock.release()

    def _execute(self,proposal,plan):
        if not isinstance(proposal,Proposal) or not isinstance(plan,CheckPlan):
            raise Failure("POLICY_DENIED","sandbox_trusted_proposal_plan_required")
        proposal.validate(self.config.limits,plan.role)
        plan.validate()
        if proposal.original_sha256 != plan.original_sha256:
            raise Failure("POLICY_DENIED","sandbox_original_preimage_mismatch")
        if self.blocked or self.active is not None:
            raise Failure("HANDOFF_REQUIRED","sandbox_previous_session_unresolved")
        if self.budget.sessions >= self.config.limits.sessions:
            raise Failure("BUDGET_EXHAUSTED","sandbox_session_limit")
        self.budget.check(self.cancel)
        self.budget.sessions += 1
        name = f"ipa-{self.run_id}-{plan.role}-{self.budget.sessions}"
        self.active = {"name":name,"session_id":None,"role":plan.role,"source_sha256":proposal.source_sha256,
                       "original_sha256":proposal.original_sha256,"actor_closed":proposal.actor_closed,
                       "public_record_sha256":proposal.public_record_sha256,
                       "requested_timeout_ms":int(min(self.budget.remaining,self.config.limits.wall_seconds)*1000),
                       "probe_sha256":plan.probe_sha256,"create_sent":False,"stop_sent":False,"delete_sent":False}
        result = {"status":"INCOMPLETE","error":None,"role":plan.role,"mode":self.config.mode,
                  "source_sha256":proposal.source_sha256,"probe_sha256":plan.probe_sha256,
                  "domain_verified":False,"external_isolation_verified":False,"records":[],
                  "real_sandbox_sessions":0 if self.config.mode == "local-double" else None}
        try:
            archive = upload_archive(proposal,plan,self.config.limits)
            payload = {"projectId":self.config.project_id,"name":name,"image":self.config.image,
                       "architecture":self.config.architecture,"resources":{"vcpus":1,"memory":2048},
                       "persistent":False,"networkPolicy":{"mode":"deny-all"},"ports":[],"env":{},
                       "timeout":self.active["requested_timeout_ms"],
                       "tags":{"run":self.run_id,"role":plan.role}}
            self.active["create_sent"] = True
            self._save()  # Write-ahead identity survives a lost create response.
            value = self._json("POST","/v4/sandboxes",encoded(payload))
            session = self._identity(value)
            self.active["session_id"] = session["id"]
            self._identity(self._json("GET",f"/v2/sandboxes/sessions/{session['id']}"),named=False,running=True)
            commands = fixed_commands(self.config)
            for label,program,args in commands[:2]:
                output = self._command(label,program,args)
                text = output["stdout"]+output["stderr"]
                pattern = r'(?:openjdk|java) version "17(?:[.\"])' if label == "java-version" else r"javac 17(?:\.|\s|$)"
                if not re.search(pattern,text):
                    raise Failure("RUNTIME_MISMATCH","sandbox_jdk17_required")
            self._request("POST",f"/v2/sandboxes/sessions/{session['id']}/fs/write",archive,binary=True)
            if self._read(SOURCE_PATH) != proposal.content or self._read(PROBE_PATH) != plan.probe:
                raise Failure("CONTRACT_REJECTED","sandbox_uploaded_preimage_mismatch")
            output = None
            for label,program,args in commands[2:]:
                output = self._command(label,program,args)
            if self._read(SOURCE_PATH) != proposal.content:
                raise Failure("CONTRACT_REJECTED","sandbox_source_changed_after_execution")
            records = [parse_json(line) for line in output["stdout"].splitlines() if line]
            expected = [{"quantity":q,"accepted":a} for q,a in plan.expected]
            well_typed = all(isinstance(r,dict) and set(r)=={"quantity","accepted"}
                             and type(r["quantity"]) is int and type(r["accepted"]) is bool for r in records)
            result.update(status="CONTRACT_COMPLETE" if well_typed and records == expected else "CONTRACT_REJECTED",
                          records=records,expected_count=len(expected),matched_count=sum(a==b for a,b in zip(records,expected)))
        except Failure as failure:
            result.update(status=failure.status,error=failure.code,ambiguous_delivery=failure.ambiguous)
            if failure.ambiguous: self.blocked = True
        finally:
            result["cleanup_complete"] = self._recover()
            if not result["cleanup_complete"]:
                result.update(status="HANDOFF_REQUIRED",cleanup_error=self.journal.get("cleanup_error"))
            result.update(budget=self.budget.snapshot(),session_name=name,journal=redact(self.journal))
        return redact(result)

    def recover(self):
        if not self._lock.acquire(blocking=False):
            raise Failure("HANDOFF_REQUIRED","sandbox_operation_already_active")
        try:
            return self._recover()
        finally:
            self._lock.release()

    def _recover(self):
        """Cleanup only. Never resume execution or recreate an uncertain guest."""
        if self.active is None: return True
        try:
            a = self.active
            if a["session_id"] is None:
                found = self._json("GET",f"/v2/sandboxes/{a['name']}",cleanup=True,named=True)
                if found is None:
                    raise Failure("HANDOFF_REQUIRED","sandbox_create_absence_not_confirmed")
                a["session_id"] = self._identity(found)["id"]
            sid = a["session_id"]
            current = self._json("GET",f"/v2/sandboxes/sessions/{sid}",cleanup=True)
            if current is None:
                raise Failure("HANDOFF_REQUIRED","sandbox_session_absence_not_confirmed")
            state = self._identity(current,named=False)["status"]
            if state not in {"stopped","aborted","failed"}:
                if a["stop_sent"]:
                    raise Failure("HANDOFF_REQUIRED","sandbox_stop_still_pending")
                a["stop_sent"] = True
                self._save()
                self._request("POST",f"/v2/sandboxes/sessions/{sid}/stop",cleanup=True)
                state = self._identity(self._json("GET",f"/v2/sandboxes/sessions/{sid}",cleanup=True),named=False)["status"]
            if state not in {"stopped","aborted","failed"}:
                raise Failure("HANDOFF_REQUIRED","sandbox_stop_not_observed")
            if not a["delete_sent"]:
                a["delete_sent"] = True
                self._save()
                self._request("DELETE",f"/v2/sandboxes/{a['name']}",cleanup=True,named=True)
            remaining = self._json("GET",f"/v2/sandboxes/{a['name']}",cleanup=True,named=True)
            if remaining is not None:
                raise Failure("HANDOFF_REQUIRED","sandbox_delete_not_observed")
            self._event("session_cleanup_confirmed",name=a["name"],session_id=sid)
            self.active = None
            self.journal["cleanup"] = "stopped_and_named_absence_observed"
            self._save()
            return getattr(self.transport,"cleanup_complete",False) is True
        except Failure as failure:
            self.blocked = True
            self.journal.update(cleanup="unresolved",cleanup_error=failure.code)
            self._save()
            return False
