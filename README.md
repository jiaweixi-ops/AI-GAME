# AI-game — Factorio Autonomous Agent Lite V0

Current version: **V1.6.1 V0 Remediation**.

> The LLM chooses the future; deterministic code moves reality toward that future.

This repository contains the minimum trusted execution kernel for an event-driven Factorio agent. It deliberately does **not** attempt full-game automation yet.

## Implemented kernel

- live-probed `GameBridge` contract + callback adapter
- Verified Tool Surface with ACK + fresh-state
- research verification that rejects starved "selected only" false success
- fixed State Digest schema
- desired-state/idempotent tasks
- independent Atomic Budget + Task Budget, scoped by `task_id`
- automatic blocked -> incident -> AI replan -> bounded safe-stop path
- task-scoped Watchdog: no-progress, short loop patterns, state recurrence
- real JSONL incident action log
- AI/provider exception safe fallback
- persistent `ControllerLoop` without LLM tick-loop behavior
- basic runtime metrics
- in-memory Bridge and regression tests

## V0 non-goals

No universal layout generator, Blueprint IR executor, rail/signals, `run_python`, active nest clearing, random-new-game autonomy, rocket automation, screenshot control, or mouse/keyboard control.

## Run tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The V1.6.1 remediation suite contains **28 tests** covering the compliance-audit failure paths in addition to the original trusted-loop behavior.

## Real Factorio integration

The repository still does not invent your existing Controller/Lua action names. Wire already-live-probed callbacks through `CallbackBridgeAdapter`; see `docs/REAL_BRIDGE_INTEGRATION.md`.

Before V0.5, the next milestone remains **real current-save V0 acceptance**:

1. run Live Contract Probes for each real primitive;
2. connect normalized snapshot/query/action callbacks;
3. complete one non-prewritten real objective;
4. force one blocked condition and confirm automatic replan;
5. restart during a task and confirm live-state reconciliation;
6. verify false success = 0 and infinite loop = 0.

See `docs/V0_SPEC.md` and `docs/V1.6.1_REMEDIATION.md`.
