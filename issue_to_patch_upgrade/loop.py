"""One finite function/tool journey; independent verification starts after actor closure."""
import time
import uuid

from . import DATASET_VERSION, PROMPT_VERSION, VERSION
from .core import Budget, Failure, digest, encoded
from .events import Events, redact
from .fixture import CONTRACT, DATASET_HASH, ISSUE, VISIBLE
from .gateway import SYSTEM_PROMPT
from .tools import Tools
from .verifier import verify


def run(provider, sandbox, config, *, clock=time.monotonic, cancel=None, code_version="unrecorded"):
    # U1 has no genuine sandbox adapter: a live provider is never silently paired with an inert VM.
    if config.mode != "local-double" or sandbox.mode != "local-double":
        raise Failure("AUTHORIZATION_DENIED", "u1_has_no_real_execution_path")
    budget = Budget(config.limits, clock=clock)
    tools = Tools(sandbox, config.limits)
    run_id = uuid.uuid4().hex
    common = {"run_id": run_id, "task_id": "D01-contract", "mode": config.mode, "code_version": code_version,
              "package_version": VERSION, "schema_version": "native-tools-u1", "config_version": "u1-config-1",
              "prompt_version": PROMPT_VERSION, "prompt_sha256": digest(SYSTEM_PROMPT),
              "config_sha256": config.fingerprint, "dataset_version": DATASET_VERSION, "dataset_sha256": DATASET_HASH,
              "model": config.model, "provider": config.serving_provider, "generation_id": None,
              "actual_cost_inr": None, "estimated_cost_inr": None}
    events = Events(common, budget)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": encoded({
        "task_id": "D01-contract", "issue": ISSUE, "contract": CONTRACT, "visible_files": VISIBLE,
        "evidence_mode": "local-double", "execution_authority": "inert_double_only"}).decode()}]
    state, error, independent, ambiguity = "INCOMPLETE", None, {"status": "not_run", "domain_verified": False}, False
    denied = 0
    events.append("run_started", approval={"execution": "inert_only", "live_allocation_inr": 0})
    try:
        while True:
            budget.check(cancel)
            events.append("decision_requested", request_index=budget.requests + 1)
            request_start = budget.clock()
            reply = provider.decide(messages, budget, cancel)
            budget.check(cancel)
            events.append("decision_received", generation_id=reply.generation_id, usage=reply.usage,
                          provider_seconds=budget.clock() - request_start,
                          request_sha256=provider.request_sha256, response_sha256=provider.response_sha256,
                          action_id=reply.action.id, tool=reply.action.tool)
            budget.tool()
            events.append("tool_requested", action_id=reply.action.id, tool=reply.action.tool, args=reply.action.args)
            result = tools.execute(reply.action)
            budget.check(cancel)
            events.append("tool_observed", action_id=reply.action.id, tool=reply.action.tool, result=result)
            messages.extend([reply.assistant_message, {"role": "tool", "tool_call_id": reply.action.id,
                                                      "content": encoded(result).decode()}])
            if len(encoded(messages)) > config.limits.history_bytes:
                raise Failure("BUDGET_EXHAUSTED", "history_limit")
            if reply.action.tool == "abstain":
                state = "ABSTAINED"
                break
            if reply.action.tool == "finish":
                sealed = tools.seal()
                events.append("actor_closed", candidate_sha256=sealed.source_sha256)
                budget.check(cancel)
                independent = verify(sealed, actor_closed=tools.closed)
                budget.check(cancel)
                state = "CONTRACT_COMPLETE" if independent["status"] == "simulated_contract_pass" else "CONTRACT_REJECTED"
                break
    except Failure as failure:
        state, error, ambiguity = failure.status, failure.code, failure.ambiguous
        denied = int(state == "POLICY_DENIED")
    except KeyboardInterrupt:
        state, error = "CANCELLED", "cancelled"
    finally:
        sealed = tools.seal()
    cleanup = getattr(provider.transport, "cleanup_complete", False)
    if not cleanup:
        state, error = "HANDOFF_REQUIRED", "owned_helper_cleanup_failed"
    # Terminal diagnostics survive even when the telemetry cap itself ends the run.
    try:
        events.append("run_finished", outcome=state, error=error, ambiguity=ambiguity,
                      candidate_sha256=sealed.source_sha256, human_intervention=state == "HANDOFF_REQUIRED",
                      cleanup_complete=cleanup, independent_status=independent["status"])
    except Failure:
        pass
    report = {**common, "status": state, "error": error, "ambiguous_delivery": ambiguity,
              "budget": budget.snapshot(), "candidate_sha256": sealed.source_sha256,
              "original_sha256": sealed.original_sha256, "candidate_text": sealed.source,
              "diff": tools.diff(), "edits": tools.edits,
              "changed_lines": tools.changed_lines, "public_checks": tools.checks, "actor_closed": tools.closed,
              "independent": independent, "events": events.records, "messages": messages,
              "unsafe_tool_requests_denied": denied, "unsafe_actions_allowed": 0,
              "real_provider_requests": 0, "generated_code_host_processes": 0, "real_sandbox_sessions": 0,
              "owned_transport_helpers_started": getattr(provider.transport, "started", 0),
              "owned_cleanup_complete": cleanup, "actual_model_tokens": None,
              "evidence": "Authored function-call and inert sandbox doubles; no real repair or live quality claim."}
    return redact(report)

