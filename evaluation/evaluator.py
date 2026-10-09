"""Frozen contract oracles; never sent to the acting provider."""
import json
from issue_to_patch.observations import compare
from issue_to_patch.runner import parse_observations


def evaluate(workspace, runner):
    if not workspace.frozen:
        raise ValueError("independent evaluation requires frozen source")
    observation = runner.observe(workspace, independent=True)
    if observation["status"] != "observed":
        return observation
    trust = runner.trust
    trust.verify_immutable()
    expected = json.loads((trust.repo / trust.case_info["independent_expected"]).read_text(encoding="utf-8"))
    if not trust.case_info.get("legacy_observations"):
        verdict = compare(observation["output"], expected)
        return dict(verdict, status="rejected" if verdict["failures"] else "accepted",
                    source_sha256=observation["source_sha256"])
    quantities = {int(key.split(".")[0].removeprefix("quantity_")) for key in expected}
    rows = parse_observations(observation["output"], quantities)
    assertions = []
    for quantity in sorted(quantities):
        for index, field in enumerate(("accepted", "stock", "orders")):
            key = f"quantity_{quantity}.{field}"
            assertions.append({"id": key, "expected": expected[key],
                               "actual": rows[quantity][index], "passed": type(rows[quantity][index]) is type(expected[key])
                               and rows[quantity][index] == expected[key]})
    failures = [item["id"] for item in assertions if not item["passed"]]
    return {"status": "rejected" if failures else "accepted", "source_sha256": observation["source_sha256"],
            "scenario_count": len(quantities), "assertion_count": len(assertions),
            "passed_assertions": len(assertions) - len(failures), "failures": failures, "assertions": assertions}
