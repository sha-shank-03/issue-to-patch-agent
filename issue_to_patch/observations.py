"""Strict, typed domain observations. Expected outcomes are host-selected."""
import re
from .workspace import AuthorityError


def parse(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 65536:
        raise AuthorityError("probe observation exceeds bound")
    rows = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            raise AuthorityError("malformed typed observation")
        scenario, field, kind, text = parts
        key = scenario + "." + field
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", key) or key in rows:
            raise AuthorityError("duplicate/invalid observation ID")
        if kind == "bool" and text in {"true", "false"}:
            value = text == "true"
        elif kind == "int" and re.fullmatch(r"-?[0-9]{1,20}", text):
            value = int(text)
        elif kind == "ints" and (text == "" or re.fullmatch(r"-?[0-9]{1,20}(?:,-?[0-9]{1,20}){0,127}", text)):
            value = [] if not text else [int(item) for item in text.split(",")]
        else:
            raise AuthorityError("invalid observation type/value")
        rows[key] = value
    return rows


def compare(raw, expected):
    rows = parse(raw)
    if set(rows) != set(expected):
        raise AuthorityError("missing/unexpected observation fields")
    assertions = [{"id": key, "expected": value, "actual": rows[key],
                   "passed": type(rows[key]) is type(value) and rows[key] == value}
                  for key, value in sorted(expected.items())]
    failures = [item["id"] for item in assertions if not item["passed"]]
    return {"assertions": assertions, "assertion_count": len(assertions),
            "passed_assertions": len(assertions) - len(failures), "failures": failures,
            "scenario_count": len({key.split(".")[0] for key in expected})}
