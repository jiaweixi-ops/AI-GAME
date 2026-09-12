# V0-RC1 Second Review

This review records the second verification pass after V1.6.1 remediation and V0.5 infrastructure work. It is the input to V0-RC2 runtime hardening.

## Verified fixed in V0-RC1

- real CLI entry point exists (`gar-ai` and `python -m gar_ai`);
- `run_forever` keeps the process alive after orchestrator `safe_stop`;
- Keeper action history is bounded in memory and persisted in full to JSONL;
- Global Batch Budget survives restart and uses a rolling time window;
- smelting operational verification requires a positive output-rate threshold;
- safety-critical code touched by the previous patch was expanded into reviewable formatting;
- `resume()` forces a `user_resume` strategic synchronization.

## Open findings addressed by V0-RC2

1. SAFE_HOLD was previously enforced only by `run_forever`; direct `step()` callers could bypass the transition.
2. SAFE_HOLD had no CLI/OS recovery path, making it a one-way state for an unattended process.
3. Global Budget persistence rewrote JSON on every atomic action and needed bounded write batching.
4. Long-running operations needed a clean stop path and configurable Keeper action-log retention.

## V0-RC2 decisions

- SAFE_HOLD transition belongs inside `ControllerLoop.step()`.
- `SIGINT`/`SIGTERM` request graceful shutdown.
- `SIGUSR1` (POSIX) or `SIGBREAK` (Windows when available) calls `ControllerLoop.resume()`.
- Global Budget persists on configurable action/time thresholds and force-flushes at checkpoints and terminal batch transitions.
- `--duration-sec` exposes a supervised graceful stop path.
- `--action-log-limit` is propagated through `KeeperPolicy` instead of being hard-coded by orchestration.
- shutdown performs best-effort fsync of durable runtime files.

## Explicitly deferred

- real Factorio Bridge/Mod/Lua integration;
- real-save Live Contract Probe and V0 release acceptance;
- cross-context concurrent Global Budget transactions;
- task preemption / parallel DAG;
- Combat Runtime, rollback, rail, run_python, multi-force, Space Age.

## Release discipline

V0/V0.5 code remains **IMPLEMENTED / MOCK_VERIFIED**, not **LIVE_VERIFIED**. After V0-RC2, framework expansion stops. The next engineering input must come from a real Factorio Bridge, Live Contract Probes, and current-save V0 acceptance.
