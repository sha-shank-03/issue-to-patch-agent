"""Lightweight portable-source checks; no build, network, Git or inference."""
import hashlib
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.freeze import verify
from issue_to_patch.workspace import no_reparse

APPROVED_FREEZE = "14e1c6d5f476550fa308e91433e24718e9e0a53801441dc25675cfb658eea34c"
APPROVED_TRUST = "70fed424125df3b9bb02b33ede90fadb056358d5d56949ebb1cac241807fc86e"
OMIT = {".git", "work", ".venv", "__pycache__", ".pytest_cache", "node_modules", "target", "build"}


def release_files(repo):
    repo = Path(repo)
    for path in repo.rglob("*"):
        relative = path.relative_to(repo)
        if any(part in OMIT for part in relative.parts) or relative.as_posix() == "AGENTS.md":
            continue
        no_reparse(path)
        if path.is_file():
            yield path


def verify_ci(text, pins):
    found = dict(re.findall(r"uses:\s+(actions/[a-z-]+)@([a-f0-9]{40})", text))
    expected = {name: item["sha"] for name, item in pins["actions"].items()}
    if found != expected or len(re.findall(r"\buses:", text)) != 3:
        raise ValueError("CI must use exactly the three pinned official actions")
    required = ("  push:", "  pull_request:", "  workflow_dispatch:", "contents: read",
                "persist-credentials: false", "max-parallel: 1", "timeout-minutes: 15",
                "os: [ubuntu-latest, windows-latest]", "python-version: '3.11'", "java-version: '17'",
                "distribution: microsoft", "python -m issue_to_patch doctor", "python scripts/release_check.py",
                "python -m unittest discover -s tests/unit -v", "python scripts/acceptance.py --milestone all")
    if any(item not in text for item in required):
        raise ValueError("CI runtime, permissions, platforms or acceptance commands changed")
    if re.search(r"(?i)secrets\.|pull_request_target|cache:|upload-artifact|allow-unsafe|pip install|curl |wget |ollama", text):
        raise ValueError("CI contains excluded credentials, downloads, cache or live provider configuration")


def verify_release(repo=REPO):
    repo = Path(repo)
    frozen = verify(repo)
    if frozen["freeze_sha256"] != APPROVED_FREEZE or frozen["trust_sha256"] != APPROVED_TRUST:
        raise ValueError("accepted M2 frozen inputs/runtime changed")
    if (repo / ".gitattributes").read_text(encoding="utf-8").strip() != "* text eol=lf":
        raise ValueError("portable checkout must preserve LF bytes")
    license_text = (repo / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text or "Permission is hereby granted" not in license_text:
        raise ValueError("MIT license missing")
    required = ("README.md", "ARCHITECTURE.md", "ATTRIBUTION.md", "EVIDENCE.md", "docs/PROVIDER_TESTS.md",
                "docs/ci-actions.json", "evaluation/development.py", "scripts/development.py",
                "tests/unit/test_provider_details.py", "tests/pure/test_m3_source.py")
    if any(not (repo / name).is_file() for name in required):
        raise ValueError("release handoff document/source missing")
    pins = json.loads((repo / "docs/ci-actions.json").read_text(encoding="utf-8"))
    workflow = (repo / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    verify_ci(workflow, pins)
    fingerprints = {}
    for path in release_files(repo):
        name = path.relative_to(repo).as_posix()
        data = path.read_bytes()
        if name.startswith(".env") or path.suffix in {".exe", ".dll", ".jar", ".class", ".pyc"}:
            raise ValueError("unexpected credential/generated/runtime file in release source")
        text = data.decode("utf-8")
        if b"\r\n" in data:
            raise ValueError("release source has checkout-sensitive CRLF bytes: " + name)
        if re.search(r"(?i)[a-z]:[/\\]Users[/\\]|CodexPortfolios[/\\]|coordination[/\\]workers", text):
            raise ValueError("personal or coordination path in release source")
        if path.suffix == ".py":
            compile(text, name, "exec")
        fingerprints[name] = hashlib.sha256(data).hexdigest()
    return {"status": "source_verified", "frozen_cases": 9, "release_files": len(fingerprints),
            "source_sha256": hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest(),
            "files": fingerprints, "freeze_sha256": APPROVED_FREEZE, "trust_sha256": APPROVED_TRUST,
            "java_processes": 0, "child_processes": 0, "network_requests": 0,
            "hosted_ci": "unexecuted", "live_model_calls": 0}


def main():
    try:
        receipt = verify_release()
        print(json.dumps({key: value for key, value in receipt.items() if key != "files"}, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "release_source_invalid", "error": str(exc).replace(str(REPO), "<repo>")}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
