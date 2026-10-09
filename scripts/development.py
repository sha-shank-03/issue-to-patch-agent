"""Run only authored development ablations and exactly three V01 repeats."""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from evaluation.development import run_development


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", required=True)
    parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("Select Python 3.11 explicitly.")
    paired, repeated, output = run_development(REPO)
    print(json.dumps({"evidence_kind": paired["evidence_kind"], "paired_tasks": paired["task_denominator"],
          "baseline_accepted": paired["baseline_accepted"], "loop_accepted": paired["loop_accepted"],
          "V01_repeat_denominator": repeated["repeat_denominator"], "V01_repeats_accepted": repeated["accepted"],
          "reports": output.relative_to(REPO).as_posix(), "model_calls": 0,
          "live_heldout_solve_rate": None}, indent=2))
    return 0 if all(all(item["fairness"].values()) for item in paired["cases"].values()) and repeated["accepted"] == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
