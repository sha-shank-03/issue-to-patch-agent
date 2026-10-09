"""Owned, bounded Java process execution for statically permitted source only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from .workspace import AuthorityError, BudgetError, SOURCE


class JavaRunner:
    execution_kind = "java_subprocess"

    def __init__(self, repo, trust, javac=None, java=None):
        self.repo, self.trust = Path(repo).resolve(), trust
        self.javac = javac or shutil.which("javac")
        self.java = java or shutil.which("java")
        self.commands = []
        self.deadline = None

    def _run(self, argv, cwd, timeout):
        start = time.monotonic()
        if self.deadline is not None:
            timeout = min(timeout, self.deadline - start)
        if timeout <= 0:
            raise BudgetError("wall-time budget exhausted before process launch")
        env = {key: os.environ[key] for key in ("SystemRoot", "SystemDrive", "ProgramData", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
        env.update({"LANG": "C", "LC_ALL": "C"})
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.Popen(argv, cwd=cwd, env=env, shell=False,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, creationflags=flags)
        buffers = [bytearray(), bytearray()]
        lock, overflow = threading.Lock(), threading.Event()

        def drain(pipe, index):
            while True:
                chunk = pipe.read1(4096)
                if not chunk:
                    break
                with lock:
                    room = 262144 - sum(len(buffer) for buffer in buffers)
                    buffers[index].extend(chunk[:max(0, room)])
                    if len(chunk) > room:
                        overflow.set()

        threads = [threading.Thread(target=drain, args=(pipe, i), daemon=True)
                   for i, pipe in enumerate((proc.stdout, proc.stderr))]
        for thread in threads:
            thread.start()
        status = "completed"
        try:
            while proc.poll() is None:
                if overflow.is_set():
                    status = "output_limit"
                    proc.kill()
                    break
                if time.monotonic() - start >= timeout:
                    status = "timeout"
                    proc.kill()
                    break
                time.sleep(0.01)
            proc.wait()
        except BaseException:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            raise
        finally:
            for thread in threads:
                thread.join(timeout=1)
            proc.stdout.close()
            proc.stderr.close()
        if overflow.is_set():
            status = "output_limit"
        result = {"status": status, "exit_code": proc.returncode,
                  "stdout": buffers[0].decode("utf-8", errors="replace"),
                  "stderr": buffers[1].decode("utf-8", errors="replace"),
                  "elapsed_seconds": round(time.monotonic() - start, 6),
                  "argv": [Path(argv[0]).name] + [str(arg).replace(str(self.repo), "<repo>") for arg in argv[1:]]}
        result["stdout"] = result["stdout"].replace(str(self.repo), "<repo>")
        result["stderr"] = result["stderr"].replace(str(self.repo), "<repo>")
        return result

    def observe(self, workspace, independent=False):
        source = workspace.path(SOURCE)
        digest = workspace.digest
        if not self.trust.permits(source):
            raise AuthorityError("novel source is proposal-only")
        workspace.verify_public_copy(self.trust)
        if not self.javac or not self.java:
            return {"status": "infrastructure_error", "error": "java/javac unavailable", "source_sha256": digest}
        for executable in (self.javac, self.java):
            if not Path(executable).is_file() or Path(executable).suffix.lower() in {".bat", ".cmd"}:
                return {"status": "infrastructure_error", "error": "invalid Java executable", "source_sha256": digest}
        build = workspace.run_dir / ("independent-build" if independent else "public-build") / str(len(self.commands))
        build.mkdir(parents=True, exist_ok=False)
        probe = self.repo / self.trust.case_info["independent_probe"] if independent else workspace.path("public/PublicProbe.java")
        main = "fixture.IndependentProbe" if independent else "fixture.PublicProbe"
        compile_args = [self.javac, "-J-Xmx256m", "--release", "17", "-proc:none", "-encoding", "UTF-8", "-d", str(build), str(source), str(probe)]
        try:
            compile_result = self._run(compile_args, workspace.run_dir, 15)
            compile_result.update({"stage": "compile", "source_sha256": digest, "independent": independent})
            self.commands.append(compile_result)
            if compile_result["status"] != "completed" or compile_result["exit_code"] != 0:
                return {"status": "compile_error", "source_sha256": digest, "command": compile_result}
            self.trust.verify_immutable()
            workspace.verify_public_copy(self.trust)
            if workspace.digest != digest:
                raise AuthorityError("candidate changed before launch")
            observed = self._run([self.java, "-Xmx128m", "-Dfile.encoding=UTF-8", "-cp", str(build), main], workspace.run_dir, 5)
            observed.update({"stage": "probe", "source_sha256": digest, "independent": independent})
            self.commands.append(observed)
            if observed["status"] != "completed" or observed["exit_code"] != 0:
                return {"status": "probe_error", "source_sha256": digest, "command": observed}
            self.trust.verify_immutable()
            workspace.verify_public_copy(self.trust)
            if workspace.digest != digest:
                raise AuthorityError("candidate changed during probe")
            return {"status": "observed", "source_sha256": digest, "output": observed["stdout"]}
        except OSError:
            return {"status": "infrastructure_error", "error": "Java process could not start", "source_sha256": digest}


def public_verdict(observation, trust=None):
    if observation["status"] != "observed":
        return observation
    if trust is not None and not trust.case_info.get("legacy_observations"):
        from .observations import compare
        trust.verify_immutable()
        expected = json.loads((trust.repo / trust.case_info["public_expected"]).read_text(encoding="utf-8"))
        verdict = compare(observation["output"], expected)
        return {"status": "semantic_failure" if verdict["failures"] else "passed",
                "source_sha256": observation["source_sha256"], "scenario_count": verdict["scenario_count"],
                "failures": verdict["failures"], "observations": observation["output"]}
    expected = {0: (False, 200, 0), -1: (False, 200, 0), 5: (True, 195, 1)}
    if trust is not None:
        frozen = json.loads((trust.repo / trust.case_info["public_expected"]).read_text(encoding="utf-8"))
        quantities = {int(key.split(".")[0].removeprefix("quantity_")) for key in frozen}
        expected = {q: tuple(frozen[f"quantity_{q}.{field}"] for field in ("accepted", "stock", "orders")) for q in quantities}
    rows = parse_observations(observation["output"], set(expected))
    failures = [str(quantity) for quantity in expected if rows[quantity] != expected[quantity]]
    return {"status": "semantic_failure" if failures else "passed", "source_sha256": observation["source_sha256"],
            "scenario_count": len(expected), "failures": failures, "observations": observation["output"]}


def parse_observations(raw, quantities):
    rows = {}
    for line in raw.splitlines():
        fields = line.split("\t")
        if len(fields) != 4 or fields[1] not in {"true", "false"}:
            raise AuthorityError("malformed probe output")
        try:
            quantity, stock, orders = int(fields[0]), int(fields[2]), int(fields[3])
        except ValueError as exc:
            raise AuthorityError("non-integer probe output") from exc
        if quantity in rows or quantity not in quantities:
            raise AuthorityError("duplicate/unexpected probe scenario")
        rows[quantity] = (fields[1] == "true", stock, orders)
    if set(rows) != quantities:
        raise AuthorityError("missing probe scenarios")
    return rows
