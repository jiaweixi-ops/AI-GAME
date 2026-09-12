from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .budget import BudgetContext, BudgetExceeded

GLOBAL_BUDGET_SCHEMA_VERSION = "1.0"


class GlobalBudgetStore(Protocol):
    def load_global_budget(self) -> dict[str, Any]: ...
    def save_global_budget(self, data: dict[str, Any]) -> None: ...


@dataclass(slots=True)
class GlobalBudgetLimits:
    max_actions: int = 10000
    max_entities: int = 5000
    max_material_cost: int = 100000
    window_sec: float = 3600.0


@dataclass(slots=True)
class GlobalBudgetPersistencePolicy:
    """Bound global-budget disk writes without making persistence optional."""

    flush_every_actions: int = 25
    flush_interval_sec: float = 5.0

    def validate(self) -> None:
        if self.flush_every_actions <= 0:
            raise ValueError("flush_every_actions must be > 0")
        if self.flush_interval_sec <= 0:
            raise ValueError("flush_interval_sec must be > 0")


@dataclass(slots=True)
class BatchBudgetLimits:
    max_actions: int = 500
    max_entities: int = 256
    max_material_cost: int = 5000
    max_duration_sec: float = 900.0
    max_failures: int = 10
    checkpoint_every_entities: int = 10


@dataclass(slots=True)
class GlobalBudgetState:
    actions: int = 0
    entities: int = 0
    material_cost: int = 0
    window_started_at_epoch: float = field(default_factory=time.time)
    schema_version: str = GLOBAL_BUDGET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any] | None,
        *,
        now: float | None = None,
    ) -> "GlobalBudgetState":
        raw = dict(data or {})
        return cls(
            actions=int(raw.get("actions", 0) or 0),
            entities=int(raw.get("entities", 0) or 0),
            material_cost=int(raw.get("material_cost", 0) or 0),
            window_started_at_epoch=float(
                raw.get(
                    "window_started_at_epoch",
                    now if now is not None else time.time(),
                )
            ),
            schema_version=str(
                raw.get("schema_version", GLOBAL_BUDGET_SCHEMA_VERSION)
            ),
        )


