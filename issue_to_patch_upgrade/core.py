"""Small typed limits, persistent accounting and credential-free configuration."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
import time

from issue_to_patch.protocol import ProtocolError, strict_json


class Failure(ValueError):
    """Safe constant codes only: never expose a transport/provider error body."""
    def __init__(self, status, code, *, ambiguous=False):
        super().__init__(code)
        self.status, self.code, self.ambiguous = status, code, ambiguous


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    data = value.encode("utf-8") if isinstance(value, str) else encoded(value)
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Limits:
    wall_seconds: float = 60
    request_seconds: float = 20
    requests: int = 12
    tools: int = 20
    tokens: int = 65536
    output_tokens: int = 2048
    request_bytes: int = 131072
    response_bytes: int = 131072
    history_bytes: int = 131072
    observation_bytes: int = 24576
    edits: int = 3
    changed_lines: int = 200
    public_checks: int = 8

    def __post_init__(self):
        maxima = {"requests": 12, "tools": 20, "tokens": 65536, "output_tokens": 2048,
                  "request_bytes": 131072, "response_bytes": 131072, "history_bytes": 131072,
                  "observation_bytes": 24576, "edits": 3, "changed_lines": 200, "public_checks": 8}
        for name, maximum in maxima.items():
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= maximum:
                raise Failure("CONFIG_ERROR", "invalid_limit")
        for name, maximum in (("wall_seconds", 600), ("request_seconds", 20)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
                raise Failure("CONFIG_ERROR", "invalid_deadline")


@dataclass(frozen=True)
class Config:
    model: str
    serving_provider: str
    mode: str = "local-double"
    limits: Limits = Limits()

    def __post_init__(self):
        if (not isinstance(self.model, str) or not re.fullmatch(r"[a-z0-9.-]+/[a-zA-Z0-9_.:-]+", self.model)
                or len(self.model) > 200 or not isinstance(self.serving_provider, str)
                or not re.fullmatch(r"[a-z0-9.-]{1,64}", self.serving_provider)
                or self.mode not in {"local-double", "live"} or not isinstance(self.limits, Limits)):
            raise Failure("CONFIG_ERROR", "explicit_model_provider_required")
        if self.mode == "local-double" and (self.model != "test/synthetic-coder" or self.serving_provider != "test"):
            raise Failure("CONFIG_ERROR", "double_identity_required")

    @property
    def fingerprint(self):
        return digest(asdict(self))


class Budget:
    """Counters persist in reports; U1 refuses execution resume rather than resetting them."""
    def __init__(self, limits, *, clock=time.monotonic):
        self.limits, self.clock = limits, clock
        self.started = clock()
        self.requests = self.tools = self.observed_tokens = 0
        self.usage_complete = True

    @property
    def remaining(self):
        return max(0.0, self.limits.wall_seconds - (self.clock() - self.started))

    def check(self, cancel=None):
        if cancel is not None and cancel():
            raise Failure("CANCELLED", "cancelled")
        if self.remaining <= 0:
            raise Failure("BUDGET_EXHAUSTED", "total_deadline")
        if self.observed_tokens >= self.limits.tokens:
            raise Failure("BUDGET_EXHAUSTED", "token_limit")

    def request(self):
        self.check()
        if self.requests >= self.limits.requests:
            raise Failure("BUDGET_EXHAUSTED", "request_limit")
        self.requests += 1

    def tool(self):
        self.check()
        if self.tools >= self.limits.tools:
            raise Failure("BUDGET_EXHAUSTED", "tool_limit")
        self.tools += 1

    def usage(self, usage):
        if usage is None:
            self.usage_complete = False
            return
        self.observed_tokens += usage["total_tokens"]
        if self.observed_tokens > self.limits.tokens:
            raise Failure("BUDGET_EXHAUSTED", "token_limit")

    def snapshot(self):
        return {"requests": self.requests, "tool_attempts": self.tools,
                "observed_tokens": self.observed_tokens, "usage_complete": self.usage_complete,
                "active_seconds": max(0, self.clock() - self.started), "limits": asdict(self.limits),
                "automatic_transport_retries": 0, "resume_supported": False}


def parse_json(raw):
    try:
        return strict_json(raw)
    except (ProtocolError, UnicodeError, RecursionError):
        raise Failure("PROTOCOL_ERROR", "invalid_json") from None

