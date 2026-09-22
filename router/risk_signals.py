"""Deterministic semantic risk signals for the routing state.

Spec: docs/research/2026-09-19-jev-risk-routed-hybrid-core.md, sections 6 and 9.

Section 6 places concurrency, material ambiguity, and unclear root cause in Tier C.
Section 9's fast gate can only see candidate paths and declared flags, so those
semantic risks have no channel into the decision. Benchmark task C08 is the proof:
a genuine concurrency bug, in two innocuous files, with frozen acceptance and
executable checks, routed straight to the fast tier.

This module is that channel. It is a pure, model-free scan of the request text.
It exists so a semantic risk can reach the model layer instead of being silently
under-routed, which section 11 calls the expensive direction.

Vocabulary is deliberately small and technical, and it is a calibration target,
not a tuned value. Note that the C08 request never contains the word
"concurrency": its signal words are starvation, scheduling, coalesced, and races.
A scanner keyed on category names would miss the task that motivated the module.
"""

from __future__ import annotations

import re
from typing import Iterable, Tuple

#: Signal names, in the stable order they are reported.
SIGNALS: Tuple[str, ...] = (
    "concurrency",
    "ambiguous_requirements",
    "unclear_root_cause",
)

#: Contract signal names. These route differently from :data:`SIGNALS`: section 9
#: makes a shared-contract change a hard expert override, not a deferral to a
#: model. They are kept separate so the two classes cannot be conflated.
CONTRACT_SIGNALS: Tuple[str, ...] = ("public_interface",)

_MARKERS: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        "concurrency",
        re.compile(
            r"concurren"
            r"|starv"
            r"|deadlock"
            r"|\brace(s)?\b"
            r"|interleav"
            r"|thread[-\s]?safe"
            r"|coalesc"
            r"|backpressure"
            r"|non-?deterministic"
            r"|schedul"
            r"|\batomic\b"
            r"|lock contention"
            r"|queue drain",
            re.IGNORECASE,
        ),
    ),
    (
        "ambiguous_requirements",
        re.compile(
            r"ambiguous"
            r"|unspecified"
            r"|unclear (which|what|whether|how|if)"
            r"|multiple interpretations"
            r"|figure out (which|what|how)",
            re.IGNORECASE,
        ),
    ),
    (
        "unclear_root_cause",
        re.compile(
            r"flaky"
            r"|intermittent"
            r"|root cause"
            r"|unreproducible"
            r"|not reproducible"
            r"|why does",
            re.IGNORECASE,
        ),
    ),
)

__all__ = ["CONTRACT_SIGNALS", "SIGNALS", "scan_contract_signals", "scan_risk_signals"]


#: Markers for a change to a public or shared contract. Section 9 treats this as
#: an expert override, so the vocabulary is narrower than the semantic one: a
#: false positive sends work to GPT, which is the safe direction but wasteful.
#: A bare "interface" is deliberately absent, because it is an ordinary word.
_CONTRACT_MARKERS: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        "public_interface",
        re.compile(
            r"public (api|interface|contract)"
            r"|documented (standard )?interface"
            r"|breaking change"
            r"|backward(s)? compat"
            r"|shared (schema|contract|state)"
            r"|wire format"
            r"|plugin (api|interface)",
            re.IGNORECASE,
        ),
    ),
)


def _scan(text: str, table: Tuple[Tuple[str, re.Pattern], ...], names: Tuple[str, ...]) -> Tuple[str, ...]:
    if not text or not text.strip():
        return ()
    found = {name for name, pattern in table if pattern.search(text)}
    return tuple(name for name in names if name in found)


def scan_risk_signals(text: str, vocabulary: Iterable[Tuple[str, re.Pattern]] | None = None) -> Tuple[str, ...]:
    """Return the semantic risk signals present in ``text``, in :data:`SIGNALS` order.

    Pure and deterministic: the same text always yields the same tuple, and the
    result never depends on match order within the text.
    """
    table = tuple(vocabulary) if vocabulary is not None else _MARKERS
    return _scan(text, table, SIGNALS)


def scan_contract_signals(text: str, vocabulary: Iterable[Tuple[str, re.Pattern]] | None = None) -> Tuple[str, ...]:
    """Return the public/shared contract signals present in ``text``.

    These are expert overrides, not deferrals, so they are reported separately
    from :func:`scan_risk_signals`.
    """
    table = tuple(vocabulary) if vocabulary is not None else _CONTRACT_MARKERS
    return _scan(text, table, CONTRACT_SIGNALS)
