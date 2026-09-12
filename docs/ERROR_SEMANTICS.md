# Error semantics

The code uses stable error codes with policy metadata: retryable, write failure history, trigger AI, and safe stop.

Core codes include `ACK_REJECTED`, `FRESH_STATE_UNVERIFIED`, `VERIFY_TIMEOUT`, `TOOL_FAILED`, `REJECTED_FOR_STRATEGY_REVIEW`, `ATOMIC_BUDGET_EXCEEDED`, `TASK_BUDGET_EXCEEDED`, `BATCH_BUDGET_EXCEEDED`, `GLOBAL_BUDGET_EXCEEDED`, `REPLAN_BUDGET_EXCEEDED`, `STALE_STATE`, `AREA_LOCK_CONFLICT`, `MATERIAL_RESERVATION_FAILED`, `SCHEMA_INCOMPATIBLE`, `UNKNOWN_ABORT_PATH`, and `SAFE_STOP`.

Tool outcomes are separate from error codes: `verified`, `noop`, `pending`, `unverified`, `blocked`, `timeout`, `failed`, `rejected_for_strategy_review`.
