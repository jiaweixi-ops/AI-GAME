# AI-game — Factorio Autonomous Agent Lite

Current code target: **V0.5 Engineering Freeze** on top of the V1.6.1 trusted V0 kernel.

> The LLM chooses the future; deterministic code moves reality toward that future.

## V0 trusted kernel

The repository keeps the V0 guarantees: ACK + fresh-state verified writes, desired-state/idempotent tasks, bounded replan, Watchdog, incident bundles, safe AI fallback and event-driven control.

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

## Smelting template scope

V0.5 intentionally supports only:

- furnace count: `8 / 16 / 24 / 48`;
- layout: `single-row / double-row`;
- input side: `left / right`;
- expansion direction: `north / south`.

It is not a universal layout engine.

## Safety behavior

A failed batch does **not** automatically demolish player construction. It records a partial transaction, releases unused reservations/area locks, emits structured evidence, and expects desired-state reconciliation/replan.

Real Factorio action names are still not invented here. Each primitive must pass a versioned Live Contract Probe before being wired through the real Bridge adapter.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Next real milestone

Before expanding to V1, connect the real Factorio Bridge and perform current-save acceptance of V0/V0.5: live probes, real site selection, material staging, one smelting module construction, production verification, forced failure/replan, restart reconciliation and metrics collection.
