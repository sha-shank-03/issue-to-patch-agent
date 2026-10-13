"""Fixed Sandbox control-plane envelope; no caller-selected authority or guest command API."""
import base64
import re
from urllib.parse import parse_qs, urlsplit
from issue_to_patch_upgrade.core import Failure, parse_json
from .contract import ROOT, SOURCE_PATH, PROBE_PATH, fixed_commands


def decode_request(raw):
    if not isinstance(raw,bytes) or len(raw) > 131072:
        raise Failure("PROTOCOL_ERROR","sandbox_wire_limit")
    value = parse_json(raw)
    if not isinstance(value,dict) or set(value) != {"method","path","content_type","cwd","payload"}:
        raise Failure("PROTOCOL_ERROR","sandbox_wire_schema")
    if not isinstance(value["path"],str) or len(value["path"]) > 1024:
        raise Failure("PROTOCOL_ERROR","sandbox_wire_route")
    try:
        url = urlsplit(value["path"])
    except ValueError:
        raise Failure("POLICY_DENIED","sandbox_wire_route") from None
    if url.scheme or url.netloc or url.fragment or "%" in url.path:
        raise Failure("POLICY_DENIED","sandbox_wire_route")
    token = r"[A-Za-z0-9_-]{1,128}"
    name = r"ipa-[a-f0-9]{32}-(?:public|verifier)-[12]"
    routes = {"POST": [r"/v4/sandboxes",rf"/v2/sandboxes/sessions/{token}/(?:stop|fs/read|fs/write|cmd)"],
              "GET": [rf"/v2/sandboxes/{name}",rf"/v2/sandboxes/sessions/{token}",
                      rf"/v2/sandboxes/sessions/{token}/cmd/{token}(?:/logs)?"],
              "DELETE": [rf"/v2/sandboxes/{name}"]}
    if not isinstance(value["method"],str) or value["method"] not in routes or not any(re.fullmatch(p,url.path) for p in routes[value["method"]]):
        raise Failure("POLICY_DENIED","sandbox_wire_route")
    try:
        query = parse_qs(url.query,strict_parsing=True)
    except ValueError:
        raise Failure("POLICY_DENIED","sandbox_wire_query") from None
    if set(query) - {"teamId","projectId","resume","wait"} or any(len(v)!=1 for v in query.values()):
        raise Failure("POLICY_DENIED","sandbox_wire_query")
    if not re.fullmatch(r"team_[A-Za-z0-9_-]{1,100}",query.get("teamId",[""])[0]):
        raise Failure("POLICY_DENIED","sandbox_wire_query")
    named = bool(re.fullmatch(rf"/v2/sandboxes/{name}",url.path))
    if named:
        expected = {"teamId","projectId"} | ({"resume"} if value["method"]=="GET" else set())
        if set(query)!=expected or not re.fullmatch(r"prj_[A-Za-z0-9_-]{1,100}",query["projectId"][0]):
            raise Failure("POLICY_DENIED","sandbox_wire_query")
        if value["method"]=="GET" and query["resume"] != ["false"]:
            raise Failure("POLICY_DENIED","sandbox_auto_resume_forbidden")
    else:
        expected = {"teamId"} | ({"wait"} if re.fullmatch(rf"/v2/sandboxes/sessions/{token}/cmd/{token}",url.path) else set())
        if set(query)!=expected or ("wait" in query and query["wait"] != ["true"]):
            raise Failure("POLICY_DENIED","sandbox_wire_query")
    if not isinstance(value["payload"],str):
        raise Failure("PROTOCOL_ERROR","sandbox_wire_body")
    try:
        payload = base64.b64decode(value["payload"],validate=True)
    except ValueError:
        raise Failure("PROTOCOL_ERROR","sandbox_wire_body") from None
    upload = url.path.endswith("/fs/write")
    if len(payload)>65536 or (value["method"] in {"GET","DELETE"} and payload):
        raise Failure("BUDGET_EXHAUSTED","sandbox_wire_body")
    if value["content_type"] != ("application/gzip" if upload else "application/json") or value["cwd"] != (ROOT if upload else None):
        raise Failure("POLICY_DENIED","sandbox_wire_headers")
    if payload and not upload:
        body = parse_json(payload)
        if not isinstance(body,dict):
            raise Failure("POLICY_DENIED","sandbox_wire_body")
        if url.path.endswith("/cmd"):
            fields = {"command","args","cwd","env","sudo","wait","logs","attachStdin","timeout"}
            allowed = [(program,args) for _,program,args in fixed_commands(None)]
            if (set(body)!=fields or (body["command"],body["args"]) not in allowed or body["cwd"]!=ROOT
                    or body["env"]!={} or any(body[k] is not False for k in ("sudo","wait","logs","attachStdin"))
                    or type(body["timeout"]) is not int or not 100<=body["timeout"]<=15000):
                raise Failure("POLICY_DENIED","sandbox_fixed_argv_required")
        elif url.path.endswith("/fs/read"):
            if set(body)!={"path","cwd"} or body["path"] not in {SOURCE_PATH,PROBE_PATH} or body["cwd"]!=ROOT:
                raise Failure("POLICY_DENIED","sandbox_fixed_read_path_required")
        elif url.path=="/v4/sandboxes":
            fields = {"projectId","name","image","architecture","resources","persistent","networkPolicy","ports","env","timeout","tags"}
            if (set(body)!=fields or body["persistent"] is not False or body["ports"]!=[] or body["env"]!={}
                    or body["networkPolicy"]!={"mode":"deny-all"} or body["resources"]!={"vcpus":1,"memory":2048}
                    or any(type(body["resources"][k]) is not int for k in ("vcpus","memory"))
                    or body["architecture"]!="amd64" or type(body["timeout"]) is not int or not 1<=body["timeout"]<=180000
                    or not isinstance(body["projectId"],str) or not re.fullmatch(r"prj_[A-Za-z0-9_-]{1,100}",body["projectId"])
                    or not isinstance(body["name"],str) or not re.fullmatch(name,body["name"])
                    or not isinstance(body["image"],str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@sha256:[0-9a-f]{64}",body["image"])
                    or not isinstance(body["tags"],dict) or body["tags"]!={"run":body["name"][4:36],"role":body["name"].split("-")[-2]}):
                raise Failure("POLICY_DENIED","sandbox_pinned_creation_required")
        else:
            raise Failure("POLICY_DENIED","sandbox_empty_body_required")
    elif not payload and value["method"]=="POST" and not url.path.endswith("/stop"):
        raise Failure("POLICY_DENIED","sandbox_wire_body_required")
    return value,payload
