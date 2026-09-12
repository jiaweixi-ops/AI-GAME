# AI-game — Factorio Autonomous Agent Lite

Current code target: **V0-RC1 readiness + V0.5 Engineering Freeze implementation**.

> The LLM chooses the future; deterministic code moves reality toward that future.

## Status discipline

Implementation state and acceptance state are deliberately separate:

- V0/V0.5 Python kernel: **IMPLEMENTED / MOCK_VERIFIED**
- real Factorio Bridge/Mod/Lua adapter: **NOT PRESENT IN THIS REPOSITORY**
- real current-save V0 acceptance: **NOT YET LIVE_VERIFIED**
- real smelting V0.5 acceptance: **NOT YET LIVE_VERIFIED**

Passing unit tests does not count as a live Factorio release acceptance.

## V0 trusted kernel

The repository keeps the V0 guarantees: ACK + fresh-state verified writes, desired-state/idempotent tasks, bounded replan, Watchdog, incident bundles, safe AI fallback and event-driven control.

## V0-RC1 runtime hardening

- `gar-ai` CLI / `python -m gar_ai` is the real controller entry point;
- the CLI requires a user-supplied, already-live-probed `module:function` Bridge factory;
- orchestrator `safe_stop` becomes controller `SAFE_HOLD`; the 24/7 process stays alive;
- `ControllerLoop.resume()` leaves SAFE_HOLD and forces state/strategy resynchronization;
- Keeper in-memory action history is a bounded ring buffer;
- full action history is persisted as JSONL;
- Global Batch Budget is persisted and uses a rolling window so restart cannot bypass it and long-running controllers do not hit a lifetime quota;
- V0.5 smelting verification requires a positive product-rate threshold.

## V0.5 implemented infrastructure

- schema/version contracts for tools, Digest, TaskSpec, prompts, Blueprint IR and Contract Probes;
- unified error semantics and policies;
- tick/timestamp freshness metadata;
- Global + Task + Batch + Atomic budget layering;
- persistent area locks and material reservations;
- non-blocking async verification (`pending -> verified/timeout/failed`);
- operation journal / transaction boundary for batch work;
- structured failure fingerprints and duplicate-recovery rejection support;
- replan rate guard;
- formal runtime metrics;
- versioned Blueprint IR;
- deterministic Site Planner;
- parameterized 8/16/24/48-furnace smelting layouts;
- Batch Executor with checkpoints, partial-failure accounting, lock/reservation release and final production verification.

## Running the controller

The repository intentionally does not invent your real Factorio action names. Provide a Python factory that returns an object implementing the `GameBridge` contract, then run:

```bash
export GAR_AI_ENDPOINT="https://your-provider.example/v1/chat/completions"
export GAR_AI_MODEL="your-model"
export GAR_AI_API_KEY="..."

gar-ai \
  --bridge-factory your_factorio_adapter:create_bridge \
  --runtime-dir runtime/live
```

Equivalent:

```bash
python -m gar_ai --bridge-factory your_factorio_adapter:create_bridge
```

Every primitive exposed by that adapter must pass a versioned Live Contract Probe first.

## Safety behavior

A failed batch does **not** automatically demolish player construction. It records a partial transaction, releases unused reservations/area locks, emits structured evidence, and expects desired-state reconciliation/replan.

An AI/provider failure does not terminate the 24/7 controller. The controller enters `SAFE_HOLD`, continues heartbeat/state availability, and waits for an explicit resume or later recovery mechanism.

## Tests

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Next real milestone

Do not expand to V1 yet.

1. provide the real Factorio Bridge/Controller/Mod adapter;
2. run Live Contract Probes against the real game;
3. complete one non-prewritten V0 objective on the current save;
4. force a blocked condition and prove replan/recovery;
5. restart mid-task and prove desired-state reconciliation;
6. only then run the V0.5 real smelting acceptance: site selection, reservation, batch construction, power and mandatory production-rate verification.
