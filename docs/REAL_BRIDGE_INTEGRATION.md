# Real Factorio Bridge integration

The V0 kernel intentionally does **not** guess the existing Factorio Controller/Bridge method names. Wire your already-tested controller through `CallbackBridgeAdapter`.

## Required callbacks

```python
BridgeCallbacks(
    snapshot=...,
    scan_area=...,
    query_recipe=...,
    query_technology=...,
    act=...,
)
```

### `snapshot()`

Return a normalized dictionary containing the V0 fields: game tick, player position/inventory, entities, power, resources, research and threat.

```python
{
    "game_tick": 123,
    "player": {"position": [0, 0], "inventory": {"iron-plate": 10}},
    "entities": [{"name": "lab", "position": [5, 5], "inventory": {"automation-science-pack": 2}, "recipe": None}],
    "power": {"margin": 0.25, "status": "ok"},
    "resources": {"iron": {"stock": 100, "rate": 60}, "copper": {"stock": 80, "rate": 45}, "coal": {"stock": 50, "rate": 20}},
    "research": {"technology": "automation", "progress": 0.24, "unit_count": 10, "science_supply": {"automation-science-pack": 3}, "state": "progressing"},
    "threat": {"level": "low"}
}
```

Normalize the real game/controller state here. Do not make the planner understand multiple raw Bridge formats.

## `act(action, params)`

Return `Ack(status="accepted" | "rejected", action_id="...", detail="...")`.

`accepted` means only that the command was accepted. It does **not** mean the world changed. `VerifiedToolSurface` always reads a fresh snapshot afterward.

## Live Contract Probe checklist

For every primitive mapped into `act`:

1. verify accepted ACK on a valid action;
2. verify the expected world-state mutation;
3. verify rejected/blocked behavior;
4. verify already-satisfied/idempotent behavior;
5. verify edge conditions and Factorio 2.0 semantics;
6. record the probe result before exposing the primitive to AI-facing code.

## Wiring example

```python
from gar_ai.adapters import BridgeCallbacks, CallbackBridgeAdapter
from gar_ai.types import Ack

callbacks = BridgeCallbacks(
    snapshot=lambda: normalized_snapshot_from_existing_controller(),
    scan_area=lambda center, radius: existing_scan(center, radius),
    query_recipe=lambda name: existing_recipe_probe(name),
    query_technology=lambda name: existing_tech_probe(name),
    act=lambda action, params: Ack(**existing_action_dispatch(action, params)),
)

bridge = CallbackBridgeAdapter(callbacks)
```

The important rule is not the names. It is that **every exposed write primitive has known live semantics and can be proven by fresh state**.
