"""Deterministic static routing layer for the risk-routed hybrid Core (Stage 0).

Spec: docs/research/2026-09-19-jev-risk-routed-hybrid-core.md, sections 8, 9, 10.

This module is deliberately inert. It classifies one task state into one of three
execution tiers and returns a value. It does not call a model, does not read the
clock, does not touch the filesystem, and does not change execution. Stage 0 is
observe-only, so every decision here is shadow output that can be logged and
replayed.

Tier semantics (section 6, section 9):

* ``FAST_DEEPSEEK`` - every fast condition holds, so DeepSeek may execute directly.
* ``EXPERT_GPT``    - a hard static rule fired; the task must not be routed cheaply.
* ``UNCERTAIN``     - deterministic rules cannot decide; a model layer may evaluate it.

The layer is intentionally biased: an under-route (cheap route that later needs a
GPT rescue) costs more than an over-route (section 11), so anything not provably
safe falls through to ``UNCERTAIN`` rather than to ``FAST_DEEPSEEK``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

EXPERT_GPT = "expert_gpt"
FAST_DEEPSEEK = "fast_deepseek"
GUARDED_DEEPSEEK = "guarded_deepseek"
UNCERTAIN = "uncertain"

__all__ = [
    "EXPERT_GPT",
    "FAST_DEEPSEEK",
    "GUARDED_DEEPSEEK",
    "UNCERTAIN",
    "RouteDecision",
    "StaticPolicy",
    "route",
]


@dataclass(frozen=True)
class StaticPolicy:
    """Uncalibrated placeholder knobs.

    Section 11 forbids copying thresholds from community projects, so these are
    named, overridable placeholders rather than production values. Calibration is
    a later stage and requires labelled outcomes.
    """

    bounded_file_limit: int = 3

    #: Tier B (Guarded) requires the scope to be at least *known*.
    #:
    #: Section 6 defines Tier B as "multi-file but clearly specified". The first
    #: half is countable; the second half is a semantic judgement the static layer
    #: cannot make. A request that names no path at all leaves the layer unable to
    #: tell "multi-file" from "unknown scope", so the conservative default refuses
    #: to promote it. Setting this False adopts the broad reading of section 6, in
    #: which any task with a runnable check and no hard risk qualifies.
    guarded_requires_known_scope: bool = True


@dataclass(frozen=True)
class RouteDecision:
    """A pure routing verdict. Equality is value equality, so replay is exact."""

    tier: str
    reason: str
    matched_rules: Tuple[str, ...]

    @property
    def needs_model_evaluation(self) -> bool:
        """True only for the tier a model layer is allowed to re-evaluate."""
        return self.tier == UNCERTAIN


# Documentation paths describe a risky area without implementing one. Section 9
# is explicit that "documentation about auth should not automatically become a
# security implementation", so documentation is excluded before any risk rule runs.
_DOCUMENTATION_PATH = re.compile(
    r"(^|/)(docs?|documentation|examples?)(/|$)|\.(md|rst|txt)$",
    re.IGNORECASE,
)

# Section 9: the expert override keys on actual candidate paths, not on prose.
#
# A risk word reaches the matcher as a directory segment (``src/auth/session.py``)
# or as a single-file module (``src/auth.py``, ``src/db/transaction.py``). Both are
# the risk area the section names, so a segment may carry one source extension.
# The suffix is deliberately narrow: it accepts ``auth.py`` but rejects
# ``authentication.py`` and ``transaction_helpers.py``, which are different areas.
# Documentation is filtered before this table runs, so ``docs/auth.md`` never
# reaches it and cannot become a security implementation.
_SEGMENT_SUFFIX = r"(?:\.[a-z0-9]+)?"

_RISK_PATH_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        "security_or_credentials",
        re.compile(
            r"(^|/)(auth|authn|authz|security|credentials?|secrets?)"
            + _SEGMENT_SUFFIX
            + r"(/|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "migration_or_shared_contract",
        re.compile(r"(^|/)(migrations?|alembic)" + _SEGMENT_SUFFIX + r"(/|$)", re.IGNORECASE),
    ),
    (
        "deployment",
        re.compile(
            r"(^|/)(deploy|deployment|infra|terraform|helm|k8s|kubernetes)"
            + _SEGMENT_SUFFIX
            + r"(/|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "payment",
        re.compile(
            r"(^|/)(payments?|billing|checkout|invoices?)" + _SEGMENT_SUFFIX + r"(/|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "transaction",
        re.compile(r"(^|/)(transactions?)" + _SEGMENT_SUFFIX + r"(/|$)", re.IGNORECASE),
    ),
)

# Section 9: explicit destructive intent is an override. Keyword mentions in the
# request are only a signal, so they are deliberately absent from this table.
_FLAG_OVERRIDES: Tuple[Tuple[str, str], ...] = (
    ("destructive", "destructive_or_irreversible"),
    ("auth", "security_or_credentials"),
    ("migration", "migration_or_shared_contract"),
    ("shared_contract", "migration_or_shared_contract"),
)


def _expert_rules(state: Mapping[str, Any]) -> Tuple[str, ...]:
    """Collect every hard static rule that fires, in a stable order."""
    repo = state.get("repo") or {}
    flags = repo.get("static_flags") or {}
    matched = []

    for flag, rule in _FLAG_OVERRIDES:
        if flags.get(flag):
            matched.append(rule)

    for path in repo.get("candidate_paths") or ():
        if not isinstance(path, str) or _DOCUMENTATION_PATH.search(path):
            continue
        for rule, pattern in _RISK_PATH_RULES:
            if pattern.search(path):
                matched.append(rule)
                break

    # De-duplicate while preserving the stable declaration order.
    return tuple(dict.fromkeys(matched))


def _fast_gate_misses(state: Mapping[str, Any], policy: StaticPolicy) -> Tuple[str, ...]:
    """Return the section 9 fast conditions that are not provably satisfied.

    Conditions 3 and 4 (no hard-risk flags, no shared-contract change) are
    enforced by the expert overrides upstream: a state that violates either has
    already returned before this gate runs.
    """
    task = state.get("task") or {}
    repo = state.get("repo") or {}
    misses = []

    files = repo.get("estimated_files")
    bounded = isinstance(files, int) and not isinstance(files, bool) and 1 <= files <= policy.bounded_file_limit
    if not bounded or not (repo.get("candidate_paths") or ()):
        misses.append("bounded_file_ownership")

    if not (task.get("acceptance_summary") or ()):
        misses.append("explicit_acceptance")

    if not (repo.get("test_commands") or ()):
        misses.append("executable_verification")

    return tuple(misses)


def _semantic_risk_rules(state: Mapping[str, Any]) -> Tuple[str, ...]:
    """Collect declared semantic risk signals (section 6 Tier C concerns).

    Section 9's path rules cannot see concurrency, material ambiguity, or unclear
    root cause. Those arrive here as declared signals instead, so they reach the
    model layer rather than being silently fast-routed.
    """
    task = state.get("task") or {}
    signals = task.get("risk_signals") or ()
    return tuple(
        f"semantic_risk:{signal}"
        for signal in signals
        if isinstance(signal, str) and signal
    )


def _guarded_gate_misses(state: Mapping[str, Any], policy: StaticPolicy) -> Tuple[str, ...]:
    """Return the section 6 Tier B conditions that are not provably satisfied.

    "No hard-risk surface" is enforced upstream by the expert overrides, so only
    the remaining conditions are checked here. The acceptance conditions mirror
    the fast gate: Tier B is a DeepSeek tier too, so it needs the same definition
    of done. Without a runnable check there is no safety net and Guarded is
    unavailable at any scope.
    """
    task = state.get("task") or {}
    repo = state.get("repo") or {}
    misses = []

    if not (task.get("acceptance_summary") or ()):
        misses.append("explicit_acceptance")

    if not (repo.get("test_commands") or ()):
        misses.append("deterministic_checks")

    if policy.guarded_requires_known_scope and not (repo.get("candidate_paths") or ()):
        misses.append("scope_known")

    return tuple(misses)


def route(state: Mapping[str, Any], policy: StaticPolicy | None = None) -> RouteDecision:
    """Classify one section 8 routing state into an execution tier.

    Pure and deterministic: the same state always yields the same decision, and
    the input mapping is never mutated.

    Precedence is: hard static override, then declared semantic risk, then the
    fast gate, then the guarded gate. A hard override wins outright. Semantic
    risk and the fast gate are both reported, so the log explains the verdict.
    """
    policy = policy or StaticPolicy()

    expert = _expert_rules(state)
    if expert:
        return RouteDecision(
            tier=EXPERT_GPT,
            reason="hard static rule fired: " + ", ".join(expert),
            matched_rules=expert,
        )

    semantic = _semantic_risk_rules(state)
    misses = _fast_gate_misses(state, policy)

    if semantic:
        detail = ", ".join(rule.split(":", 1)[1] for rule in semantic)
        reason = f"declared semantic risk: {detail}"
        rules = list(semantic)
        if misses:
            reason += "; fast conditions unmet: " + ", ".join(misses)
            rules += [f"unmet:{name}" for name in misses]
        return RouteDecision(tier=UNCERTAIN, reason=reason, matched_rules=tuple(rules))

    if not misses:
        return RouteDecision(
            tier=FAST_DEEPSEEK,
            reason="all static fast conditions hold",
            matched_rules=("static_fast",),
        )

    guarded_misses = _guarded_gate_misses(state, policy)
    if not guarded_misses:
        return RouteDecision(
            tier=GUARDED_DEEPSEEK,
            reason="section 6 tier B holds; fast conditions unmet: " + ", ".join(misses),
            matched_rules=("static_guarded",) + tuple(f"unmet:{name}" for name in misses),
        )

    reason = "fast conditions unmet: " + ", ".join(misses)
    rules = [f"unmet:{name}" for name in misses]
    if guarded_misses:
        reason += "; guarded conditions unmet: " + ", ".join(guarded_misses)
        rules += [f"unmet:{name}" for name in guarded_misses]
    return RouteDecision(tier=UNCERTAIN, reason=reason, matched_rules=tuple(rules))
