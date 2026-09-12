from pathlib import Path
import shutil

from gar_ai.ai_client import ScriptedAIClient
from gar_ai.incidents import IncidentManager
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.orchestrator import Orchestrator
from gar_ai.storage import JsonStateStore
from gar_ai.watchdog import Watchdog, WatchdogConfig

ROOT = Path("runtime/demo_v0")
shutil.rmtree(ROOT, ignore_errors=True)
bridge = InMemoryBridge()
bridge.state["entities"].append({"name": "lab", "position": [5.0, 5.0], "inventory": {}, "recipe": None})
bridge.state["research"].update({"technology": "automation", "progress": 0.20, "unit_count": 10, "science_supply": {}, "state": "starved"})
ai = ScriptedAIClient([{"decision": "create_task", "reason": "research is starved", "plan_patch": {"current": "restore research", "next": "continue automation", "watch": ["research"]}, "task": {"task_id": "restore-research-demo", "objective": "restore research progress", "reason": "science supply is empty", "desired_state": {"research.state": "progressing"}, "operations": [{"tool": "ensure_item_verified", "args": {"item": "automation-science-pack", "count": 3}}, {"tool": "transfer_verified", "args": {"item": "automation-science-pack", "x": 5, "y": 5, "target_count": 3}}], "success_when": [{"path": "research.state", "op": "eq", "value": "progressing"}], "abort_if": []}}])
orchestrator = Orchestrator(bridge=bridge, ai=ai, store=JsonStateStore(ROOT / "state"), incidents=IncidentManager(ROOT / "incidents"), watchdog=Watchdog(WatchdogConfig(no_progress_sec=999)))
result = orchestrator.tick(trigger="startup")
print("orchestrator:", result.status)
print("research:", bridge.snapshot()["research"])
