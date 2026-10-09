"""Milestone acceptance; all Java calls are sequential and authored."""
import argparse
import json
import io
from pathlib import Path
import sys
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evaluation.evaluator import evaluate
from issue_to_patch.agent import run
from issue_to_patch.providers import ScriptedProvider
from issue_to_patch.runner import JavaRunner, public_verdict
from issue_to_patch.workspace import SOURCE, Trust, Workspace, atomic_json, sha256
from scripts.freeze import verify
from scripts.release_check import verify_release
from evaluation.development import run_development
import uuid


def milestone_one():
    started = time.monotonic()
    checks, reports, runners = [], {}, []

    def check(name, condition):
        if not condition:
            raise RuntimeError("acceptance failed: " + name)
        checks.append(name)

    trust = Trust(REPO)
    baseline = Workspace(REPO, REPO / "work/runs" / uuid.uuid4().hex, trust)
    baseline.frozen = True
    baseline_runner = JavaRunner(REPO, trust)
    original = evaluate(baseline, baseline_runner)
    runners += baseline_runner.commands
    check("original_fails_zero_quantity_semantics", original["status"] == "rejected" and "quantity_0.accepted" in original["failures"])

    for scenario in ("repair", "false-fix", "novel"):
        report, output = run(REPO, ScriptedProvider(scenario))
        reports[scenario] = {"report": report, "directory": output.relative_to(REPO).as_posix()}
        runners += report["commands"]
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        check(scenario + "_source_and_probe_digests_agree",
              report["candidate_source_sha256"] == sha256(output / "workspace" / SOURCE)
              == manifest["candidate_source_sha256"] and report["immutable_sha256"] == trust.fingerprints
              == manifest["immutable_sha256"] and report["trust_manifest_sha256"] == sha256(REPO / "evaluation/trusted.json"))
        trace = (output / "trace.jsonl").read_text(encoding="utf-8")
        check(scenario + "_private_verifier_absent_from_agent_trace",
              all(value not in trace for value in ("IndependentProbe", "evaluation/", "quantity_100.")))

    repair = reports["repair"]["report"]
    check("authored_repair_passes_21_independent_assertions",
          repair["status"] == "ACCEPTED" and repair["exit_code"] == 0
          and repair["independent"]["passed_assertions"] == repair["independent"]["assertion_count"] == 21)
    repair_trace = [json.loads(line) for line in (REPO / reports["repair"]["directory"] / "trace.jsonl").read_text().splitlines()]
    check("repair_uses_actual_failed_public_feedback_before_revision",
          repair["patch_attempts"] == 2 and sum(entry["result"]["status"] == "semantic_failure" for entry in repair_trace) == 2)
    false_fix = reports["false-fix"]["report"]
    check("public_passing_false_fix_rejected_independently",
          false_fix["public_check"]["status"] == "passed" and false_fix["status"] == "REJECTED"
          and false_fix["exit_code"] == 2 and "quantity_100.accepted" in false_fix["independent"]["failures"])
    novel = reports["novel"]["report"]
    check("novel_code_never_compiled_or_run",
          novel["status"] == "REVIEW_REQUIRED" and novel["exit_code"] == 3
          and novel["post_edit_processes"] == 0 and novel["independent"]["status"] == "not_run")
    missing, missing_dir = run(REPO, ScriptedProvider(), runner_factory=lambda repo, trust: JavaRunner(
        repo, trust, javac=str(repo / "work/missing-javac.exe")))
    check("missing_compiler_is_infrastructure_error", missing["status"] == "INFRA_ERROR" and missing["exit_code"] == 4 and not missing["commands"])
    check("all_decisions_labeled_scripted_and_zero_model_requests",
          all(item["report"]["evidence_kind"] == "scripted_workflow" and item["report"]["model_requests"] == 0
              and item["report"]["live_heldout_solve_rate"] is None for item in reports.values()))
    trust.verify_immutable()
    summary = {"milestone": 1, "checks_passed": len(checks), "checks": checks,
               "original": original, "reports": {key: value["directory"] for key, value in reports.items()},
               "missing_compiler_report": missing_dir.relative_to(REPO).as_posix(),
               "java_processes": len(runners),
               "heavy_process_seconds": round(sum(item["elapsed_seconds"] for item in runners), 6),
               "elapsed_seconds": round(time.monotonic() - started, 6),
               "model_calls": 0, "downloads": 0, "live_heldout_solve_rate": None,
               "unexecuted": ["M2/M3", "live model inference", "hosted CI", "main independent acceptance"]}
    atomic_json(REPO / "work/acceptance-m1.json", summary)
    return summary


