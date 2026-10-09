import argparse
import json
from pathlib import Path
import shutil
import sys

from .agent import run
from .providers import OllamaProvider, ScriptedProvider
from .workspace import AuthorityError, Trust, no_reparse


def repository():
    return Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Authored Java issue-to-patch demonstration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    report_parser = commands.add_parser("report")
    report_parser.add_argument("--latest", action="store_true", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--case", choices=["V01", "P01", "T01"], default="V01")
    demo.add_argument("--scenario", choices=["repair", "false-fix", "novel"], default="repair")
    live = commands.add_parser("run")
    live.add_argument("--case", choices=["V01", "P01", "T01"], default="V01")
    live.add_argument("--provider", choices=["ollama"], required=True)
    live.add_argument("--model", required=True)
    live.add_argument("--endpoint", default="http://127.0.0.1:11434")
    live.add_argument("--allow-local-model", action="store_true")
    args = parser.parse_args(argv)
    repo = repository()
    try:
        if args.command == "doctor":
            trust = Trust(repo)
            valid = sys.version_info[:2] == (3, 11) and bool(shutil.which("java")) and bool(shutil.which("javac"))
            print(json.dumps({"python": sys.version.split()[0], "java_available": bool(shutil.which("java")),
                              "javac_available": bool(shutil.which("javac")), "fixture_digests_valid": True,
                              "frozen_cases": len(trust.data["cases"]),
                              "trust_manifest_sha256": trust.manifest_hash, "builds_executed": 0}, indent=2))
            return 0 if valid else 4
        if args.command == "report":
            reports = list((repo / "work/runs").glob("*/report.json"))
            if not reports:
                raise ValueError("no completed report")
            latest = max(reports, key=lambda path: path.stat().st_mtime_ns)
            no_reparse(latest)
            print(latest.read_text(encoding="utf-8"))
            return 0
        provider = ScriptedProvider(args.scenario, case_id=args.case, repo=repo) if args.command == "demo" else OllamaProvider(
            args.model, args.endpoint, allow_local_model=args.allow_local_model)
        result, output = run(repo, provider, case_id=args.case)
        print(json.dumps({"status": result["status"], "exit_code": result["exit_code"],
                          "report": (output / "report.json").relative_to(repo).as_posix(),
                          "diff": (output / "patch.diff").relative_to(repo).as_posix(),
                          "independent": result["independent"]["status"]}, indent=2))
        return result["exit_code"]
    except (ValueError, OSError, AuthorityError) as exc:
        print(json.dumps({"status": "INFRA_ERROR", "error": str(exc).replace(str(repo), "<repo>")}), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
