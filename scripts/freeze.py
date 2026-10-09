"""Read-only verification of authored inputs and static candidate digests."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from issue_to_patch.workspace import AuthorityError, Trust, sha256


def verify(repo=REPO):
    repo = Path(repo)
    trust = Trust(repo)
    frozen = json.loads((repo / "evaluation/frozen.json").read_text(encoding="utf-8"))
    split = json.loads((repo / "evaluation/split.json").read_text(encoding="utf-8"))
    development = {"V01", "P01", "T01"}
    held_out = {"V02", "V03", "P02", "P03", "T02", "T03"}
    if (set(split["development"]) != development or set(split["held_out"]) != held_out
            or len(split["development"]) != 3 or len(split["held_out"]) != 6
            or set(trust.data["cases"]) != development | held_out):
        raise AuthorityError("frozen case split changed")
    immutable = {key: value for key, value in trust.fingerprints.items() if key != "evaluation/frozen.json"}
    if frozen["files"] != immutable or frozen["dataset_version"] != split["dataset_version"]:
        raise AuthorityError("freeze and trust digests disagree")
    result = {}
    for case_id in sorted(development | held_out):
        case = Trust(repo, case_id)
        info = case.case_info
        family = {"V": "validation", "P": "pagination", "T": "transaction"}[case_id[0]]
        case_split = "development" if case_id in development else "held-out"
        candidates = json.loads((repo / info["candidate_sources"]).read_text(encoding="utf-8"))
        hashes = {role.replace("-", "_"): hashlib.sha256(source.encode("utf-8")).hexdigest()
                  for role, source in candidates.items()}
        required = {"original", "repair", "false_fix"} | ({"intermediate"} if case_id == "V01" else set())
        if (set(hashes) != required or hashes != case.candidates or len(set(hashes.values())) != len(hashes)
                or hashes["original"] != sha256(repo / "fixtures" / case_id / info["source"])
                or info["family"] != family or info["split"] != case_split):
            raise AuthorityError("candidate or case manifest mismatch")
        counts = {}
        for scope in ("public", "independent"):
            expected = json.loads((repo / info[scope + "_expected"]).read_text(encoding="utf-8"))
            inputs = json.loads((repo / info[scope + "_inputs"]).read_text(encoding="utf-8"))
            ids = [f"quantity_{item['quantity']}" if info.get("legacy_observations") else item["id"] for item in inputs]
            if len(ids) != len(set(ids)) or set(ids) != {key.split(".")[0] for key in expected}:
                raise AuthorityError("oracle/input scenario mismatch")
            if any(type(value) not in {bool, int, list} or
                   (type(value) is list and any(type(item) is not int for item in value)) for value in expected.values()):
                raise AuthorityError("invalid frozen oracle type")
            counts[scope + "_assertions"] = len(expected)
            counts[scope + "_scenarios"] = len(ids)
        receipt = {"family": family, "split": case_split, "candidates": hashes, **counts}
        if frozen["cases"].get(case_id) != receipt:
            raise AuthorityError("frozen case receipt mismatch")
        result[case_id] = receipt
    if {path.stem for path in (repo / "demos").glob("*.json")} != {"P01", "T01"}:
        raise AuthorityError("unexpected scripted case transcript")
    return {"status": "verified", "case_count": len(result), "development_count": 3, "held_out_count": 6,
            "immutable_files": len(trust.fingerprints), "freeze_sha256": sha256(repo / "evaluation/frozen.json"),
            "trust_sha256": trust.manifest_hash, "cases": result, "java_processes": 0, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", required=True)
    parser.parse_args()
    try:
        print(json.dumps(verify(), indent=2, sort_keys=True))
        return 0
    except (AuthorityError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "freeze_invalid", "error": str(exc).replace(str(REPO), "<repo>")}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
