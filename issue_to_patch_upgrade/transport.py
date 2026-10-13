"""Owned, bounded transport for trusted Python only; no Java execution facility."""
from dataclasses import dataclass
import base64
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from .core import Failure, encoded, parse_json


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    ambiguous: bool = False


class ReservationGate:
    """Portable per-run gate, not main's global ledger. Unknown delivery holds reservations."""
    def __init__(self, *, authorized=False, allocation_inr=0, quote_inr=None,
                 model=None, serving_provider=None, metadata_verified=False):
        from decimal import Decimal, InvalidOperation
        try:
            self.allocation = Decimal(str(allocation_inr))
            self.quote = None if quote_inr is None else Decimal(str(quote_inr))
        except InvalidOperation:
            raise Failure("CONFIG_ERROR", "invalid_cost_quote") from None
        if (not self.allocation.is_finite() or self.allocation < 0
                or self.quote is not None and (not self.quote.is_finite() or self.quote <= 0)):
            raise Failure("CONFIG_ERROR", "invalid_cost_quote")
        self.authorized, self.verified = authorized is True, metadata_verified is True
        self.model, self.provider, self.reserved = model, serving_provider, Decimal(0)

    def reserve(self, config):
        if (not self.authorized or not self.verified or self.quote is None
                or self.model != config.model or self.provider != config.serving_provider
                or self.reserved + self.quote > self.allocation):
            raise Failure("AUTHORIZATION_DENIED", "live_dispatch_or_allocation_missing")
        self.reserved += self.quote

    def snapshot(self):
        return {"allocation_inr": str(self.allocation), "held_reservations_inr": str(self.reserved),
                "actual_cost_inr": None, "reconciliation": "main_required", "automatic_retries": 0}


def worker_input(config, body, remaining, *, port=None, credential=None):
    """No caller-controlled host/path; test port is a trusted integration-only injection."""
    if not isinstance(body, bytes) or len(body) > config.limits.request_bytes:
        raise Failure("BUDGET_EXHAUSTED", "request_body_limit")
    if config.mode == "local-double":
        if type(port) is not int or not 1 <= port <= 65535 or credential is not None:
            raise Failure("CONFIG_ERROR", "invalid_double_transport")
    elif (port is not None or not isinstance(credential, str) or not credential
          or len(credential) > 4096 or any(c in credential for c in "\r\n\x00")):
        raise Failure("AUTHORIZATION_DENIED", "runtime_credential_required")
    return encoded({"mode": config.mode, "port": port, "credential": credential,
                    "body": base64.b64encode(body).decode("ascii"),
                    "response_bytes": config.limits.response_bytes,
                    "timeout": min(config.limits.request_seconds, remaining)})


def decode_worker(raw, limit):
    data = parse_json(raw)
    if not isinstance(data, dict) or set(data) != {"status", "body", "error", "ambiguous"}:
        raise Failure("TRANSPORT_ERROR", "invalid_worker_reply", ambiguous=True)
    if type(data["ambiguous"]) is not bool:
        raise Failure("TRANSPORT_ERROR", "invalid_worker_reply", ambiguous=True)
    if data["error"] is not None:
        codes = {"transport_failure", "response_limit", "invalid_worker_input"}
        if not isinstance(data["error"], str) or data["error"] not in codes:
            raise Failure("TRANSPORT_ERROR", "invalid_worker_reply", ambiguous=True)
        raise Failure("TRANSPORT_ERROR", data["error"], ambiguous=data["ambiguous"])
    if type(data["status"]) is not int or not 100 <= data["status"] <= 599 or not isinstance(data["body"], str):
        raise Failure("TRANSPORT_ERROR", "invalid_worker_reply", ambiguous=True)
    try:
        body = base64.b64decode(data["body"], validate=True)
    except ValueError:
        raise Failure("TRANSPORT_ERROR", "invalid_worker_reply", ambiguous=True) from None
    if len(body) > limit:
        raise Failure("TRANSPORT_ERROR", "response_limit", ambiguous=True)
    return Response(data["status"], body, data["ambiguous"])


