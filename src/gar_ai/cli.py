from __future__ import annotations

import argparse
import importlib
import logging
import os
from pathlib import Path
from typing import Callable

from .ai_client import OpenAICompatibleAIClient
from .controller import ControllerConfig, ControllerLoop
from .incidents import IncidentManager
from .orchestrator import Orchestrator
from .storage import JsonStateStore

REQUIRED_BRIDGE_METHODS = (
    "snapshot",
    "scan_area",
    "query_recipe",
    "query_technology",
    "act",
)


def load_bridge_factory(spec: str):
    """Load ``module:function`` and return its GameBridge instance."""
    if ":" not in spec:
        raise ValueError("bridge factory must use module:function syntax")
    module_name, function_name = spec.split(":", 1)
    if not module_name or not function_name:
        raise ValueError("bridge factory must use module:function syntax")

    module = importlib.import_module(module_name)
    factory: Callable = getattr(module, function_name)
    bridge = factory()

    missing = [
        name
        for name in REQUIRED_BRIDGE_METHODS
        if not callable(getattr(bridge, name, None))
    ]
    if missing:
        raise TypeError(
            "bridge factory returned incompatible object; missing: "
            + ", ".join(missing)
        )
    return bridge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gar-ai",
        description="Run the Factorio autonomous-agent controller loop.",
    )
    parser.add_argument(
        "--bridge-factory",
        required=True,
        help="Python factory in module:function form returning a live-probed GameBridge",
    )
    parser.add_argument(
        "--runtime-dir",
        default="runtime/live",
        help="Persistent runtime directory",
    )
    parser.add_argument("--endpoint", default=os.getenv("GAR_AI_ENDPOINT"))
    parser.add_argument("--model", default=os.getenv("GAR_AI_MODEL"))
    parser.add_argument(
        "--api-key-env",
        default="GAR_AI_API_KEY",
        help="Environment variable containing the model API key",
    )
    parser.add_argument(
        "--goal",
        default="advance the current game safely",
    )
    parser.add_argument("--heartbeat-sec", type=float, default=1.0)
    parser.add_argument("--strategic-review-sec", type=float, default=180.0)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not args.endpoint:
        raise SystemExit("--endpoint or GAR_AI_ENDPOINT is required")
    if not args.model:
        raise SystemExit("--model or GAR_AI_MODEL is required")

    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(
            f"API key environment variable is not set: {args.api_key_env}"
        )

    bridge = load_bridge_factory(args.bridge_factory)
    runtime = Path(args.runtime_dir)
    store = JsonStateStore(runtime / "state")
    incidents = IncidentManager(runtime / "incidents")
    ai = OpenAICompatibleAIClient(
        endpoint=args.endpoint,
        model=args.model,
        api_key=api_key,
    )
    orchestrator = Orchestrator(
        bridge=bridge,
        ai=ai,
        store=store,
        incidents=incidents,
        goal=args.goal,
    )
    controller = ControllerLoop(
        orchestrator,
        ControllerConfig(
            heartbeat_sec=args.heartbeat_sec,
            strategic_review_sec=args.strategic_review_sec,
        ),
    )

    try:
        controller.run_forever()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info(
            "controller shutdown requested by user"
        )
        return 0
    return 0
