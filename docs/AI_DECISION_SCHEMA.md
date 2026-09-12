# AI decision schema — V0

The planner returns a single JSON object. Free-form execution instructions are rejected.

```json
{
  "decision": "create_task",
  "reason": "research is starved",
  "plan_patch": {
    "current": "restore research",
    "next": "continue current technology",
    "watch": ["research.state", "research.progress"]
  },
  "task": {
    "task_id": "restore-research-001",
    "objective": "restore research progress",
    "reason": "science supply is empty",
    "desired_state": {"research.state": "progressing"},
    "operations": [
      {"tool": "ensure_item_verified", "args": {"item": "automation-science-pack", "count": 3}},
      {"tool": "transfer_verified", "args": {"item": "automation-science-pack", "x": 5, "y": 5, "target_count": 3}}
    ],
    "success_when": [{"path": "research.state", "op": "eq", "value": "progressing"}],
    "abort_if": []
  }
}
```

Allowed condition operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `truthy`, `falsy`.

The model cannot name arbitrary bridge/Lua actions. `operations[].tool` must be in the fixed verified-tool allowlist or the decision is rejected before execution.
