from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .types import Decision

logger = logging.getLogger(__name__)


class AIClient(Protocol):
    def decide(self, *, digest: Mapping[str, Any], master_plan: Mapping[str, Any], failure_history: list[Mapping[str, Any]], allowed_tools: list[str], trigger: str) -> Decision: ...


SYSTEM_PROMPT = """You are the strategic planner for a Factorio automation controller.
You are NOT a tick-loop and you do not directly control the bridge.
Game facts in the digest/query results override your memory.
Choose the smallest useful next task. Do not repeat recovery methods already proven to fail.
A task must describe desired state and a bounded sequence of allowed verified tools.
Every create_task MUST include at least one success_when condition.
Use dot-separated snapshot paths in desired_state and conditions, e.g. research.state.
Do not output prose. Output one JSON object only.
"""


class DecisionValidationError(ValueError):
    pass


def validate_decision(decision: Decision, allowed_tools: list[str]) -> Decision:
    if decision.decision == "create_task":
        if decision.task is None:
            raise DecisionValidationError("create_task missing task")
        if not decision.task.operations:
            raise DecisionValidationError("V0 create_task requires at least one operation")
        if not decision.task.success_when:
            raise DecisionValidationError("V0 create_task requires at least one success_when condition")
        for call in decision.task.operations:
            if call.tool not in allowed_tools:
                raise DecisionValidationError(f"tool not allowed: {call.tool}")
    return decision


def _extract_json_payload(data: Any) -> Mapping[str, Any]:
    if isinstance(data, Mapping) and "decision" in data: return data
    if isinstance(data, Mapping) and isinstance(data.get("output"), Mapping) and "decision" in data["output"]: return data["output"]
    if isinstance(data, Mapping):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
            content = message.get("content") if isinstance(message, Mapping) else None
            if isinstance(content, str):
                parsed = json.loads(content)
                if isinstance(parsed, Mapping): return parsed
    raise DecisionValidationError("AI response does not contain a decision object")


class OpenAICompatibleAIClient:
    def __init__(self, *, endpoint: str, model: str, api_key: str, timeout_sec: float = 60.0, max_output_tokens: int = 1500, extra_headers: Mapping[str, str] | None = None) -> None:
        if not endpoint or not model or not api_key: raise ValueError("endpoint, model and api_key are required")
        self.endpoint = endpoint; self.model = model; self.api_key = api_key; self.timeout_sec = timeout_sec; self.max_output_tokens = max_output_tokens; self.extra_headers = dict(extra_headers or {})

    def decide(self, *, digest: Mapping[str, Any], master_plan: Mapping[str, Any], failure_history: list[Mapping[str, Any]], allowed_tools: list[str], trigger: str) -> Decision:
        user_payload = {"trigger": trigger, "digest": digest, "master_plan": master_plan, "failure_history": failure_history[-20:], "allowed_tools": allowed_tools}
        body = {"model": self.model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}], "temperature": 0.1, "max_tokens": self.max_output_tokens, "response_format": {"type": "json_object"}}
        request = urllib.request.Request(self.endpoint, data=json.dumps(body).encode("utf-8"), method="POST", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", **self.extra_headers})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response: raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.exception("AI API request failed"); raise RuntimeError(f"AI API request failed: {exc}") from exc
        return validate_decision(Decision.from_dict(_extract_json_payload(json.loads(raw))), allowed_tools)


@dataclass(slots=True)
class ScriptedAIClient:
    decisions: list[Mapping[str, Any] | Exception]
    calls: int = 0

    def decide(self, *, digest: Mapping[str, Any], master_plan: Mapping[str, Any], failure_history: list[Mapping[str, Any]], allowed_tools: list[str], trigger: str) -> Decision:
        if self.calls >= len(self.decisions): return Decision(decision="safe_stop", reason="script exhausted")
        payload = self.decisions[self.calls]; self.calls += 1
        if isinstance(payload, Exception): raise payload
        return validate_decision(Decision.from_dict(payload), allowed_tools)
