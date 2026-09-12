"""Factorio Autonomous Agent Lite V0 kernel."""

from .ai_client import AIClient, OpenAICompatibleAIClient, ScriptedAIClient
from .budget import AtomicBudgetLimits, BudgetContext, BudgetExceeded, TaskBudgetLimits
from .digest import StateDigestBuilder
from .incidents import IncidentManager
from .keeper import Keeper, KeeperPolicy
from .orchestrator import Orchestrator
from .storage import JsonStateStore
from .types import Decision, MasterPlan, TaskSpec, ToolOutcome, ToolResult
from .verified_tools import VerifiedToolSurface
from .watchdog import Watchdog, WatchdogConfig

__all__ = [
    "AIClient",
    "OpenAICompatibleAIClient",
    "ScriptedAIClient",
    "AtomicBudgetLimits",
    "BudgetContext",
    "BudgetExceeded",
    "TaskBudgetLimits",
    "StateDigestBuilder",
    "IncidentManager",
    "Keeper",
    "KeeperPolicy",
    "Orchestrator",
    "JsonStateStore",
    "Decision",
    "MasterPlan",
    "TaskSpec",
    "ToolOutcome",
    "ToolResult",
    "VerifiedToolSurface",
    "Watchdog",
    "WatchdogConfig",
]
