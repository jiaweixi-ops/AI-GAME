# AI decision schema — 1.1

Planner output is strict JSON. Unknown fields are rejected.

Top-level fields: `decision`, `reason`, `plan_patch`, optional `task`, `output_schema_version`, `prompt_version`.

`create_task` requires a versioned TaskSpec with a non-empty bounded `operations` list and at least one `success_when` condition. Every ToolCall carries or assumes the current `tool_schema_version`.

Legacy 1.x payloads that omit version fields migrate to current 1.x defaults. A different major version is rejected safely.

The model cannot name arbitrary Bridge/Lua actions. Tool calls remain constrained by the Verified Tool Surface allowlist.
