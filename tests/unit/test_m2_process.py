"""Requires the integration lease: harmless real owned Python process only."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from issue_to_patch.runner import JavaRunner
from issue_to_patch.workspace import Trust

REPO = Path(__file__).resolve().parents[2]


class RealCancellationTests(unittest.TestCase):
    def test_keyboard_cancellation_reaps_real_owned_child(self):
        owned = []
        actual_popen = subprocess.Popen
        def start(*args, **kwargs):
            process = actual_popen(*args, **kwargs)
            owned.append(process)
            return process
        runner = JavaRunner(REPO, Trust(REPO))
        with patch("issue_to_patch.runner.subprocess.Popen", side_effect=start), \
                patch("issue_to_patch.runner.time.sleep", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                runner._run([sys.executable, "-c", "import time; time.sleep(30)"], REPO, 5)
        self.assertEqual(len(owned), 1)
        self.assertIsNotNone(owned[0].poll())
        self.assertTrue(owned[0].stdout.closed and owned[0].stderr.closed)
