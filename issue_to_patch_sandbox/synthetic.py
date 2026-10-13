"""Authored control-plane responses. No sockets, guest, Java or SDK execution."""
import hashlib
import io
import json
import tarfile
from urllib.parse import urlsplit

from issue_to_patch.protocol import Action
from issue_to_patch_upgrade.core import Failure, Limits, digest, encoded, parse_json
from issue_to_patch_upgrade.fixture import SOURCE, ORIGINAL, REPAIRED, FALSE_FIX, SOURCE_PATH
from issue_to_patch_upgrade.sandbox_double import InertSandbox
from issue_to_patch_upgrade.tools import Tools
from issue_to_patch_upgrade.transport import Response
from .client import SandboxClient
from .contract import Proposal, CheckPlan, ROOT, PROBE_PATH, synthetic_config
from .wire import decode_request


def probe_plan(role):
    pairs = ((0,False),(2,True)) if role=="public" else ((-1,False),(0,False),(1,True),(2,True),(100,True),(101,False))
    quantities = ",".join(str(q) for q,_ in pairs)
    text = ('public final class ContractProbe { public static void main(String[] args) {\n'
            'for (int q : new int[]{'+quantities+'}) System.out.println("{\\\"quantity\\\":"+q+",\\\"accepted\\\":"+QuantityApi.accepts(q)+"}");\n'
            '} }\n').encode()
    return CheckPlan(role,text,hashlib.sha256(text).hexdigest(),pairs)


class SyntheticPlane:
    mode = "local-double"
    cleanup_complete = True
    started = 0

    def __init__(self,scenario="success"):
        self.scenario = scenario
        self.requests = []
        self.named = {}
        self.sessions = {}
        self.commands = {}
        self.maximum_active = 0

    def exchange(self,raw,*,budget,cancel=None):
        budget.check(cancel,cleanup=True)
        value,payload = decode_request(raw)
        path = urlsplit(value["path"]).path
        self.requests.append({**value,"payload_sha256":hashlib.sha256(payload).hexdigest()})
        return self.respond(value["method"],path,payload)

    def session_response(self,session,named=False):
        value = {"routes":[],"session":{k:v for k,v in session.items() if k not in {"files","meta"}}}
        if named: value["sandbox"] = session["meta"].copy()
        return value

    def respond(self,method,path,payload=b""):
        def response(data=None,status=200):
            return Response(status,b"" if data is None else encoded(data))
        if path=="/v4/sandboxes":
            request = parse_json(payload)
            if self.scenario=="http-403": return response(status=403)
            sid = "sbx_"+str(len(self.sessions)+1)
            session = {"id":sid,"projectId":request["projectId"],"sourceSandboxName":request["name"],
                       "cwd":ROOT,"vcpus":1,"memory":2048,"architecture":"amd64","runtime":"synthetic",
                       "timeout":request["timeout"],"region":"synthetic","createdAt":0,"updatedAt":0,"requestedAt":0,
                       "status":"running","networkPolicy":{"mode":"deny-all"},"files":{},
                       "meta":{"name":request["name"],"currentSessionId":sid,"persistent":request["persistent"],
                               "image":request["image"],"networkPolicy":request["networkPolicy"],"tags":request["tags"]}}
            if self.scenario=="wrong-image": session["meta"]["image"]="synthetic/wrong@sha256:"+"1"*64
            self.sessions[sid] = session
            self.named[request["name"]] = sid
            self.maximum_active = max(self.maximum_active,sum(s["status"]=="running" for s in self.sessions.values()))
            if self.scenario in {"lost-create","lost-create-missing"}:
                if self.scenario=="lost-create-missing": self.named.clear();self.sessions.clear()
                raise Failure("TRANSPORT_ERROR","synthetic_create_response_loss",ambiguous=True)
            return response(self.session_response(session,named=True))
        parts = path.split("/")
        if len(parts)==4:
            name = parts[-1]
            if name not in self.named: return response(status=404)
            sid = self.named[name]
            if method=="DELETE":
                del self.named[name]
                return response({})
            return response({**self.session_response(self.sessions[sid],named=True),"resumed":False})
        sid = parts[4]
        if sid not in self.sessions: return response(status=404)
        session = self.sessions[sid]
        if len(parts)==5: return response(self.session_response(session))
        if path.endswith("/stop"):
            session["status"] = "stopping" if self.scenario=="stop-pending" else "stopped"
            return response(self.session_response(session))
        if path.endswith("/fs/write"):
            with tarfile.open(fileobj=io.BytesIO(payload),mode="r:gz") as archive:
                for member in archive.getmembers():
                    if not member.isfile() or member.name not in {SOURCE_PATH,PROBE_PATH}:
                        raise Failure("POLICY_DENIED","synthetic_upload_member")
                    session["files"][member.name] = archive.extractfile(member).read()
            return response({})
        if path.endswith("/fs/read"):
            target = parse_json(payload)["path"]
            content = session["files"][target]
            if self.scenario=="wrong-source" and target==SOURCE_PATH: content += b"tampered"
            return Response(200,content)
        if path.endswith("/cmd"):
            request = parse_json(payload)
            cid = "cmd_"+str(len(self.commands)+1)
            command = {"id":cid,"sessionId":sid,"name":request["command"],"args":request["args"],"cwd":request["cwd"],"exitCode":None}
            self.commands[cid] = command
            return response({"command":command})
        cid = parts[6]
        command = self.commands[cid]
        label = "compile" if command["name"].endswith("javac") and "-version" not in command["args"] else "other"
        if not path.endswith("/logs"):
            command["exitCode"] = 1 if self.scenario=="compile-failure" and label=="compile" else 0
            return response({"command":command})
        if self.scenario=="bad-log": return Response(200,b'{"stream":"unknown","data":"synthetic"}\n')
        if command["args"]==["-version"]:
            major = "21" if self.scenario=="wrong-runtime" else "17"
            text = "javac "+major+".0.1\n" if command["name"].endswith("javac") else 'openjdk version "'+major+'.0.1"\n'
        elif label=="compile": text = "synthetic compile diagnostic\n" if command["exitCode"] else ""
        else:
            quantities = (0,2) if session["meta"]["tags"]["role"]=="public" else (-1,0,1,2,100,101)
            records = InertSandbox().observe(session["files"][SOURCE_PATH].decode(),quantities)["records"]
            if self.scenario=="false-completion": records[0]["accepted"] = not records[0]["accepted"]
            text = "".join(json.dumps(r,separators=(",",":"))+"\n" for r in records)
        return Response(200,encoded({"stream":"stdout","data":text})+b"\n")


