"""Development-only scripted ablation and timing; no live solve-rate claim."""
import hashlib
import json
from pathlib import Path
import statistics
import time
import uuid

from issue_to_patch.agent import run
from issue_to_patch.protocol import ProviderReply, parse_action
from issue_to_patch.providers import ScriptedProvider
from issue_to_patch.runner import JavaRunner
from issue_to_patch.workspace import AuthorityError, SOURCE, Trust, Workspace, atomic_json, sha256
from .evaluator import evaluate

DEVELOPMENT = ("V01", "P01", "T01")


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def semantic_context(observation):
    """Clock telemetry differs by run; authored inputs and budget limits match."""
    keys = ("protocol_version", "case", "state", "issue", "contract", "visible_files", "source_sha256")
    context = {key: observation[key] for key in keys}
    context["remaining"] = {key: value for key, value in observation["remaining"].items() if key != "wall_seconds"}
    context["wall_seconds_limit"] = 120
    return context


class PairedProvider:
    """Both modes delegate to the same accepted development script."""
    def __init__(self, case_id, mode, repo):
        if case_id not in DEVELOPMENT or mode not in {"one_candidate", "feedback_loop"}:
            raise ValueError("only the three development tasks and two fixed modes are supported")
        self.script = ScriptedProvider(case_id=case_id, repo=repo)
        self.mode, self.edits = mode, 0
        self.actions = []
        self.context_sha256 = self.first_candidate_sha256 = self.prefix_sha256 = None
        self.prefix_action_count = None
        self.request_count = 0

    def decide(self, observation):
        if self.context_sha256 is None:
            self.context_sha256 = canonical_sha(semantic_context(observation))
        reply = self.script.decide(observation)
        action = parse_action(reply.action_json)
        if self.mode == "one_candidate" and action.tool == "replace_text" and self.edits:
            # Close the acting channel honestly. The host can evaluate this frozen
            # failed candidate separately, without fabricating a passing finish.
            action = parse_action(json.dumps({"id": "one-candidate-stop", "tool": "abstain",
                "args": {"reason": "The first candidate failed its public check; this ablation permits one candidate."}}))
        if action.tool == "replace_text":
            self.edits += 1
        entry = {"id": action.id, "tool": action.tool, "args": action.args}
        self.actions.append(entry)
        if action.tool == "run_check" and self.edits == 1 and self.prefix_sha256 is None:
            self.first_candidate_sha256 = observation["source_sha256"]
            self.prefix_sha256 = canonical_sha(self.actions)
            self.prefix_action_count = len(self.actions)
        return ProviderReply(json.dumps(entry), dict(reply.metadata, comparison_mode=self.mode), reply.usage)


def regressions(original, final):
    if original.get("status") not in {"accepted", "rejected"} or final.get("status") not in {"accepted", "rejected"}:
        return {"status": "not_comparable", "count": None, "denominator": None, "ids": None}
    before = {item["id"]: item["passed"] for item in original["assertions"]}
    after = {item["id"]: item["passed"] for item in final["assertions"]}
    if set(before) != set(after):
        raise ValueError("regression comparison requires identical assertion IDs")
    passing = {key for key, value in before.items() if value}
    failed = sorted(key for key in passing if not after[key])
    return {"status": "compared", "count": len(failed), "denominator": len(passing), "ids": failed}


def _mode(repo, case_id, mode, original, runner_factory):
    started = time.monotonic()
    captured = {}
    def factory(root, trust):
        runner = runner_factory(root, trust)
        observe = runner.observe
        def capture(ws, independent=False):
            captured["workspace"] = ws
            return observe(ws, independent=independent)
        runner.observe = capture
        captured["runner"] = runner
        return runner
    provider = PairedProvider(case_id, mode, repo)
    report, output = run(repo, provider, case_id=case_id, runner_factory=factory)
    # The actor report remains unchanged on disk and in this snapshot.
    actor_report = json.loads(json.dumps(report))
    final = actor_report["independent"]
    host_commands = []
    if (mode == "one_candidate" and report["status"] == "ABSTAINED" and report["patch_attempts"] == 1
            and report["public_check"]["status"] == "semantic_failure"):
        ws, runner = captured["workspace"], captured["runner"]
        if not ws.frozen:
            raise AuthorityError("baseline evaluation requires terminated, frozen candidate")
        count = len(runner.commands)
        final = evaluate(ws, runner)
        host_commands = runner.commands[count:]
        atomic_json(output / "baseline-evaluation.json", {"actor_status": report["status"],
                    "independent": final, "commands": host_commands, "acting_channel_closed": True})
    metrics = {"workflow_status": actor_report["status"], "domain_status": final["status"],
               "regressions": regressions(original, final), "patch_attempts": actor_report["patch_attempts"],
               "changed_lines": actor_report["changed_lines"], "changed_files": 1 if actor_report["patch_attempts"] else 0,
               "decisions": actor_report["decisions"], "public_checks": actor_report["public_checks"],
               "elapsed_seconds": round(time.monotonic() - started, 6),
               "actor_elapsed_seconds": actor_report["elapsed_seconds"],
               "public_pass_private_fail": actor_report["public_check"] is not None and
                   actor_report["public_check"]["status"] == "passed" and final["status"] == "rejected"}
    return {"mode": mode, "directory": output.relative_to(repo).as_posix(), "actor_report": actor_report,
            "independent": final, "host_evaluation_commands": host_commands, "metrics": metrics,
            "initial_context_sha256": provider.context_sha256, "first_candidate_sha256": provider.first_candidate_sha256,
            "shared_action_prefix_sha256": provider.prefix_sha256, "prefix_action_count": provider.prefix_action_count,
            "patch_sha256": sha256(output / "patch.diff")}


