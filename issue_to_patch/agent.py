"""One bounded decision/tool loop; private verification occurs after it closes."""
import json
from pathlib import Path
import time
import uuid

from evaluation.evaluator import evaluate
from .protocol import ProtocolError, parse_action
from .providers import ProviderError
from .runner import JavaRunner
from .tools import Tools
from .workspace import AuthorityError, BudgetError, SOURCE, Trust, Workspace, atomic_json

EXIT_CODES = {"ACCEPTED": 0, "REJECTED": 2, "NOT_REPRODUCED": 2,
              "REVIEW_REQUIRED": 3, "ABSTAINED": 3, "BUDGET_EXHAUSTED": 3,
              "POLICY_DENIED": 3, "INFRA_ERROR": 4, "CANCELLED": 130}


def run(repo, provider, *, case_id="V01", runner_factory=JavaRunner, max_decisions=20,
        wall_seconds=120, max_observed_tokens=16384):
    if (type(max_decisions) is not int or not 0 <= max_decisions <= 100
            or not 0 < wall_seconds <= 600 or type(max_observed_tokens) is not int or max_observed_tokens < 1):
        raise ValueError("invalid run budget")
    start = time.monotonic()
    repo = Path(repo).resolve()
    trust = Trust(repo, case_id)
    run_dir = repo / "work/runs" / uuid.uuid4().hex
    ws = Workspace(repo, run_dir, trust)
    runner = runner_factory(repo, trust)
    runner.deadline = start + wall_seconds
    tools = Tools(ws, runner, trust)
    history, last, state = [], None, "INSPECTING"
    independent = {"status": "not_run"}
    corrections = 0
    observed_usage = []
    observed_tokens = 0
    metadata = {"provider": "unknown", "model": None}
    error = None
    trace = run_dir / "trace.jsonl"

    def record(entry):
        history.append(entry)
        with trace.open("a", encoding="utf-8") as output:
            output.write(json.dumps(entry, sort_keys=True) + "\n")

    def within_budget():
        if time.monotonic() >= runner.deadline:
            raise BudgetError("wall-time budget exhausted")
        if observed_tokens > max_observed_tokens:
            raise BudgetError("observed token budget exhausted")

    try:
        for decision in range(max_decisions):
            within_budget()
            trust.verify_immutable()
            ws.verify_public_copy(trust)
            observation = {"protocol_version": 1, "case": case_id, "state": state,
                           "issue": ws.read("issue.md"), "contract": ws.read("contract.md"),
                           "visible_files": list(ws.visible),
                           "source_sha256": ws.digest, "last_result": last, "history": history,
                           "remaining": {"decisions": max_decisions - decision, "patches": 3 - ws.patch_attempts,
                                         "public_checks": 5 - tools.checks,
                                         "wall_seconds": max(0, runner.deadline - time.monotonic()),
                                         "observed_tokens": max(0, max_observed_tokens - observed_tokens)}}
            if hasattr(provider, "timeout"):
                provider.timeout = min(provider.timeout, observation["remaining"]["wall_seconds"])
            reply = provider.decide(observation)
            metadata = reply.metadata
            if reply.usage is not None:
                observed_usage.append(reply.usage)
                for value in reply.usage.values():
                    if value is not None:
                        if type(value) is not int or value < 0:
                            raise ProviderError("invalid observed usage")
                        observed_tokens += value
            within_budget()
            try:
                action = parse_action(reply.action_json)
            except ProtocolError as exc:
                corrections += 1
                last = {"status": "protocol_error", "error": str(exc)}
                record({"sequence": len(history) + 1, "state": state, "result": last})
                if corrections >= 2:
                    state = "POLICY_DENIED"
                    break
                continue
            before = state
            try:
                last = tools.dispatch(action)
            except AuthorityError as exc:
                record({"sequence": len(history) + 1, "state_before": before,
                        "action": {"id": action.id, "tool": action.tool, "args": action.args},
                        "result": {"status": "denied", "error": str(exc)}})
                raise
            if action.tool == "run_check":
                if last["status"] not in {"passed", "semantic_failure"}:
                    state = "INFRA_ERROR"
                elif not tools.reproduced:
                    state = "NOT_REPRODUCED"
                else:
                    state = "EDITING" if last["status"] == "semantic_failure" else "CHECKING"
            elif action.tool == "replace_text":
                state = "REVIEW_REQUIRED" if last["execution"] == "proposal_only" else "CHECKING"
            elif action.tool == "finish":
                state = "FROZEN"
            elif action.tool == "abstain":
                state = "ABSTAINED"
            record({"sequence": len(history) + 1, "state_before": before, "state_after": state,
                    "action": {"id": action.id, "tool": action.tool, "args": action.args}, "result": last,
                    "provider": metadata})
            within_budget()
            if state in EXIT_CODES or state == "FROZEN":
                break
        else:
            state = "BUDGET_EXHAUSTED"
        tools.closed, ws.frozen = True, True
        if state == "FROZEN":
            within_budget()
            independent = evaluate(ws, runner)
            within_budget()
            state = {"accepted": "ACCEPTED", "rejected": "REJECTED"}.get(independent["status"], "INFRA_ERROR")
    except KeyboardInterrupt:
        state, error = "CANCELLED", "keyboard cancellation"
    except (AuthorityError, ProviderError, ValueError, OSError) as exc:
        state = "BUDGET_EXHAUSTED" if isinstance(exc, BudgetError) else "POLICY_DENIED" if isinstance(exc, AuthorityError) else "INFRA_ERROR"
        error = str(exc).replace(str(repo), "<repo>")
    tools.closed, ws.frozen = True, True
    final_digest = ws.digest
    execution_kind = getattr(runner, "execution_kind", "unspecified_double")
    scripted = metadata.get("provider") == "scripted"
    evidence_kind = "scripted_workflow" if scripted else "provider_protocol_or_proposal"
    if execution_kind != "java_subprocess":
        evidence_kind = "scripted_protocol_double" if scripted else "protocol_double"
    report = {"schema_version": 2, "case": case_id, "family": trust.case_info["family"],
              "split": trust.case_info["split"], "milestone": 2, "status": state,
              "exit_code": EXIT_CODES.get(state, 4), "error": error,
              "evidence_kind": evidence_kind, "execution_kind": execution_kind,
              "provider": metadata, "model_usage": observed_usage or None,
              "observed_tokens": observed_tokens, "token_usage_complete": bool(observed_usage) and
                  all(all(value is not None for value in usage.values()) for usage in observed_usage),
              "provider_http_requests": getattr(provider, "request_count", 0),
              "model_requests": 0 if metadata.get("provider") == "scripted" else None,
              "live_heldout_solve_rate": None, "live_tasks_attempted": 0,
              "original_source_sha256": ws.original_digest, "candidate_source_sha256": final_digest,
              "trust_manifest_sha256": trust.manifest_hash, "immutable_sha256": trust.fingerprints,
              "reproduction": tools.reproduction, "public_check": tools.public_result,
              "independent": independent, "decisions": len(history), "patch_attempts": ws.patch_attempts,
              "changed_lines": ws.changed_lines, "public_checks": tools.checks,
              "commands": runner.commands,
              "post_edit_processes": sum(command.get("source_sha256") != ws.original_digest for command in runner.commands),
              "elapsed_seconds": round(time.monotonic() - start, 6),
              "unexecuted_checks": ["live model inference", "M3 baseline comparison", "hosted CI"] +
                  (["Java compilation and execution (Python double only)"] if execution_kind != "java_subprocess" else [])}
    (run_dir / "patch.diff").write_text(ws.diff(), encoding="utf-8")
    atomic_json(run_dir / "manifest.json", {"case": case_id, "schema_version": 2,
                                            "original_source_sha256": ws.original_digest,
                                            "candidate_source_sha256": final_digest,
                                            "immutable_sha256": trust.fingerprints})
    atomic_json(run_dir / "report.json", report)
    verdict = independent.get("status", "not_run")
    (run_dir / "report.md").write_text(
        f"# {case_id} report\n\nStatus: {state}. Evidence: {report['evidence_kind']}.\n\n"
        f"Candidate SHA-256: {final_digest}\n\nIndependent verification: {verdict}; "
        f"{independent.get('passed_assertions', 0)}/{independent.get('assertion_count', 0)} assertions passed.\n\n"
        f"Patch attempts: {ws.patch_attempts}; public checks: {tools.checks}.\n\n"
        "Decisions are authored in scripted mode. Novel patches are proposal-only. "
        "Live held-out solve rate is unmeasured. A subprocess is not a hostile-code sandbox.\n",
        encoding="utf-8")
    return report, run_dir