def actor_candidate(false_fix=False):
    actor = Tools(InertSandbox(),Limits())
    actor.execute(Action("reproduce","run_check",{"check":"public"}))
    actor.execute(Action("edit","replace_text",{"path":SOURCE_PATH,"old":ORIGINAL,
                                                 "new":FALSE_FIX if false_fix else REPAIRED,
                                                 "preimage_sha256":actor.source_sha256}))
    actor.execute(Action("public","run_check",{"check":"public"}))
    return actor


def contract_journey(scenario="success",*,clock=None,journal_sink=None):
    actor = actor_candidate(scenario=="false-fix")
    plane = SyntheticPlane(scenario)
    kwargs = {"journal_sink":journal_sink}
    if clock: kwargs["clock"] = clock
    client = SandboxClient(synthetic_config(),plane,**kwargs)
    draft = Proposal(actor.source.encode(),actor.source_sha256,digest(SOURCE),False,digest({"public":"draft"}))
    public = client.execute(draft,probe_plan("public"))
    if public["status"] != "CONTRACT_COMPLETE":
        actor.seal()
        return {"status":public["status"],"public":public,"verifier":None,"domain_verified":False,
                "maximum_synthetic_sessions_active":plane.maximum_active,"actor_closed":actor.closed}
    sealed = Proposal.from_actor(actor)
    verifier = client.execute(sealed,probe_plan("verifier"))
    return {"status":verifier["status"],"public":public,"verifier":verifier,"domain_verified":False,
            "maximum_synthetic_sessions_active":plane.maximum_active,"actor_closed":actor.closed}
