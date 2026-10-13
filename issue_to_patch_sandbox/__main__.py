"""Reviewer CLI for synthetic Sandbox contracts; never inspects credentials."""
import argparse
import json
from pathlib import Path
import sys
import uuid
from issue_to_patch.workspace import no_reparse
from issue_to_patch_upgrade.core import Failure
from . import VERSION, SCHEMA_VERSION, source_version
from .contract import synthetic_config
from .synthetic import contract_journey

REPO = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser=argparse.ArgumentParser(description="U2-A Sandbox contracts; no real guest/Java/model execution.")
    commands=parser.add_subparsers(dest="command",required=True)
    commands.add_parser("doctor")
    demo=commands.add_parser("contract-demo")
    demo.add_argument("--scenario",choices=["success","false-fix","compile-failure","lost-create","lost-create-missing","stop-pending","wrong-image","wrong-runtime","wrong-source","bad-log","false-completion"],default="success")
    commands.add_parser("external-run")
    args=parser.parse_args(argv)
    if args.command=="external-run":
        print(json.dumps({"status":"AUTHORIZATION_DENIED","error":"u2a_external_assignment_image_auth_compute_pending", "credential_presence_checked":False}),file=sys.stderr)
        return 3
    if args.command=="doctor":
        print(json.dumps({"status":"source_ready","version":VERSION,"code_version":source_version(),"schema_version":SCHEMA_VERSION,
                          "mode":"local-double","config_sha256":synthetic_config().fingerprint,"verified_image":None,
                          "external_isolation_verified":False,"credentials":"not_inspected","java":"not_invoked","allocation_inr":0},indent=2))
        return 0
    try:
        result=contract_journey(args.scenario)
        folder=REPO/"work/sandbox-contract/runs"/uuid.uuid4().hex
        no_reparse(folder);folder.mkdir(parents=True,exist_ok=False)
        target=folder/"report.json"
        target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
        print(json.dumps({"status":result["status"],"mode":"local-double","domain_verified":False,
                          "report":target.relative_to(REPO).as_posix(),"actor_closed":result["actor_closed"],
                          "maximum_synthetic_sessions_active":result["maximum_synthetic_sessions_active"]},indent=2))
        return {"CONTRACT_COMPLETE":0,"CONTRACT_REJECTED":2,"TRANSPORT_ERROR":4}.get(result["status"],3)
    except (Failure,OSError):
        print(json.dumps({"status":"INFRA_ERROR","error":"synthetic_contract_report_io"}),file=sys.stderr)
        return 4


if __name__=="__main__":
    raise SystemExit(main())
