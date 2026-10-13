"""Independent proposal and simulated-state checks after actor closure; no Java."""
from .core import digest
from .fixture import SOURCE
from .sandbox_double import InertSandbox


def verify(candidate, *, actor_closed):
    # These inputs/expectations are never provided by acting tools or provider prompts.
    inputs = (-1, 0, 1, 2, 100, 101)
    expected = (False, False, True, True, True, False)
    proposal_checks = {
        "actor_closed": actor_closed is True,
        "candidate_hash_matches": digest(candidate.source) == candidate.source_sha256,
        "original_hash_matches": candidate.original_sha256 == digest(SOURCE),
        "bounded_nonempty_edit": 1 <= candidate.edits <= 3 and 0 < candidate.changed_lines <= 200,
        "current_public_success": bool(candidate.public_result and candidate.public_result.get("status") == "passed"
                                       and candidate.public_result.get("source_sha256") == candidate.source_sha256
                                       and candidate.public_result.get("execution") == "none"
                                       and candidate.public_result.get("mode") == "local-double"),
    }
    result = {"status": "proposal_invalid", "proposal_checks": proposal_checks,
              "evidence_mode": "local-double", "domain_verified": False,
              "actual_code_executions": 0, "real_sandbox_sessions": 0,
              "simulated_passed": 0, "simulated_total": len(inputs), "raw_simulated_records": []}
    if not all(proposal_checks.values()):
        return result
    from .core import Failure
    try:
        sandbox = InertSandbox()
        observations = sandbox.observe(candidate.source, inputs)
        public = sandbox.public(candidate.source)
        if candidate.public_result.get("records") != public["records"]:
            return result
    except Failure:
        return result
    records = observations["records"]
    if len(records) != len(inputs):
        return result
    passed = sum(type(r.get("accepted")) is bool and r.get("quantity") == q and r["accepted"] == e
                 for r, q, e in zip(records, inputs, expected))
    original = sandbox.observe(SOURCE, inputs)["records"]
    previously_passing = [i for i, (r, e) in enumerate(zip(original, expected)) if r["accepted"] == e]
    regressions = sum(records[i]["accepted"] != expected[i] for i in previously_passing)
    result.update(status="simulated_contract_pass" if passed == len(inputs) else "simulated_contract_rejected",
                  simulated_passed=passed, raw_simulated_records=records,
                  originally_passing_simulated_assertions=len(previously_passing), simulated_regressions=regressions)
    return result