@dataclass(slots=True)
class BatchBudgetState:
    batch_id: str
    actions: int = 0
    entities: int = 0
    material_cost: int = 0
    failures: int = 0
    started_at_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BatchBudgetContext:
    """Task/Batch/Global budget adapter.

    Every atomic call is charged to the parent task budget first and only then
    committed to batch/global counters. Global counters may be persisted through
    ``global_store`` and reset on a bounded rolling window.

    Persistence is deliberately batched: an active process may have a small
    in-memory delta, while checkpoints/terminal transitions call
    :meth:`flush_global` to force durability. This avoids rewriting a JSON file
    for every belt/inserter placement.

    One context is thread-safe. Cross-context concurrent scheduling remains a V1
    concern and requires a shared store-level transaction/lock.
    """

    def __init__(
        self,
        parent: BudgetContext,
        *,
        batch_id: str,
        batch_limits: BatchBudgetLimits | None = None,
        global_limits: GlobalBudgetLimits | None = None,
        batch_state: BatchBudgetState | None = None,
        global_state: GlobalBudgetState | None = None,
        global_store: GlobalBudgetStore | None = None,
        persistence: GlobalBudgetPersistencePolicy | None = None,
        clock=time.time,
    ) -> None:
        self.parent = parent
        self.batch_limits = batch_limits or BatchBudgetLimits()
        self.global_limits = global_limits or GlobalBudgetLimits()
        self.persistence = persistence or GlobalBudgetPersistencePolicy()
        self.persistence.validate()
        self.clock = clock
        self.global_store = global_store
        self._lock = threading.Lock()

        now = float(clock())
        self.batch = batch_state or BatchBudgetState(
            batch_id=batch_id,
            started_at_epoch=now,
        )
        if self.batch.batch_id != batch_id:
            raise ValueError("batch_state.batch_id mismatch")

        if global_state is not None:
            self.global_state = global_state
        elif global_store is not None:
            self.global_state = GlobalBudgetState.from_dict(
                global_store.load_global_budget(),
                now=now,
            )
        else:
            self.global_state = GlobalBudgetState(window_started_at_epoch=now)

        self._dirty_actions = 0
        self._last_persist_at = now
        self._refresh_global_window(now)

    def _write_global(self, now: float | None = None) -> None:
        if self.global_store is None:
            self._dirty_actions = 0
            self._last_persist_at = float(
                self.clock() if now is None else now
            )
            return

        current = float(self.clock() if now is None else now)
        self.global_store.save_global_budget(self.global_state.to_dict())
        self._dirty_actions = 0
        self._last_persist_at = current

    def _persist_global_if_due(self, now: float | None = None) -> None:
        current = float(self.clock() if now is None else now)
        if self._dirty_actions >= self.persistence.flush_every_actions:
            self._write_global(current)
            return
        if current - self._last_persist_at >= self.persistence.flush_interval_sec:
            self._write_global(current)

    def flush_global(self) -> None:
        """Force durable Global Budget state at a checkpoint/terminal boundary."""
        with self._lock:
            self._write_global()

    def _refresh_global_window(self, now: float | None = None) -> None:
        current = float(self.clock() if now is None else now)
        if self.global_limits.window_sec <= 0:
            raise ValueError("global budget window_sec must be > 0")

        age = current - self.global_state.window_started_at_epoch
        if age < self.global_limits.window_sec:
            return

        self.global_state = GlobalBudgetState(window_started_at_epoch=current)
        self._dirty_actions = 0
        self._write_global(current)

    def _preflight(self, *, entities: int, material_cost: int) -> None:
        now = float(self.clock())
        self._refresh_global_window(now)

        if now - self.batch.started_at_epoch > self.batch_limits.max_duration_sec:
            raise BudgetExceeded(
                "BATCH_BUDGET_EXCEEDED",
                "batch duration budget exceeded",
            )
        if self.batch.actions + 1 > self.batch_limits.max_actions:
            raise BudgetExceeded(
                "BATCH_BUDGET_EXCEEDED",
                "batch action budget exceeded",
            )
        if self.batch.entities + entities > self.batch_limits.max_entities:
            raise BudgetExceeded(
                "BATCH_BUDGET_EXCEEDED",
                "batch entity budget exceeded",
            )
        if (
            self.batch.material_cost + material_cost
            > self.batch_limits.max_material_cost
        ):
            raise BudgetExceeded(
                "BATCH_BUDGET_EXCEEDED",
                "batch material budget exceeded",
            )
        if self.global_state.actions + 1 > self.global_limits.max_actions:
            raise BudgetExceeded(
                "GLOBAL_BUDGET_EXCEEDED",
                "global action budget exceeded",
            )
        if self.global_state.entities + entities > self.global_limits.max_entities:
            raise BudgetExceeded(
                "GLOBAL_BUDGET_EXCEEDED",
                "global entity budget exceeded",
            )
        if (
            self.global_state.material_cost + material_cost
            > self.global_limits.max_material_cost
        ):
            raise BudgetExceeded(
                "GLOBAL_BUDGET_EXCEEDED",
                "global material budget exceeded",
            )

    def consume_atomic(
        self,
        tool: str,
        *,
        entities: int = 0,
        material_cost: int = 0,
    ) -> None:
        with self._lock:
            self._preflight(entities=entities, material_cost=material_cost)
            self.parent.consume_atomic(
                tool,
                entities=entities,
                material_cost=material_cost,
            )

            self.batch.actions += 1
            self.batch.entities += entities
            self.batch.material_cost += material_cost

            self.global_state.actions += 1
            self.global_state.entities += entities
            self.global_state.material_cost += material_cost
            self._dirty_actions += 1
            self._persist_global_if_due()

    def record_failure(self) -> None:
        self.batch.failures += 1
        self.parent.record_failure()
        if self.batch.failures > self.batch_limits.max_failures:
            raise BudgetExceeded(
                "BATCH_BUDGET_EXCEEDED",
                "batch failure budget exceeded",
            )

    def checkpoint_due(self) -> bool:
        interval = self.batch_limits.checkpoint_every_entities
        return (
            interval > 0
            and self.batch.entities > 0
            and self.batch.entities % interval == 0
        )
