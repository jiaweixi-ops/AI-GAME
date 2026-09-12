import unittest

from gar_ai.ai_client import DecisionValidationError, validate_decision
from gar_ai.types import Decision


class AIClientTests(unittest.TestCase):
    def test_create_task_requires_success_condition(self):
        decision = Decision.from_dict({"decision": "create_task", "task": {"task_id": "t", "objective": "x", "reason": "y", "desired_state": {}, "operations": [{"tool": "get_digest", "args": {}}], "success_when": [], "abort_if": []}})
        with self.assertRaises(DecisionValidationError): validate_decision(decision, ["get_digest"])

    def test_unknown_tool_rejected(self):
        decision = Decision.from_dict({"decision": "create_task", "task": {"task_id": "t", "objective": "x", "reason": "y", "desired_state": {"research.state": "progressing"}, "operations": [{"tool": "raw_lua", "args": {}}], "success_when": [{"path": "research.state", "op": "eq", "value": "progressing"}], "abort_if": []}})
        with self.assertRaises(DecisionValidationError): validate_decision(decision, ["get_digest"])


if __name__ == "__main__": unittest.main()
