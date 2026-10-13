"""Offline reviewer CLI; real Gateway/Sandbox execution remains explicitly unavailable in U1."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from issue_to_patch.workspace import no_reparse
from . import DATASET_VERSION, PROMPT_VERSION, VERSION
from .core import Config, Failure, digest, encoded, parse_json
from .doubles import InertGateway
from .fixture import DATASET_HASH
from .gateway import GatewayProvider, SYSTEM_PROMPT
from .loop import run
from .sandbox_double import InertSandbox

REPO = Path(__file__).resolve().parents[1]
EXITS = {"CONTRACT_COMPLETE": 0, "CONTRACT_REJECTED": 2, "CANCELLED": 130,
         "TRANSPORT_ERROR": 4, "TRANSPORT_TIMEOUT": 4, "PROVIDER_ERROR": 4}


def source_version():
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(Path(__file__).parent.glob("*.py"))}
    return digest(files)


def save(report):
    folder = REPO / "work/upgrade/runs" / report["run_id"]
    no_reparse(folder)
    folder.mkdir(parents=True, exist_ok=False)
    for name, data in (("report.json", json.dumps(report, indent=2, sort_keys=True) + "\n"),
                       ("events.jsonl", "".join(encoded(e).decode() + "\n" for e in report["events"])),
                       ("proposal.diff", report["diff"]), ("proposal.java", report["candidate_text"])):
        (folder / name).write_text(data, encoding="utf-8", newline="\n")
    return folder.relative_to(REPO).as_posix()


def load_report(run_id):
    root = REPO / "work/upgrade/runs"
    no_reparse(root)
    if run_id == "latest":
        folders = sorted((p for p in root.glob("*") if re.fullmatch(r"[a-f0-9]{32}", p.name)),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if not folders:
            raise Failure("CONFIG_ERROR", "no_saved_upgrade_report")
        run_id = folders[0].name
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise Failure("CONFIG_ERROR", "invalid_run_id")
    path = root / run_id / "report.json"
    no_reparse(path)
    if path.stat().st_size > 4194304:
        raise Failure("CONFIG_ERROR", "saved_report_limit")
    return parse_json(path.read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description="U1 native function-call contracts; inert execution only.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    demo = commands.add_parser("offline-demo")
    demo.add_argument("--case", choices=["D01"], default="D01")
    demo.add_argument("--scenario", choices=["repair", "false-fix", "early-finish", "unknown-tool", "http-401",
                                             "http-402", "http-429", "http-503", "malformed", "ambiguous-loss"], default="repair")
    report = commands.add_parser("report")
    report.add_argument("--run", default="latest")
    resume = commands.add_parser("resume")
    resume.add_argument("--run", required=True)
    gateway = commands.add_parser("run")
    gateway.add_argument("--provider", choices=["gateway"], required=True)
    gateway.add_argument("--model", required=True)
    gateway.add_argument("--serving-provider", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = {"status": "source_ready", "package_version": VERSION, "python": sys.version.split()[0],
                      "code_version": source_version(), "prompt_version": PROMPT_VERSION,
                      "prompt_sha256": digest(SYSTEM_PROMPT), "dataset_version": DATASET_VERSION,
                      "dataset_sha256": DATASET_HASH, "java": "not_invoked", "credentials": "not_inspected",
                      "application_dependencies": [], "real_gateway": "gated", "real_sandbox": "not_implemented_U1",
                      "commons_lang": "U2_candidate_not_downloaded", "live_allocation_inr": 0,
                      "generated_code_host_processes": 0, "network_requests": 0}
        elif args.command == "run":
            Config(args.model, args.serving_provider, mode="live")
            raise Failure("AUTHORIZATION_DENIED", "u1_has_no_real_execution_path")
        elif args.command == "offline-demo":
            config = Config("test/synthetic-coder", "test")
            provider = GatewayProvider(config, InertGateway(args.scenario))
            result = run(provider, InertSandbox(), config, code_version=source_version())
            path = save(result)
            print(json.dumps({"status": result["status"], "error": result["error"], "mode": result["mode"],
                              "task": "D01-contract", "domain_verified": False, "report_directory": path,
                              "candidate_sha256": result["candidate_sha256"], "actions": [
                                  {"tool": e["tool"], "result": e["result"]["status"]} for e in result["events"]
                                  if e["kind"] == "tool_observed"], "evidence": result["evidence"]}, indent=2))
            return EXITS.get(result["status"], 3)
        else:
            result = load_report(args.run)
            if args.command == "resume":
                result = {"status": "RESUME_DENIED", "error": "u1_resume_not_supported",
                          "run_id": result["run_id"], "preserved_budget": result["budget"],
                          "no_counter_reset": True, "network_requests": 0}
                print(json.dumps(result, indent=2))
                return 3
        print(json.dumps(result, indent=2))
        return 0
    except Failure as failure:
        print(json.dumps({"status": failure.status, "error": failure.code, "mode": "offline",
                          "real_provider_requests": 0, "generated_code_host_processes": 0}), file=sys.stderr)
        return EXITS.get(failure.status, 3)
    except OSError:
        print(json.dumps({"status": "INFRA_ERROR", "error": "local_report_io"}), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())

