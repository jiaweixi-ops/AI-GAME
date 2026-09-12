from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from .async_verify import (
    AsyncVerificationSpec,
    AsyncVerificationStatus,
    AsyncVerifier,
    PendingVerification,
)
from .batch_budget import BatchBudgetContext
from .blueprint_ir import BlueprintIR
from .coordination import (
    AreaLockConflict,
    AreaLockManager,
    MaterialReservationError,
    MaterialReservationManager,
)
from .errors import ErrorCode
from .failure_fingerprint import FailureFingerprint, FailureFingerprintStore
from .journal import JournalEntry, OperationJournal
from .metrics import MetricsRecorder, ProgressKind


class ToolResultLike(Protocol):
    ok: bool
    changed: bool
    reason: str | None
    error_code: str | None


class ToolSurfaceLike(Protocol):
    def call(self, tool: str, args: dict[str, Any]) -> ToolResultLike: ...


@dataclass(slots=True)
class BatchExecutionResult:
    status: str
    phase: str
    placed: int
    total: int
    reason: str | None = None
    error_code: str | None = None
    pending: PendingVerification | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "completed"


class BatchExecutor:
    def __init__(
        self,
        *,
        surface: ToolSurfaceLike,
        batch_budget: BatchBudgetContext,
        area_locks: AreaLockManager,
        reservations: MaterialReservationManager,
        journal: OperationJournal,
        snapshot: Callable[[], Mapping[str, Any]],
        metrics: MetricsRecorder | None = None,
        async_verifier: AsyncVerifier | None = None,
        failure_store: FailureFingerprintStore | None = None,
        environment_summary: (
            Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
        ) = None,
    ) -> None:
        self.surface = surface
        self.batch_budget = batch_budget
        self.area_locks = area_locks
        self.reservations = reservations
        self.journal = journal
        self.snapshot = snapshot
        self.metrics = metrics
        self.async_verifier = async_verifier or AsyncVerifier(snapshot)
        self.failure_store = failure_store
        self.environment_summary = environment_summary or (
            lambda state: {
                "game_tick": state.get("game_tick"),
                "power": state.get("power"),
                "threat": state.get("threat"),
            }
        )

        surface_budget = getattr(surface, "budget", None)
        if surface_budget is not None and surface_budget is not batch_budget:
            raise ValueError("surface must use the same BatchBudgetContext")

    def _available_inventory(self) -> dict[str, int]:
        inventory = (
            (self.snapshot().get("player") or {}).get("inventory") or {}
        )
        return {
            str(key): int(value or 0)
            for key, value in dict(inventory).items()
        }

    def prepare(
        self,
        *,
        task_id: str,
        batch_id: str,
        ir: BlueprintIR,
        lock_ttl_sec: float | None = None,
    ) -> None:
        ir.validate()
        lock_id = f"area:{batch_id}"
        reservation_id = f"materials:{batch_id}"

        self.area_locks.acquire(
            lock_id=lock_id,
            task_id=task_id,
            footprint=ir.footprint,
            ttl_sec=lock_ttl_sec,
        )

        try:
            self.reservations.reserve(
                reservation_id=reservation_id,
                task_id=task_id,
                requested=ir.required_items,
                available=self._available_inventory(),
            )
        except Exception:
            self.area_locks.release(lock_id, task_id=task_id)
            raise

        self.journal.append(
            JournalEntry.create(
                task_id=task_id,
                batch_id=batch_id,
                operation_id="prepare",
                phase="prepare",
                status="committed",
                side_effect="reservation",
                detail={
                    "footprint": ir.footprint.to_dict(),
                    "required_items": ir.required_items,
                },
            )
        )

    def _abort(
        self,
        *,
        task_id: str,
        batch_id: str,
        phase: str,
        placed: int,
        total: int,
        reason: str,
        error_code: str,
    ) -> BatchExecutionResult:
        reservation_id = f"materials:{batch_id}"
        reservation = self.reservations.get(reservation_id)
        released = (
            self.reservations.release(reservation_id)
            if reservation is not None
            else {}
        )
        self.area_locks.release(f"area:{batch_id}", task_id=task_id)

        self.journal.append(
            JournalEntry.create(
                task_id=task_id,
                batch_id=batch_id,
                operation_id=f"abort:{placed}",
                phase=phase,
                status="aborted",
                side_effect="partial_construction",
                detail={
                    "reason": reason,
                    "error_code": error_code,
                    "released": released,
                    "placed": placed,
                    "total": total,
                },
            )
        )

        return BatchExecutionResult(
            "partial",
            phase,
            placed,
            total,
            reason,
            error_code,
            evidence={"released": released},
        )

    def execute_placements(
        self,
        *,
        task_id: str,
        batch_id: str,
        ir: BlueprintIR,
        checkpoint: Callable[[Mapping[str, Any], int, int], bool] | None = None,
    ) -> BatchExecutionResult:
        total = len(ir.entities)
        placed = 0
        reservation_id = f"materials:{batch_id}"

        if self.reservations.get(reservation_id) is None:
            try:
                self.prepare(task_id=task_id, batch_id=batch_id, ir=ir)
            except AreaLockConflict as exc:
                return BatchExecutionResult(
                    "blocked",
                    "prepare",
                    0,
                    total,
                    str(exc),
                    ErrorCode.AREA_LOCK_CONFLICT.value,
                )
            except MaterialReservationError as exc:
                return BatchExecutionResult(
                    "blocked",
                    "prepare",
                    0,
                    total,
                    str(exc),
                    ErrorCode.MATERIAL_RESERVATION_FAILED.value,
                )

        if self.metrics:
            self.metrics.state.batches_attempted += 1
            self.metrics._save()

        for index, entity in enumerate(ir.entities):
            operation_id = f"place:{entity.entity_id}"
            self.journal.append(
                JournalEntry.create(
                    task_id=task_id,
                    batch_id=batch_id,
                    operation_id=operation_id,
                    phase="construction",
                    status="started",
                    side_effect="place_entity",
                    detail={
                        "entity": entity.name,
                        "position": [entity.x, entity.y],
                    },
                )
            )

            try:
                result = self.surface.call(
                    "place_verified",
                    entity.to_tool_args(),
                )
            except Exception as exc:
                return self._abort(
                    task_id=task_id,
                    batch_id=batch_id,
                    phase="construction",
                    placed=placed,
                    total=total,
                    reason=str(exc),
                    error_code=getattr(
                        exc,
                        "code",
                        ErrorCode.BATCH_BUDGET_EXCEEDED.value,
                    ),
                )

            if not result.ok:
                try:
                    self.batch_budget.record_failure()
                except Exception:
                    pass

                fingerprint = None
                if self.failure_store is not None:
                    recorded = self.failure_store.record(
                        FailureFingerprint.build(
                            task_id=task_id,
                            task_type=ir.module_type,
                            tool="place_verified",
                            target=entity.name,
                            position=[entity.x, entity.y],
                            environment=self.environment_summary(
                                self.snapshot()
                            ),
                            reason_code=(
                                result.error_code
                                or ErrorCode.TOOL_FAILED.value
                            ),
                            evidence={"reason": result.reason},
                        )
                    )
                    fingerprint = recorded.fingerprint

                outcome = self._abort(
                    task_id=task_id,
                    batch_id=batch_id,
                    phase="construction",
                    placed=placed,
                    total=total,
                    reason=result.reason or "placement failed",
                    error_code=(
                        result.error_code or ErrorCode.TOOL_FAILED.value
                    ),
                )
                if fingerprint:
                    outcome.evidence["failure_fingerprint"] = fingerprint
                return outcome

            if result.changed:
                self.reservations.consume(
                    reservation_id,
                    entity.name,
                    1,
                )
                placed += 1
                if self.metrics:
                    self.metrics.record_progress(ProgressKind.ENTITY)

            self.journal.append(
                JournalEntry.create(
                    task_id=task_id,
                    batch_id=batch_id,
                    operation_id=operation_id,
                    phase="construction",
                    status="committed",
                    side_effect="place_entity",
                    detail={"changed": bool(result.changed)},
                )
            )

            if (
                self.batch_budget.checkpoint_due()
                and checkpoint is not None
                and not checkpoint(self.snapshot(), index + 1, total)
            ):
                return self._abort(
                    task_id=task_id,
                    batch_id=batch_id,
                    phase="checkpoint",
                    placed=placed,
                    total=total,
                    reason="checkpoint verification failed",
                    error_code=ErrorCode.FRESH_STATE_UNVERIFIED.value,
                )

        return BatchExecutionResult(
            "constructed",
            "construction",
            placed,
            total,
        )

    def begin_final_verification(
        self,
        *,
        spec: AsyncVerificationSpec,
    ) -> PendingVerification:
        return self.async_verifier.start(spec)

    def poll_final_verification(
        self,
        *,
        task_id: str,
        batch_id: str,
        pending: PendingVerification,
        predicate,
    ) -> BatchExecutionResult:
        pending = self.async_verifier.poll_once(pending, predicate)

        if pending.status is AsyncVerificationStatus.PENDING:
            return BatchExecutionResult(
                "pending",
                "verify",
                0,
                0,
                pending=pending,
                evidence=pending.evidence,
            )

        if pending.status is AsyncVerificationStatus.VERIFIED:
            self.reservations.release(f"materials:{batch_id}")
            self.area_locks.release(
                f"area:{batch_id}",
                task_id=task_id,
            )
            self.journal.append(
                JournalEntry.create(
                    task_id=task_id,
                    batch_id=batch_id,
                    operation_id="verify:final",
                    phase="verify",
                    status="committed",
                    side_effect="none",
                    detail=pending.evidence,
                )
            )
            if self.metrics:
                self.metrics.state.batches_completed += 1
                self.metrics._save()
                self.metrics.record_progress(ProgressKind.PRODUCTION)

            return BatchExecutionResult(
                "completed",
                "verify",
                0,
                0,
                evidence=pending.evidence,
            )

        return self._abort(
            task_id=task_id,
            batch_id=batch_id,
            phase="verify",
            placed=0,
            total=0,
            reason=f"final verification {pending.status.value}",
            error_code=(
                ErrorCode.VERIFY_TIMEOUT.value
                if pending.status is AsyncVerificationStatus.TIMEOUT
                else ErrorCode.TOOL_FAILED.value
            ),
        )


