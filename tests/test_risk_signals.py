"""Acceptance tests for the deterministic risk-signal scanner.

Spec: docs/research/2026-09-19-jev-risk-routed-hybrid-core.md, sections 6 and 9.

Section 6 puts concurrency, material ambiguity, and unclear root cause in Tier C,
but section 9's fast gate can only see paths and declared flags. That gap is how
a real concurrency bug (benchmark task C08) reached the fast tier. This scanner is
the missing channel: a deterministic, model-free read of the request that declares
the semantic risk the path rules cannot see.

The scanner is deliberately conservative in vocabulary and generous in effect:
a matched signal defers to the model layer, which costs latency, while a missed
signal under-routes, which section 11 calls the expensive direction.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.risk_signals import (  # noqa: E402
    CONTRACT_SIGNALS,
    SIGNALS,
    scan_contract_signals,
    scan_risk_signals,
)

# A faithful excerpt of the real C08 request. It never says "concurrency": the
# signal words are starvation, scheduling, coalesced, and races. A scanner keyed
# on the category name would miss the very task that motivated this module.
C08_EXCERPT = """
fix(events): avoid internal queue starvation on finite output bursts

Fast valid RPC output can overflow the SDK's internal event queue before a ready
consumer gets enough execution time. The behavior remains after the
pre-acknowledgement fix in PR #33.

Separate scheduling starvation from actual sustained consumer overload.
Preserve framing across yields and handle EOF/exit/close races without duplicate
or partially parsed records.
"""

CLEAN_REQUEST = """
Add a `--json-output` flag to the recipes CLI command. It should serialise the
existing recipe list as JSON and print it to stdout. Update the README section
that documents the command, and add a test that asserts the flag is accepted.
"""


class SignalDetectionTest(unittest.TestCase):
    def test_real_c08_request_yields_the_concurrency_signal(self) -> None:
        self.assertIn("concurrency", scan_risk_signals(C08_EXCERPT))

    def test_clean_bounded_request_yields_no_signals(self) -> None:
        self.assertEqual(scan_risk_signals(CLEAN_REQUEST), ())

    def test_concurrency_markers(self) -> None:
        for text in (
            "There is a race condition in the worker.",
            "The queue can starve under load.",
            "This deadlocks when two writers hold the lock.",
            "Fix the coalesced burst handling.",
            "Make the counter update atomic.",
            "The test is nondeterministic.",
        ):
            with self.subTest(text=text):
                self.assertIn("concurrency", scan_risk_signals(text))

    def test_ambiguity_markers(self) -> None:
        for text in (
            "The requirement is ambiguous here.",
            "It is unclear which of the two behaviours is intended.",
            "The spec is unspecified for this case.",
        ):
            with self.subTest(text=text):
                self.assertIn("ambiguous_requirements", scan_risk_signals(text))

    def test_unclear_root_cause_markers(self) -> None:
        for text in (
            "The failure is intermittent.",
            "This test is flaky.",
            "Find the root cause before changing anything.",
        ):
            with self.subTest(text=text):
                self.assertIn("unclear_root_cause", scan_risk_signals(text))

    def test_multiple_signals_are_reported_together(self) -> None:
        signals = scan_risk_signals("The flaky test has a race condition.")
        self.assertIn("concurrency", signals)
        self.assertIn("unclear_root_cause", signals)

    def test_matching_is_case_insensitive(self) -> None:
        self.assertEqual(scan_risk_signals("RACE CONDITION"), scan_risk_signals("race condition"))

    def test_output_is_deterministic_and_stable_ordered(self) -> None:
        first = scan_risk_signals(C08_EXCERPT)
        second = scan_risk_signals(C08_EXCERPT)
        self.assertEqual(first, second)
        self.assertEqual(first, tuple(s for s in SIGNALS if s in first))

    def test_scan_does_not_mutate_and_handles_empty(self) -> None:
        self.assertEqual(scan_risk_signals(""), ())
        self.assertEqual(scan_risk_signals("   "), ())

    def test_declared_signal_vocabulary_is_small_and_named(self) -> None:
        self.assertEqual(
            set(SIGNALS),
            {"concurrency", "ambiguous_requirements", "unclear_root_cause"},
        )


#: Benchmark task C06 asks for plugin loading "through a documented standard
#: interface". Section 9 makes a shared-contract change a hard expert override,
#: but the path rules cannot see a contract, so this is the second class of
#: semantic risk the static layer was missing.
C06_EXCERPT = """
Custom parser plugins load from user and project parser directories through a
documented standard interface. The CLI can list and explicitly select built-in
and plugin parsers, with clear validation errors.
"""


class ContractSignalTest(unittest.TestCase):
    """Shared-contract signals are expert overrides, not model-evaluation deferrals."""

    def test_real_c06_request_yields_a_contract_signal(self) -> None:
        self.assertIn("public_interface", scan_contract_signals(C06_EXCERPT))

    def test_clean_bounded_request_yields_no_contract_signal(self) -> None:
        self.assertEqual(scan_contract_signals(CLEAN_REQUEST), ())

    def test_contract_markers(self) -> None:
        for text in (
            "This changes the public API.",
            "Introduce a documented standard interface for plugins.",
            "This is a breaking change for callers.",
            "Keep backwards compatibility with the old wire format.",
            "The shared schema gains a column.",
        ):
            with self.subTest(text=text):
                self.assertIn("public_interface", scan_contract_signals(text))

    def test_bare_word_interface_is_not_a_contract(self) -> None:
        """A common word must not become an expert override on its own."""
        self.assertEqual(scan_contract_signals("Tidy up the interface of this helper."), ())

    def test_contract_signals_are_separate_from_semantic_signals(self) -> None:
        """The two classes route differently, so they must not be conflated."""
        self.assertNotIn("public_interface", SIGNALS)
        self.assertEqual(set(CONTRACT_SIGNALS), {"public_interface"})
        self.assertEqual(scan_risk_signals(C06_EXCERPT), ())

    def test_deterministic(self) -> None:
        self.assertEqual(scan_contract_signals(C06_EXCERPT), scan_contract_signals(C06_EXCERPT))


if __name__ == "__main__":
    unittest.main()
