# AI decision schema — V0.1

The planner returns one JSON object. Free-form execution instructions are rejected.

`create_task` requires a non-empty bounded `operations` list and at least one structured `success_when` condition.

`desired_state` uses dot-separated paths into the normalized live snapshot, for example `research.state` or `player.position`.

Allowed condition operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `truthy`, `falsy`, `changed`, `increased`, `delta_gt`.

`changed` / `increased` / `delta_gt` compare the final state with the task execution baseline.

Unknown `abort_if` paths fail safe and block the task.

`operations[].tool` must be in the fixed Verified Tool Surface allowlist. Raw Lua/direct Bridge actions are rejected.
