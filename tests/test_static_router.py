"""Acceptance tests for the deterministic static routing layer.

Spec: docs/research/2026-09-19-jev-risk-routed-hybrid-core.md, sections 8, 9, 10.

This layer is Stage 0 of the risk-routed hybrid Core: it classifies and (in a
later slice) logs only. It never changes execution, never calls a model, and
never performs a side effect. Every rule below is deterministic, so the same
state must always produce the same decision.

The state shape is the section 8 routing state contract, verbatim.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.static_router import (  # noqa: E402
    EXPERT_GPT,
    FAST_DEEPSEEK,
    GUARDED_DEEPSEEK,
    UNCERTAIN,
    StaticPolicy,
    route,
)


def make_state(
    *,
    paths=(),
    files=1,
    acceptance=("pytest tests/test_x.py -q",),
    test_commands=("pytest",),
    flags=None,
    risk_signals=(),
    request="Add a bounded helper to an existing module.",
    language="en",
):
    """Build a section 8 routing state contract, defaulting to an obvious-fast task."""
    return {
        "task": {
            "request": request,
            "language": language,
            "acceptance_summary": list(acceptance),
            "risk_signals": list(risk_signals),
        },
        "repo": {
            "project_type": "python",
            "candidate_paths": list(paths),
            "estimated_files": files,
            "test_commands": list(test_commands),
            "static_flags": {
                "auth": False,
                "migration": False,
                "shared_contract": False,
                "destructive": False,
                **(flags or {}),
            },
        },
    }


class StaticOverrideTest(unittest.TestCase):
    """Section 9: hard static overrides are absolute and beat every fast condition."""

    def test_destructive_flag_overrides_to_expert(self) -> None:
        decision = route(make_state(flags={"destructive": True}))
        self.assertEqual(decision.tier, EXPERT_GPT)
        self.assertIn("destructive", " ".join(decision.matched_rules))

    def test_auth_flag_overrides_to_expert(self) -> None:
        self.assertEqual(route(make_state(flags={"auth": True})).tier, EXPERT_GPT)

    def test_migration_flag_overrides_to_expert(self) -> None:
        self.assertEqual(route(make_state(flags={"migration": True})).tier, EXPERT_GPT)

    def test_shared_contract_flag_overrides_to_expert(self) -> None:
        self.assertEqual(route(make_state(flags={"shared_contract": True})).tier, EXPERT_GPT)

    def test_risk_paths_override_to_expert(self) -> None:
        cases = {
            "src/auth/session.py": "auth directory",
            "src/security/policy.py": "security directory",
            "db/migrations/0001_init.py": "migration directory",
            "infra/terraform/main.tf": "deployment directory",
            "src/payments/stripe_gateway.py": "payment directory",
            "src/auth.py": "auth module file",
            "src/security.py": "security module file",
            "src/db/transaction.py": "transaction module file",
            "app/payments.py": "payment module file",
        }
        for path, label in cases.items():
            with self.subTest(path=path):
                decision = route(make_state(paths=[path]))
                self.assertEqual(
                    decision.tier,
                    EXPERT_GPT,
                    f"{label} path {path} must override to expert, got {decision.tier}",
                )

    def test_risk_word_matching_is_narrow(self) -> None:
        """A word that merely starts with a risk word is a different area."""
        for path in (
            "src/authentication.py",
            "src/transaction_helpers.py",
            "src/authors.py",
            "src/deployment_notes_util.py",
        ):
            with self.subTest(path=path):
                self.assertNotEqual(
                    route(make_state(paths=[path])).tier,
                    EXPERT_GPT,
                    f"{path} is not in a named risk area",
                )

    def test_hard_override_beats_every_fast_condition(self) -> None:
        """A task that satisfies all five fast conditions is still expert if it is risky."""
        decision = route(
            make_state(
                paths=["src/auth/token.py"],
                files=1,
                acceptance=("pytest -q",),
                test_commands=("pytest",),
            )
        )
        self.assertEqual(decision.tier, EXPERT_GPT)

    def test_documentation_about_a_risky_area_is_not_a_risky_implementation(self) -> None:
        """Section 9: documentation about auth must not become a security implementation."""
        for path in ("docs/auth.md", "docs/migrations.md", "README.md", "docs/security.md"):
            with self.subTest(path=path):
                decision = route(make_state(paths=[path]))
                self.assertNotEqual(
                    decision.tier,
                    EXPERT_GPT,
                    f"{path} is documentation, not a risky implementation",
                )

    def test_documentation_does_not_mask_a_risky_sibling_path(self) -> None:
        """A doc path must not launder a risky implementation in the same task."""
        decision = route(make_state(paths=["docs/auth.md", "src/auth/token.py"]))
        self.assertEqual(decision.tier, EXPERT_GPT)
        self.assertIn("security_or_credentials", decision.matched_rules)

    def test_request_keywords_are_signals_not_proof(self) -> None:
        """Section 9: keyword mentions alone must not trigger a hard override."""
        decision = route(
            make_state(
                paths=["src/util.py"],
                request="Document how the auth layer works in a comment.",
            )
        )
        self.assertNotEqual(
            decision.tier,
            EXPERT_GPT,
            "a keyword mention without a risk path or flag is a signal, not proof",
        )


class FastGateTest(unittest.TestCase):
    """Section 9: static Fast requires all five conditions at once."""

    def test_all_five_conditions_route_fast(self) -> None:
        decision = route(make_state(paths=["src/util.py"], files=1))
        self.assertEqual(decision.tier, FAST_DEEPSEEK)

    def test_missing_explicit_acceptance_is_not_fast(self) -> None:
        self.assertEqual(route(make_state(paths=["src/util.py"], acceptance=())).tier, UNCERTAIN)

    def test_missing_executable_verification_is_not_fast(self) -> None:
        self.assertEqual(
            route(make_state(paths=["src/util.py"], test_commands=())).tier,
            UNCERTAIN,
        )

    def test_unbounded_file_ownership_is_not_fast(self) -> None:
        """Unbounded work is not Fast. With checks and no risk it is Tier B, not GPT."""
        self.assertEqual(
            route(make_state(paths=["src/util.py"], files=25)).tier,
            GUARDED_DEEPSEEK,
        )

    def test_missing_candidate_paths_is_not_fast(self) -> None:
        self.assertEqual(route(make_state(paths=[], files=1)).tier, UNCERTAIN)

    def test_bounded_file_limit_is_a_named_policy_knob(self) -> None:
        """The limit is an uncalibrated placeholder, so it must be overridable."""
        state = make_state(paths=["src/util.py"], files=5)
        self.assertEqual(route(state).tier, GUARDED_DEEPSEEK)
        self.assertEqual(route(state, policy=StaticPolicy(bounded_file_limit=8)).tier, FAST_DEEPSEEK)


class GuardedTierTest(unittest.TestCase):
    """Section 6 Tier B: multi-file but specified, no hard risk, checks exist.

    Section 6 defines Tier B with static conditions, but section 10 only reaches
    GUARDED_DEEPSEEK inside the Jev branch, so the two sections disagree. This
    implementation follows section 6 and exposes the disagreement as a named
    policy knob rather than picking silently.

    The hard part is "clearly specified": it is a semantic judgement, not a path,
    a flag, or a file count. ``guarded_requires_known_scope`` is where that
    ambiguity is made explicit.
    """

    def test_multi_file_with_known_scope_and_checks_is_guarded(self) -> None:
        decision = route(make_state(paths=["src/a.py", "src/b.py"], files=6))
        self.assertEqual(decision.tier, GUARDED_DEEPSEEK)

    def test_unknown_scope_is_not_guarded_by_default(self) -> None:
        """A request naming no path cannot distinguish 'multi-file' from 'unknown'."""
        self.assertEqual(route(make_state(paths=[], files=0)).tier, UNCERTAIN)

    def test_unknown_scope_becomes_guarded_when_policy_allows_it(self) -> None:
        policy = StaticPolicy(guarded_requires_known_scope=False)
        decision = route(make_state(paths=[], files=0), policy=policy)
        self.assertEqual(decision.tier, GUARDED_DEEPSEEK)

    def test_no_deterministic_checks_cannot_be_guarded(self) -> None:
        """Without a runnable check there is no safety net, so Guarded is unavailable."""
        decision = route(make_state(paths=["src/a.py"], files=6, test_commands=()))
        self.assertEqual(decision.tier, UNCERTAIN)

    def test_hard_static_override_outranks_guarded(self) -> None:
        decision = route(make_state(paths=["src/auth/x.py"], files=6))
        self.assertEqual(decision.tier, EXPERT_GPT)

    def test_semantic_risk_outranks_guarded(self) -> None:
        decision = route(
            make_state(paths=["src/a.py"], files=6, risk_signals=["concurrency"])
        )
        self.assertEqual(decision.tier, UNCERTAIN)

    def test_bounded_task_stays_fast_rather_than_guarded(self) -> None:
        self.assertEqual(route(make_state(paths=["src/a.py"], files=1)).tier, FAST_DEEPSEEK)

    def test_guarded_needs_no_model_evaluation(self) -> None:
        """Tier B is a static verdict: DeepSeek executes under strict verification."""
        decision = route(make_state(paths=["src/a.py"], files=6))
        self.assertFalse(decision.needs_model_evaluation)

    def test_tiers_are_four_distinct_values(self) -> None:
        self.assertEqual(
            {EXPERT_GPT, FAST_DEEPSEEK, GUARDED_DEEPSEEK, UNCERTAIN},
            {"expert_gpt", "fast_deepseek", "guarded_deepseek", "uncertain"},
        )


class SemanticRiskGateTest(unittest.TestCase):
    """Section 6 semantic risks must reach the model layer, not the fast tier.

    Section 6 puts concurrency, material ambiguity, and unclear root cause in
    Tier C, but section 9's fast gate only sees paths and flags. Without this
    channel, benchmark task C08 (a real concurrency bug in two innocuous files)
    routes fast -- the false-cheap error section 11 calls the expensive one.
    """

    def test_declared_semantic_risk_beats_every_fast_condition(self) -> None:
        """The exact C08 shape: bounded, accepted, verified, but concurrent."""
        decision = route(
            make_state(
                paths=["src/pi_agent/sync.py", "tests/test_sync.py", "docs/rpc.md"],
                files=3,
                risk_signals=["concurrency"],
            )
        )
        self.assertEqual(decision.tier, UNCERTAIN)
        self.assertTrue(decision.needs_model_evaluation)

    def test_hard_static_override_still_outranks_semantic_risk(self) -> None:
        decision = route(
            make_state(
                paths=["src/auth/session.py"],
                risk_signals=["concurrency"],
            )
        )
        self.assertEqual(decision.tier, EXPERT_GPT)

    def test_absent_risk_signals_do_not_change_existing_behaviour(self) -> None:
        self.assertEqual(route(make_state(paths=["src/util.py"])).tier, FAST_DEEPSEEK)
        self.assertEqual(
            route(make_state(paths=["src/util.py"], risk_signals=[])).tier,
            FAST_DEEPSEEK,
        )

    def test_reason_names_the_declared_signals(self) -> None:
        decision = route(
            make_state(paths=["src/util.py"], risk_signals=["concurrency", "unclear_root_cause"])
        )
        self.assertIn("concurrency", decision.reason)
        self.assertIn("unclear_root_cause", decision.reason)

    def test_semantic_risk_is_reported_as_its_own_rule(self) -> None:
        decision = route(make_state(paths=["src/util.py"], risk_signals=["concurrency"]))
        self.assertIn("semantic_risk:concurrency", decision.matched_rules)

    def test_semantic_risk_does_not_mask_a_fast_gate_miss(self) -> None:
        """Both reasons must survive, so the log explains the whole verdict."""
        decision = route(
            make_state(paths=["src/util.py"], files=99, risk_signals=["concurrency"])
        )
        self.assertEqual(decision.tier, UNCERTAIN)
        self.assertIn("bounded_file_ownership", decision.reason)


class ContractTest(unittest.TestCase):
    """The decision is a pure value and never mutates its input."""

    def test_same_state_yields_same_decision(self) -> None:
        state = make_state(paths=["src/util.py"])
        self.assertEqual(route(state), route(state))

    def test_route_does_not_mutate_input(self) -> None:
        import copy

        state = make_state(paths=["src/auth/session.py"], flags={"auth": True})
        snapshot = copy.deepcopy(state)
        route(state)
        self.assertEqual(state, snapshot)

    def test_uncertain_is_the_only_tier_needing_model_evaluation(self) -> None:
        self.assertTrue(route(make_state(paths=[], files=1)).needs_model_evaluation)
        self.assertFalse(route(make_state(paths=["src/util.py"])).needs_model_evaluation)
        self.assertFalse(route(make_state(flags={"auth": True})).needs_model_evaluation)

    def test_every_decision_carries_a_reason_and_rule_ids(self) -> None:
        for state in (
            make_state(paths=["src/util.py"]),
            make_state(flags={"auth": True}),
            make_state(paths=[], files=1),
        ):
            with self.subTest(tier=state):
                decision = route(state)
                self.assertTrue(decision.reason)
                self.assertTrue(decision.matched_rules)

    def test_tiers_are_the_three_declared_values(self) -> None:
        self.assertEqual({EXPERT_GPT, FAST_DEEPSEEK, UNCERTAIN}, {"expert_gpt", "fast_deepseek", "uncertain"})


if __name__ == "__main__":
    unittest.main()
