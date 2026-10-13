"""LEASE REQUIRED: one U2-A socket/helper suite and fixed synthetic contract scenarios."""
import json
from pathlib import Path
import sys
import unittest

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from issue_to_patch_sandbox import source_version
from issue_to_patch_sandbox.synthetic import contract_journey


def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(REPO/"tests/sandbox_transport")))
    if not result.wasSuccessful(): return 1
    expected={"success":"CONTRACT_COMPLETE","false-fix":"CONTRACT_REJECTED","compile-failure":"COMMAND_FAILED",
              "lost-create":"TRANSPORT_ERROR","lost-create-missing":"HANDOFF_REQUIRED","stop-pending":"HANDOFF_REQUIRED"}
    rows=[]
    for scenario,status in expected.items():
        report=contract_journey(scenario)
        checks={"expected_status":report["status"]==status,"actor_closed":report["actor_closed"],
                "domain_unverified":report["domain_verified"] is False,"serial_synthetic_sessions":report["maximum_synthetic_sessions_active"]<=1}
        rows.append({"scenario":scenario,"checks":checks,"report":report})
    receipt={"mode":"local-double","version":source_version(),"transport_units":result.testsRun,
             "assertions":sum(len(row["checks"]) for row in rows),"passed":all(all(row["checks"].values()) for row in rows),
             "rows":rows,"actual_java_executions":0,"real_sandbox_sessions":0,"model_calls":0}
    target=REPO/"work/sandbox-contract/acceptance-u2a.json";target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({k:v for k,v in receipt.items() if k!="rows"},indent=2))
    return 0 if receipt["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
