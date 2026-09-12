from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .types import MasterPlan, TaskSpec


class JsonStateStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.task_path = self.root / "task.json"
        self.runtime_path = self.root / "task_runtime.json"
        self.plan_path = self.root / "master_plan.json"
        self.failure_path = self.root / "failure_history.json"
        self.metrics_path = self.root / "metrics.json"
        self.global_budget_path = self.root / "global_budget.json"
        self.action_history_path = self.root / "actions.jsonl"

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def save_task(self, task: TaskSpec) -> None:
        self._atomic_write(self.task_path, task.to_dict())

    def load_task(self) -> TaskSpec | None:
        if not self.task_path.exists():
            return None
        return TaskSpec.from_dict(
            json.loads(self.task_path.read_text(encoding="utf-8"))
        )

    def clear_task(self) -> None:
        self.task_path.unlink(missing_ok=True)
        self.runtime_path.unlink(missing_ok=True)

    def save_runtime(self, data: dict[str, Any]) -> None:
        self._atomic_write(self.runtime_path, data)

    def load_runtime(self) -> dict[str, Any]:
        if not self.runtime_path.exists():
            return {}
        return dict(json.loads(self.runtime_path.read_text(encoding="utf-8")))

    def save_plan(self, plan: MasterPlan) -> None:
        self._atomic_write(self.plan_path, plan.to_dict())

    def load_plan(self) -> MasterPlan:
        if not self.plan_path.exists():
            return MasterPlan()
        return MasterPlan.from_dict(
            json.loads(self.plan_path.read_text(encoding="utf-8"))
        )

    def save_failure_history(self, failures: list[dict[str, Any]]) -> None:
        self._atomic_write(self.failure_path, failures)

    def load_failure_history(self) -> list[dict[str, Any]]:
        if not self.failure_path.exists():
            return []
        data = json.loads(self.failure_path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []

    def load_metrics(self) -> dict[str, Any]:
        if not self.metrics_path.exists():
            return {
                "ai_calls": 0,
                "safe_stops": 0,
                "replans": 0,
                "incidents": 0,
            }
        return dict(json.loads(self.metrics_path.read_text(encoding="utf-8")))

    def increment_metric(self, name: str, amount: int = 1) -> None:
        metrics = self.load_metrics()
        metrics[name] = int(metrics.get(name, 0) or 0) + amount
        self._atomic_write(self.metrics_path, metrics)

    def load_global_budget(self) -> dict[str, Any]:
        if not self.global_budget_path.exists():
            return {}
        data = json.loads(self.global_budget_path.read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, dict) else {}

    def save_global_budget(self, data: dict[str, Any]) -> None:
        self._atomic_write(self.global_budget_path, data)

    def append_action(self, entry: dict[str, Any]) -> None:
        self.action_history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.action_history_path.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as fh:
            fh.write(
                json.dumps(
                    entry,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
            )
            fh.write("\n")

    def flush(self) -> None:
        """Best-effort fsync of durable runtime files on graceful shutdown."""
        paths = (
            self.task_path,
            self.runtime_path,
            self.plan_path,
            self.failure_path,
            self.metrics_path,
            self.global_budget_path,
            self.action_history_path,
        )
        for path in paths:
            if not path.exists():
                continue
            try:
                with path.open("rb") as fh:
                    os.fsync(fh.fileno())
            except OSError:
                # Shutdown flush is best-effort; already-closed atomic writes stay valid.
                continue
