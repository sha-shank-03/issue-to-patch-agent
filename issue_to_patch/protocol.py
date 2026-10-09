"""Strict model-facing action protocol; no strings are interpreted as shell code."""
from dataclasses import dataclass
import json
import re


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Action:
    id: str
    tool: str
    args: dict


@dataclass(frozen=True)
class ProviderReply:
    action_json: str
    metadata: dict
    usage: dict | None = None


FIELDS = {
    "list_files": {},
    "read_file": {"path": "text", "start_line": "positive", "max_lines": "lines"},
    "search": {"query": "query"},
    "run_check": {"check": "check"},
    "replace_text": {"path": "text", "preimage_sha256": "sha", "old": "edit", "new": "edit"},
    "show_diff": {},
    "finish": {"summary": "summary"},
    "abstain": {"reason": "summary"},
}


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def strict_json(raw):
    def reject_constant(value):
        raise ProtocolError("non-finite JSON value")
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject_constant)
    except (ValueError, TypeError) as exc:
        raise ProtocolError(str(exc)) from exc


def parse_action(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 65536:
        raise ProtocolError("action exceeds response bound")
    value = strict_json(raw)
    if not isinstance(value, dict) or set(value) != {"id", "tool", "args"}:
        raise ProtocolError("action requires exactly id, tool, args")
    if not isinstance(value["id"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value["id"]):
        raise ProtocolError("invalid action ID")
    tool, args = value["tool"], value["args"]
    if not isinstance(tool, str) or tool not in FIELDS:
        raise ProtocolError("unknown tool")
    if not isinstance(args, dict) or set(args) != set(FIELDS[tool]):
        raise ProtocolError("wrong tool arguments")
    for key, kind in FIELDS[tool].items():
        item = args[key]
        if kind in {"positive", "lines"}:
            upper = 200 if kind == "lines" else 100000
            if type(item) is not int or not 1 <= item <= upper:
                raise ProtocolError("line bounds invalid")
        else:
            limits = {"text": 200, "sha": 64, "edit": 8192, "summary": 1024, "query": 128, "check": 16}
            if not isinstance(item, str) or not item or "\x00" in item or len(item.encode("utf-8")) > limits[kind]:
                raise ProtocolError("string bound invalid")
            if kind == "sha" and not re.fullmatch(r"[a-f0-9]{64}", item):
                raise ProtocolError("invalid source digest")
            if kind == "check" and item != "public":
                raise ProtocolError("unknown public check")
    return Action(value["id"], tool, args)


def action_schema():
    """The same finite tool variants sent to a structured-output provider."""
    variants = []
    for tool, fields in FIELDS.items():
        properties = {}
        for name, kind in fields.items():
            if kind in {"positive", "lines"}:
                spec = {"type": "integer", "minimum": 1, "maximum": 200 if kind == "lines" else 100000}
            else:
                spec = {"type": "string", "minLength": 1}
                if kind == "check":
                    spec["enum"] = ["public"]
                if kind == "sha":
                    spec["pattern"] = "^[a-f0-9]{64}$"
            properties[name] = spec
        variants.append({"type": "object", "additionalProperties": False,
                         "required": ["id", "tool", "args"], "properties": {
                             "id": {"type": "string", "pattern": "^[A-Za-z0-9_.-]{1,64}$"},
                             "tool": {"type": "string", "enum": [tool]},
                             "args": {"type": "object", "additionalProperties": False,
                                      "required": list(fields), "properties": properties}}})
    return {"oneOf": variants}
