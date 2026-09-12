# AI-game — Factorio Autonomous Agent Lite V0

This repository contains the **V1.6 engineering-freeze / V0 minimum trusted loop** for the Factorio autonomous-agent plan.

The design rule is simple:

> **The LLM chooses the future; deterministic code moves reality toward that future.**

The model is not a tick-loop. It is an event-driven strategic planner. `Keeper` executes bounded work, `VerifiedToolSurface` requires **ACK accepted + fresh-state**, and `Watchdog` stops no-progress/looping behavior.

## V0 scope

Included:

- `GameBridge` protocol (no guessed Factorio API signatures)
- callback adapter for an existing controller
- `VerifiedToolSurface`
- fixed V0 `StateDigest`
- idempotent desired-state tasks
- persistent **Atomic Budget + Task Budget**
- `Keeper` with cursor-based restart/resume
- `Watchdog`: `NO_PROGRESS`, `LOOP_DETECTED`, `STATE_RECURRENCE`
- failure history and incident bundles
- versioned `MasterPlan`
- event-driven AI client protocol
- dependency-free chat-completions-compatible HTTP adapter
- in-memory bridge + unit/integration tests

Explicitly **not** in V0:

- universal layout generation
- rail/signals
- `run_python`
- active nest clearing
- random-new-game autonomy
- rocket automation
- screenshot / mouse-keyboard control

## Architecture

```text
Factorio
   ↕
Real Bridge / existing controller
   ↕
GameBridge adapter
   ↓
VerifiedToolSurface ── shared BudgetContext
   ↓
Keeper ── Watchdog ── Incident store
   ↑
TaskSpec (desired_state + bounded operations)
   ↑
Event-driven AI client
   ↑
StateDigest + MasterPlan + failure history
```

## Why the real Factorio adapter is not hard-coded here

The target GitHub repository was empty when V0 was created, and the existing Factorio Bridge/Controller implementation was not present in this repository. V0 therefore defines a narrow `GameBridge` contract and a `CallbackBridgeAdapter` instead of inventing action names or response semantics.

**Before connecting a real primitive, run a live contract probe.** Only primitives whose real ACK/state behavior is confirmed should be exposed through the adapter.

See [`docs/REAL_BRIDGE_INTEGRATION.md`](docs/REAL_BRIDGE_INTEGRATION.md).

## Run tests

Python 3.11+:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Run the local V0 demo

```bash
PYTHONPATH=src python examples/demo_v0.py
```

The demo starts from a simulated `research.state = "starved"`, receives one strategic task, obtains science packs, transfers them to a lab, and only reports completion after fresh-state confirms research is progressing.

## Core success rule

A write is successful only when:

```text
ACK == accepted
AND
fresh game state proves the desired state
```

An accepted command with no state change is returned as `unverified`, not success.

## Idempotency

Tools are designed around desired state, for example:

```text
transfer_verified(item="automation-science-pack", target_count=3)
```

On restart, if the lab already contains 3 packs the tool returns `NOOP`; it does not transfer another 3.

`Keeper` also persists the task cursor and budget counters after every verified operation.

## Budget model

Every atomic tool call consumes `AtomicBudget`, including calls made inside future batch executors. The whole task also consumes `TaskBudget`.

The stricter limit wins.

```text
Atomic Budget
  max_total_actions
  per_tool limits

Task Budget
  max_actions
  max_entities
  max_material_cost
  max_duration_sec
  max_failures
  max_replans
```

A batch executor is therefore not a way to bypass atomic limits.

## AI integration

Production code depends on the small `AIClient` protocol. `OpenAICompatibleAIClient` is only one adapter and can be replaced by any provider-specific implementation.

The AI may return only:

- `create_task`
- `continue`
- `safe_stop`

A V0 task contains:

- `task_id`
- `objective`
- `reason`
- `desired_state`
- bounded `operations`
- `success_when`
- `abort_if`

Only allow-listed verified tools are accepted. Raw Lua / direct bridge execution is not exposed to the model.

## Runtime state

By default, callers choose the runtime directory. Typical layout:

```text
runtime/
  state/
    task.json
    task_runtime.json
    master_plan.json
    failure_history.json
  incidents/
    <timestamp>_<reason>/
      digest.json
      task.json
      master_plan.json
      actions.jsonl
      failures.json
      nearby_state.json
      budget.json
```

## Next milestone

Do **not** expand V0 until the real current-save loop passes:

1. bridge primitives live-probed;
2. a real non-stage-specific problem is detected from `StateDigest`;
3. AI creates a bounded task;
4. Keeper executes through verified tools;
5. fresh-state proves success;
6. blocked work stops and produces an incident/replan;
7. controller restart resumes idempotently;
8. false success = 0, infinite loop = 0.

After that, V0.5 should add the first parameterized smelting module + Blueprint IR executor.
