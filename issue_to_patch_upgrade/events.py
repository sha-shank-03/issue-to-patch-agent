"""Bounded local telemetry. Provider error bodies and credentials are never fields."""
import re
from datetime import datetime, timezone

from .core import Failure, encoded

SECRET_KEYS = {"authorization", "api_key", "ai_gateway_api_key", "password", "secret", "credential",
               "credentials", "access_token", "vercel_token", "vercel_oidc_token"}


def redact(value, canaries=()):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if str(k).lower() in SECRET_KEYS else redact(v, canaries)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, canaries) for v in value]
    if isinstance(value, str):
        for secret in canaries:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        value = re.sub(r"\bsk-[a-zA-Z0-9_-]+", "[REDACTED]", value)
        return re.sub(r"(?i)\b[A-Z_]*(?:API_KEY|TOKEN|PASSWORD)\s*=\s*[^\s\"']+", "[REDACTED]", value)
    return value


class Events:
    def __init__(self, common, budget, canaries=()):
        self.common, self.budget, self.canaries = common, budget, canaries
        self.records = []
        self.bytes = 0

    def append(self, kind, **fields):
        item = redact({**self.common, "sequence": len(self.records), "kind": kind,
                       "wall_time": datetime.now(timezone.utc).isoformat(),
                       "active_seconds": self.budget.snapshot()["active_seconds"], **fields}, self.canaries)
        size = len(encoded(item))
        if len(self.records) >= 128 or size > 65536 or self.bytes + size > 2097152:
            raise Failure("BUDGET_EXHAUSTED", "event_limit")
        self.records.append(item)
        self.bytes += size
        return item

