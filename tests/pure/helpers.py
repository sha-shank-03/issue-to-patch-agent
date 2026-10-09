import json
from pathlib import Path
import shutil
import tempfile
import unittest
from issue_to_patch.workspace import AuthorityError, Trust, Workspace

REPO = Path(__file__).resolve().parents[2]


class LocalCase(unittest.TestCase):
    def setUp(self):
        scratch = REPO / "work/pure-unit"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        for name in ("fixtures", "evaluation", "demos", "issue_to_patch"):
            shutil.copytree(REPO / name, self.repo / name, ignore=shutil.ignore_patterns("__pycache__"))

    def tearDown(self):
        self.temp.cleanup()

    def workspace(self, case_id="V01", name="unit"):
        trust = Trust(self.repo, case_id)
        return Workspace(self.repo, self.repo / "work/runs" / name, trust), trust


def typed_output(expected):
    rows = []
    for key, value in expected.items():
        scenario, field = key.split(".", 1)
        if type(value) is bool:
            kind, text = "bool", str(value).lower()
        elif type(value) is int:
            kind, text = "int", str(value)
        else:
            kind, text = "ints", ",".join(str(item) for item in value)
        rows.append("\t".join((scenario, field, kind, text)))
    return "\n".join(rows) + "\n"


class ProtocolRunnerDouble:
    """Fictional outputs test control flow only, never Java/domain correctness."""
    execution_kind = "python_unit_double"

    def __init__(self, repo, trust):
        self.repo, self.trust = Path(repo), trust
        self.commands, self.observations = [], []

    def observe(self, ws, independent=False):
        if not self.trust.permits(ws.path("src/ShopApi.java")):
            raise AuthorityError("novel source is proposal-only")
        ws.verify_public_copy(self.trust)
        self.observations.append((ws.digest, independent))
        role = next(role for role, digest in self.trust.candidates.items() if digest == ws.digest)
        if self.trust.case_id == "V01":
            quantities = [-1, 0, 1, 5, 99, 100, 101] if independent else [-1, 0, 5]
            rows = []
            for q in quantities:
                accepted = 1 <= q <= 100
                if role == "original" and q == 0:
                    accepted = True
                if role == "intermediate" and q == 5 or role == "false_fix" and q == 100:
                    accepted = False
                rows.append(f"{q}\t{str(accepted).lower()}\t{200-q if accepted else 200}\t{1 if accepted else 0}")
            output = "\n".join(rows) + "\n"
        else:
            scope = "independent" if independent else "public"
            expected = json.loads((self.repo / self.trust.case_info[scope + "_expected"]).read_text())
            if role == "original" or (role == "false_fix" and independent):
                key = next(key for key, value in expected.items() if type(value) is bool)
                expected[key] = not expected[key]
            output = typed_output(expected)
        return {"status": "observed", "source_sha256": ws.digest, "output": output}
