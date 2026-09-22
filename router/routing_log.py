"""Append-only routing decision log (section 17 of the risk-routed Core spec).

Section 17 requires an append-only local JSONL record of every routing decision,
and forbids writing source, secrets, credentials, hidden tests, raw prompts, or
full tool output.

That prohibition is enforced by projection, not by filtering: the log is written
through :data:`APPROVED_FIELDS`, an allow-list. A key that is not on the list is
dropped, so an unanticipated sensitive field cannot leak by default. A blocklist
would fail open on the first key nobody thought of.

Stage 0 is observe-only. This module writes decisions; it never influences one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Union

#: Metadata that may be written to the routing log.
#:
#: Section 17 fields plus the deterministic static-layer extension that Stage 0
#: needs. Content is never approved: there is no field here that carries source,
#: prompts, tool output, transcripts, or credentials.
APPROVED_FIELDS = frozenset(
    {
        # provenance
        "task_id",
        "timestamp",
        "policy_version",
        "question_pack_hash",
        # inputs (metadata only)
        "language",
        "static_risk",
        "risk_signals",
        # deterministic static layer
        "static_decision",
        "static_rules",
        "static_reason",
        # model layer (unused until a later stage)
        "jev_model",
        "jev_decision",
        "confidence",
        "jev_latency_ms",
        # routing outcome
        "predicted_route",
        "actual_route",
        "final_models",
        "escalated",
        "fallback_reason",
        # task outcome
        "public_pass",
        "hidden_pass",
        "time_to_green_s",
        "gpt_input_tokens",
        "gpt_output_tokens",
        # dry-run provenance
        "source",
        "derivation",
    }
)

__all__ = ["APPROVED_FIELDS", "append_entry", "build_entry", "read_entries"]


def build_entry(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Project ``raw`` onto :data:`APPROVED_FIELDS`.

    Unapproved keys are dropped. The input mapping is never mutated.
    """
    return {key: value for key, value in raw.items() if key in APPROVED_FIELDS}


def append_entry(path: Union[str, Path], entry: Mapping[str, Any]) -> None:
    """Append one decision to the JSONL log.

    Raises ``ValueError`` if ``entry`` carries an unapproved key. The check runs
    before the file is touched, so a rejected entry leaves no partial line and
    does not create the log.
    """
    unapproved = sorted(set(entry) - APPROVED_FIELDS)
    if unapproved:
        raise ValueError(
            "refusing to write unapproved routing-log fields: " + ", ".join(unapproved)
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(entry), ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_entries(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Read every logged entry. A missing log is an empty log."""
    path = Path(path)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
