import unittest

from gar_ai.ai_client import DecisionValidationError, ScriptedAIClient


class AIClientTests(unittest.TestCase):
    def test_disallowed_tool_rejected(self):
        client = ScriptedAIClient([{"decision": "create_task", "task": {"task_id": "bad", "objective": "bad", "reason": "bad", "desired_state": {}, "operations": [{"tool": "raw_lua", "args": {}}], "success_when": [], "abort_if": []}}])
        with self.assertRaises(DecisionValidationError):
            client.decide(digest={}, master_plan={}, failure_history=[], allowed_tools=["move_to_verified"], trigger="test")


if __name__ == "__main__": unittest.main()