def pairs(repo, *, runner_factory=JavaRunner):
    repo = Path(repo).resolve()
    started = time.monotonic()
    results, commands = {}, []
    for case_id in DEVELOPMENT:
        trust = Trust(repo, case_id)
        if trust.case_info["split"] != "development":
            raise AuthorityError("development ablation cannot score held-out cases")
        original_ws = Workspace(repo, repo / "work/runs" / uuid.uuid4().hex, trust)
        original_ws.frozen = True
        original_runner = runner_factory(repo, trust)
        original_runner.deadline = time.monotonic() + 60
        original = evaluate(original_ws, original_runner)
        commands += original_runner.commands
        atomic_json(original_ws.run_dir / "development-original.json", {"case": case_id, "independent": original,
                    "commands": original_runner.commands, "source_sha256": original_ws.digest})
        baseline = _mode(repo, case_id, "one_candidate", original, runner_factory)
        loop = _mode(repo, case_id, "feedback_loop", original, runner_factory)
        fairness = {key: baseline[key] is not None and baseline[key] == loop[key] for key in
                    ("initial_context_sha256", "first_candidate_sha256", "shared_action_prefix_sha256")}
        for mode in (baseline, loop):
            commands += mode["actor_report"]["commands"] + mode["host_evaluation_commands"]
        results[case_id] = {"original": original, "original_directory": original_ws.run_dir.relative_to(repo).as_posix(),
                            "baseline": baseline, "feedback_loop": loop, "fairness": fairness}
    return {"evidence_kind": "scripted_development_ablation", "execution_kind": getattr(original_runner, "execution_kind", "unspecified_double"),
            "task_denominator": len(results), "cases": results,
            "baseline_accepted": sum(item["baseline"]["independent"]["status"] == "accepted" for item in results.values()),
            "loop_accepted": sum(item["feedback_loop"]["independent"]["status"] == "accepted" for item in results.values()),
            "context_exclusions": ["remaining.wall_seconds (clock telemetry)"], "same_budget_limits": True,
            "commands": commands, "elapsed_seconds": round(time.monotonic() - started, 6),
            "model_calls": 0, "live_heldout_solve_rate": None, "held_out_scored": 0,
            "limitations": ["Three authored development cases; no inference-quality comparison",
                            "First candidates and the V01 revision are deliberately scripted",
                            "Failure and infrastructure rows remain in the denominator"]}


def repeats(repo, *, runner_factory=JavaRunner):
    repo = Path(repo).resolve()
    results, commands = [], []
    for index in range(3):
        report, output = run(repo, ScriptedProvider(), case_id="V01", runner_factory=runner_factory)
        results.append({"index": index + 1, "directory": output.relative_to(repo).as_posix(), "report": report})
        commands += report["commands"]
    seconds = [item["report"]["elapsed_seconds"] for item in results]
    return {"evidence_kind": "scripted_runtime_repetitions", "execution_kind": results[0]["report"]["execution_kind"],
            "case": "V01", "repeat_denominator": 3, "accepted": sum(item["report"]["status"] == "ACCEPTED" for item in results),
            "runs": results, "commands": commands,
            "elapsed_seconds": {"min": min(seconds), "median": statistics.median(seconds), "max": max(seconds)},
            "model_calls": 0, "live_heldout_solve_rate": None,
            "limitation": "Timing variation of a scripted Java workflow, not stochastic model variance"}


def run_development(repo, *, runner_factory=JavaRunner):
    repo = Path(repo).resolve()
    output = repo / "work/development" / uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    paired = pairs(repo, runner_factory=runner_factory)
    atomic_json(output / "pairs.json", paired)
    repeated = repeats(repo, runner_factory=runner_factory)
    atomic_json(output / "repeats.json", repeated)
    return paired, repeated, output