def milestone_two():
    started = time.monotonic()
    freeze = verify(REPO)
    freeze_before, trust_before = freeze["freeze_sha256"], freeze["trust_sha256"]
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(REPO / "tests/pure"))
    groups = {}
    def count_groups(item):
        if isinstance(item, unittest.TestSuite):
            for child in item:
                count_groups(child)
        else:
            name = type(item).__name__
            groups[name] = groups.get(name, 0) + 1
    count_groups(suite)
    required_groups = {"DatasetTests", "ObservationTests", "ProtocolTests", "WorkspaceTests", "LoopFailureTests",
                       "EditBudgetTests", "ProviderMockTests", "ProcessOwnershipTests", "RunnerIntegrityTests"}
    if not required_groups.issubset(groups):
        raise RuntimeError("required adversarial unit group missing")
    units = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    (REPO / "work/m2-pure-units.txt").write_text(stream.getvalue(), encoding="utf-8")
    if not units.wasSuccessful() or units.skipped:
        raise RuntimeError("M2 bounded failure groups failed or were skipped; see work/m2-pure-units.txt")
    cases, commands, checks = {}, [], []

    def check(name, condition):
        if not condition:
            raise RuntimeError("acceptance failed: " + name)
        checks.append(name)

    # Host calibration uses authored sources; it is not an acting-agent solve.
    for case_id, receipt in freeze["cases"].items():
        trust = Trust(REPO, case_id)
        sources = json.loads((REPO / trust.case_info["candidate_sources"]).read_text(encoding="utf-8"))
        sources = {role.replace("-", "_"): source for role, source in sources.items()}
        outcomes = {}
        for role in ("original", "repair", "false_fix"):
            ws = Workspace(REPO, REPO / "work/runs" / uuid.uuid4().hex, trust)
            if role != "original":
                ws.path(SOURCE, write=True).write_text(sources[role], encoding="utf-8", newline="\n")
            check(case_id + "." + role + ".static_digest", ws.digest == trust.candidates[role])
            ws.frozen = True
            runner = JavaRunner(REPO, trust)
            runner.deadline = time.monotonic() + 60
            public = public_verdict(runner.observe(ws), trust)
            private = evaluate(ws, runner)
            commands += runner.commands
            check(case_id + "." + role + ".assertion_denominator", private.get("assertion_count") == receipt["independent_assertions"])
            check(case_id + "." + role + ".source_unchanged", ws.digest == trust.candidates[role])
            outcome = {"public": public, "independent": private, "source_sha256": ws.digest,
                       "commands": runner.commands, "directory": ws.run_dir.relative_to(REPO).as_posix(),
                       "evidence_kind": "authored_candidate_calibration", "model_calls": 0}
            atomic_json(ws.run_dir / "calibration.json", outcome)
            outcomes[role] = outcome
        check(case_id + ".original_semantic_reproduction", outcomes["original"]["public"]["status"] == "semantic_failure"
              and outcomes["original"]["independent"]["status"] == "rejected")
        check(case_id + ".reference_all_assertions", outcomes["repair"]["public"]["status"] == "passed"
              and outcomes["repair"]["independent"]["status"] == "accepted"
              and outcomes["repair"]["independent"]["passed_assertions"] == receipt["independent_assertions"])
        check(case_id + ".false_fix_public_pass_independent_rejection", outcomes["false_fix"]["public"]["status"] == "passed"
              and outcomes["false_fix"]["independent"]["status"] == "rejected"
              and bool(outcomes["false_fix"]["independent"]["failures"]))
        cases[case_id] = {"family": receipt["family"], "split": receipt["split"],
                          "independent_assertions": receipt["independent_assertions"], "outcomes": outcomes}
    # M1 regression retains the novel, false-fix, feedback and missing compiler checks.
    m1 = milestone_one()
    check("M1_regression", m1["checks_passed"] == 13)
    demonstrations = {}
    for case_id in ("P01", "T01"):
        report, output = run(REPO, ScriptedProvider(case_id=case_id), case_id=case_id)
        commands += report["commands"]
        check(case_id + ".development_script", report["status"] == "ACCEPTED"
              and report["evidence_kind"] == "scripted_workflow" and report["model_requests"] == 0
              and report["independent"]["assertion_count"] == freeze["cases"][case_id]["independent_assertions"])
        trace = (output / "trace.jsonl").read_text(encoding="utf-8")
        check(case_id + ".private_oracle_not_in_trace", all(value not in trace for value in ("evaluation/", "IndependentProbe", "independent_expected")))
        demonstrations[case_id] = output.relative_to(REPO).as_posix()
    after = verify(REPO)
    check("frozen_hashes_unchanged", after["freeze_sha256"] == freeze_before and after["trust_sha256"] == trust_before)
    families = {}
    for family in ("validation", "pagination", "transaction"):
        items = {key: value for key, value in cases.items() if value["family"] == family}
        held_out = {key: value for key, value in items.items() if value["split"] == "held-out"}
        families[family] = {"task_denominator": len(items), "held_out_denominator": len(held_out),
                            "originals_reproduced": sum(item["outcomes"]["original"]["public"]["status"] == "semantic_failure" for item in items.values()),
                            "references_accepted": sum(item["outcomes"]["repair"]["independent"]["status"] == "accepted" for item in items.values()),
                            "false_fixes_rejected": sum(item["outcomes"]["false_fix"]["independent"]["status"] == "rejected" for item in items.values()),
                            "held_out_cases": list(held_out),
                            "reference_assertions_passed": sum(item["outcomes"]["repair"]["independent"]["passed_assertions"] for item in items.values()),
                            "reference_assertion_denominator": sum(item["independent_assertions"] for item in items.values())}
    summary = {"milestone": 2, "evidence_kind": "authored_candidate_calibration_and_development_scripts",
               "checks_passed": len(checks), "checks": checks, "pure_python_units": units.testsRun,
               "pure_python_units_passed": True, "pure_python_groups": groups, "development_tasks": 3, "held_out_tasks": 6,
               "task_denominator": len(cases), "families": families, "cases": cases,
               "development_demonstrations": demonstrations, "M1_regression": m1,
               "frozen_sha256": freeze_before, "trust_sha256": trust_before,
               "java_processes": len(commands) + m1["java_processes"],
               "heavy_process_seconds": round(sum(item["elapsed_seconds"] for item in commands) + m1["heavy_process_seconds"], 6),
               "elapsed_seconds": round(time.monotonic() - started, 6), "model_calls": 0, "downloads": 0,
               "live_heldout_solve_rate": None, "live_tasks_attempted": 0,
               "unexecuted": ["live model inference", "M3 baseline/CI", "real hostile code containment",
                              "actual Windows junction creation (attribute doubles only)", "main independent M2 acceptance"]}
    atomic_json(REPO / "work/acceptance-m2.json", summary)
    return summary


