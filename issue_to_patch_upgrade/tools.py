"""Finite in-memory authority. Text is never interpreted or executed on the host."""
from dataclasses import dataclass
import difflib

from .core import Failure, digest, encoded
from .fixture import CONTRACT, ISSUE, SOURCE, SOURCE_PATH, VISIBLE


@dataclass(frozen=True)
class SealedCandidate:
    source: str
    source_sha256: str
    original_sha256: str
    public_result: dict | None
    edits: int
    changed_lines: int


class Tools:
    def __init__(self, sandbox, limits):
        if sandbox.mode != "local-double":
            raise Failure("AUTHORIZATION_DENIED", "u1_inert_sandbox_only")
        self.sandbox, self.limits = sandbox, limits
        self.source = SOURCE
        self.files = {"issue.md": ISSUE, "contract.md": CONTRACT}
        self.closed = self.reproduced = False
        self.edits = self.changed_lines = self.checks = 0
        self.public_result = None
        self.cache = {}

    @property
    def source_sha256(self):
        return digest(self.source)

    def diff(self):
        return "".join(difflib.unified_diff(SOURCE.splitlines(keepends=True), self.source.splitlines(keepends=True),
                                           fromfile="a/" + SOURCE_PATH, tofile="b/" + SOURCE_PATH))

    def execute(self, action):
        if self.closed:
            raise Failure("POLICY_DENIED", "actor_closed")
        body_hash = digest({"tool": action.tool, "args": action.args})
        if action.id in self.cache:
            previous, result = self.cache[action.id]
            if previous != body_hash:
                raise Failure("POLICY_DENIED", "action_id_conflict")
            return {**result, "idempotent_replay": True}
        args, name = action.args, action.tool
        if name == "list_files":
            result = {"status": "listed", "files": list(VISIBLE)}
        elif name == "read_file":
            if args["path"] not in VISIBLE:
                raise Failure("POLICY_DENIED", "path_not_authorized")
            text = self.source if args["path"] == SOURCE_PATH else self.files[args["path"]]
            lines = text.splitlines()[args["start_line"] - 1:args["start_line"] - 1 + args["max_lines"]]
            result = {"status": "read", "path": args["path"], "text": "\n".join(lines)}
        elif name == "search":
            result = {"status": "searched", "matches": [
                {"path": SOURCE_PATH, "line": i, "text": text} for i, text in enumerate(self.source.splitlines(), 1)
                if args["query"] in text][:100]}
        elif name == "run_check":
            if self.checks >= self.limits.public_checks:
                raise Failure("BUDGET_EXHAUSTED", "public_check_limit")
            self.checks += 1
            result = self.sandbox.public(self.source)
            if result.get("source_sha256") != self.source_sha256 or result.get("mode") != "local-double":
                raise Failure("CONTRACT_REJECTED", "public_observation_identity")
            if self.edits == 0 and result["status"] == "semantic_failure":
                self.reproduced = True
            self.public_result = result
        elif name == "replace_text":
            if args["path"] != SOURCE_PATH:
                raise Failure("POLICY_DENIED", "edit_path_not_authorized")
            if not self.reproduced:
                raise Failure("POLICY_DENIED", "reproduction_required")
            if args["preimage_sha256"] != self.source_sha256:
                raise Failure("POLICY_DENIED", "stale_preimage")
            if self.source.count(args["old"]) != 1:
                raise Failure("POLICY_DENIED", "exact_match_required")
            candidate = self.source.replace(args["old"], args["new"], 1)
            lines = sum(line[:2] in {"+ ", "- "} for line in difflib.ndiff(self.source.splitlines(), candidate.splitlines()))
            if (candidate == self.source or self.edits >= self.limits.edits
                    or self.changed_lines + lines > self.limits.changed_lines or len(candidate.encode()) > 1048576):
                raise Failure("BUDGET_EXHAUSTED", "edit_limit")
            self.source, self.edits = candidate, self.edits + 1
            self.changed_lines += lines
            self.public_result = None
            result = {"status": "edited", "patch_attempt": self.edits}
        elif name == "show_diff":
            result = {"status": "diff", "diff": self.diff()}
        elif name == "finish":
            if (not self.reproduced or not self.edits or not self.public_result
                    or self.public_result.get("status") != "passed"
                    or self.public_result.get("source_sha256") != self.source_sha256):
                raise Failure("POLICY_DENIED", "current_public_success_required")
            result = {"status": "finish_requested"}
        elif name == "abstain":
            result = {"status": "abstained"}
        else:
            raise Failure("POLICY_DENIED", "unknown_tool")
        result = {**result, "source_sha256": self.source_sha256, "mode": "local-double"}
        if len(encoded(result)) > self.limits.observation_bytes:
            raise Failure("BUDGET_EXHAUSTED", "observation_limit")
        self.cache[action.id] = body_hash, result
        return result

    def seal(self):
        self.closed = True
        # Deep-copy observation to keep an external holder from mutating a sealed record.
        import json
        public = json.loads(encoded(self.public_result)) if self.public_result else None
        return SealedCandidate(self.source, self.source_sha256, digest(SOURCE), public, self.edits, self.changed_lines)

