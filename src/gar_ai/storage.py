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

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)

    def save_task(self, task: TaskSpec) -> None:
        self._atomic_write(self.task_path, task.to_dict())

    def load_task(self) -> TaskSpec | None:
        if not self.task_path.exists():
            return None
        return TaskSpec.from_dict(json.loads(self.task_path.read_text(encoding="utf-8")))

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
        return MasterPlan.from_dict(json.loads(self.plan_path.read_text(encoding="utf-8")))

    def save_failure_history(self, failures: list[dict[str, Any]]) -> None:
        self._atomic_write(self.failure_path, failures)

    def load_failure_history(self) -> list[dict[str, Any]]:
        if not self.failure_path.exists():
            return []
        data = json.loads(self.failure_path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
