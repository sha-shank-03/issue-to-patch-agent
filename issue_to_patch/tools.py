"""Tool authority, edit idempotency and workflow preconditions outside the provider."""
import json

from .runner import public_verdict
from .workspace import AuthorityError, BudgetError, SOURCE


class Tools:
    def __init__(self, workspace, runner, trust):
        self.workspace, self.runner, self.trust = workspace, runner, trust
        self.reproduced = False
        self.reproduction = None
        self.public_result = None
        self.checks = 0
        self.closed = False
        self.requests = {}

    def dispatch(self, action):
        if self.closed:
            raise AuthorityError("tool channel is closed")
        body = json.dumps({"tool": action.tool, "args": action.args}, sort_keys=True)
        if action.id in self.requests:
            previous_body, previous_result = self.requests[action.id]
            if previous_body != body:
                raise AuthorityError("action ID reused with different content")
            return dict(previous_result, duplicate=True)
        args, tool, ws = action.args, action.tool, self.workspace
        if tool == "list_files":
            result = {"status": "listed", "files": list(ws.visible)}
        elif tool == "read_file":
            result = {"status": "read", "path": args["path"],
                      "text": ws.read(args["path"], args["start_line"], args["max_lines"])}
        elif tool == "search":
            matches = []
            for path in ws.visible:
                for line, text in enumerate(ws.read(path).splitlines(), 1):
                    if args["query"] in text:
                        matches.append({"path": path, "line": line, "text": text})
            result = {"status": "searched", "matches": matches[:20]}
        elif tool == "run_check":
            if self.checks >= 5:
                raise BudgetError("public-check budget exhausted")
            self.checks += 1
            result = public_verdict(self.runner.observe(ws), self.trust)
            self.public_result = result
            if ws.digest == ws.original_digest and not self.reproduced:
                self.reproduction = result
                self.reproduced = result["status"] == "semantic_failure"
        elif tool == "replace_text":
            if not self.reproduced:
                raise AuthorityError("edit requires semantic reproduction")
            result = ws.replace(**args)
            self.public_result = None
            result["execution"] = "permitted" if self.trust.permits(ws.path(SOURCE)) else "proposal_only"
        elif tool == "show_diff":
            result = {"status": "diff", "text": ws.diff()}
        elif tool == "finish":
            if (not self.reproduced or not self.public_result or self.public_result["status"] != "passed"
                    or self.public_result["source_sha256"] != ws.digest):
                raise AuthorityError("finish requires current public checks after reproduction")
            ws.frozen = True
            self.closed = True
            result = {"status": "finished", "summary": args["summary"]}
        elif tool == "abstain":
            self.closed, ws.frozen = True, True
            result = {"status": "abstained", "reason": args["reason"]}
        else:
            raise AuthorityError("tool not allowed")
        self.requests[action.id] = body, result
        return result
