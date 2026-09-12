import json
import tempfile
import unittest
from pathlib import Path

from gar_ai.incidents import IncidentManager


class IncidentTests(unittest.TestCase):
    def test_actions_jsonl_is_real_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = IncidentManager(td).create("x", digest={}, task=None, master_plan={}, actions=[{"a": 1}, {"b": 2}], failures=[], nearby_state=None, budget={})
            lines = (Path(path) / "actions.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2); self.assertEqual(json.loads(lines[0]), {"a": 1}); self.assertEqual(json.loads(lines[1]), {"b": 2})


if __name__ == "__main__": unittest.main()
