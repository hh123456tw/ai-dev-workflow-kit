"""Command-line entry point for the static routing layer.

A launcher needs to ask one question -- "which tier is this task?" -- and get an
answer it can act on. This module answers it, and owns the tier-to-model mapping
so the mapping is testable in Python rather than buried in a shell script.

It is read-only. It reads a request file and a repository, prints a decision, and
exits. It writes nothing, and it never contacts a network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from router.state_builder import build_state
from router.static_router import (
    EXPERT_GPT,
    FAST_DEEPSEEK,
    GUARDED_DEEPSEEK,
    UNCERTAIN,
    StaticPolicy,
    route,
)

#: Which model each tier selects. The two DeepSeek tiers share a model because
#: the difference between them is execution policy, not the model: Guarded runs
#: the same workhorse under strict verification and a mandatory reviewer.
TIER_MODEL: Dict[str, str] = {
    FAST_DEEPSEEK: "deepseek/deepseek-v4-flash",
    GUARDED_DEEPSEEK: "deepseek/deepseek-v4-flash",
    UNCERTAIN: "openai/gpt-5.6-sol",
    EXPERT_GPT: "openai/gpt-5.6-sol",
}

#: The conservative reading of section 6's "clearly specified" is the default.
TIER_B_POLICIES = {
    "conservative": StaticPolicy(guarded_requires_known_scope=True),
    "broad": StaticPolicy(guarded_requires_known_scope=False),
}

__all__ = ["TIER_MODEL", "TIER_B_POLICIES", "build_parser", "decide", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m router.cli",
        description="Classify one task into an execution tier (read-only).",
    )
    parser.add_argument("--request-file", required=True, help="Path to the request text.")
    parser.add_argument("--repo", required=True, help="Repository the task will touch.")
    parser.add_argument(
        "--tier-b",
        choices=sorted(TIER_B_POLICIES),
        default="conservative",
        help="Reading of section 6's 'clearly specified' for the Guarded tier.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full decision instead of just the tier.",
    )
    return parser


def decide(request_file: str, repo: str, tier_b: str = "conservative") -> Dict[str, Any]:
    """Return the routing decision for one request. Pure apart from reading files."""
    request = Path(request_file).read_text(encoding="utf-8", errors="replace")
    state = build_state(request, repo)
    decision = route(state, TIER_B_POLICIES[tier_b])
    return {
        "tier": decision.tier,
        "model": TIER_MODEL[decision.tier],
        "reason": decision.reason,
        "rules": list(decision.matched_rules),
        "risk_signals": list(state["task"]["risk_signals"]),
        "candidate_paths": list(state["repo"]["candidate_paths"]),
        "test_commands": list(state["repo"]["test_commands"]),
        "tier_b_policy": tier_b,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = decide(args.request_file, args.repo, args.tier_b)
    except FileNotFoundError as error:
        print(f"router: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(result["tier"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
