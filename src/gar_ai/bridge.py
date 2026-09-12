from __future__ import annotations

from typing import Any, Mapping, Protocol

from .types import Ack


class GameBridge(Protocol):
    """Minimal bridge contract required by V0.

    Real Factorio integration should adapt the existing controller/Bridge to this
    interface. Do not guess API semantics here: each implementation must be backed
    by live contract probes.
    """

    def snapshot(self) -> dict[str, Any]: ...
    def scan_area(self, center: tuple[float, float], radius: float) -> dict[str, Any]: ...
    def query_recipe(self, name: str) -> dict[str, Any] | None: ...
    def query_technology(self, name: str) -> dict[str, Any] | None: ...
    def act(self, action: str, params: Mapping[str, Any]) -> Ack: ...
