# V0 Engineering Freeze — V1.6.1 remediation

## Goal

Prove one minimum trusted autonomous loop on the current save:

`real state -> digest -> AI decision -> desired-state task -> Keeper -> verified tools -> fresh-state -> complete OR bounded stop + incident + automatic replan`

## V0 tool surface

Read: `get_digest`, `scan_area`, `query_recipe`, `query_technology`.

Write: `move_to_verified`, `ensure_item_verified`, `place_verified`, `transfer_verified`, `set_recipe_verified`, `research_verified`.

Write success requires ACK accepted **and** fresh-state evidence. `research_verified` additionally requires evidence that the target research is actually progressing, not merely selected.

## Task schema

A `create_task` decision MUST include `task_id`, `objective`, `reason`, dot-path `desired_state`, non-empty bounded `operations`, non-empty `success_when`, and `abort_if`.

Keeper reconciles from live state on each execution. It replays the bounded operation list from the beginning; V0 tools are idempotent, so satisfied writes become `NOOP` while externally-lost effects can be repaired.

## Budget semantics

Atomic and task action counters are distinct and both are charged for every atomic tool call. Both are per-task. Runtime budget restoration is accepted only when `task_id` matches, preventing a completed task from consuming a later task's lifetime budget.

Budget exhaustion has structured codes such as `ATOMIC_BUDGET_EXCEEDED`, `TASK_BUDGET_EXCEEDED`, and `REPLAN_BUDGET_EXCEEDED`.

## Replan contract

A blocked task creates an incident and automatically enters `ai.decide(trigger="replan")`. Each replan increments the persisted replan budget. Exhausting `max_replans` enters `safe_stop`.

## Watchdog contract

Watchdog history is task-scoped. It recognizes at least `A-B-A-B`, a width-3 pattern repeated twice, repeated key state with no meaningful progress, and no-progress timeout.

## Controller loop

`ControllerLoop` is the persistent V0 driver. Heartbeats do not imply LLM calls: active Keeper work is local, idle heartbeats are zero-token, and AI is reached on startup, automatic replan, user/strategic events, or low-frequency strategic review.

## Safe fallback

AI/provider/schema exceptions do not escape the orchestrator. They create an incident and return `safe_stop`.

## Acceptance

- false success = 0
- infinite loops = 0
- blocked work automatically replans
- replan budget is effective
- budgets reset at task boundary but survive restart of the same task
- repeated task submission stays idempotent
- unknown `abort_if` paths fail safe
- incident `actions.jsonl` is real JSONL
- no raw Lua/direct bridge action is exposed to the model
