"""Trusted transport helper. Private input arrives on stdin, never argv/env/logs."""
import base64
import http.client
import json
import sys


def main():
    connection = None
    attempted = False
    result = {"status": None, "body": "", "error": "invalid_worker_input", "ambiguous": False}
    try:
        raw = sys.stdin.buffer.read(262145)
        if len(raw) > 262144:
            raise ValueError()
        data = json.loads(raw)
        if set(data) != {"mode", "port", "credential", "body", "response_bytes", "timeout"}:
            raise ValueError()
        if type(data["response_bytes"]) is not int or not 1 <= data["response_bytes"] <= 131072:
            raise ValueError()
        if type(data["timeout"]) not in (int, float) or not 0 < data["timeout"] <= 20:
            raise ValueError()
        body = base64.b64decode(data["body"], validate=True)
        if len(body) > 131072:
            raise ValueError()
        headers = {"Content-Type": "application/json"}
        if data["mode"] == "local-double":
            if type(data["port"]) is not int or not 1 <= data["port"] <= 65535 or data["credential"] is not None:
                raise ValueError()
            connection = http.client.HTTPConnection("127.0.0.1", data["port"], timeout=data["timeout"])
        elif data["mode"] == "live":
            key = data["credential"]
            if data["port"] is not None or not isinstance(key, str) or not key or any(c in key for c in "\r\n\x00"):
                raise ValueError()
            connection = http.client.HTTPSConnection("ai-gateway.vercel.sh", timeout=data["timeout"])
            headers["Authorization"] = "Bearer " + key
        else:
            raise ValueError()
        attempted = True
        connection.request("POST", "/v1/chat/completions", body=body, headers=headers)
        response = connection.getresponse()
        limit = data["response_bytes"]
        length = response.getheader("Content-Length")
        if length is not None and (int(length) < 0 or int(length) > limit):
            result["error"] = "response_limit"
        else:
            content = response.read(limit + 1)
            if len(content) > limit:
                result["error"] = "response_limit"
            else:
                # Error bodies are intentionally discarded at the earliest boundary.
                result.update(status=response.status, error=None,
                              body=base64.b64encode(content if response.status == 200 else b"").decode("ascii"))
    except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
        result["error"] = "transport_failure" if attempted else "invalid_worker_input"
    finally:
        result["ambiguous"] = attempted and result["error"] is not None
        if connection is not None:
            connection.close()
    sys.stdout.buffer.write(json.dumps(result, separators=(",", ":")).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

