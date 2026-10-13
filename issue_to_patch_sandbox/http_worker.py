"""Trusted bounded REST helper; fixed HTTPS api.vercel.com or explicit literal loopback."""
import base64
import http.client
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from issue_to_patch_upgrade.core import Failure, parse_json
from issue_to_patch_sandbox.wire import decode_request


def main():
    connection = None
    attempted = False
    result = {"status":None,"body":"","error":"invalid_worker_input","ambiguous":False}
    try:
        raw = sys.stdin.buffer.read(262145)
        if len(raw)>262144: raise ValueError()
        data = parse_json(raw)
        if set(data) != {"mode","port","credential","body","response_bytes","timeout"}: raise ValueError()
        if type(data["response_bytes"]) is not int or not 1<=data["response_bytes"]<=65536: raise ValueError()
        if type(data["timeout"]) not in (int,float) or not math.isfinite(data["timeout"]) or not 0<data["timeout"]<=20: raise ValueError()
        frame,payload = decode_request(base64.b64decode(data["body"],validate=True))
        headers = {"Content-Type":frame["content_type"]}
        if frame["cwd"] is not None: headers["x-cwd"] = frame["cwd"]
        if data["mode"] == "local-double":
            if type(data["port"]) is not int or not 1<=data["port"]<=65535 or data["credential"] is not None: raise ValueError()
            connection = http.client.HTTPConnection("127.0.0.1",data["port"],timeout=data["timeout"])
        elif data["mode"] == "live":
            key = data["credential"]
            if data["port"] is not None or not isinstance(key,str) or not 0<len(key)<=4096 or any(c in key for c in "\r\n\x00"): raise ValueError()
            connection = http.client.HTTPSConnection("api.vercel.com",timeout=data["timeout"])
            headers["Authorization"] = "Bearer "+key
        else: raise ValueError()
        http.client._MAXHEADERS = 32
        http.client._MAXLINE = 8192
        attempted = True
        connection.request(frame["method"],frame["path"],body=payload,headers=headers)
        response = connection.getresponse()
        limit = data["response_bytes"]
        length = response.getheader("Content-Length")
        if length is not None and not 0<=int(length)<=limit:
            result["error"] = "response_limit"
        else:
            body = response.read(limit+1)
            if len(body)>limit: result["error"] = "response_limit"
            else: result.update(status=response.status,error=None,body=base64.b64encode(body if response.status==200 else b"").decode("ascii"))
    except (Failure,OSError,ValueError,TypeError,KeyError,http.client.HTTPException):
        result["error"] = "transport_failure" if attempted else "invalid_worker_input"
    finally:
        result["ambiguous"] = attempted and result["error"] is not None
        if connection is not None: connection.close()
    sys.stdout.buffer.write(json.dumps(result,separators=(",",":")).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
