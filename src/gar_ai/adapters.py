from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .types import Ack


@dataclass(slots=True)
class BridgeCallbacks:
    snapshot: Callable[[], dict[str, Any]]
    scan_area: Callable[[tuple[float, float], float], dict[str, Any]]
    query_recipe: Callable[[str], dict[str, Any] | None]
    query_technology: Callable[[str], dict[str, Any] | None]
    act: Callable[[str, Mapping[str, Any]], Ack]


class CallbackBridgeAdapter:
    """Adapter for wiring an existing Factorio controller without guessing its API.

    The caller supplies five already-live-probed callbacks. This keeps the V0
    kernel independent from repository-specific controller signatures.
    """

    def __init__(self, callbacks: BridgeCallbacks) -> None:
        self._cb = callbacks

    def snapshot(self) -> dict[str, Any]: return self._cb.snapshot()
    def scan_area(self, center: tuple[float, float], radius: float) -> dict[str, Any]: return self._cb.scan_area(center, radius)
    def query_recipe(self, name: str) -> dict[str, Any] | None: return self._cb.query_recipe(name)
    def query_technology(self, name: str) -> dict[str, Any] | None: return self._cb.query_technology(name)
    def act(self, action: str, params: Mapping[str, Any]) -> Ack: return self._cb.act(action, params)
