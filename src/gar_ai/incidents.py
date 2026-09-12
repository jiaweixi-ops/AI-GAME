from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class IncidentManager:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")

    @staticmethod
    def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)); fh.write("\n")

    def create(self, reason: str, *, digest: Mapping[str, Any], task: Mapping[str, Any] | None, master_plan: Mapping[str, Any], actions: list[Mapping[str, Any]], failures: list[Mapping[str, Any]], nearby_state: Mapping[str, Any] | None, budget: Mapping[str, Any]) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in reason)[:80]
        path = self.root / f"{stamp}_{safe_reason}"; suffix = 1
        while path.exists():
            suffix += 1; path = self.root / f"{stamp}_{safe_reason}_{suffix}"
        path.mkdir(parents=True)
        self._write(path / "digest.json", digest); self._write(path / "task.json", task); self._write(path / "master_plan.json", master_plan)
        self._write_jsonl(path / "actions.jsonl", actions)
        self._write(path / "failures.json", failures); self._write(path / "nearby_state.json", nearby_state); self._write(path / "budget.json", budget)
        return path
