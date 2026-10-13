"""LEASE REQUIRED: ordered U1 loopback/owned-process suite plus inert journey checks."""
import argparse
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))

from issue_to_patch_upgrade.cli import source_version
from issue_to_patch_upgrade.core import Config
from issue_to_patch_upgrade.doubles import InertGateway
from issue_to_patch_upgrade.gateway import GatewayProvider
from issue_to_patch_upgrade.loop import run
from issue_to_patch_upgrade.sandbox_double import InertSandbox


def main():
    parser=argparse.ArgumentParser(description="U1 local-only acceptance; operator must hold named heavy lease.")
    parser.add_argument("--milestone",choices=["U1"],required=True)
    parser.add_argument("--mode",choices=["local-double"],required=True)
    parser.parse_args()
    suite=unittest.defaultTestLoader.discover(str(REPO/"tests/upgrade_transport"))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    config=Config("test/synthetic-coder","test")
    rows=[]
    expected={"repair":"CONTRACT_COMPLETE","false-fix":"CONTRACT_REJECTED","early-finish":"POLICY_DENIED",
              "http-401":"AUTHORIZATION_DENIED","http-402":"FUNDS_DENIED","http-429":"RATE_LIMITED",
              "http-503":"PROVIDER_ERROR","unknown-tool":"PROTOCOL_ERROR","ambiguous-loss":"TRANSPORT_ERROR"}
    for scenario,status in expected.items():
        report=run(GatewayProvider(config,InertGateway(scenario)),InertSandbox(),config,code_version=source_version())
        checks={"expected_status":report["status"]==status,"actor_closed":report["actor_closed"],
                "no_generated_host_process":report["generated_code_host_processes"]==0,
                "no_real_provider":report["real_provider_requests"]==0,"no_real_vm":report["real_sandbox_sessions"]==0,
                "no_domain_verified":report["independent"]["domain_verified"] is False}
        if scenario=="repair":
            checks.update(two_edits=report["edits"]==2,three_public_checks=report["public_checks"]==3,
                          simulated_assertions=report["independent"]["simulated_passed"]==6)
        if scenario=="false-fix":
            checks.update(public_pass=any(e.get("result",{}).get("status")=="passed" for e in report["events"]),
                          private_simulation_rejected=report["independent"]["simulated_passed"]==5)
        rows.append({"scenario":scenario,"checks":checks,"report":report})
    receipt={"milestone":"U1","mode":"local-double","owned_transport_units":result.testsRun,
             "checks":sum(len(r["checks"]) for r in rows),"passed":all(all(r["checks"].values()) for r in rows),
             "rows":rows,"live_model_calls":0,"real_sandbox_sessions":0,"generated_code_host_processes":0}
    target=REPO/"work/upgrade/acceptance-u1.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({k:v for k,v in receipt.items() if k!="rows"},indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