def smelting_operational_predicate(
    ir: BlueprintIR,
    *,
    min_product_rate: float,
    min_power_margin: float | None = None,
):
    """Return the V0.5 final operational verification predicate.

    A positive output-rate threshold is mandatory. A constructed layout is not
    considered operational merely because its entities exist.
    """
    if min_product_rate <= 0:
        raise ValueError("min_product_rate must be > 0")

    targets = {
        (entity.name, round(entity.x, 2), round(entity.y, 2))
        for entity in ir.entities
    }
    product = str(ir.metadata.get("product", ""))
    if not product:
        raise ValueError("BlueprintIR metadata.product is required")

    def predicate(snapshot):
        actual = {
            (
                str(entity.get("name")),
                round(
                    float((entity.get("position") or [0, 0])[0]),
                    2,
                ),
                round(
                    float((entity.get("position") or [0, 0])[1]),
                    2,
                ),
            )
            for entity in snapshot.get("entities", []) or []
        }
        built = len(targets & actual)
        margin = (snapshot.get("power") or {}).get("margin")
        rate = (snapshot.get("production") or {}).get(product)

        power_ok = (
            min_power_margin is None
            or (
                margin is not None
                and float(margin) >= min_power_margin
            )
        )
        production_ok = (
            rate is not None and float(rate) >= min_product_rate
        )
        ok = built == len(targets) and power_ok and production_ok

        return ok, {
            "built": built,
            "expected": len(targets),
            "power_margin": margin,
            "product": product,
            "product_rate": rate,
            "min_product_rate": min_product_rate,
        }

    return predicate
