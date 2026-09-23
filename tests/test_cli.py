"""Acceptance tests for the routing CLI and its tier-to-model mapping.

A launcher acts on this output, so two things must hold: every tier the router
can return has a model, and the mapping is the one the design intends. The
completeness test is the important one -- it fails if a new tier is added without
a model, rather than letting a launcher pick an undefined value at runtime.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.cli import TIER_MODEL, build_parser, decide, main  # noqa: E402
from router.static_router import (  # noqa: E402
    EXPERT_GPT,
    FAST_DEEPSEEK,
    GUARDED_DEEPSEEK,
    UNCERTAIN,
)

BOUNDED = "**Safe zone:** `data/agent/recipes.json` only. Keep it minimal.\n"
CONCURRENT = "**Safe zone:** `data/agent/recipes.json` only. Avoid the race condition.\n"


class MappingTest(unittest.TestCase):
    def test_every_tier_has_a_model(self) -> None:
        self.assertEqual(
            set(TIER_MODEL),
            {FAST_DEEPSEEK, GUARDED_DEEPSEEK, UNCERTAIN, EXPERT_GPT},
        )

    def test_deepseek_tiers_select_the_workhorse(self) -> None:
        self.assertEqual(TIER_MODEL[FAST_DEEPSEEK], "deepseek/deepseek-v4-flash")
        self.assertEqual(TIER_MODEL[GUARDED_DEEPSEEK], "deepseek/deepseek-v4-flash")

    def test_gpt_tiers_select_the_expert(self) -> None:
        self.assertEqual(TIER_MODEL[EXPERT_GPT], "openai/gpt-5.6-sol")
        self.assertEqual(TIER_MODEL[UNCERTAIN], "openai/gpt-5.6-sol")


class DecideTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (self.repo / "data" / "agent").mkdir(parents=True)
        (self.repo / "data" / "agent" / "recipes.json").write_text("{}", encoding="utf-8")
        self.request = self.repo / "req.md"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_request(self, text: str) -> None:
        self.request.write_text(text, encoding="utf-8")

    def test_bounded_request_selects_deepseek(self) -> None:
        self.write_request(BOUNDED)
        result = decide(str(self.request), str(self.repo))
        self.assertEqual(result["tier"], FAST_DEEPSEEK)
        self.assertEqual(result["model"], "deepseek/deepseek-v4-flash")

    def test_semantic_risk_selects_gpt(self) -> None:
        self.write_request(CONCURRENT)
        result = decide(str(self.request), str(self.repo))
        self.assertEqual(result["model"], "openai/gpt-5.6-sol")

    def test_result_carries_the_evidence_a_launcher_logs(self) -> None:
        self.write_request(BOUNDED)
        result = decide(str(self.request), str(self.repo))
        for key in ("tier", "model", "reason", "rules", "risk_signals", "candidate_paths", "test_commands"):
            self.assertIn(key, result)

    def test_request_text_never_appears_in_the_result(self) -> None:
        """Section 17 forbids logging raw prompts, and this result is what gets logged."""
        self.write_request(BOUNDED)
        result = decide(str(self.request), str(self.repo))
        self.assertNotIn("Safe zone", json.dumps(result))

    def test_tier_b_policy_is_selectable(self) -> None:
        self.write_request("Add a helper somewhere in the codebase.\n")
        conservative = decide(str(self.request), str(self.repo), "conservative")
        broad = decide(str(self.request), str(self.repo), "broad")
        self.assertNotEqual(conservative["tier"], broad["tier"])
        self.assertEqual(broad["tier"], GUARDED_DEEPSEEK)


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (self.repo / "data" / "agent").mkdir(parents=True)
        (self.repo / "data" / "agent" / "recipes.json").write_text("{}", encoding="utf-8")
        self.request = self.repo / "req.md"
        self.request.write_text(BOUNDED, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_output_is_the_bare_tier(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--request-file", str(self.request), "--repo", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().strip(), FAST_DEEPSEEK)

    def test_json_output_is_valid_json(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            main(["--request-file", str(self.request), "--repo", str(self.repo), "--json"])
        self.assertEqual(json.loads(buffer.getvalue())["tier"], FAST_DEEPSEEK)

    def test_missing_request_file_is_a_clean_error(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--request-file", str(self.repo / "nope.md"), "--repo", str(self.repo)])
        self.assertEqual(code, 2)

    def test_parser_rejects_an_unknown_tier_b_policy(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(
                ["--request-file", "x", "--repo", "y", "--tier-b", "whatever"]
            )


if __name__ == "__main__":
    unittest.main()
