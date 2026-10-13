"""Inert source-digest/observation double. No compilation, evaluation, shell or VM."""
from .core import Failure, digest
from .fixture import FALSE_FIX, INTERMEDIATE, ORIGINAL, known_sources


class InertSandbox:
    mode = "local-double"
    generated_code_processes = 0
    real_sessions = 0

    def observe(self, source, quantities):
        pattern = known_sources().get(digest(source))
        if pattern is None:
            raise Failure("CONTRACT_REJECTED", "double_source_not_recognized")
        # A finite lookup implementation for authored fixture bytes, not a Java interpreter.
        bounds = {ORIGINAL: (0, 100), INTERMEDIATE: (1, 1), FALSE_FIX: (1, 99)}
        low, high = bounds.get(pattern, (1, 100))
        return {"mode": self.mode, "execution": "none", "source_sha256": digest(source),
                "records": [{"quantity": q, "accepted": low <= q <= high} for q in quantities]}

    def public(self, source):
        result = self.observe(source, (0, 2))
        result["status"] = "passed" if [r["accepted"] for r in result["records"]] == [False, True] else "semantic_failure"
        return result

