"""Small manifest-visible workspace and a static authored-code allowlist."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

SOURCE = "src/ShopApi.java"
VISIBLE = (SOURCE, "public/PublicProbe.java", "issue.md", "contract.md")


class AuthorityError(ValueError):
    pass


class BudgetError(AuthorityError):
    pass


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def no_reparse(path):
    path = Path(path)
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            attrs = item.lstat()
            if stat.S_ISLNK(attrs.st_mode) or getattr(attrs, "st_file_attributes", 0) & 0x400:
                raise AuthorityError("symlink/reparse paths are outside authority")


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


class Trust:
    def __init__(self, repo, case_id="V01"):
        self.repo = Path(repo).resolve()
        self.path = self.repo / "evaluation/trusted.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.manifest_hash = sha256(self.path)
        self.fingerprints = dict(self.data["immutable"])
        self.verify_immutable()
        if case_id not in self.data["cases"]:
            raise AuthorityError("unknown case")
        self.case_id = case_id
        entry = self.data["cases"][case_id]
        self.case_info = json.loads((self.repo / entry["manifest"]).read_text(encoding="utf-8"))
        if self.case_info["id"] != case_id or tuple(self.case_info["visible"]) != VISIBLE:
            raise AuthorityError("invalid fixture authority manifest")
        self.candidates = dict(entry["candidates"])

    def verify_immutable(self):
        if sha256(self.path) != self.manifest_hash:
            raise AuthorityError("trust allowlist changed")
        for relative, expected in self.fingerprints.items():
            no_reparse(self.repo / relative)
            if sha256(self.repo / relative) != expected:
                raise AuthorityError("immutable fixture/probe digest changed")

    def permits(self, source):
        self.verify_immutable()
        no_reparse(source)
        return sha256(source) in self.candidates.values()


class Workspace:
    def __init__(self, repo, run_dir, trust):
        self.repo = Path(repo).resolve()
        self.case_id = trust.case_id
        self.visible = tuple(trust.case_info["visible"])
        self.run_dir = Path(run_dir)
        self.root = self.run_dir / "workspace"
        no_reparse(self.run_dir.parent)
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.root.mkdir()
        for relative in self.visible:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.repo / "fixtures" / self.case_id / relative, target)
        self.original = (self.root / SOURCE).read_text(encoding="utf-8")
        self.original_digest = sha256(self.root / SOURCE)
        if self.original_digest != trust.candidates["original"]:
            raise AuthorityError("original source digest changed")
        self.frozen = False
        self.patch_attempts = 0
        self.changed_lines = 0

    @property
    def digest(self):
        return sha256(self.path(SOURCE))

    def path(self, relative, write=False):
        if relative not in self.visible or (write and relative != SOURCE):
            raise AuthorityError("path not in manifest authority")
        if self.frozen and write:
            raise AuthorityError("candidate is frozen")
        target = self.root / relative
        no_reparse(target)
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise AuthorityError("path escapes workspace")
        return target

    def read(self, relative, start=1, count=200):
        text = self.path(relative).read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > 65536:
            raise AuthorityError("visible file exceeds bound")
        result = "\n".join(text.splitlines()[start - 1:start - 1 + count])
        if len(result.encode("utf-8")) > 16384:
            raise AuthorityError("read exceeds observation bound")
        return result

    def replace(self, path, preimage_sha256, old, new):
        target = self.path(path, write=True)
        if sha256(target) != preimage_sha256:
            raise AuthorityError("stale preimage digest")
        text = target.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AuthorityError("replacement requires exactly one match")
        changed = text.replace(old, new, 1)
        lines = sum(1 for line in difflib.ndiff(text.splitlines(), changed.splitlines()) if line[:2] in {"+ ", "- "})
        if self.patch_attempts >= 3 or self.changed_lines + lines > 200 or len(changed.encode("utf-8")) > 65536:
            raise BudgetError("patch budget exhausted")
        temp = target.with_suffix(".java.tmp")
        temp.write_text(changed, encoding="utf-8", newline="\n")
        os.replace(temp, target)
        self.patch_attempts += 1
        self.changed_lines += lines
        return {"status": "edited", "source_sha256": self.digest}

    def diff(self):
        current = self.path(SOURCE).read_text(encoding="utf-8")
        return "".join(difflib.unified_diff(self.original.splitlines(keepends=True),
                                           current.splitlines(keepends=True),
                                           fromfile="a/" + SOURCE, tofile="b/" + SOURCE))

    def verify_public_copy(self, trust):
        trust.verify_immutable()
        actual = sha256(self.path("public/PublicProbe.java"))
        if actual != trust.fingerprints[f"fixtures/{self.case_id}/public/PublicProbe.java"]:
            raise AuthorityError("public probe copy changed")
