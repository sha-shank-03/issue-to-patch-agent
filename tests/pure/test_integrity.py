from unittest.mock import patch
from issue_to_patch.runner import JavaRunner
from issue_to_patch.providers import ORIGINAL, NOVEL
from issue_to_patch.workspace import AuthorityError, SOURCE
from helpers import LocalCase


class RunnerIntegrityTests(LocalCase):
    def runner(self, trust):
        executable = self.repo / "fictional-not-executable.exe"
        executable.write_bytes(b"test double; never launched")
        return JavaRunner(self.repo, trust, javac=str(executable), java=str(executable))

    def test_novel_source_denied_before_compile_double(self):
        ws, trust = self.workspace()
        ws.replace(SOURCE, ws.digest, ORIGINAL, NOVEL)
        runner = self.runner(trust)
        with patch.object(runner, "_run") as execute, self.assertRaises(AuthorityError):
            runner.observe(ws)
        execute.assert_not_called()

    def test_candidate_mutation_between_compile_and_launch_is_denied(self):
        ws, trust = self.workspace()
        runner = self.runner(trust)
        def compile_double(*args):
            ws.path(SOURCE).write_text(ws.original + "\n", encoding="utf-8", newline="\n")
            return {"status": "completed", "exit_code": 0}
        with patch.object(runner, "_run", side_effect=compile_double) as execute, self.assertRaises(AuthorityError):
            runner.observe(ws)
        self.assertEqual(execute.call_count, 1)

    def test_public_probe_mutation_between_compile_and_launch_is_denied(self):
        ws, trust = self.workspace()
        runner = self.runner(trust)
        def compile_double(*args):
            ws.path("public/PublicProbe.java").write_text("tampered", encoding="utf-8")
            return {"status": "completed", "exit_code": 0}
        with patch.object(runner, "_run", side_effect=compile_double) as execute, self.assertRaises(AuthorityError):
            runner.observe(ws)
        self.assertEqual(execute.call_count, 1)

    def test_candidate_mutation_during_probe_is_denied(self):
        ws, trust = self.workspace()
        runner = self.runner(trust)
        calls = []
        def execute_double(*args):
            calls.append(args)
            if len(calls) == 2:
                ws.path(SOURCE).write_text(ws.original + "\n", encoding="utf-8", newline="\n")
            return {"status": "completed", "exit_code": 0, "stdout": "fake observations"}
        with patch.object(runner, "_run", side_effect=execute_double), self.assertRaises(AuthorityError):
            runner.observe(ws)
        self.assertEqual(len(calls), 2)

    def test_missing_compiler_returns_infrastructure_error_without_launch(self):
        ws, trust = self.workspace()
        runner = JavaRunner(self.repo, trust, javac=str(self.repo / "missing.exe"), java=str(self.repo / "missing-java.exe"))
        with patch.object(runner, "_run") as execute:
            result = runner.observe(ws)
        self.assertEqual(result["status"], "infrastructure_error")
        execute.assert_not_called()