class OwnedTransport:
    """One owned helper per POST. No fallback, retries, inherited model credentials or shell."""
    def __init__(self, config, *, port=None, credential=None, gate=None, helper=None):
        self.config, self.mode = config, config.mode
        self.port, self.credential, self.gate = port, credential, gate
        self.helper = Path(helper) if helper else Path(__file__).with_name("http_worker.py")
        # A helper override is an explicit trusted test injection, never model-visible.
        self.started = 0
        self.cleanup_complete = True

    def exchange(self, body, *, budget, cancel=None):
        budget.check(cancel)
        if not self.cleanup_complete:
            raise Failure("HANDOFF_REQUIRED", "owned_helper_cleanup_failed", ambiguous=True)
        if self.mode == "live":
            if self.gate is None:
                raise Failure("AUTHORIZATION_DENIED", "live_dispatch_or_allocation_missing")
            self.gate.reserve(self.config)
        data = worker_input(self.config, body, budget.remaining, port=self.port, credential=self.credential)
        seconds = min(budget.remaining, self.config.limits.request_seconds)
        if seconds <= 0.6:
            raise Failure("BUDGET_EXHAUSTED", "insufficient_cleanup_time")
        # Reserve cleanup inside both the request and cumulative wall deadline.
        end = time.monotonic() + seconds
        work_end = end - 0.5
        env = {k: os.environ[k] for k in ("SystemRoot", "SystemDrive", "ProgramData", "TEMP", "TMP", "PATH")
               if k in os.environ}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            child = subprocess.Popen([sys.executable, str(self.helper)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                     env=env, shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            raise Failure("TRANSPORT_ERROR", "helper_start_failed") from None
        self.started += 1
        self.cleanup_complete = False
        output, stderr = bytearray(), bytearray()
        overflow, pipe_failed = threading.Event(), threading.Event()

        def drain(pipe, target, cap):
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    if len(target) + len(chunk) > cap:
                        overflow.set()
                        break
                    target.extend(chunk)
            except (OSError, ValueError):
                pipe_failed.set()

        def write():
            try:
                view = memoryview(data)
                while view:
                    written = child.stdin.write(view)
                    if not written:
                        raise OSError("pipe closed")
                    view = view[written:]
                child.stdin.close()
            except (OSError, ValueError):
                pipe_failed.set()

        readers = [threading.Thread(target=drain, args=(child.stdout, output, 262144), daemon=True),
                   threading.Thread(target=drain, args=(child.stderr, stderr, 4096), daemon=True),
                   threading.Thread(target=write, daemon=True)]
        reason = None
        try:
            for reader in readers:
                reader.start()
            while child.poll() is None:
                if cancel is not None and cancel():
                    reason = Failure("CANCELLED", "cancelled", ambiguous=True)
                    break
                if time.monotonic() >= work_end:
                    reason = Failure("TRANSPORT_TIMEOUT", "transport_total_deadline", ambiguous=True)
                    break
                if overflow.is_set() or pipe_failed.is_set():
                    reason = Failure("TRANSPORT_ERROR", "worker_pipe_limit_or_failure", ambiguous=True)
                    break
                overflow.wait(min(0.01, max(0, work_end - time.monotonic())))
        except KeyboardInterrupt:
            reason = Failure("CANCELLED", "cancelled", ambiguous=True)
        finally:
            try:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=max(0.01, end - time.monotonic()))
            except (OSError, subprocess.TimeoutExpired):
                pass
            for pipe in (child.stdin, child.stdout, child.stderr):
                try:
                    pipe.close()
                except (OSError, ValueError):
                    pass
            for reader in readers:
                if reader.ident is not None:
                    reader.join(timeout=max(0, min(0.1, end - time.monotonic())))
            self.cleanup_complete = child.poll() is not None and not any(r.is_alive() for r in readers)
        if not self.cleanup_complete:
            raise Failure("HANDOFF_REQUIRED", "owned_helper_cleanup_failed", ambiguous=True)
        if reason is not None:
            raise reason
        if overflow.is_set() or pipe_failed.is_set() or child.returncode != 0 or stderr:
            raise Failure("TRANSPORT_ERROR", "worker_failed", ambiguous=True)
        return decode_worker(bytes(output), self.config.limits.response_bytes)

