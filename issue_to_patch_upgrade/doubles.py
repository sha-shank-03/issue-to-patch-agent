"""Authored function-call double, visibly labelled; not model inference or a sandbox."""
from .core import Failure, encoded, parse_json
from .fixture import FALSE_FIX, INTERMEDIATE, ORIGINAL, REPAIRED, SOURCE_PATH
from .transport import Response


def completion(model, call_id, name, args, *, usage=None):
    return encoded({"id": "double-" + call_id, "object": "chat.completion", "model": model,
                    "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                        "role": "assistant", "content": None, "tool_calls": [
                            {"id": call_id, "type": "function", "function": {"name": name, "arguments": encoded(args).decode()}}]}}],
                    "usage": usage})


class InertGateway:
    mode = "local-double"
    started = 0
    cleanup_complete = True

    def __init__(self, scenario="repair"):
        if scenario not in {"repair", "false-fix", "early-finish", "unknown-tool", "http-401", "http-402",
                            "http-429", "http-503", "malformed", "ambiguous-loss"}:
            raise Failure("CONFIG_ERROR", "unknown_double_scenario")
        self.scenario, self.requests = scenario, []

    def exchange(self, body, *, budget, cancel=None):
        budget.check(cancel)
        payload = parse_json(body)
        self.requests.append(payload)
        index = len(self.requests)
        if self.scenario.startswith("http-"):
            return Response(int(self.scenario[5:]), b"discarded synthetic error")
        if self.scenario == "ambiguous-loss":
            raise Failure("TRANSPORT_ERROR", "transport_failure", ambiguous=True)
        if self.scenario == "malformed":
            return Response(200, b'{"id":1,"id":2}')
        if self.scenario == "early-finish":
            name, args = "finish", {"summary": "An untrusted completion claim."}
        elif self.scenario == "unknown-tool":
            name, args = "shell", {"command": "denied"}
        else:
            messages = payload["messages"]
            last = parse_json(messages[-1]["content"]) if messages[-1]["role"] == "tool" else None
            status = last.get("status") if last else None
            if status is None:
                name, args = "list_files", {}
            elif status == "listed":
                name, args = "read_file", {"path": SOURCE_PATH, "start_line": 1, "max_lines": 200}
            elif status == "read":
                name, args = "search", {"query": "quantity"}
            elif status in {"searched", "edited"}:
                name, args = "run_check", {"check": "public"}
            elif status == "semantic_failure":
                already_edited = any(m["role"] == "tool" and parse_json(m["content"]).get("status") == "edited"
                                     for m in messages)
                old = INTERMEDIATE if already_edited else ORIGINAL
                new = REPAIRED if already_edited else FALSE_FIX if self.scenario == "false-fix" else INTERMEDIATE
                name, args = "replace_text", {"path": SOURCE_PATH, "preimage_sha256": last["source_sha256"],
                                              "old": old, "new": new}
            elif status == "passed":
                name, args = "show_diff", {}
            elif status == "diff":
                name, args = "finish", {"summary": "Authored protocol proposal; independent simulation only."}
            else:
                raise Failure("PROTOCOL_ERROR", "double_journey_mismatch")
        return Response(200, completion(payload["model"], "call-" + str(index), name, args))

