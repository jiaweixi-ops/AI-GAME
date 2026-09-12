# V0 Engineering Freeze

## Goal

Prove one minimum trusted autonomous loop on the **current save**:

```text
real state
→ fixed State Digest
→ AI chooses one non-prewritten objective
→ desired-state task
→ Keeper
→ verified tools
→ fresh-state
→ complete OR bounded stop + incident + replan
```

## Non-goals

No universal layouts, rail/signals, `run_python`, active nest clearing, random new-game autonomy, rocket automation, screenshot control, or mouse/keyboard control.

## V0 tools

Read: `get_digest`, `scan_area`, `query_recipe`, `query_technology`.

Write: `move_to_verified`, `ensure_item_verified`, `place_verified`, `transfer_verified`, `set_recipe_verified`, `research_verified`.

Write success means **ACK accepted + fresh-state verified**.

## Digest contract

Fields are fixed in V0 and are never silently omitted. Unknown values are `null`: schema version, timestamp, game tick, goal, agent state, power, iron/copper/coal, research, bottleneck, recent failure, threat, and current/next/watch plan fields.

## Meaningful progress

Counts: technology truly advances, target inventory grows, target production improves, new entity is fresh-state verified, area becomes powered, task/work item closes, or research changes from starved to progressing.

Does not count: movement, scanning, opening containers, repeated query, repeated failed action, waiting, or log output.

## Budget contract

Every atomic tool call consumes `AtomicBudget` even when called by a future batch executor. The task also consumes `TaskBudget`; the stricter limit wins. Budget state is persisted so restarting the controller does not reset action counters.

## Watchdog contract

V0 must stop on `NO_PROGRESS`, `LOOP_DETECTED`, `STATE_RECURRENCE`, budget exhaustion, rejected ACK, or accepted ACK with failed fresh-state verification. No infinite retry path is allowed.

## Stage-handler policy

Legacy stage handlers may exist only as bootstrap/fallback/safety-net behavior. They must not silently become the main path.

## Combat scope

V0 does not actively clear nests. Safety events may interrupt ordinary work; active attack planning is a later milestone.

## V0 release acceptance

- at least one real non-prewritten objective completed
- false success: 0
- infinite loops: 0
- budget bypass: 0
- blocked work stops automatically
- replan can produce a new valid task
- restart does not repeat completed work
- repeated task submission is idempotent
- no obvious strategic thrashing
- AI is event-driven, not tick-driven
- Keeper performs deterministic execution with zero AI tokens