def milestone_three():
    started = time.monotonic()
    before = verify_release(REPO)
    paired, repeated, output = run_development(REPO)
    checks = []
    def check(name, condition):
        if not condition:
            raise RuntimeError("acceptance failed: " + name + "; retained development reports: " + output.relative_to(REPO).as_posix())
        checks.append(name)
    check("three_development_pairs_only", paired["task_denominator"] == 3 and set(paired["cases"]) == {"V01", "P01", "T01"}
          and paired["held_out_scored"] == 0)
    for case_id, item in paired["cases"].items():
        check(case_id + ".same_context_first_candidate_and_actions", all(item["fairness"].values())
              and item["baseline"]["prefix_action_count"] == item["feedback_loop"]["prefix_action_count"] == 6)
        check(case_id + ".same_original_source", item["baseline"]["actor_report"]["original_source_sha256"]
              == item["feedback_loop"]["actor_report"]["original_source_sha256"])
        check(case_id + ".baseline_one_candidate", item["baseline"]["metrics"]["patch_attempts"] == 1)
        check(case_id + ".loop_accepted_no_regressions", item["feedback_loop"]["independent"]["status"] == "accepted"
              and item["feedback_loop"]["metrics"]["regressions"]["status"] == "compared"
              and item["feedback_loop"]["metrics"]["regressions"]["count"] == 0)
        for mode in ("baseline", "feedback_loop"):
            trace = (REPO / item[mode]["directory"] / "trace.jsonl").read_text(encoding="utf-8")
            check(case_id + "." + mode + ".protected_oracle_absent", all(value not in trace for value in ("evaluation/", "IndependentProbe", "quantity_100.")))
    v01 = paired["cases"]["V01"]
    check("V01_baseline_honest_termination_and_private_rejection", v01["baseline"]["metrics"]["workflow_status"] == "ABSTAINED"
          and v01["baseline"]["independent"]["status"] == "rejected" and len(v01["baseline"]["host_evaluation_commands"]) == 2)
    check("V01_actual_failed_feedback_before_revision", v01["baseline"]["actor_report"]["public_check"]["status"] == "semantic_failure"
          and v01["feedback_loop"]["metrics"]["patch_attempts"] == 2)
    check("development_ablation_expected_authored_outcomes", paired["baseline_accepted"] == 2 and paired["loop_accepted"] == 3)
    check("three_V01_repetitions_pass", repeated["repeat_denominator"] == repeated["accepted"] == 3)
    hashes = {item["report"]["candidate_source_sha256"] for item in repeated["runs"]}
    check("repetitions_identical_candidate_and_assertions", len(hashes) == 1 and
          all(item["report"]["independent"]["assertion_count"] == item["report"]["independent"]["passed_assertions"] == 21 for item in repeated["runs"]))
    check("authored_evidence_and_no_live_model_claims", paired["evidence_kind"] == "scripted_development_ablation"
          and repeated["evidence_kind"] == "scripted_runtime_repetitions" and paired["execution_kind"] == repeated["execution_kind"] == "java_subprocess"
          and paired["model_calls"] == repeated["model_calls"] == 0
          and paired["live_heldout_solve_rate"] is repeated["live_heldout_solve_rate"] is None)
    after = verify_release(REPO)
    check("release_source_and_accepted_freeze_unchanged", before["source_sha256"] == after["source_sha256"]
          and before["freeze_sha256"] == after["freeze_sha256"] and before["trust_sha256"] == after["trust_sha256"])
    commands = paired["commands"] + repeated["commands"]
    summary = {"milestone": 3, "checks_passed": len(checks), "checks": checks,
        "development_directory": output.relative_to(REPO).as_posix(), "paired_task_denominator": 3,
        "baseline_accepted": paired["baseline_accepted"], "loop_accepted": paired["loop_accepted"],
        "V01_repeat_denominator": 3, "V01_repeats_accepted": repeated["accepted"], "V01_runtime_seconds": repeated["elapsed_seconds"],
        "java_processes": len(commands), "heavy_process_seconds": round(sum(item["elapsed_seconds"] for item in commands), 6),
        "elapsed_seconds": round(time.monotonic() - started, 6), "release_source_sha256": after["source_sha256"],
        "freeze_sha256": after["freeze_sha256"], "trust_sha256": after["trust_sha256"],
        "evidence_kind": "scripted_development_ablation_and_repetitions", "model_calls": 0, "downloads": 0,
        "live_heldout_solve_rate": None, "unexecuted": ["hosted Linux/Windows CI", "live model inference",
          "hostile code containment", "actual Windows junction creation", "main independent M3 acceptance"]}
    atomic_json(REPO / "work/acceptance-m3.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--milestone", choices=["1", "2", "3", "all"], required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("Select Python 3.11 explicitly.")
    if args.milestone == "all":
        m2, m3 = milestone_two(), milestone_three()
        if not {"PairedSourceTests", "ProviderBoundarySourceTests", "CiSourceTests"}.issubset(m2["pure_python_groups"]):
            raise RuntimeError("M3 isolated pairing/provider/CI unit group missing")
        summary = {"milestone": "all", "M2_checks_passed": m2["checks_passed"], "M3_checks_passed": m3["checks_passed"],
                   "full_outcome_calibration": "9 originals / 9 references / 9 false fixes", "pure_units": m2["pure_python_units"],
                   "baseline_accepted": m3["baseline_accepted"], "loop_accepted": m3["loop_accepted"],
                   "paired_denominator": m3["paired_task_denominator"], "V01_repeats_accepted": m3["V01_repeats_accepted"],
                   "V01_runtime_seconds": m3["V01_runtime_seconds"], "java_processes": m2["java_processes"] + m3["java_processes"],
                   "heavy_process_seconds": round(m2["heavy_process_seconds"] + m3["heavy_process_seconds"], 6),
                   "elapsed_seconds": round(m2["elapsed_seconds"] + m3["elapsed_seconds"], 6),
                   "freeze_sha256": m3["freeze_sha256"], "trust_sha256": m3["trust_sha256"],
                   "release_source_sha256": m3["release_source_sha256"], "development_directory": m3["development_directory"],
                   "model_calls": 0, "downloads": 0, "live_heldout_solve_rate": None, "unexecuted": m3["unexecuted"]}
        atomic_json(REPO / "work/acceptance-all.json", summary)
    else:
        summary = {"1": milestone_one, "2": milestone_two, "3": milestone_three}[args.milestone]()
    printable = {key: value for key, value in summary.items() if key not in {"cases", "M1_regression", "checks"}}
    print(json.dumps(printable, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
