# V0-RC1 runtime hardening

This patch is a response to the second V0/V0.5 code review. It does not add V1 gameplay scope.

## Fixed in code

1. `ControllerLoop.run_forever()` is wired through a package CLI entry point.
2. Orchestrator `safe_stop` is interpreted as controller `SAFE_HOLD`; it no longer terminates the 24/7 loop.
3. `ControllerLoop.resume()` requests a fresh `user_resume` synchronization.
4. `Keeper.action_log` is bounded in memory; every action is also persisted to `actions.jsonl`.
5. Global batch-budget counters are persisted in `JsonStateStore`.
6. Persistent Global Budget uses a rolling window (default one hour), preventing both restart bypass and lifetime exhaustion.
7. V0.5 smelting operational verification requires a positive `min_product_rate`.
8. Touched safety-critical files were expanded from dense one-line style into reviewable code.

## Not claimed as fixed

- real Factorio Bridge/Mod/Lua integration;
- Live Contract Probe against a real save;
- V0 release acceptance in the real game;
- cross-context concurrent BatchBudget transactions;
- V1 task preemption, Combat Runtime, rollback, rail, run_python, or Space Age.

V0.5 remains implemented but not live-accepted until the real V0 release gate passes.
